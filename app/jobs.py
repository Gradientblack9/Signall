import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .db import now
from .services import safe_error


class Jobs:
    def __init__(self, db, engine):
        self.db, self.engine = db, engine
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='signal-job')
        self.scheduler = BackgroundScheduler(job_defaults={'coalesce': True, 'max_instances': 1, 'misfire_grace_time': 3600})
        self.lock = threading.Lock()
        self.active = set()

    def start(self):
        self.db.run("UPDATE job_logs SET status='failed',finished_at=?,error='Process stopped before this job finished; run it again.' WHERE status IN ('running','queued')", (now(),))
        if os.getenv('SIGNAL_SCHEDULER', 'true').lower() == 'true':
            self.scheduler.start()
            for company in self.db.all('SELECT id FROM companies'):
                self.configure(company['id'])

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.pool.shutdown(wait=True, cancel_futures=True)

    def configure(self, company_id):
        if not self.scheduler.running:
            return
        settings = self.db.settings(company_id)
        hour, minute = map(int, settings['brief_time'].split(':'))
        specs = {
            'weekly': CronTrigger(day_of_week=settings['brief_day'], hour=hour, minute=minute, timezone=settings['timezone']),
            'audit': CronTrigger(day=settings['audit_day'], hour=hour, minute=minute, timezone=settings['timezone']),
            'crawl': IntervalTrigger(hours=settings['crawl_hours']),
            'refresh': IntervalTrigger(days=settings['refresh_days']),
        }
        for kind, trigger in specs.items():
            self.scheduler.add_job(self.submit, trigger, args=[company_id, kind], id=f'{company_id}:{kind}', replace_existing=True)

    def schedules(self, company_id):
        if not self.scheduler.running:
            return []
        return [{'id': j.id, 'next_run': j.next_run_time.isoformat(), 'trigger': str(j.trigger)}
                for j in self.scheduler.get_jobs() if j.id.startswith(f'{company_id}:')]

    def submit(self, company_id, kind):
        allowed = {'research', 'discover', 'crawl', 'analyze', 'brief', 'weekly', 'audit', 'reassess', 'refresh'}
        if kind not in allowed:
            raise ValueError('Unknown job type')
        self.db.company(company_id)
        with self.lock:
            if company_id in self.active:
                # Preserve scheduler collision evidence instead of silently losing the event.
                jid = self.db.insert('job_logs', company_id=company_id, kind=kind, status='skipped',
                    started_at=now(), finished_at=now(), error='Another operation is active for this company; retry after it completes.')
                return {'job_id': jid, 'status': 'skipped'}
            self.active.add(company_id)
            jid = self.db.insert('job_logs', company_id=company_id, kind=kind, status='queued', started_at=now())
        self.pool.submit(self.execute, jid, company_id, kind)
        return {'job_id': jid, 'status': 'queued'}

    def execute(self, job_id, company_id, kind):
        self.db.run("UPDATE job_logs SET status='running' WHERE id=?", (job_id,))
        try:
            if kind == 'weekly':
                result = {'crawl': self.engine.crawl(company_id), 'analysis': self.engine.analyze(company_id),
                          'brief': self.engine.brief(company_id)}
            elif kind == 'refresh':
                result = {'discovery': self.engine.discover(company_id), 'reassessment': self.engine.reassess(company_id)}
            elif kind == 'reassess':
                result = self.engine.context_change(company_id)
            else:
                result = getattr(self.engine, kind)(company_id)
            partial = self.has_errors(result)
            self.db.run('UPDATE job_logs SET status=?,finished_at=?,result=? WHERE id=?',
                ('partial' if partial else 'success', now(), json.dumps(result), job_id))
        except Exception as exc:
            self.db.run("UPDATE job_logs SET status='failed',finished_at=?,error=? WHERE id=?", (now(), safe_error(exc), job_id))
        finally:
            with self.lock:
                self.active.discard(company_id)

    @classmethod
    def has_errors(cls, value):
        if isinstance(value, dict):
            return bool(value.get('error') or value.get('failures') or value.get('limitations')) or any(cls.has_errors(v) for v in value.values())
        if isinstance(value, list):
            return any(cls.has_errors(v) for v in value)
        return False
