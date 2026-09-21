# Time to Hire Analyst

> Breaks hiring cycle time down stage by stage and names the one stage actually holding the queue — separating the stage that is slow for everybody from the stage that is slow at eight sites, and both from the stage that is only slow in peak season.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You point it at a pipeline export — one row per application, with a timestamp for each stage — and ask:

> "Where is our hiring time actually going?"

It builds the clock stage by stage, finds which segments carry each wait, separates delay that is structural from delay that only appears under load, tests every concentrated delay against the confounds that reliably produce false answers in hiring data, and sizes what comes off the calendar if each confirmed problem is fixed.

The statistics are computed by `scripts/analyze.py`, a dependency-free Python engine, not improvised in prose. Same export, same numbers, every run.

## Why it exists

"Time to hire" is a single number describing a process that is slow in several unrelated ways at once, and it has three specific failure modes.

**It averages incompatible problems.** On the retail sample, the stage carrying the most calendar time is interview-scheduled to interview-completed — four days, for everybody, by design. The stage you can actually fix is the one before it, where eight sites out of forty-two hold candidates nearly seven days longer than the rest because they have scarce self-schedule slots. One number reports neither. Optimise the first and you have shaved a stage that is working as intended.

**It is computed over the people who finished.** A median wait excludes everybody still in the queue — and they are excluded precisely because their wait is longer than the one being reported. The more of your pipeline is in flight, the more flattering the number. This engine counts them, reports how long they have already waited, and refuses the analysis outright past 60%.

**It confuses a capacity problem with a process problem.** A stage that stretches three days in peak months and returns to baseline in January is a staffing decision. A stage that is long in every month is how the process is built. They have different owners and different costs; averaged together they look like one vague complaint about speed.

## Install

**In the Claude app** — Settings → Customize → Skills → **+** → upload a `.zip` of this folder. Works on Free, Pro, Max, Team and Enterprise. Team and Enterprise owners can provision it to everyone from Organization settings → Skills.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/analysing/time-to-hire-analyst ~/.claude/skills/
```

Then ask: *"Here's our pipeline export for the last six months — where is our hiring time going?"*

**Prerequisites:** Python 3 for the analysis engine. No packages to install — it uses the standard library only, deliberately, so it runs wherever the skill lands.

## What it needs

One row per application, at least 500 usable rows, and **at least two stage timestamps** — the analysis is arithmetic on the gaps between those dates.

Worth knowing before you ask for the export: almost no ATS ships one row per application with a date column per stage. The timestamps live in a status-history log, one row per status change, so the pivot is a real step and the ask has to be explicit. `SKILL.md` covers what to request and which entry to take when a stage appears more than once.

No export handy? `frontline_pipeline_sample.csv` ships in `data/`; three more are on the library page.

## What it refuses

| | |
|---|---|
| A column that looks nominative | Names, emails, addresses. Nothing here needs to know who anybody is |
| Timestamps that contradict the stage order | Above 2%, the dates do not mean what the columns say and every median is fiction |
| A file still mostly in flight | Past 60% waiting, the report describes the fast ones and nobody else |
| Mixed stage vocabularies | A funnel timed against the wrong stage list is wrong in a way that still looks plausible |
| A file under 500 usable rows | A stage median moves several days on a handful of records |

## Verifying this

```bash
python3 scripts/analyze.py --test
```

22 assertions against each sample present, plus five refusal cases. The samples carry a known timing structure, and the assertions are comparisons between effects rather than thresholds on one — the suite checks that the site effect appears at the scheduling stage *and not at the others*, that the load effect lands on a different stage than the structural one, and that five managers planted with poor retention and no timing problem are never reported as slow. The same assertions run against the gig sample on its five-stage funnel, so what passes is the method rather than a memory of one file.

## Where this stops

It reads a file you exported, so it sees one moment and changes nothing. It cannot tell you your queue today, or whether a fix worked.

It measures waiting, not work: a stage where nothing happens for four days and a stage where four days of checks happen are identical in a timestamp.

And it does not claim a shorter wait means more hires. Long waits and drop-off travel together, but how much of one converts into the other is a drop-off question and a different analysis.

## Licence

MIT. Use it, fork it, ship it inside your own tooling.
