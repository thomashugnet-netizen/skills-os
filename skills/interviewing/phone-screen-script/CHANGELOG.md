# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Andrea Michelle Eighme.

- Writes a five-minute phone screen in a fixed running order: opener, availability
  against the shifts you are short of, start date, journey, genuine prerequisites,
  a thirty-second preview with the pay, their questions, the decision, the booking.
- Checks the script and blocks it, with the reason, until it passes: availability
  first and asked block by block with a day or time, "how would you get here", only
  a minimum age, a licence or certificate, or work authorization as prerequisites,
  no assessment questions, no questions on age, citizenship, family, health,
  religion, arrests or pay history, three gates and no others, a written no and a
  redirect, two slots and a confirmation with when, where and who, pay stated,
  under five minutes read aloud.
- Writes the unanswered path: voicemail under twenty seconds with a way back, a text
  after every voicemail with an opt-out, attempts spread across the day, a stop
  rule, a callback script, five capture fields at most.
- Prints a one-page call sheet, only once the script is ready.
- Reads a call log: booking by speed to first call, answer rate by part of the day,
  the effect of a text after voicemail, callers whose calls end open or unbooked,
  shows by how far off the interview is, limbo and over-calling. A comparison is
  stated only when the 90% ranges do not overlap.
- Refuses logs with email addresses, phone numbers, or name, address or notes
  columns.
- An adversarial pass before release found that calls arranged after a candidate
  texted back were counted as attempts, which inflated the evening answer rate and
  called people "over-called" who had simply been reached; that a log without a
  `booked` column reported 0% booked everywhere; and that a time with a UTC offset
  could crash the read. Attempts now stop at the first contact, missing columns are
  named instead of read as zero, and offsets keep the local wall-clock time, which
  is what decides morning or evening. All three are kept as tests.
