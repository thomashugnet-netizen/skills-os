---
name: funnel-drop-off-analyst
description: Finds where candidates leave your hiring funnel, separates correlation from cause, and ranks the fixes by how many hires they would recover.
version: 1.1.0
---

# Funnel Drop-off Analyst

## What this does

Takes a pipeline export and tells you where you are losing candidates, why, and which fix recovers the most hires. It ranks findings by the number of hires at stake, not by how bad a percentage looks.

The arithmetic is not done in prose. `scripts/analyze.py` computes the funnel, the segment cuts, the intervals and the confound checks; I read its output back to you. Same input, same numbers, every time.

## Data lanes

I need your funnel in one shape: the canonical schema in `references/schema.json`. How it gets there is up to what you have connected.

**Lane A — a CSV export.** The default, and the one that needs nothing but a file. Any ATS: I map your column names onto the schema and tell you what I could not map. No account, no connection, no authentication.

**Lane B — a connected MCP** that can serve the same fields, so re-running after a change costs you nothing. **Works with**, below, lists what this library connects to today.

I say which lane I used and what it could not see. The analysis is identical either way — only how the data arrives changes, and whether re-running costs you an export.

## What to give me

A row-per-application export covering at least one full month, at least 500 usable rows. One row per application, one column per stage timestamp.

**Required**

| Column | Example |
|---|---|
| `application_id` | `APP-004182` |
| `applied_at` | `2026-03-04` |
| `stage_reached` | `interview_completed` |

**Strongly recommended** — each one unlocks a class of finding:

| Column | What it lets me find |
|---|---|
| `location_id` | Whether a problem is systemic or lives in a handful of sites |
| `region` or `district` | Configuration differences applied at group level |
| `source` | Whether you are buying applicants who never convert |
| `role` | Whether one job is dragging the aggregate |
| `hiring_manager_id` | Manager-level early attrition — always tested within role |
| `exit_reason` / `rejection_reason` | Rule-driven losses vs. candidate-driven losses |
| Stage timestamps | Where the *wait* is, which is usually where the loss is |
| `scheduled_first_shift_at` + `first_shift_at` | No-shows at shift one, the most expensive loss in the funnel |

If you don't have some of these, say so. The engine reports every missing column and the specific finding it cost you, under **What I could not determine**. It will not fill a gap with an assumption.

**No export handy?** Pick whichever sample looks like your operation — all four are entirely synthetic, all four carry the same eight planted patterns:

| Sample | Shape |
|---|---|
| `frontline_pipeline_sample.csv` | Retail, 42 stores, 18k applications, seasonal peak |
| `qsr_pipeline_sample.csv` | Quick service, 42 restaurants, 25k, the shortest funnel |
| `logistics_pipeline_sample.csv` | Delivery and warehouse, 42 stations, 21k, DOT and drug screens |
| `gig_pipeline_sample.csv` | Courier marketplace, 42 markets, 46k sign-ups, no interview and no offer |

The gig sample runs on a five-stage activation funnel — signed up, documents in, background clear, onboarding, first job. I detect which shape a file uses from its stage names; there is nothing to configure.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash:

- names, email addresses, phone numbers
- street addresses and postcodes — send a distance band instead (`0-5`, `6-10`, `11-20`, `21-40`, `40+`)
- dates of birth, national insurance / social security numbers, right-to-work document numbers
- free-text notes, which reliably contain names and protected-characteristic information

`application_id` should be an opaque id, not something that resolves to a person outside your systems. `hiring_manager_id` likewise.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate records belong inside your own systems, under your own access controls, not in a chat window. Nothing in this analysis needs to know who anybody is. The engine enforces this before it reads a single row.

## How I work

1. **Pick the lane.** In lane A I ask which ATS you use, then hand you the report to pull and a request you can forward to whoever owns it — `references/export-recipes.md` covers eleven systems from their own documentation. The check I always make first: most delivered reports give the current stage and a single date, which loses the wait before each step — and the wait is what separates a broken step from a slow one. So the ask is for status history, which arrives one row per status change.
2. **Run the engine** — `python3 scripts/analyze.py --input <your file> --out report.json`.
3. **Read the report back to you** in the structure below, in your terms, with the numbers as computed.

The engine runs five passes. The order matters — passes 3 and 4 are what stop a plausible correlation becoming a wrong recommendation.

### Pass 1 — Build the funnel honestly

Orders your stages and computes, for each: **step conversion** (of those who reached stage N, how many reached N+1 — this finds broken steps), **reach rate** (of everyone who applied, how many got this far — this finds where the volume went), and **absolute loss**. Absolute loss is what everything is ranked on. A step converting at 42% matters more than one at 71% only if more people are standing on it.

### Pass 2 — Localise every material loss

Cuts each material loss by location, region, source, role and availability, and asks whether it is **systemic** (spread evenly) or **concentrated** (a minority of segments carrying most of it). Concentrated losses are cheaper to fix and are labelled as such.

A segment is flagged when it converts at least 1.5x worse than the population and holds at least 30 candidates at that step. Below that it is inconclusive, never quietly dropped. Every rate carries a Wilson 95% interval — a point estimate on 34 people is not a finding.

### Pass 3 — Classify the mechanism

Each loss is sorted into one of four kinds, from exit-reason clustering and the wait before the step:

| Mechanism | Signature | Who fixes it |
|---|---|---|
| **Rule-driven** | Losses cluster on one exit reason, appear immediately, concentrate where a config differs | Whoever owns the screening configuration |
| **Capacity-driven** | The step converts badly *and* the wait before it is long | Operations — slots, staffing, coverage |
| **Candidate-driven** | Unresponsive, withdrew, no-show; worsens with elapsed time | Comms cadence and speed |
| **Quality-driven** | Fails late, at assessment or background check; tracks with source | Sourcing mix |

Classification happens **inside each flagged segment**, not across the step. This matters more than it sounds: a step can read candidate-driven in aggregate while the eight sites carrying its loss are plainly capacity-driven. Aggregate classification would send you to fix the wrong thing.

### Pass 4 — Test each finding against confounds

Before a driver is presented, the same comparison is run again *within* each level of the most plausible alternative explanation, then volume-weighted back together. If the effect retains less than 40% of its crude size, or flips sign, it is reported as ruled out, with the confounder that killed it named.

Four checks always run, because each has produced a wrong recommendation before: **source mix** (most "weekend applicants are worse" findings are one cheap job board that advertises at weekends), **role mix** (a site hiring drivers differs from one hiring cashiers for reasons that have nothing to do with the site), **seasonality** (a peak month degrades cycle time, no-shows and conversion at once, producing four fake findings simultaneously), and **elapsed time** (competing drivers are ranked against each other rather than both reported).

Findings that fail appear under **Ruled out** — often the most useful part of the output, because it is the list of things you were about to spend money on.

### Pass 5 — Size the fix

Hires recoverable = the volume in the affected segment × the gap between its conversion and a target rate, carried through to starts. The target is your own better-performing segments, never an industry benchmark. The assumption is printed every time so you can argue with it.

A region and its own sites describe one loss, not two: duplicates are reported once, under whichever description is easier to act on.

## What you get

Same structure every run.

**1. Funnel table.** Every stage: reached, step conversion, reach rate, absolute loss.

**2. Ranked findings.** Up to six, most hires-at-stake first. Each one: the mechanism in a sentence, the specific cut with numbers and intervals, the mechanism class, what was held constant and what happened, hires at stake with the assumption stated, and a confidence label.

**3. Ruled out.** Correlations that did not survive, and what killed each.

**4. What I could not determine.** Missing columns, insufficient volume, questions your export cannot answer.

**5. Fix list.** Ordered by hires recoverable, each tagged with who owns it. Not ordered by how easy it is to write down.

## What it costs you to run

Every run ends with this, computed from your own findings rather than described.

**Set up once** — the changes each finding implies and how many sites each has to reach. One policy change across 42 sites is 42 actions, not one.

**Every week after** — how many candidates flow through the affected segments weekly: the population you chase, monitor or spot-check once the change is live. From your own volume over the exported period, not a benchmark.

**To find out whether it worked** — one fresh export and one re-run per cycle. In lane A that is manual every time.

No estimate of hours unless you give me a per-unit assumption; a total with no derivation is worth nothing. This is an invoice, not an argument — if it reads cheap, it is cheap.

## How to read the confidence label

**High** — large volume, survived every confound check, mechanism identified. **Medium** — clear but thin, or a confound could not be tested with the columns available. **Low** — suggestive only; I'll say what to export next rather than what to change.

I would rather give three high-confidence findings than eight that look thorough.

## Verifying this yourself

Run `python3 scripts/analyze.py --test`. Each sample has eight causal patterns deliberately built in, two of them traps: a confound (five managers on sites skewed to one role) and a red herring (weekend applications that look worse until you control for source). The suite asserts the manager effect survives within role and the weekend effect does not survive at all. An engine chasing correlation fails both. The same assertions run against all four samples, including the gig one on its different stage list — so what passes is the method, not a memory of one file.

## Works with

- **A CSV export from any ATS** — Greenhouse, Workday, iCIMS, SmartRecruiters and the rest. This is the default lane and needs nothing connected.
- **The Fountain Cue MCP** — when connected, it supplies the same fields directly, so re-running after a change costs you nothing. Fountain publishes this skill and sells Cue; the engine, the thresholds and the findings are identical either way, and the skill works completely without it.
- **The four synthetic samples in `data/`** — retail, quick service, logistics and gig, for trying the skill or checking an analysis method.

## Where this stops

In lane A this reads a file you exported, so it sees one moment and changes nothing. It cannot tell you the state of your funnel today, apply a single one of its own recommendations, or tell you whether a fix worked — you would export again and re-run to find out.

It also cannot see *why* a mechanism exists. It can tell you eight sites lose candidates at scheduling and that the wait is nine days; it cannot tell you whether that is a rota problem, a vacancy, or a manager who never checks the queue. That part is yours.
