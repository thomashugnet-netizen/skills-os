# Check-in Designer: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/checkins.py --plan references/sample/northline_plan.json

## Example prompt

> Design day 1, 7 and 30 check-ins for our overnight stockers. Our shift leads run them, and anything serious goes to the site lead or HR.

## Example output

From the skill's demo: the worked example it ships for this brief (`references/sample/northline_plan.json`, a fictional grocer), and its checker's verdict. An excerpt: the day 1 card.

**Day 1, at the end of the first shift, before they leave.** Run by the overnight shift lead (duty manager if not). About 100 seconds.

"Quick check before you head home, two minutes."

| Question | If the answer is | Goes to | By when |
|---|---|---|---|
| Did you get boots, gloves and a vest that fit? | No kit, or the wrong size | Overnight shift lead: swap the size from the cage before their next shift | Within 24 hours |
| Do you know when your next shift starts? | No schedule | Site lead: send it by text | Within 24 hours |
| Did you get your break tonight? | No break taken | Site lead: set the break for the next shift | Within 24 hours |
| Do you know who to call if you can't make a shift? | Does not know the number | Shift lead: add it to their phone now | Within the week |
| Did anything feel unsafe tonight? | Unsafe, or someone hurt | Site lead: walk the area with them | Within 24 hours |
| | Someone's conduct towards them | HR business partner, out of the check-in to the grievance route | Same day |

**Checker:** day 1 about 100 seconds, day 7 about 104, day 30 about 103. READY to run.
