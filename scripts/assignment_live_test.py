"""Real API acceptance stages. Public-site answers only; private questions are skipped.

This does not import fixtures or seed competitor/source lists. Review discovered
sources before invoking --stage collect with an explicit --approve-ids list.
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()
OUT = Path('output/assignment-audit')
OUT.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['setup','collect','snapshot','context'], required=True)
    parser.add_argument('--company-id', type=int)
    parser.add_argument('--name')
    parser.add_argument('--url')
    parser.add_argument('--approve-ids', default='')
    parser.add_argument('--analyze', action='store_true')
    args = parser.parse_args()
    headers = {'Authorization':'Bearer '+os.environ['SIGNAL_ACCESS_TOKEN']} if os.getenv('SIGNAL_ACCESS_TOKEN') else {}
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=180, headers=headers) as client:
        def call(method, path, **kwargs):
            response = client.request(method,path,**kwargs)
            if not response.is_success:
                detail = response.json().get('detail', 'Request failed')
                raise RuntimeError(f'{response.status_code}: {detail}')
            return response.json()
        cid = args.company_id
        if not cid:
            if not args.name or not args.url:
                parser.error('Provide --company-id or --name and --url')
            existing = call('GET','/api/companies')
            match = next((c for c in existing if c['name']==args.name and c['url'].rstrip('/')==args.url.rstrip('/')),None)
            cid = match['id'] if match else call('POST','/api/companies',json={'name':args.name,'url':args.url})['id']
        root = f'/api/companies/{cid}'
        target = OUT/f'company-{cid}-live.json'
        report = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'synthetic':False,'company_id':cid,'events':[]}
        def save():
            report['updated_at'] = datetime.now(timezone.utc).isoformat()
            target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        def job(kind):
            queued = call('POST',root+'/jobs/'+kind)
            deadline = time.monotonic()+1200
            print('Started',cid,kind,queued,flush=True)
            while time.monotonic()<deadline:
                row = next(j for j in call('GET',root+'/jobs')['logs'] if j['id']==queued['job_id'])
                if row['status'] not in ('queued','running'):
                    report['events'].append(row);save()
                    print('Finished',cid,kind,row['status'],row.get('error') or '',flush=True)
                    return row
                time.sleep(2)
            raise RuntimeError('Job is still active; inspect dashboard before retrying')
        if args.stage=='setup':
            company = call('GET',root)
            if not company['profile']:
                if job('research')['status']=='failed': return 1
            for _ in range(10):
                company = call('GET',root)
                completed = [a for a in company['answers'] if a['answer'] or a['skipped']]
                if len(completed)>=10: break
                question = call('POST',root+'/interview/next')
                if question.get('complete'): break
                profile = company['profile']
                text = question['question'].casefold()
                private = bool(re.search(r'revenue|margin|conversion|budget|confidential|internal|next (6|12|six|twelve)|priorit|growth target|sales pipeline|retention rate|acquisition cost|forecast',text))
                public_theme = bool(re.search(r'product|service|customer|segment|differentiat|problem|position|business line|offering|value proposition',text))
                if public_theme and not private:
                    facts = [f for f in profile.get('facts',[]) if f.get('status')=='verified']
                    answer = 'Evaluation answer from public website only, not founder confirmation. '
                    answer += 'Publicly described offerings: '+', '.join(profile.get('products',[]))+'. '
                    answer += 'Publicly described customer segments (AI classification): '+', '.join(profile.get('customers',[]))+'. '
                    answer += ' '.join(f['claim']+' Source: '+f['url'] for f in facts[:2])
                    answer += ' No private metrics or strategy are supplied; this may only partially answer the question.'
                else:
                    answer = ''
                call('PUT',root+f'/interview/{question["id"]}',json={'answer':answer,'skipped':not bool(answer)})
                report['events'].append({'type':'interview','position':question['position'],'question':question['question'],'skipped':not bool(answer),'basis':'Public website only; private information not inferred'})
                save();print('Interview',cid,question['position'],'answered from public site' if answer else 'skipped',flush=True)
            company = call('GET',root)
            answered = next((a for a in company['answers'] if a['answer']),None)
            if answered and not answered['follow_up']:
                report['follow_up'] = call('POST',root+f'/interview/{answered["id"]}/follow-up');save()
            job('discover')
        elif args.stage=='collect':
            ids = [int(v) for v in args.approve_ids.split(',') if v.strip()]
            for sid in ids:
                call('PATCH',root+f'/sources/{sid}',json={'status':'approved'})
            if ids:
                report['source_review'] = {'approved_ids':ids,'basis':'Sources reviewed by the evaluator after automatic discovery; no sources or competitors seeded in application code.'};save()
            job('crawl')
            if args.analyze:
                job('analyze')
                job('brief')
        elif args.stage=='context':
            company = call('GET',root)
            profile = company['profile']
            report['before_context'] = {'sources':call('GET',root+'/sources'),'signals':call('GET',root+'/signals')}
            profile['priorities'] = ['Evaluation monitoring focus: public customer feedback about onboarding and pricing. This is a test configuration, not a claim about private company strategy.']
            report['profile_change'] = call('PUT',root+'/profile',json=profile);save()
            jid = report['profile_change']['job']['job_id']
            for _ in range(600):
                row = next(j for j in call('GET',root+'/jobs')['logs'] if j['id']==jid)
                if row['status'] not in ('queued','running'):
                    report['events'].append(row);save();break
                time.sleep(2)
            report['after_context'] = {'sources':call('GET',root+'/sources'),'signals':call('GET',root+'/signals'),'diffs':call('GET',root+'/context-changes')}
            save();job('brief')
        report['company'] = call('GET',root)
        for endpoint in ('overview','sources','documents','signals','briefs','jobs','context-changes'):
            report[endpoint] = call('GET',root+'/'+endpoint)
        report['checks'] = {
            'interview_questions':len(report['company']['answers']),
            'unique_questions':len({a['question'].strip().casefold() for a in report['company']['answers']}),
            'approved_sources':sum(s['status']=='approved' for s in report['sources']),
            'competitors':len(report['company']['profile'].get('competitors',[])),
            'actual_records':len(report['documents']),
            'signals':len(report['signals']),
            'all_signals_have_links_and_excerpts':bool(report['signals']) and all(s['evidence'].get('url') and s['evidence'].get('quote') for s in report['signals']),
            'briefs':len(report['briefs'])}
        save();print(json.dumps({'company_id':cid,'checks':report['checks'],'report':str(target)},indent=2),flush=True)
    return 0


if __name__=='__main__':sys.exit(main())
