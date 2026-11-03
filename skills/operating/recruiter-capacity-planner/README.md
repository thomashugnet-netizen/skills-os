# Recruiter Capacity Planner

> Finds the weekly load at which your recruiters start to slow down, tells capacity from process, upstream or individual problems, and ranks automation by hours a month returned.

Created with Andrea Michelle Eighme. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

From an export with who owned each application (and, if you have it, a leave roster and your own handling times):

- **Load per recruiter per week**: applications, screens, bookings, reschedules, offers, hiring managers in play, per available day
- **The knee**: the load above which the screening wait rises faster than load, fitted with each recruiter's own level and each role's typical wait taken out, or a plain "cannot be located"
- **Checks**: does the knee survive without the busiest weeks (season), whose raw wait is just the roles they hold (role mix), what leave does to the picture
- **A diagnosis per recruiter**: capacity, process (rework), upstream (volume that never progresses), individual, or room to spare
- **Headcount**, only where capacity is the diagnosis
- **Automation ranked by hours a month returned** per unit of effort, from your export's frequencies and your minutes, with an eliminate-instead list

## Why it exists

"We need two more recruiters" is usually argued from req counts, which measure nothing. On the demo, seven recruiters at a fictional retailer: the knee sits at about 69 applications a week per available recruiter; three recruiters are over it often enough to be a capacity problem, and one of them only looks slow because of the supervisor reqs they hold; a fourth is busy too but also about two days slower than everyone at the same load; one is buried in applications that never get past the form; one reschedules 59 of every 100 interviews. Hiring helps the first group only. The top automation is not the exciting one: interview reminders, 42 hours a month back for a small effort.

## Install

**1. Download** [recruiter-capacity-planner.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/recruiter-capacity-planner.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the recruiter capacity demo."* Then: *"Here's our last six months of applications with recruiter ids. Do we need more recruiters?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/operating/recruiter-capacity-planner ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | Columns | |
|---|---|---|
| export | `application_id, recruiter_id, applied_at, screened_at` + `role, region, interview_scheduled_at, reschedules, offer_at, hiring_manager_id, exit_reason` | required |
| roster | `week, recruiter_id, available_days` | recommended |
| tasks | `task, data_key, per_month, minutes, automatable, effort, eliminate` | for the automation ranking |

`data_key` takes the task's frequency from your export: `applications`, `screens`, `bookings`, `reschedules`, `reminders`, `offers`, `manager_updates`.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Central recruiting teams covering many stores, with seasonal peaks. |
| Quick-service restaurants | Strong | Very high application volume per recruiter, much of it never progressing. |
| Logistics and delivery (W2) | Strong | Recruiters split across sites and roles with very different screening times. |
| Gig and courier marketplaces | Limited | Onboarding is often unowned and automated; works where an ops team owns queues. |
| No owner on each application | Does not fit | Load per recruiter cannot be rebuilt; hiring managers can stand in for coordination load only. |

## Verifying this yourself

```bash
python3 scripts/capacity.py --test
```

The demo was generated with known answers by `references/sample/generate.py`. The suite checks the knee comes back within 10% of the planted 70, that it survives without the busiest weeks, and that each of the seven recruiters is diagnosed as planted, including the one who only looks slow because of the roles she holds. It also builds worlds that must not produce a knee: no load effect at all, a straight-line effect, and a pure season effect. A team slow even in light weeks must be called a process problem, and a slow recruiter who is never busy must be called individual, not capacity. Before release, 800 damaged exports and rosters ran without a crash.

Exit codes: 0 report written, 3 input refused, 4 the engine itself failed.

## Who it's for

- **Heads of talent acquisition** building or defending a recruiter headcount case.
- **Recruiting operations** deciding what to automate first.
- **Recruiting managers** who want to know whether a slow week is the team, the season, or the reqs.
