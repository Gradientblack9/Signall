# Acceptance and test evidence

## Automated local verification

Run `python -m pytest -q` inside the project environment. Tests use explicitly synthetic `.example` domains and injected responses. Production imports do not reference `tests/fixtures.py`.

The three fixture contexts represent study-abroad services, clinic operations and freight logistics. Each discovers 24 distinct test sources and seven test competitor candidates. Approved fixture RSS feeds supply more than 30 records; the tests verify distinct briefs and a changed-priority relevance/score diff. **These are controlled test fixtures, not real MeetUniversity research or live PRD success metrics.**

The API integration tests traverse company creation, research jobs, interview answers/follow-ups, source discovery and approval, crawling, intake, analysis, brief generation/export, actions, schedules, failures, auth, and settings. The scheduler test fires the actual registered weekly job through APScheduler with a short date trigger; it does not wait a week or prove production uptime. The final full suite passed 35 tests. Two adjusted context/deletion regression tests were subsequently rerun and passed.

Browser QA confirmed all eight pages, source creation and approval, successful real crawling, and mobile navigation at a 390-pixel viewport without horizontal overflow. No browser console errors were observed. The MeetUniversity homepage yielded one real record in the live local database; this is partial crawler acceptance, not the required 30-record milestone.

See `output/test-results.txt` for the latest run and `output/fixtures/` for inspectable test artifacts when generated. Browser checks cover the local dashboard. Local `/health` returns 200 and reports scheduler/configuration state.

## Real-company run

1. Create a free-tier Gemini key in your own Google account, store it only in `.env`, restart and use **Test connection**. Choose a currently available free-tier model if your account does not offer the default.
2. Start with MeetUniversity and `https://www.meetuniversity.com/`. Run research and inspect each fact's quote/URL. The website was located via public search; its claims still require application-level research and review.
3. Answer the ten interview questions; confirm they adapt to prior answers. Reassess context. Discover sources, inspect relevance and approve at least 20 appropriate sources. Review 5–10 competitor candidates against their official pages. If free search is blocked, record that limitation and add real sources manually; that does not establish the unseen-company automatic discovery criterion.
4. Crawl and inspect at least 30 real records and original links. Import approved internal test notes if available. Analyze and verify zero accepted signals lack evidence URLs and matching excerpts.
5. Generate a brief; inspect all ten sections, explicit empty sections and opportunity coverage. If fewer than three opportunities are supported, record the shortfall. Export all three formats.
6. Repeat for two unrelated real companies. Edit context and reassess; inspect source and signal changes and saved diffs. Preserve earlier briefs as historical versions.
7. Trigger the weekly pipeline manually, then leave the application running until a scheduled run fires. Confirm both log entries and briefs. Run a monthly audit manually and inspect dead URLs, duplication/inactivity/relevance and new candidates.

`scripts/live_acceptance.py` checks the running API and outputs an evidence report. It can create a company and run research/discovery, but approval remains a human review action in the dashboard. Keys are never supplied as command-line arguments. Read its `--help` before use.

## Remaining external gates

A live Gemini key, working external search/crawl access, and a continuously running host are needed for live acceptance. Publishing also needs a deployment target and repository account. No GitHub URL, hosted deployment URL, populated live demo, or real-source acceptance result should be claimed until those steps actually complete.
