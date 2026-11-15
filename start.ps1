$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -X utf8 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& '.venv\Scripts\python.exe' -X utf8 -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. See the pip output above.' }
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
    Write-Host 'Created .env. Set GEMINI_API_KEY there to enable AI features.'
}
& '.venv\Scripts\python.exe' -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
