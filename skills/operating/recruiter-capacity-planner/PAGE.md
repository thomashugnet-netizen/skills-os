# Recruiter Capacity Planner: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/capacity.py --export references/sample/northline_recruiting.csv --roster references/sample/northline_roster.csv --tasks references/sample/northline_tasks.csv

## Example prompt

> Here's our last six months of applications with recruiter ids, plus the leave roster. Do we need more recruiters, or is something else going on?

## Example output

From the engine's run on the demo files (`references/sample/northline_*.csv`: seven recruiters, 30 weeks, 13,032 applications). An excerpt.

**The knee:** about 69 applications a week per available recruiter. Below it, the screening wait barely moves (+0.09 days per 10 more applications); above it, +0.65 days per 10. It holds without the busiest weeks, so it is load, not the calendar.

**Each recruiter**

| Recruiter | Diagnosis | Why |
|---|---|---|
| REC-01, REC-02, REC-03 | Capacity | Above the knee 10 to 13 weeks out of 30 |
| REC-04 | Upstream | 83% of their volume never gets past the form: fix sourcing or knockouts first |
| REC-05 | Individual | 1.8 days slower than the team at the same load, within role: a conversation, not a plan |
| REC-06 | Process | 59 reschedules per 100 bookings: the rework is the fix |
| REC-07 | Room to spare | Never above the knee |

**Headcount:** recent weeks average 562 applications, which needs 9 recruiters against 7 available. But about 53 applications a week never get past the form: fix that before hiring against it.

**Automation, ranked by hours a month returned per unit of effort:** interview reminders (42 h, small effort), booking by phone and text (56.7 h, medium), rescheduling (16.6 h, small). Two tasks should be eliminated, not automated: copying each hire into payroll by hand, and a monthly report nobody opens.
