# Candidate Message Sequencer: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/sequencer.py --check references/sample/northline_applied_sms.txt

## Example prompt

> Applicants keep going quiet after applying and never book the screening call. Write me the follow-up text sequence for our night stocker roles. The call takes ten minutes, and night stockers make $17.50 an hour plus $1.50 for nights.

## Example output

From the skill's demo: the worked example it ships for this brief (`references/sample/northline_applied_sms.txt`, a fictional grocer), and its checker's verdict on the whole sequence.

**Stage:** applied, no screening call booked. **Stops when:** the candidate books a call, or replies STOP.

| When | Message |
|---|---|
| Day 0, 10:00 | Hi {first_name}, it's Northline. Thanks for applying for night stocker at {site}. Pick a 10-min call: {link}. Reply STOP to opt out. |
| Day 2, 17:30 | {first_name}, Northline again. Night stocker pays $17.50 an hour, plus $1.50 for nights. Book a call: {link} |
| Day 5, 12:00 | Hi {first_name}. Hard to fit a call in? Text us a good time and Northline will ring you. |

**Checker:** 3 messages over 5.1 days. No findings against its rules on spacing, quiet hours, length, the opt-out, naming the sender, repeated messages, false urgency and sensitive asks. READY TO SEND.

Each message says something new (the job, then the pay, then an easier way in) instead of repeating the first one louder.
