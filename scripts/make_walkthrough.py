"""Captioned screen-sequence tour from actual QA screenshots; no live AI claims.

Optional authoring dependencies: pillow, imageio-ffmpeg.
"""
import sys
import textwrap
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
PAGES = [
    ('01-overview','The workspace','Real counts, channel mix, setup checklist and job outcomes. One approved public source and one real collected record are present.'),
    ('02-company','Company context','Research with Gemini. Exact excerpts support fact labels; unsupported claims remain assumptions. Live AI needs a local key.'),
    ('03-interview','Strategic context','Ten tailored questions, one at a time. Save, skip, edit and ask follow-ups. Prior answers shape the next question.'),
    ('04-stack','The signal stack','Discover candidates or add a source. Review, approve, inspect health and crawl history. The real website crawl succeeded.'),
    ('05-feed','Evidence into perspective','Collect web evidence and import CSV, Excel, PDF or text. Inspect separate evidence, AI interpretation and ranking factors.'),
    ('06-brief','The Monday perspective','Ten sections with explicit empty categories. Export Markdown, HTML and PDF. Live AI brief generation awaits Gemini setup.'),
    ('07-actions','Turn insight into action','Create tasks with owners, due dates and status. Move work from open to in progress and completed.'),
    ('08-automation','A reliable rhythm','Choose timezone and cadence. Run weekly pipelines, audits and reassessment. Inspect every failure or partial result.'),
]


def main():
    def font(name,size):
        p=Path('C:/Windows/Fonts')/name
        return ImageFont.truetype(str(p),size) if p.exists() else ImageFont.load_default(size=size)
    title_font,label_font,body_font=font('georgia.ttf',32),font('segoeui.ttf',16),font('segoeui.ttf',21)
    out=Path('output/Signal_Stack_Dashboard_Tour.mp4')
    writer=imageio_ffmpeg.write_frames(str(out),(1280,960),fps=4,codec='libx264',pix_fmt_in='rgb24',pix_fmt_out='yuv420p',quality=8,ffmpeg_log_level='error')
    writer.send(None)
    for i,(filename,title,caption) in enumerate(PAGES):
        frame=Image.new('RGB',(1280,960),'#f8f9f5');draw=ImageDraw.Draw(frame)
        draw.text((30,22),'SIGNAL STACK / DASHBOARD TOUR',font=label_font,fill='#708256')
        draw.text((1130,22),f'{i+1:02d} / 08',font=label_font,fill='#708256')
        shot=Image.open(Path('output/screenshots')/(filename+'.png')).convert('RGB')
        shot.thumbnail((900,850),Image.Resampling.LANCZOS);frame.paste(shot,(24,78))
        draw.rounded_rectangle((944,78,1256,910),radius=10,fill='#eaf0e0',outline='#d9e2cb')
        draw.text((965,103),'THE WORKFLOW',font=label_font,fill='#708256');y=150
        for line in textwrap.wrap(title,17):
            draw.text((965,y),line,font=title_font,fill='#214736');y+=43
        y+=28
        for line in textwrap.wrap(caption,25):
            draw.text((965,y),line,font=body_font,fill='#617454');y+=32
        draw.text((965,815),'Local UI screen sequence',font=label_font,fill='#738466')
        draw.text((965,842),'Gemini not configured',font=label_font,fill='#9a734b')
        draw.text((30,932),'Actual screenshots. Controlled fixture tests are separate from live acceptance.',font=label_font,fill='#839175')
        for _ in range(24):writer.send(frame.tobytes())
    writer.close();print(str(out.resolve()),'(48 seconds; captioned screen sequence)')


if __name__=='__main__':main()
