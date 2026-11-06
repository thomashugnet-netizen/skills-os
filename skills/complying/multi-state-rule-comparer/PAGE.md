# Multi-State Rule Comparer: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output or the rules
file changes, re-run this and update the excerpt:

    python3 scripts/compare.py --demo --as-of 2026-11-06 --md report.md

## Example prompt

> We run 20 sites in 15 states: grocery stores, a café in Hartford, a distribution center in Philadelphia and another in unincorporated Los Angeles County. 2,350 employees in total, including head office. Several stores employ 16 and 17 year olds. Here is the site list with city, county, headcount and whether minors work there. Which state and city rules apply to us, what is the strictest version of each if we run one national process, what changes in the next 18 months, and what should we research first?

## Example output

From the skill's demo: Harbor & Pine Market, a fictional grocery chain (`references/sample/harbor_pine_sites.csv`, 20 sites in 15 states), compared as of November 6, 2026. An excerpt.

**The grid** (6 of 14 rows)

● applies at your size · ◆ a city or county rule applies · ◐ partial duty · ○ below the threshold or not your industry · → coming · ? confirm · – no rule

| | NY (320) | TX (280) | CA (240) | WA (220) | PA (210) | IL (160) | FL (120) | GA (115) | CO (110) | NJ (75) | VA (60) | ME (45) | DE (40) | NV (30) | CT (8) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Minimum wage | ● | – | ● | ● | – | ● | ● | – | ● | ● | ● | ● | ● | ● | ● |
| Paid sick leave | ● | – | ● | ● | ◆ | ● | – | – | ● | ● | – | ● | – | ○ | → |
| Predictive scheduling | ◆ | – | ◆ | ◆ | – | ◆ | – | – | – | – | – | – | – | – | – |
| Pay range disclosure | ● | – | ● | ● | – | ● | – | – | ● | ● | ● | ● | → | ◐ | ● |
| Criminal history timing | ◐ | – | ● | ● | ◆ | ● | – | – | ● | ● | ◐ | ● | – | – | ● |
| Minors: work permits | ● | – | ● | ● | ○ | ● | – | ○ | ○ | ● | ○ | ● | ○ | ○ | ○ |

**The strictest rule, if you run one process** (3 of 14)

- **Minimum wage** (needs state or site variants): $21.30 at HP-SEA-01 (Seattle). One national rate would have to be at least this. Rates cannot be merged: each site pays at least the highest of federal, state and local rates. Paying the highest rate everywhere is a business choice, not a compliance need.
- **Pay range disclosure** (one process works): A good-faith pay range in every posting, internal and external (CA, CO, CT, IL, Jersey City, ME, NJ, NY, New York City, VA, WA), with a benefits description (CO, CT, IL, Jersey City, NJ, WA). A good-faith pay range plus a short benefits description in every posting, internal and external, satisfies every state posting law here. Some states add duties on promotions or on request.
- **Criminal history timing** (one process, with variants): No criminal history questions before a conditional offer (CA, Chicago, Los Angeles, Los Angeles County (unincorporated), New York City, Philadelphia, WA). Before withdrawing an offer, the longest response window is 10 business days (Philadelphia). Asking nothing about criminal history until after a conditional offer meets every timing rule. The notice and waiting steps before withdrawing an offer differ by state and city and need variants.

**What changes in the next 18 months** (3 of 14)

| Date | Where | Rule | Change |
|---|---|---|---|
| 2027-01-01 | Connecticut | Paid sick leave | Coverage extends to employers with 1 or more employees in Connecticut. |
| 2027-01-01 | Washington | Criminal history timing | The conditional-offer rule extends to employers of every size. |
| 2027-09-26 | Delaware | Pay range disclosure | Pay range and benefits in every posting, 26+ employees. |

**Site by site** (4 of 20)

| Site | Place | People | Minimum wage | City and county rules |
|---|---|---|---|---|
| HP-SEA-01 | Seattle, WA | 150 | $21.30 (Seattle) | Seattle: criminal history timing ●; Seattle: minimum wage ●; Seattle: paid sick leave ●; Seattle: predictive scheduling ● |
| HP-LAX-02 | Unincorporated, CA | 60 | $18.47 (Los Angeles County (unincorporated)) | Los Angeles County (unincorporated): criminal history timing ●; Los Angeles County (unincorporated): minimum wage ●; Los Angeles County (unincorporated): predictive scheduling ○ |
| HP-PHL-DC1 | Philadelphia, PA | 210 | $7.25 (federal) | Philadelphia: criminal history timing ●; Philadelphia: paid sick leave ●; Philadelphia: predictive scheduling ○; Philadelphia: salary history ● Preempted by the state: minimum wage. |
| HP-LVS-01 | Las Vegas, NV | 30 | $12.00 (NV) | none in my list |

**Research checklist, by exposure** (3 of 87)

| # | Rule | Where | What to confirm | Start at |
|---|---|---|---|---|
| 1 | Minors: work permits | New York | Before a minor's first shift: Working papers required under 18, issued by the school. Hours and task limits are not covered here. | [US DOL, State employment/age certificate requirements](https://www.dol.gov/agencies/whd/state/age-certificates) |
| 13 | Predictive scheduling | HP-LAX-01 (Los Angeles, CA) | Los Angeles: Fair Work Week: retail employers with 300+ employees globally: 14 days' notice, 10 hours' rest (premium with consent), hours offered to current staff, good-faith estimate before hire. | [source](https://wagesla.lacity.gov/fair-work-week-information) |
| 25 | Criminal history timing | HP-ATX-01 (Austin, TX) | Austin: Fair Chance Hiring: no criminal history questions before a conditional offer; employers of 15+. Texas's 2023 preemption law may reach it: confirm. (not confirmed) | [Accurate, Ban the box laws by state and jurisdiction](https://www.accurate.com/ban-the-box/) |
