# Turnover Analyst

> Tells you whether your early attrition is a hiring problem or a job problem — by looking for structure in each tenure band separately and asking whether the structure found in the first month survives into the second.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You point it at an export of everyone who started — one row per hire, with how long they stayed — and ask:

> "Who is leaving, when, and is it who we hired or what we hired them into?"

It builds the 1-30, 31-90 and 91+ bands over their own at-risk cohorts, finds which managers, sites, sources and roles carry more than their share of each, screens those findings against the false discoveries that two hundred comparisons guarantee, re-tests every survivor against the dimensions it is entangled with, and then asks the question the whole skill exists for: does the first-month gap persist?

The statistics are computed by `scripts/analyze.py`, a dependency-free Python engine, not improvised in prose. Same export, same numbers, every run.

## Why it exists

Turnover analysis in hiring goes wrong in four specific ways, and this engine exists because each one of them was found in its own test suite before it was found in the code.

**A band rate over the wrong denominator.** Two of them, actually. People hired last month cannot be recorded as 90-day leavers, and people who left on day 20 were never at risk of leaving on day 60. Get either wrong and each band inherits the band before it — a segment with terrible first-month attrition comes out looking good at 90 days, because its denominator is full of people who had already gone.

**Two hundred comparisons and no correction.** Forty managers across four dimensions and three tenure bands. At the usual threshold that yields roughly ten findings in a file with nothing in it — and it did, until the suite ran against a band where the generator had planted nothing and the engine confidently reported four managers.

**The confound.** Managers and roles are entangled in almost every frontline operation, because one manager runs the site that hires most of one job. Cut by role and you blame the job; cut by manager and you blame the person. Only one of them survives being held constant, and which one is the entire finding.

**Exit reasons that explain nothing.** With five categories and a few hundred leavers, two random halves of the same population routinely differ by ten points. This engine reshuffles the labels a few thousand times before it will say a segment leaves for different reasons — and on the sample data, it never says so.

## Install

**In the Claude app** — Settings → Customize → Skills → **+** → upload a `.zip` of this folder. Works on Free, Pro, Max, Team and Enterprise. Team and Enterprise owners can provision it to everyone from Organization settings → Skills.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/retaining/turnover-analyst ~/.claude/skills/
```

Then ask: *"Here's everyone who started in the last year and how long they stayed — where are we losing people?"*

**Prerequisites:** Python 3. No packages to install — standard library only, deliberately, so it runs wherever the skill lands.

## What it needs

One row per hire, at least 200 people who actually started, `first_shift_at`, and `tenure_days` (blank for people still employed). `hiring_manager_id`, `location_id`, `source` and `role` each unlock a class of finding. `separation_reason` gets tested and usually reported as explaining nothing.

The window should end **at least a quarter before today**. An export that runs to yesterday is mostly people who have not had time to leave.

## What it refuses

| | |
|---|---|
| A column that looks nominative | This output names managers as carrying attrition. It must never sit beside a list of who left |
| No `tenure_days` or no start date | There is no band to measure, and no cohort to measure it over |
| An export cut too close to today | If most hires have not had thirty days, the rate understates itself by however much you have been hiring |
| Fewer than 200 actual hires | A band rate moves several points on a handful of records |
| Mixed stage vocabularies | A hire population built from the wrong stage list is wrong in a way that still looks plausible |

## Verifying this

```bash
python3 scripts/analyze.py --test
```

26 assertions against each sample, plus five refusal cases. The assertions are comparisons between effects rather than thresholds on one: the manager effect must keep most of itself within role while the role effect loses most of itself to the manager group; no weak manager may reappear in the 31-90 band; and eight sites planted with a scheduling problem and no attrition problem must never be reported as turnover. The same assertions run against the gig sample on its five-stage funnel, so what passes is the method rather than a memory of one file.

## Where this stops

It reads a file you exported, so it sees one moment and changes nothing. It is not a prediction — every number is about people who have already left.

It cannot tell you *why* a manager loses people. Rostering, training, a genuinely harder site, or one person: the analysis is the beginning of that conversation, not its conclusion.

It errs toward missing a real problem rather than inventing one. A segment that does not appear here has not been cleared; it has not been proven, which is a different thing.

## Licence

MIT. Use it, fork it, ship it inside your own tooling.
