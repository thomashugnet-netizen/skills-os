# Pay Competitiveness Checker

> Places every posted hourly rate on the local wage ladder for the same job, from official US government wage data, and shows which postings pay less than most employers in that metro and what it would cost to fix.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You give it your postings, one row per job per city, and ask:

> "Are we paying enough to fill these?"

It matches each title to an occupation and each city to its metro, shows you the matches to confirm, then places every rate between the local 10th and 90th percentile for that occupation. You get the postings below the 25th percentile, where three in four employers of that job in that metro pay more, the gap in dollars an hour, the yearly cost of closing it, and the places where your own sites pay differently for the same job.

The arithmetic is done by `scripts/checker.py`, a dependency-free Python engine, against the U.S. Bureau of Labor Statistics wage estimates bundled in `references/wages.csv`.

## Why it exists

One national rate is not one decision. On the sample company, the same $14.50 cashier rate sits at the median in Dallas, Atlanta and Columbus, and below the 10th percentile in Phoenix. Its overnight stockers are below the 25th in three of four metros, and lifting the seven postings under the 25th costs about $47,000 a year across 30 openings. None of that shows in a pay table sorted by job.

## Install

**1. Download** [pay-competitiveness-checker.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/pay-competitiveness-checker.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the pay check demo."* Then with your own: *"Here are our postings and pay by city. Are we competitive?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/sourcing/pay-competitiveness-checker ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The data

U.S. Bureau of Labor Statistics, [Occupational Employment and Wage Statistics](https://www.bls.gov/oes/2025/may/oessrcma.htm), May 2025 estimates, published May 2026: hourly 10th, 25th, 50th, 75th and 90th percentile wages for 34 frontline occupations across 530 metropolitan and nonmetropolitan areas, all industries. BLS data is in the public domain; every report cites it as the source.

The estimates describe May 2025. The checker prints their age on every result and never adjusts them on its own. `scripts/build_wages.py` rebuilds the table from the next release.

## Where it fits, and where it does not

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Cashiers, sales associates, stockers, supervisors: high-volume jobs with a deep local ladder. |
| Quick-service restaurants | Strong | Crew, cooks, shift managers. |
| Logistics and delivery (W2) | Strong | Warehouse, forklift, delivery and truck drivers. |
| Gig and courier marketplaces | Limited | Contractors are paid per task, not by the hour, and the data covers employees only. |

US only. Wages, not total offers: benefits, schedules, tips and bonuses are not in the data.

## Verifying this yourself

```bash
python3 scripts/checker.py --test
```

The ladder arithmetic, the bands, pay parsing (rates, ranges, salaries), title and metro matching, refusals, and the uplift are tested against a small fixture table with known answers. Against the real table, the suite checks that every row has a median, that percentiles never decrease, and that only listed occupations are kept. The sample's expected results (every posting's band, the two postings that must not be placed, the one internal pay spread) were predicted by hand from the published percentiles before the engine was run, and the suite checks the engine agrees.

## Who it's for

- **HR, comp and talent leads** setting hourly rates across many sites.
- **Recruiting and ops managers** whose postings stay open and who want to know whether pay is why.
- **District managers** comparing their sites with each other and with the metro.
