# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Madelyn Rovellada.

- Writes nudge sequences for the four places a frontline funnel stalls: no screen booked,
  no interview booked, documents missing, start date set and nothing since.
- Grades the **sequence**, not the message: cadence, volume cap, three-week window,
  quiet hours, repetition and opt-out placement are properties no per-message check can
  see, and they are where a well-meant sequence turns into harassment. Each finding
  either blocks the sequence or is advice, as listed in the rubric.
- Refuses to write a sequence with no stop condition, or one that asks for identity or
  banking details over a messaging channel, for any stated reason.
- Counts an SMS the way a phone does: the link as a real short link, and one character
  outside the GSM alphabet (a curly apostrophe, an em dash, an emoji) as switching the
  whole text to Unicode, with a 70-character limit. The finding names the character.
- Reads a send log: per message, of the people it reached who had not acted, how many
  acted before the next one and how many opted out, with 90% ranges; people who acted
  and kept getting messages, with an hour's grace for sync lag; anything sent after an
  opt-out; sends at night, under twenty hours apart, or past the cap. Refuses logs with
  email addresses, phone numbers, name columns or the message text.
- An adversarial pass on the September draft before release found:
  - its own passing SMS was 167 characters once the link was a real short link, so two
    parts; the link is now counted at 23 characters;
  - another fixture marked fine contained an em dash, which makes an SMS Unicode and
    would have sent it as two parts;
  - actions and phrases were matched inside other words ("text" in "context", "book" in
    "booked", "visit" in "visitor"), and inside placeholders, so polite messages were
    told they offered three actions; matching is now by whole word;
  - "Reply YES to confirm" counted as two actions, and "we need your documents to confirm
    it" as one the candidate must take; a verb after "to" is now a purpose, not an action.
  All four are kept as tests. Fuzzing the new log reader found two crashes (a step of
  "inf", a date in the year 9999), both now refused with a reason.
- The rubric encodes conservative defaults and says plainly that it is not legal advice:
  consent basis, opt-out wording and permitted hours vary by jurisdiction and the checker
  does not know where you are.
