# Check-In Designer

> Writes the day 1, day 7 and day 30 check-ins that catch a new hourly hire before they quit, each under three minutes, with every answer routed somewhere, and checks the plan before anyone runs it.

Created with Adam Hickman. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The plan:** three short conversations, each answering a different question. Day 1: did the basics happen? Day 7: is the job what they were told? Day 30: did the first pay and the promises hold? Each comes with who asks and who covers, the probes, and an escalation table that sorts every answer into act within 24 hours, this week, log the theme, or the grievance route.

**The check:** `scripts/checkins.py --plan` enforces the rubric in code. Day 1, 7 and 30 all present; four to six questions each, twenty words or fewer; under three minutes read aloud with answers; an owner and a different fallback; day 30 not owned by the day-7 supervisor; kit, next shift, breaks, pay and safety all routed to act within 24 hours; conduct routed out to the grievance owner, never logged; pay and safety never only logged; every fix one the site can make without permission; a reply to the worker within seven days; no question about health, family, age, religion or where someone is from.

**The log:** once it runs, one line per check-in. `scripts/checkins.py --log` shows completion by site and touchpoint, escalations past their deadline, sites that answer urgent items late, answers that were logged when they needed a response, and the top themes.

## Why it exists

New hourly hires decide to leave early, often over things a site could have fixed in a day: boots that don't fit, a schedule nobody sent, a shift that moved and broke the bus trip. Check-in programmes exist to catch that, and most die within a quarter, either because the script is too long to run on a shift or because what comes back goes nowhere.

On the sample, three months at five sites: one site runs fewer than one in five day-7 check-ins, one answers its urgent items late four times out of five, one has a "no buddy on nights" item open for eight weeks, and one logged a shift lead yelling at new hires as a theme instead of handing it to HR.

## Install

**1. Download** [check-in-designer.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/check-in-designer.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the check-in demo."* Then: *"Design day 1, 7 and 30 check-ins for our warehouse associates"*, or *"Here's our check-in log, what does it say?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/retaining/check-in-designer ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | High first-month attrition, a shift lead on every shift who can fix kit and schedules. |
| Quick-service restaurants | Strong | New crew decide in the first two weeks; shift managers can ask at the end of a shift. |
| Logistics and delivery (W2) | Strong | Nights, PPE and the trip in are the usual early reasons to leave, and all are fixable on site. |
| Gig and courier marketplaces | Limited | No shift lead and no first shift in the same sense. The day-7 and day-30 questions adapt to an in-app message; the owner rules do not. |

US practice. Not legal advice.

## Verifying this yourself

```bash
python3 scripts/checkins.py --test
```

The sample plan must pass clean. 27 broken copies of it must each fail for the one named reason (no day 7, seven questions, too long to say aloud, one question over a breath, two questions in one, the fallback is the owner, day 30 owned by the day-7 supervisor, a question about kids, health in a probe, "where are you from", conduct logged as a theme, pay only logged, safety or kit not urgent, an answer routed nowhere, a fix the site can't authorise, no "declined" line, a reply in fourteen days, no grievance owner) or be refused for their shape. 21 risky phrasings must be caught ("Is ur daycare ok with these hours?", "Does your partner drive you in?") and 16 job questions must not ("Did a customer's kids get in your way?", "Do you know where the family restroom is?"). The sample log's planted problems must come back exactly, small sites must never be judged, check-ins inside their grace period must not count as missed, and malformed logs must be refused rather than crash. Before release, 8,000 randomly broken plans and logs ran without a crash.

Exit codes: 0 plan ready or log read, 1 plan not ready, 3 input refused, 4 the checker itself failed.

## Who it's for

- **HR and onboarding leads** who want a first-month programme sites actually keep running.
- **Site and store managers** who lose people in week one and want to know why before the exit interview.
- **Operations leaders** who want one number per site: did the day-7 check-in happen?
