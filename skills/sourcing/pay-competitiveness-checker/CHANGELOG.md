# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter. The wage data's reference period
is in `references/wages_meta.json`.

## 1.0.0

First release.

- Places each posted hourly rate on the local ladder for the same occupation: 10th,
  25th, median, 75th and 90th percentile, by straight line between published points.
- Wage data: U.S. Bureau of Labor Statistics, Occupational Employment and Wage
  Statistics, May 2025 (published May 2026), 34 frontline occupations, 530 metropolitan
  and nonmetropolitan areas. Public domain; BLS is cited on every report.
- Shows every title-to-occupation and city-to-metro mapping for confirmation, and
  never guesses either: an unknown title or a suburb is listed, not placed.
- Reads hourly rates, ranges (placed on the low end) and salaries (converted at 2,080
  hours, and said so).
- Reports the gap to the 25th percentile in dollars an hour and the yearly cost of
  closing it per opening, at the hours a week you give.
- Flags the same job in the same metro paid a dollar or more apart across your sites.
- Prints the data's age on every result. Never adjusts it on its own; an explicit
  `--uplift` percentage is applied and labelled when you give one.
- Flags thin estimates (fewer than 100 jobs of that kind in the area) and reports
  areas with no published estimate rather than filling them in.
- A fictional four-metro grocery chain as the sample. Its expected results were
  predicted by hand from the published percentiles before the engine was run, and
  the suite checks the engine agrees.
- `scripts/build_wages.py` rebuilds the table from the next BLS release, standard
  library only.
- An adversarial pass before release found 14 kinds of wrong answer and 6 crashes, from
  "$2,500/month" read as a salary and "401k" read as thousands, to a rate equal to a
  tied 10th and 25th filed as below market and "Cleaning Crew" mapped to fast food.
  Fixed and tested (101 assertions), with two limits left: a city in a metro that
  spans several states is matched and flagged for you to confirm rather than checked
  against the state it is really in, and a ladder whose low points are tied is drawn with
  its ticks stacked.
