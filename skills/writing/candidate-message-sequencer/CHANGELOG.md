# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release.

- Writes nudge sequences for the four places a frontline funnel stalls: no screen booked,
  no interview booked, documents missing, start date set and nothing since.
- Grades the **sequence**, not the message. Cadence, volume cap, send window, quiet
  hours, repetition and opt-out placement are all properties no per-message check can
  see, and they are where a well-meant sequence turns into harassment.
- Refuses to write a sequence with no stop condition. Without one it keeps messaging
  people who have already done the thing it asks for.
- Refuses to ask for identity or banking details over a messaging channel, in any
  sequence, for any stated reason. Collecting them by text trains candidates to hand
  documents to whoever asks.
- The opt-out belongs on the first message and only there. Absent is a compliance
  problem; on every message it reads as a company that expects to annoy you.
- Fourteen fixtures, twelve of which must fail for a named reason, plus three parser
  refusals. Each fixture also declares what must not be found in it — a checker that
  flags everything is as useless as one that flags nothing, and only that half of the
  suite can tell the difference.
- Two defects found by the suite before release, both from the same cause: the opt-out
  clause was being treated as content, so it counted as a competing call to action and
  it stopped two identical messages from matching each other. Boilerplate is now
  stripped before a message is judged on what it says.
- The rubric encodes conservative defaults and says plainly that it is not legal advice:
  consent basis, opt-out wording and permitted hours vary by jurisdiction and the
  checker does not know where you are.
