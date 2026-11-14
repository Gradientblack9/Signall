"""Generate inspectable, explicitly synthetic acceptance artifacts; no external calls."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.db import Database, now
from app.exports import brief_html, brief_pdf
from app.llm import LLM
from app.services import Engine
from tests.fixtures import COMPANIES, FixtureLLM, FixtureWeb


def main():
    out=Path('output/fixtures');out.mkdir(parents=True,exist_ok=True)
    # A fresh run ID avoids sharing state with the running app or an earlier run.
    import tempfile
    with tempfile.TemporaryDirectory(dir=out.resolve()) as temp:
        db=Database(Path(temp)/'fixtures.db')
        engine=Engine(db,LLM(db,FixtureLLM()),FixtureWeb())
        results=[]
        for name,url,_,_ in COMPANIES:
            cid=db.insert('companies',name=name,url=url,created_at=now(),updated_at=now())
            engine.research(cid);engine.discover(cid)
            db.run("UPDATE sources SET status='approved' WHERE company_id=?",(cid,))
            engine.crawl(cid);engine.analyze(cid);result=engine.brief(cid)
            brief=db.one('SELECT * FROM briefs WHERE id=?',(result['brief_id'],))
            brief['title']='SYNTHETIC FIXTURE / '+brief['title']
            brief['markdown']='> SYNTHETIC TEST FIXTURE — NOT REAL COMPANY INTELLIGENCE.\n\n'+brief['markdown']
            slug=url.split('//')[1].split('.')[0]
            (out/f'{slug}-brief.md').write_text(brief['markdown'],encoding='utf-8')
            (out/f'{slug}-brief.html').write_text(brief_html(brief),encoding='utf-8')
            (out/f'{slug}-brief.pdf').write_bytes(brief_pdf(brief))
            count=db.one('SELECT COUNT(*) n FROM documents WHERE company_id=?',(cid,))['n']
            results.append({'company':name,'sources':25,'competitors':7,'records':count,'brief_id':result['brief_id'],'synthetic':True})
            if cid==1:
                old_scores=[{'id':s['id'],'score':s['score']} for s in engine.signals(cid)]
                profile=db.company(cid)['profile'];profile['priorities']=['New segment']
                diff=engine.update_profile(cid,profile);assessment=engine.context_change(cid)
                (out/'context-diff.json').write_text(json.dumps({'synthetic':True,'profile_diff':diff,'reassessment':assessment,
                    'before_scores':old_scores,'after_scores':[{'id':s['id'],'score':s['score']} for s in engine.signals(cid)]},indent=2),encoding='utf-8')
        (out/'evidence.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out.resolve()),'fixtures':results},indent=2))


if __name__=='__main__':main()
