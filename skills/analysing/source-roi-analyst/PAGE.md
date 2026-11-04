# Source ROI Analyst: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/roi.py --pipeline data/frontline_pipeline_sample.csv --spend data/sourcing_spend_sample.csv --screen-minutes 10 --hourly 18

## Example prompt

> Here's our pipeline export and our job board spend by month. What does each channel really cost per hire who's still there after 30 days? Count ten minutes of screening per application at $18 an hour.

## Example output

From the engine's run on the retail sample (`frontline_pipeline_sample.csv` and `sourcing_spend_sample.csv`: 17,010 applications over 11 months). An excerpt: the cost ladder and the move it recommends.

**The cost ladder**

| Channel | Spend | Applications | Per application | Per start | Per hire still there at 30 days | All-in per start |
|---|---:|---:|---:|---:|---:|---:|
| jobboard_c | $7,835 | 5,233 | $1.50 | $19.54 | $26.47 | $58.69 |
| social | $7,502 | 2,033 | $3.69 | $29.65 | $34.41 | $53.76 |
| jobboard_a | $15,280 | 3,400 | $4.49 | $34.57 | $40.85 | $57.65 |
| jobboard_b | $15,036 | 2,407 | $6.25 | $50.80 | $60.63 | $75.19 |

"All-in" adds the screening time you gave it: $3.00 an application. jobboard_c is the cheapest per start on media alone, but it takes 13 applications to get one start, and only 74% of its starts are still there at 30 days, against 86% for social. Once handling an application costs more than $2.02, social is cheaper per start.

**The move**

Move 15% of jobboard_b's monthly spend ($205 a month) to social: about 6.9 more starts a month from social and 4.0 fewer from jobboard_b, so +2.9 a month. Check after six weeks, and move it back if social's cost per start rises more than 20% above $29.65.

**Checked and cleared:** re-weighting by role, location and month leaves every channel's gap in place, so the differences belong to the channels, not to the mix.
