# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Kristi Kennebrew.

- Sorts a pipeline export into four contactable groups (reached interview or beyond,
  screened then dropped, former workers in good standing, rejected against a requirement
  of a different job) or a named reason each record is out, every row accounted for.
- Settles what may be sent first: retention period (records past it counted as a
  deletion job), and whether past applicants, former workers and other-role contacts are
  allowed; an undecided question blocks its group.
- Matches people to openings near them by site or region; offers someone rejected
  against a requirement a different role, or the same role when its pattern changed.
- Counts the people dropped by the employer (no slot, no follow-up, a slow check).
- Segments by recency, send windows by shift, waves sized to reply capacity, and a
  contact list of ids only.
- Checks the three messages: days 0, 1 and 3, opt-out and sender in each, reason on day
  0, news on day 1, "last message" on day 3, no re-apply, known merge fields only, length.
- Refuses exports with name, email, phone, address or notes columns.
- An adversarial pass before release found that the suite itself treated people knocked
  out at the application stage as abandoned forms (they are not: they are the
  different-role group), that day-1 news written with a merge field such as the pay rate
  was not recognised, and that a missing sender was read as the word "None". All fixed
  and kept as tests.
