---
name: phone-screen-script
description: Writes and checks a five-minute phone screen for an hourly role, with availability asked first and shift by shift against the real rota gaps, three gates that decide on the call, and a booked interview before hanging up, plus the voicemail, text and attempt rule; then reads the call log for what a better script cannot fix.
version: 1.0.0
---

# Phone Screen Script

Created with Andrea Michelle Eighme.

## What this does

Writes the call your team actually makes: five minutes, word for word, availability first, the decision made before hanging up, and an interview booked before the line goes quiet. Built for frontline hiring, where one coordinator makes sixty calls a day, most reach a voicemail, and the screen exists to confirm facts and book a slot.

`scripts/screen.py` checks the script against the rules below and blocks it until it passes, prints a one-page call sheet, and, once the calls happen, reads the call log. Same script, same verdict, every time.

## How this differs from the interview

`structured-interview-guide` writes the interview, scored with anchors. This is the call before it, and it assesses nothing: it decides on facts (shifts, start, journey, a genuine prerequisite, the answer after an honest preview) and books the interview. A question that would need anchors to score is blocked here.

## What to give me

- **The role, the site, and the shifts you need filling this week.** Essential. Not the shifts the job has: the blocks you are short of, such as "Sunday to Wednesday nights, 10pm to 6:30am". Availability is asked against these.
- **What your application already asked**, and which answers you don't trust. Re-asking what you already know reliably wastes seconds you don't have.
- **What the next step is, and how it gets booked**: where, who they ask for, which slots you have. Essential. A screen with no slot to offer cannot end properly; it drifts into an interview.
- **Anything genuinely disqualifying**: a minimum age for the role, a licence or certificate the job needs, work authorization. Nothing else ends a screen.
- **The honest hard part of the job**, for a thirty-second preview, and **the pay**, which the caller must be able to say.
- **Where partial availability goes**: another site, other shifts.

Where you can't tell me the next step, I say the script is incomplete rather than inventing one.

## Before you paste anything

The script holds no personal data. A call log does: **opaque candidate and caller ids only**. If a log contains an email address, a phone number, or a column that looks like a name, an address or notes, I stop and ask you to re-export.

## How I work

### Step 1: Fix the running order, and lead with availability

1. **Who you are, which job, how long this takes.** Two sentences. Callers who skip this get treated as a sales call.
2. **Availability, against your actual rota**: each block you are short of, read out, yes or no on each.
3. **Earliest start date**, and whether they owe notice.
4. **Getting here for the earliest shift**, in their words.
5. **Any genuine prerequisite.**
6. **Thirty seconds of honest preview**, pay included, then: "Knowing that, do you still want it?"
7. **Their questions**, briefly.
8. **The decision**, out loud, on the call.
9. **The booking**: two specific slots, and a confirmation sent before you hang up.

Availability leads because it is the fact most likely to end the call and the one most likely to be wrong on the application: people tick availability boxes on a phone, generously. Asked in minute one, out loud, against real shifts, it frames the rest of the call around a specific shift.

### Step 2: Confirm out loud what the application claimed

Three claims are worth the seconds: **availability block by block** ("Can you work Sunday to Wednesday nights, 10pm to 6:30am?", never "is your availability still correct?", which gets a yes from everybody); **the earliest shift by name**; and **the journey**, asked as "how would you get here for a 10pm start", never "can you get here". A route with a time in it is a different answer from "yeah, it's fine". Everything else is taken at face value. A screen is not an audit.

### Step 3: Decide on the call

Three gates, and only three: availability overlap, a genuine prerequisite, the answer after the preview. Any one failing ends the call politely, there and then, in words written into the script so every caller says it the same way. Everything else advances. Partial availability is a routing outcome, not a rejection: "our Kettering store is short of weekend day shifts". The candidate gets an answer on the phone, the largest single difference between a screen people complete and one they abandon.

### Step 4: End with a booked slot, or the call has not finished

Two specific slots, not "when suits you?": two options get chosen, an open question gets postponed. Then a confirmation text with when, where and who to ask for, sent before hanging up. A screen ending in an intention hands the candidate to whichever employer books properly.

### Step 5: Write the path most calls actually take

At frontline volume most attempts don't reach anyone, so the script includes:

- **A voicemail under twenty seconds** naming the company and the job, with a way back: a text-back number or a booking link. People who missed your call text; they do not ring an unknown number.
- **A text after every voicemail**, under two text segments, with an opt-out. The text gets read; the voicemail does not.
- **An attempt rule**: two to five calls, spread across mornings, afternoons and evenings. Someone on nights is asleep at 2pm.
- **A stop rule**, so nobody sits in the queue forever.
- **A script for the callback**, because whoever answers has no idea what the call is about.
- **Five fields to write down**, at most.

### Step 6: Check it

The check blocks the script, with the reason, when any of these fails:

| Rule | Blocks |
|---|---|
| Order and length | a missing section, availability after anything but the opener, over five minutes read aloud with answers |
| Opener | more than two sentences, no company or length, "tell me about yourself" |
| Availability | fewer questions than shift gaps, no day or time named, "still correct?", no gate |
| Travel | no "how would you get here" question |
| Prerequisites | anything but a minimum age, a licence or certificate, work authorization |
| Every question | assessment ("tell me about a time", strengths, "why do you want"); age, citizenship, family and childcare, health, religion, arrests, pay history |
| Preview | over thirty seconds, empty, or no gate after it |
| Decision | a gate anywhere else, no wording for each no, no redirect, "we'll be in touch" |
| Booking | fewer than two slots, no confirmation, a confirmation missing when, where or who |
| Pay | never stated |
| Unanswered path | voicemail too long, unnamed or with no way back; no text, too long, no opt-out; attempts in one part of the day; no stop rule; no callback script; more than five capture fields |

### Step 7: Read the call log

Once the calls happen, a log with one row per attempt (`candidate_id, caller_id, applied_at, attempt_at, outcome`, and if you have them `result, booked, interview_at, showed, texted`) shows what decides whether a better script changes anything:

- **Speed**: booked rate by hours to first call. Frontline applicants apply to several employers in one sitting, so calling first beats scripting well.
- **When people answer**, by part of the day, and whether most attempts go out when people answer least.
- **The text after a voicemail**: how many come back with and without one.
- **Callers** whose calls end with no decision, or whose advanced candidates leave unbooked.
- **Shows**, for interviews within two days of the call and further out.
- **Limbo**: never reached, called fewer times than the rule, nothing for a week; and anyone called more.

A comparison is stated only with at least 30 in each group and 90% ranges that do not overlap; otherwise I say the log cannot separate them.

## What you get

1. **The script**, word for word, in running order: READY, or the exact list of what to fix.
2. **The call sheet**, one printable page with the gates marked, the no and the redirect, the booking line, the voicemail, the text, the attempt rule and the fields to write down.
3. **The call-log read**, when you have one.

```bash
python3 scripts/screen.py --script script.json --html sheet.html
python3 scripts/screen.py --calls calls.csv --max-attempts 3 --html calls.html
```

## What I will push back on

**"Can we add a question about their experience?"** That is the interview. It costs ninety seconds a call and cannot be scored in five minutes.

**"Can we ask whether they have childcare for nights?"** No. Ask whether they can work the nights, and stop there. The check blocks family, age, citizenship, health, religion, arrest and pay-history questions wherever they appear.

**"The script is fine, people just don't answer."** Then read the log: if most attempts go out at 2pm and nobody follows a voicemail with a text, the wording is not the problem.

## Verifying this yourself

```bash
python3 scripts/screen.py --test
```

The sample script must pass. 59 damaged copies of it (`references/fixtures/broken_scripts.json`) must each be blocked for the right reason, or refused as malformed. The sample call log was generated with known answers by `references/sample/generate_calls.py`: calling within 4 hours books more, evenings answer best while most calls go out in the afternoon, a text after voicemail brings more people back, one caller lets advanced candidates go unbooked, another ends calls with no decision, near interviews show better, and a known number sit in limbo. The suite checks each comes back, and that the same log with outcomes and bookings shuffled is never read as speed or texting mattering.

## Works with

- **`structured-interview-guide`** in this library writes the interview this call books.
- **`recruiter-capacity-planner`** ranks booking and reminders among the tasks worth automating.
- **The Fountain Cue MCP.** When connected, it can supply the open interview slots for the booking line and this week's call attempts per candidate, so the log is read as it fills rather than from an export. Fountain publishes this skill and sells Cue. The script, the check and the numbers are identical either way, and the skill works completely without it.

## Where this stops

This writes and checks words; it cannot hear a call, so it cannot tell a script problem from a caller who does not use the script. The list of risky topics catches common wording, not every way to ask an unlawful question, and it is not legal advice: what may be asked, and whether you may text a candidate, depends on where you hire and on the consent you collected. Have someone who knows your local rules read the script once. The call-log read describes calls that happened; it changes nothing, and planted effects in the sample are illustrations, not benchmarks for your team.
