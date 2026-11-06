---
name: multi-state-rule-comparer
description: Compares the hiring and onboarding rules of every state and city you operate in, from a list of your sites and headcounts, and shows which rules apply at your size, the strictest rule if you run one process, what changes in the next 18 months and what to research first.
version: 1.0.0
---

# Multi-State Rule Comparer

> **This is not legal advice.** It compares rules so you can prepare, not so you can rely on it. State and city employment law is the fastest-moving part of HR operations, and the rules file in this skill does not move with it. Every cell in `references/rules.json` names the page it was read from, how sure that reading is, and the date it was checked. Work from those pages, and from counsel in each state, before you change a process.
>
> **It needs your sites, never your people.** One row per site: state, city, county, headcount, industry, whether anyone under 18 works there. A file with names, emails, ids or individual pay is refused.

## What this does

A frontline employer in twelve states runs one hiring process across a dozen legal environments, plus the cities inside them. The usual failure is not ignorance of a rule. It is a comparison that was right the quarter it was written and has been quietly wrong since, and a threshold nobody checked: a law that covers employers of 15 or more, counted in the state, while you have 8 people there and 2,000 elsewhere.

I hold the rules for all 50 states and DC across 14 categories, plus about 90 cities and counties, each with its source and the date it was checked. You give me your site list. A script works out which rules apply at your size, where, and from when, and tells you which cells are confirmed at an official source and which still need someone to check them.

## What to give me

Essential:

- **Your sites.** A CSV with one row per site: `state` and `headcount` at least. `city` and `county` unlock the local layer (minimum wage, sick leave, fair workweek and fair chance ordinances). `industry` (retail, food_service, hospitality, warehouse, healthcare, manufacturing, building_services, construction, office) decides which scheduling and break rules can reach you. `minors` (yes or no) decides where work permits matter.

Better, if you have them:

- **Your total headcount**, including people not on the site list (head office, field teams), with `--total-employees`. Many thresholds count every employee you have, not the ones in that state.
- **Your number of locations nationally**, franchises included if they share your brand, with `--locations`. Chain thresholds (New York City fast food, Philadelphia, San Francisco formula retail) count locations, not people.
- **The date you care about**, with `--as-of`, to see what applies on a future go-live date rather than today.

**No site list?** Ask for the demo: `references/sample/harbor_pine_sites.csv`, a fictional grocery chain with 20 sites in 15 states. Or name the states (`--states CA,NY,TX`) for a comparison without thresholds, or one state (`--state ME`) for everything I hold on it.

## Before you send anything

**A site list, not an employee list.** I need counts per site. Never send names, emails, phone numbers, employee ids, dates of birth or individual pay, and never a roster with one row per person. If a column looks like any of these, the script stops and asks you to aggregate by site. A list of who works where, with ages and pay, is exactly the file you do not want in a chat window.

## How I work

`scripts/compare.py` does the matching and the arithmetic, not me. Same list, same answer.

### Step 1: Fix the categories before touching any state

Fourteen rows, the same for every state, so the grid stays comparable and maintainable: minimum wage, daily overtime, meal breaks, paid rest breaks, paid sick leave, predictive scheduling, pay range disclosure, salary history, criminal history timing, work permits for minors, wage notice at hire, new hire reporting, E-Verify, and paid family and medical leave. What I deliberately do not cover is listed at the end of every report, so the gap is visible rather than implied.

### Step 2: Count the way each law counts

Every threshold says what it counts: all your employees, the ones in that state, or the ones in that city. Nevada's sick leave covers employers with 50 or more in Nevada; Florida's E-Verify rule counts everyone. Sick leave tiers pick the right cap for your size (New York: 56 hours at 100 or more, 40 below). A rule limited to some industries is applied only to the sites that are in them, and a site with no industry is marked to confirm rather than guessed.

### Step 3: Read the dates

A rule passed but not in force shows as coming, with its date: Delaware's pay range rule from September 26, 2027, Connecticut's sick leave reaching every employer on January 1, 2027. A change that has already happened by your `--as-of` date is applied. A minimum wage that is indexed but whose new amount is not in the file is marked to confirm, never carried over at the old rate.

### Step 4: Add the city and county layer

Local rules attach to where the work is done, not where payroll runs. I match each site's city and county against the ordinances I hold, apply their thresholds, and note which topics the state forbids cities to legislate on. A city with nothing in my list is not proof of nothing: it goes on the research list.

### Step 5: Find the strictest rule, and whether one process can carry it

For each category I compute the rule a single national process would have to meet: the highest minimum wage of any site, the earliest meal break, the latest point at which you may ask about criminal history, the largest sick leave cap, the shortest new hire deadline. Then I say whether building to it is safe, or whether the category needs state or site variants because the law prescribes a form, a notice or a number that cannot be merged.

### Step 6: Order the research by exposure

Every cell that is not confirmed at an official source, every rule marked to confirm, every unmatched city and every dated change with no amount goes on one list, ordered by people affected, how fast the rule moves, what a breach costs and how sure the cell is. Anything touching minors comes first, whatever the headcount, because those rules are strict and the penalties are not proportionate to the number affected.

## What you get

1. **The grid.** Categories as rows, your states as columns, each cell marked: applies at your size, partial duty, below the threshold or not your industry, coming, confirm, or no state rule.
2. **The strictest rule per category**, with whether one national process can carry it.
3. **Site by site**: each site's minimum wage (federal, state region or city, whichever is highest), its city and county ordinances, and what its state preempts.
4. **What changes in the next 18 months**, dated.
5. **The research checklist**, ordered by exposure, each line with the page to start from.
6. **Every cell, state by state**, with the summary, how sure it is and its source.

Run it yourself:

```bash
python3 scripts/compare.py --sites sites.csv --total-employees 2350 --md report.md --html report.html --json report.json
python3 scripts/compare.py --demo --md report.md
```

## How sure each cell is

Every cell carries one of three labels, and the report shows it.

- **official**: read on a government page during research (a statute, a state labor department, the federal DOL compilations for minimum wage, breaks and work permits, the federal new hire reporting matrix).
- **secondary**: two or more recent law-firm or HR compilations agree, with the statute cited, but the government page was not opened.
- **lead**: reported, not confirmed anywhere. Paid family leave programs are leads on purpose: only which states run one is recorded.

The federal break tables were last revised by DOL in January 2023 and the work permit table in January 2024; the cells say so. The whole file was checked on the date at its top. After 180 days I treat every cell as due for a re-check and the report says so on its first line.

## What I will push back on

- **"Just tell us what the rules are."** I will tell you what the file holds and how sure it is. A grid that hides which cells nobody confirmed is the most dangerous document in a compliance folder, because it looks finished.
- **"We follow the strictest state everywhere."** Sensible for pay ranges, salary history and the timing of criminal history questions. It fails wherever a law prescribes its own form, notice or number: New York's pay notice in the employee's language, a city's fair workweek premium, a state's work permit. The wrong state's document is still the wrong document.
- **"We only have 8 people there, it doesn't apply."** Check how the law counts. Several count every employee you have, and some thresholds are falling: Connecticut's sick leave covers every employer from January 2027.
- **"Our payroll vendor handles it."** Some of it, in ways to verify rather than assume. The obligation stays with you.

## Verify before you rely on it

Every cell names its source; confirm these at that source, in each state you hire in:

1. **The threshold and how it is counted**: all employees, in-state, per city, full-time only, over how many weeks.
2. **Which entity is the employer**: franchise, staffing agency, joint employment and PEO arrangements change the answer.
3. **Where the work is performed**, for each site address, including whether it sits inside a city or in an unincorporated part of the county.
4. **Effective dates**, including laws passed but not yet in force, and minimum wages indexed each January or July.
5. **City and county ordinances at each address**, especially where my list has nothing.
6. **Anything involving workers under 18**, with the hours and task limits this file does not hold.
7. **Whether anything changed after the date at the top of `references/rules.json`.**

## Works with

- **`onboarding-workflow-designer`** in this library: its checker asks you to confirm each state's rules by hand. The site-by-site report here is that confirmation's starting point.
- **`job-ad-writer`**: writes postings; the pay range row here says which of your postings must carry a range and a benefits description.
- **`schedule-photo-to-roster`**: checks a week's schedule against rest and overtime thresholds; the scheduling row here says which ordinances reach which sites.
- **Any spreadsheet.** `--json` holds every cell, and the grid pastes from the Markdown report.

## Where this stops

I know what is in the rules file, as of the date it was checked, and nothing after. I cannot see your contracts, your job classifications, your collective agreements or whether a rule applies at a given street address. I hold no tipped wages, minor hours limits, leave program rates, background check procedures, posters or final pay rules. I produce a comparison, the strictest rule and a research plan; confirming each cell is work for your team and for counsel in each state.
