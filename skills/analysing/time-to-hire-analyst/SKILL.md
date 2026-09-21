---
name: time-to-hire-analyst
description: Breaks hiring cycle time down stage by stage and names the one stage actually holding the queue, rather than the average.
version: 1.0.0
---

# Time to Hire Analyst

## What this does

Takes a pipeline export and tells you which stage is holding your queue, for whom, and whether it is slow always or only when volume arrives. It does not report a time to hire. A single number averages a stage that is slow for everybody by design with a stage that is slow at eight sites for a reason you could fix this week, and points at neither.

Three questions, kept apart because they have three different owners:

- **Where is the calendar going?** Which stage carries the largest share of total elapsed days — not the longest median, which can belong to a stage almost nobody reaches.
- **Is it slow for everyone, or for a minority?** A stage that is slow everywhere is the process. A stage that is slow at eight locations out of forty-two is those eight locations, and fixing it means a rota change, not a redesign.
- **Is it slow always, or under load?** A stage that stretches in peak months has enough capacity for a normal month and not for a peak. You staff it, and it recovers on its own. A stage that is long every month is how the process is built, and staffing will not touch it.

---

## Data lanes

I need your funnel in one shape: the canonical schema in `references/schema.json`. How it gets there is up to what you have connected.

**Lane A — a CSV export.** The default, and the one that needs nothing but a file. Any ATS: I map your column names onto the schema and tell you what I could not map. No account, no connection, no authentication.

**Lane B — a connected MCP** that can serve the same fields, so re-running after a change costs you nothing. **Works with**, below, lists what this library connects to today.

The analysis is identical either way. Only how the data arrives changes.

## What to give me

A row-per-application export covering at least one full month, at least 500 usable rows, with **a timestamp for each stage a candidate reached**. That last part is the whole job — this analysis is arithmetic on the gaps between those dates, and without them there is nothing to measure.

**Required**

| Column | Example |
|---|---|
| `application_id` | `APP-004182` |
| `stage_reached` | `interview_completed` |
| At least two stage timestamps | `applied_at`, `screened_at`, … |

**Strongly recommended** — each unlocks a class of finding:

| Column | What it lets me find |
|---|---|
| Every stage timestamp | The full clock. A missing one merges two waits into one and hides which of them is the problem |
| `location_id` | Whether a queue is systemic or lives in a handful of sites |
| `region` or `district` | Scheduling rules applied at group level |
| `source` | Whether one channel's candidates wait longer — and whether that explains a site effect |
| `role` | Whether one job's requirements are what is slow, not the site running it |

If you don't have some of these, say so. The engine reports every missing column and the finding it cost you. It will not fill a gap with an assumption.

**The export most systems give you by default is the wrong one.** Almost no ATS ships one row per application with a date column per stage. The timestamps exist as a status-history log — one row per status change — so getting to the shape above means a pivot, and the ask has to be explicit. Ask for status history with the change timestamp, not the pipeline report. Where the history keeps several entries for one stage, take the *first* arrival at each: the last one measures how long the record was edited, not how long the candidate waited.

**No export handy?** `frontline_pipeline_sample.csv` ships in `data/`. Three more — quick service, logistics, and a five-stage gig activation funnel with no interview and no offer — are on the library page you got this skill from. All four are synthetic and carry the same planted timing structure. I detect which funnel shape a file uses from its stage names; there is nothing to configure.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash names, email addresses, phone numbers, street addresses, dates of birth, document numbers, and free-text notes.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate records belong inside your own systems, under your own access controls, not in a chat window. Nothing in a cycle-time analysis needs to know who anybody is. The engine enforces this before it reads a single row.

## How I work

Everything below runs in `scripts/analyze.py` — standard library, no network, no model arithmetic. The same file always produces the same numbers.

### First, two checks that can stop the analysis

**Do the timestamps agree with the stage order?** If more than 2% of rows arrive at a stage before they left the previous one, the dates do not mean what the column names say — usually two columns crossed, or a history pivot that took the wrong entry. Every median below would be fiction, so I stop and say which pair is inconsistent.

**How many people are still waiting?** This is the trap the engine is built around. A median computed over people who finished waiting is a median over the lucky ones: everybody still stuck in the queue is, by construction, waiting longer than the figure being reported, and they are excluded *because* it is longer. So I count them, report the share and how long they have already waited, and flag any stage where enough are in flight to move the answer. Past 60%, I stop — a report on the fast ones is worse than no report. This is why an export that ends yesterday flatters you, and why the window should close a full cycle before today.

### Then five passes

1. **The clock.** Median, p75 and p90 wait at every stage, plus the share of total elapsed days each one carries. Ranked by days held, not by median: a four-day wait everybody sits through holds more calendar than a twenty-day wait forty people reach.
2. **Concentration.** For each stage, is the wait spread evenly or carried by a minority of locations, regions, sources or roles? Each segment is compared against the rest of the file rather than the overall median, which a large enough offender drags towards itself until it stops looking like one.
3. **Load.** Peak months are derived from your own volume, then every stage is measured inside and outside them. A stage has to be both proportionally and materially slower — a median moving from one day to two is a rounding boundary in a date-only export, not a capacity problem.
4. **Confounds.** Every concentrated delay is re-tested holding each other dimension constant. If eight slow sites are slow because they run one role and that role needs a licence check, it is reported as a role finding. What did not survive is listed under **Ruled out**, with the dimension that killed it named.
5. **Sizing.** What comes off the calendar if each confirmed problem is fixed, in days and in the number of people who wait them, using the confound-adjusted excess rather than the raw gap.

## What you get

A short report: the stage holding the most calendar time, the stage carrying a concentrated delay, and whether they are the same stage — they usually are not, and that gap is the point. Then the per-stage clock with its in-flight count, the confirmed findings sized in days, the load effects kept separate from the structural ones, and what was ruled out and why.

## What this does not claim

**It does not tell you a shorter wait means more hires.** Long waits and drop-off travel together, but how much of one converts into the other differs by stage and is not answerable from timestamps alone. That is a drop-off question, and a different analysis. Saying so is cheaper than being caught at it.

## Verifying this yourself

Run `python3 scripts/analyze.py --test`. The samples carry a known timing structure: one stage where a subset of sites has scarce scheduling capacity, and a peak period that lengthens a different stage. The suite asserts the site effect is found **at that stage and not at the others** — a weaker engine reports slow sites as slow everywhere — that it survives its confound checks, that the load effect lands on a different stage than the structural one, and that five managers planted with poor *retention* and no timing problem are never reported as slow. The same assertions run against all four samples, including the gig funnel on its different stage list, plus five refusal cases. What passes is the method, not a memory of one file.

## Works with

- **A CSV export from any ATS** — this is the default lane and needs nothing connected.
- **The Fountain Cue MCP** — when connected, it supplies the same fields directly, so re-running after a change costs you nothing. Fountain publishes this skill and sells Cue; the engine, the thresholds and the findings are identical either way, and the skill works completely without it.
- **The four synthetic samples** — retail, quick service, logistics and gig.

## Where this stops

In lane A this reads a file you exported, so it sees one moment and changes nothing. It cannot tell you your queue today, act on a single one of its own findings, or tell you whether a fix worked — you would export again and re-run to find out.

It cannot see *why* a stage is slow. It can tell you eight sites hold candidates six days longer at scheduling and that the effect survives every confound it could be tested against; it cannot tell you whether that is a rota problem, an unfilled vacancy, or a manager who never opens the queue. That part is yours.

And it measures waiting, not work. A stage where nothing happens for four days and a stage where four days of checks happen look identical in a timestamp. Which is which is something you know and the export does not.
