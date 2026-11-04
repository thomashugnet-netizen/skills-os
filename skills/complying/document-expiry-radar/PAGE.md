# Document Expiry Radar: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/radar.py --documents references/sample/northline_documents.csv --shifts references/sample/northline_shifts.csv --requirements references/sample/northline_requirements.csv

## Example prompt

> Here's our certifications export and next week's schedule. Who can't work, whose renewal should already have started, and which shifts are at risk?

## Example output

From the engine's run on the demo files (`references/sample/northline_*.csv`: a fictional delivery company with 164 people at five stations), on 4 November 2026. An excerpt.

**Headline:** 6 people cannot work today (none of them still on the schedule), 4 renewals should already have started, 18 documents lapse within 30 days, and 3 drivers have no DOT medical card on file at all.

**Start the renewal now**

| Person | Station | Document | Expires | Renewal takes | Should have started |
|---|---|---|---|---|---|
| W-0508 | STN-05 | DOT medical card | 5 Nov | about 21 days | 15 Oct |
| W-0109 | STN-01 | DOT medical card | 8 Nov | about 21 days | 18 Oct |
| W-0501 | STN-05 | Driver's licence (incl. CDL) | 25 Nov | about 30 days | 26 Oct |
| W-0105 | STN-01 | Driver's licence (incl. CDL) | 29 Nov | about 30 days | 30 Oct |

**Crunch week:** STN-05 has 14 forklift operator evaluations expiring in the same week, the week of 23 November.

**About the file:** one expiry date could not be read and was left out, by name, rather than guessed. One older record was replaced by a later expiry for the same person and document.
