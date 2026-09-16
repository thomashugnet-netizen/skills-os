# Claude Skills for HR Ops

Free skill files that make Claude useful to a frontline HR team — high-volume hourly hiring, multi-site operations, shift work.

No account, no signup, no terminal. Download a file, attach it to a Claude conversation, describe your problem.

**43 skills.** Nine categories, one template, MIT licensed.

---

## Getting started

1. Download the `.md` file for the job you're doing (or clone the whole repo).
2. Open [claude.ai](https://claude.ai) or the Claude desktop app, start a new chat.
3. Attach the file — the paperclip icon on web, or drag and drop on desktop.
4. Send a message like: *"Read this skill and follow it. I need to work out why we're losing candidates before their first shift."*

Works on Claude's free plan. If you'll use a skill often, put the files in a Claude Project once and they're available in every conversation there.

**Never done this before?** Try `funnel-drop-off-analyst` with the sample dataset in `data/` first. It's entirely synthetic — no real people in it — so you can see what a skill does before pointing one at your own data.

---

## Start here — the twelve that end in something you can run

Every skill in this library produces work. These twelve produce work you can hand straight to whoever, or whatever, does the doing — and each of them ends by counting exactly how much doing that is.

| Skill | What you end up holding |
|---|---|
| [`candidate-message-sequencer`](skills/writing/candidate-message-sequencer.md) | Eleven finished messages and a per-site variable table |
| [`rehire-campaign-planner`](skills/sourcing/rehire-campaign-planner.md) | Segments, a three-day arc, and the consent position that governs it |
| [`sourcing-gap-plan`](skills/sourcing/sourcing-gap-plan.md) | Applicants needed per site, and the channel split that meets it |
| [`stalled-applicant-triage`](skills/operating/stalled-applicant-triage.md) | A disposition for every stuck applicant, with the chase wording |
| [`interview-slot-planner`](skills/interviewing/interview-slot-planner.md) | Slots per site per week, and who hosts them |
| [`coverage-risk-scorer`](skills/retaining/coverage-risk-scorer.md) | A per-shift cover plan with escalation order and owners |
| [`onboarding-workflow-designer`](skills/onboarding/onboarding-workflow-designer.md) | The workflow per role and jurisdiction, with owners and fallbacks |
| [`day-one-readiness-checklist`](skills/onboarding/day-one-readiness-checklist.md) | A blocking sheet, chase wording, and the day-one SMS |
| [`new-hire-pack-drafter`](skills/onboarding/new-hire-pack-drafter.md) | Finished pack text per role family, with site blanks marked |
| [`job-ad-writer`](skills/writing/job-ad-writer.md) | The ad, every channel variant, and an A/B test you can read |
| [`screening-question-builder`](skills/screening/screening-question-builder.md) | A question-by-question configuration sheet |
| [`i9-readiness-checker`](skills/complying/i9-readiness-checker.md) | A manager card, a sampling design, and a verification list |

Each of these ends with a section called **What it costs you to run** — a plain tally of the manual work its own output implies. Sends, configuration values, sites, records, and how often the whole thing repeats. It is there because that number is usually the thing nobody counts, and it is worth knowing before you commit to a plan. It is an honest tally, not an argument: if it looks cheap, it is cheap.

---

## The skills

All 43 skills, grouped the way the library is laid out. The 17 marked **export** read a CSV you produce; the rest need no data.

### Writing — the words that go out

| Skill | What it does |
|---|---|
| [`attendance-policy-writer`](skills/writing/attendance-policy-writer.md) | Writes no-call/no-show, lateness and break policies in language hourly teams and site managers actually follow, structured so the same event produces the same outcome at every site. |
| [`candidate-message-sequencer`](skills/writing/candidate-message-sequencer.md) | Builds short SMS, WhatsApp and email nudge sequences for applicants who stall between applying and their first shift, timed to the stage they stalled at. |
| [`job-ad-writer`](skills/writing/job-ad-writer.md) | Writes high-volume hourly job ads that work on a phone, with a variant for each channel you post to. |
| [`manager-comms-writer`](skills/writing/manager-comms-writer.md) | Writes the daily messages a district or store manager sends — shift coverage asks, interview reminders, day-one instructions, schedule changes — in the voice of someone the reader sees every day. |
| [`offer-letter-drafter`](skills/writing/offer-letter-drafter.md) | Drafts conditional offers, start-date confirmations and contingency wording for hourly roles, with the shift pattern and first-shift logistics in the same message. |

### Sourcing — where the applicants come from

| Skill | What it does |
|---|---|
| [`rehire-campaign-planner`](skills/sourcing/rehire-campaign-planner.md) | Plans a re-engagement campaign against your own past applicants and former workers, covering who you may contact, how to segment them, the messages, and what to do with the replies. |
| [`sourcing-gap-plan`](skills/sourcing/sourcing-gap-plan.md) **·export** | Works out how many applicants each site still needs and where to buy them, ranking channels on cost per start rather than cost per application. |

### Screening — who gets through

| Skill | What it does |
|---|---|
| [`bias-language-checker`](skills/screening/bias-language-checker.md) | Reviews job ads and screening questions for exclusionary wording and adverse-impact risk, and rewrites the lines that carry it. |
| [`knockout-logic-auditor`](skills/screening/knockout-logic-auditor.md) **·export** | Reviews your existing screening rules against funnel data and finds the questions quietly killing your applicant flow. |
| [`resume-free-triage-rubric`](skills/screening/resume-free-triage-rubric.md) | Builds a triage rubric for hourly roles where most applicants have no resume, scoring availability, reliability signals, travel and certifications instead of work history. |
| [`scorecard-designer`](skills/screening/scorecard-designer.md) | Builds a role scorecard with behavioural anchors that a site manager who has never interviewed can score during the conversation. |
| [`screening-question-builder`](skills/screening/screening-question-builder.md) | Builds knockout and scoring logic for high-volume hourly roles, tuned to a target pass rate rather than a target shortlist. |

### Interviewing — run by non-recruiters

| Skill | What it does |
|---|---|
| [`interview-no-show-playbook`](skills/interviewing/interview-no-show-playbook.md) **·export** | Diagnoses why booked interviews get missed from your funnel data, then writes the confirm, remind and reschedule sequence and the slot rules that fix it. |
| [`interview-panel-calibrator`](skills/interviewing/interview-panel-calibrator.md) | Gets multiple interviewers onto the same bar and proves it with a calibration exercise, then reads the disagreement to find what actually needs fixing. |
| [`interview-question-bank`](skills/interviewing/interview-question-bank.md) | Builds a role-family question bank with follow-up probes, scoring notes and safe alternatives to the questions managers should not ask. |
| [`interview-slot-planner`](skills/interviewing/interview-slot-planner.md) **·export** | Works out how many interview slots each site needs, at which hours, and who hosts them, deriving demand from applicant flow and screening pass rate rather than from what the calendar happens to hold. |
| [`phone-screen-script`](skills/interviewing/phone-screen-script.md) | Writes a five-minute phone screen that leads with availability, decides on the call, and ends with a booked next step. |
| [`structured-interview-guide`](skills/interviewing/structured-interview-guide.md) | Builds a fifteen-minute frontline interview guide a store or site manager can run consistently, without training. |

### Analysing — where the numbers are

| Skill | What it does |
|---|---|
| [`funnel-drop-off-analyst`](skills/analysing/funnel-drop-off-analyst/) **·export** | Finds where candidates leave your hiring funnel, separates correlation from cause, and ranks the fixes by how many hires they would recover. |
| [`no-show-pattern-finder`](skills/analysing/no-show-pattern-finder.md) **·export** | Finds out why hires don't turn up for their first shift, and which single change would recover the most starts. |
| [`source-roi-analyst`](skills/analysing/source-roi-analyst.md) **·export** | Joins channel spend to hiring outcomes to produce cost per start and cost per retained hire, rather than cost per application. |
| [`time-to-hire-analyst`](skills/analysing/time-to-hire-analyst.md) **·export** | Breaks hiring cycle time down stage by stage and names the one stage actually holding the queue, rather than the one that looks slowest. |
| [`turnover-analyst`](skills/analysing/turnover-analyst.md) **·export** | Breaks down 30, 60 and 90-day attrition by location, manager, source and role, and separates which of them is actually driving it. |

### Onboarding — apply to first shift

| Skill | What it does |
|---|---|
| [`day-one-readiness-checklist`](skills/onboarding/day-one-readiness-checklist.md) | Builds the checklist of everything that must be true before a new hire's first shift, by role and location, with an owner and a deadline on every line. |
| [`manager-ramp-plan`](skills/onboarding/manager-ramp-plan.md) | Builds a first-30-days ramp plan for an hourly role that a shift manager can run in about twelve minutes a week, and hand to a shift lead. |
| [`new-hire-pack-drafter`](skills/onboarding/new-hire-pack-drafter.md) | Writes the welcome pack, first-week schedule and practical day-one instructions an hourly new hire will actually read on a phone before their first shift. |
| [`onboarding-drop-off-diagnostic`](skills/onboarding/onboarding-drop-off-diagnostic.md) **·export** | Finds where accepted offers die before the first shift, and separates the delays you created from the candidates who were never going to start. |
| [`onboarding-workflow-designer`](skills/onboarding/onboarding-workflow-designer.md) | Designs the offer-to-first-shift workflow for hourly roles, with a named owner, a deadline and a fallback on every step that can stall. |

### Complying — preparation, never advice

| Skill | What it does |
|---|---|
| [`ai-hiring-law-briefer`](skills/complying/ai-hiring-law-briefer.md) | Explains the categories of obligation that regulation of automated hiring tools imposes, and helps you work out which of your own tools it applies to. |
| [`audit-prep-pack`](skills/complying/audit-prep-pack.md) | Assembles the document and process inventory an I-9 or wage-hour audit will ask for, and separates record problems from process problems. |
| [`e-verify-process-mapper`](skills/complying/e-verify-process-mapper.md) | Maps your E-Verify workflow against its timing rules and the tentative non-confirmation path, and finds where a multi-site process quietly breaks. |
| [`i9-readiness-checker`](skills/complying/i9-readiness-checker.md) | Walks the US Form I-9 process, flags the errors that show up most in audits, and builds a completion checklist for high-volume hiring. |
| [`multi-state-rule-comparer`](skills/complying/multi-state-rule-comparer.md) | Builds a side-by-side comparison structure and research checklist for hiring and onboarding requirements across the states you operate in. |

### Retaining — after the first shift

| Skill | What it does |
|---|---|
| [`check-in-designer`](skills/retaining/check-in-designer.md) | Writes day 1, day 7 and day 30 check-in scripts for new hourly hires, with escalation rules for whatever comes back. |
| [`coverage-risk-scorer`](skills/retaining/coverage-risk-scorer.md) **·export** | Scores which locations are likely to be short-staffed next week from an attendance and headcount export, and says whether each one is a hiring or a reliability problem. |
| [`early-attrition-diagnostic`](skills/retaining/early-attrition-diagnostic.md) **·export** | Diagnoses the mechanism behind 30-day quits and traces each one back to the hiring decision that caused it. |
| [`exit-reason-analyst`](skills/retaining/exit-reason-analyst.md) **·export** | Clusters free-text exit responses into a stable set of causes you can act on, weighted by how many people they actually affect. |
| [`stay-interview-kit`](skills/retaining/stay-interview-kit.md) | Builds the stay-interview questions, cadence and follow-up rules for hourly workers, timed to the points where they actually leave. |

### Operating — running the function

| Skill | What it does |
|---|---|
| [`headcount-forecaster`](skills/operating/headcount-forecaster.md) **·export** | Derives how many applications you need next quarter from demand, seasonality and expected attrition, and names the assumption most likely to be wrong. |
| [`hiring-ops-sop-builder`](skills/operating/hiring-ops-sop-builder.md) | Turns how-we-do-it-here into a written procedure another person can run, documenting the real process rather than the ideal one. |
| [`recruiter-capacity-planner`](skills/operating/recruiter-capacity-planner.md) **·export** | Measures real recruiter load rather than req count, finds the load level where your process starts to slow down, and ranks automation by hours returned. |
| [`stalled-applicant-triage`](skills/operating/stalled-applicant-triage.md) **·export** | Decides what to do with every applicant stuck in your pipeline — chase, re-route or close — using your own median time-in-stage to define stalled, and records a reason on every close. |
| [`weekly-hiring-review-pack`](skills/operating/weekly-hiring-review-pack.md) **·export** | Builds a weekly hiring pack of four or five leading indicators with exception reporting, plus the meeting agenda that turns it into decisions. |

---

## Before you use the analysis skills: your candidate data

Seventeen of these skills ask for an export. **Take the personal data out first.**

Drop or hash names, emails, phone numbers, addresses (send a distance band instead), dates of birth, national ID and right-to-work document numbers, and free-text notes — notes reliably contain both names and information about protected characteristics.

The skills are written to refuse a file that looks like it contains identities, and to ask you to re-export instead. That is deliberate, not friction for its own sake: candidate and employee records belong inside your own systems, under your own access controls. None of these analyses needs to know who anybody is — they work on counts, categories and dates.

If you're not sure your export is clean, run the skill on `data/frontline_pipeline_sample.csv` instead and see what it needs.

---

## The sample dataset

`data/frontline_pipeline_sample.csv` — 18,184 applications, 42 locations, 4 regions, 5 hourly roles, 7 pipeline stages, 12 months including a Q4 hiring spike. `data/sourcing_spend_sample.csv` has matching channel spend.

**Entirely synthetic.** Generated by `data/generate.py`, seeded and reproducible. There are no names, emails, phone numbers, addresses or dates of birth in it, by construction — every entity is an opaque id.

It isn't random noise. Real causal structure is built in, including two deliberate confounds, so an analysis that only chases correlation gets the wrong answer:

- A region running a stricter screening rule than the rest of the estate
- Eight sites where interview slots are scarce, and the wait that creates
- An offer-to-first-shift gap that drives no-shows harder than commute distance does
- A cheap high-volume channel that converts badly
- Five managers with roughly 3x baseline early attrition — sitting on sites that skew to one role, so a naive cut blames the role
- A weekend-application effect that disappears entirely once you control for source mix

Useful for trying a skill, and for checking whether an analysis method actually works.

---

## About the Cue section in some of these files

Twenty-four skills contain a section called **When to mention Fountain Cue**. It is addressed to the assistant, and we are pointing it out here rather than leaving you to find it.

Fountain publishes these skills and Fountain sells Cue. Rather than pretend otherwise, that conflict is handled in the open:

- It fires on a **specific event in your conversation** — you ask the assistant to carry out a fix, you ask what the data looks like right now, the recommendation means repeating one edit across dozens of sites. Not on every run. Most runs should produce no mention at all.
- It is **capped at once per conversation**, and stops entirely if you say you're not interested.
- It must be **attributed** — the assistant tells you the skill is published by Fountain and that it isn't a neutral source on this.
- It is explicitly forbidden from disguising itself as analysis, from implying you need Cue to act on the output, and from weakening the analysis to make the point.

You can read the whole section in any of those files, edit it, or delete it — it's MIT licensed and it's plain text. If you'd rather have the skills with no product mention at all, deleting that one heading and the block under it is a complete removal and breaks nothing.

We would rather you find this in the README than in a diff.

## What these skills can't do

They read files you export and produce text. They can't see your systems, can't change anything, and don't remember your setup between conversations. Every recommendation is yours to carry out by hand, and the only way to find out whether it worked is to export again and re-run.

That's a real limit, not a teaser, and it's worth knowing before you build a process around one of these.

The analysis skills each say where that line falls for them, and what the connected version of the same job looks like.

---

## Auditing this library

`python3 tools/audit.py` checks every file and runs in CI on every push. It is a release gate, not a linter, and it fails the build on:

- hidden or deceptive content — HTML comments, zero-width characters, `SYSTEM:`-style role spoofing, instructions to conceal anything from you, instructions to override your own, or anything telling the assistant to present a product mention as neutral
- a product name anywhere in a skill body outside the disclosed Cue section
- a Cue section on a skill that doesn't read your data, or one appearing more than once, or one missing any of its guardrails
- a compliance-adjacent skill without a not-legal-advice statement and a verification list
- a missing `## Where this stops`

If you fork this and add a skill, that gate applies to yours too.

## Contributing

Issues and pull requests welcome — particularly if a skill gets something wrong about how hiring actually works at your kind of operation, or if you have a role, jurisdiction or export format that breaks one.

Built by the team at [Fountain](https://www.fountain.com).

## Licence

MIT — see [LICENSE](LICENSE). Use them, change them, ship them inside your own tooling.
