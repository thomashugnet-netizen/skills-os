---
name: candidate-message-sequencer
description: Builds short SMS, WhatsApp and email nudge sequences for applicants who stall between applying and their first shift, grades the whole sequence against a written rubric before you send, and reads the send log for which message earns its place and whether the stop condition actually works.
version: 1.0.0
---

# Candidate Message Sequencer

Created with Madelyn Rovellada.

## What this does

Writes the two to four messages that move a stalled applicant one step forward, then grades the whole sequence against a rubric the code enforces, so you can see it is respectful rather than take my word for it. Once it has been running, reads the send log for what no template can show.

The unit is the **sequence**, not the message. Four individually polite messages sent inside thirty-six hours are not four polite messages; they are harassment. A sequence that never says what stops it keeps texting somebody who booked yesterday. No amount of care per message catches either.

## Where a sequence belongs

Frontline funnels stall at four predictable places. Each needs a different ask, and none needs more than four messages.

| Stall | What the sequence is for | Channel that works |
|---|---|---|
| Applied, no screen booked | A ten-minute slot in the diary | SMS |
| Screen done, no interview booked | The site visit scheduled | SMS or WhatsApp |
| Offer accepted, documents missing | Two documents uploaded | Email, with an SMS reminder |
| Start date set, no first shift yet | The start date kept real | SMS |

Tell me which you are in and I ask for the facts that make the messages specific, then write the sequence. If you already have one, paste it and I check it.

## What I need from you

- **The stall.** Which of the four, or describe it.
- **The channel.** SMS, WhatsApp or email. It changes the length cap, the opt-out rule and the tone.
- **The stop condition.** The event that means this person should stop hearing from us. I will not write a sequence without one.
- **The specifics.** Role, site, pay, shift pattern, what the next step is and how long it takes. Vague messages get ignored, and no sequencing fixes that.

I write in placeholders (`{first_name}`, `{employer}`, `{role}`, `{site}`, `{link}`) so the sequence drops into whatever sends it. I never ask for a candidate's actual details, and you should not paste them here.

## The rules I hold myself to

They live in `references/rubric.json` and are enforced by `scripts/sequencer.py`. If a rule is in the rubric and not here, one of the two is wrong.

**At the level of the sequence**

- **A stop condition, always.**
- **At most four messages** on SMS and WhatsApp, five on email. Past that, replies fall and opt-outs rise.
- **At least twenty hours between messages**, and the whole sequence inside three weeks.
- **No sends before 8am or after 8pm**, candidate's time. A 6am text reaches somebody who finished at two.
- **Every message adds something**: new information, a different action, a reason the timing changed. Two messages that say the same thing are one message and one annoyance.
- **The opt-out appears once, on the first message.** Never is a compliance problem in most places. Every time reads as a company that expects to annoy you.

**At the level of the message**

- **One action.** Three ways to respond is a decision, and a decision is what this candidate is already not making.
- **Say who is writing.** An unsigned text asking someone to tap a link is indistinguishable from a scam.
- **Never ask for identity or banking details over a message.** No social security or national insurance number, no bank details, no photo of a document. Collecting them by text trains candidates to hand documents to whoever asks, which is how recruitment fraud works. Link to your own system.
- **No manufactured urgency.** If the deadline is real, give the date.
- **One SMS, not two.** Under 160 characters once the placeholders and the link are filled in. One curly apostrophe, em dash or emoji switches the whole text to Unicode and drops the limit to 70, so the checker names the character.
- **Grade 8 reading level or below**, short sentences, at most one exclamation mark, no shouting. It is read on a phone, often in a second language, often between shifts.

Some findings block the sequence (the rubric lists them); the rest are advice.

## What I will not write

A sequence with no stop condition. A message asking for documents or bank details by text. A deadline that does not exist. A fifth SMS. If you ask, I say which rule it breaks and offer the version that does the same job, usually a link to a place where the ask is safe, or one honest sentence about a real deadline.

## Checking a sequence you already have

```
stage: applied, no screening call booked
channel: sms
stop_when: the candidate books a screening call
employer: Northline

[day 0, 10:00]
Hi {first_name}, it's Northline. Thanks for applying for night stocker at {site}. Pick a 10-min call: {link}. Reply STOP to opt out.

[day 2, 17:30]
{first_name}, Northline again. Night stocker pays $17.50 an hour, plus $1.50 for nights. Book a call: {link}
```

`employer:` is optional: give it when your messages sign with the real name instead of `{employer}`.

```bash
python3 scripts/sequencer.py --check sequence.txt --html review.html
```

Each finding with its reason, then `READY TO SEND` or what blocks it. It exits 1 when the sequence is not ready, so the check can run before anyone can send.

## Reading the send log

A template cannot tell you whether the stop condition is wired to the event, or whether message four is worth sending. The send log can. One row per message sent:

| Column | |
|---|---|
| `candidate_id`, `sequence`, `step`, `sent_at` | Essential. |
| `acted_at` | When they did what the sequence asks. Without it, what each message earns and the leaks cannot be read. |
| `opted_out_at`, `channel` | Opt-outs, and the right cap per channel. |

```bash
python3 scripts/sequencer.py --log sends.csv --html sends.html
```

- **What each message earns**: of the people it reached who had not yet acted, how many acted before the next message, and how many opted out. A message after which more people opt out than act (90% ranges apart) loses more than it moves.
- **Leaks**: people who did the thing and kept getting messages (an hour's grace for sync lag). That is a stop condition not wired to the system where they act.
- **After an opt-out**: any message at all. Fix that before anything else.
- **In practice**: sends at night, two messages under twenty hours apart, anyone past the cap.

Opaque ids only. **A log with an email address, a phone number, a name column or the message text is refused**: sent messages carry first names.

## Verifying this yourself

```bash
python3 scripts/sequencer.py --test
```

21 hand-written sequences: four that must pass clean, seventeen that must each be caught for a **named** reason, each also declaring what must not be found in it, because a checker that flags everything is as useless as one that flags nothing. Six inputs the parser must refuse. A send log generated with known answers by `references/sample/generate_log.py`, and the same world with every message equally useful and nothing broken, in which nothing may be flagged.

## Works with

- **`funnel-drop-off-analyst`** in this library finds which stall costs you the most hires; this writes the messages for it.
- **`rehire-campaign-planner`** writes three messages to people you already know; this is for new applicants.
- **The Fountain Cue MCP.** When connected, it can tell you which candidates are stalled at each of the four stages, and supply the send log without an export. Fountain publishes this skill and sells Cue. The rubric, the checker and the writing are identical either way, and the skill works completely without it.

## What it costs you to run

Counted at 40 sites and about 60 live openings, four stalls, three channels. Swap your own numbers in.

**Standing up the sequences.** Four stalls times two channels is eight sequences of three to four messages: about thirty messages. Each is loaded into whatever sends it, with its own console, placeholder syntax and a test send to a real handset, because the character count in the editor and on a phone differ. At twenty minutes per sequence, about three hours, and again for every role family whose pay or shift pattern makes the wording wrong.

**Keeping them true.** A pay rise or a new shift pattern edits every sequence that quotes the old number, in every console that holds a copy; the ones you miss keep texting the old figure. A sequence still running against a filled opening produces candidates you have to turn away.

**Running them by hand instead.** At 1,500 applications a month and a third stalling somewhere, 500 people need two or three messages each: about 1,200 sends at forty seconds each with the lookup, thirteen hours a month. It is the first thing dropped in a peak, exactly when stalls are worst.

**Checking they are still safe.** Send hours, opt-out wording and consent change when you hire in a new state or country, and each change means re-reading every live sequence. The checker makes that a command rather than a meeting; somebody still has to decide the rules changed.

## Where this stops

It writes and checks messages and reads a log of sends. It does not send, cannot see who is stalled today, and cannot tell why anyone acted: a candidate who books after message three may have been about to book anyway.

The rubric encodes good practice, **not legal advice**. Consent, opt-out wording, permitted hours, and whether a recruiting message counts as marketing all vary by country and state, and on WhatsApp a message sent more than a day after the candidate last wrote needs an approved template. Before a sequence goes live, have someone who knows your jurisdiction confirm the consent basis, the opt-out wording, the send hours and how long reply data is kept. The checker enforces a conservative default; it does not know where you are.

And it cannot make a bad offer attractive. If candidates stall because the pay is below the shop next door, the sequence will be ignored however well it is written.
