import io
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.db import Database, now
from app.exports import brief_html, brief_pdf
from app.llm import LLM, LLMUnavailable
from app.models import Interpretation, Profile, Question
from app.network import canonical_url, public_url
from app.services import Engine
from tests.fixtures import COMPANIES, FixtureLLM, FixtureWeb


@pytest.fixture
def stack(tmp_path):
    db=Database(tmp_path/'test.db')
    transport=FixtureLLM()
    llm=LLM(db,transport)
    web=FixtureWeb()
    engine=Engine(db,llm,web)
    ids=[db.insert('companies',name=name,url=url,created_at=now(),updated_at=now()) for name,url,_,_ in COMPANIES]
    return db,engine,web,transport,ids


def test_llm_validated_and_cached(stack):
    db,engine,web,transport,ids=stack
    result=engine.llm.ask('test',{},Question)
    assert result.question=='Connection verified'
    engine.llm.ask('test',{},Question)
    assert transport.calls==1


def test_missing_key_is_explicit(stack,monkeypatch):
    db,*_=stack
    monkeypatch.setenv('LLM_PROVIDER','gemini')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    with pytest.raises(LLMUnavailable,match='not configured'):
        LLM(db).ask('test',{},Question)


def test_retries_validate_before_cache(stack,monkeypatch):
    db,*_=stack
    calls=[]
    def transport(*args):
        calls.append(1)
        return 'invalid json' if len(calls)<3 else {'question':'valid','why':'recovered'}
    monkeypatch.setattr('app.llm.time.sleep',lambda _:None)
    llm=LLM(db,transport)
    assert llm.ask('retry',{},Question).question=='valid'
    assert len(calls)==3
    assert db.one('SELECT COUNT(*) n FROM llm_cache')['n']==1


def test_research_downgrades_unmatched_verified_claims(stack):
    db,e,w,t,ids=stack
    profile=e.research(ids[0])['profile']
    assert profile['facts'][0]['status']=='verified'
    assert profile['facts'][1]['status']=='assumption'
    assert profile['facts'][1]['url']==''
    assert db.one('SELECT COUNT(*) n FROM documents')['n']==1


def test_interview_is_ten_tailored_and_resumes(stack):
    db,e,w,t,ids=stack
    questions=[]
    for cid in ids[:2]:
        e.research(cid)
        first=e.next_question(cid)
        assert e.next_question(cid)['id']==first['id']
        questions.append(first['question'])
        for n in range(1,11):
            q=e.next_question(cid)
            assert q['position']==n
            db.run('UPDATE profile_answers SET answer=?,skipped=? WHERE id=?',('Our priorities' if n!=3 else '',int(n==3),q['id']))
        assert e.next_question(cid)['complete']
        assert db.one('SELECT COUNT(*) n FROM profile_answers WHERE company_id=?',(cid,))['n']==10
        assert e.follow_up(cid,first['id'])['question']
    assert questions[0]!=questions[1]


def test_discovery_candidates_require_approval_and_no_url_invention(stack):
    db,e,w,t,ids=stack
    cid=ids[0];e.research(cid)
    result=e.discover(cid)
    assert result['added']==24 and result['competitors']==7
    assert db.one("SELECT COUNT(*) n FROM sources WHERE status='approved'")['n']==0
    with pytest.raises(ValueError,match='Approve'):
        e.crawl(cid)
    assert all('.example' in c['url'] for c in db.company(cid)['profile']['competitors'])


def test_crawl_rss_dedup_change_and_failure_isolation(stack):
    db,e,w,t,ids=stack
    cid=ids[0];e.research(cid);e.discover(cid)
    db.run("UPDATE sources SET status='approved' WHERE company_id=?",(cid,))
    source=db.one("SELECT * FROM sources WHERE url LIKE '%source1.example%'")
    w.blocked.add(source['url'])
    result=e.crawl(cid)
    assert result['records']>=30 and result['failures']==1
    assert e.crawl(cid)['records']==0
    w.revision='New evidence revision'
    assert e.crawl(cid)['records']>=30
    assert db.one('SELECT COUNT(*) n FROM documents WHERE previous_id IS NOT NULL')['n']>=30
    assert db.one("SELECT COUNT(*) n FROM crawl_runs WHERE status='failed'")['n']==3


def test_intake_formats_and_duplicate_hashes(stack):
    from openpyxl import Workbook
    from reportlab.pdfgen.canvas import Canvas
    db,e,w,t,ids=stack;cid=ids[0]
    csv=b'reason,request\nLost deal,Needs SSO\nObjection,Pricing too high\n'
    assert e.intake(cid,'notes.csv',csv)['records']==2
    assert e.intake(cid,'again.csv',csv)['records']==0
    assert e.intake(cid,'notes.txt',b'Customers request a simpler onboarding flow.')['records']==1
    buffer=io.BytesIO();book=Workbook();book.active.append(['A request from a clinic to support referrals']);book.save(buffer)
    assert e.intake(cid,'notes.xlsx',buffer.getvalue())['records']==1
    pdf=io.BytesIO();canvas=Canvas(pdf);canvas.drawString(50,700,'An internal customer objects to the renewal price.');canvas.save()
    assert e.intake(cid,'notes.pdf',pdf.getvalue())['records']==1
    with pytest.raises(ValueError,match='Supported formats'):
        e.intake(cid,'notes.exe',b'data')


def test_analysis_rejects_fabricated_quotes(stack):
    db,e,w,t,ids=stack;cid=ids[0];e.research(cid)
    doc=db.one('SELECT * FROM documents')
    def invalid(task,context,schema):
        return t(task,context,schema)|{'evidence_quote':'A fabricated quote that is not in the source'}
    e.llm=LLM(db,invalid)
    with pytest.raises(ValueError,match='not present'):
        e.analyze(cid)
    assert db.one('SELECT COUNT(*) n FROM signals')['n']==0


def test_unknown_publication_is_not_fresh_and_rank_explained(stack):
    db,e,w,t,ids=stack;cid=ids[0];e.research(cid);e.analyze(cid)
    signal=e.signals(cid)[0]
    assert signal['factors']['recency']==.35
    assert signal['evidence']['url'].startswith('https://')
    assert signal['evidence']['quote']
    assert 'relevance' in signal['explanation']
    assert set(['reliability','evidence_strength','strategic_relevance'])<=signal.keys()


def test_three_companies_have_distinct_stacks_briefs_and_context_diffs(stack,tmp_path):
    db,e,w,t,ids=stack
    outputs=[]
    for cid in ids:
        e.research(cid);e.discover(cid)
        db.run("UPDATE sources SET status='approved' WHERE company_id=?",(cid,))
        e.crawl(cid)
        assert e.analyze(cid)['analyzed']>=30
        result=e.brief(cid)
        assert result['sections']==10 and result['opportunities']>=3
        brief=db.one('SELECT * FROM briefs WHERE id=?',(result['brief_id'],))
        assert len(json.loads(brief['sections']))==10
        assert 'AI interpretation' in brief['markdown'] and 'Evidence:' in brief['markdown']
        assert '<blockquote>' in brief_html(brief)
        pdf=brief_pdf(brief)
        from pypdf import PdfReader
        assert len(PdfReader(io.BytesIO(pdf)).pages)>0
        outputs.append(brief['markdown'])
    assert len(set(outputs))==3
    before=e.signals(ids[0])[0]['score']
    profile=db.company(ids[0])['profile'];profile['priorities']=['New segment']
    change=e.update_profile(ids[0],profile)
    assert '-    "Improve onboarding"' in change['diff']
    assert db.one('SELECT COUNT(*) n FROM sources WHERE company_id=? AND stale=1',(ids[0],))['n']>0
    result=e.context_change(ids[0])
    assert result['sources'][0]['before']!=result['sources'][0]['after']
    assert e.signals(ids[0])[0]['score']<before
    assert db.one('SELECT COUNT(*) n FROM context_changes')['n']==2


def test_thin_brief_states_shortfall_and_empty_categories(stack):
    db,e,w,t,ids=stack;cid=ids[0];e.research(cid);e.analyze(cid)
    result=e.brief(cid)
    brief=db.one('SELECT * FROM briefs WHERE id=?',(result['brief_id'],))
    sections=json.loads(brief['sections'])
    assert 'target of 3 was not met' in sections[5]['note']
    assert 'No meaningful development' in sections[2]['note']


def test_no_current_signals_no_brief(stack):
    db,e,w,t,ids=stack
    with pytest.raises(ValueError,match='No analyzed evidence'):
        e.brief(ids[0])
    e.research(ids[0]);e.analyze(ids[0])
    profile=db.company(ids[0])['profile'];profile['priorities']=['New segment'];e.update_profile(ids[0],profile)
    with pytest.raises(ValueError,match='current profile'):
        e.brief(ids[0])


def test_audit_flags_inactivity_duplicates_and_reassesses(stack):
    db,e,w,t,ids=stack;cid=ids[0]
    e.research(cid);e.discover(cid)
    e.add_source(cid,'https://educationsource1.example/other','Duplicate domain','Market','Test duplicate domain')
    db.run("UPDATE sources SET status='approved' WHERE company_id=?",(cid,))
    w.blocked.add('https://educationsource1.example/')
    result=e.audit(cid)
    kinds={i['issue'] for i in result['issues']}
    assert 'possible duplicate domain' in kinds
    assert 'inactive; no new records in 30 days' in kinds
    assert 'dead or blocked URL' in kinds
    assert result['reassessment']['sources']


def test_source_deletion_keeps_evidence_and_original_channel(stack):
    db,e,w,t,ids=stack;cid=ids[0]
    e.research(cid);e.analyze(cid)
    signal=e.signals(cid)[0];source=db.one('SELECT id FROM sources WHERE company_id=?',(cid,))
    db.run('DELETE FROM sources WHERE id=?',(source['id'],))
    e.analyze(cid,force=True)
    assert e.signals(cid)[0]['category']==signal['category']
    assert e.signals(cid)[0]['evidence']['url']==signal['evidence']['url']


@pytest.mark.parametrize('url',['file:///etc/passwd','http://user:pass@example.com/','http://example.com:8000/','javascript:alert(1)'])
def test_invalid_urls(url):
    with pytest.raises(ValueError):canonical_url(url)


@pytest.mark.parametrize('url',['http://127.0.0.1/','http://169.254.169.254/','http://[::1]/','http://10.0.0.1/'])
def test_network_blocks_private_urls(url):
    with pytest.raises(ValueError):public_url(url)
