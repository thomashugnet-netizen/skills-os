---
name: turnover-analyst
description: Breaks down 30, 60 and 90-day attrition by location, manager, source and role, and separates whether you have a hiring problem or a job problem.
version: 1.0.0
---

# Turnover Analyst

## What this does

Takes a pipeline export and tells you whether your early attrition is a **hiring and first-month problem** or a **job problem** — because those have different owners, different fixes, and a single turnover percentage reports neither.

The method is to look for segment structure in each tenure band separately, then ask whether the structure found early persists later.

- If certain managers, sites or sources lose far more people in the first thirty days, and the gap **disappears** afterwards, the people who were going to leave have already left. What you are looking at is selection, expectation-setting and the first week.
- If the same segments keep losing people who already survived a month, that is the **job** — pay, schedule, supervision. No amount of better hiring touches it.

Those two conclusions send you to different rooms. Averaged into one number, neither is visible.

---

## Data lanes

I need your workforce in one shape: the canonical schema in `references/schema.json`.

**Lane A — a CSV export.** The default, and the one that needs nothing but a file. Any ATS or HRIS: I map your column names onto the schema and tell you what I could not map.

**Lane B — a connected MCP** serving the same fields, so re-running after a change costs you nothing. **Works with**, below, lists what this library connects to today.

## What to give me

One row per hire, at least 200 people who actually started, and a window that **ends at least a quarter before today**.

**Required**

| Column | Example | Why |
|---|---|---|
| `application_id` | `APP-004182` | |
| `stage_reached` | `started` | Identifies who actually became a hire |
| `first_shift_at` | `2026-03-04` | The clock starts here, and it decides who has had time to leave |
| `tenure_days` | `17` | How long they stayed. Blank means still employed |

**Strongly recommended** — each unlocks a class of finding:

| Column | What it lets me find |
|---|---|
| `hiring_manager_id` | The single most common carrier of early attrition — always tested within role |
| `location_id` | Whether it is a handful of sites or the whole estate |
| `source` | Whether you are buying people who leave |
| `role` | Whether one job is dragging the average, or just looks like it |
| `separation_reason` | Tested, and usually reported as *not* explaining anything — see below |

**On `tenure_days`.** If your system gives you a separation date instead, send `separation_at` alongside `first_shift_at` and compute the difference before exporting. If `tenure_days` is only populated for people who left in their first month, say so — I will detect it as a band with no events and tell you rather than reporting 0%.

**No export handy?** `frontline_pipeline_sample.csv` ships in `data/`. Three more — quick service, logistics, and a five-stage gig activation funnel — are on the library page you got this skill from.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Drop or hash names, emails, phone numbers, addresses, dates of birth, document numbers and free-text notes.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: this analysis names managers and sites as carrying attrition, which is exactly the kind of output that must never sit next to a list of who left. The engine enforces this before it reads a single row.

## How I work

Everything below runs in `scripts/analyze.py` — standard library, no network, no model arithmetic. The same file always produces the same numbers.

### The two corrections that make band rates mean anything

**Only count people who had time to leave.** Someone hired three weeks before your export closed cannot be recorded as a 90-day leaver. Counting them in the denominator is not conservative — it is wrong in the flattering direction, by exactly as much as you have been hiring lately. Each band gets its own eligible cohort, and I report how many people that excluded and how much the uncorrected figure understated.

**Each band is a conditional rate.** Someone who left on day 20 was never going to leave between days 31 and 90. Leaving them in the denominator makes every band depend on the band before it, so a segment with terrible first-month attrition gets an artificially *good* 31-90 figure. Of the people who reached the start of a band, how many left during it — that is the only version of the number that can be compared across segments.

### Then six passes

1. **The bands.** 1-30, 31-90, 91+ — each over its own at-risk cohort, with a confidence interval and the naive figure beside it.
2. **Structure.** Which managers, sites, sources or roles carry more than their share, in each band.
3. **Screening.** Forty managers across four dimensions and three bands is over two hundred comparisons, and at the usual 5% threshold that produces around ten findings in a file containing nothing. Findings are screened with a false-discovery-rate procedure across the whole band at once, and must also clear a materiality floor — significant-but-tiny wastes your week.
4. **Confounds.** Every surviving finding is re-tested holding each other dimension constant. Managers and roles are entangled in most frontline operations — one manager runs the site that hires most of one job — so the manager set is tested within role and the role within the manager group. Whatever did not survive is reported under **Ruled out**, with the dimension that killed it named.
5. **The band contrast.** The pass the skill exists for: does the early gap persist? This is what produces the hiring-problem / job-problem verdict.
6. **Sizing.** People, not percentages, using the confound-adjusted excess.

### Exit reasons get a permutation test, and usually fail it

If you have `separation_reason`, I test whether your flagged segments leave for a measurably different mix of reasons. Almost always they do not — and the naive comparison will not tell you that, because with five categories and a few hundred leavers, two random halves of the same population routinely differ by ten points on some category. So the labels are reshuffled a few thousand times and the observed difference is placed against what chance produces.

When the answer is no, I say so plainly: **your exit reasons will not identify which segment is the problem, and a programme built on the reason mix would be built on noise.** That is a finding, not a gap.

### One column, two names

In most frontline operations one manager runs one site, so `hiring_manager_id` and `location_id` cut the data identically. Reported separately that is the same finding printed twice, which reads as corroboration. I detect it and report it once, naming both columns.

## What you get

The verdict and what it rests on: the three band rates with their cohorts, the confirmed segments sized in people, the band contrast that produced the verdict, the exit-reason test, and what was ruled out and why.

## Verifying this yourself

Run `python3 scripts/analyze.py --test`. The samples carry a known structure: five managers with roughly three times baseline first-month attrition, sitting on sites that skew to one role — so a naive cut blames the job. The suite asserts the manager effect survives within role, that the role effect **loses far more of itself to the manager than the manager loses to the role**, that no weak manager reappears in the 31-90 band, and that eight sites planted with a *scheduling* problem and no attrition problem are never reported as a turnover finding. The same assertions run against all four samples, including the gig funnel on its different stage list, plus five refusal cases.

## Works with

- **A CSV export from any ATS or HRIS** — the default lane, nothing connected.
- **The Fountain Cue MCP** — when connected, it supplies the same fields directly. Fountain publishes this skill and sells Cue; the engine, the thresholds and the findings are identical either way, and the skill works completely without it.
- **The four synthetic samples** — retail, quick service, logistics and gig.

## Where this stops

It reads a file you exported, so it sees one moment and changes nothing. It cannot tell you who is about to leave, and it is not a prediction — every number here is about people who have already gone.

It cannot see *why* a manager loses people. It can tell you five managers lose a quarter more of their hires in the first month and that this survives every confound it could be tested against; it cannot tell you whether that is rostering, training, a site that is genuinely harder, or one person. That part is yours, and the analysis is the beginning of that conversation rather than its conclusion.

It errs toward missing a real problem rather than inventing one. The screening is deliberately conservative, so a small segment with a genuine issue can fail to clear it. A segment you believe is a problem and that does not appear here has not been cleared — it has not been proven, which is a different thing.
