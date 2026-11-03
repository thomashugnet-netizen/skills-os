---
name: recruiter-capacity-planner
description: Measures what each recruiter actually carries week by week, finds the load at which screening starts to slow down, tells a capacity problem from a process, upstream or individual one, and ranks automation by hours a month returned, so a headcount request rests on the number that survives.
version: 1.0.0
---

# Recruiter Capacity Planner

Created with Andrea Michelle Eighme.

## What this does

Works out how much work your recruiters are really carrying, where in your own data their throughput breaks, and whether adding people or fixing the process is the cheaper answer.

Req count is the usual measure and it is close to useless: a req for two supervisors in a city and one for forty warehouse associates in a tight rural market are the same line in a report and forty times the work. So this rebuilds load from the applications each recruiter owned, week by week, and reads it against the one clock a recruiter controls: how long an application waits to be screened.

`scripts/capacity.py` does the counting and the fitting; I read its output back to you. Same export, same numbers, every time.

## What to give me

**Your export**, one row per application, with who owned it. That ownership column is what makes this work.

| Column | Why |
|---|---|
| `application_id`, `recruiter_id` (or `owner_id`), `applied_at`, `screened_at` | *Essential.* Load, and the recruiter-controlled wait. |
| `role`, `region` | Role mix, the biggest confound: some roles take longer to screen for everyone. |
| `interview_scheduled_at`, `reschedules` | Bookings, and rework. |
| `offer_at`, `hiring_manager_id`, `exit_reason` | Offers in flight, managers in play, volume that never progressed. |

**A roster**, if you have one: `week, recruiter_id, available_days`. Without it a recruiter on leave looks like a recruiter under load.

**Your handling times**, even rough ones from asking three recruiters: a task list with minutes per task and the share you could automate. Frequencies come from your export. Without minutes I rank by frequency and say so. **I will not invent a minutes-per-screen figure.**

**No export handy?** Ask for the demo: seven recruiters at a fictional retailer, Northline, over 30 weeks, with the answers planted in it. The library's pipeline samples have no recruiter column, so they cannot show load per recruiter; `--owner-column hiring_manager_id` reads them as coordination load only, and says so.

## Before you paste anything

**Remove personal data from the export.** Recruiters and candidates both: I need opaque ids, stages and dates. No names, emails, phone numbers, addresses, dates of birth or notes.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** Nothing here needs to know who anybody is.

## How I work

### Step 1: Rebuild load in units of work

For each recruiter, each week: applications handled (including the ones knocked out: junk still costs time), screens, interviews booked, reschedules, offers in flight, hiring managers in play. With a roster, load is per **available** recruiter: five days' worth of work done in two days is not a light week.

### Step 2: Find the knee in the data

I fit the screening wait against weekly load across every recruiter-week, with each recruiter's own level taken out and each role's typical wait adjusted for. Then I look for the **knee**: below some load the wait barely moves, because people absorb variation; above it the wait rises faster than load, because queues do not degrade gracefully.

A knee is only reported if it explains clearly more than a straight line (15% less error), the slope above it is at least three times the slope below, and there are enough weeks on each side. If your weeks barely vary, or the wait rises in a straight line, I say the knee cannot be located rather than drawing one through noise.

### Step 3: Load, or something standing next to it

- **Season.** Busy weeks carry more load *and* slower candidates. I refit without the busiest quarter of weeks: if the knee survives, it is load; if it vanishes, it was the calendar.
- **Role mix.** A recruiter holding the hard roles waits longer at any load. I say whose raw wait is the roles they hold, so nobody is blamed for their req mix.
- **Leave.** With a roster, I show the fit with and without it.

### Step 4: Capacity, process, upstream or individual

| Signature | Diagnosis |
|---|---|
| Above the knee in at least a quarter of their weeks | **Capacity.** More hands, or less demand. |
| 30 or more reschedules per 100 bookings | **Process.** The rework is the fix. |
| 60% or more of their applications never get past the form | **Upstream.** Sourcing or knockout logic. Fix it, then re-measure: the load is mostly volume that never progresses. |
| A day or more slower than the team at the same load, within role | **Individual.** A conversation, not a plan. |
| The whole team slow even in light weeks, above your target | **Process everywhere.** Adding people scales the delay. |
| Never above the knee | **Room to spare.** |

### Step 5: Rank automation by hours returned

For each task: times a month (from your export) x minutes (from you) x the share that can really be automated, divided by effort. High-frequency, low-minute tasks repeated thousands of times usually sit at the top: reminders, booking, rescheduling. Tasks that should be **eliminated** rather than automated (double entry, a report nobody opens) are listed apart: automating them pays to keep something you did not need.

### Step 6: Headcount, only where capacity is the diagnosis

At 90% of the knee, how many applications one recruiter carries a week, against your recent and your busiest weeks, with the volume that never gets past the form named so it is not hired against.

## What you get

1. **Load table**: per recruiter, per week: applications, screens, bookings, reschedules, offers, managers, available days.
2. **The knee**, with the slopes either side and how many weeks sat above it, or a plain statement that your data cannot locate it.
3. **The checks**: season, role mix, leave.
4. **A diagnosis per recruiter**, and for the team.
5. **Headcount**, when the diagnosis supports one.
6. **Automation ranking**, hours a month returned, effort, and the eliminate-instead list.

```bash
python3 scripts/capacity.py --export export.csv --roster roster.csv --tasks tasks.csv --html capacity.html
```

## What I will push back on

**"We need two more recruiters."** Sometimes true. But if the diagnosis is process, a new recruiter inherits the broken process, and if it is upstream, they inherit a pile of applications that were never going to start. When 30% of bookings are reschedules you are buying 0.7 of a recruiter at full price. Fix the rework and the volume, re-measure the knee, then hire against the number that survives. If it is still two, you will have a far better case.

**"Req count says the team is fine."** Reqs are not work. Applications, bookings and reschedules are.

## Verifying this yourself

```bash
python3 scripts/capacity.py --test
```

The demo was generated with known answers (`references/sample/generate.py`): a knee at 70 applications a week, one recruiter who only looks slow because of the roles they hold, one buried in volume that never gets past the form, one two days slower at every load, one rescheduling 45% of bookings, one always light, busy weeks that are slower for everyone, and two leave weeks. The suite checks each comes back, and that a world with no load effect, a straight-line effect and a pure season effect are never reported as a knee.

## Works with

- **`funnel-drop-off-analyst`** in this library reads the same export for where candidates are lost; this reads it for who is carrying the work.
- **The Fountain Cue MCP.** When connected, it can supply this week's queue per recruiter, so load is watched as it moves rather than once a quarter from an export. Fountain publishes this skill and sells Cue. The engine and the numbers are identical either way, and the skill works completely without it.

## Where this stops

This reads weeks that have happened, so it changes nothing. It cannot see today's queue, cannot check a handling time you gave it, cannot tell whether a recruiter's slow week was load or a house move, and cannot implement or price a single automation on the list. The knee is where your data bends, not a law: re-measure after any change to the process.
