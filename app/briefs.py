"""The ten report sections required by the EDXSO assignment."""
import json
from datetime import datetime, timedelta, timezone

from .db import now
from .dates import explicit_date

SECTIONS = ['Executive Summary', 'Customer Signals', 'Competitor Intelligence', 'Market Intelligence',
            'Internal Business Intelligence', 'Opportunities Identified', 'Risks & Threats',
            'Recommended Actions for This Week', 'What We Should Watch', 'Source Appendix']


def compose(db, company, signals, opportunity_ideas=()):
    ranked = sorted(signals, key=lambda s: s['score'], reverse=True)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    def freshness(signal):
        raw = signal['evidence'].get('published_at') or signal['interpretation'].get('event_date')
        if not raw:
            return 'Date unknown; not established as a new event this week'
        stamp = explicit_date(raw)
        if stamp is None:
            return 'Date unknown; not established as a new event this week'
        return 'Dated within the last seven days' if cutoff <= stamp <= datetime.now(timezone.utc)+timedelta(days=1) else 'Historical or outside the current week'
    # Background company descriptions are traceable context, not new developments.
    developments = [s for s in ranked if s['interpretation'].get('is_development', True) and freshness(s) != 'Historical or outside the current week']
    sections = [{'title': name, 'items': []} for name in SECTIONS]

    def item(signal, action=False):
        evidence, analysis = signal['evidence'], signal['interpretation']
        return {'signal_id': signal['id'], 'text': analysis['suggested_action'] if action else analysis['what'],
                'evidence': evidence['quote'], 'url': evidence['url'], 'score': signal['score'],
                'why': analysis['why_it_matters'], 'impact': round(100 * analysis['impact']),
                'priority': 'high' if signal['score'] >= 70 else 'medium' if signal['score'] >= 40 else 'low',
                'urgency': analysis['urgency'], 'next_step': analysis['suggested_action'],
                'suggested_owner': analysis.get('suggested_owner', 'Strategy lead (suggested role)'),
                'published_at': evidence.get('published_at'), 'discovered_at': evidence['discovered_at'],
                'when': analysis.get('event_date') or evidence.get('published_at') or 'Date not established by the source',
                'freshness': freshness(signal),
                'original_source': evidence.get('source_url') or evidence['url'],
                'verified': bool(evidence.get('verified')),
                'verification': evidence.get('verification', 'Not independently corroborated'),
                'evidence_strength': signal['evidence_strength']}

    sections[0]['items'] = [item(s) for s in developments[:5]]
    answered = db.one("SELECT COUNT(*) n FROM profile_answers WHERE company_id=? AND answer!='' AND skipped=0", (company['id'],))['n']
    sections[0]['note'] = (f'{len(developments)} source-supported developments from the current collection window; '
        'items with unknown event dates are explicitly marked and are not confirmed as new this week. '
        f'{len(ranked) - len(developments)} background/historical records excluded from development headlines. '
        f'{max(0, 10-answered)} interview questions remain unanswered or skipped. '
        'Interpretations and suggested roles are AI assessments, not independently verified facts.')
    for index, category in enumerate(('Customers', 'Competitors', 'Market', 'Internal'), 1):
        sections[index]['items'] = [item(s) for s in developments if s['category'] == category][:8]
    opportunities = [s for s in developments if s['interpretation']['sentiment'] == 'opportunity']
    sections[5]['items'] = [item(s) for s in opportunities[:6]]
    eligible = {s['id']: s for s in developments}
    existing_titles = {v['text'].strip().casefold() for v in sections[5]['items']}
    for idea in opportunity_ideas:
        if not idea.signal_ids or not all(sid in eligible for sid in idea.signal_ids):
            continue
        if idea.title.strip().casefold() in existing_titles:
            continue
        proposed = item(eligible[idea.signal_ids[0]])
        proposed.update(text=idea.title, why=idea.impact_statement, next_step=idea.next_step,
            priority=idea.priority, suggested_owner=idea.suggested_owner,
            interpretation_type='AI-proposed response to existing evidence; not a new event',
            supporting_signal_ids=idea.signal_ids)
        sections[5]['items'].append(proposed)
        existing_titles.add(idea.title.strip().casefold())
        if len(sections[5]['items']) >= 6:
            break
    opportunity_count = len(sections[5]['items'])
    if opportunity_count < 3:
        sections[5]['note'] = f'Only {opportunity_count} evidence-supported opportunities this week; the target of 3 was not met.'
    elif opportunity_ideas:
        sections[5]['note'] = 'Opportunities can be proposed responses to reported risks. These are AI recommendations, not additional events or claims about current company strategy.'
    sections[6]['items'] = [item(s) for s in developments if s['interpretation']['sentiment'] == 'threat'][:6]
    sections[7]['items'] = [item(s, action=True) for s in developments if s['interpretation']['suggested_action']][:6]
    for signal in ranked:
        reason = signal['interpretation'].get('watch_reason')
        if reason:
            watch = item(signal)
            watch['text'] = reason
            sections[8]['items'].append(watch)
    sections[8]['items'] = sections[8]['items'][:6]
    for signal in ranked:
        appendix = item(signal)
        appendix['text'] = signal['evidence']['title']
        appendix['kind'] = 'source_appendix'
        sections[9]['items'].append(appendix)
    sources = db.all('SELECT status,health,stale FROM sources WHERE company_id=?', (company['id'],))
    sections[9]['note'] = (f'{len(sources)} sources; {sum(s["status"]=="approved" for s in sources)} approved; '
        f'{sum(s["health"]=="failed" for s in sources)} failed; {sum(s["stale"] for s in sources)} need context review. '
        'An exact text match confirms the excerpt exists; it does not independently prove the event. '
        'Publication dates are left unknown when not supplied by the publisher.')
    for section in sections:
        if not section['items']:
            section['note'] = (section.get('note', '') + ' No meaningful development supported by collected evidence this week.').strip()
    title = f'{company["name"]} - Monday Morning Brief - {datetime.now(timezone.utc):%d %b %Y}'
    lines = [f'# {title}', '', f'Context version {company["context_version"]}. Window: last 7 days. Generated {now()}.', '']
    for section in sections:
        lines += ['## ' + section['title'], '']
        if section.get('note'):
            lines += [section['note'], '']
        for record in section['items']:
            label = 'Original source' if record.get('kind') == 'source_appendix' else 'AI interpretation'
            lines += [f'- **{label}:** {record["text"]} (score {record["score"]})',
                f'  - Evidence: "{record["evidence"]}"', f'  - Source: {record["url"]}',
                f'  - Original source: {record["original_source"]}',
                f'  - Published: {record["published_at"] or "Unknown"}; discovered: {record["discovered_at"]}',
                f'  - Freshness: {record["freshness"]}',
                f'  - Verification: {record["verification"]}',
                f'  - Why it matters (AI): {record["why"]}',
                f'  - Impact (AI): {record["impact"]}/100; priority: {record["priority"]}; urgency: {record["urgency"]}',
                f'  - Next step (AI): {record["next_step"]}',
                f'  - Suggested owner (role): {record["suggested_owner"]}', '']
    return title, sections, '\n'.join(lines), len(developments), opportunity_count
