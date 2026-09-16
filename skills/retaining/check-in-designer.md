---
name: check-in-designer
description: Writes day 1, day 7 and day 30 check-in scripts for new hourly hires, with escalation rules for whatever comes back.
---

# Check-In Designer

## What this does

Builds the three short conversations that catch a new hire before they quit, and the rules for what happens to the answers. Most check-in programmes fail for one of two reasons: the script is too long to run on a shift, or something comes back and nobody has to do anything about it. This designs against both. The check-ins are under three minutes each, and every possible answer routes to either an action, an escalation or a logged theme.

## What to give me

- **The role and the shift patterns** people are hired onto, including whether new hires get nights or weekends in their first month. *Essential.*
- **Who is on shift with the new hire** at each point — supervisor, shift lead, buddy, nobody. This determines who can realistically ask. *Essential.*
- **What a site can fix without permission**: shift swaps, start times, break timing, kit, locker, PPE size, parking, transport help. *Essential — an escalation rule pointing at something nobody can authorise is decoration.*
- **Your 30-day attrition, and the day it spikes**, if you know it. It moves where I put the second check-in.
- **Any existing onboarding steps** in the first month, so the check-ins attach to something already in the calendar rather than becoming a fourth thing to remember.
- **Who the escalation goes to**, by role, and whether that person's inbox is actually read on a shift day.

## How I work

**Three touchpoints, because they answer three different questions.** They are not the same conversation repeated, and the reason each exists determines its script.

**Day 1, at the end of the first shift.** The question is whether the basics happened. Did anyone expect you, did you have kit that fits, do you know where to be tomorrow and at what time, did you get a break, do you know who to call if you can't make it. This is a checklist read aloud, not an exploration of how they're feeling — the failures at day 1 are logistical and binary, and a worker on their first day has no basis for an opinion about anything else. Two minutes.

**Day 7, after the first full week.** The question is whether the job matches what they were told. They have now worked the real pace, the real rota and the real journey. So: is the work what you expected, is the schedule what you agreed, how is the journey in, has anything happened that you didn't know how to handle. Day 7 is where preview mismatch surfaces and where it is still cheap to fix, because a shift can be changed before it becomes a pattern of lateness. Three minutes.

**Day 30, after the first pay.** The question is whether they intend to stay, and whether the first month's promises held. Pay correct, hours as expected, anything still outstanding from days 1 and 7, what would make the next month better, and one forward-looking question about hours they want more or less of. This is the one that overlaps with a stay interview, and if you run `stay-interview-kit` from this library, day 30 is where the two join up. Three minutes.

**Under three minutes, or it won't happen.** This is the second thing I'll push back on, and it is not a style preference. A ten-question check-in given to a supervisor with 30 direct reports during a delivery window does not get run late — it gets run for the first four hires, then skipped, then quietly dropped, and you find out six months later when someone asks for the data. So each script is four to six questions, closed or near-closed, phrasable in one breath, with the follow-up probes listed separately for the interviewer who has time. If you want more depth, add a touchpoint, don't lengthen one.

**Who does it.** Day 1 belongs to whoever is on shift and senior enough to fix something — often the shift lead, not the manager. Day 7 belongs to the supervisor. Day 30 belongs to the supervisor's manager or a neighbouring site lead, because by day 30 the supervisor is one of the things worth asking about. I'll name a fallback for each, since in frontline reality the named person is off sick a third of the time, and a check-in with no fallback is a check-in that doesn't happen.

**Escalation rules, written as rules.** Every question has answers pre-sorted into three tiers, so the person asking never has to judge:

- **Act within 24 hours** — no kit or wrong-size PPE, no rota for next week, pay wrong or missing, no break taken, doesn't know their next shift, a safety concern, any allegation about a person's conduct, journey now impossible because the shift changed. These are named answer-by-answer, not left to interpretation.
- **This week, by the site lead** — shift preference conflicts, training gaps, buddy not available, small friction that recurs.
- **Log the theme** — anything that is a pattern question rather than an individual one, aggregated monthly. Nothing else gets logged-and-forgotten; if it is not in this tier it needs a response.

Anything alleging conduct or discrimination leaves the check-in process entirely and goes to your grievance route with a named owner. It is not a theme to aggregate.

**Closing the loop, with a deadline.** Every escalated item gets a response back to the worker inside seven days, including the ones you refuse. A check-in that raises something and returns nothing teaches a new hire in their first week that saying something is pointless, which is a worse position than never having asked. So the pack includes the three sentences to say back — done, in progress, not possible and why — and the rule that whoever asked the question owns the answer.

## What you get

**1. Three scripts**, each on one phone screen: opening line, questions in order, closing line, time budget.

**2. Follow-up probes** per question, for the interviewer with a spare minute.

**3. Owner and fallback** for each touchpoint, plus where in the shift it fits.

**4. The escalation table** — every anticipated answer sorted into 24-hour, this-week, or log, with the recipient named.

**5. Close-the-loop scripts** for done, in progress and declined.

**6. A one-line capture format** a supervisor can complete on a phone in under 30 seconds, and what to aggregate from it monthly.

**7. What not to ask** — the health, caring-responsibility and immigration-adjacent phrasings that friendly small talk routes into, with safe alternatives.

## Making it survive month three

Check-in programmes decay predictably. Two things slow it down. First, completion is visible: whoever owns onboarding should be able to say, per site, how many day-7 check-ins happened out of how many eligible hires. A site at 20% completion is not a check-in problem, it is a staffing or span-of-control problem, and lengthening the script will not fix it. Second, the escalation tier has to be seen working at least once. The fastest way to kill the programme is a supervisor escalating a wrong-size safety boot and hearing nothing for two weeks.

If you cannot resource all three, keep day 7. Day 1 failures usually show up anyway; day 7 is the one nobody else catches.

## Where this stops

This writes the scripts, the owners and the rules. It cannot run a check-in, cannot see who is at day 7 today, and cannot make an escalation get answered — the escalation table is only as real as the person on the receiving end. It also cannot tell you whether the check-ins you ran last quarter changed your retention, because that requires comparing hires who got them against hires who didn't, and only your own records hold that.
