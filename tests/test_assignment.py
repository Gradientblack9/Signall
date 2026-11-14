import json

import pytest

from app.briefs import SECTIONS
from app.db import Database, now
from app.exports import brief_html
from app.filtering import filter_signals
from app.llm import LLM, LLMUnavailable
from app.models import Candidates, Interpretation, OpportunityPlan, Question, Reassessment, SourceHypotheses
from app.services import Engine, unique_competitors
from app.network import Page
from tests.fixtures import FixtureLLM, FixtureWeb
from tests.test_api import client, setup_company, wait_job


def engine(tmp_path, transport=None, web=None):
    db = Database(tmp_path/'assignment.db')
    cid = db.insert('companies', name='MeetUniversity fixture', url='https://education.example/', created_at=now(), updated_at=now())
    return db, Engine(db, LLM(db, transport or FixtureLLM()), web or FixtureWeb()), cid


def test_assignment_exact_brief_sections_and_required_details(tmp_path):
    db, e, cid = engine(tmp_path)
    e.research(cid)
    e.intake(cid, 'feedback.txt', b'Customers ask for clearer application progress updates.')
    e.analyze(cid)
    result = e.brief(cid)
    brief = db.one('SELECT * FROM briefs WHERE id=?', (result['brief_id'],))
    sections = json.loads(brief['sections'])
    assert [s['title'] for s in sections] == [
        'Executive Summary', 'Customer Signals', 'Competitor Intelligence', 'Market Intelligence',
        'Internal Business Intelligence', 'Opportunities Identified', 'Risks & Threats',
        'Recommended Actions for This Week', 'What We Should Watch', 'Source Appendix']
    opportunity = sections[5]['items'][0]
    assert all(key in opportunity for key in ('evidence','impact','next_step','priority'))
    assert sections[7]['items'][0]['suggested_owner']
    appendix = sections[9]['items'][0]
    assert all(key in appendix for key in ('original_source','url','published_at','discovered_at','evidence','verification'))
    assert appendix['verified'] is False
    assert 'Published' in brief_html(brief) and 'Suggested owner' in brief_html(brief)
    assert 'not independently corroborated' in brief['markdown']


def test_background_pages_do_not_become_news_or_opportunities(tmp_path):
    base = FixtureLLM()
    def transport(task, context, schema):
        data = base(task, context, schema)
        if schema is Interpretation:
            data.update(is_development=False, sentiment='neutral')
        return data
    db, e, cid = engine(tmp_path, transport)
    e.research(cid); e.analyze(cid)
    result = e.brief(cid)
    assert result['developments'] == 0 and result['opportunities'] == 0
    sections = json.loads(db.one('SELECT sections FROM briefs')['sections'])
    assert not sections[0]['items'] and sections[9]['items']
    assert 'No meaningful development' in sections[0]['note']


def test_search_outage_fallback_only_keeps_observed_urls(tmp_path):
    web, base = FixtureWeb(), FixtureLLM()
    web.search = lambda _: (_ for _ in ()).throw(ValueError('Search unavailable'))
    web.blocked.add('https://educationsource8.example/')
    def transport(task, context, schema):
        if schema is SourceHypotheses:
            candidates = [{'url': f'https://educationsource{i}.example/', 'title': f'Fixture {i}'} for i in range(1,25)]
            return base(task, context | {'candidates': candidates}, Candidates)
        return base(task, context, schema)
    db, e, cid = engine(tmp_path, transport, web)
    e.research(cid)
    result = e.discover(cid)
    assert result['candidates'] == 23
    assert 'validated' in result['method']
    assert not db.one('SELECT id FROM sources WHERE url=?', ('https://educationsource8.example/',))
    assert result['limitations']


def sample_signal(sid, day, relevance, impact, verified, competitor):
    return {'id':sid,'created_at':day,'score':100*relevance,'category':'Competitors',
        'evidence':{'url':f'https://rival{sid}.example/', 'quote':'Exact source excerpt', 'published_at':day,
                    'discovered_at':day,'verified':verified,'quote_matched':True},
        'interpretation':{'sentiment':'opportunity','urgency':'medium','competitor_name':competitor,
                          'relevance':relevance,'impact':impact}}


def test_all_assignment_feed_filters_and_chronological_order():
    rows = [sample_signal(1,'2026-11-10',.9,.8,False,'Rival One'), sample_signal(2,'2026-11-14',.5,.3,True,'Rival Two')]
    assert [s['id'] for s in filter_signals(rows)] == [2,1]
    assert [s['id'] for s in filter_signals(rows,sort='importance')] == [1,2]
    assert [s['id'] for s in filter_signals(rows,competitor='Rival One')] == [1]
    assert [s['id'] for s in filter_signals(rows,date_from='2026-11-12')] == [2]
    assert [s['id'] for s in filter_signals(rows,date_to='2026-11-12')] == [1]
    assert [s['id'] for s in filter_signals(rows,min_relevance=.8,min_impact=.7)] == [1]
    assert [s['id'] for s in filter_signals(rows,verification='verified')] == [2]
    assert len(filter_signals(rows,verification='quote_matched')) == 2
    rows[1]['interpretation']['event_date'] = 'Nov 14'
    assert [s['id'] for s in filter_signals(rows,date_from='2026-11-12')] == [2]
    assert not filter_signals([sample_signal(3,'2026-11-14',.8,.8,False,'Patagonia')],competitor='On')
    with pytest.raises(ValueError): filter_signals(rows,date_from='yesterday')
    with pytest.raises(ValueError): filter_signals(rows,date_from='2026-12-01',date_to='2026-11-01')


def test_verification_requires_review_and_is_company_scoped(client):
    c, app = client
    cid = setup_company(c)
    wait_job(c,cid,'research'); wait_job(c,cid,'analyze')
    root = f'/api/companies/{cid}'
    signals = c.get(root+'/signals').json()
    sid = signals[0]['id']
    assert signals[0]['evidence']['verified'] is False
    assert c.patch(root+f'/signals/{sid}/verification',json={'verified':True,'note':'Reviewed the linked evidence and independent corroboration.'}).status_code == 200
    assert c.get(root+'/signals?verification=verified').json()[0]['id'] == sid
    assert c.patch(root+f'/signals/{sid}/verification',json={'verified':True,'note':'yes'}).status_code == 422
    assert c.patch(root+'/signals/9999/verification',json={'verified':True,'note':'Not a real signal ID.'}).status_code == 404
    assert c.get(root+'/signals?min_impact=2').status_code == 422
    assert c.get(root+'/signals?date_from=invalid').status_code == 400


def test_monthly_report_survives_llm_outage(tmp_path):
    db, e, cid = engine(tmp_path)
    e.research(cid)
    db.run("UPDATE sources SET status='approved' WHERE company_id=?", (cid,))
    e.fetcher.blocked.add('https://education.example/')
    def fail(*args): raise LLMUnavailable('Synthetic quota outage')
    e.llm.ask = fail
    report = e.audit(cid)
    assert report['report_type'] == 'monthly_source_health'
    assert report['summary']['sources_checked'] > 0
    assert report['issues'] and report['reassessment']['error'] and report['discovery']['error']


def test_context_change_also_recommends_new_candidates(tmp_path):
    db, e, cid = engine(tmp_path)
    e.research(cid); e.discover(cid); e.analyze(cid)
    profile = db.company(cid)['profile']
    profile['priorities'] = ['New segment']
    e.update_profile(cid,profile)
    result = e.context_change(cid)
    assert 'new_candidates' in result and result['new_queries']
    assert result['sources'] and any(s['before'] != s['after'] for s in result['sources'])


def test_repeated_interview_question_is_rejected(tmp_path):
    base = FixtureLLM()
    def transport(task, context, schema):
        return {'question':'The same repeated question?', 'why':'Fixture duplication'} if schema is Question else base(task,context,schema)
    db, e, cid = engine(tmp_path,transport)
    e.research(cid)
    first=e.next_question(cid)
    db.run('UPDATE profile_answers SET answer=? WHERE id=?',('Public answer',first['id']))
    with pytest.raises(ValueError,match='repeated'):
        e.next_question(cid)
    assert db.one('SELECT COUNT(*) n FROM profile_answers')['n']==1


def test_monthly_scheduler_runs_independently_from_weekly(client):
    import time
    from datetime import datetime, timedelta, timezone
    from apscheduler.triggers.date import DateTrigger
    c,app=client;cid=setup_company(c)
    wait_job(c,cid,'research');wait_job(c,cid,'discover')
    jobs=app.state.jobs;jobs.scheduler.start();jobs.configure(cid)
    weekly=jobs.scheduler.get_job(f'{cid}:weekly')
    assert weekly and jobs.scheduler.get_job(f'{cid}:audit')
    jobs.scheduler.reschedule_job(f'{cid}:audit',trigger=DateTrigger(run_date=datetime.now(timezone.utc)+timedelta(milliseconds=50)))
    for _ in range(300):
        row=app.state.db.one("SELECT * FROM job_logs WHERE company_id=? AND kind='audit' ORDER BY id DESC LIMIT 1",(cid,))
        if row and row['status'] not in ('queued','running'):break
        time.sleep(.02)
    assert row and row['status']=='success'
    assert json.loads(row['result'])['report_type']=='monthly_source_health'
    assert jobs.scheduler.get_job(weekly.id).next_run_time
    assert not app.state.db.one("SELECT id FROM job_logs WHERE company_id=? AND kind='weekly'",(cid,))


def test_blocked_rss_falls_back_to_permitted_html(tmp_path):
    class Website:
        def get(self, url, delay=1):
            if url.endswith('/feed'):
                raise ValueError('Disallowed by robots.txt')
            return Page(url, '<html><head><title>Public page</title><link type="application/rss+xml" href="/feed"></head><body>A real public page with enough readable company information to collect as background evidence.</body></html>', 'text/html')
    db,e,cid=engine(tmp_path,web=Website())
    sid,_=e.add_source(cid,'https://education.example/','Public site','Customers','First-party context',status='approved')
    result=e.crawl_source(db.one('SELECT * FROM sources WHERE id=?',(sid,)))
    assert result['records']==1 and result['limitations']
    assert db.one('SELECT status FROM crawl_runs')['status']=='success'
    assert db.one('SELECT content FROM documents')['content']


def test_competitor_country_aliases_do_not_inflate_minimum_target():
    competitors=[{'name':'On','url':'https://www.on.com/en-us','reason':'US site'},
                 {'name':'On Running','url':'https://www.on.com/en-in','reason':'Same company'},
                 {'name':'Nike','url':'https://nike.com/','reason':'Global site'},
                 {'name':'Nike','url':'https://nike.in/','reason':'Same brand'},
                 {'name':'Other brand','url':'https://other.example/','reason':'Different company'}]
    assert len(unique_competitors(competitors))==3


def test_historical_articles_are_not_presented_as_this_week_news(tmp_path):
    db,e,cid=engine(tmp_path)
    e.research(cid)
    db.run('UPDATE documents SET published_at=? WHERE company_id=?',('2020-01-01T00:00:00+00:00',cid))
    e.analyze(cid)
    result=e.brief(cid)
    assert result['developments']==0
    sections=json.loads(db.one('SELECT sections FROM briefs')['sections'])
    assert sections[9]['items'][0]['freshness']=='Historical or outside the current week'


def test_explicit_written_dates_do_not_make_old_articles_current():
    from app.dates import explicit_date
    assert explicit_date('14 Oct 2026').date().isoformat() == '2026-10-14'
    assert explicit_date('October 14, 2026').date().isoformat() == '2026-10-14'
    assert explicit_date('Nov 12') is None
    assert explicit_date('2026-11-14T05:00:00Z').year == 2026


def test_opportunities_can_address_risks_without_inventing_events(tmp_path):
    base=FixtureLLM()
    def transport(task,context,schema):
        if schema is OpportunityPlan:
            ideas=[{'signal_ids':[s['id']],'title':f'Proposed response for evidence {s["id"]}',
                    'impact_statement':'A conditional AI interpretation of this specific evidence.',
                    'next_step':'Test an improvement tied to the quoted request.','priority':'medium','suggested_owner':'Product lead'}
                   for s in context['signals'][:3]]
            ideas.append({'signal_ids':[999999],'title':'Invented event','impact_statement':'Not supported',
                'next_step':'Must be rejected','priority':'high','suggested_owner':'Nobody'})
            return {'opportunities':ideas}
        data=base(task,context,schema)
        if schema is Interpretation:data.update(sentiment='threat')
        return data
    db,e,cid=engine(tmp_path,transport)
    e.research(cid)
    e.intake(cid,'notes.txt',b'Customers request quicker application feedback.\n\nCustomers request transparent pricing information.')
    e.analyze(cid)
    result=e.brief(cid)
    assert result['opportunities']==3 and result['developments']==3
    assert db.one('SELECT COUNT(*) n FROM signals')['n']==3
    sections=json.loads(db.one('SELECT sections FROM briefs')['sections'])
    assert len(sections[6]['items'])==3
    assert all(i['text']!='Invented event' for i in sections[5]['items'])
    assert 'AI recommendations' in sections[5]['note']
