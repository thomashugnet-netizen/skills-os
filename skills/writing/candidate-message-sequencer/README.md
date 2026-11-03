# Candidate Message Sequencer

> Writes the two to four messages that move a stalled applicant one step forward, grades the whole sequence against a rubric the code enforces, and reads the send log for which message earns its place, because the unit that goes wrong is the sequence, not the message.

Created with Madelyn Rovellada. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**Writes** the nudge sequence for the place candidates stall (applied but no screen booked, screen done but no interview, offer accepted but no documents, start date set but nothing since) in placeholders that drop into whatever sends them.

**Checks** it. `scripts/sequencer.py` grades the sequence against `references/rubric.json`: a stop condition, the cap per channel, twenty hours between messages, no sends at night, opt-out once on the first message, one action per message, who is writing, no identity or banking details by text, no manufactured deadline, one SMS part once the link is filled in, including the curly apostrophe that silently halves the limit. It exits non-zero when the sequence is not ready, so the check can run before anyone can send.

**Reads the send log** once it runs: what each message earns in actions against opt-outs, people who did the thing and kept getting messages, anything sent after an opt-out, sends at night, too close together or past the cap.

## Why it exists

Four individually polite messages sent inside thirty-six hours are harassment, and every rule that would catch them lives at the level of the sequence. A sequence that does not name the event that stops it keeps messaging somebody who booked yesterday. And even a good template is only as good as its wiring: if the stop condition is not connected to the system where candidates act, they keep getting reminders after doing what was asked.

On the demo, two months of messages at a fictional retailer across four stalls: the fourth message of the application sequence is followed by 8% opt-outs and 2% actions, so it loses more people than it moves; 35% of people who uploaded their documents kept getting reminders, because the upload happens in another system; 7 messages went to people who had already opted out; one sequence sends every message at 07:15.

## Install

**1. Download** [candidate-message-sequencer.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/candidate-message-sequencer.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the message sequencer demo."* Then: *"Applicants keep going quiet after applying and never book the screening call. Write me the follow-up sequence."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/writing/candidate-message-sequencer ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | What | |
|---|---|---|
| sequence | a text file: `stage`, `channel`, `stop_when`, then `[day N, HH:MM]` blocks | written with you |
| send log | `candidate_id, sequence, step, sent_at` + `acted_at, opted_out_at, channel` | optional |

A send log with an email address, a phone number, a name column or the message text is refused: sent messages carry first names.

## What it refuses to write

A sequence with no stop condition. Any message asking for a social security or national insurance number, bank details or a photo of an identity document. A manufactured deadline. A fifth SMS. In each case it names the rule and offers the version that does the same job.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | High application volume, stalls at every stage, SMS the channel candidates read. |
| Quick-service restaurants | Strong | Applicants go quiet within hours; the first message does most of the work. |
| Logistics and warehousing (W2) | Strong | Document and start-date stalls, shift workers who sleep in the day. |
| Healthcare support (CNA, home care) | Partial | Credential uploads fit the documents stall; licensing steps happen outside the sequence. |
| Salaried or professional hiring | Limited | Candidates expect a person, not a sequence; email etiquette differs. |

## Verifying this yourself

```bash
python3 scripts/sequencer.py --test
```

112 checks. 21 hand-written sequences: four that must pass clean, seventeen that must each be caught for a **named** reason, and every one also declares what must *not* be found in it: a checker that flags everything is as useless as one that flags nothing, and only the must-not half notices. Six inputs the parser must refuse. A send log generated with known answers by `references/sample/generate_log.py`, and the same world with every message equally useful and nothing broken, in which nothing may be flagged. Before release, 6,000 damaged sequences and send logs ran without a crash.

Exit codes: 0 sequence ready or log read, 1 sequence not ready, 3 input refused, 4 the engine itself failed.

## Where this stops

It writes, checks and reads a log. It does not send, does not know who is stalled today, and cannot tell why anyone acted.

**The rubric is good practice, not legal advice.** Consent basis, opt-out wording, permitted send hours and what counts as marketing differ by country and state, and WhatsApp needs approved templates for most follow-ups. Have someone who knows your jurisdiction confirm a sequence before it goes live.

And it cannot make a bad offer attractive. If candidates stall because the pay is below the shop next door, the sequence gets ignored however well it is written.

## Who it's for

- **Recruiting coordinators** who chase stalled applicants by hand today.
- **Recruiting operations** setting up automated sequences in an ATS or messaging tool.
- **Talent acquisition leads** who want proof the sequences are respectful before they go live.
