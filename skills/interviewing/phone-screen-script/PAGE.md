# Phone Screen Script: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/screen.py --script references/sample/northline_script.json

## Example prompt

> Write our phone screen for overnight stockers at the Dayton store. We're short Sunday to Wednesday nights and Thursday and Friday nights, 10pm to 6:30am. Pay is $17.50 an hour plus $1.50 for nights, paid weekly. It's on your feet all night, lifting cases up to 40 pounds, and the back room is cold in winter. Candidates must be 18 and authorized to work in the US. If nights don't work for someone, our Kettering store needs weekend day shifts, Saturday and Sunday 7am to 3:30pm.

## Example output

From the skill's demo: the worked example it ships for this brief (`references/sample/northline_script.json`, a fictional grocer), and its checker's verdict. An excerpt.

**Opener:** "Hi, this is {caller} from Northline, about the overnight stocker job you applied for at our Dayton store. It takes about five minutes, is now still a good time?"

**Availability first, because it decides everything else**

1. "We need people Sunday to Wednesday nights, 10pm to 6:30am. Can you work those four nights?" *(gate)*
2. "We also have Thursday and Friday nights, same hours. Can you do either of those?" *(gate)*

**The honest preview:** "It is overnight, on your feet the whole shift, lifting cases up to 40 pounds, and the back room is cold in winter. Pay is $17.50 an hour, plus $1.50 an hour for nights, paid every week. Knowing that, do you still want it?" *(gate)*

**If the nights don't work:** "Our Kettering store is short of weekend day shifts, Saturday and Sunday 7am to 3:30pm, same pay. If those suit you, I can book you there instead, right now."

**The close:** "I can do {slot_1} or {slot_2} at the store, about twenty minutes with {interviewer}. Which works?" Then a confirmation text, and a three-call stop rule: evening, morning, afternoon, then a last-chance text. No fourth call.

**Checker:** 8 questions, about 140 seconds read aloud with answers. READY to dial.
