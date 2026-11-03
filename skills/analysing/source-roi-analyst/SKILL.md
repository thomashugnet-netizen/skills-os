---
name: source-roi-analyst
description: Joins channel spend to hiring outcomes and prices every source per start and per hire still there at 30 days, not per application. Reconciles the two files first, prices screening time if you give it, checks the ranking is not just role, site or season mix, and proposes a bounded budget move with a check date and a stop rule.
version: 1.0.0
---

# Source ROI Analyst

Created with Cathy Neal.

## What this does

Works out what each hiring channel costs you per **start**, then per hire **still there at 30 days**. Almost nobody has those two numbers, because producing them means joining a spend file to an outcome file, and most reporting stops at cost per application. That is the number channels are sold on, and on its own it misleads.

The arithmetic is not done in prose. `scripts/roi.py` reconciles the files, builds the cost ladder, measures 30-day retention, runs the mix checks and sizes the budget move; I read its output back to you. Same files, same numbers, every time.

## What to give me

Two files. They join on month and source label.

**Pipeline export** (one row per application)

| Column | Example | |
|---|---|---|
| `application_id` | `APP-004182` | required |
| `source` | `jobboard_c` | required |
| `applied_at` | `2026-03-04` | required |
| `first_shift_at` (or `first_job_at`) | `2026-03-22` | required, or `stage_reached` = `started` |
| `screened_at`, `interview_completed_at`, `offer_at` | dates | each adds a rung to the ladder |
| `separation_at` or `tenure_days` | `2026-04-10` / `19` | for cost per hire still there at 30 days |
| `role`, `location_id` | `Cashier`, `LOC-14` | for the mix check |

**Spend export**

| Column | Example | |
|---|---|---|
| `month` | `2026-03` | required |
| `source` | `jobboard_c` | required |
| `spend_usd` | `938.03` | required |
| `applications` | `345` | optional: lets me check the two files count the same thing |

**Optional, and it changes the answer:** how long it takes to screen one application and what that hour costs. Every application is someone's time. Give me both and I add it to every channel as an all-in cost per start.

**No export handy?** Use `frontline_pipeline_sample.csv` and `sourcing_spend_sample.csv` from this library: 18,184 synthetic applications at 42 stores over a year. The quick-service, logistics and gig samples work the same way.

## Before you paste anything

**Remove personal data from the export.** I need categories and dates, never identities. Before exporting, drop names, emails, phone numbers, street addresses, dates of birth, government id numbers and free-text notes. `application_id` should be opaque.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** Candidate records belong inside your own systems, not in a chat window, and nothing here needs to know who anybody is. The engine enforces it before it reads a row.

## How I work

### Step 1: Reconcile the two files first

Every number downstream inherits a mistake made here, so this comes first and I stop on it.

- **Labels.** `jobboard_a` in one file and `Job Board A` in the other: I treat them as one channel and say so, so you can check. A label in one file only is reported: its cost is missing, not zero.
- **Months.** Months missing from either side are left out and named. Months too recent for their applications to have started (45 days) are left out too, or the newest month would look like a channel that never converts.
- **Volumes.** Where the spend file carries an application count, I compare it with the pipeline. A gap over 5% usually means one side counts clicks or duplicates. I report it rather than pick a side.

### Step 2: The cost ladder

For each channel: cost per application, per screen pass, per interview, per offer, per start, per hire still there at 30 days. Side by side, because the ranking can reorder as you move right, and when it does, that is the finding.

When it does not reorder, I say so. A channel can be the cheapest per application, convert worst and **still** be the cheapest per start on media cost alone, because its price is low enough to absorb the waste. What it does not absorb is your team's time.

### Step 3: Price the screening

A channel that takes thirteen applications to produce a start, where others take eight, is spending a manager's afternoon on every hire. I compute the **break-even**: the cost of handling one application above which the media-cheapest channel stops being the cheapest per start. If your screening costs more than that, the cheap channel is not cheap. With your minutes and hourly cost, I add it to every channel and re-rank.

### Step 4: Still there at 30 days

Starts are not the finish line. For starts with a full 30 days behind them, I measure who is still there, by channel, with a 90% range, and divide the cost per start by it. Starts too recent to judge are left out and counted, because a nine-day-old start always looks like it stayed.

### Step 5: The channel, or the mix?

Channels are not bought evenly across roles, sites and months. A channel bought mostly for your hardest role is charged for the role. So I re-weight each channel's start rate to one role mix, one site mix and one month mix. A channel whose gap halves or flips is reported as **explained by mix**, and I build no budget move on it.

### Step 6: Does it get worse as you spend more?

Cost per start was measured at the spend you ran, and is not a constant. I check, in your own history, whether starts per dollar fall in a channel's high-spend months. When those months are your peak months for every channel, saturation and season cannot be told apart, and I say that instead of fitting a line to it. Where spend barely varies, I say it cannot be read.

### Step 7: A bounded move

Move a bounded share (15% by default, 20% at most) of the dearest fully priced channel's monthly spend to the cheapest, measured per hire still there at 30 days (screening included when you priced it). I give the starts it should add and lose, the extra applications to screen, the assumption, a check after six weeks and the rule for moving it back.

**Partial cost.** Referral and career site usually have no real price in the spend file: no referral bonuses, no recruiter time, no site cost. I label them partial cost everywhere and never rank them or send money to them. They also benefit from last-touch attribution: someone sees a paid ad, searches your name and applies through the career site, and the career site takes the credit.

## What you get

1. **Reconciliation note**: label variants, missing months, volume gaps, channels with no spend.
2. **The cost ladder**, with every rank change flagged, and the all-in column if you priced screening.
3. **The break-even** handling cost for the cheapest channel.
4. **30-day retention by channel**, with ranges.
5. **The mix check**: raw beside re-weighted, and what was explained by mix.
6. **The elasticity read**, or a plain statement that your history cannot support one.
7. **The reallocation**: amount, expected starts, extra screening, assumption, check date, stop rule.
8. **What it could not see**: partial-cost channels, attribution, unpriced costs.

```bash
python3 scripts/roi.py --pipeline pipeline.csv --spend spend.csv --screen-minutes 10 --hourly 18 --html roi.html
```

## What I will push back on

- **"Move everything into the cheapest channel."** Every channel has a finite pool at a given price. You exhaust the good part of it before the budget, the ranking was measured at your current split, and one channel supplying most of your starts is a single point of failure. Move in increments, re-measure, keep a second channel alive.
- **"That channel gives us the most applications."** Volume is what the channel optimises and is paid on. On your side it is screening time. A channel that doubles applications and halves the start rate delivered no extra hires and a lot of extra work.
- **"Referrals are free."** They are unpriced in this file, which is different.

## Verifying this yourself

```bash
python3 scripts/roi.py --test
```

The four synthetic datasets were generated with known patterns, and the suite checks the engine finds them in each: the cheap channel is cheapest per application, converts worst, needs the most applications per start and keeps the fewest at 30 days; referral and career site are partial cost and never ranked; nothing is explained by mix, because source was drawn independently of role and site; spend and volume peak in the same months, so no saturation claim is made without the season caveat. The break-even is checked from both sides: 10% under it the cheap channel stays first, 10% over it does not. A channel deliberately bought for the hardest role must be caught as explained by mix. Label variants, a missing channel, a missing month and a 40% volume gap must each be reported; name and email columns, thin files, duplicate ids and bad spend must be refused.

## Works with

- **Any ATS that exports one row per application, and any spend report by month and channel.** The default; nothing needs connecting.
- **`funnel-drop-off-analyst`** in this library reads the same export for where candidates are lost.
- **The Fountain Cue MCP.** When connected, it can supply pipeline and spend for the current month, so the cost per start updates as spend lands rather than once a quarter. Fountain publishes this skill and sells Cue. The engine and the numbers are identical either way, and the skill works completely without it.

## Where this stops

This reads two files you exported, so it describes months that have closed and changes nothing. It cannot see current bids, pause a campaign, move budget, or tell you whether a move you already made worked: you would export again and re-run. It cannot price what the spend file leaves out (referral bonuses, agency fees, check fees, recruiter time) beyond the screening cost you give it. And source labels are last touch: no file can show how much of a free channel's demand a paid channel created.
