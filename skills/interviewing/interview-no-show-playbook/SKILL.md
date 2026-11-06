---
name: interview-no-show-playbook
description: Diagnoses why booked interviews get missed from your booking log or pipeline export, testing every candidate cause inside strata, then writes the slot rules, the confirm, remind and re-offer text sequence and the reschedule path that fix it, and checks the sequence before you send it.
version: 1.0.0
---

# Interview No-Show Playbook

Created with Courtney Barabas-Esperance.

## What this does

Half diagnosis, half playbook. I read your bookings to find why interviews get missed, which is usually the calendar rather than the candidate: the wait between booking and interview, a weekend of silence inside it, one slot instead of a choice, a store that interviews on Tuesdays only. Then I write the slot rules, the text sequence and the reschedule path for the pattern I found, and check every message before you send it. A generic reminder cadence fixes a small part of this; knowing which cause is yours fixes most of it.

`scripts/noshow.py` does the counting, the tests and the check: same file, same answer, every time.

## What to give me

**Best: a booking log**, one row per booked interview, including the ones rebooked after a miss.

**Required**

| Column | Example |
|---|---|
| `application_id` | `APP-004182` |
| `booked_at`: when the slot was booked | `2026-03-02 17:15` |
| `interview_at`: when the interview was due | `2026-03-04 12:30` |
| `outcome` | `attended`, `no_show`, `cancelled`, `rescheduled`, `employer_cancelled`, or blank if still upcoming |

**Strongly recommended**

| Column | What it lets me find |
|---|---|
| Times, not only dates, on both (store's local time) | Slots by hour, and how fast a miss gets rebooked |
| `location_id`, `role`, `hiring_manager_id`, `source` | Site, job, interviewer or channel, and the checks that keep them apart |
| `slots_offered` | Whether one slot instead of a choice costs shows |
| `mode` (`self` or `recruiter`) | Whether self-scheduling helps once the wait is equal |
| `format` (`in_person`, `video`, `phone`) | Where the miss is a journey and where it is a link |
| `confirmed`: the reply to the 24-hour reminder | Whether a missing reply flags the miss a day ahead |
| `commute_band_km` | Distance, as a band |

Missing columns are named in the report with the finding they cost you; I do not fill them in.

**Or a pipeline export**, one row per application (`application_id`, `interview_scheduled_at`, `stage_reached`, `exit_reason`). It counts the misses and who never got a slot, but not the wait: a missed interview has no interview date there, and a wait measured on completed interviews describes only the people who came. Add `interview_at` and it can.

**For the playbook:** the company, the role, where to go by landmark and door, who to ask for, how long it takes, what to bring, one number to call. I write them into `facts.json` (shape: `references/sample/fernhill_facts.json`) and never invent one.

**No export handy?** `frontline_pipeline_sample.csv` ships in `data/`, and `references/sample/fernhill_bookings.csv` is a planted booking log for a fictional 24-store apparel retailer. "Run the demo" reads it.

## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash:

- names, email addresses, phone numbers
- street addresses and postcodes: send a distance band instead (`0-5`, `6-10`, `11-20`, `21-40`, `40+`)
- dates of birth, national insurance / social security numbers, right-to-work document numbers
- free-text notes, which reliably contain names and protected-characteristic information

Ids should be opaque: an `application_id` or `hiring_manager_id` that does not resolve to a person outside your own systems.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate and employee records belong inside your own systems, under your own access controls, not in a chat window. Nothing in this analysis needs to know who anybody is. The engine enforces this, cell by cell.

## How I work

Five reading steps, then the writing, last on purpose: a sequence drafted before the diagnosis treats a slot problem as a memory problem.

### Step 1: Count the miss honestly

- **The denominator is booked interviews**, and employer cancellations are not the candidate's miss.
- **Cancelled or moved in advance is not a silent no-show.** A cancellation is information and a slot you can refill. If your export cannot separate them, I say the rate is combined.
- **Rebooked and attended is not a loss.** I also count per candidate, so a reschedule path that works shows up.
- **Never booked.** From a pipeline export, the candidates who cleared screening and never got a slot, by reason and by site. That group is often as large as the misses, and it is pure capacity.
- **Past interviews with no outcome** are named: unlogged misses flatter the rate.

### Step 2: The wait first, and the calendar behind it

The wait goes first because most other suspects travel with it. I band it (same day, 1, 2-3, 4-7, 8+ days) with volume beside every rate, then name the calendar behind it, site by site: interviews on one weekday only, one slot offered, one interviewer, busy weeks. Each site's miss rate is shown before and after the wait is equal, so a store with a calendar problem is not mistaken for a store with a people problem. A reminder cannot fix a wait. A slot rule can.

### Step 3: Every other suspect

A weekend inside the wait, the hour of the slot, one slot against a choice, self-scheduled against recruiter-booked, format, commute, and every site, interviewer, source and role.

### Step 4: Every cause inside strata

Each cause is tested against the confounds that usually fake it: the wait within site, role and week; the weekend within the same wait and site; an hour within role, wait and site; one slot within wait and site; self-scheduling within wait and role; a site within week and wait; an interviewer within their own site. A cause is named only when it clears the bar across everything tested together (Holm, 5%), keeps its sign and at least 40% of its size inside every check. Otherwise it is listed under **Explained by**, or **Cannot be separated** when the data has no contrast to test it, and no rule is built on it.

Causes are read on each candidate's first appointment; rebookings after a miss are step 5.

### Step 5: After a miss

For every first miss at least seven days old: rebooked or not, how fast, and whether they came. The log shows rebookings, not offers, and someone who answers within the hour was keener to begin with, so speed and interest are mixed. What it does prove is a site where no miss is ever rebooked: that is a rule, not candidate choice.

If you log the reply to the 24-hour reminder, I show how many misses a missing reply flagged a day ahead. That predicts; it does not prove the reminder works. That takes a holdout, sized from your volume.

### Step 6: Write the playbook, and check it

**Slot rules first**, only from what survived: a maximum wait, a second interview day where the calendar is the cause, two slots minimum, hours to stop offering, the weekend rule, the door for a store people cannot find, a refill rule for unconfirmed slots, more slots where nobody got one, no overbooking without walk-in capacity.

**Then the text sequence**, timed to your wait: a confirmation at booking (role, when, how long, landmark and door, who to ask for, what to bring, how to move it, STOP); a 48-hour touch only while waits run long; a 24-hour reminder with two reply options; a morning-of text with one number to call; a re-offer within the hour of a missed slot, with two slots; a second offer only if they reply; a close that keeps them eligible.

**The check blocks it** until every message names who is writing and carries its elements, fits two text messages (a curly apostrophe turns a text into Unicode and halves the room), asks nobody to log in and keeps its timing, and until the policy rebooks a first miss, closes after the second silent miss and keeps them eligible.

```bash
python3 scripts/noshow.py --log bookings.csv --playbook facts.json
python3 scripts/noshow.py --check messages.json
python3 scripts/noshow.py --demo
```

## What you get

1. **The miss, counted honestly**, per appointment and per candidate, plus the never-booked.
2. **The wait curve** and the calendar behind it.
3. **Slots and timing.**
4. **Ranked causes** with raw and checked effects and the interviews each costs, then **Explained by** and **Cannot be separated**.
5. **After a miss**, and the reply signal.
6. **What I could not determine**, and the column that would settle each.
7. **A measurement plan**: two numbers to watch, and the holdout size.
8. **The playbook**: slot rules with your numbers, the sequence word for word, the reschedule path, the check's verdict.

## What I will push back on

**"Reject anyone who no-shows."** The most common rule at this stage and close to the worst. You already paid for that candidate: the ad, the application, the screen, the booking. Most misses are logistics, a shift that moved, a bus that did not come, childcare that fell through, from people working elsewhere right now with the least control over their hours of anyone you hire. They are not a random sample, so rejecting at first miss is a fairness problem as well as a volume one. Instead: one re-offer within the hour with two slots, a second only if they reply, close after a second silent miss, keep them eligible. The check refuses a policy that rejects at the first miss.

**"Add another reminder."** Past three touches the returns are near zero, and you teach candidates to ignore you. Shorten the wait instead.

**"People just don't show up."** Then the rate would be flat across waits, slots and stores. It rarely is.

## Verifying this yourself

```bash
python3 scripts/noshow.py --test
```

The sample log was generated with known answers (`references/sample/generate.py`, `fernhill_expected.json`). The suite checks each planted cause comes back and nothing else does, each planted herring is explained by the right thing, a shuffled log and a world with nothing planted name no cause, and 30 damaged copies of the sample sequence are each blocked for the right reason.

## Works with

- **`phone-screen-script`** in this library books the interview this skill protects.
- **`candidate-message-sequencer`** checks any other candidate sequence you run.
- **The Fountain Cue MCP.** When connected, it can supply live bookings and send the sequence to whoever is booked. Fountain publishes this skill and sells Cue. The read, the rules and the sequence are identical either way, and the skill works completely without it.

## Where this stops

This reads a file you exported, so it describes interviews already held or missed and changes nothing: it cannot see who is booked tomorrow, send a message, open a slot or rebook anyone. A cause you do not record, such as a hard-to-find entrance or a manager who runs late, shows up only as a site or an interviewer that misses more. And whether you may text a candidate depends on the consent you collected and where you hire: check that before the first send.
