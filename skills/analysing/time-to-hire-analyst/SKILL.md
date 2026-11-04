---
name: time-to-hire-analyst
description: Breaks hiring cycle time down stage by stage and names the stage actually holding the queue, keeping apart the stage slow for everybody, the one slow at a few sites, and the one slow only in peak months.
version: 1.0.0
---

# Time to Hire Analyst

Created with Kathleen Rakusin.

## What this does

Takes a pipeline export and tells you which stage is holding your queue, for whom, and whether it is slow always or only when volume arrives. It does not report a time to hire. A single number averages a stage that is slow for everybody by design with a stage that is slow at eight sites for a reason you could fix this week, and points at neither.

Three questions, kept apart because they have three different owners:

- **Where is the calendar going?** Which stage carries the largest share of total elapsed days — not the longest median, which can belong to a stage almost nobody reaches.
- **Is it slow for everyone, or for a minority?** A stage that is slow everywhere is the process. A stage that is slow at eight locations out of forty-two is those eight locations, and fixing it means a rota change, not a redesign.
- **Is it slow always, or under load?** A stage that stretches in peak months lacks capacity for a peak: you staff it, and it recovers. A stage that is long every month is how the process is built, and staffing will not touch it.

---

## Data lanes

I need your funnel in one shape: the canonical schema in `references/schema.json`. **Lane A** is a CSV export from any ATS: I map your column names onto the schema and tell you what I could not map. **Lane B** is a connected MCP serving the same fields (see **Works with**). The analysis is identical either way.

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
| Every stage timestamp | The full clock. A missing one leaves the two waits on either side of it unmeasured |
| `exit_reason` | Tells a candidate who left from one still open. Without it, the two are counted together and the report says so |
| `location_id` | Whether a queue is systemic or lives in a handful of sites |
| `region` or `district` | Scheduling rules applied at group level |
| `source` | Whether one channel's candidates wait longer — and whether that explains a site effect |
| `role` | Whether one job's requirements are what is slow, not the site running it |

If you don't have some of these, say so. The engine reports every missing column and the finding it cost you. It will not fill a gap with an assumption.

**The default export is usually the wrong one.** Few ATSs ship one row per application with a date per stage; the dates live in a status-history log, one row per status change. Ask for that log with its timestamps and pivot it. Where a stage appears several times, take the *first* arrival: the last one measures how long the record was edited.

**No export handy?** `frontline_pipeline_sample.csv` ships in `data/` (synthetic, with a planted timing structure); three more, including a five-stage gig activation funnel, are on the library page. I detect the funnel shape from the stage names.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash names, email addresses, phone numbers, street addresses, dates of birth, document numbers, and free-text notes.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate records belong inside your own systems, under your own access controls, not in a chat window. Nothing in a cycle-time analysis needs to know who anybody is. The engine enforces this before it reads a single row.

## How I work

Everything below runs in `scripts/analyze.py` — standard library, no network, no model arithmetic. The same file always produces the same numbers.

```bash
python3 scripts/analyze.py --input export.csv --as-of 2026-11-04 --md report.md --out report.json
python3 scripts/analyze.py --demo      # the bundled retail sample
```

Pass `--as-of` as the day the export was pulled; without it, the latest date in the file stands in. Exit codes: 0 report written, 3 input refused (the reason is printed), 4 the engine itself failed. I map your columns onto the schema first, then run it, then explain the report — I do not recompute anything it computed.

### First, the checks that can stop the analysis

**Is it one row per application, with dates I can read?** A raw status-history log repeats each application once per status change; I stop and ask for the pivot rather than count people several times. Dates must be ISO, or slash dates whose order the file itself proves (a 31/01 somewhere). A file where every slash date could be read either way, or where more than 1% of a date column is not a date (spreadsheet serial numbers, text), is refused: guessing moves dates by months without an error.

**Do the timestamps agree with the stage order?** If more than 2% of rows arrive at a stage before they left the previous one, the dates do not mean what the column names say — usually two columns crossed, or a history pivot that took the wrong entry. Every median below would be fiction, so I stop and say which pair is inconsistent.

**Who is actually still waiting?** This is the trap the engine is built around, and it runs both ways. Count everyone without the next date as waiting, and the candidates rejected or withdrawn months ago swell a queue that does not exist. Ignore the ones still open, and the median flatters you: an export that ends yesterday has only timed the fast ones among its last arrivals. So everyone who reached a stage is sorted once: moved on, left (closed with an exit reason), skipped or undated, still open and recent (in flight), or still open with no movement for longer than the stage normally takes (stale). Each stage is timed only over arrivals old enough to have finished it — at least three times its p90, two weeks minimum, before the export ends. If 60% or more of a stage's arrivals are recent and open, I stop: the early finishers cannot stand for the rest.

### Then five passes

1. **The clock.** Median, p75 and p90 wait at every stage, plus the share of total elapsed days each one carries. Ranked by days held, not by median: a four-day wait everybody sits through holds more calendar than a twenty-day wait forty people reach.
2. **Concentration.** For each stage, is the wait spread evenly or carried by a minority of locations, regions, sources or roles? Each segment is compared against the rest of the file rather than the overall median, which a large enough offender drags towards itself until it stops looking like one.
3. **Load.** Peak months (calendar months, with their year) come from your own volume; each stage is then measured by the month candidates arrived at it. A stage has to be both proportionally and materially slower — a median moving from one day to two is a rounding boundary, not a capacity problem.
4. **Confounds.** Every concentrated delay is re-tested holding each other dimension constant. If eight slow sites are slow because they run one role that needs a licence check, it is a role finding. An effect that shrinks below 40% or reverses inside the strata is listed under **Ruled out**, with the dimension that killed it named.
5. **Sizing.** What comes off the calendar if each confirmed problem is fixed, in days and in the number of people who wait them, using the confound-adjusted excess rather than the raw gap.

## What you get

A short report (`--md`): the stage holding the most calendar time, the stage carrying a concentrated delay, and whether they are the same stage — they usually are not, and that gap is the point. Then the per-stage clock with how many moved on, left and are still open, the confirmed findings sized in days, the load effects kept separate from the structural ones, what was ruled out and why, and what the data could not show (stale open applications, stages passed without a date, no exit reasons).

## What this does not claim

**It does not tell you a shorter wait means more hires.** Long waits and drop-off travel together, but how much of one converts into the other differs by stage and is not answerable from timestamps alone. That is a drop-off question, and a different analysis (`funnel-drop-off-analyst` in this library reads the same export for it). Saying so is cheaper than being caught at it.

## Verifying this yourself

Run `python3 scripts/analyze.py --test`. The samples carry a known timing structure: scarce scheduling capacity at eight sites, and a peak that lengthens a different stage. The suite asserts the site effect is found **at that stage and not at the others**, survives its confound checks, and is told apart from the load effect; that five managers planted with poor retention and no timing problem are never reported as slow; and that every closed application is counted as left, never as waiting. Then the guards: shuffled site labels flag no site, an effect that reverses within roles does not survive, and each refusal above is triggered on purpose.

## Works with

- **A CSV export from any ATS** — this is the default lane and needs nothing connected.
- **The Fountain Cue MCP** — when connected, it supplies the same fields directly, so re-running after a change costs you nothing. Fountain publishes this skill and sells Cue; the engine, the thresholds and the findings are identical either way, and the skill works completely without it.
- **The four synthetic samples** — retail, quick service, logistics and gig.

## Where this stops

In lane A this reads a file you exported, so it sees one moment and changes nothing. It cannot tell you your queue today, act on its findings, or tell you whether a fix worked — you would export again and re-run.

It cannot see *why* a stage is slow. It can tell you eight sites hold candidates six days longer at scheduling and that the effect survives every confound it could be tested against; it cannot tell you whether that is a rota problem, an unfilled vacancy, or a manager who never opens the queue. That part is yours.

And it measures waiting, not work: four days of nothing and four days of checks look identical in a timestamp. Which is which, you know and the export does not.
