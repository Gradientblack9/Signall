# Signal Stack

A local company intelligence and executive briefing engine built from the supplied PRD. FastAPI, SQLite, APScheduler and a buildless eight-page dashboard. Gemini is the default LLM provider; Groq and Ollama are configurable alternatives. There are no hard-coded company sources, competitors or interview questions in the application.

The dashboard uses plain text for the Signal Stack name, standard fonts, and simple white and gray panels. It has no logo, promotional slogans, or decorative icons.

## Run on Windows

```powershell
git clone https://github.com/Gradientblack9/Signall.git
cd Signall
python -X utf8 -m venv .venv
.\.venv\Scripts\python.exe -X utf8 -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env locally: set GEMINI_API_KEY. Never commit this file.
.\.venv\Scripts\python.exe -X utf8 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Run these commands from the cloned repository root. Python 3.11+ and Git are required. The `-X utf8` option supports Windows folder names containing non-ASCII characters. Copy the environment example only during initial setup; retain your existing `.env` on later runs.

Open **http://127.0.0.1:8000**. A fresh clone starts with an empty database and no API key. The server creates `data/signal.db` on startup. Add your own company and key to run AI operations. For later Windows starts, use [start.ps1](start.ps1) with `.\start.ps1` from the repository root.

Committed sample reports are in [docs/sample_reports](docs/sample_reports/), and published test evidence is in [docs/acceptance_evidence](docs/acceptance_evidence/README.md). The local `output/` directory contains generated exports and full acceptance snapshots; it is ignored by Git and is not included in a fresh clone.

macOS/Linux, from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Set GEMINI_API_KEY in .env locally.
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

## The workflow

1. Add a company name and its public URL. In **Company profile**, run research. Each supported fact includes an exact excerpt and source URL; unsupported claims are assumptions. Summary, industry and classifications are AI interpretations.
2. Complete **Strategy interview**. Questions are generated one at a time from the profile and prior answers. Skip, request a follow-up, or edit an answer. Include a follow-up response in the original answer. After the interview, run **Reassess context**.
3. In **Signal stack**, discover sources. Review the reason and specificity/recency/credibility/relevance estimates. Approve candidates to enable monitoring. You can add sources manually, reject or remove them, inspect history, and see possible duplicate domains.
4. Crawl approved sources. RSS/Atom is preferred where published; otherwise collect readable HTML. Robots restrictions, failures and content changes are visible. There is no login, paywall or CAPTCHA bypass.
5. In **Intelligence feed**, import CSV, XLSX, text-based PDF, TXT or Markdown if needed, and run analysis. Every accepted signal must quote text from an actual collected record. Publication and discovery dates are separate. See the scoring explanation for each item.
6. Generate a **Monday brief**. Ten sections, explicit empty sections, evidence links and separate AI interpretation. Export Markdown, HTML or PDF. Create tracked actions from signals or brief items.
7. Configure timezone and cadence under **Automation & settings**. Run the weekly pipeline, refresh, context reassessment or monthly audit manually. View failures and partial results. Scheduled jobs run only while the server is running.

## Configuration

See [.env.example](.env.example). Keep keys on the server. Gemini free-tier eligibility and quotas depend on your Google account, region and selected model. This app does not create paid accounts or enable billing. It cannot enforce a provider's account-level billing policy; use a free-tier-only project and monitor your provider quota.

`GEMINI_MODEL` is configurable because model availability changes. **Test connection** verifies a real structured response. No key means AI operations report a configuration error; there is no fabricated fallback. For Ollama, set `LLM_PROVIDER=ollama`, `OLLAMA_MODEL`, and `OLLAMA_URL` after installing/pulling your model. No automatic provider failover silently changes where internal data goes.

`SIGNAL_DB` defaults to `data/signal.db`. `SIGNAL_SCHEDULER=false` disables scheduling. `SIGNAL_ACCESS_TOKEN` enables bearer-token access on all `/api` routes; enter it using the sidebar settings icon. Loopback binding is the default. Health is intentionally public and exposes configuration presence, never credentials.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check static/app.js
```

Tests isolate databases in temporary folders and inject explicitly synthetic web/LLM responses. They cover three company contexts, 20+ candidate sources, 5–10 competitor candidates, 30+ records, interviews, quote grounding, uploads, ranking, export, context diffs, failure isolation, authentication, and scheduler-triggered weekly pipeline execution. **Fixture counts are not live acceptance evidence.**

```powershell
.\.venv\Scripts\python.exe scripts/make_fixture_artifacts.py
```

This generates `output/fixtures/` locally with three clearly labeled synthetic briefs and a context diff, keeping production data untouched. Those files do not exist until the command is run. [scripts/live_acceptance.py](scripts/live_acceptance.py) drives the real API for a supplied company; source approval remains a separate review step. See [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md).

## Deployment

```powershell
docker compose up --build -d
```

Docker persists SQLite under `./data` and publishes only on localhost. For remote deployment, use a persistent disk, HTTPS reverse proxy, `SIGNAL_ACCESS_TOKEN`, and **one** Uvicorn worker/replica. The scheduler is in-process; free hosting that sleeps cannot guarantee Monday delivery. The included Vercel adapter disables scheduling and uses temporary storage, so it does not demonstrate the complete persistent monitoring workflow. Docker configuration is provided; image execution requires Docker on the host.

## Deliverables & Documentation Links

- **Repository**: [https://github.com/Gradientblack9/Signall](https://github.com/Gradientblack9/Signall)
- **Technical Documentation (5-Page PDF)**: [`docs/Signal_Stack_Technical_Guide.pdf`](docs/Signal_Stack_Technical_Guide.pdf) and [`docs/TECHNICAL.md`](docs/TECHNICAL.md)
- **Database Schema**: [`schema.sql`](schema.sql)
- **Three Sample Company Reports**:
  - MeetUniversity (Primary / EdTech): [Markdown](docs/sample_reports/MeetUniversity_Monday_Morning_Brief.md), [HTML](docs/sample_reports/MeetUniversity_Monday_Morning_Brief.html), [PDF](docs/sample_reports/MeetUniversity_Monday_Morning_Brief.pdf)
  - Buffer (SaaS / Social Media): [Markdown](docs/sample_reports/Buffer_Monday_Morning_Brief.md), [HTML](docs/sample_reports/Buffer_Monday_Morning_Brief.html), [PDF](docs/sample_reports/Buffer_Monday_Morning_Brief.pdf)
  - Allbirds (Direct-to-Consumer / Footwear): [Markdown](docs/sample_reports/Allbirds_Monday_Morning_Brief.md), [HTML](docs/sample_reports/Allbirds_Monday_Morning_Brief.html), [PDF](docs/sample_reports/Allbirds_Monday_Morning_Brief.pdf)
- **Cost Statement**: [`docs/COSTS.md`](docs/COSTS.md) (100% free / open-source tier disclosure)
- **Demo video**: [`docs/demo/Signal_Stack_Demo.mp4`](docs/demo/Signal_Stack_Demo.mp4) (Git LFS); see [`docs/DEMO.md`](docs/DEMO.md) and the [7–8 minute narration script](docs/VIDEO_SCRIPT.md). The supplied video is 11 minutes 50 seconds and should be trimmed to the assignment's 5–10 minute target.
- **Test Evidence & Acceptance**: [`docs/ASSIGNMENT_AUDIT.md`](docs/ASSIGNMENT_AUDIT.md), [`docs/acceptance_evidence/README.md`](docs/acceptance_evidence/README.md), [`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) and [`docs/PHASES.md`](docs/PHASES.md)

The published sample-report folder contains Markdown, HTML and PDF versions of all three real public-data reports. Acceptance completed with 50 tests passing, plus two final export regressions. The genuine 5-10 minute demo recording is still pending. `.env`, runtime databases and virtual environments are excluded from Git.

## Reading order

- `docs/Signal_Stack_Technical_Guide.pdf`: 5-page submission PDF covering architecture, source discovery, crawling, ranking, AI analysis, scheduling and reliability.
- `docs/PHASES.md`: implementation and acceptance status for stages 0–11.
- `docs/TECHNICAL.md`: architecture, model, grounding, reliability and operations.
- `docs/COSTS.md`: no-cost dependencies, quotas and resource limits.
- `docs/ACCEPTANCE.md`: live acceptance instructions and honest release gates.
- `docs/DEMO.md`: demo walkthrough and recording guidance.


The final EDXSO assignment specifies the ten report sections; `app/briefs.py` implements that exact structure. Ranking weights are explicit in `app/services.py`. Unsupported opportunity or headline counts remain visible shortfalls. See `docs/ASSIGNMENT_AUDIT.md` for the actual requirements comparison and remaining submission gaps.
