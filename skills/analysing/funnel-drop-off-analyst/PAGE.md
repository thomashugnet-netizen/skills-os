# Funnel Drop-off Analyst: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/analyze.py --input data/frontline_pipeline_sample.csv --out report.json

## Example prompt

> Here's our pipeline export for the last twelve months, one row per application. Where are we losing people, and which fix gets the most hires back?

## Example output

From the engine's run on the retail sample (`frontline_pipeline_sample.csv`: 18,184 synthetic applications across 42 stores). An excerpt: the funnel, the fix list, and one effect that survived the confound tests and one that did not.

**The funnel**

| Step | Reached | Moved on | Conversion | Lost |
|---|---:|---:|---:|---:|
| Applied → screened | 18,184 | 9,772 | 53.7% | 8,412 |
| Screened → interview scheduled | 9,772 | 6,928 | 70.9% | 2,844 |
| Interview scheduled → completed | 6,928 | 5,214 | 75.3% | 1,714 |
| Interview completed → offer | 5,214 | 3,583 | 68.7% | 1,631 |
| Offer → onboarding started | 3,583 | 3,033 | 84.7% | 550 |
| Onboarding started → first shift | 3,033 | 2,155 | 71.1% | 878 |

**The fix list, ranked by hires recoverable**

| # | Where the loss sits | Mechanism | Hires back | Who owns it |
|---|---|---|---:|---|
| 1 | Offer to first shift, for hires who wait 4 days or more | Candidate | 409 | Comms cadence and speed |
| 2 | Applied to screened, Midwest region | Rule | 249 | Whoever owns the screening configuration |
| 3 | Screened to interview scheduled, 8 stores | Capacity | 187 | Operations: slots, staffing, coverage |

All three carry a high confidence label. Each figure assumes the segment could reach your own best-performing band, not a benchmark, and the report says so beside it.

**Survived:** five hiring managers run 38% thirty-day attrition against 13% elsewhere. Held within role, source and region, the gap keeps 90% or more of its size.

**Ruled out:** weekend sign-ups look worse at reaching a first shift. Held within source, only 13% of the effect is left: the weekend gap comes from which channel those sign-ups arrived through, and the report names source as what killed it.
