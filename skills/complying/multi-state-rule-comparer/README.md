# Multi-State Rule Comparer

> Compares the hiring and onboarding rules of every state and city you operate in, from your site list: which rules apply at your size, the strictest rule if you run one process, what changes in the next 18 months, and what to research first. Every rule names its source and how sure it is.

Created with Trisha Zulic. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The rules:** all 50 states and DC across 14 categories (minimum wage, daily overtime, meal and rest breaks, paid sick leave, predictive scheduling, pay range disclosure, salary history, criminal history timing, work permits for minors, wage notice at hire, new hire reporting, E-Verify, paid family and medical leave), plus about 90 city and county ordinances and which topics each state forbids its cities to legislate on. 714 state cells: 332 read on a government page, 331 from recent compilations that agree and cite the statute, 51 leads. Each one carries its source and the date it was checked.

**The comparison:** give it your sites (state, city, county, headcount, industry, whether minors work there) and `scripts/compare.py` works out which rules apply at your size, counting the way each law counts: all employees, in the state, or in the city. Sick leave tiers, industry-only rules, chain thresholds that count locations, and laws passed but not yet in force are all handled.

**The output:** the grid, the strictest rule per category with whether one national process can carry it, each site's minimum wage and local ordinances, the changes coming in the next 18 months, and a research checklist ordered by exposure, minors first.

## Why it exists

A multi-state comparison is usually a spreadsheet that was right the quarter it was written. Nobody dated the cells, so nobody knows which ones have gone stale, and nobody wrote down how each threshold counts, so a store with 8 people in Connecticut looks exempt from a law that covers it from January 2027.

On the demo, a fictional grocery chain with 20 sites in 15 states and 2,350 employees: 104 state rules and 28 city or county rules apply. One national minimum wage would have to be $21.30, set by Seattle. Its Philadelphia distribution center is outside the city's fair workweek law (warehouses are not covered), while its Los Angeles, Seattle, Chicago and Brooklyn stores are inside theirs. Its 30 people in Las Vegas are below Nevada's 50-employee sick leave threshold, its 8-person Connecticut café becomes covered on January 1, 2027, and Delaware's pay range rule reaches its Wilmington store in September 2027. Fourteen dated changes in the next 18 months, and 87 research items, the six work-permit states with minors first.

## Install

**1. Download** [multi-state-rule-comparer.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/multi-state-rule-comparer.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the multi-state rule comparer demo."* Then: *"Here are our 14 stores with headcounts. Which state and city rules apply to us, and what should we research first?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/complying/multi-state-rule-comparer ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | What | |
|---|---|---|
| sites | `state, headcount` + `site_id, city, county, industry, minors` | yours |
| rules | `references/rules.json`: every cell with its source, confidence and date | shipped |

Common column names are recognised (`store`, `employees`, `st`, `under_18`). One row per site: a file with names, emails, ids, dates of birth or individual pay is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Many sites, minors on staff, and most fair workweek and pay range laws written with retail in mind. |
| Quick-service restaurants | Strong | Local minimum wages, scheduling ordinances that count locations, minors. |
| Logistics and warehousing (W2) | Strong | Sites in suburbs and unincorporated counties, where the local layer is easiest to miss. |
| Hospitality | Partial | State and city rules hold; hotel-worker minimum wages and ordinances are not in the file. |
| Healthcare support | Partial | General rules hold; licensing, healthcare-specific wage rules and scheduling exemptions are not covered. |
| Gig and 1099 delivery | Weak | Almost every rule here is for employees. |
| Outside the US | No | US states and cities only. |

## Verifying this yourself

```bash
python3 scripts/compare.py --test
```

4,521 checks. The rules file is checked for shape (every state has every category, every cell a source unless it is a lead, every threshold says how it counts). Facts that must not drift silently are pinned: Maine's 10-employee pay range threshold, Delaware's 2027 date, Florida's 25-employee E-Verify rule, New York's regional minimum wage. Then the logic: thresholds counted in-state against total (Nevada, North Carolina, Florida), tiers (New York, Michigan, Nebraska, DC), dates before and after a change (Connecticut, Delaware, Washington, Michigan, California), industry-only rules (Maryland meal breaks, Oregon scheduling, Philadelphia), chain thresholds, regional and city minimum wages, unincorporated counties, city name variants, preemption. Refusals: personal columns, duplicate sites, files that are not UTF-8, impossible headcounts. The sample's planted findings must all come back, and 300 random site files must never crash it.

Exit codes: 0 report written, 2 input refused.

Not legal advice. Each cell names its source; confirm it there before changing a process.

## Who it's for

- **HR operations and compliance leads** at frontline employers in several states.
- **Talent acquisition leaders** standardizing postings, screening and onboarding across states.
- **Anyone opening a site in a new state or city**, with `--as-of` set to the opening date.
