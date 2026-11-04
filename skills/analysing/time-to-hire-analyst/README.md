# Time to Hire Analyst

> Breaks hiring cycle time down stage by stage and names the stage actually holding the queue: the one slow for everybody, the one slow at a few sites, and the one slow only in peak season, kept apart.

Created with Kathleen Rakusin. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You point it at a pipeline export, one row per application with a date for each stage, and ask:

> "Where is our hiring time actually going?"

It answers three questions, kept apart because they have different owners:

- **Where is the calendar going?** Every stage's median, p75 and p90 wait, ranked by the share of all waiting days it holds, not by its median.
- **Slow for everyone, or for a few?** For each stage, which sites, regions, sources or roles hold candidates materially longer than the rest, re-tested holding each other dimension constant. What does not survive is listed as ruled out, with the reason.
- **Slow always, or only in peak months?** Peak months come from your own volume. A stage that only stretches then is a staffing decision, not a process change.

It sizes each confirmed delay in days and in the number of people who wait them, and writes a one-page report (`--md`) beside the full JSON. The arithmetic is done by `scripts/analyze.py`, a dependency-free Python engine: same export, same numbers, every run.

## Why it exists

"Time to hire" is one number for a process that is slow in several unrelated ways at once. On the retail sample (18,184 applications), the stage holding the most calendar time is the interview itself, four days for everybody, 26% of all waiting days. The stage you can actually fix is the one before it: eight sites out of 42 hold candidates 6.7 days longer to get an interview booked, after checks for role and source. And the run-up to the first shift is three days longer in October to December only (8 against 5), which is staffing, not process. One average reports none of the three.

It also refuses the two easy mistakes with the queue. Count everyone without a next date as "waiting" and candidates rejected months ago swell a queue that does not exist: on that same sample, 8,412 people who left at screening. Time a stage over its most recent arrivals and only the fast ones have finished. So every candidate is sorted once (moved on, left, still open and recent, still open and stale), and each stage is timed only over arrivals old enough to have finished it.

## Install

**1. Download** [time-to-hire-analyst.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/time-to-hire-analyst.zip). Do not unzip it. The retail sample is inside.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the time to hire demo."* Then: *"Here's our pipeline export for the last six months, pulled today. Where is our hiring time going?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/analysing/time-to-hire-analyst ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Many sites on one process, so a slow minority of sites stands out from the rest. |
| Quick-service restaurants | Strong | Short funnels where a two-day queue at one step is most of the cycle. |
| Logistics and delivery (W2) | Strong | Checks before day one carry long waits; separating them from scheduling delay is the point. |
| Gig and courier marketplaces | Strong | The five-stage activation funnel (sign-up, documents, background check, onboarding, first job) is read natively. |
| An ATS that keeps only the current status | Does not fit | Without a date for each stage there is no wait to measure. Ask for the status-history log instead. |
| Under 500 applications, or one site | Weak | Stage medians move days on a handful of records, and there is no minority to compare. |

## Verifying this yourself

```bash
python3 scripts/analyze.py --test
```

118 checks across the four synthetic samples (40 with the retail sample shipped in the zip). The samples carry a planted timing structure, and the assertions compare effects rather than test one threshold: the eight scarce sites are found at the scheduling step and not at the others; the effect survives role and source; the peak-season stretch lands on a different stage; five managers planted with poor retention and no timing problem are never reported as slow; and every closed application is counted as left, never as waiting. Then the guards: shuffled site labels must flag no site, an effect that reverses within roles must not survive, a funnel losing most people at step one must still run, and a file mostly in flight, a status-history log, spreadsheet serial dates, ambiguous day/month dates, a non-UTF-8 file, a name or email column, a thin file, crossed date columns and mixed stage vocabularies must each be refused. Before release, 5,150 randomly damaged files ran without a crash.

Exit codes: 0 report written, 3 input refused, 4 the engine itself failed.

## Who it's for

- **Talent acquisition leaders** asked why hiring takes as long as it does, who need to point at a stage and an owner.
- **HR and recruiting operations** deciding between a process change, a local fix and peak-season staffing.
- **Anyone reporting time to hire** who wants the number to come with what is behind it.
