import json
import time

import pytest
from fastapi.testclient import TestClient

from app.db import Database
from app.llm import LLM
from app.main import create_app
from tests.fixtures import FixtureLLM, FixtureWeb


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.delenv('SIGNAL_ACCESS_TOKEN',raising=False)
    db=Database(tmp_path/'api.db')
    app=create_app(db,LLM(db,FixtureLLM()),FixtureWeb(),scheduler=False)
    with TestClient(app) as client:
        yield client,app


def setup_company(client):
    return client.post('/api/companies',json={'name':'MeetUniversity fixture','url':'https://education.example/'}).json()['id']


def wait_job(client,cid,kind):
    response=client.post(f'/api/companies/{cid}/jobs/{kind}');assert response.status_code==202
    jid=response.json()['job_id']
    for _ in range(200):
        job=next(j for j in client.get(f'/api/companies/{cid}/jobs').json()['logs'] if j['id']==jid)
        if job['status'] not in ('queued','running'):return job
        time.sleep(.02)
    raise AssertionError('Job did not complete')


def test_health_and_full_clickable_api_flow(client):
    c,app=client
    assert c.get('/health').json()['status']=='ok'
    assert c.get('/').status_code==200
    assert c.post('/api/llm/test').json()['status']=='ok'
    cid=setup_company(c);root=f'/api/companies/{cid}'
    assert wait_job(c,cid,'research')['status']=='success'
    q=c.post(root+'/interview/next').json()
    assert c.put(root+f'/interview/{q["id"]}',json={'answer':'Improve student onboarding'}).status_code==200
    assert c.post(root+f'/interview/{q["id"]}/follow-up').status_code==200
    assert wait_job(c,cid,'discover')['status']=='success'
    sources=c.get(root+'/sources').json()
    for source in sources:
        assert c.patch(root+f'/sources/{source["id"]}',json={'status':'approved'}).status_code==200
    assert wait_job(c,cid,'crawl')['status']=='success'
    assert c.post(root+'/intake',files={'file':('feedback.txt',b'Customers want simpler forms and transparent pricing.')}).status_code==200
    assert wait_job(c,cid,'analyze')['status']=='success'
    signals=c.get(root+'/signals').json();assert len(signals)>=30
    internal=next(s for s in signals if s['category']=='Internal')
    assert c.get(internal['evidence']['url'].split('#')[0]).status_code==200
    assert wait_job(c,cid,'brief')['status']=='success'
    bid=c.get(root+'/briefs').json()[0]['id']
    for fmt in ['md','html','pdf']:
        r=c.get(root+f'/briefs/{bid}/export/{fmt}');assert r.status_code==200
        assert 'attachment' in r.headers['content-disposition']
    signal=signals[0]
    action=c.post(root+'/actions',json={'title':'Review evidence','signal_id':signal['id'],'owner':'Strategy','due_date':'2026-12-01'}).json()
    assert c.put(root+f'/actions/{action["id"]}',json={'title':'Reviewed evidence','status':'done'}).status_code==200
    assert c.get(root+'/actions').json()[0]['status']=='done'
    assert c.get(root+'/overview').json()['counts']['briefs']==1
    assert c.get(root+'/documents').json()
    assert c.get(root+f'/sources/{sources[0]["id"]}/history').json()


def test_invalid_settings_and_company_scoping(client):
    c,app=client;cid=setup_company(c);root=f'/api/companies/{cid}'
    assert c.put(root+'/settings',json={'timezone':'Not/A_Zone'}).status_code==400
    assert c.put(root+'/settings',json={'brief_time':'25:99'}).status_code==422
    assert c.put(root+'/settings',json={'request_delay':0}).status_code==422
    assert c.put(root+'/settings',json={'timezone':'Asia/Kolkata','brief_time':'08:30'}).status_code==200
    assert c.get(root+'/settings').json()['brief_time']=='08:30'
    assert c.get('/api/companies/999999').status_code==404
    assert c.patch(root+'/sources/9999',json={'status':'approved'}).status_code==404
    assert c.post(root+'/jobs/unknown').status_code==400
    assert c.post(root+'/actions',json={'title':'Bad link','signal_id':9999}).status_code==400
    assert c.post(root+'/actions',json={'title':'Bad date','due_date':'tomorrow'}).status_code==400


def test_auth_and_cross_origin_protection(client,monkeypatch):
    c,app=client
    monkeypatch.setenv('SIGNAL_ACCESS_TOKEN','test-token')
    assert c.get('/api/companies').status_code==401
    assert c.get('/api/companies',headers={'Authorization':'Bearer test-token'}).status_code==200
    assert c.post('/api/companies',json={'name':'Test','url':'https://example.com'},headers={'Authorization':'Bearer test-token','Origin':'https://evil.example'}).status_code==403


def test_failed_job_visible(client,monkeypatch):
    c,app=client;cid=setup_company(c)
    def fail(_):raise ValueError('Synthetic network outage')
    monkeypatch.setattr(app.state.engine,'research',fail)
    job=wait_job(c,cid,'research')
    assert job['status']=='failed' and 'network outage' in job['error']


def test_scheduler_registration_and_same_weekly_callback(client,monkeypatch):
    c,app=client;cid=setup_company(c)
    jobs=app.state.jobs
    jobs.scheduler.start()
    jobs.configure(cid)
    schedules=jobs.schedules(cid)
    assert len(schedules)==4
    weekly=jobs.scheduler.get_job(f'{cid}:weekly')
    assert weekly.func==jobs.submit and weekly.args==(cid,'weekly')
    wait_job(c,cid,'research');wait_job(c,cid,'discover')
    app.state.db.run("UPDATE sources SET status='approved' WHERE company_id=?",(cid,))
    from apscheduler.triggers.date import DateTrigger
    from datetime import datetime, timedelta, timezone
    # Fire the registered weekly job through the real scheduler using a short test trigger.
    jobs.scheduler.reschedule_job(weekly.id,trigger=DateTrigger(run_date=datetime.now(timezone.utc)+timedelta(milliseconds=50)))
    for _ in range(300):
        row=app.state.db.one("SELECT * FROM job_logs WHERE company_id=? AND kind='weekly' ORDER BY id DESC LIMIT 1",(cid,))
        if row and row['status'] not in ('queued','running'):break
        time.sleep(.02)
    assert row['status']=='success'
    assert app.state.db.one('SELECT COUNT(*) n FROM briefs')['n']==1


def test_profile_update_queues_reassessment_and_diff(client):
    c,app=client;cid=setup_company(c);root=f'/api/companies/{cid}'
    wait_job(c,cid,'research');wait_job(c,cid,'discover');wait_job(c,cid,'analyze')
    profile=c.get(root).json()['profile'];profile['priorities']=['New segment']
    result=c.put(root+'/profile',json=profile)
    assert result.status_code==200 and 'New segment' in result.json()['diff']
    assert c.get(root+'/context-changes').json()
