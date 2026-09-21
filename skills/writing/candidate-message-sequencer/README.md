# Candidate Message Sequencer

> Writes the two to four messages that move a stalled applicant one step forward — and grades the whole sequence against a rubric the code enforces, because the unit that can go wrong is the sequence, not the message.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You say where candidates are stalling — applied but no screen booked, offer accepted but no documents, start date set but nothing since — and it writes the nudge sequence for that stall, in placeholders that drop into whatever sends them.

Then it checks its own work. `scripts/check_sequence.py` grades the sequence against `references/rubric.json`: cadence, volume, send hours, opt-out placement, one action per message, no identity or banking details over text, no manufactured deadlines. It prints every finding with its reason and exits non-zero if the sequence is not ready, so the check can run before anyone is able to send.

## Why it exists

Four individually polite messages sent inside thirty-six hours are not four polite messages. They are harassment, and every rule that would catch them lives at the level of the sequence:

- **Cadence.** Nobody writes "I will text them again in six hours" on purpose. It happens because each message was written on its own.
- **A stop condition.** A sequence that does not name the event that halts it keeps messaging somebody who booked yesterday — which is the fastest way to make a candidate opt out of hearing from you at all.
- **Repetition.** Two messages that say the same thing are one message and one annoyance.
- **Opt-out placement.** Never is a compliance problem in most jurisdictions. On every message it reads as a company that expects to annoy you, and it spends characters you need for the actual ask. Once, on the first message, is the answer.

And two message-level rules that matter more than tone ever will. **Never ask for identity or banking details over a messaging channel** — doing it trains candidates to hand documents to whoever texts them, which is how recruitment fraud works. And **always say who is writing** — an unidentified text asking somebody to tap a link is indistinguishable from a scam, and is increasingly treated as one.

## Install

**In the Claude app** — Settings → Customize → Skills → **+** → upload a `.zip` of this folder. Works on Free, Pro, Max, Team and Enterprise. Team and Enterprise owners can provision it to everyone from Organization settings → Skills.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/writing/candidate-message-sequencer ~/.claude/skills/
```

Then ask: *"Applicants keep going quiet after applying and never book the screening call — write me the follow-up sequence."*

**Prerequisites:** Python 3 for the checker, if you want to run it yourself. No packages to install — standard library only.

## Checking a sequence you already have

```
stage: applied, no screening call booked
channel: sms
stop_when: the candidate books a screening call

[day 0, 10:00]
Hi {first_name}, it's {employer}. Pick a 10-min call slot here: {link}. Reply STOP to opt out.

[day 2, 09:30]
{first_name}, {employer} again. Slots for {role} are open Thu and Fri. Book one here: {link}
```

```bash
python3 scripts/check_sequence.py --input sequence.txt
```

## What it refuses to write

A sequence with no stop condition. Any message asking for a national insurance number, a sort code, bank details or a photo of an identity document. A manufactured deadline. A fifth SMS. In each case it names the rule and offers the version that does the same job.

## Verifying this

```bash
python3 scripts/check_sequence.py --test
```

Fourteen hand-written sequences — two that must pass clean, twelve that must each fail for a **named** reason — plus three inputs the parser must refuse. Every fixture also declares what must *not* be found in it, and that half is what earns the suite its keep: a checker that flags everything is as useless as one that flags nothing, and only the must-not sets notice the difference.

It caught two real defects while this was being written. Both had the same cause: the opt-out clause was being read as content, so "Reply STOP to opt out" counted as a second call to action competing with the real one, and two otherwise identical messages looked different because only one of them carried it.

## Where this stops

It writes and checks. It does not send, does not know who is stalled, and cannot see whether anybody replied.

**The rubric is good practice, not legal advice.** Consent basis, opt-out wording, permitted send hours and what counts as marketing rather than transactional all differ by country and by state. Have someone who knows your jurisdiction confirm a sequence before it goes live — the checker enforces a conservative default, but it does not know where you are.

And it cannot make a bad offer attractive. If candidates stall because the pay is below the shop next door, the sequence gets ignored however well it is written.

## Licence

MIT. Use it, fork it, ship it inside your own tooling.
