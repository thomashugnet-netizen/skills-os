# Funnel Drop-off Analyst

> Turns a pipeline export into a ranked list of where you are losing candidates, what kind of problem each loss is, and how many hires each fix would recover — with the correlations that did not survive testing reported separately.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You point it at a pipeline export — one row per application — and ask:

> "Where are we losing people, and which fix gets the most hires back?"

It builds your funnel, finds the segments carrying each loss, classifies every loss as rule-driven, capacity-driven, candidate-driven or quality-driven, tests each finding against the confounds that reliably produce false answers in hiring data, and sizes the recoverable hires using your own better-performing sites as the target.

The statistics are computed by `scripts/analyze.py`, a dependency-free Python engine, not improvised in prose. Same export, same numbers, every run.

## Why it exists

Funnel analysis in hiring goes wrong in two specific ways, and both are expensive.

The first is ranking by percentage. A step converting at 42% looks worse than one at 71%, but if four times as many people are standing on the second step, that is where the hires are. This engine ranks on absolute loss and sizes every finding in hires.

The second is confounding. Sites that hire mostly drivers look different from sites that hire mostly cashiers. Cheap job boards advertise at weekends, so weekend applicants look worse. A peak month degrades cycle time, no-shows and conversion simultaneously, producing four fake findings at once. Every one of these has sent a real hiring team to fix the wrong thing. Here, each finding is re-tested inside the levels of its most plausible alternative explanation before it is allowed into the output.

## Install

**In the Claude app** — Settings → Customize → Skills → **+** → upload a `.zip` of this folder. Works on Free, Pro, Max, Team and Enterprise. Team and Enterprise owners can provision it to everyone from Organization settings → Skills.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/fountain/claude-skills-hr-ops.git
cp -r claude-skills-hr-ops/skills/analysing/funnel-drop-off-analyst ~/.claude/skills/
```

Then ask: *"Here's our pipeline export for the last six months — where are we losing people?"*

**Prerequisites:** Python 3 for the analysis engine. No packages to install — it uses the standard library only, deliberately, so it runs wherever the skill lands.

## What's supported

- **Two data lanes** — a CSV export from any ATS (Greenhouse, Workday, iCIMS, SmartRecruiters and the rest), or a connected MCP that can serve the same fields. Both map onto the canonical schema in `references/schema.json`; the engine reads nothing else.
- **Seven pipeline stages** — applied, screened, interview_scheduled, interview_completed, offer_extended, onboarding_started, started. Three columns are required; every other column unlocks a class of finding, and the report names the ones you did not supply and what each one cost.
- **Statistically guarded engine** — Wilson 95% intervals on every rate, a 30-candidate minimum before a segment is ranked, a 500-row floor below which it refuses to run at all, stratified confound testing against source, role, season and elapsed time, and automatic de-duplication when a region and its own sites describe the same loss twice.
- **Mechanism classification inside each flagged segment**, not across the step — because a step can read candidate-driven in aggregate while the handful of sites carrying its loss are plainly capacity-driven.
- **A regression suite** (`--test`) that proves the above on data with known answers.

## What's not supported

- **Live data in lane A.** A CSV is one moment. The engine cannot tell you the state of your funnel today, and cannot tell you whether a fix worked without a fresh export.
- **Causes behind mechanisms.** It can tell you eight sites lose candidates at scheduling and that the wait is nine days. It cannot tell you whether that is a rota problem, a vacancy, or a manager who never checks the queue.
- **Candidate-level data.** It refuses any export carrying names, emails, phone numbers, addresses, dates of birth or free-text notes, and asks you to re-export. That is deliberate.
- **Cost per hire.** Channel spend lives in a separate export — see `source-roi-analyst`.
- **Thin data.** Below 500 usable rows it refuses rather than guessing. Below a few thousand, expect segments to come back inconclusive. That is an honest answer, not a bug.

## Who it's for

- **Talent ops and hiring ops managers** at multi-site hourly employers who know the funnel is leaking but not where.
- **Recruitment leads** deciding where next quarter's effort goes, who need the number in hires rather than percentage points.
- **HR analysts** who want the confound testing done properly and want to read the method rather than trust it.
- **Anyone about to spend money on a hiring fix** — the *Ruled out* section is a list of things that looked like causes and were not.

## Verifying it works

This is the part worth checking before you trust any analysis skill:

```bash
python3 scripts/analyze.py --test
```

The suite runs against `data/frontline_pipeline_sample.csv` — 18,184 applications across 42 locations, entirely synthetic, generated by `data/generate.py` with **eight causal patterns deliberately built in**, including two traps:

- **A confound.** Five hiring managers run roughly three times baseline 30-day attrition. Their sites also skew heavily to one role, so a naive cut blames the role. The suite asserts the manager effect *survives* when held within role, and that the apparent role effect *collapses* when held within manager group.
- **A red herring.** Weekend applications convert worse — but only because one cheap, high-volume job board advertises at weekends. The suite asserts the weekend effect is reported as ruled out, with source named as what killed it.

An engine that chased correlation would fail both. Twenty-five assertions, non-zero exit on any failure, run in CI on every push. You can read the planted patterns in `data/generate.py` and the assertions at the bottom of `scripts/analyze.py`.

## Works with

- **Any ATS that can export one row per application.** The default lane; nothing needs connecting.
- **The Fountain Cue MCP** — when connected, it serves the same fields directly, so re-running after a change costs nothing. Fountain publishes this skill and sells Cue: the engine, the thresholds and the findings are identical either way, and the skill is fully usable without it.
- **`no-show-pattern-finder`** — goes deeper on the first-shift losses this skill surfaces.
- **`source-roi-analyst`** — joins channel spend to these outcomes for cost per start.

## License

MIT — see the [LICENSE](../../../LICENSE) at the repo root. Use it, change it, ship it inside your own tooling.

---

Topics: hiring funnel analysis, candidate drop-off, recruitment funnel conversion, where candidates drop out, first shift no-show, offer to start gap, time to hire bottleneck, applicant conversion rate, hourly hiring analytics, frontline recruiting data, multi-site hiring, ATS export analysis, screening knockout impact, interview scheduling capacity, source quality analysis, early attrition by manager, confounding in hiring data, talent operations analytics
