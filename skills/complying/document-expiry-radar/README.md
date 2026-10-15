# Document Expiry Radar

> Shows who cannot legally work today, whose licence or certificate has to start renewal now to avoid a lapse, and which scheduled shifts sit on the far side of an expiry.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You export the documents your people need to work (DOT medical cards, driver's licences, forklift evaluations, food handler cards, first aid) with their expiry dates, and ask:

> "Who's about to lapse, and what does it hit?"

It keeps one current record per person per document, works out the date each renewal had to start, and sorts everything into: expired and still scheduled, expired, start the renewal now, and due in the next 90 days. Give it the schedule and it counts the shifts and hours after each expiry. Give it what each role needs and it finds the people with no record at all.

The dates are computed by `scripts/radar.py`, a dependency-free Python engine. Same file, same answer, every run.

## Why it exists

The deadline is not the expiry date. A medical card that expires in 20 days is already late when booking the exam and getting the new card on file takes three weeks, and a spreadsheet sorted by expiry shows that driver as fine. On the sample company, five drivers are past their start-by date while none has expired yet, and three of them are booked for shifts after their card runs out.

## Install

**1. Download** [document-expiry-radar.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/document-expiry-radar.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the document radar demo."* Then with your own: *"Here's our certifications export and next week's schedule. Who's at risk?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/complying/document-expiry-radar ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## What's supported

- **Eleven document types** recognised under their common names: DOT medical card, driver's licence and CDL, forklift evaluation, food handler card, food manager certificate, first aid and CPR, alcohol server permit, security guard licence, vehicle insurance, vehicle registration, periodic background re-check. Anything else is kept, with the renewal time assumed and said so.
- **Scheduled staff or contractors.** A schedule for shift workers, or a list of who is active for gig and independent contractors.
- **Site minimums**, such as at least one certified food manager per restaurant, with the day each site drops below it.
- **Your own renewal lead times** per role and document, which override the planning defaults.
- **Renewed documents** sitting beside the old row: the later date wins.
- **Crunch weeks**: five or more of one document expiring at one site in one week.
- **A one-page HTML report** with expiries by site and week.

## What's not supported

- **Names, contact details, document numbers.** Refused. Opaque ids only.
- **Work-authorisation documents.** Work permits, visas, I-9 reverification and E-Verify rows are refused on purpose.
- **Checking a document is genuine** or that a renewal was really booked.
- **Legal advice.** Validity periods are described in shape and point to the issuing body.

## Verifying this yourself

```bash
python3 scripts/radar.py --test
```

Three sample companies are planted with exactly what the radar should find. The delivery company: two drivers expired and still scheduled, one expired warehouse associate, five DOT cards past their start-by date, fourteen forklift evaluations from one training cohort expiring in the same week, three drivers with no medical card on file, one renewed card that must not be reported, one unreadable date and a trickle of six ordinary renewals. One station has nothing planted and must come back clean. The restaurant chain: one site with no certified food manager today, one losing its last in four weeks, expired manager certificates that must not stop the manager working, crew cards to renew, two new hires with no card, a hiring-event cohort, and one clean restaurant. The courier marketplace: two couriers active with expired insurance, one inactive, three renewals to start, and one active courier with no documents on file. The suite also covers lead-time edge cases, your own lead times overriding the defaults, unknown and misspelled document types, a clean file, and the edge cases an adversarial pass found before release: the expiry day itself, shifts already worked, one person with two expired documents, role and id spelling, people on the schedule but not in the export, non-UTF-8 files, and eighteen kinds of input that must be refused because they would put a name, a contact detail or a document number in the report.

## Where it fits, and where it does not

| Business | Fit | Why |
|---|---|---|
| Logistics and delivery (W2) | Strong | Medical cards, CDLs and forklift evaluations: an expired one means the person cannot legally drive or operate. |
| Quick-service restaurants | Strong | Food handler cards for crew and a certified food manager per site, with turnover that keeps cards expiring all year. |
| Gig and courier marketplaces | Good | Licence, insurance, registration and background re-checks, against who is active rather than who is scheduled. |
| General retail | Limited | Most store roles need no document that expires. It earns its place for alcohol sales, deli and pharmacy counters, and stockroom forklifts, and will show little elsewhere. |

The document types and sources are US-based.

## Who it's for

- **Operations and site managers** who need to know on Monday who cannot be put on a shift.
- **Compliance and HR teams** who keep the certification spreadsheet and want it to say who to chase first.
- **Fleet and warehouse leads** whose drivers and operators cannot work a day without a current card.
