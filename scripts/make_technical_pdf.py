"""Render the five-section technical guide as a five-page delivery document."""
import html
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer


def main():
    target=Path('output/Signal_Stack_Technical_Guide.pdf');target.parent.mkdir(parents=True,exist_ok=True)
    source=Path('docs/TECHNICAL.md').read_text(encoding='utf-8')
    sections=re.split(r'^## ',source,flags=re.M)[1:]
    body=ParagraphStyle('Body',fontName='Helvetica',fontSize=9.3,leading=12.3,textColor=colors.HexColor('#222222'),spaceAfter=7)
    title=ParagraphStyle('Title',fontName='Times-Roman',fontSize=25,leading=29,textColor=colors.HexColor('#214736'),spaceAfter=17)
    eyebrow=ParagraphStyle('Eyebrow',fontName='Helvetica-Bold',fontSize=8,leading=12,textColor=colors.HexColor('#819360'),spaceAfter=15)
    story=[]
    for i,section in enumerate(sections):
        heading,text=section.split('\n',1)
        if i:story.append(PageBreak())
        story+=[Paragraph('SIGNAL STACK / TECHNICAL GUIDE',eyebrow),Paragraph(html.escape(heading),title)]
        for paragraph in text.strip().split('\n\n'):
            paragraph=html.escape(paragraph)
            paragraph=re.sub(r'`([^`]+)`',r'<font name="Courier" size="8.1">\1</font>',paragraph)
            paragraph=re.sub(r'\*\*([^*]+)\*\*',r'<b>\1</b>',paragraph)
            story.append(Paragraph(paragraph,body))
    def footer(canvas,doc):
        canvas.saveState();canvas.setStrokeColor(colors.HexColor('#dce5d3'));canvas.line(18*mm,17*mm,192*mm,17*mm)
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#819078'))
        canvas.drawString(18*mm,12*mm,'Signal Stack | Local implementation and operational limits')
        canvas.drawRightString(192*mm,12*mm,f'{doc.page} / 5');canvas.restoreState()
    document=SimpleDocTemplate(str(target),pagesize=(210*mm,297*mm),leftMargin=18*mm,rightMargin=18*mm,topMargin=18*mm,bottomMargin=23*mm)
    document.build(story,onFirstPage=footer,onLaterPages=footer)
    from pypdf import PdfReader
    pages=len(PdfReader(target).pages)
    if pages!=5:raise RuntimeError(f'Expected five pages, got {pages}; adjust layout before delivery')
    print(str(target.resolve()),f'({pages} pages)')


if __name__=='__main__':main()
