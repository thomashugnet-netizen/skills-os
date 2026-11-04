# Bias Language Checker: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/bias_check.py --library references/sample/northline_templates.csv

## Example prompt

> Here's every candidate-facing template we use: application questions, job ads, the phone screen, emails and offer letters, with how many people each one reaches. What should we fix first?

## Example output

From the checker's run on the demo library (`references/sample/northline_templates.csv`: 13 templates reaching 2,688 candidates). An excerpt.

**10 high, 6 medium and 4 low findings.** One Spanish template was not checked, by name, with a note to have someone who reads Spanish review it.

**Fix first: severity, then how many people the line reaches**

| Line | Where | Reaches | Instead |
|---|---|---:|---|
| "What year did you graduate high school?" | Application | 940 | If the role has a legal minimum age, ask "Are you 18 or older?" and nothing more. |
| "Are you a US citizen?" | Application | 940 | "Are you legally authorised to work in the United States?" Verify after hire, through Form I-9. |
| "Have you ever been arrested?" | Application | 940 | Leave it out. If a check is needed, run it after a conditional offer. |
| "Do you have childcare sorted for nights?" | Phone screen | 80 | Ask everyone: "Can you work the posted schedule, nights and weekends included?" |
| "Must have own car." | 4 job ads | 126 | Say the start time and the place: "Shifts start at 5am at our Dayton store (bus route 17 stops outside)." Fix the master the four were copied from. |
| "...a better culture fit for the team." | Decline email | 410 | Name the job requirement the person did or did not meet. |

Nothing here is an approval: a rewritten line is lower-risk, not cleared, and the report says so.
