# Claude Skills for HR Ops

Skills that make Claude useful to a frontline hiring team — high-volume hourly hiring, multi-site operations, shift work.

**18 ready now. 24 more on the way.** Every one that ships carries the code that decides what *correct* means for it, and a test suite that proves it — run them yourself, they are in the box.

## Installing one

1. Download the .zip - do not unzip it.
2. In Claude, open Settings, then Customize, then Skills.
3. Press + and upload the .zip.
4. Start a new conversation and describe your problem. Claude picks the skill up on its own.

*An installed skill never updates itself. Re-upload the zip to move to a newer version.*

## Ready now

| Skill | What it does | |
|---|---|---|
| [`funnel-drop-off-analyst`](skills/analysing/funnel-drop-off-analyst/) | Finds where candidates leave your hiring funnel, separates correlation from cause, and ranks the fixes by how many hires they would recover. | needs a CSV export, 0.3 MB |
| [`source-roi-analyst`](skills/analysing/source-roi-analyst/) | Joins channel spend to hiring outcomes and prices every source per start and per hire still there at 30 days, not per application. Reconciles the two files first, prices screening time if you give it, checks the ranking is not just role, site or season mix, and proposes a bounded budget move with a check date and a stop rule. | needs a CSV export, 0.3 MB |
| [`time-to-hire-analyst`](skills/analysing/time-to-hire-analyst/) | Breaks hiring cycle time down stage by stage and names the stage actually holding the queue, keeping apart the stage slow for everybody, the one slow at a few sites, and the one slow only in peak months. | needs a CSV export, 0.3 MB |
| [`document-expiry-radar`](skills/complying/document-expiry-radar/) | Reads a list of the licences, cards and certificates your people need to work, with their expiry dates, and shows who cannot work today, whose renewal has to start now to avoid a lapse, and which scheduled shifts that puts at risk. | no data needed, 43 KB |
| [`multi-state-rule-comparer`](skills/complying/multi-state-rule-comparer/) | Compares the hiring and onboarding rules of every state and city you operate in, from a list of your sites and headcounts, and shows which rules apply at your size, the strictest rule if you run one process, what changes in the next 18 months and what to research first. | no data needed, 55 KB |
| [`interview-panel-calibrator`](skills/interviewing/interview-panel-calibrator/) | Gets several interviewers onto the same bar. Builds a twenty-minute calibration exercise from your own anchors, then reads the scores to say whether each disagreement comes from the anchor wording or from a person, and which person is lenient, severe or not separating strong answers from weak ones. | no data needed, 27 KB |
| [`phone-screen-script`](skills/interviewing/phone-screen-script/) | Writes and checks a five-minute phone screen for an hourly role, with availability asked first and shift by shift against the real rota gaps, three gates that decide on the call, and a booked interview before hanging up, plus the voicemail, text and attempt rule; then reads the call log for what a better script cannot fix. | no data needed, 62 KB |
| [`structured-interview-guide`](skills/interviewing/structured-interview-guide/) | Builds a fifteen-minute frontline interview a store or site manager can run the same way every time, without training, and checks the questions managers ask today for the ones that are a legal risk or predict nothing. | no data needed, 39 KB |
| [`onboarding-workflow-designer`](skills/onboarding/onboarding-workflow-designer/) | Designs the offer-to-first-shift onboarding workflow for hourly roles as a short, checkable document, with one owner, a deadline and a fallback on every step that can stall, a timeline by category and owner, and the federal US filing deadlines checked in code. | no data needed, 61 KB |
| [`recruiter-capacity-planner`](skills/operating/recruiter-capacity-planner/) | Measures what each recruiter actually carries week by week, finds the load at which screening starts to slow down, tells a capacity problem from a process, upstream or individual one, and ranks automation by hours a month returned, so a headcount request rests on the number that survives. | needs a CSV export, 0.4 MB |
| [`schedule-photo-to-roster`](skills/operating/schedule-photo-to-roster/) | Turns a photo or screenshot of a shift schedule into a clean roster, then shows where the week is short-staffed, who is heading into overtime, who closes and opens with too little rest, and which hours could move. | no data needed, 0.2 MB |
| [`check-in-designer`](skills/retaining/check-in-designer/) | Writes the day 1, day 7 and day 30 check-ins that catch a new hourly hire before they quit, each under three minutes, with every possible answer routed to an action, an escalation or a logged theme, and checks the plan in code before anyone runs it. Then reads the one-line log supervisors keep to show which sites are not running them and which answers nobody acted on. | no data needed, 27 KB |
| [`bias-language-checker`](skills/screening/bias-language-checker/) | Checks every text a candidate reads (job ads, application questions, text and email templates, offer letters, interview scripts, careers pages) for wording that excludes people you would hire or asks what you may not ask, and reads a whole template library at once to rank the fixes by how many candidates each line reaches. | no data needed, 30 KB |
| [`career-site-builder`](skills/sourcing/career-site-builder/) | Redesigns a careers page for an hourly, multi-site employer as a polished, on-brand landing page with job search, from a single request such as "redo our careers page", and checks it for search, AI visibility, accessibility and honesty before handover. | no data needed, 79 KB |
| [`pay-competitiveness-checker`](skills/sourcing/pay-competitiveness-checker/) | Places every posted hourly rate on the local wage ladder for the same job, from official US government wage data, and shows which postings pay less than most employers in that metro, what it would cost to fix, and where your own sites pay differently for the same job. | no data needed, 0.4 MB |
| [`rehire-campaign-planner`](skills/sourcing/rehire-campaign-planner/) | Turns your own past applicants and former workers into a re-engagement campaign. Settles who you may contact first, sorts every record into a segment or a named reason it is out, sizes waves to the replies someone can actually answer, and checks the three messages before they go. | needs a CSV export, 0.3 MB |
| [`candidate-message-sequencer`](skills/writing/candidate-message-sequencer/) | Builds short SMS, WhatsApp and email nudge sequences for applicants who stall between applying and their first shift, grades the whole sequence against a written rubric before you send, and reads the send log for which message earns its place and whether the stop condition actually works. | no data needed, 80 KB |
| [`job-ad-writer`](skills/writing/job-ad-writer/) | Writes high-volume hourly job ads that work on a phone, with a variant for each channel you post to. | no data needed, 16 KB |

## Sample datasets

Nobody should hand real candidate data to a tool they have not watched work. Every sample is synthetic, carries no personal data of any kind, and has real causal structure buried in it — including two traps for anything that mistakes correlation for cause.

| Dataset | Rows | Shape |
|---|---|---|
| [`frontline`](data/frontline_pipeline_sample.csv) | 18,184 | Retail & multi-site — 42 stores, a seasonal peak, heavy job-board reliance. |
| [`qsr`](data/qsr_pipeline_sample.csv) | 24,642 | Quick service restaurants — 42 restaurants, the shortest funnel - apply to first shift in days. |
| [`logistics`](data/logistics_pipeline_sample.csv) | 21,473 | Logistics & delivery — 42 stations, drug screens and DOT medicals before day one. |
| [`gig`](data/gig_pipeline_sample.csv) | 46,219 | Delivery & courier (gig) — 42 markets, no interview and no offer - activation, not hiring. |

## Coming soon

Written, not yet through their gate. They ship when they pass it.

**Writing — the words that go out**

- `attendance-policy-writer` — Writes no-call/no-show, lateness and break policies in language hourly teams and site managers actually follow, structured so the same event produces the same outcome at every site.
- `manager-comms-writer` — Writes the daily messages a district or store manager sends — shift coverage asks, interview reminders, day-one instructions, schedule changes — in the voice of someone the reader sees every day.
- `offer-letter-drafter` — Drafts conditional offers, start-date confirmations and contingency wording for hourly roles, with the shift pattern and first-shift logistics in the same message.

**Screening — who gets through**

- `knockout-logic-auditor` — Reviews your existing screening rules against funnel data and finds the questions quietly killing your applicant flow. *(needs a CSV export)*
- `resume-free-triage-rubric` — Builds a triage rubric for hourly roles where most applicants have no resume, scoring availability, reliability signals, travel and certifications instead of work history.

**Interviewing — run by non-recruiters**

- `interview-no-show-playbook` — Diagnoses why booked interviews get missed from your funnel data, then writes the confirm, remind and reschedule sequence and the slot rules that fix it. *(needs a CSV export)*

**Analysing — where the numbers are**

- `no-show-pattern-finder` — Finds out why hires don't turn up for their first shift, and which single change would recover the most starts. *(needs a CSV export)*
- `turnover-analyst` — Breaks down 30, 60 and 90-day attrition by location, manager, source and role, and separates which of them is actually driving it. *(needs a CSV export)*

**Onboarding — apply to first shift**

- `day-one-readiness-checklist` — Builds the checklist of everything that must be true before a new hire's first shift, by role and location, with an owner and a deadline on every line.
- `manager-ramp-plan` — Builds a first-30-days ramp plan for an hourly role that a shift manager can run in about twelve minutes a week, and hand to a shift lead.
- `new-hire-pack-drafter` — Writes the welcome pack, first-week schedule and practical day-one instructions an hourly new hire will actually read on a phone before their first shift.
- `onboarding-drop-off-diagnostic` — Finds where accepted offers die before the first shift, and separates the delays you created from the candidates who were never going to start. *(needs a CSV export)*

**Complying — preparation, never advice**

- `ai-hiring-law-briefer` — Explains the categories of obligation that regulation of automated hiring tools imposes, and helps you work out which of your own tools it applies to.
- `audit-prep-pack` — Assembles the document and process inventory an I-9 or wage-hour audit will ask for, and separates record problems from process problems.
- `e-verify-process-mapper` — Maps your E-Verify workflow against its timing rules and the tentative non-confirmation path, and finds where a multi-site process quietly breaks.
- `i9-readiness-checker` — Walks the US Form I-9 process, flags the errors that show up most in audits, and builds a completion checklist for high-volume hiring.

**Retaining — after the first shift**

- `coverage-risk-scorer` — Scores which locations are likely to be short-staffed next week from an attendance and headcount export, and says whether each one is a hiring or a reliability problem. *(needs a CSV export)*
- `early-attrition-diagnostic` — Diagnoses the mechanism behind 30-day quits and traces each one back to the hiring decision that caused it. *(needs a CSV export)*
- `exit-reason-analyst` — Clusters free-text exit responses into a stable set of causes you can act on, weighted by how many people they actually affect. *(needs a CSV export)*
- `stay-interview-kit` — Builds the stay-interview questions, cadence and follow-up rules for hourly workers, timed to the points where they actually leave.

**Operating — running the function**

- `headcount-forecaster` — Derives how many applications you need next quarter from demand, seasonality and expected attrition, and names the assumption most likely to be wrong. *(needs a CSV export)*
- `hiring-ops-sop-builder` — Turns how-we-do-it-here into a written procedure another person can run, documenting the real process rather than the ideal one.
- `stalled-applicant-triage` — Decides what to do with every applicant stuck in your pipeline — chase, re-route or close — using your own median time-in-stage to define stalled, and records a reason on every close. *(needs a CSV export)*
- `weekly-hiring-review-pack` — Builds a weekly hiring pack of four or five leading indicators with exception reporting, plus the meeting agenda that turns it into decisions. *(needs a CSV export)*

## How this is built

`tools/audit.py` blocks hidden or deceptive content across every file a skill ships. `tools/package.py` extracts each archive to a scratch directory and runs that skill's own suite from inside it, so a package that only works in this repository is not a package. Nothing reaches the site unless both pass — see `CONTRIBUTING.md`.

Published by Fountain. MIT licensed.
