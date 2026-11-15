# Acceptance evidence

The final EDXSO assignment was checked on 14-15 November 2026. See [ASSIGNMENT_AUDIT.md](ASSIGNMENT_AUDIT.md) for the requirement matrix and remaining deliverables. Selected publishable evidence is included in [acceptance_evidence/](acceptance_evidence/README.md); full local run snapshots remain under ignored `output/assignment-audit/`.

## Completed verification

- Full isolated regression suite: 50 passed. One upstream Starlette/httpx deprecation warning remains. Results: `output/assignment-audit/final-tests.txt`.
- Real Gemini research, ten unique adaptive questions per company, discovery, reviewed approvals, public crawling, analysis and briefs: MeetUniversity, Buffer and Allbirds.
- 123 stored public records across 114 distinct URLs within the company contexts; changed content is retained as separate versions. Background records are included in collection counts and excluded from current brief headlines.
- MeetUniversity: 21 approved sources, eight discovered competitors, 34 records. Buffer: 13 approved sources, five competitors, 31 records. Allbirds: 16 approved sources, five competitors, 58 records.
- Every accepted signal has a matching excerpt in its saved document and an evidence URL. This proves traceability, not independent factual corroboration.
- Three briefs with the exact ten sections and three grounded opportunities each. MeetUniversity has three executive items rather than five, with the limitation stated. Empty current categories are explicit.
- Buffer context changes retained a profile diff and previous brief, changed source relevance and ranking, and added seven candidates. The new priority is labeled an evaluation setting.
- Explicit real scheduler run fired registered weekly and monthly jobs using short date triggers. A weekly brief and independent source-health report were saved. Restricted URLs produced partial statuses. Evidence: `live-scheduler-completed.json`.
- Source addition, duplicate detection, approval and removal passed through the real API using a temporary public article entry. Original sources/evidence retained. Evidence: `source-manager.json`.
- CSV, XLSX, text PDF and text ingestion, actions, isolation, retries, quote rejection, hash deduplication, history, monthly independence and failure logs are exercised by isolated fixture tests.

## Reproduce

Start as described in README. Keep the Gemini key in `.env` and use **Test connection**. Never put keys in command-line arguments or reports.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --check static/app.js
.\.venv\Scripts\python.exe scripts/assignment_live_test.py --stage snapshot --company-id 1
.\.venv\Scripts\python.exe scripts/export_live_audit.py
```

For another company, use `assignment_live_test.py --stage setup --name NAME --url URL`. This helper supplies labeled public answers and skips private questions, as authorized by the user. It is not founder interview attestation. Review sources before `--stage collect --approve-ids ... --analyze`.

`assignment_scheduler_test.py` is an explicit manual integration script, guarded against execution on import. Run only while MeetUniversity jobs are idle. It advances schedules in a separate evaluation process without changing saved cadence. The first completed run is retained separately from a later interrupted rerun. Production delivery requires an online server.

## Remaining submission gates

Local setup is documented and permitted by the assignment. Source is published at https://github.com/Gradientblack9/Signall. A genuine approximately 5-10 minute screen recording remains missing; the existing 48-second screenshot tour does not satisfy that requirement. No private founder answers or internal files were supplied. Source access, publication dates and independent verification remain limited by public evidence.
