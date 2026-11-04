# Job Ad Writer: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/check_ad.py --input ad.txt --channel job_board

## Example prompt

> Write a job ad for overnight stockers at our Dayton store, 3100 Wayne Avenue, Dayton OH 45420. Sunday to Wednesday nights, 10pm to 6:30am, the same nights every week, schedule posted two weeks ahead. $17.50 an hour plus $1.50 for nights, paid every Friday. They unload the truck, fill shelves, check dates and keep the aisles clear. On their feet all shift, lifting cases up to 40 pounds, and the back room is cold in winter. Bus route 7 stops outside, parking is free. No experience needed, two nights of training, and a path to overnight shift lead. Apply by texting NIGHTS to 60777 or at northline.example/jobs.

## Example output

From a run of the skill on the brief above (a fictional grocer), with each variant scored by its rubric, `scripts/check_ad.py`. An excerpt: the job board version and the SMS variant.

**Job board**

> Overnight Stocker - $17.50 an hour + $1.50 nights - Dayton, OH 45420
>
> Nights, 10pm to 6:30am, Sunday to Wednesday. Four nights a week, same nights every week. Schedule posted two weeks ahead.
>
> $17.50 an hour, plus $1.50 an hour for every night hour. Paid every Friday.
>
> The store is at 3100 Wayne Avenue. Bus route 7 stops outside, and parking is free.
>
> What you will do:
> - Unload the truck and fill shelves before we open
> - Check dates and rotate stock
> - Keep the aisles clear and safe
>
> It is on your feet the whole shift, lifting cases up to 40 pounds. The back room is cold in winter. We say that now so it is not a surprise in week two.
>
> What you get:
> - Pay every week
> - A set schedule you can plan around
> - A path to overnight shift lead
>
> No experience needed. We train you on your first two nights.
>
> To apply, text NIGHTS to 60777 or go to northline.example/jobs.

Rubric: 869 characters, reading grade 2.6. Nothing to fix.

**SMS**

> Northline Dayton: overnight stocker, $17.50/hr + $1.50 nights, Sun-Wed 10pm-6:30am, paid weekly. Apply: northline.example/jobs

Rubric: 126 characters. Nothing to fix.

A full run also returns a per-site variable table, social, poster and referral variants, two A/B variants that each change one thing, a title set and a posting checklist. This excerpt shows two of the variants.
