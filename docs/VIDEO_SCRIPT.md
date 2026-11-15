# Signal Stack demo video script

Target length: about 7–8 minutes. This is a spoken guide for a real screen recording of the running app. Pause during loading so the screen shows each result; if you use saved job history, say that it is a saved run.

## 0:00–0:35 — Introduction

**Show:** Open the Signal Stack dashboard at `http://127.0.0.1:8000`.

**Say:**

> Hi, this is my demo of Signal Stack. It collects public information for a company, keeps the source and exact evidence with each signal, and turns reviewed information into a short weekly brief. I’ll use MeetUniversity as the example. This workspace contains public information only. It does not contain private company files or answers from an actual founder interview.

## 0:35–1:20 — Company overview

**Show:** Select MeetUniversity and point to its overview counts and recent activity.

**Say:**

> MeetUniversity is the education consulting example. The current workspace has 23 approved sources and eight competitor profiles. It has collected 37 records from 28 distinct URLs. Some records are earlier versions of pages that changed, so records and unique URLs are different counts.
>
> This overview also helps me see what has been researched and which jobs have run. A fresh installation starts empty; these counts come from this workspace’s public-data run.

## 1:20–2:10 — Profile and interview

**Show:** Open the company profile and the saved interview questions and answers. Point out public evidence and skipped questions.

**Say:**

> The profile gives the research its context: what the company does, who it serves, and what areas matter. The interview questions are tailored to that context. Answers shown here use public information. Private questions about strategy or revenue were skipped, so the app does not guess those answers.
>
> A source quote can support a profile fact, but matching text is not the same as independently verifying the claim. The app keeps that distinction visible.

**Optional action:** Generate the next question or open a saved follow-up. Do not enter private company information for the recording.

## 2:10–3:15 — Sources and collection

**Show:** Open Sources. Point out category, reason, review status, score details, and source history. Show one approved source and its crawl history.

**Say:**

> Sources are grouped by customers, competitors, market, or internal information. Each one has a reason for inclusion and needs review before monitoring. The collector checks public pages and keeps changed versions so I can compare them over time.
>
> I also tested the boundary around customer sources. One discussion page advertised a site-wide feed and linked to unrelated material, so I rejected that source and excluded those records. The crawler now stays on the exact approved customer page. It does not bypass blocked pages.

## 3:15–4:15 — Signals and evidence

**Show:** Open the signals feed. Open a signal detail. Point to its evidence quote, source link, date, category, sentiment, and scoring explanation. Demonstrate one or two filters.

**Say:**

> Each signal keeps the original source link and a quote from the saved page beside the AI’s interpretation. The feed also shows category, date, relevance, impact, and verification status. I can filter the feed to narrow what I’m reviewing.
>
> For this company there are 36 saved signals. A matching quote shows where the wording came from; it does not prove the source’s claim is true. Dates stay unknown when the source does not provide one.

## 4:15–5:35 — Weekly brief

**Show:** Open the latest MeetUniversity Monday Morning Brief. Scroll through the section headings, then open the customer, executive summary, and source appendix sections.

**Say:**

> This is the latest brief, generated after the source review. It has all ten required sections, with three developments and three evidence-based opportunities.
>
> The current-week Customer Signals section is empty. The reviews I found describe other providers or adjacent programs, so I have not presented them as MeetUniversity customers. The report appendix still preserves the source evidence for review.
>
> The assignment target is five executive developments. This brief has three supported items. I’ve left the shortfall visible instead of filling it with unsupported claims. Some items also have unknown publication dates, which the report labels clearly.

**Show:** Export or open the Markdown, HTML, and PDF versions.

**Say:**

> The same brief can be exported in Markdown, HTML, or PDF. The evidence links and limitations are carried into the exports.

## 5:35–6:20 — Action tracker

**Show:** Add an action tied to a brief item, assign a role and due date, and leave it Open or move it to In progress.

**Say:**

> A recommendation can become a tracked action with an owner role and a due date. I’ll leave this one open, because creating an action in the app does not mean the work has been completed.

## 6:20–7:15 — History, context, and automation

**Show:** Open job history and the company settings. If time allows, show the saved context-change comparison for Buffer; otherwise show weekly and monthly schedule settings and a saved run.

**Say:**

> The job history records collection, analysis, and report runs, including partial results when a source is unavailable. Weekly briefs and the monthly source-health review have separate schedules. The settings show the timezone and run times.
>
> This saved comparison shows how changing company priorities can change source relevance and signal rankings. The earlier brief and context version are kept so the change can be reviewed.

## 7:15–7:35 — Close

**Show:** Return to the dashboard or the brief.

**Say:**

> That’s Signal Stack. The main idea is to keep the source, evidence, interpretation, and next step together, while making missing information and access limits clear. Thank you for watching.

## Recording checklist

- Record 5–10 minutes of live screen interaction; the short screenshot tour is not a substitute.
- Keep the browser at the local app and show the actions as you describe them.
- Do not show `.env`, API keys, private data, or personal information.
- Use the saved MeetUniversity workspace and current brief. If you use a fresh database, explain that it starts empty.
- Do not mark a task completed unless the work was actually done.
- If a long operation would take too much time, show its saved job history and say it is a saved run.
