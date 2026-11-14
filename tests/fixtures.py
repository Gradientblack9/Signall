"""Explicitly synthetic fixtures. Never imported by the production application."""
from urllib.parse import urlsplit

from app.models import Candidates, FollowUp, Interpretation, OpportunityPlan, Profile, Question, Reassessment, SearchPlan
from app.network import Page

COMPANIES = [
    ('MeetUniversity fixture', 'https://education.example/', 'study abroad', 'students'),
    ('Harbor Health fixture', 'https://health.example/', 'clinic operations', 'clinics'),
    ('Orbit Logistics fixture', 'https://logistics.example/', 'freight logistics', 'carriers'),
]


class FixtureWeb:
    def __init__(self):
        self.blocked = set()
        self.revision = ''

    def get(self, url, delay=1):
        if url in self.blocked:
            raise ValueError('Disallowed by robots.txt (synthetic fixture)')
        host = urlsplit(url).hostname
        if host.endswith('.example') and 'source' not in host:
            info = next((c for c in COMPANIES if urlsplit(c[1]).hostname == host), COMPANIES[0])
            return Page(url, f'<html><title>{info[0]}</title><body><h1>{info[0]}</h1><p>We provide {info[2]} services to {info[3]}. Our customers request transparent pricing, quicker onboarding and clear updates.</p>{self.revision}</body></html>', 'text/html')
        n = int(host.split('source')[1].split('.')[0])
        entries = ''.join(f'<item><title>Synthetic evidence {n}-{i}</title><link>https://{host}/record/{i}</link><description>Fixture source {n} record {i}: customers request onboarding improvements and transparent pricing for the next quarter. {self.revision}</description><pubDate>Fri, 13 Nov 2026 08:00:00 GMT</pubDate></item>' for i in range(3))
        return Page(url, f'<?xml version="1.0"?><rss version="2.0"><channel><title>Fixture feed {n}</title>{entries}</channel></rss>', 'application/rss+xml')

    def search(self, query):
        prefix = 'education' if 'education' in query else 'health' if 'health' in query else 'logistics'
        return [{'url':f'https://{prefix}source{i}.example/', 'title':f'{prefix} source {i}', 'snippet':'Synthetic candidate search evidence for tests only.'} for i in range(1,25)]


class FixtureLLM:
    def __init__(self):
        self.calls = 0

    def __call__(self, task, context, schema):
        self.calls += 1
        if schema is Profile:
            page=context['pages'][0]
            name=context['company']
            quote=page['text']
            return {'summary':name+' supplies services in its own market. SYNTHETIC TEST DATA.',
                'industry':name.split()[0], 'customers':['Customers of '+name],
                'products':['Services for '+name], 'priorities':['Improve onboarding'],
                'facts':[{'claim':'Website describes the service', 'status':'verified','url':page['url'],'quote':quote},
                         {'claim':'Unsupported market leadership', 'status':'verified','url':page['url'],'quote':'This invented quote does not appear'}],
                'competitors':[]}
        if schema is Question:
            if not context:
                return {'question':'Connection verified','why':'Synthetic fixture transport'}
            return {'question':f"For {context['company']['name']}, what is your priority for {context['company']['profile'].get('industry')} in question {len(context['answers'])+1}?",'why':'Tailored to profile and previous answers'}
        if schema is FollowUp:
            return {'question':'Which part of that priority has the greatest measurable impact?'}
        if schema is SearchPlan:
            host=urlsplit(context['company']['url']).hostname.split('.')[0]
            return {'queries':[f'{host} market sources competitors']}
        if schema is Candidates:
            candidates=context['candidates']
            return {'sources':[{'url':c['url'],'name':c['title'],'category':['Customers','Competitors','Market'][i%3],
                'reason':'Matches '+context['company']['name']+' strategic context', 'specificity':.8,'recency':.7,'credibility':.8,'relevance':.9} for i,c in enumerate(candidates)],
                'competitors':[{'name':c['title'],'url':c['url'],'reason':'Synthetic competitor fixture'} for c in candidates[1:8]],}
        if schema is Interpretation:
            d=context['document']
            return {'what':f"{context['company']['name']}: {d['title']} suggests an onboarding opportunity.",
                'why_it_matters':'AI interpretation: this may improve onboarding and retention.',
                'business_area':'customer success','sentiment':'opportunity','urgency':'medium',
                'suggested_action':'Review the evidence and test an onboarding improvement.',
                'relevance':.2 if context['company']['profile'].get('priorities')==['New segment'] else .9,
                'impact':.8,'urgency_score':.6,'evidence_strength':.8,
                'evidence_quote':d['content'][:110], 'internal_type':'product_request' if d['kind']=='internal' else 'other'}
        if schema is Reassessment:
            return {'sources':[{'id':s['id'],'relevance':.2 if context['company']['profile'].get('priorities')==['New segment'] else .85,
                                'reason':'Updated to reflect the revised strategy.'} for s in context['sources']], 'new_queries':['new segment market research']}
        if schema is OpportunityPlan:
            return {'opportunities': []}
        raise AssertionError('No fixture for schema '+schema.__name__)
