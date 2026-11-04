# Time to Hire Analyst: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/analyze.py --input data/frontline_pipeline_sample.csv --md report.md

## Example prompt

> Here's our pipeline export for the last twelve months, one row per application with the date of each stage. Where is our hiring time actually going, and what can we fix?

## Example output

From the engine's run on the retail sample (`frontline_pipeline_sample.csv`: 18,184 applications across 42 stores). An excerpt of its report: the answer, the clock and the confirmed delay.

**The answer**

- **Most of the calendar:** interview_scheduled -> interview_completed, median 4 days, p90 6, 26% of all the days candidates spent waiting between stages.
- **The delay you can fix:** screened -> interview_scheduled, where 8 sites hold candidates 6.7 days longer than everyone else, after the confound checks.
- These are **different stages**. The first is long for everybody; the second is a local fix.
- **Only slow in peak months:** onboarding_started -> started. That is capacity, not process.

End to end, 1,922 people applied early enough to be timed to their first shift: median 16 days, p90 23. That is not the sum of the stage medians below, which describe larger groups.

**The clock, stage by stage**

| Stage | Median days | p90 | Timed | Share of waiting days | Moved on | Left | Still open |
|---|---:|---:|---:|---:|---:|---:|---:|
| applied -> screened | 2 | 3 | 9,772 | 21% | 9,772 | 8,412 | 0 |
| screened -> interview_scheduled | 2 | 4 | 6,928 | 22% | 6,928 | 2,844 | 0 |
| interview_scheduled -> interview_completed | 4 | 6 | 5,210 | 26% | 5,214 | 1,714 | 0 |
| interview_completed -> offer_extended | 2 | 3 | 3,581 | 8% | 3,583 | 1,631 | 0 |
| offer_extended -> onboarding_started | 1 | 2 | 3,027 | 4% | 3,033 | 550 | 0 |
| onboarding_started -> started | 6 | 11 | 2,047 | 19% | 2,155 | 878 | 0 |

**Confirmed delay**

- 8 sites hold candidates 6.7 days longer than the rest at screened -> interview_scheduled. 737 people waited there. About 4,916 candidate-days in this export. Segments: LOC-40, LOC-03, LOC-07, LOC-14, LOC-19, LOC-25, LOC-31, LOC-36.
