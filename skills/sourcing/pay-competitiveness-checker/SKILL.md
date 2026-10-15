---
name: pay-competitiveness-checker
description: Places every posted hourly rate on the local wage ladder for the same job, from official US government wage data, and shows which postings pay less than most employers in that metro, what it would cost to fix, and where your own sites pay differently for the same job.
version: 1.0.0
---

# Pay Competitiveness Checker

## What this does

You give me what you post for each job in each city. I place every rate on the local ladder for that occupation, from the 10th to the 90th percentile of what employers in that metro actually pay, and tell you which postings are priced to stay open.

The insight is that one national rate is not one decision. On the sample company, the same $14.50 cashier rate sits at the median in Dallas, Atlanta and Columbus, and below the 10th percentile in Phoenix. The rate is fine three times and a problem once, and a single company-wide number cannot show that.

The wages come from the U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, bundled in `references/wages.csv`: 34 frontline occupations across 530 metropolitan and nonmetropolitan areas. `scripts/checker.py` does the arithmetic. Same file, same answer.

## What to give me

Essential, one row per posting:

- **`job_title`** as you post it, and **`pay`**: an hourly rate, a range (`16-18`, placed on its low end, because that is the number an applicant compares), or a salary (`$46,000/yr`, converted at 2,080 hours, and I say so).
- **Where:** `city` and `state`, or `area` (the metro's name or code) when the city is a suburb.

Better, if you have them:

- **`site`** and **`openings`**, so the cost to fix is counted per opening and your own sites can be compared with each other.
- **`soc`**, the occupation code, for any title I do not recognise.
- **`hours_per_week`** per posting, if not 30, for the cost figure.

A pay value I cannot read as a rate ("DOE", "up to $18", a tipped base, a day rate) is listed with the reason, and the other postings still run. Postings need no names or contact details, and a file with an email address in it is refused.

**No file handy?** Ask for the demo: `references/sample/northline_postings.csv`, a fictional grocery chain with stores in four metros and a distribution centre.

## How I work

### Step 1: Match each posting to an occupation, and show you

"Crew member", "barista" and "front counter" are all one occupation in the wage data; "warehouse associate" and "picker" are two. I match titles through `references/occupations.json` and show every mapping before you read a single result. A title I do not recognise is listed, never guessed: you confirm the occupation or add its code. So is a title that names a second job inside it ("Cashier Supervisor", "Delivery Driver Helper", "Cashier/Stocker"), because the word that changes the job is easy to miss.

### Step 2: Find the metro

A city is matched only when it is a principal city in a metro's official name. A suburb such as Plano is not guessed into Dallas: I ask you to name the metro, because the wrong ladder gives a confident wrong answer.

### Step 3: Place each rate on the ladder

The data gives five points: the 10th, 25th, 50th, 75th and 90th percentiles. I place your rate between them on a straight line and put it in one of five bands: bottom 10%, below market (10th to 25th), under the median, at or above the median, top quarter.

Below the 25th percentile means three in four employers of that job in that metro pay more. That is the line I report against, with the gap in dollars an hour and the yearly cost of closing it.

### Step 4: Compare your own sites

The same job in the same metro paid a dollar or more apart across your sites is listed. It is a fairness question before it is a market one, and applicants compare postings too.

### Step 5: Say how old the data is

The estimates describe May of their survey year and are published a year later. I print their age on every result and do not adjust them on my own. If you want them moved forward, give me a percentage (`--uplift`), and every number that uses it says so.

## What you get

1. **The mappings**, to confirm.
2. **The headline:** postings in the bottom 10%, postings below the 25th, the openings they cover, and the yearly cost of lifting them to the 25th.
3. **Every posting on its ladder**, worst first, with the local 10th, 25th, median and 90th.
4. **Same job, same metro, different pay** across your own sites.
5. **What could not be placed, and why.**
6. **A one-page report** (`--html`), each posting drawn on its local ladder.

```bash
python3 scripts/checker.py --postings postings.csv --hours-per-week 30 --html pay.html
```

## What I will push back on

- **"We pay competitive wages."** Competitive with whom? A rate is only competitive against the same job in the same place.
- **A national rate.** It is a different decision in every metro you hire in.
- **Calling the median the target.** At the median, half the employers pay more. Below the 25th, most of them do. Where to set pay is your decision; I only show where it lands.

## What the data cannot tell you

These are wages, not total offers. Benefits, schedule, tips, bonuses and how quickly you hire all change what a rate is worth to an applicant, and none of them are in the data. The estimates cover all employers of an occupation in a metro, not your direct competitors. An estimate based on few jobs in an area is flagged as thin. And an area or occupation with no published estimate is reported as such, never filled in from somewhere else.

## Works with

- **`job-ad-writer`.** It puts the number in the ad; this checks the number first.
- **`career-site-builder`.** It shows pay on every job page; this tells you whether that pay will get read twice.
- **The Fountain Cue MCP.** When connected, it can read your live openings and their pay, so the check runs without an export. Fountain publishes this skill and sells Cue. The data, the checks and the report are identical either way, and the skill works completely without it.

## Where this stops

It compares posted pay with published market wages and nothing else. It is not a pay recommendation, does not check minimum-wage or pay-transparency law, and cannot see what your competitors are posting this week. The data is a survey of what employers paid, published with a delay, and local labour markets move faster than it does.
