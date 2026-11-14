"""Drive the actual running application, without bypassing human source approval."""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    parser.add_argument('--company-id',type=int)
    parser.add_argument('--name',help='Create this company if --company-id is absent')
    parser.add_argument('--url',help='Public company URL')
    parser.add_argument('--jobs',default='research,discover',help='Comma-separated jobs; source approval is always performed in dashboard')
    parser.add_argument('--output',default='output/live-acceptance.json')
    args=parser.parse_args();load_dotenv()
    token=os.getenv('SIGNAL_ACCESS_TOKEN','')
    with httpx.Client(base_url=args.base_url,headers={'Authorization':'Bearer '+token} if token else {},timeout=120) as client:
        def call(method,path,**kwargs):
            r=client.request(method,path,**kwargs)
            if not r.is_success:raise RuntimeError(f'{r.status_code}: {r.text[:500]}')
            return r.json()
        report={'synthetic':False,'started_at':datetime.now(timezone.utc).isoformat(),'health':call('GET','/health'),'jobs':[]}
        report['llm_test']=call('POST','/api/llm/test')
        cid=args.company_id
        if not cid:
            if not args.name or not args.url:parser.error('Provide --company-id or both --name and --url')
            cid=call('POST','/api/companies',json={'name':args.name,'url':args.url})['id']
        root=f'/api/companies/{cid}'
        for kind in args.jobs.split(','):
            job=call('POST',root+'/jobs/'+kind.strip())
            deadline=time.monotonic()+1800
            while time.monotonic()<deadline:
                row=next(j for j in call('GET',root+'/jobs')['logs'] if j['id']==job['job_id'])
                if row['status'] not in ('queued','running'):break
                time.sleep(2)
            else:raise RuntimeError('Job timeout; inspect Automation dashboard')
            report['jobs'].append(row)
            print(kind,row['status'],row.get('error') or '')
        report['overview']=call('GET',root+'/overview')
        report['sources']=call('GET',root+'/sources')
        report['signals']=call('GET',root+'/signals')
        report['all_signals_have_links']=all(s['evidence']['url'] and s['evidence']['quote'] for s in report['signals'])
        output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Saved evidence to',str(output.resolve()))
        if any(j['status']=='failed' for j in report['jobs']):return 1
    return 0


if __name__=='__main__':sys.exit(main())
