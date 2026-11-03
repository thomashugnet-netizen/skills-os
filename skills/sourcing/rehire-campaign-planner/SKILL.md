---
name: rehire-campaign-planner
description: Turns your own past applicants and former workers into a re-engagement campaign. Settles who you may contact first, sorts every record into a segment or a named reason it is out, sizes waves to the replies someone can actually answer, and checks the three messages before they go.
version: 1.0.0
---

# Rehire Campaign Planner

Created with Kristi Kennebrew.

## What this does

Builds a campaign against the cheapest supply a high-volume employer has and most reliably ignores: the people already in its own system. Someone who reached your interview stage five months ago has cleared the steps most new applicants fail, knows the shift pattern, and costs a message rather than a click.

The work is deciding which few thousand of your tens of thousands of records are worth contacting, and having somewhere for the replies to land. `scripts/rehire.py` does the sorting from your export; I read it back to you, write the messages and the reply playbook, and the same script checks the messages.

## What to give me

**Your export**, one row per application, opaque ids only. The library's pipeline samples work as they are.

| Column | Why |
|---|---|
| `application_id`, `stage_reached`, `exit_reason` | *Essential.* An interview drop-off and an abandoned form are not the same campaign, and a rejection on a background check is not the same as one on availability. |
| `location_id`, `role` | *Essential.* To match people to an opening near them. |
| Stage dates (`applied_at` at least) | Recency, and your retention period. |
| `separation_at`, `separation_reason` | Former workers, and whether they left in good standing. |
| `rehire_eligible`, `opted_out`, `person_id` | When you have them: an eligibility flag someone maintains, opt-outs, one message per person. |

**A short policy** (`references/sample/northline_policy.json` shows the shape): your retention period, whether your privacy notice covers contacting past applicants, former workers, and people about a *different* job (yes, no, or not decided), what you are hiring for now by site, role and shift, what has genuinely changed since they applied, and how many hours a day someone answers replies.

**A suppression list** if opt-outs live outside the export.

**No export handy?** Ask for the demo: 18,184 synthetic applications at 42 stores, with a policy for twelve of them.

## Before you paste anything

**Remove personal data from the export.** I need stages, reasons, sites and dates, never identities: no names, emails, phone numbers, addresses, dates of birth or notes. The contact list I produce carries application ids only, for you to join back inside your own system.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** Nothing in this plan needs to know who anybody is.

## How I work

### Step 1: Settle what you may send, before writing a word

This runs first because it can delete half the plan. **This is not legal advice**; it is the four questions to take to whoever owns data protection, and the plan follows their answers.

1. **What did they agree to?** An application creates a basis for messages about that application. Contacting the same person eight months later about a different job is a different purpose, and whether it is covered depends on your notice, not on how reasonable it feels.
2. **Is it inside your retention period?** Records past it are not a segment. They are a deletion job, and I count them as one.
3. **Which channel per person?** A number given to arrange an interview is not automatically consent to campaign texts.
4. **Is suppression checked at send time?** Not at build time: people opt out in between.

A question nobody has answered is `null` in the policy, and that group is **blocked**, not contacted. The demo shows it: nobody has decided whether Northline may write to people about a different job, so 3,821 records wait for that decision.

### Step 2: Build the pool from stage and reason, not from the database

Every record lands in exactly one place, and the report names where.

**In:**
- **Reached interview or beyond, never started.** Highest yield: assessed, wanted it once, stopped by something specific.
- **Screened, then dropped.** Including the ones *you* dropped: no interview slot offered, a recruiter who never followed up, a check that took too long. Those get their own count, and the message leads with it.
- **Former workers who left in good standing**: voluntary quits, found another job, schedule conflict. Small, and disproportionately valuable.
- **Rejected against a requirement of a different job**: knocked out on availability, a knockout question, a vehicle check. Offered a *different* role near them, or the same role if the pattern they were rejected against has changed.

**Out for good:** background, drug-screen, medical-certificate, document and right-to-work outcomes; involuntary and attendance exits; anyone flagged not eligible for rehire; opt-outs.
**Out for now:** past retention; still working for you; never got past the form; no opening near them; a purpose not yet decided; a reason code nobody can read. I never guess at a free-text reason.

### Step 3: Segment on group and recency

Recency bands: 0-3 months, 4-6, 7-12, 13+ if retention allows. Recency changes the message: at three months you pick up where they left off; at twelve you are reintroducing the job. A segment under 25 people is folded into the next band rather than given its own messages.

### Step 4: The arc, three messages over three days

- **Day 0, mid-morning (late afternoon for night workers).** Who is writing, why ("you applied in March and got as far as an interview"), what is open at which site, one tap to a slot. **Never re-apply**: making someone who reached your offer stage fill in the form again is the most common way this fails.
- **Day 1, a different time of day.** The news: the rate, the pattern, the closer site, the step you removed. One line.
- **Day 3, late afternoon.** Marked as the last message. Ending cleanly earns the right to run it again next quarter.

Every message carries an opt-out and names the sender. Send windows follow the shift each person would work: messaging a night-shift population at 9am reaches them asleep.

`scripts/rehire.py --messages messages.json` checks this: three messages on days 0, 1 and 3; an opt-out and the sender in each; the reason on day 0; news on day 1; "last message" on day 3; no "re-apply"; only merge fields the send tool fills (a `[SITE]` left in goes to two thousand people); under two text segments.

### Step 5: Size the waves to the replies

Replies arrive in a burst within hours of each send. The waves are sized so the expected replies in each four-day arc fit the hours someone has to answer them, highest-yield segments first, a first wave of a few hundred. Reply rates are stated assumptions in `references/taxonomy.json`: replace them with yours after wave 1.

## What you get

1. **Who is in and who is out**, every record accounted for, with the reason.
2. **The segment table**: size, assumed reply rate, expected replies, shift mix.
3. **Send windows** by shift pattern, and **waves** sized to your reply capacity.
4. **The contact list** (`--list-out`): application id, segment, wave, site, roles on offer. Ids only.
5. **The messages**, three per segment, checked.
6. **The reply playbook**: interested goes straight to a slot, questions get one line, stop is suppressed the same day, and an answer ready for "I already took another job".
7. **Measurement**: reply, booked and started rates per segment at day 7 and day 30, and the opt-out rate, which decides whether you run it again.

```bash
python3 scripts/rehire.py --pool export.csv --policy policy.json --list-out contactable.csv --html plan.html
python3 scripts/rehire.py --messages messages.json --policy policy.json
```

## What it costs you to run

Counted by the engine from your own export. On the demo (42 stores, 18,184 records, openings at 12 sites, 3 hours a day answering replies):

- **Once:** 8 segments, 24 messages to write and approve, 8 canned replies, the open roles, pattern and rate confirmed at 12 sites (about 36 minutes).
- **Every run:** about 165 replies at 3 minutes each, roughly 8 hours, most of it in the 48 hours after each send, across 2 waves; 15 to 46 opt-outs to record before the next wave.
- **Every month:** about 149 people became contactable in the last 30 days. Run it monthly and each wave is smaller and better aimed. Run it once and you harvest the backlog and leave the supply on the floor.

## What I will push back on

- **"Just message everyone in the database."** It spends the goodwill of your whole history in an afternoon to reach the few percent worth reaching, contacts people you rejected for reasons that have not changed, and buries the late-stage drop-offs under a pile nobody can answer.
- **"They were rejected, so they are not eligible."** A knockout on a pattern you no longer run is not a judgement about the person. A background-check outcome is, and stays out. Separating the two is the work, which is why I need reason codes.
- **A campaign with no news in it.** It asks people to change their minds for no reason.

## Works with

- **`candidate-message-sequencer`** in this library, when it ships, writes longer sequences for new applicants; this one is three messages to people you already know.
- **The Fountain Cue MCP.** When connected, it can size the pool from your live account and build the segments without an export, which matters if you run this monthly. Fountain publishes this skill and sells Cue. The rules, the segments and the messages are identical either way, and the skill works completely without it.

## Where this stops

This sorts an export and writes and checks the campaign. It cannot see your system, check a consent record, verify that a rehire flag still means what someone once said it meant, or send a message. It cannot tell you whether your retention policy allows a segment: that is for whoever owns data protection, and the plan waits for their answer rather than writing around it. The reply rates are assumptions until your first wave replaces them.
