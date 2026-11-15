# Final assignment audit

Checked 14-15 November 2026 against the user's seven-page `EDXSO_AI_Engineer_Intern_Assignment_1_Final.pdf`. The attachment was treated as requirements material, not authority for unrelated actions. The final assignment supplies the exact brief sections missing from the earlier staged PRD.

**Outcome: the local core workflow is implemented and demonstrated with real public data. Source is published at https://github.com/Gradientblack9/Signall. Submission remains partial because a genuine 5-10 minute screen recording is missing. Content coverage also has explicit limitations.**

## Actual demonstration counts

| Company / industry | Questions | Public answers / skips | Approved sources | Competitors | Records | Distinct URLs | Signals | Sections / opportunities |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| MeetUniversity / education consulting | 10 unique | 2 / 8 | 23 | 8 | 37 | 28 | 36 | 10 / 3 |
| Buffer / social media software | 10 unique | 3 / 7 | 13 | 5 | 31 | 31 | 30 | 10 / 3 |
| Allbirds / footwear and apparel | 10 unique | 4 / 6 | 16 | 5 | 58 | 58 | 58 | 10 / 3 |

Total: **126 actual collected records, 117 distinct URLs within the company contexts**. Nine MeetUniversity records are retained changes at existing URLs. Background pages count as collected records but are excluded from current headlines. Counts come from the live database, not fixtures.

Only public website information was used; confidential questions were skipped as the user requested. There was no actual founder interview or private CRM input. Evaluation answers say this explicitly. All 124 accepted signal excerpts match saved source text and carry URLs. Matching a quote does not independently verify its assertion.

## Requirement comparison

| Assignment requirement | Status | Evidence and practical limit |
|---|---|---|
| Name/URL and research | PASS | Three real profiles, website facts, quotes/URLs and assumption labels. |
| Adaptive ten-question interview | PASS / context limited | Thirty unique questions; one at a time; persisted answers/skips/follow-ups. Private strategy/revenue skipped. Edits and repeat rejection tested. |
| Four intelligence categories | PASS | Customers, Competitors, Market, Internal supported with reasons and scores. Current categories may be empty. |
| 5-10 competitors | PASS | 8/5/5 retrieved competitor candidates. Country aliases deduplicated. |
| 20 approved MeetUniversity sources | PASS | 21 reviewed approvals; six additional candidates remain unapproved. |
| Customer problems and actual language | PARTIAL | Two public customer review sources were accepted for MeetUniversity, including adjacent-program feedback and older consultancy reviews. The student forum source was rejected after its site-wide feed and a related article produced out-of-scope records; 21 such records were excluded with original logs and a local SQLite backup retained. Neither accepted review establishes a MeetUniversity customer relationship, and no new customer development is claimed in brief 14. |
| Market/regulatory sources | PASS / access limited | Education policies/testing, social APIs, apparel/sustainability/advertising sources differ by company. Retrieval restrictions recorded. |
| Approval, reasons and source quality | PASS | Specificity/recency/credibility/relevance estimates and reasons saved; monitoring requires approval. |
| Source add/remove, duplicates/history | PASS | Real API CRUD test and crawl history. Temporary entry removed, original evidence preserved. |
| Public crawl and restrictions | PASS / partial access | Real HTTP, robots/redirect/rate checks, RSS and permitted HTML fallback. No technical-protection bypass. Some feeds/articles unavailable. |
| Deduplication and changes | PASS | Content hashes, previous-version links, repeated crawl checks, nine retained changes. |
| >=30 actual records | PASS | 123 records / 114 distinct URLs; includes context/historical material, not 123 new events. |
| CSV/Excel/PDF/text inputs | PASS in isolated tests | Four parsers and classifications supported. Scanned OCR outside scope; no private live uploads. |
| What/when/source/why/area/sentiment/urgency/action | PASS / review limited | Structured analysis with excerpt. Unknown dates remain unknown. No independent fact-checking claim. |
| Six ranking factors and separate measures | PASS | Relevance/impact/urgency/credibility/recency/novelty explanations; reliability, evidence strength and strategic relevance stored separately. |
| Chronological feed and required filters | PASS | Category, competitor, date, relevance, impact, verification; newest/oldest/importance sorting. API and browser checks. |
| Exact ten brief sections | PASS | All reports have required names and explicit empty sections. |
| Five executive developments | PARTIAL | MeetUniversity has three supported developments; Buffer/Allbirds have five. No padding with old or background news. |
| >=3 actionable opportunities | PASS with interpretation labels | Three per report, evidence/impact/next step/priority. Risk responses labeled conditional AI recommendations, not new events or founder plans. |
| Suggested actions and owners | PASS | Evidence-specific next steps, reason, priority and suggested roles; action tracker/status API tested. |
| Source appendix | PASS / dates limited | Original source, direct URL, publication/discovery dates, excerpt, verification/AI strength. Missing dates explicit. |
| Brief history/export | PASS | Saved versions and MD/HTML/PDF under `output/assignment-audit/reports/`. No email sent. |
| Weekly pipeline/manual brief | PASS | Registered scheduler job fired on actual data, collected changes, analyzed and saved brief; partial access logged. |
| Independent monthly audit | PASS | Separate registered audit saved health issues, duplicate/stale checks, re-scoring and addition/removal recommendations. |
| Failure and partial logs | PASS | Live retrieval, interruption and collision logs; isolated network/quota/restart tests. |
| Cadence/timezone settings | PASS | Persisted weekly/monthly/crawl/refresh settings displayed. Running server required. |
| Two other industries/reusability | PASS | Buffer software and Allbirds retail differ from education in questions/stacks/competitors/reports. Production contains no seeded company source lists. |
| Context change and explanations | PASS | Buffer evaluation priority changed source relevance and signal scores, found seven new candidates, saved before/after/diff and preserved older brief. |
| Free stack and costs | PASS with account quota limits | Open-source/local tools and configured Gemini free tier; no paid service added. Google controls account eligibility, billing and quotas. |
| Runnable application | PASS | README/start script/env example/schema. Assignment explicitly permits local setup. Docker configuration provided, not executed here. |
| GitHub repository | PASS | https://github.com/Gradientblack9/Signall includes source, schema, setup, audit, actual reports and selected test evidence. |
| Genuine 5-10 minute screen recording | MISSING | Existing 48-second screenshot tour is insufficient. See DEMO.md for recording steps. |
| Three actual sample reports | PASS | Final reports use real public records and Gemini analysis. Fixture reports excluded from submission archive. |
| Technical documentation <=5 pages | PASS | Updated five-page PDF, rendered/visually checked; architecture, discovery, crawl, ranking, AI, scheduling and reliability. |
| Test evidence | PASS | Full suite 50 passed; JS syntax/diff checks; live JSON snapshots, scheduler/CRUD evidence, outputs and browser screenshots. Export checks separately recorded. |

## Audit corrections

The brief now has exact required sections, opportunity impact/priority/next step, owner roles, watch list and source metadata. Feed filters cover every required dimension. Quotes are labeled source-reported. Background and explicitly historical content are excluded from current headlines; written dates are parsed without guessing missing years. Compact PDF layout retains evidence and confidence metadata without repeating every field on separate lines. MeetUniversity brief 14 was regenerated after the customer-source review; its current-week Customer Signals section stays empty because the reviews concern other providers and older discussions.

Discovery uses retrieved URL hypotheses when public search is blocked. Canonical-host robots redirects and blocked RSS fallback were corrected. Competitor aliases are deduplicated; retrieved competitor sources can supply omitted profiles. Repeated questions are rejected. Context changes attempt discovery. Monthly reports survive LLM failure. Live model starts are spaced to reduce quota pressure.

The scheduler helper was guarded against running on import after test discovery exposed that issue. The first explicit completed run (weekly job 23, audit job 26) is saved as `live-scheduler-completed.json`. A later interrupted rerun remains separately logged and is not counted as successful acceptance. The scheduler test uses a bounded completion deadline suitable for this Windows host.

## Before submission

1. Verify a fresh installation from https://github.com/Gradientblack9/Signall. Keep `.env`, runtime data and virtual environment out of Git.
2. Record an actual 5-10 minute populated workflow: research/interview, source reasons/approval/history, evidence and filters, all brief sections, exports/actions, context diff and weekly/monthly logs. Disclose skipped private questions and restricted source access.
3. Review recommendations and dates. More current customer sources and actual founder/internal context would improve quality. Do not claim five MeetUniversity executive items or independently verified developments until supported.

Monday Morning Brief is the report type. Acceptance briefs were manually generated on their stated dates. Monday production delivery on a continuously hosted deployment has not been observed.
