"""Fire the real registered schedules early against existing public evidence.

Run only when this company's API jobs are idle. Production cadence is unchanged.
Uses actual HTTP/LLM providers, no fixtures, and preserves job/brief history.
"""
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from apscheduler.triggers.date import DateTrigger
from app.db import Database
from app.jobs import Jobs
from app.llm import LLM
from app.services import Engine

def main():
    load_dotenv()
    db = Database()
    cid = 1
    assert not db.one("SELECT id FROM job_logs WHERE company_id=? AND status IN ('queued','running')", (cid,))
    jobs = Jobs(db, Engine(db, LLM(db)))
    jobs.scheduler.start()
    jobs.configure(cid)
    report = {'synthetic': False, 'company_id': cid, 'trigger': 'Registered APScheduler jobs temporarily advanced in a separate evaluation process; saved production settings unchanged', 'runs': []}
    target = Path('output/assignment-audit/live-scheduler.json')
    try:
        for kind in ('weekly', 'audit'):
            previous = db.one('SELECT COALESCE(MAX(id),0) id FROM job_logs')['id']
            jobs.scheduler.reschedule_job(f'{cid}:{kind}', trigger=DateTrigger(run_date=datetime.now(timezone.utc)+timedelta(seconds=1)))
            print('Scheduled', kind, flush=True)
            deadline = time.monotonic()+1800
            while time.monotonic() < deadline:
                row = db.one('SELECT * FROM job_logs WHERE id>? AND company_id=? AND kind=? ORDER BY id DESC LIMIT 1', (previous,cid,kind))
                if row and row['status'] not in ('queued','running'):
                    row['result'] = json.loads(row['result']) if row['result'] else None
                    report['runs'].append(row)
                    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
                    print(kind,row['status'],flush=True)
                    break
                time.sleep(2)
            else:
                raise RuntimeError('Scheduled operation timed out')
    finally:
        jobs.stop()


if __name__ == '__main__':
    main()
