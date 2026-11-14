import hmac
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import Database, now
from .exports import brief_html, brief_pdf
from .jobs import Jobs
from .llm import LLM, LLMUnavailable
from .models import Category, Profile, Question
from .network import canonical_url
from .services import Engine
from .filtering import filter_signals

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent


class CompanyInput(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    url: str = Field(max_length=2000)


class SourceInput(BaseModel):
    url: str = Field(max_length=2000)
    name: str = Field(min_length=1, max_length=200)
    category: Category
    reason: str = Field(min_length=1, max_length=2000)


class SourceUpdate(BaseModel):
    status: Literal['discovered', 'approved', 'rejected']


class AnswerInput(BaseModel):
    answer: str = Field(default='', max_length=10000)
    skipped: bool = False


class SettingsInput(BaseModel):
    timezone: str = 'Asia/Kolkata'
    brief_day: Literal['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] = 'mon'
    brief_time: str = Field(default='09:00', pattern=r'^([01]\d|2[0-3]):[0-5]\d$')
    crawl_hours: int = Field(default=24, ge=1, le=720)
    refresh_days: int = Field(default=30, ge=1, le=365)
    audit_day: int = Field(default=1, ge=1, le=28)
    max_sources_per_run: int = Field(default=40, ge=1, le=100)
    request_delay: float = Field(default=1, ge=1, le=30)


class ActionInput(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    signal_id: int | None = None
    owner: str = Field(default='', max_length=200)
    due_date: str | None = None
    status: Literal['open', 'in_progress', 'done', 'dismissed'] = 'open'


class VerificationInput(BaseModel):
    verified: bool
    note: str = Field(min_length=10, max_length=2000)


def create_app(database=None, llm=None, fetcher=None, scheduler=True):
    db = database or Database()
    llm = llm or LLM(db)
    engine = Engine(db, llm, fetcher)
    jobs = Jobs(db, engine)

    @asynccontextmanager
    async def lifespan(app):
        if scheduler:
            jobs.start()
        yield
        jobs.stop()

    app = FastAPI(title='Signal Stack', version='1.0.0', lifespan=lifespan)
    app.state.db, app.state.engine, app.state.jobs = db, engine, jobs

    @app.middleware('http')
    async def protect(request: Request, call_next):
        token = os.getenv('SIGNAL_ACCESS_TOKEN', '')
        if token and request.url.path.startswith('/api'):
            provided = request.headers.get('authorization', '').removeprefix('Bearer ')
            if not hmac.compare_digest(provided, token):
                return JSONResponse({'detail': 'Access token required'}, status_code=401)
        origin = request.headers.get('origin')
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc != request.headers.get('host'):
                return JSONResponse({'detail': 'Cross-origin writes are not allowed'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=400)

    @app.exception_handler(LLMUnavailable)
    async def unavailable(request, exc):
        return JSONResponse({'detail': str(exc)}, status_code=503)

    def company(cid):
        if not db.one('SELECT id FROM companies WHERE id=?', (cid,)):
            raise HTTPException(404, 'Company not found')
        return db.company(cid)

    def idle(cid):
        company(cid)
        with jobs.lock:
            if cid in jobs.active:
                raise HTTPException(409, 'A job is running for this company. Wait until it completes before editing context or sources.')

    @app.get('/health')
    def health():
        db.one('SELECT 1')
        return {'status': 'ok', 'database': 'sqlite', 'llm': llm.status(), 'scheduler': jobs.scheduler.running}

    @app.post('/api/llm/test')
    def llm_test():
        result = llm.ask('Connection test. Set question to "Connection verified" and why to the model purpose.', {}, Question)
        return {'status': 'ok', 'response': result.model_dump()}

    @app.get('/api/companies')
    def companies():
        return db.all('SELECT id,name,url,context_version,created_at FROM companies ORDER BY id')

    @app.post('/api/companies', status_code=201)
    def add_company(body: CompanyInput):
        url = canonical_url(body.url)
        cid = db.insert('companies', name=body.name.strip(), url=url, created_at=now(), updated_at=now())
        jobs.configure(cid)
        return db.company(cid)

    @app.get('/api/companies/{cid}')
    def get_company(cid: int):
        return company(cid) | {'answers': db.all('SELECT * FROM profile_answers WHERE company_id=? ORDER BY position', (cid,))}

    @app.put('/api/companies/{cid}/profile')
    def update_profile(cid: int, body: Profile):
        idle(cid)
        result = engine.update_profile(cid, body.model_dump())
        return result | {'job': jobs.submit(cid, 'reassess')}

    @app.get('/api/companies/{cid}/overview')
    def overview(cid: int):
        c = company(cid)
        counts = {table: db.one(f'SELECT COUNT(*) n FROM {table} WHERE company_id=?', (cid,))['n']
                  for table in ('sources', 'documents', 'signals', 'briefs', 'actions')}
        counts['approved'] = db.one("SELECT COUNT(*) n FROM sources WHERE company_id=? AND status='approved'", (cid,))['n']
        return {'company': c, 'counts': counts, 'signals': sorted(engine.signals(cid), key=lambda s: s['score'], reverse=True)[:5],
            'jobs': db.all('SELECT * FROM job_logs WHERE company_id=? ORDER BY id DESC LIMIT 5', (cid,)),
            'schedules': jobs.schedules(cid), 'llm': llm.status()}

    @app.post('/api/companies/{cid}/jobs/{kind}', status_code=202)
    def submit(cid: int, kind: str):
        company(cid)
        return jobs.submit(cid, kind)

    @app.get('/api/companies/{cid}/jobs')
    def logs(cid: int):
        company(cid)
        rows = db.all('SELECT * FROM job_logs WHERE company_id=? ORDER BY id DESC LIMIT 100', (cid,))
        for row in rows:
            row['result'] = json.loads(row['result']) if row['result'] else None
        return {'logs': rows, 'schedules': jobs.schedules(cid)}

    @app.post('/api/companies/{cid}/interview/next')
    def next_question(cid: int):
        idle(cid)
        return engine.next_question(cid)

    @app.put('/api/companies/{cid}/interview/{aid}')
    def answer(cid: int, aid: int, body: AnswerInput):
        idle(cid)
        existing = db.one('SELECT * FROM profile_answers WHERE company_id=? AND id=?', (cid, aid))
        if not existing:
            raise HTTPException(404, 'Question not found')
        if not body.skipped and not body.answer.strip():
            raise ValueError('Write an answer or choose Skip')
        with db.connect() as conn:
            conn.execute('UPDATE profile_answers SET answer=?,skipped=?,updated_at=? WHERE id=?', (body.answer, int(body.skipped), now(), aid))
            conn.execute('UPDATE companies SET context_version=context_version+1,updated_at=? WHERE id=?', (now(), cid))
            conn.execute("UPDATE sources SET stale=1 WHERE company_id=? AND status!='rejected'", (cid,))
            conn.execute('INSERT INTO context_changes (company_id,before_profile,after_profile,diff,created_at) VALUES (?,?,?,?,?)',
                (cid, json.dumps(existing), body.model_dump_json(), json.dumps({'type': 'answer', 'question': existing['question'], 'before': existing['answer'], 'after': body.answer, 'skipped': body.skipped}), now()))
        return {'saved': True, 'context_updated': True, 'note': 'Run Reassess context after completing or editing the interview.'}

    @app.post('/api/companies/{cid}/interview/{aid}/follow-up')
    def follow_up(cid: int, aid: int):
        idle(cid)
        return engine.follow_up(cid, aid)

    @app.get('/api/companies/{cid}/sources')
    def sources(cid: int):
        company(cid)
        rows = db.all('SELECT * FROM sources WHERE company_id=? ORDER BY relevance DESC,id DESC', (cid,))
        from urllib.parse import urlsplit
        domains = {}
        for row in rows:
            host = urlsplit(row['url']).hostname
            domains.setdefault(host, []).append(row['id'])
        for row in rows:
            row['possible_duplicates'] = [i for i in domains[urlsplit(row['url']).hostname] if i != row['id']]
        return rows

    @app.post('/api/companies/{cid}/sources', status_code=201)
    def add_source(cid: int, body: SourceInput):
        idle(cid)
        sid, fresh = engine.add_source(cid, **body.model_dump())
        return {'id': sid, 'created': fresh, 'duplicate': not fresh}

    @app.patch('/api/companies/{cid}/sources/{sid}')
    def update_source(cid: int, sid: int, body: SourceUpdate):
        idle(cid)
        if not db.one('SELECT id FROM sources WHERE id=? AND company_id=?', (sid, cid)):
            raise HTTPException(404, 'Source not found')
        db.run('UPDATE sources SET status=? WHERE id=? AND company_id=?', (body.status, sid, cid))
        return {'saved': True}

    @app.delete('/api/companies/{cid}/sources/{sid}')
    def delete_source(cid: int, sid: int):
        idle(cid)
        db.run('DELETE FROM sources WHERE id=? AND company_id=?', (sid, cid))
        return {'deleted': True}

    @app.get('/api/companies/{cid}/sources/{sid}/history')
    def source_history(cid: int, sid: int):
        company(cid)
        return db.all('SELECT * FROM crawl_runs WHERE company_id=? AND source_id=? ORDER BY id DESC LIMIT 50', (cid, sid))

    @app.get('/api/companies/{cid}/documents')
    def documents(cid: int):
        company(cid)
        return db.all('SELECT id,source_id,url,title,published_at,discovered_at,kind,previous_id,substr(content,1,500) snippet FROM documents WHERE company_id=? ORDER BY id DESC LIMIT 200', (cid,))

    @app.post('/api/companies/{cid}/intake')
    async def intake(cid: int, file: UploadFile):
        idle(cid)
        content = await file.read(10_000_001)
        if len(content) > 10_000_000:
            raise HTTPException(413, 'File exceeds 10 MB limit')
        from starlette.concurrency import run_in_threadpool
        return await run_in_threadpool(engine.intake, cid, file.filename or 'upload.txt', content)

    @app.get('/api/companies/{cid}/internal/{upload_hash}')
    def internal_evidence(cid: int, upload_hash: str):
        company(cid)
        prefix = f'/api/companies/{cid}/internal/{upload_hash}#'
        records = db.all('SELECT id,title,content,url FROM documents WHERE company_id=? AND kind=\'internal\' AND url LIKE ?', (cid, prefix+'%'))
        if not records:
            raise HTTPException(404, 'Internal evidence not found')
        return {'records': records}

    @app.get('/api/companies/{cid}/signals')
    def signals(cid: int, category: str = '', sentiment: str = '', urgency: str = '', q: str = '',
                min_score: float = Query(0, ge=0, le=100), competitor: str = '', date_from: str = '', date_to: str = '',
                min_relevance: float = Query(0, ge=0, le=1), min_impact: float = Query(0, ge=0, le=1),
                verification: Literal['', 'verified', 'unverified', 'quote_matched'] = '',
                sort: Literal['latest', 'oldest', 'importance'] = 'latest'):
        profile = company(cid)['profile']
        return filter_signals(engine.signals(cid), category=category, sentiment=sentiment, urgency=urgency,
            q=q, min_score=min_score, competitor=competitor, date_from=date_from, date_to=date_to,
            min_relevance=min_relevance, min_impact=min_impact, verification=verification, sort=sort,
            competitors=profile.get('competitors', []))

    @app.patch('/api/companies/{cid}/signals/{sid}/verification')
    def verify_signal(cid: int, sid: int, body: VerificationInput):
        idle(cid)
        row = db.one('SELECT evidence FROM signals WHERE company_id=? AND id=?', (cid, sid))
        if not row:
            raise HTTPException(404, 'Signal not found')
        evidence = json.loads(row['evidence'])
        evidence.update(verified=body.verified, user_reviewed=True, reviewed_at=now(), verification=body.note)
        db.run('UPDATE signals SET evidence=? WHERE id=? AND company_id=?', (json.dumps(evidence), sid, cid))
        return {'saved': True, 'evidence': evidence}

    @app.get('/api/companies/{cid}/briefs')
    def briefs(cid: int):
        company(cid)
        return db.all('SELECT id,title,context_version,created_at FROM briefs WHERE company_id=? ORDER BY id DESC', (cid,))

    @app.get('/api/companies/{cid}/briefs/{bid}')
    def brief_detail(cid: int, bid: int):
        company(cid)
        row = db.one('SELECT * FROM briefs WHERE company_id=? AND id=?', (cid, bid))
        if not row:
            raise HTTPException(404, 'Brief not found')
        row['sections'] = json.loads(row['sections'])
        return row

    @app.get('/api/companies/{cid}/briefs/{bid}/export/{format}')
    def export(cid: int, bid: int, format: Literal['md', 'html', 'pdf'], request: Request):
        company(cid)
        row = db.one('SELECT * FROM briefs WHERE company_id=? AND id=?', (cid, bid))
        if not row:
            raise HTTPException(404, 'Brief not found')
        sections = json.loads(row['sections'])
        for section in sections:
            for item in section['items']:
                for field in ('url', 'original_source'):
                    value = item.get(field, '')
                    if value.startswith('/'):
                        absolute = str(request.base_url).rstrip('/') + value
                        row['markdown'] = row['markdown'].replace(value, absolute)
                        item[field] = absolute
        row['sections'] = json.dumps(sections)
        content = row['markdown'] if format == 'md' else brief_html(row) if format == 'html' else brief_pdf(row)
        media = {'md': 'text/markdown', 'html': 'text/html', 'pdf': 'application/pdf'}[format]
        return Response(content, media_type=media, headers={'Content-Disposition': f'attachment; filename="signal-brief-{bid}.{format}"'})

    @app.get('/api/companies/{cid}/actions')
    def actions(cid: int):
        company(cid)
        return db.all('SELECT * FROM actions WHERE company_id=? ORDER BY id DESC', (cid,))

    def action_values(cid, body):
        if body.signal_id and not db.one('SELECT id FROM signals WHERE company_id=? AND id=?', (cid, body.signal_id)):
            raise ValueError('Signal does not belong to this company')
        if body.due_date:
            try:
                datetime.strptime(body.due_date, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Due date must be YYYY-MM-DD') from None
        return body.model_dump()

    @app.post('/api/companies/{cid}/actions', status_code=201)
    def add_action(cid: int, body: ActionInput):
        company(cid)
        aid = db.insert('actions', company_id=cid, **action_values(cid, body), created_at=now(), updated_at=now())
        return {'id': aid}

    @app.put('/api/companies/{cid}/actions/{aid}')
    def update_action(cid: int, aid: int, body: ActionInput):
        company(cid)
        if not db.one('SELECT id FROM actions WHERE id=? AND company_id=?', (aid, cid)):
            raise HTTPException(404, 'Action not found')
        values = action_values(cid, body)
        db.run('UPDATE actions SET title=?,signal_id=?,owner=?,due_date=?,status=?,updated_at=? WHERE id=? AND company_id=?',
            (values['title'],values['signal_id'],values['owner'],values['due_date'],values['status'],now(),aid,cid))
        return {'saved': True}

    @app.get('/api/companies/{cid}/settings')
    def settings(cid: int):
        company(cid)
        return db.settings(cid) | {'schedules': jobs.schedules(cid)}

    @app.put('/api/companies/{cid}/settings')
    def update_settings(cid: int, body: SettingsInput):
        company(cid)
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise ValueError('Unknown IANA timezone') from None
        db.run('INSERT OR REPLACE INTO settings VALUES (?,?)', (cid, body.model_dump_json()))
        jobs.configure(cid)
        return {'saved': True, 'schedules': jobs.schedules(cid)}

    @app.get('/api/companies/{cid}/context-changes')
    def changes(cid: int):
        company(cid)
        rows = db.all('SELECT * FROM context_changes WHERE company_id=? ORDER BY id DESC LIMIT 50', (cid,))
        for row in rows:
            row['diff'] = json.loads(row['diff'])
        return rows

    app.mount('/static', StaticFiles(directory=ROOT/'static'), name='static')

    @app.get('/')
    def index():
        return FileResponse(ROOT/'static'/'index.html')

    return app


app = create_app()
