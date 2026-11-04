# Schedule Photo to Roster

> Turns a photo of the schedule pinned in the back room into a clean roster, then shows, hour by hour, where the week is short-staffed, who is heading into overtime and who closes and opens with too little rest.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

You take a photo of the schedule, or a screenshot of the spreadsheet, and ask:

> "Here's next week. Are we covered?"

Claude reads the photo, shows you what it read with every unclear cell marked, and waits for you to confirm. Then a script checks the week in 15-minute slots: where you are short of what you need, where a role is missing, who is past the overtime line, who has under ten hours between a close and the next open, who works seven days straight, and where hours could move from a quiet day to a short one.

The checks are computed by `scripts/roster.py`, a dependency-free Python engine, not improvised in prose. Same roster, same findings, every run.

## Why it exists

A schedule's problems do not show on the sheet. A grid of names and times hides that Sunday evening has one person on the floor, that the Friday closer is back at six on Saturday, and that one lead sits at 46 hours while another has 31. Laid out by the hour, all three are obvious.

On the sample week, the fix for Sunday is already in the schedule: Tuesday midday carries 18.5 person-hours above need.

## Install

**1. Download** [schedule-photo-to-roster.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/schedule-photo-to-roster.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the schedule demo."* Then with your own: *"Here's our schedule for next week [photo]. We need 3 people from 7 to 11 and 4 until close, always one shift lead."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/operating/schedule-photo-to-roster ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## What's supported

- **Photos, screenshots, scans and spreadsheets** of a weekly schedule. Handwriting is fine; times without am or pm are resolved from the store hours on the sheet, and the readback says how.
- **Needs by day, time and role**, in a small CSV. Without them, it still finds gaps and people working alone.
- **Overnight shifts**, counted across midnight.
- **Overtime and rest thresholds** for US federal rules, California, and the local scheduling laws in Oregon, Seattle, Chicago, Evanston, New York City, Philadelphia, Los Angeles (city and county), Berkeley, Emeryville and San Francisco. Each names its official source and the date it was checked.
- **A one-page HTML report** with the week as a coloured grid, readable on a phone.

## What's not supported

- **What actually happened.** It checks the schedule as written, not attendance, swaps or late changes.
- **Contracts, union agreements and your own policies.** Only the thresholds in its rules file.
- **Legal advice.** The rules file describes the shape of each rule and points to the source; it records no premiums or penalties, because those change.
- **Contact details.** It refuses a roster containing phone numbers or emails.

## Verifying this yourself

```bash
python3 scripts/roster.py --test
```

The suite runs the sample week and checks that it finds exactly what was planted and nothing else: Dana's 6 overtime hours, Marco's 7-hour turnaround, Leo's seven days, Priya's double booking, the smudged Thursday cell, short Saturday morning and Sunday evening, the missing Sunday shift lead and the Tuesday surplus. A clean week must come back clean. Overnight shifts, California daily overtime, rest thresholds that change the answer by city, duplicates, misreads and four kinds of refused input are covered too.

## Who it's for

- **Store and site managers** who write the schedule by hand and want a second pair of eyes before posting it.
- **District and area managers** checking a dozen sites' schedules without opening a dozen spreadsheets.
- **HR and operations leads** who want overtime and rest-rule exposure seen before the week starts, not in payroll after it.
