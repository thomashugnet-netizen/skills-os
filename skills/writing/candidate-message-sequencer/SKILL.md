---
name: candidate-message-sequencer
description: Builds short SMS, WhatsApp and email nudge sequences for applicants who stall between applying and their first shift, and checks them against a written rubric before you send.
version: 1.0.0
---

# Candidate Message Sequencer

## What this does

Writes the two to four messages that move a stalled applicant one step forward — and then grades the whole sequence against a rubric the code enforces, so you can see it is respectful rather than take my word for it.

The unit here is the **sequence**, not the message. That distinction is the whole skill. Four individually polite messages sent inside thirty-six hours are not four polite messages; they are harassment. A sequence that never says what stops it keeps texting somebody who booked yesterday. No amount of care per message catches either.

## Where a sequence belongs

Frontline funnels stall at four predictable places. Each one needs a different ask, and none of them needs more than four messages.

| Stall | What the sequence is for | Channel that works |
|---|---|---|
| Applied, no screen booked | Get a ten-minute slot in the diary | SMS |
| Screen done, no interview booked | Get the site visit scheduled | SMS or WhatsApp |
| Offer accepted, documents missing | Get two documents uploaded | Email, SMS reminder |
| Start date set, no first shift yet | Keep the start date real | SMS |

If you tell me which of these you are in, I will ask for the three or four facts that make the messages specific — the role, the site, the pay, what the next step actually is — and write the sequence. If you already have one, paste it and I will check it.

## What I need from you

- **The stall.** Which of the four above, or describe it.
- **The channel.** SMS, WhatsApp or email. It changes the length cap, the opt-out rule and the tone.
- **The stop condition.** What event means this person should stop hearing from us. I will not write a sequence without one.
- **The specifics.** Role, site, pay, shift pattern, what the next step is and how long it takes. Vague messages get ignored, and no amount of sequencing fixes that.

I write in placeholders — `{first_name}`, `{employer}`, `{role}`, `{site}`, `{link}` — so the sequence drops into whatever sends it. I never ask you for a candidate's actual details, and you should not paste them here.

## The rules I hold myself to

These live in `references/rubric.json` and are enforced by `scripts/check_sequence.py`. If a rule is in the rubric and not in this document, one of the two is wrong.

**At the level of the sequence**

- **A stop condition, always.** The sequence names the event that halts it.
- **At most four messages** on SMS and WhatsApp, five on email. Past that, reply rates fall and opt-out rates rise: you are spending future contactability on somebody who has already decided.
- **At least twenty hours between messages**, and the whole sequence inside three weeks. A second nudge before someone has had a working day to see the first is the same message to them.
- **No sends before 8am or after 8pm.** Shift workers sleep at hours office workers do not. A 6am text reaches somebody who finished at two.
- **Every message adds something** — new information, a different action, or a reason the timing changed. Two messages that say the same thing are one message and one annoyance.
- **The opt-out appears once, on the first message.** Not never, which is a compliance problem in most places and the reason people block the number. Not every time, which reads as a company that expects to annoy you and spends characters you need for the ask.

**At the level of the message**

- **One action.** Every message exists to make one specific thing easy. Three ways to respond is a decision, and a decision is what this candidate is already not making.
- **Say who is writing.** An unidentified text asking somebody to tap a link is indistinguishable from a scam, and is increasingly treated as one.
- **Never ask for identity or banking details over a message.** Not a national insurance or social security number, not a sort code, not a photo of a document. Collecting those by text trains candidates to hand identity documents to whoever asks, which is precisely how recruitment fraud works. Link to your own system and let them authenticate.
- **No manufactured urgency.** If the deadline is real, give the date. If it is not, "final warning" is a threat sent to somebody deciding whether to trust you as an employer.
- **Grade 8 reading level or below**, short sentences, at most one exclamation mark, no shouting. This is read on a phone, often in a second language, often between shifts.

## What I will not write

A sequence with no stop condition. A message asking for documents or bank details by text. Anything that manufactures a deadline that does not exist. A fifth SMS.

If you ask for one of these, I will say which rule it breaks and offer the version that does the same job — usually a link to a place where the ask is safe, or one honest sentence about a real deadline.

## Checking a sequence you already have

Save it in this shape and run the checker:

```
stage: applied, no screening call booked
channel: sms
stop_when: the candidate books a screening call

[day 0, 10:00]
Hi {first_name}, it's {employer}. Thanks for applying for {role} at {site}. Pick a 10-min call slot here: {link}. Reply STOP to opt out.

[day 2, 09:30]
{first_name}, {employer} again. Slots for {role} are open Thu and Fri. Book one here: {link}
```

```bash
python3 scripts/check_sequence.py --input sequence.txt
```

It prints each finding with the reason, and ends with `READY TO SEND` or the list of what is blocking. It exits non-zero when the sequence is not ready, so it drops into a pipeline if you want the check to run before anyone can send.

## Verifying this yourself

Run `python3 scripts/check_sequence.py --test`. Fourteen hand-written sequences: two that must pass clean, twelve that must each fail for a **named** reason — too many messages, two in six hours, a 6.45am send, no opt-out, an opt-out on every message, a request for a sort code, a manufactured final warning, a repeated message, a missing stop condition, an unsigned message, an SMS over the limit, and one that shouts. Plus three inputs the parser must refuse.

Each fixture also declares what must *not* be found in it, and that half is what earns the suite its keep: a checker that flags everything is as useless as one that flags nothing, and only the must-not sets notice the difference. Two real defects were caught that way while this was being written — the opt-out clause was being counted as a second call to action, and it was making two otherwise identical messages look different.

## Works with

- **Any sending tool** — the output is plain text with placeholders, so it drops into an ATS campaign, a CRM, or a spreadsheet mail-merge.
- **The Fountain Cue MCP** — when connected, it can tell you which candidates are actually stalled at each of the four stages, so the sequence goes to the right list. Fountain publishes this skill and sells Cue; the rubric, the checker and the writing are identical either way, and the skill works completely without it.
- **`funnel-drop-off-analyst`** — that skill finds which stall is costing you the most hires. This one writes the messages for it.

## What it costs you to run

Counted at 40 sites and about 60 live openings, four stalls, three channels. Swap your own numbers in.

**Standing up the sequences.** Four stalls times two channels is eight sequences, each three to four messages, so roughly thirty messages to write. Each one then has to be loaded into whatever sends it, which means a different console per channel, its own placeholder syntax, and a test send to a real handset because the character count in the editor and the character count on a phone are not the same number. At twenty minutes per sequence including the test send, about three hours — then again for every role family whose pay or shift pattern makes the wording wrong.

**Keeping them true.** A pay rise, a new shift pattern or a moved start date does not edit one sequence. It edits every sequence that quotes the old number, in every console that holds a copy, and the ones you miss keep texting the old figure to people who then arrive expecting it. Same arithmetic for a site that closes a role: a nudge sequence still running against a filled opening produces candidates you have to turn away, which costs the rejection and the goodwill.

**Running them by hand instead.** The alternative most estates are actually on is a coordinator working a list. At 1,500 applications a month across the estate and roughly a third stalling somewhere, that is 500 people needing two or three messages each — 1,200 sends, typed or pasted individually, at maybe forty seconds each with the lookup. About thirteen hours a month, every month, and it is the first thing dropped in a peak, which is exactly when the stalls are worst.

**Checking they are still safe.** Send hours, opt-out wording and consent basis change when you enter a new state or country, and each change means re-reading every live sequence. The checker makes that a command rather than a meeting, but somebody still has to decide the rules changed.

## Where this stops

It writes and checks the messages. It does not send them, does not know who is stalled, and cannot see whether anybody replied.

The rubric encodes good practice, **not legal advice**. Messaging rules for recruitment differ by country and by state — consent, opt-out wording, permitted hours, and what counts as a marketing message rather than a transactional one all vary. Before a sequence goes live, have someone who knows your jurisdiction confirm: that your consent basis covers this contact, that your opt-out wording is the one your regulator expects, that your send hours are inside local rules, and that your retention of the reply data is covered. The checker enforces a conservative default; it does not know where you are.

And it cannot make a bad offer attractive. If candidates stall because the pay is below the shop next door or the shift pattern is impossible, the sequence will be ignored no matter how well it is written, and the honest read of a sequence that gets no replies is usually that the problem was never the messaging.
