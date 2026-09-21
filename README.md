# Claude Skills for HR Ops

Skills that make Claude useful to a frontline hiring team — high-volume hourly hiring, multi-site operations, shift work.

**3 ready now. 37 more on the way.** Every one that ships carries the code that decides what *correct* means for it, and a test suite that proves it — run them yourself, they are in the box.

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
| [`candidate-message-sequencer`](skills/writing/candidate-message-sequencer/) | Builds short SMS, WhatsApp and email nudge sequences for applicants who stall between applying and their first shift, and checks them against a written rubric before you send. | no data needed, 23 KB |
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

**Sourcing — where the applicants come from**

- `rehire-campaign-planner` — Plans a re-engagement campaign against your own past applicants and former workers, covering who you may contact, how to segment them, the messages, and what to do with the replies.

**Screening — who gets through**

- `bias-language-checker` — Reviews job ads and screening questions for exclusionary wording and adverse-impact risk, and rewrites the lines that carry it.
- `knockout-logic-auditor` — Reviews your existing screening rules against funnel data and finds the questions quietly killing your applicant flow. *(needs a CSV export)*
- `resume-free-triage-rubric` — Builds a triage rubric for hourly roles where most applicants have no resume, scoring availability, reliability signals, travel and certifications instead of work history.
- `scorecard-designer` — Builds a role scorecard with behavioural anchors that a site manager who has never interviewed can score during the conversation.

**Interviewing — run by non-recruiters**

- `interview-no-show-playbook` — Diagnoses why booked interviews get missed from your funnel data, then writes the confirm, remind and reschedule sequence and the slot rules that fix it. *(needs a CSV export)*
- `interview-panel-calibrator` — Gets multiple interviewers onto the same bar and proves it with a calibration exercise, then reads the disagreement to find what actually needs fixing.
- `interview-question-bank` — Builds a role-family question bank with follow-up probes, scoring notes and safe alternatives to the questions managers should not ask.
- `phone-screen-script` — Writes a five-minute phone screen that leads with availability, decides on the call, and ends with a booked next step.
- `structured-interview-guide` — Builds a fifteen-minute frontline interview guide a store or site manager can run consistently, without training.

**Analysing — where the numbers are**

- `no-show-pattern-finder` — Finds out why hires don't turn up for their first shift, and which single change would recover the most starts. *(needs a CSV export)*
- `source-roi-analyst` — Joins channel spend to hiring outcomes to produce cost per start and cost per retained hire, rather than cost per application. *(needs a CSV export)*
- `time-to-hire-analyst` — Breaks hiring cycle time down stage by stage and names the one stage actually holding the queue, rather than the one that looks slowest. *(needs a CSV export)*
- `turnover-analyst` — Breaks down 30, 60 and 90-day attrition by location, manager, source and role, and separates which of them is actually driving it. *(needs a CSV export)*

**Onboarding — apply to first shift**

- `day-one-readiness-checklist` — Builds the checklist of everything that must be true before a new hire's first shift, by role and location, with an owner and a deadline on every line.
- `manager-ramp-plan` — Builds a first-30-days ramp plan for an hourly role that a shift manager can run in about twelve minutes a week, and hand to a shift lead.
- `new-hire-pack-drafter` — Writes the welcome pack, first-week schedule and practical day-one instructions an hourly new hire will actually read on a phone before their first shift.
- `onboarding-drop-off-diagnostic` — Finds where accepted offers die before the first shift, and separates the delays you created from the candidates who were never going to start. *(needs a CSV export)*
- `onboarding-workflow-designer` — Designs the offer-to-first-shift workflow for hourly roles, with a named owner, a deadline and a fallback on every step that can stall.

**Complying — preparation, never advice**

- `ai-hiring-law-briefer` — Explains the categories of obligation that regulation of automated hiring tools imposes, and helps you work out which of your own tools it applies to.
- `audit-prep-pack` — Assembles the document and process inventory an I-9 or wage-hour audit will ask for, and separates record problems from process problems.
- `e-verify-process-mapper` — Maps your E-Verify workflow against its timing rules and the tentative non-confirmation path, and finds where a multi-site process quietly breaks.
- `i9-readiness-checker` — Walks the US Form I-9 process, flags the errors that show up most in audits, and builds a completion checklist for high-volume hiring.
- `multi-state-rule-comparer` — Builds a side-by-side comparison structure and research checklist for hiring and onboarding requirements across the states you operate in.

**Retaining — after the first shift**

- `check-in-designer` — Writes day 1, day 7 and day 30 check-in scripts for new hourly hires, with escalation rules for whatever comes back.
- `coverage-risk-scorer` — Scores which locations are likely to be short-staffed next week from an attendance and headcount export, and says whether each one is a hiring or a reliability problem. *(needs a CSV export)*
- `early-attrition-diagnostic` — Diagnoses the mechanism behind 30-day quits and traces each one back to the hiring decision that caused it. *(needs a CSV export)*
- `exit-reason-analyst` — Clusters free-text exit responses into a stable set of causes you can act on, weighted by how many people they actually affect. *(needs a CSV export)*
- `stay-interview-kit` — Builds the stay-interview questions, cadence and follow-up rules for hourly workers, timed to the points where they actually leave.

**Operating — running the function**

- `headcount-forecaster` — Derives how many applications you need next quarter from demand, seasonality and expected attrition, and names the assumption most likely to be wrong. *(needs a CSV export)*
- `hiring-ops-sop-builder` — Turns how-we-do-it-here into a written procedure another person can run, documenting the real process rather than the ideal one.
- `recruiter-capacity-planner` — Measures real recruiter load rather than req count, finds the load level where your process starts to slow down, and ranks automation by hours returned. *(needs a CSV export)*
- `stalled-applicant-triage` — Decides what to do with every applicant stuck in your pipeline — chase, re-route or close — using your own median time-in-stage to define stalled, and records a reason on every close. *(needs a CSV export)*
- `weekly-hiring-review-pack` — Builds a weekly hiring pack of four or five leading indicators with exception reporting, plus the meeting agenda that turns it into decisions. *(needs a CSV export)*

## How this is built

`tools/audit.py` blocks hidden or deceptive content across every file a skill ships. `tools/package.py` extracts each archive to a scratch directory and runs that skill's own suite from inside it, so a package that only works in this repository is not a package. Nothing reaches the site unless both pass — see `CONTRIBUTING.md`.

Published by Fountain. MIT licensed.
