# Rehire Campaign Planner: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/rehire.py --demo

## Example prompt

> Here's our applicant export from the last year. We're hiring night stockers, day sales associates and evening cashiers across 12 stores. Who can we re-engage, and how many at a time?

## Example output

From the engine's demo run (the retail pipeline sample with `references/sample/northline_policy.json`: 18,184 records, as of 1 September 2026). An excerpt.

**1,535 people are contactable.**

| Who is in | People |
|---|---:|
| Former workers who left in good standing | 80 |
| Reached interview or beyond, never started | 752 |
| Screened, then dropped | 703 |

Of those 703, 404 dropped because of you: no slot offered, nobody followed up, a check that took too long. The report says to lead with that.

**Who is out, and why:** 4,429 past your retention period (a deletion job, not a campaign), 3,821 blocked because nobody has decided whether you may contact people about a different role, 1,674 still working for you, 133 who left on conduct or attendance, or are marked not eligible for rehire.

**Waves, sized to who answers the replies (3 hours a day):** wave 1, 400 people, about 70 replies; wave 2, 1,135 people, about 95. Reply rates are assumptions, labelled as such, to replace with yours after wave 1.

**Settle these before the first send:** no suppression list was given, channel consent is not in the export, and a number given to arrange an interview is not automatically consent to campaign texts.
