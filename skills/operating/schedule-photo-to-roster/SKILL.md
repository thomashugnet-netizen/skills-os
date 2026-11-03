---
name: schedule-photo-to-roster
description: Turns a photo or screenshot of a shift schedule into a clean roster, then shows where the week is short-staffed, who is heading into overtime, who closes and opens with too little rest, and which hours could move.
version: 1.0.0
---

# Schedule Photo to Roster

> **This is not legal advice.** It checks a schedule against overtime and rest-between-shifts thresholds so you can prepare, not so you can rely on it. Those rules depend on where you operate and on whether your business is covered, they change, and the rules file in this skill does not. Every threshold in `references/rules.json` names the official page to read and the date it was checked. Work from that page, and from someone who knows your jurisdiction, before acting on a finding.

## What this does

You photograph the schedule pinned in the back room, or screenshot the one in your spreadsheet, and I turn it into a roster you can use: one row per shift, every time in 24-hour form, every unclear cell marked. Then a script checks the week hour by hour.

The insight is that a schedule's problems are invisible on the sheet. Nobody writing it sees that Sunday evening has one person on the floor, that the Friday closer is back at six on Saturday, or that one lead is at 46 hours while another sits at 31. A grid of names and times hides all three. Laid out by the hour, they are obvious.

## What to give me

Essential:

- **The schedule.** A photo, a screenshot, a PDF page or a spreadsheet. Phone photos of paper are fine. Straight on and in focus helps; I will tell you which cells I could not read.

Better, if you have them:

- **What you need on the floor.** "3 people from 7 to 11, 4 until close, always one shift lead." Without it I can only show gaps and people working alone. With it I can say where you are short and where you have more people than you asked for.
- **Where you operate.** A state or city changes the overtime and rest thresholds. Run `python3 scripts/roster.py --list-rules` for the ones I know.
- **An average hourly rate**, if you want the overtime premium as money rather than hours.

**No schedule handy?** Ask for the demo. I read `references/sample/northline_store14_photo.jpg`, a fictional store's week, exactly as I would read yours.

## Before you send the photo

A schedule needs first names or initials. It never needs a way to reach anyone. If phone numbers, emails or addresses are on the sheet, crop them out or let me ignore them: I will not copy them into the roster, and the script refuses any file that contains them.

## How I work

### Step 1: Read the photo

I follow `references/extraction.md`. I transcribe rather than correct: two times in one cell become two shifts, because that is what the sheet says and it may be the problem. I never guess a time. Am and pm come from the store hours and the pattern on the sheet, and I say which one decided it. A cell I am not sure of keeps my best reading and is marked low confidence.

### Step 2: Read it back, and wait

I show you the roster in the same layout as your sheet, with every uncertain cell marked, and ask you to confirm it. This step is never skipped. A misread time becomes a finding with a confident number beside it, and it is cheaper to fix a cell than to argue with a report.

### Step 3: Check the week

`scripts/roster.py` does the arithmetic, not me. Same roster, same findings, every run. In order:

1. **The roster itself.** Cells to confirm, the same shift written twice, a shift too long to be real.
2. **Conflicts.** The same person in two places at once. One of the two shifts is not real, and the coverage built on it is not either.
3. **Coverage,** in 15-minute slots: short of your need, a role missing, nobody on, one person alone.
4. **People.** Overtime under the rules you chose, short rest between a close and an open, seven days without a day off, long shifts with no break written down.
5. **Surplus.** Two or more people above your need for two hours or more. One extra at a handover is how shifts overlap, not waste.

### Step 4: Say what to move

Each problem comes with the move that fixes it where the schedule already holds the answer. On the sample week, Tuesday midday carries 18.5 person-hours above need while Sunday evening is 9.5 short with no shift lead. The fix is not a new hire.

## What you get

1. **The readback,** to confirm before anything else.
2. **The clean roster** as a CSV, ready to paste into a spreadsheet or import into a scheduling tool.
3. **A one-page report** (`--html`): the headline numbers, the week as an hour-by-hour grid coloured by shortfall, every finding, and hours per person against the overtime line.
4. **The fix list,** in the order to do it: confirm, resolve conflicts, cover the gaps, then rebalance hours.

Run it yourself:

```bash
python3 scripts/roster.py --roster roster.csv --needs needs.csv --rules oregon --rate 17.50 --html report.html --clean roster_clean.csv
```

## What I will push back on

- **Fixing overtime by moving it to next week.** The hours are still there, and so is the person working them.
- **Calling a 7-hour turnaround fine because they asked for it.** Where a local rule applies, consent usually changes the cost, not the rule. Where none does, a close followed by an open is the shift pattern people quit over.
- **A schedule with no needs attached.** Without a target, "short" means nothing. Two lines of needs turn this from a tidy roster into an answer.

## Verify before you rely on it

Confirm against the official source for each place you operate:

- whether your business is covered by a local scheduling law, given its industry and size
- the minimum rest between shifts there, and what happens when someone works inside it
- how overtime is counted: by week, by day, or both, and whether a seventh consecutive day changes it
- what your meal and rest break rules require for the shift lengths you use
- whether any of the above changed after the date in `references/rules.json`

## Works with

- **Any spreadsheet or scheduling tool.** The clean roster is a plain CSV.
- **The Fountain Cue MCP.** When connected, the same confirmed roster can become shift templates and live shifts, so the schedule you just checked is the one that gets published. Fountain publishes this skill and sells Cue. The reading, the checks and the report are identical either way, and the skill works completely without it.

## Where this stops

It reads one schedule at a time and checks it as written. It cannot see who actually turned up, who swapped informally, or what was changed after the photo was taken. It knows the thresholds in its rules file and nothing about your union agreement, your contracts or your own policies. And it cannot tell you what you need on the floor. If the needs you give it are wrong, every shortfall it reports is wrong with them.
