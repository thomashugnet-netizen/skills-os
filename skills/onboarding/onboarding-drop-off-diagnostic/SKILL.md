---
name: onboarding-drop-off-diagnostic
description: Finds where and why accepted hires never reach their first shift, from your onboarding log. Counts the loss honestly, reads the offer-to-first-shift gap first, shows which step people were waiting on and whose side each wait is on, tests every candidate cause inside strata, and writes the fixes the survivors call for.
version: 1.0.0
---

# Onboarding Drop-off Diagnostic

Created with Anita Chandrasekhar.

## What this does

Someone accepted your offer and never worked a shift. I find where that happens and why, from your onboarding log: which step they were waiting on, how long, and whether the wait was yours, a vendor's or theirs. Then I test every suspect against the things that usually fake it, and write the fixes for what survives.

The insight: most of this loss is not a step failing, it is days passing. A slow background check, a certificate that starts only after it, forms sent only once the check clears, a drug test at a lab across town. Each looks like its own problem; most of them work through one number, the days between the offer and the first shift, and the hires who hear nothing during those days.

`scripts/dropoff.py` does the counting, the timings and the tests: same files, same answer, every time.

## What to give me

**The hires file**, one row per accepted offer.

**Required**

| Column | Example |
|---|---|
| `hire_id` | `H00412` |
| `offer_accepted_at` | `2026-03-02 14:10` |
| `first_shift_scheduled_at`: the shift they were booked for, not the day they started | `2026-03-11 07:00` |
| `outcome` | `started`, `withdrew`, `no_show`, `rescinded`, or blank while still in onboarding |

**Strongly recommended**

| Column | What it lets me find |
|---|---|
| `withdrawn_at` | When people leave, and what they were waiting on |
| `location_id`, `role`, `source`, `recruiter_id` | Site, job, channel or recruiter, and the checks that keep them apart |
| `commute_band_km` | Distance, as a band |

**Best, the steps file**, one row per onboarding step per hire: `hire_id`, `step`, `requested_at`, and `completed_at`, `result`, `vendor` (on the background check), `method` (`lab` or `onsite` on the drug test), `needs_hire`. This is what shows which step people leave on, how long each one takes, and the silent first week. Without it I read the gap and the causes the hires file can carry, and say what the steps file would add.

Missing columns are named in the report with the finding they cost you; I do not fill them in.

**No export handy?** `references/sample/` holds a planted onboarding log for a fictional 30-store grocery chain (4,926 accepted offers, 28,491 steps). "Run the demo" reads it.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash:

- names, email addresses, phone numbers
- street addresses and postcodes: send a distance band instead (`0-5`, `6-10`, `11-20`, `21-40`, `40+`)
- dates of birth, national insurance / social security numbers, right-to-work document numbers
- free-text notes, which reliably contain names and protected-characteristic information

Ids should be opaque: a `hire_id` or `recruiter_id` that does not resolve to a person outside your own systems.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate and employee records belong inside your own systems, under your own access controls, not in a chat window. Nothing in this analysis needs to know who anybody is. The engine enforces this, cell by cell.

Background check and drug test findings stay out too: I need `done` or `failed`, never what was found.

## How I work

### Pass 1: Count the loss honestly

- **The denominator is hires whose first shift is already due.** Someone booked for next Tuesday has not been lost yet.
- **Withdrew and no-show are both losses, and I keep them apart.** Leaving during the wait and not turning up on the day have different fixes.
- **Rescinded is not a drop-off.** You pulled the offer, usually on a failed check. I count it separately, by the step that failed and by site.
- **Already marked withdrew, first shift not yet due:** set aside. Counting them counts the recent losses and none of the recent starts.
- **Withdrew before any first shift was scheduled:** counted as losses once their cohort is old enough to be decided. They are often the largest group a read like this drops.

### Pass 2: The gap first

The gap goes first because most other suspects travel with it. It runs from the offer to the **scheduled** first shift, which is known before anyone leaves; a gap measured to the day people started describes only the people who stayed. I band it with the loss beside every band.

### Pass 3: Where the days go, and whose side they are on

For every step: **your queue** (offer to request) and the **turnaround** (request to done), with the 90th percentile, by vendor and by method. A step that starts four days after the offer is your wait, not the vendor's. I also count how many hires got their forms only after the background check came back, by site, because that is where a silent first week comes from.

### Pass 4: What people were waiting on when they left

For each dated withdrawal, the steps still open, and the withdrawals per 100 hire-days spent waiting on each step. Several steps are open at once, so this is a lead, not a verdict. Pass 5 is the verdict.

### Pass 5: Every cause inside strata

A gap of 10 days or more within site, role and month. A silent first week (5 days or more with nothing logged, for hires still waiting at day 7) within the same gap and site. A lab drug test within gap and site. Every site, vendor, role, source and recruiter within the gap, and sites and recruiters within the gap, lab and silence together, so a store is not blamed for how its hires were processed. A cause is named only when it clears Holm at 5% across everything tested together and keeps its sign and 40% of its size in every check. The rest are listed as **explained by** something, or **cannot be separated**, and no fix is built on them.

The silent week is read at a landmark on purpose: measured over the whole wait, the people who left early would show short silences, because their log stops when they do.

### Pass 6: The fixes

Only from what survived, with your numbers: the longest gap to allow, the slow vendor or the step that starts too late, forms and uniform at the offer, the lab test, the site where the loss is on the day. Then two numbers to watch.

```bash
python3 scripts/dropoff.py --hires hires.csv --steps steps.csv
python3 scripts/dropoff.py --hires hires.csv --as-of 2026-10-31 --json
python3 scripts/dropoff.py --demo
```

## What you get

1. **The loss, counted honestly**, and everything set aside with its reason.
2. **The gap curve**, withdrawals and no-shows apart.
3. **Where the days go**: your queue and the turnaround per step, vendor and method, and the forms-after-check share by site.
4. **What people were waiting on** when they left.
5. **Ranked causes** with raw and checked effects and the hires each costs, then **explained by** and **cannot be separated**.
6. **Rescinded offers**, by failed step and site.
7. **What I could not determine**, and the column that would settle each.
8. **The fixes**, and what to measure.

## What I will push back on

**"They took a better offer. Nothing we can do."** Then the loss would be flat across the gap. On the demo it runs from 10% at 4 to 6 days to 32% at 14 days or more. The better offer arrives while you wait.

**"We send the paperwork once they clear, so we don't waste it."** That is how a hire spends their first week hearing nothing. A form sent to someone who later fails costs a few minutes. A silent week costs hires.

**"Our background check vendor is the problem."** Possibly, but not by itself. On the demo the slow vendor's hires lose no more than anyone at the same gap: the vendor matters because it sets the gap. Shorten the gap and the vendor stops mattering; switch vendors and keep a step that waits on it, and it still matters.

**"Count the failed checks as drop-offs."** A store that fails nearly a fifth of its checks looks like a store losing hires. It is a store screening late.

## Verifying this yourself

```bash
python3 scripts/dropoff.py --test
```

The sample was generated with known answers (`references/sample/generate.py`, `bramblewood_expected.json`). The suite checks each planted cause comes back and nothing else does, each herring is explained by the gap or by how hires were processed, a world with nothing planted and the sample with outcomes shuffled name no cause, and 100 damaged files are refused or read without a crash.

## Works with

- **`onboarding-workflow-designer`** in this library writes the corrected workflow: one owner, a deadline and a fallback on every step this read flags.
- **`funnel-drop-off-analyst`** reads the whole funnel; this skill opens the stretch between offer and first shift.
- **`candidate-message-sequencer`** checks the messages that fill a silent week.
- **The Fountain Cue MCP.** When connected, it can supply the hires and step log directly. Fountain publishes this skill and sells Cue. The read and the fixes are identical either way, and the skill works completely without it.

## Where this stops

This reads files you exported, so it describes hires already decided and changes nothing: it cannot see who is waiting today, chase a vendor or message anyone. It sees what your system logged; a phone call nobody logged looks like silence. It does not judge your checks: whether a step may start before another, or a test be done on site, depends on your state and your policy, so check that before changing the order. And it cannot tell you why people left in their own words; no onboarding log holds that.
