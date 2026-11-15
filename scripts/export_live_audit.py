"""Save current real-company acceptance evidence and three report formats."""
import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--company-id', type=int, help='Export only this company; summary counts still cover all companies.')
    args = parser.parse_args()
    load_dotenv()
    target = Path('output/assignment-audit')
    reports = target/'reports'
    reports.mkdir(parents=True, exist_ok=True)
    headers = {'Authorization': 'Bearer '+os.environ['SIGNAL_ACCESS_TOKEN']} if os.getenv('SIGNAL_ACCESS_TOKEN') else {}
    summary = {'synthetic': False, 'generated_at': datetime.now(timezone.utc).isoformat(), 'companies': []}
    with httpx.Client(base_url='http://127.0.0.1:8000', headers=headers, timeout=120) as client:
        def get(path):
            response = client.get(path)
            response.raise_for_status()
            return response.json()
        for company in get('/api/companies'):
            cid = company['id']
            root = f'/api/companies/{cid}'
            snapshot = {'synthetic': False, 'company': get(root)}
            for endpoint in ('overview', 'sources', 'documents', 'signals', 'briefs', 'jobs', 'context-changes'):
                snapshot[endpoint] = get(root+'/'+endpoint)
            if not snapshot['briefs']:
                raise RuntimeError('A required company has no brief')
            brief_id = snapshot['briefs'][0]['id']
            brief = get(root+f'/briefs/{brief_id}')
            snapshot['latest_brief'] = brief
            slug = company['name'].lower().replace(' ', '-')
            if args.company_id is None or args.company_id == cid:
                for fmt in ('md', 'html', 'pdf'):
                    response = client.get(root+f'/briefs/{brief_id}/export/{fmt}')
                    response.raise_for_status()
                    (reports/f'{slug}-brief.{fmt}').write_bytes(response.content)
            (target/f'company-{cid}-final.json').write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding='utf-8')
            sections = brief['sections']
            if isinstance(sections, str):
                sections = json.loads(sections)
            docs = {d['id']: d for d in snapshot['documents']}
            database = Path(os.getenv('SIGNAL_DB', 'data/signal.db'))
            assert database.exists()
            with sqlite3.connect(database) as connection:
                contents = dict(connection.execute('SELECT id,content FROM documents WHERE company_id=?', (cid,)))
            def norm(value):
                return ' '.join(value.split()).casefold()
            matched = all(norm(s['evidence']['quote']) in norm(contents[s['document_id']]) for s in snapshot['signals'])
            assert matched, 'Stored signal evidence no longer matches its saved document'
            summary['companies'].append({
                'id': cid, 'name': company['name'], 'industry': snapshot['company']['profile'].get('industry'),
                'questions': len(snapshot['company']['answers']),
                'unique_questions': len({norm(a['question']) for a in snapshot['company']['answers']}),
                'answered_from_public_information': sum(bool(a['answer']) and not a['skipped'] for a in snapshot['company']['answers']),
                'skipped': sum(bool(a['skipped']) for a in snapshot['company']['answers']),
                'approved_sources': sum(s['status']=='approved' for s in snapshot['sources']),
                'sources': len(snapshot['sources']),
                'competitor_profiles': len(snapshot['company']['profile'].get('competitors', [])),
                'collected_records': len(docs), 'unique_record_urls': len({d['url'] for d in docs.values()}),
                'changed_content_versions': sum(d['previous_id'] is not None for d in docs.values()),
                'signals': len(snapshot['signals']), 'all_signal_quotes_match_saved_documents': matched,
                'all_signals_have_links': all(s['evidence']['url'] for s in snapshot['signals']),
                'brief_history': len(snapshot['briefs']), 'latest_brief_id': brief_id,
                'sections': len(sections), 'executive_items': len(sections[0]['items']),
                'opportunities': len(sections[5]['items']),
                'sections_with_no_current_development': [s['title'] for s in sections if not s['items']],
                'report_path': f'reports/{slug}-brief.pdf'})
    summary['total_collected_records'] = sum(c['collected_records'] for c in summary['companies'])
    summary['total_unique_record_urls_within_each_company'] = sum(c['unique_record_urls'] for c in summary['companies'])
    (target/'final-summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
