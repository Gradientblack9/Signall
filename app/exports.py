import html
import io
import json


def item_details(item):
    details = []
    for field, label in [('impact', 'Impact (AI, /100)'), ('priority', 'Priority'), ('urgency', 'Urgency'),
                         ('next_step', 'Next step (AI)'), ('suggested_owner', 'Suggested owner (role)'),
                         ('original_source', 'Original source'), ('published_at', 'Published'),
                         ('discovered_at', 'Discovered'), ('verification', 'Verification')]:
        if field in item:
            details.append((label, str(item[field]) if item[field] is not None else 'Unknown'))
    if 'evidence_strength' in item:
        details.append(('Evidence strength (AI; not proof)', f'{item["evidence_strength"]:.0%}'))
    if 'freshness' in item:
        details.append(('Freshness', item['freshness']))
    return details


def brief_html(brief):
    sections = json.loads(brief['sections'])
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>', html.escape(brief['title']),
        '</title><style>body{font:16px/1.65 system-ui;max-width:860px;margin:60px auto;padding:0 24px;color:#17352f}h1{font-size:36px}h2{border-top:1px solid #ddd;padding-top:20px}article{margin-bottom:24px}blockquote{border-left:3px solid #6a8b65;margin-left:0;padding-left:18px;color:#52665e}small{color:#666}a{color:#276f52}@media print{body{margin:0}article{break-inside:avoid}}</style><body>',
        '<small>SIGNAL STACK · EXECUTIVE INTELLIGENCE</small><h1>', html.escape(brief['title']), '</h1>',
        '<p>Generated ', html.escape(brief['created_at']), ' · Context ', str(brief['context_version']), '</p>']
    for section in sections:
        parts += ['<h2>', html.escape(section['title']), '</h2>']
        if section.get('note'):
            parts += ['<p>', html.escape(section['note']), '</p>']
        for item in section['items']:
            label = 'Original source:' if item.get('kind') == 'source_appendix' else 'AI interpretation:'
            parts += ['<article><b>' + label + '</b> ', html.escape(item['text']),
                '<blockquote><b>Evidence:</b> ', html.escape(item['evidence']), '</blockquote>',
                '<a href="', html.escape(item['url'], quote=True), '">Evidence source</a><p><b>Why it matters (AI):</b> ',
                html.escape(item['why']), '</p><dl>']
            for name, value in item_details(item):
                parts += ['<dt><b>', html.escape(name), '</b></dt><dd>', html.escape(value), '</dd>']
            parts += ['</dl></article>']
    parts += ['</body></html>']
    return ''.join(parts)


def brief_pdf(brief):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, CondPageBreak
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    styles['Heading2'].keepWithNext = True
    styles.add(ParagraphStyle(name='Evidence', parent=styles['BodyText'], leftIndent=14,
        textColor=colors.HexColor('#486258'), spaceAfter=10, leading=14))
    doc = SimpleDocTemplate(buffer, pagesize=(8.27*inch,11.69*inch), rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    def esc(text):
        return html.escape(str(text)).replace('\n', '<br/>')
    story = [Paragraph('SIGNAL STACK / EXECUTIVE INTELLIGENCE', styles['Heading3']),
        Paragraph(esc(brief['title']), styles['Title']),
        Paragraph(esc(f"Generated {brief['created_at']} / context {brief['context_version']}"), styles['BodyText']), Spacer(1, 18)]
    for section in json.loads(brief['sections']):
        story += [CondPageBreak(180), Paragraph(esc(section['title']), styles['Heading2'])]
        if section.get('note'):
            story += [Paragraph(esc(section['note']), styles['BodyText']), Spacer(1, 10)]
        for item in section['items']:
            label = 'Original source:' if item.get('kind') == 'source_appendix' else 'AI interpretation:'
            paragraphs = [Paragraph('<b>' + label + '</b> ' + esc(item['text']), styles['BodyText']),
                Paragraph('<b>Evidence:</b> ' + esc(item['evidence']), styles['Evidence']),
                Paragraph('<link href="' + html.escape(item['url'], quote=True) + '">Source: ' + esc(item['url']) + '</link>', styles['Evidence']),
                Paragraph('<b>Why it matters (AI):</b> ' + esc(item['why']), styles['BodyText'])]
            paragraphs += [Paragraph('<b>' + esc(name) + ':</b> ' + esc(value), styles['Evidence']) for name, value in item_details(item)]
            story += [KeepTogether(paragraphs), Spacer(1, 15)]
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.HexColor('#486258'))
        canvas.drawString(48, 28, 'Signal Stack | Evidence and AI interpretation are separate')
        canvas.drawRightString(document.width+48, 28, str(document.page))
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
