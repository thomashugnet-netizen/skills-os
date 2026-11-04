# Interview Panel Calibrator: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/calibrate.py --scores references/sample/northline_scores.csv --key references/sample/northline_key.csv --live references/sample/northline_live.csv

## Example prompt

> Here are my panel's scores on the calibration exercise, and last quarter's live interview results. Are they scoring the same way, and if not, is it them or the guide?

## Example output

From the engine's run on the demo files (`references/sample/northline_*`: seven interviewers, nine written answers, 63 scores on a 1 to 3 scale, and their live results across six sites). An excerpt.

**What to fix in the guide**

| Answer | What the panel did | What it means |
|---|---|---|
| Q2-B | Split between 1 and 2 | Two defensible readings of the anchor. Rewrite it so only one survives; coaching people fixes nothing, because nobody is wrong. |
| Q3-A | Agreed on 2; you wrote it as a 3 | They agree with each other and not with you: the anchor does not say what you meant. |
| Middle answers | 57% of scores left the group's level, against 24% at the ends | The middle anchor is underspecified. Write what a middle answer sounds like. |

**Each interviewer, against the others**

| Interviewer | Finding | What to do |
|---|---|---|
| Dana | Scores 0.7 levels above the group, in the same order | Show where their bar sits, with a worked answer at each level. |
| Luis | Gives strong and weak answers the same score | Practise on the extremes. Until the scores separate, should not score alone. |
| Jo, Kim, Marcus, Priya, Sam | Score with the group | Nothing on paper. |

**Live interviews:** Sam advances 28% of candidates against a pool of 53%, but scores with the group on paper, so look at their site's vacancies before coaching anyone. Across the six sites, pass rate rises with open roles (rank correlation 0.99): that is hiring pressure, and coaching alone will not hold.
