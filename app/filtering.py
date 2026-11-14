from datetime import date
import re
from urllib.parse import urlsplit
from .dates import explicit_date


def filter_signals(rows, *, category='', sentiment='', urgency='', q='', min_score=0,
                   competitor='', date_from='', date_to='', min_relevance=0, min_impact=0,
                   verification='', sort='latest', competitors=()):
    for value in (date_from, date_to):
        if value:
            date.fromisoformat(value)
    if date_from and date_to and date_from > date_to:
        raise ValueError('Start date must be before or equal to end date')
    matched = []
    for row in rows:
        evidence, interpretation = row['evidence'], row['interpretation']
        day = ''
        for value in (interpretation.get('event_date'), evidence.get('published_at'), evidence['discovered_at']):
            stamp = explicit_date(value)
            if stamp:
                day = stamp.date().isoformat()
                break
        if category and row['category'] != category:
            continue
        if sentiment and interpretation['sentiment'] != sentiment or urgency and interpretation['urgency'] != urgency:
            continue
        if row['score'] < min_score or interpretation['relevance'] < min_relevance or interpretation['impact'] < min_impact:
            continue
        if date_from and day < date_from or date_to and day > date_to:
            continue
        if verification == 'verified' and not evidence.get('verified'):
            continue
        if verification == 'unverified' and evidence.get('verified'):
            continue
        if verification == 'quote_matched' and not (evidence.get('quote_matched') or 'quote matched' in evidence.get('verification', '').lower()):
            continue
        if competitor:
            name = interpretation.get('competitor_name', '').casefold()
            host = urlsplit(evidence['url']).hostname or ''
            pattern = r'(?<!\w)' + re.escape(competitor.casefold()) + r'(?!\w)'
            targets = [c for c in competitors if re.search(pattern, c['name'].casefold())]
            if not re.search(pattern, name) and not any((urlsplit(c['url']).hostname or '').removeprefix('www.') == host.removeprefix('www.') for c in targets):
                continue
        if q:
            import json
            if q.casefold() not in json.dumps(row, ensure_ascii=False).casefold():
                continue
        matched.append(row)
    if sort == 'importance':
        matched.sort(key=lambda s: s['score'], reverse=True)
    else:
        matched.sort(key=lambda s: (s['evidence'].get('published_at') or s['evidence']['discovered_at'], s['id']), reverse=sort != 'oldest')
    return matched
