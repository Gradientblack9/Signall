# Signal Stack

A local company intelligence and executive briefing engine built from the supplied PRD. FastAPI, SQLite, APScheduler and a buildless eight-page dashboard. Gemini is the default LLM provider; Groq and Ollama are configurable alternatives. There are no hard-coded company sources, competitors or interview questions in the application.

The dashboard uses plain text for the Signal Stack name, standard fonts, and simple white and gray panels. It has no logo, promotional slogans, or decorative icons.

## Run on Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env locally: set GEMINI_API_KEY. Never commit this file.
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Open **http://127.0.0.1:8000**. On this workspace the environment is already installed. `./start.ps1` starts it again and creates `.env` if absent. The current local preview has a MeetUniversity company entry, one approved first-party source, one successfully crawled real record, and no fabricated intelligence.

macOS/Linux: use `python3 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, `cp .env.example .env`, then `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1`.

## The workflow

1. Add a company name and its public URL. In **Company profile**, run research. Each supported fact includes an exact excerpt and source URL; unsupported claims are assumptions. Summary, industry and classifications are AI interpretations.
2. Complete **Strategy interview**. Questions are generated one at a time from the profile and prior answers. Skip, request a follow-up, or edit an answer. Include a follow-up response in the original answer. After the interview, run **Reassess context**.
3. In **Signal stack**, discover sources. Review the reason and specificity/recency/credibility/relevance estimates. Approve candidates to enable monitoring. You can add sources manually, reject or remove them, inspect history, and see possible duplicate domains.
4. Crawl approved sources. RSS/Atom is preferred where published; otherwise collect readable HTML. Robots restrictions, failures and content changes are visible. There is no login, paywall or CAPTCHA bypass.
5. In **Intelligence feed**, import CSV, XLSX, text-based PDF, TXT or Markdown if needed, and run analysis. Every accepted signal must quote text from an actual collected record. Publication and discovery dates are separate. See the scoring explanation for each item.
6. Generate a **Monday brief**. Ten sections, explicit empty sections, evidence links and separate AI interpretation. Export Markdown, HTML or PDF. Create tracked actions from signals or brief items.
7. Configure timezone and cadence under **Automation & settings**. Run the weekly pipeline, refresh, context reassessment or monthly audit manually. View failures and partial results. Scheduled jobs run only while the server is running.

## Configuration

See `.env.example`. Keep keys on the server. Gemini free-tier eligibility and quotas depend on your Google account, region and selected model. This app does not create paid accounts or enable billing. It cannot enforce a provider's account-level billing policy; use a free-tier-only project and monitor your provider quota.

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

This writes three clearly labeled fixture briefs and a context diff to `output/fixtures/`, keeping production data untouched. `scripts/live_acceptance.py` drives the real API for a supplied company; it does not approve sources automatically. See `docs/ACCEPTANCE.md`.

## Deployment

```powershell
docker compose up --build -d
```

Docker persists SQLite under `./data` and publishes only on localhost. For remote deployment, use a persistent disk, HTTPS reverse proxy, `SIGNAL_ACCESS_TOKEN`, and **one** Uvicorn worker/replica. The scheduler is in-process; free hosting that sleeps cannot guarantee Monday delivery. No remote deployment or GitHub push has been performed without an account/target. Docker configuration is provided; image execution requires Docker on the host.

## Reading order

- `docs/PHASES.md`: implementation and acceptance status for stages 0–11.
- `docs/TECHNICAL.md`: architecture, model, grounding, reliability and operations.
- `docs/COSTS.md`: no-cost dependencies, quotas and resource limits.
- `docs/ACCEPTANCE.md`: live acceptance instructions and honest release gates.
- `docs/DEMO.md`: demo walkthrough and recording guidance.

The PRD does not name its ten brief sections or score weights. The chosen defaults are explicit in `app/services.py` and the technical guide. The requirement for at least three opportunities is an evidence threshold: if fewer exist, the brief states the shortfall.
