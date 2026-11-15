"""Create a submission archive without credentials, runtime databases or environments."""
import hashlib
import json
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
files=[]
for directory in ['app','static','docs','scripts','tests']:
    files.extend(p for p in (root/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for name in ['requirements.txt','README.md','Dockerfile','compose.yaml','start.ps1','.env.example','.gitignore','.dockerignore']:
    files.append(root/name)
for directory in ['assignment-audit']:
    files.extend(p for p in (root/'output'/directory).rglob('*') if p.is_file())
for name in ['Signal_Stack_Technical_Guide.pdf']:
    path=root/'output'/name
    if path.exists():files.append(path)
manifest={'files':[{'path':str(p.relative_to(root)).replace('\\','/'),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in sorted(set(files))],
          'excludes':['.env','data/','.venv/','.git/','tmp/'],
          'live_acceptance':'Real public-data workflows completed for MeetUniversity, Buffer and Allbirds. See docs/ASSIGNMENT_AUDIT.md for counts, partial results and remaining submission gaps.',
          'demo_video':'A genuine 5-10 minute end-to-end screen recording is still missing. The old screenshot tour is excluded.',
          'tests':'Full suite: 50 passed. Final PDF export/API regressions: 2 passed. See output/assignment-audit/.'}
target=root/'output'/'Signal_Stack_Submission.zip'
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for p in sorted(set(files)):archive.write(p,p.relative_to(root))
    archive.writestr('MANIFEST.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(target) as archive:
    assert archive.testzip() is None
    assert '.env' not in archive.namelist()
print(str(target),f'({target.stat().st_size:,} bytes, {len(files)} files)')
