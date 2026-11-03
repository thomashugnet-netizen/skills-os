# Source ROI Analyst

> Prices every hiring channel per start and per hire still there at 30 days, not per application, and says how much budget to move, with a check date and a stop rule.

Created with Cathy Neal. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Joins your pipeline export to your channel spend and builds the cost ladder: cost per application, per screen pass, per interview, per offer, per start, per hire still there at 30 days. Then:

- **reconciles the files first**: label variants, months missing on either side, application counts that disagree, channels with no spend
- **prices screening time** if you say how long an application takes and what the hour costs, and gives the break-even above which the cheapest channel stops being cheapest
- **checks the mix**: a channel bought for your hardest role, your weakest sites or your peak months is not charged for them
- **reads elasticity** only where your history can support it, and says so when season and saturation cannot be told apart
- **proposes a bounded move**: 15% of the dearest fully priced channel's spend to the cheapest, with expected starts, extra screening, a six-week check and a rule for moving it back

Referral and career site are labelled partial cost and never ranked: their price is not in the spend file.

## Why it exists

Channels are sold on cost per application. On the frontline sample, the cheapest job board costs $1.50 an application against $3.69 to $6.25 for the others, converts worst, takes 13 applications per start and keeps 74% of its starts at 30 days against 84% to 86% elsewhere. On media cost alone it is still the cheapest per start. Once screening an application costs more than about $2 (seven minutes at $18 an hour), it is not. That break-even is the number a hiring team can actually argue about.

## Install

**1. Download** [source-roi-analyst.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/source-roi-analyst.zip). Do not unzip it. The frontline sample is inside.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the source ROI demo, with ten minutes of screening per application at $18 an hour."* Then: *"Here's our pipeline export and our job board spend, what does each channel cost per hire?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/analysing/source-roi-analyst ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Several paid job boards, high volume, screening done by store managers. |
| Quick-service restaurants | Strong | Text-to-apply and job boards side by side, very short funnels. |
| Logistics and delivery (W2) | Strong | Agencies and boards at very different prices per start. |
| Gig and courier marketplaces | Strong | Paid social, affiliates and search ads priced per activated worker. |
| One channel only | Does not fit | There is nothing to compare. |

## Verifying this yourself

```bash
python3 scripts/roi.py --test
```

92 checks. In each of the four synthetic datasets, the planted patterns must come back: the cheap channel cheapest per application, worst at converting, most applications per start, fewest still there at 30 days; referral and career site partial cost and never ranked; nothing explained by mix; the seasonal confound named. The break-even is checked from both sides. A channel deliberately bought for the hardest role must be caught as explained by mix and kept out of the budget move. Label variants, a missing channel, a missing month and a 40% volume gap must be reported; name and email columns, thin files, duplicate ids and bad spend must be refused. Before release, 1,950 randomly damaged file pairs ran without a crash.

Exit codes: 0 report written, 3 input refused, 4 the engine itself failed.

## Who it's for

- **Talent acquisition and recruitment marketing leads** who set channel budgets.
- **HR operations and finance partners** who want cost per hire they can defend.
- **Anyone renewing a job board contract** on the strength of its application numbers.
