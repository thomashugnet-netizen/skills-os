# Schedule Photo to Roster: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/roster.py --roster references/sample/northline_store14_truth.csv --needs references/sample/northline_store14_needs.csv --rules oregon --rate 17.50

## Example prompt

> Here's our schedule for next week [photo], and the staffing we need by hour is in this file. Always one shift lead on the floor. We're in Oregon, and the rate is $17.50.

## Example output

From the engine's check of the demo week (Store 14's handwritten schedule, `references/sample/northline_store14_photo.jpg`, as read back in `northline_store14_truth.csv`), under Oregon's predictive scheduling rules. An excerpt.

**57 shifts, 12 people, 434.5 hours.** 11.5 person-hours short, 6 overtime hours, 1 short rest, 1 double booking. Overtime premium about $52.50.

**Check the photo first:** Sam on Thursday (12:00 to 18:00) was smudged; best reading 12 to 6. Confirm it before trusting the rest.

| Problem | Where | What it means |
|---|---|---|
| Double booking | Priya, Wednesday, 06:30 to 15:00 and 12:00 to 20:00 | One of them is not real, and the coverage that depends on it is not either |
| Short-staffed | Sunday 15:00 to 22:00 | Short by up to 2 (9.5 person-hours), and no shift lead on the floor |
| Short-staffed | Saturday 07:00 to 09:00 | Short by up to 1 |
| Overtime | Dana, 46 hours | 6 over the 40-hour week; Marco could take them |
| Short rest | Marco, Friday 23:00 to Saturday 06:00 | 7 hours between shifts, under Oregon's 10 |
| No day off | Leo | 7 days in a row |

**Hours you could move:** Tuesday 11:00 to 19:30 carries 18.5 person-hours above what you said you need.
