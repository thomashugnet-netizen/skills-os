---
name: phone-screen-script
description: Writes a five-minute phone screen that leads with availability, decides on the call, and ends with a booked next step.
---

# Phone Screen Script

## What this does

Writes the call your team actually makes: five minutes, word for word, availability first, decision made before hanging up. Built for the version of this job that exists in frontline hiring, where one coordinator makes sixty calls a day, most go to voicemail, and the screen exists to confirm facts and book a slot rather than to assess anybody.

## What to give me

- **The role, the site, and the shifts you need filling.** Essential. The call is built around the second half of that.
- **What your application already asked**, and which answers you don't trust. Essential — the script's job is to confirm those out loud, and re-asking things you already know reliably wastes seconds you don't have.
- **What the next step is, and how it gets booked.** Essential. A screen with no slot to offer cannot end properly, and it drifts into an interview.
- **Who makes these calls**, and how many a day.
- **Anything genuinely disqualifying** — minimum age for the role, a licence the law requires, right to work.
- **Pay and shift facts the caller may state.** If they can't answer "what does it pay", candidates disengage and your callback rate drops.

Where you can't tell me the next step, I'll say the script is incomplete rather than inventing one.

## How I work

### Step 1 — Fix the running order, and lead with availability

The order is not taste. It is what stops five minutes being wasted:

1. **Who you are, which job, how long this takes.** Two sentences. Callers who skip this get treated as sales calls.
2. **Availability, against your actual rota** — the specific blocks you are short of, read out, yes or no on each.
3. **Earliest start date**, and whether they owe notice.
4. **Getting here for the earliest shift**, in their words.
5. **Any genuine prerequisite** — age for the role, the licence, right to work.
6. **Thirty seconds of honest job preview**, then: knowing that, do you still want it.
7. **Their questions**, briefly.
8. **The decision and the booking**, out loud, on the call.

Availability leads because it is the fact most likely to end the call, and the one most likely to be wrong on the application. Applicants tick availability boxes on a phone in the middle of doing something else, and they tick generously. Asking in minute one, out loud, against real shifts, is how you avoid discovering in minute four that this person can work none of them.

It also frames everything after it. The rest of the call is about a specific shift on a specific rota rather than a job in the abstract, and that is the conversation that produces an accurate yes.

### Step 2 — Confirm out loud what the application already claimed

Three claims are worth re-asking even though they sit in your system already, because the spoken answer differs from the tapped one often enough to pay for the seconds:

- **Availability, block by block.** "Can you work Monday to Friday, 6am to 2pm?" not "is your availability still correct?" The second question gets a yes from everybody.
- **The earliest shift specifically.** If the rota has a 5am or a Sunday night, name it and get a spoken yes on that one.
- **The journey.** Ask them to describe how they'd get here for the earliest start, not whether they can. A route with a time in it is a different quality of answer from "yeah, it's fine", and this is where the caller listens for hesitation.

Everything else gets taken at face value. A screen is not an audit.

### Step 3 — Design the voicemail and callback path, because it is the main path

At frontline volume most attempts don't reach a person, so voicemail is not an edge case. Leaving it to the caller to improvise is where the funnel leaks. So the script includes:

- **A voicemail under twenty seconds** naming the company, role, site and a specific way back — ideally a text-back number or a booking link, because people who missed your call will text and will not ring an unknown number.
- **A text sent immediately after every voicemail.** The text gets read; the voicemail does not.
- **A call-attempt rule**: how many attempts, spaced across different times of day rather than three in one afternoon. Someone on nights is asleep at 2pm.
- **A stop rule**, so the candidate moves to a defined state instead of sitting in a queue forever.
- **A script for the inbound callback**, because whoever answers has no idea what the call is about.

Speed matters more than any wording here. Frontline applicants apply to several employers in one sitting, and calling first beats scripting well.

### Step 4 — Decide on the call

The decision rule is written into the script and binary at three points: availability overlap, prerequisite, preview answer. Any one failing ends the call politely, there and then. Everything else advances.

That removes the need for judgement, which is the point, because judgement is what makes sixty calls take three days and produce sixty standards. It also means the candidate gets an answer while still on the phone, which is the largest single difference between a screen candidates complete and one they abandon.

So the script includes the exact words for a polite no, and for the redirect: "you can't do those shifts, but the site down the road needs Tuesday mornings." Partial availability is a routing outcome, not a rejection.

### Step 5 — End with a booked slot, or the call has not finished

An advanced candidate does not leave the call with "we'll be in touch". They leave with a date, a time, an address, a named person, and a confirmation sent before you hang up. The script offers two specific slots rather than asking when suits them, because two options get chosen and an open question gets postponed. Then the confirmation text and the reminder cadence. A screen ending in an intention hands the candidate back to whichever employer books properly.

## What you get

**1. The script**, word for word, in running order, on one page: opener, availability block, prerequisites, preview, close.

**2. The availability block** built against your actual rota gaps, with the shifts named.

**3. The decision rule** — three binary gates, what each outcome does, and the wording for each.

**4. Voicemail and text templates**, with the attempt cadence, the stop rule, and the inbound-callback script.

**5. Redirect language** for partial availability and wrong-site candidates.

**6. Booking language and confirmations**, including the pre-interview reminder.

**7. A five-field capture sheet.** What the caller writes down, and nothing else. If the record needs more than five fields, the call will run over.

## What I'll push back on

- **Trying to assess competence in five minutes.** Two behavioural questions in a five-minute call produce two unscoreable answers and cost you the booking at the end. A screen confirms facts, previews the job honestly, and books a slot. Assessment goes in the interview, with anchors — see `structured-interview-guide` and `scorecard-designer` in this library. A screen that assesses is a short interview with none of the structure, run by someone holding no scorecard.
- **A screen that ends without a booked next step.** The most common defect and the most expensive one. Every hour between call and booking is an hour a competitor uses. If interview slots aren't visible to the caller, fix that before you fix the wording.
- **"Tell me about yourself" as the opener.** It burns ninety seconds of a three-hundred-second call and produces nothing you score.
- **Reading the whole job description out.** Thirty seconds of the honest hard part beats two minutes of the full picture, and it is the half that changes anybody's mind.
- **Leaving voicemail wording to the caller.** Sixty improvised voicemails a day is your largest single source of unrecovered applicants.
- **Withholding pay until the interview.** Candidates ask, and a caller who can't answer gets a lower show rate. If it's a range, give the range.

## Where this stops

This writes the call. It cannot make it, and it cannot see whether your callers stick to it. It cannot tell you your answer rate, your time to first call, or how many screened candidates turn up, and those decide whether a better script changes anything. If bookings are made and then missed, the script is not the problem: that is diagnosed from funnel data, and `interview-no-show-playbook` in this library does it.
