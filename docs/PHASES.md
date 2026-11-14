# Phased delivery

Statuses distinguish implementation from demonstrated live acceptance. No synthetic fixture result is counted as live company research.

| PRD stage | Implemented | Validation / remaining acceptance |
|---|---|---|
| 0 Setup | FastAPI, SQLite schema, Gemini/Groq/Ollama JSON client, retry, cache, health | Health verified locally; structured-response integration tested with injected transport. Live Gemini call requires a local key. |
| 1 Company + Research | Public-page research; profile; excerpt-matched facts vs assumptions | Automated grounding test passes; live research awaits Gemini key. |
| 2 Interview | Ten dynamic questions; one at a time; persistence; skip; edit; optional follow-up | Two distinct fixture companies receive different questions; follow-up responses can be added to the original answer. |
| 3 Source Discovery | Generated queries; free search; real-candidate URL allowlist; scores/reasons; approval | 24 fixture sources and 7 competitor candidates tested; 20+ live MeetUniversity approvals and 5–10 live competitors remain unverified. |
| 4 Crawler | robots.txt; spacing; RSS/Atom preference; hash deduplication; version links; failure history | 30+ synthetic records, blocked source isolation and change detection tested; one real MeetUniversity page crawled successfully through the dashboard. 30+ real records remain a live release gate. |
| 5 Internal Intake | CSV/XLSX/text PDF/TXT/MD; traceable internal record URLs; AI classification | Four file formats tested; documents are stored before analysis; scanned PDF OCR is outside scope. |
| 6 Analysis + Ranking | Evidence quote matching; separate interpretation; six-factor score; separate reliability, strength and relevance | Invented quotes rejected; missing dates handled conservatively; contextual re-analysis tested. |
| 7 Monday Brief | Ten sections; explicit empty sections; opportunity shortfall; history; MD/HTML/PDF | Three distinct fixture briefs and export tests; live three-company briefs await configuration. |
| 8 Automation | Weekly pipeline; monthly audit; crawl/refresh; timezone; logs; manual jobs | Four schedules registered; weekly job fired through APScheduler with a short test trigger. Production Monday delivery needs a running deployment. |
| 9 Dashboard | Eight responsive pages; filters; source history/health; action board; intake; cadence | Browser and API workflow verification recorded in acceptance evidence. |
| 10 Stress Test | Context versions; diff; source re-scoring; stale flags; re-analysis | Three synthetic company flows and changed-priority score differences tested. Three unseen real-company runs remain a live release gate. |
| 11 Deliver | Source, local setup, Docker, five-page technical PDF, cost statement, tests, fixture artifacts, captioned UI tour | Local package supplied. Live hosting, GitHub remote and a populated live demo require a key and deployment/account destination. |

## Release gates

- Configure a Gemini free-tier-only project key locally and verify a real JSON response.
- Run real research, interview and discovery for MeetUniversity, then review and approve at least 20 relevant sources and 5–10 competitor candidates.
- Store at least 30 real evidence records, produce a live brief, repeat for two other companies, and inspect a changed-context diff.
- Keep the process running through a scheduled weekly run; inspect its logs and resulting brief.
- Choose a deployment host and GitHub repository; publish using your own accounts. Record the populated live workflow after these gates pass.
