# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release.

- Reads a photo, screenshot, scan or spreadsheet of a weekly schedule into a roster,
  following written transcription rules: transcribe rather than correct, never guess a
  time, resolve am and pm from the store hours on the sheet and say so.
- Always reads the roster back for confirmation before any analysis, with every
  uncertain cell marked.
- Checks the week in 15-minute slots against the needs you give it: short-staffed
  windows, missing roles, surplus of two or more people for two hours or more. Without
  needs, it finds gaps and people working alone.
- Checks people: overtime by week, and by day under California-shaped rules; rest
  between a close and the next open; seven days without a day off; long shifts with no
  break written down; the same person booked twice.
- Overtime and rest thresholds for US federal rules, California and twelve local
  scheduling laws, each with its official source and the date checked. No premiums or
  penalties are recorded, because they change and this file does not.
- Suggests same-role people with spare hours for each overtime case.
- One-page HTML report, no scripts or external files, light and dark.
- Refuses rosters containing phone numbers or emails, times that are not 24-hour, and
  dates that are not real dates.
- A sample week with a photo and its ground truth, planted with exactly nine problems.
  The suite checks the engine finds those nine and nothing else, and that a clean week
  comes back clean.
