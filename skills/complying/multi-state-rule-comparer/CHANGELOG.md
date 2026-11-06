# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter. The date the rules were checked is
at the top of `references/rules.json`; rules change faster than versions, so check that
date first.

## 1.0.0

First release, created with Trisha Zulic. Rules checked 2026-11-06.

- `references/rules.json`: 50 states and DC across 14 categories (714 cells: 332 read on a government page, 331 from agreeing compilations with the statute cited, 51 leads), about 90 city and county ordinances, and state preemption of local rules. Every cell names its source, its confidence and the date it was checked.
- Announced 2027 minimum wages for the states and cities that had published them by 2026-11-05; New York's 2027 off-ramp; Maine's pay range law (July 29, 2026), Virginia's (July 1, 2026) and Delaware's (September 26, 2027); Washington's fair chance amendments (July 1, 2026 and January 1, 2027); Connecticut's sick leave reaching every employer on January 1, 2027.
- `scripts/compare.py`: applies each threshold the way the law counts it (all employees, in-state, in-city, locations), sick leave tiers, industry-only rules, regional and local minimum wages, and dated changes against `--as-of`.
- Output: the grid, the strictest rule per category with whether one process can carry it, site by site, 18 months of dated changes, and a research checklist ordered by exposure with minors first. Text, Markdown, HTML and JSON.
- `--states` compares states with no site list; `--state` prints everything held for one state.
- Refuses employee-level files, personal columns, duplicate sites and files that are not UTF-8.
- Test suite: 4,521 checks, including the sample's planted findings and 300 random site files.
