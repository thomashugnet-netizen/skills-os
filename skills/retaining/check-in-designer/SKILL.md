---
name: check-in-designer
description: Writes the day 1, day 7 and day 30 check-ins that catch a new hourly hire before they quit, each under three minutes, with every possible answer routed to an action, an escalation or a logged theme, and checks the plan in code before anyone runs it. Then reads the one-line log supervisors keep to show which sites are not running them and which answers nobody acted on.
version: 1.0.0
---

# Check-In Designer

Created with Adam Hickman.

## What this does

Builds the three short conversations that catch a new hire before they quit, and the rules for what happens to the answers.

Most check-in programmes fail for one of two reasons: the script is too long to run on a shift, or something comes back and nobody has to do anything about it. This designs against both. Each check-in is under three minutes, read aloud with answers, and every answer goes somewhere: an action within 24 hours, a fix this week, a theme for the monthly review, or, for anything about someone's conduct, out of the check-in to your grievance route.

Two parts:

1. **The plan**, which I write and `scripts/checkins.py --plan` checks: the three scripts, who asks and who covers, the escalation table and the lines to say back.
2. **The log**, once it runs: one line per check-in, read by `scripts/checkins.py --log` to show completion by site, escalations that missed their deadline, and answers routed to the wrong place.

## What to give me

- **The role and the shift patterns** new hires start on, including whether they get nights or weekends in the first month. *Essential.*
- **Who is on shift with the new hire** at each point: supervisor, shift lead, buddy, nobody. That decides who can realistically ask. *Essential.*
- **What a site can fix without asking anyone**: shift swaps, start times, break timing, kit and PPE sizes, lockers, parking. *Essential: an escalation that points at something nobody on site can authorise is decoration, and the check refuses it.*
- **Who escalations go to**, by role, including who handles a complaint about someone's conduct, and whether their inbox is read on a shift day.
- **Your 30-day attrition and the day it spikes**, if you know it. It moves where day 7 sits.
- **Steps already in the first month**, so the check-ins attach to something already in the calendar.

**Nothing handy?** Ask for the demo: a plan for an overnight stocker at a fictional retailer, Northline, and three months of its check-in log across five sites, with problems planted in it.

## How I work

### Three touchpoints, three different questions

**Day 1, at the end of the first shift: did the basics happen?** Kit that fits, a break taken, knowing when the next shift is, who to call if they can't make it, anything unsafe. A checklist read aloud, not a conversation about feelings: day-1 failures are logistical and binary. Two minutes.

**Day 7, after the first full week: does the job match what they were told?** They have now worked the real pace, the real schedule, the real trip in. This is where a mismatch surfaces while it is still cheap to fix, before a changed shift becomes a pattern of lateness. Three minutes. **If you can only run one, keep day 7**: day-1 failures usually show up anyway, day 7 is the one nobody else catches.

**Day 30, after the first pay: will they stay, and did the promises hold?** Pay right, hours as expected, anything still open from days 1 and 7, more or fewer hours. Asked by the supervisor's manager or a neighbouring site lead, because by day 30 the supervisor is one of the things worth asking about. The check refuses a plan where day 30 has the same owner as day 7.

### Under three minutes, or it won't happen

Not a style preference. A ten-question check-in handed to a supervisor with thirty people during a delivery window gets run for the first four hires, then skipped, then dropped. So each script is four to six questions, closed or near-closed, each sayable in one breath (twenty words or fewer). The check times every script read aloud with answers and refuses anything over 180 seconds. Probes go in a separate line for the interviewer with a spare minute. If you want more depth, add a touchpoint, don't lengthen one.

### Every answer has a destination

Each question's possible answers are sorted in advance, so the person asking never has to judge:

- **Act within 24 hours**: no kit or the wrong size, no schedule, no break, pay wrong or missing, anything unsafe, a trip that no longer works because the shift changed. The check refuses a plan where any of kit, next shift, break, pay or safety is missing from this tier.
- **This week, by the site lead**: schedule conflicts, training gaps, no buddy, small friction that recurs.
- **Log the theme**: pattern questions, reviewed monthly. Pay and safety are never only logged; the check refuses it.
- **Grievance route**: anything about someone's conduct leaves the check-in, the same day, to a named owner. It is never a theme. The check refuses conduct routed anywhere else.

Every 24-hour and this-week route names who acts and the fix, and the fix must be on your list of things a site can do without permission, or "escalate".

### Close the loop within seven days

Every escalated answer gets a reply inside seven days, including the ones you refuse. A check-in that raises something and returns nothing teaches a new hire in week one that speaking up is pointless, which is worse than never asking. The plan carries the three lines to say back: done, in progress, not possible and why. Whoever asked owns the answer.

### What not to ask

Friendly first-week small talk drifts into health, children and caring, age, religion and where someone is from. The check reads every question and probe for those, about the worker (not a customer's kids or the prayer room), and gives the job-related question to ask instead.

## What you get

1. **Three scripts**, each on one phone screen: opening line, questions in order, closing line, time.
2. **Probes** per question, for the interviewer with a spare minute.
3. **Owner and fallback** for each touchpoint, and where in the shift it fits.
4. **The escalation table**: every anticipated answer, its tier, who acts, and the fix.
5. **Close-the-loop lines** for done, in progress and not possible.
6. **A one-line capture format** a supervisor fills on a phone in under 30 seconds.
7. **The check report**, and a printable sheet once the plan passes:

```bash
python3 scripts/checkins.py --plan plan.json --html checkins.html
```

## Once it is running: the log

One row per check-in due: `site,hire,touchpoint,due,done`, plus `tier,theme,raised,answered` when something came back. `hire` is an opaque id: files with names, emails or phone numbers are refused.

```bash
python3 scripts/checkins.py --log log.csv --html log.html
```

It shows:

- **Completion by site and touchpoint**, counting only check-ins past their grace period. A site whose day-7 completion stays below half even at the top of its 90% range is flagged as a staffing or span-of-control problem, not a script problem: a shorter script will not fix it. Under ten check-ins due, a site is not judged.
- **Escalations past their deadline**: 24 hours, seven days, still open.
- **Sites that answer their 24-hour items late** as a pattern (four or more raised, fewer than half on time).
- **Answers logged that should never be a theme**: conduct, pay, safety.
- **The top themes** for the monthly review.

## What I will push back on

- **"Let's add a few more questions."** Add a touchpoint instead. Length is what kills these.
- **"HR will run the check-ins."** Whoever is on shift and can fix something runs day 1. Someone who has never met the hire gets polite answers and fixes nothing.
- **"We'll log everything and review it monthly."** A wrong-size safety boot reviewed in a month is a hire lost in a week.
- **Escalations to a manager whose inbox isn't read on shift days.** The tier is only as real as the person receiving it.

## Works with

- **`stay-interview-kit`**, when it ships: day 30 is where the two join.
- **The Fountain Cue MCP.** When connected, it can list who reaches day 1, 7 and 30 each week and remind the owner. Fountain publishes this skill and sells Cue. The plan, the check and the log reader are identical either way, and the skill works completely without it.

## Where this stops

This writes the scripts, the owners and the rules, and checks them. It cannot run a check-in, cannot see who is at day 7 today unless you give it the log, and cannot make an escalation get answered. It cannot tell you whether check-ins changed who stayed: that needs hires who got them compared with hires who didn't, and sites that run check-ins well differ in other ways too. The question check matches phrasings in English; a risky question worded in a way it has not seen can pass, so treat it as a second pair of eyes.
