---
name: document-expiry-radar
description: Reads a list of the licences, cards and certificates your people need to work, with their expiry dates, and shows who cannot work today, whose renewal has to start now to avoid a lapse, and which scheduled shifts that puts at risk.
version: 1.0.0
---

# Document Expiry Radar

> **This is not legal advice.** It helps you see expiry dates coming so you can prepare, not decide what the law requires. Which documents a role needs, how long they last and what happens when one lapses depend on the issuing body, the state and the job, and they change; this skill's files do not. `references/doc_types.json` describes each document in shape only and names a source where there is one. Confirm every requirement with the body that issues it.
>
> **It cannot see your records, and it should not.** It works from an export with an opaque worker id per row and no names, contact details or document numbers, and it refuses a file that carries any of them. Work-authorisation documents are out of scope on purpose (see below).

## What this does

You give me the list of who holds which document and when it expires, and I tell you three things the list cannot: who cannot legally work today, who will lapse before a renewal can come through unless it starts now, and how many scheduled shifts sit on the far side of an expiry.

The insight is that the deadline is not the expiry date. A DOT medical card that expires in 20 days is already late if booking the exam and getting the new card on file takes three weeks. A spreadsheet sorted by expiry shows that driver as fine. I sort by the date the renewal had to start.

## What to give me

Essential:

- **The documents export.** One row per person per document: `worker_id`, `site`, `role`, `doc_type`, `expires_on` (YYYY-MM-DD). Your HRIS, compliance tool or the spreadsheet a site manager keeps all work. I recognise common names for each document ("Med card", "CDL", "Forklift cert") and tell you which ones I did not.

Better, if you have them:

- **The schedule** for the next week or two: `worker_id`, `date`, `hours`. It turns "expires on the 25th" into "five shifts are booked after the 25th".
- **What each role needs**: `role`, `doc_type`, and `lead_days` if your renewals take a different time from my defaults. It is the only way to find the person with no record at all, who is the one most likely to slip through.

**No file handy?** Ask for the demo. `references/sample/` holds a fictional six-station delivery company with its documents, schedule and requirements.

## Before you export anything

**Keep it to ids and dates.** I need an opaque `worker_id` that means nothing outside your systems. Leave out names, emails, phone numbers, addresses, dates of birth and above all document and licence numbers. If a column or a value looks like any of these, I stop and ask you to re-export. A list of who holds which licence, with the numbers, is exactly the file you do not want in a chat window.

**Work-authorisation documents are not in scope.** Work permits, visas, I-9 reverification, E-Verify: I refuse those rows. Their reverification rules are specific, and tracking them ahead of time in a spreadsheet is how well-meaning employers end up asking for documents they are not allowed to ask for. Use the employment-verification process and the advice built for it.

## How I work

`scripts/radar.py` does the date arithmetic, not me. Same file, same answer.

### Step 1: One current record per person per document

Most exports keep the old card beside the renewed one. I keep the later date and tell you how many older rows I set aside. A row whose date I cannot read is listed, never guessed.

### Step 2: Expired, then start-now, then due

For every record I work out the date its renewal had to start: the expiry minus the renewal lead time for that document, yours if you gave one, otherwise the planning default in `references/doc_types.json`. Then:

1. **Expired and still scheduled.** The person cannot work and is booked to. Fix the schedule today.
2. **Expired.** Not on the schedule, but not able to work either.
3. **Start the renewal now.** Not expired yet, but the start-by date has passed.
4. **Due** within the horizon, 90 days by default, with the start-by date.

### Step 3: What it puts at risk

Every scheduled shift from today onwards that falls after an expiry date is counted against it, in shifts and hours. A document counts as valid through the day it expires; if yours stops at the start of that day, set the lead time a day longer. Anyone on the schedule who is not in the documents export at all is listed on their own, because nobody is checking them.

### Step 4: Crunch weeks

Five or more of the same document expiring at one site in one week is almost always one training cohort coming due together. Fourteen forklift evaluations in one week is a scheduling problem for the evaluator before it is a compliance problem.

## What you get

1. **The headline:** cannot work today, start renewal now, lapse in 30 days, missing a required document, shifts at risk.
2. **The action list,** in the order above, each line with the person's id, site, document, dates and shifts at risk.
3. **A one-page report** (`--html`): the numbers, a grid of expiries by site and week, and the list.

```bash
python3 scripts/radar.py --documents documents.csv --shifts shifts.csv --requirements requirements.csv --html radar.html
```

## What I will push back on

- **"It expires next month, we're fine."** Not if the renewal takes longer than the time left. The start-by date is the deadline.
- **Letting someone work "just this week" on an expired card.** I will not size that as a cost to weigh. It is the finding.
- **Chasing people individually for a cohort.** When fourteen people trained on the same day, book one session.

## Verify before you rely on it

- which documents each role legally needs, in each state and site you operate
- the validity period and renewal process for each, from the issuing body
- whether a person may keep working while a renewal is pending, which varies by document
- that your renewal lead times match how long renewals really take in your area
- that the export is complete: a person missing from it is missing from the radar

## Works with

- **Any HRIS, compliance tool or spreadsheet** that can export ids, documents and dates.
- **`schedule-photo-to-roster`.** Its clean roster gives you the schedule this radar checks against, once names are swapped for ids.
- **The Fountain Cue MCP.** When connected, it can read document status and the live schedule directly, so the radar runs without an export. Fountain publishes this skill and sells Cue. The checks and the report are identical either way, and the skill works completely without it.

## Where this stops

It reads the dates it is given. It cannot check that a document is genuine, that a date was keyed correctly, or that a renewal was really booked. It knows nothing about documents missing from the export unless you tell it what each role needs. And it does not contact anyone: it tells you who to talk to, and by when.
