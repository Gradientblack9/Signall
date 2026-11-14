import csv
import difflib
import io
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import feedparser

from .db import now
from .models import Candidates, FollowUp, Interpretation, OpportunityPlan, Profile, Question, Reassessment, SearchPlan, SourceHypotheses
from .network import Fetcher, canonical_url, digest, html_content

WEIGHTS = {'relevance': .25, 'impact': .20, 'urgency': .15, 'credibility': .15, 'recency': .15, 'novelty': .10}
SECTIONS = ['Executive Summary', 'Customer Signals', 'Competitor Intelligence', 'Market Intelligence',
            'Internal Business Intelligence', 'Opportunities Identified', 'Risks & Threats',
            'Recommended Actions for This Week', 'What We Should Watch', 'Source Appendix']


def normalized(value):
    return ' '.join(value.split()).casefold()


def unique_competitors(competitors):
    result, names, hosts = [], set(), set()
    for competitor in competitors:
        name = re.sub(r'\W', '', competitor['name'].casefold())
        host = (urlsplit(competitor['url']).hostname or '').removeprefix('www.')
        if name in names or host in hosts:
            continue
        result.append(competitor)
        names.add(name); hosts.add(host)
    return result[:10]


def date_value(raw):
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace('Z', '+00:00'))
    except ValueError:
        try:
            value = parsedate_to_datetime(str(raw))
        except (ValueError, TypeError):
            return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


class Engine:
    def __init__(self, db, llm, fetcher=None):
        self.db, self.llm, self.fetcher = db, llm, fetcher or Fetcher()

    def context(self, company_id):
        return {'company': self.db.company(company_id),
                'answers': self.db.all('SELECT position,question,answer,skipped FROM profile_answers WHERE company_id=? ORDER BY position', (company_id,))}

    def add_source(self, company_id, url, name, category, reason, status='discovered', **scores):
        company = self.db.company(company_id)
        url = canonical_url(url)
        existing = self.db.one('SELECT id FROM sources WHERE company_id=? AND url=?', (company_id, url))
        if existing:
            return existing['id'], False
        sid = self.db.insert('sources', company_id=company_id, url=url, name=name[:200], category=category,
            reason=reason, status=status, created_at=now(), context_version=company['context_version'],
            **{key: max(0, min(1, float(value))) for key, value in scores.items()
               if key in ('specificity', 'recency', 'credibility', 'relevance')})
        return sid, True

    def store_document(self, company_id, source_id, url, title, text, published=None, kind='web', original_name=None):
        if not text.strip():
            return None
        if kind != 'internal':
            url = canonical_url(url)
        content_hash = digest(text)
        # Dedupe syndicated content as well as same-URL repeats within a company.
        if self.db.one('SELECT id FROM documents WHERE company_id=? AND content_hash=?', (company_id, content_hash)):
            return None
        previous = self.db.one('SELECT id FROM documents WHERE company_id=? AND url=? ORDER BY id DESC LIMIT 1', (company_id, url))
        return self.db.insert('documents', company_id=company_id, source_id=source_id, url=url,
            title=title[:300], content=text[:100000], content_hash=content_hash, published_at=date_value(published),
            discovered_at=now(), previous_id=previous['id'] if previous else None, kind=kind, original_name=original_name)

    def research(self, company_id):
        company = self.db.company(company_id)
        pages, errors = [], []
        first = self.fetcher.get(company['url'])
        title, text, soup = html_content(first)
        if len(text) < 60:
            raise ValueError('Company website has too little readable content. Try a public About or product page.')
        pages.append({'url': first.url, 'title': title, 'text': text[:14000]})
        links = []
        from bs4 import BeautifulSoup
        # Navigation often contains the only link to the About page.
        for a in BeautifulSoup(first.text, 'html.parser').find_all('a', href=True):
            url = urljoin(first.url, a['href'])
            if urlsplit(url).netloc == urlsplit(first.url).netloc and re.search(r'about|product|solution|customer', url, re.I):
                if url not in links and url != first.url:
                    links.append(url)
        for url in links[:3]:
            try:
                page = self.fetcher.get(url)
                ptitle, ptext, _ = html_content(page)
                pages.append({'url': page.url, 'title': ptitle, 'text': ptext[:14000]})
            except Exception as exc:
                errors.append({'url': url, 'error': safe_error(exc)})
        profile = self.llm.ask('Build company profile only from supplied pages. Verified facts require an EXACT verbatim quote and its page URL. Other claims are assumptions. Competitors are unverified hypotheses unless explicitly evidenced.',
                               {'company': company['name'], 'pages': pages}, Profile).model_dump()
        for fact in profile['facts']:
            matching = next((p for p in pages if p['url'] == fact['url']), None)
            if not matching or not fact['quote'] or normalized(fact['quote']) not in normalized(matching['text']):
                fact['status'], fact['url'], fact['quote'] = 'assumption', '', ''
        if company['profile'] and company['profile'] != profile:
            before, after = json.dumps(company['profile'], indent=2), json.dumps(profile, indent=2)
            diff = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile='previous research', tofile='new research', lineterm=''))
            with self.db.connect() as conn:
                conn.execute('UPDATE companies SET profile=?,context_version=context_version+1,updated_at=? WHERE id=?', (json.dumps(profile), now(), company_id))
                conn.execute("UPDATE sources SET stale=1 WHERE company_id=? AND status!='rejected'", (company_id,))
                conn.execute('INSERT INTO context_changes (company_id,before_profile,after_profile,diff,created_at) VALUES (?,?,?,?,?)',
                    (company_id, before, after, json.dumps({'type': 'research', 'patch': diff}), now()))
        else:
            self.db.run('UPDATE companies SET profile=?,updated_at=? WHERE id=?', (json.dumps(profile), now(), company_id))
        for page in pages:
            sid, _ = self.add_source(company_id, page['url'], page['title'], 'Customers',
                'First-party company context; useful for product and customer positioning.', 'discovered', credibility=.8, relevance=1)
            self.store_document(company_id, sid, page['url'], page['title'], page['text'])
        return {'pages': len(pages), 'profile': profile, 'limitations': errors}

    def next_question(self, company_id):
        context = self.context(company_id)
        answers = context['answers']
        existing = self.db.one("SELECT * FROM profile_answers WHERE company_id=? AND answer='' AND skipped=0 ORDER BY position LIMIT 1", (company_id,))
        if existing:
            return existing
        if len(answers) >= 10:
            return {'complete': True, 'message': 'All 10 questions answered or skipped. You can edit answers below.'}
        if not context['company']['profile']:
            raise ValueError('Research the company first so interview questions can use its profile.')
        result = self.llm.ask('Generate exactly ONE tailored interview question. Across 10 turns explore revenue streams, highest-value customers, unmet needs, differentiation, competitors, industry changes, material risks, 6-12 month growth priorities, internal inputs, and decisions the founder needs to make. These are themes, not a fixed questionnaire. Consider all prior answers and skipped questions; never repeat them. Do not ask multiple questions in one turn. This is question ' + str(len(answers)+1), context, Question)
        if normalized(result.question) in {normalized(a['question']) for a in answers}:
            result = self.llm.ask('The last proposed question duplicated an earlier question. Generate a different single question on an uncovered theme. Do not repeat any prior question.', context | {'rejected_question': result.question}, Question)
            if normalized(result.question) in {normalized(a['question']) for a in answers}:
                raise ValueError('The model repeated an interview question; retry instead of saving a duplicate.')
        qid = self.db.insert('profile_answers', company_id=company_id, position=len(answers)+1,
                              question=result.question, updated_at=now())
        return self.db.one('SELECT * FROM profile_answers WHERE id=?', (qid,)) | {'why': result.why}

    def follow_up(self, company_id, answer_id):
        answer = self.db.one('SELECT * FROM profile_answers WHERE company_id=? AND id=?', (company_id, answer_id))
        if not answer or not answer['answer']:
            raise ValueError('Answer this question before requesting a follow-up.')
        result = self.llm.ask('Ask one short, useful follow-up to clarify this answer. It is optional and does not count toward the ten questions.', self.context(company_id) | {'answer': answer}, FollowUp)
        self.db.run('UPDATE profile_answers SET follow_up=? WHERE id=?', (result.question, answer_id))
        return result.model_dump()

    def discover(self, company_id):
        context = self.context(company_id)
        plan = self.llm.ask('Generate up to 6 targeted web search queries to find customer communities, 5-10 actual competitors and their official sites, industry news, regulators, and market evidence. Tailor queries to the company and answers. Do not use fixed source lists.', context, SearchPlan)
        candidates, errors = {}, []
        for query in plan.queries[:6]:
            try:
                for item in self.fetcher.search(query):
                    candidates[canonical_url(item['url'])] = item
            except Exception as exc:
                errors.append({'query': query, 'error': safe_error(exc)})
        method = 'public search results'
        if not candidates:
            # Search engines may refuse automated requests. Model suggestions are
            # only URL hypotheses: fetch each under robots policy before use.
            existing_urls = {s['url'] for s in self.db.all('SELECT url FROM sources WHERE company_id=?', (company_id,))}
            proposals = self.llm.ask('Public search is unavailable. Propose 30-36 NEW public source URL hypotheses tailored to this company. Include 5-10 additional relevant competitor brands NOT ALREADY in known_competitors, and include each official URL in sources too. Country versions of the same brand are not different competitors. Include customer PROBLEM/review communities, relevant regulators and industry publications. Use at most 3 of the company own marketing pages. Prefer stable official landing pages or RSS feeds over guessed article paths. These URLs are NOT evidence until fetched. Cover varied domains; do not repeat existing source URLs. No hard-coded company list is supplied.',
                context | {'existing_sources': sorted(existing_urls), 'known_competitors': [c['name'] for c in context['company']['profile'].get('competitors', [])]}, SourceHypotheses)
            def observe(source):
                page = self.fetcher.get(source.url)
                if 'xml' in page.content_type or page.text.lstrip().startswith(('<?xml', '<rss', '<feed')):
                    feed = feedparser.parse(page.text)
                    title = feed.feed.get('title', source.name)
                    from bs4 import BeautifulSoup
                    text = ' '.join(BeautifulSoup(entry.get('title', '') + ' ' + entry.get('summary', ''), 'html.parser').get_text(' ', strip=True) for entry in feed.entries[:5])
                else:
                    title, text, _ = html_content(page)
                if len(text) < 100:
                    raise ValueError('Too little public evidence to assess this candidate')
                return {'url': canonical_url(page.url), 'title': title, 'snippet': text[:2200]}
            fresh_proposals = []
            for source in proposals.sources[:36]:
                try:
                    if canonical_url(source.url) not in existing_urls:
                        fresh_proposals.append(source)
                except ValueError as exc:
                    errors.append({'url': source.url, 'error': safe_error(exc)})
            with ThreadPoolExecutor(max_workers=4) as pool:
                pending = {pool.submit(observe, source): source for source in fresh_proposals}
                for future in as_completed(pending):
                    source = pending[future]
                    try:
                        item = future.result()
                        candidates[item['url']] = item
                    except Exception as exc:
                        errors.append({'url': source.url, 'error': safe_error(exc)})
            method = 'model URL hypotheses validated by permitted public HTTP retrieval'
        if not candidates:
            raise ValueError('No usable public sources found. Search and candidate retrieval were unavailable; no sources were invented.')
        scored = self.llm.ask('Select and score relevant sources ONLY from these observed candidates. Return exact candidate URLs and explain relevance using the actual snippets. Cover Customers, Competitors and Market. Customer sources should expose customer problems, not only company mentions. Return 20+ sources and 5-10 competitors only when supported. Competitors must have their official domain present in candidates, not a directory URL. Scores are estimates; a successful fetch does not verify publisher assertions.', context | {'candidates': list(candidates.values())[:48]}, Candidates)
        added, accepted = 0, set()
        for source in scored.sources:
            try:
                url = canonical_url(source.url)
            except ValueError:
                continue
            if url not in candidates:
                continue
            data = source.model_dump()
            for key in ('url', 'name', 'category', 'reason'):
                data.pop(key)
            _, fresh = self.add_source(company_id, url, source.name, source.category, source.reason, **data)
            added += int(fresh)
            accepted.add(url)
        competitors = []
        for competitor in scored.competitors:
            try:
                if canonical_url(competitor.url) in candidates:
                    competitors.append(competitor.model_dump() | {'status': 'candidate; requires review'})
            except ValueError:
                pass
        # A scored, retrieved official competitor source is also a profile
        # candidate even if the model omitted it from its separate list.
        for source in scored.sources:
            if source.category != 'Competitors':
                continue
            try:
                url = canonical_url(source.url)
                if url in accepted:
                    competitors.append({'name': source.name, 'url': url,
                        'reason': source.reason, 'status': 'candidate; requires review'})
            except ValueError:
                continue
        company = context['company']
        previous_competitor_urls = {s['url'] for s in self.db.all("SELECT url FROM sources WHERE company_id=? AND category='Competitors'", (company_id,))}
        observed = {c['url']: c for c in competitors}
        for prior in company['profile'].get('competitors', []):
            try:
                url = canonical_url(prior['url'])
                if url in previous_competitor_urls:
                    observed.setdefault(url, prior)
            except ValueError:
                pass
        competitors = unique_competitors(list(observed.values()))
        profile = company['profile'] | {'competitors': competitors}
        self.db.run('UPDATE companies SET profile=?,updated_at=? WHERE id=?', (json.dumps(profile), now(), company_id))
        return {'added': added, 'candidates': len(candidates), 'competitors': len(competitors), 'queries': plan.queries, 'method': method, 'limitations': errors,
                'note': 'Discovered sources require approval before monitoring.'}

    def crawl_source(self, source):
        cid, sid = source['company_id'], source['id']
        run = self.db.insert('crawl_runs', company_id=cid, source_id=sid, started_at=now(), status='running')
        count, limitations = 0, []
        try:
            page = self.fetcher.get(source['url'], self.db.settings(cid)['request_delay'])
            feed = feedparser.parse(page.text) if ('xml' in page.content_type or page.text.lstrip().startswith(('<?xml', '<rss', '<feed'))) else None
            if not feed or not feed.entries:
                title, text, soup = html_content(page)
                feed_link = soup.find('link', attrs={'type': re.compile(r'application/(rss|atom)\+xml')})
                if feed_link and feed_link.get('href'):
                    try:
                        feed_page = self.fetcher.get(urljoin(page.url, feed_link['href']), self.db.settings(cid)['request_delay'])
                        feed = feedparser.parse(feed_page.text)
                    except Exception as exc:
                        limitations.append({'url': urljoin(page.url, feed_link['href']), 'error': safe_error(exc)})
                        feed = None
            if feed and feed.entries:
                from bs4 import BeautifulSoup
                for entry in feed.entries[:20]:
                    link = entry.get('link')
                    content = entry.get('summary', '') or ' '.join(v.get('value', '') for v in entry.get('content', []))
                    snippet = BeautifulSoup(content, 'html.parser').get_text(' ', strip=True)
                    if not link or not snippet:
                        continue
                    try:
                        url = canonical_url(urljoin(page.url, link))
                    except ValueError:
                        continue
                    count += bool(self.store_document(cid, sid, url, entry.get('title', 'Feed entry'), snippet,
                                      entry.get('published') or entry.get('updated')))
            else:
                if len(text) < 60:
                    raise ValueError('Too little readable content; page may require JavaScript or authentication')
                published = soup.find('meta', attrs={'property': 'article:published_time'}) or soup.find('meta', attrs={'name': 'date'})
                timestamp = soup.find('time', attrs={'datetime': True})
                publication = published.get('content') if published else timestamp.get('datetime') if timestamp else None
                count += bool(self.store_document(cid, sid, page.url, title, text, publication))
                # A small, same-site article sample is a bounded HTML fallback,
                # not an unrestricted site crawl. Every article has its own policy check.
                articles = []
                for anchor in soup.find_all('a', href=True):
                    target = urljoin(page.url, anchor['href'])
                    path = urlsplit(target).path
                    if (urlsplit(target).netloc == urlsplit(page.url).netloc
                        and target != page.url and len(path.strip('/').split('/')) >= 2
                        and re.search(r'/news/|/blog/|/articles/|/insights/|/20\d\d/\d\d/', path)
                        and not re.search(r'/tag/|/category/|/author/|/page/', path)
                        and target not in articles):
                        articles.append(target)
                for target in articles[:3]:
                    try:
                        article = self.fetcher.get(target, self.db.settings(cid)['request_delay'])
                        atitle, atext, asoup = html_content(article)
                        meta = asoup.find('meta', attrs={'property': 'article:published_time'})
                        atime = asoup.find('time', attrs={'datetime': True})
                        published = meta.get('content') if meta else atime.get('datetime') if atime else None
                        if len(atext) >= 60:
                            count += bool(self.store_document(cid, sid, article.url, atitle, atext, published))
                    except Exception as exc:
                        limitations.append({'url': target, 'error': safe_error(exc)})
            changed = source['content_hash'] is not None and source['content_hash'] != digest(page.text)
            reliability = min(1, source['reliability'] + .05)
            self.db.run("UPDATE sources SET health='healthy',error=NULL,last_checked=?,last_success=?,content_hash=?,reliability=? WHERE id=?", (now(), now(), digest(page.text), reliability, sid))
            detail = ('Content changed' if changed else 'Checked; RSS preferred when available')
            if limitations:
                detail += '; some feed/article URLs unavailable: ' + json.dumps(limitations)
            self.db.run("UPDATE crawl_runs SET status='success',finished_at=?,records=?,detail=? WHERE id=?", (now(), count, detail, run))
            return {'source_id': sid, 'records': count, 'changed': changed, 'limitations': limitations}
        except Exception as exc:
            error = safe_error(exc)
            self.db.run("UPDATE sources SET health='failed',error=?,last_checked=?,reliability=? WHERE id=?", (error, now(), max(0, source['reliability'] - .15), sid))
            self.db.run("UPDATE crawl_runs SET status='failed',finished_at=?,detail=? WHERE id=?", (now(), error, run))
            return {'source_id': sid, 'records': 0, 'error': error}

    def crawl(self, company_id):
        sources = self.db.all("SELECT * FROM sources WHERE company_id=? AND status='approved' ORDER BY COALESCE(last_checked,'') LIMIT ?", (company_id, self.db.settings(company_id)['max_sources_per_run']))
        if not sources:
            raise ValueError('Approve at least one source before running the crawler.')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(self.crawl_source, sources))
        if all('error' in r for r in results):
            raise ValueError('Every source failed. See source health and crawl history for individual errors.')
        return {'records': sum(r['records'] for r in results), 'sources': results, 'failures': sum('error' in r for r in results)}

    def intake(self, company_id, filename, content):
        suffix = Path(filename).suffix.lower()
        if suffix in ('.txt', '.md'):
            chunks = [s.strip() for s in re.split(r'\n\s*\n', content.decode('utf-8-sig')) if s.strip()]
        elif suffix == '.csv':
            reader = csv.DictReader(io.StringIO(content.decode('utf-8-sig')))
            chunks = [json.dumps(r, ensure_ascii=False) for _, r in zip(range(1000), reader)]
        elif suffix == '.xlsx':
            from openpyxl import load_workbook
            # XLSX is a ZIP; reject decompression bombs before opening it.
            import zipfile
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 40_000_000:
                    raise ValueError('Expanded workbook exceeds 40 MB limit')
            book = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            chunks = []
            for sheet in book:
                for row in sheet.iter_rows(values_only=True):
                    if len(chunks) >= 1000:
                        break
                    text = ' | '.join(str(v) for v in row if v is not None)
                    if text:
                        chunks.append(f'{sheet.title}: {text}')
            book.close()
        elif suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(content))
            if len(reader.pages) > 100:
                raise ValueError('PDF exceeds 100-page limit')
            chunks = [f'Page {i+1}: {p.extract_text() or ""}' for i, p in enumerate(reader.pages)]
        else:
            raise ValueError('Supported formats: CSV, XLSX, PDF, TXT and Markdown. Scanned PDFs need OCR first.')
        added = 0
        upload_hash = digest(content.hex())[:20]
        for i, text in enumerate(chunks[:1000]):
            if len(text.strip()) < 10:
                continue
            added += bool(self.store_document(company_id, None, f'/api/companies/{company_id}/internal/{upload_hash}#record-{i+1}',
                f'{Path(filename).name} · record {i+1}', text, kind='internal', original_name=Path(filename).name))
        if not added:
            return {'records': 0, 'note': 'No new readable records; file may be empty, scanned, or already imported.'}
        return {'records': added, 'note': 'Stored as internal evidence. Run analysis to extract objections, lost-deal reasons, requests and risks.'}

    def analyze_document(self, company_id, document, context):
        source = self.db.one('SELECT * FROM sources WHERE id=?', (document['source_id'],)) if document['source_id'] else None
        result = self.llm.ask('Analyze this one document for this company. Extract the most substantive signal, or classify neutral with low relevance. evidence_quote MUST be an exact contiguous excerpt. A homepage, about page or general service description is background: set is_development=false unless the text actually reports a change, customer problem or new event. Do not invent launches or dates. event_date must be explicitly present, otherwise empty. Differentiate internal objections, lost deals, requests, sales patterns and risks. Explain concrete business implications and an evidence-specific next step; avoid generic advice. suggested_owner is a recommended ROLE, not an asserted employee. competitor_name must be supported by the text and company context. watch_reason explains an early development worth watching, otherwise empty. Interpretation is never independently verified fact.', context | {'document': {k: document[k] for k in ('title', 'url', 'content', 'published_at', 'kind')}, 'source': source}, Interpretation)
        if not result.evidence_quote or normalized(result.evidence_quote) not in normalized(document['content']):
            raise ValueError(f"Document {document['id']}: AI quote was not present in evidence; signal rejected")
        factors = self.factors(document, result, source, company_id)
        score = round(100 * sum(factors[k] * WEIGHTS[k] for k in WEIGHTS), 1)
        evidence = {'url': document['url'], 'title': document['title'], 'quote': result.evidence_quote,
            'published_at': document['published_at'], 'discovered_at': document['discovered_at'],
            'verified': False, 'quote_matched': True, 'verification': 'Source-reported; quote matched retrieved text, claim not independently corroborated.',
            'kind': document['kind'], 'document_id': document['id'], 'source_url': source['url'] if source else document['url']}
        old = self.db.one('SELECT evidence FROM signals WHERE document_id=?', (document['id'],))
        if old:
            reviewed = json.loads(old['evidence'])
            if reviewed.get('user_reviewed') and normalized(reviewed['quote']) == normalized(evidence['quote']):
                for field in ('verified', 'verification', 'user_reviewed', 'reviewed_at'):
                    if field in reviewed:
                        evidence[field] = reviewed[field]
        explanation = '; '.join(f'{k} {factors[k]:.2f} × {WEIGHTS[k]:.0%}' for k in WEIGHTS)
        interpretation = result.model_dump(exclude={'evidence_quote'})
        prior_signal = self.db.one('SELECT category FROM signals WHERE document_id=?', (document['id'],))
        category = source['category'] if source else ('Internal' if document['kind'] == 'internal' else (prior_signal['category'] if prior_signal else 'Market'))
        values = (company_id, document['id'], category, json.dumps(evidence), json.dumps(interpretation),
            score, json.dumps(factors), source['reliability'] if source else .7, result.evidence_strength,
            result.relevance, explanation, context['company']['context_version'], now())
        self.db.run('''INSERT INTO signals (company_id,document_id,category,evidence,interpretation,score,factors,reliability,evidence_strength,strategic_relevance,explanation,context_version,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(document_id) DO UPDATE SET evidence=excluded.evidence,
            interpretation=excluded.interpretation,category=excluded.category,score=excluded.score,factors=excluded.factors,reliability=excluded.reliability,
            evidence_strength=excluded.evidence_strength,strategic_relevance=excluded.strategic_relevance,
            explanation=excluded.explanation,context_version=excluded.context_version,created_at=excluded.created_at''', values)
        return score

    def factors(self, document, result, source, company_id):
        published = date_value(document['published_at'])
        if published:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(published)).total_seconds() / 86400
            recency = math.exp(-max(0, age) / 14) if age >= -1 else 0
        else:
            recency = .35  # Discovery date is not a publication date.
        prior = self.db.one('SELECT COUNT(*) n FROM documents WHERE company_id=? AND url=? AND id<>?', (company_id, document['url'], document['id']))['n']
        return {'relevance': result.relevance, 'impact': result.impact, 'urgency': result.urgency_score,
            'credibility': ((source['credibility'] if source else .7) + result.evidence_strength) / 2,
            'recency': recency, 'novelty': 1 if not prior else .5}

    def analyze(self, company_id, force=False):
        context = self.context(company_id)
        documents = self.db.all('''SELECT d.* FROM documents d LEFT JOIN signals s ON d.id=s.document_id
            WHERE d.company_id=? AND (? OR s.id IS NULL OR s.context_version<?) ORDER BY d.id DESC LIMIT 100''',
            (company_id, int(force), context['company']['context_version']))
        analyzed, errors = 0, []
        for document in documents:
            try:
                self.analyze_document(company_id, document, context)
                analyzed += 1
            except Exception as exc:
                errors.append({'document_id': document['id'], 'error': safe_error(exc)})
                from .llm import LLMUnavailable
                if isinstance(exc, LLMUnavailable):
                    break
        if errors and not analyzed:
            raise ValueError(errors[0]['error'])
        return {'analyzed': analyzed, 'failures': errors}

    def signals(self, company_id):
        rows = self.db.all('SELECT * FROM signals WHERE company_id=? ORDER BY created_at DESC,id DESC', (company_id,))
        for row in rows:
            for field in ('evidence', 'interpretation', 'factors'):
                row[field] = json.loads(row[field])
        return rows

    def brief(self, company_id):
        from .briefs import compose
        company = self.db.company(company_id)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        signals = [s for s in self.signals(company_id) if s['evidence']['discovered_at'] >= cutoff and s['context_version'] == company['context_version']]
        if not signals:
            raise ValueError('No analyzed evidence in the last 7 days for the current profile. Crawl or upload evidence, then analyze first.')
        title, sections, markdown, developments, opportunities = compose(self.db, company, signals)
        opportunity_error = None
        if opportunities < 3 and developments >= 3:
            eligible_ids = {item['signal_id'] for section in sections[:5] for item in section['items']}
            evidence = [s for s in sorted(signals, key=lambda s: s['score'], reverse=True) if s['id'] in eligible_ids][:15]
            try:
                plan = self.llm.ask('Identify distinct, actionable business opportunities supported ONLY by these existing signal IDs and their excerpts for this company. Opportunities may be practical responses to threats, such as testing a specific service or reducing an evidenced customer pain. They are conditional AI recommendations, NOT new developments, verified facts, or assertions about private company plans. Do not invent events, revenue, customers, quotations or URLs. Explain concrete business impact, an evidence-specific next step, priority and a suggested ROLE. Avoid generic advice. Aim for three only when the evidence supports three genuinely different initiatives; otherwise return fewer or none. Do not pad the report.',
                    {'company': company, 'signals': evidence}, OpportunityPlan)
                title, sections, markdown, developments, opportunities = compose(self.db, company, signals, plan.opportunities)
            except Exception as exc:
                opportunity_error = safe_error(exc)
        bid = self.db.insert('briefs', company_id=company_id, title=title, sections=json.dumps(sections),
            markdown=markdown, context_version=company['context_version'], created_at=now())
        limitations = []
        if opportunity_error:
            limitations.append({'opportunity_analysis': opportunity_error})
        if opportunities < 3:
            limitations.append({'requirement': 'At least three evidence-supported opportunities', 'observed': opportunities})
        return {'brief_id': bid, 'signals': len(signals), 'developments': developments,
                'opportunities': opportunities, 'sections': len(sections), 'limitations': limitations}

    def audit(self, company_id):
        sources = self.db.all('SELECT * FROM sources WHERE company_id=?', (company_id,))
        issues, domains = [], {}
        for source in sources:
            if source['status'] == 'rejected':
                continue
            host = urlsplit(source['url']).hostname
            if host in domains:
                issues.append({'source_id': source['id'], 'issue': 'possible duplicate domain', 'related_id': domains[host]})
            domains[host] = source['id']
            if source['status'] == 'approved':
                try:
                    self.fetcher.get(source['url'], self.db.settings(company_id)['request_delay'])
                    self.db.run("UPDATE sources SET health='healthy',error=NULL,last_checked=?,last_success=? WHERE id=?", (now(), now(), source['id']))
                except Exception as exc:
                    error = safe_error(exc)
                    self.db.run("UPDATE sources SET health='failed',error=?,last_checked=? WHERE id=?", (error, now(), source['id']))
                    issues.append({'source_id': source['id'], 'issue': 'dead or blocked URL', 'detail': error})
            last = self.db.one('SELECT MAX(discovered_at) latest FROM documents WHERE source_id=?', (source['id'],))['latest']
            if not last or last < (datetime.now(timezone.utc)-timedelta(days=30)).isoformat():
                issues.append({'source_id': source['id'], 'issue': 'inactive; no new records in 30 days'})
            if source['stale'] or source['relevance'] < .3:
                issues.append({'source_id': source['id'], 'issue': 'declining or stale relevance; review for retirement'})
        try:
            reassessed = self.reassess(company_id)
        except Exception as exc:
            reassessed = {'error': safe_error(exc)}
        try:
            discovery = self.discover(company_id)
        except Exception as exc:
            discovery = {'error': safe_error(exc)}
        return {'report_type': 'monthly_source_health', 'generated_at': now(),
                'summary': {'sources_checked': len(sources), 'issues': len(issues)},
                'issues': issues, 'reassessment': reassessed, 'discovery': discovery,
                'removal_candidates': sorted({i['source_id'] for i in issues}),
                'recommendations': 'Review possible duplicates, replace dead sources, and approve relevant new candidates. No source was automatically rejected.'}

    def reassess(self, company_id):
        context = self.context(company_id)
        sources = self.db.all("SELECT id,name,url,category,reason,relevance FROM sources WHERE company_id=? AND status!='rejected'", (company_id,))
        if not sources:
            return {'sources': [], 'new_queries': []}
        result = self.llm.ask('Re-assess every source against the current company profile and interview. Explain relevance changes. Suggest new search queries. Return only supplied source IDs.', context | {'sources': sources}, Reassessment)
        existing = {s['id']: s for s in sources}
        changes = []
        for item in result.sources:
            if item.id not in existing:
                continue
            old = existing[item.id]
            self.db.run('UPDATE sources SET relevance=?,reason=?,stale=?,context_version=? WHERE id=? AND company_id=?',
                (item.relevance, item.reason, int(item.relevance < .4), context['company']['context_version'], item.id, company_id))
            changes.append({'source_id': item.id, 'name': old['name'], 'before': old['relevance'], 'after': item.relevance, 'reason': item.reason})
        return {'sources': changes, 'new_queries': result.new_queries}

    def context_change(self, company_id):
        result = self.reassess(company_id)
        analysis = self.analyze(company_id)
        try:
            discovery = self.discover(company_id)
        except Exception as exc:
            discovery = {'error': safe_error(exc)}
        self.db.insert('context_changes', company_id=company_id, before_profile='{}', after_profile='{}',
            diff=json.dumps({'type': 'reassessment', **result, 'analysis': analysis, 'new_candidates': discovery}), created_at=now())
        return result | {'analysis': analysis, 'new_candidates': discovery}

    def update_profile(self, company_id, profile):
        company = self.db.company(company_id)
        # User-authored edits cannot mint verified facts.
        old_facts = {json.dumps(f, sort_keys=True) for f in company['profile'].get('facts', []) if f.get('status') == 'verified'}
        for fact in profile.get('facts', []):
            if fact.get('status') == 'verified' and json.dumps(fact, sort_keys=True) not in old_facts:
                fact.update(status='assumption', url='', quote='')
        before, after = json.dumps(company['profile'], indent=2), json.dumps(profile, indent=2)
        diff = '\n'.join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile='previous profile', tofile='updated profile', lineterm=''))
        with self.db.connect() as db:
            db.execute('UPDATE companies SET profile=?,context_version=context_version+1,updated_at=? WHERE id=?', (json.dumps(profile), now(), company_id))
            db.execute("UPDATE sources SET stale=1 WHERE company_id=? AND status!='rejected'", (company_id,))
            db.execute('INSERT INTO context_changes (company_id,before_profile,after_profile,diff,created_at) VALUES (?,?,?,?,?)',
                (company_id, before, after, json.dumps({'type': 'profile', 'patch': diff}), now()))
        return {'version': company['context_version']+1, 'diff': diff}


def safe_error(exc):
    import httpx
    if isinstance(exc, httpx.HTTPStatusError):
        return f'HTTP {exc.response.status_code}: public resource unavailable'
    if isinstance(exc, httpx.HTTPError):
        return f'Network error: {type(exc).__name__}'
    return str(exc)[:700]
