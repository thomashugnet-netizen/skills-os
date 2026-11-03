# Reading a schedule photo

How I turn a photo, screenshot or scan of a schedule into `roster.csv`. The engine
trusts this file completely, so every rule here exists to keep a guess out of it.

## The output

One row per shift. Days off get no row.

```
person,role,date,start,end,break_minutes,confidence,note
Dana,Shift lead,2026-10-19,06:30,15:00,30,high,
Sam,Cashier,2026-10-22,12:00,18:00,0,low,smudged; best reading 12-6
```

| Column | Rule |
|---|---|
| `person` | Exactly as written. First names or initials are enough. Never add a surname that is not on the sheet. |
| `role` | From a role column, a section heading or a colour key on the sheet. Blank if the sheet does not say. Never inferred from the name. |
| `date` | `YYYY-MM-DD`. Built from the week shown on the sheet and the weekday column. |
| `start`, `end` | 24-hour `HH:MM`. An end at or before the start means the shift runs past midnight. |
| `break_minutes` | From the sheet: a written break, or a printed rule such as "shifts over 6 hours include a 30 minute break". Blank when the sheet says nothing. |
| `confidence` | `high` when the cell is unambiguous. `low` when any part of it is not. |
| `note` | Why a cell is `low`, or anything written in it that is not a time ("training", "swap with Kevin"). |

## Rules

**1. Transcribe, do not correct.** If a cell says something odd, that is a finding, not a
typo to fix. Two times written in one cell are two rows. A 19-hour shift is written as
a 19-hour shift, and the engine flags it.

**2. Never guess a time.** A smudged, crossed-out, cut-off or overwritten time gets my best
reading with `confidence=low` and a note saying what made it uncertain. If I cannot
produce any reading, I leave the shift out and list it under "could not read".

**3. am and pm come from the sheet, not from habit.** Handwritten schedules almost never
write am or pm. Resolve them in this order, and say which one decided it:
- an explicit marker in the cell (`a`, `p`, `am`, `pm`)
- a shift never crosses midnight unless the sheet says so (a night label, `12a`, an
  overnight section), so `6-12` is 06:00 to 12:00, not 18:00 to midnight
- the store hours printed on the sheet: prefer the reading that starts and ends within
  an hour of them. With hours of 7am to 10pm, `6-11:30` is 06:00 to 11:30, because
  18:00 to 23:30 ends ninety minutes after close
- the pattern of the column: if every closer reads `2-10:30`, the `2` is 2pm
- if a cell still has two sensible readings after all four, mark it `low` and ask.

For example, with store hours 7am to 10pm: `6:30-3` is 06:30 to 15:00, `2-10:30` is 14:00
to 22:30, `11-7:30` is 11:00 to 19:30, and `3-11` is 15:00 to 23:00.

**4. Dates come from the sheet.** Use the week written on it. If the year is missing, use
the year in which those dates fall on the weekdays shown. If the sheet shows no week at
all, ask for the Monday's date rather than assume this week.

**5. What counts as a day off.** `OFF`, `RDO`, `X`, a dash, a blank cell, `V` or `VAC`
(vacation), `PTO`, `SICK`: no row. Write vacation and sick in my readback so the
manager can see I understood them, because they change who is available.

**6. Crossed-out entries.** A struck-through time with a new time beside it: use the new
time, note "changed from ...". A struck-through time with nothing beside it: no row,
note it in the readback.

**7. Colours and highlights.** If the sheet has a key, apply it. If it has colours and no
key, say what I see ("three cells highlighted yellow") and ask what they mean. Never
invent a meaning.

**8. Nothing that reaches a person.** If the photo shows phone numbers, emails or
addresses, I do not copy them. The engine refuses any file that contains them.

## The readback

Before any analysis I show the roster back as a grid in the same layout as the photo,
with every `low` cell marked, and ask the manager to confirm or correct. A wrong reading
turns into a wrong finding with a confident number beside it, so this step is never
skipped, even in the demo.

A correction is applied to the CSV and the readback shown again only for the cells that
changed.

## Several pages or sites

One file per site. Several photos of the same week for the same site are combined into
one file, and a person who appears on two pages is the same person only if the manager
confirms it.
