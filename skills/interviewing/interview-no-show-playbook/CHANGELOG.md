# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Courtney Barabas-Esperance.

- Reads a booking log (one row per booked interview) or a pipeline export (one row
  per application). Counts the miss per appointment and per candidate, keeps
  cancellations and moves apart from silent misses, leaves employer cancellations
  and upcoming interviews out, and names past interviews with no outcome.
- From a pipeline export, counts the candidates who cleared screening and never got
  a slot, by reason and by site.
- Reads the wait between booking and interview first, and names the calendar
  behind it site by site: interviews on one weekday only, one slot offered, one
  interviewer, busy weeks, with each site's miss rate before and after the wait is
  equal.
- Tests every suspect inside the strata that usually fake it: the wait within site,
  role and week; a weekend inside the wait within the same wait and site; the hour
  within role, wait and site; one slot within wait and site; self-scheduling within
  wait and role; a site within week and wait; an interviewer within their own site.
  A cause is named only if it clears Holm at 5% across everything tested and keeps
  its sign and 40% of its size in every check. The rest are listed as explained by
  something else, or as impossible to separate in this file.
- Reads what happens after a first miss: rebooking speed, attendance after it, any
  site that never rebooks; and the reply to the 24-hour reminder as an early flag.
  Sizes a holdout to prove a reminder works.
- Writes the playbook: slot rules from what survived, a text sequence timed to the
  wait, the reschedule path. Checks it, or your own sequence, and blocks it until
  every message carries its elements, fits two text messages, asks nobody to log in
  and keeps its timing, and the policy rebooks a first miss and closes after the
  second silent miss.
- Refuses files with names, emails, phone numbers, addresses or notes, and names in
  id columns.
- An adversarial pass before release found five things, all kept as tests. The
  draft said the wait could be read from the library's pipeline sample; it cannot,
  because a missed interview has no interview date there, so a wait measured on
  completed interviews describes only the people who came. Rebookings after a miss,
  mixed into the cause tests, made recruiter-booked interviews look better than
  they were; causes are now read on each candidate's first appointment. A
  false-discovery correction let a chance interviewer through among many real
  findings; it is now Holm across everything tested. An interviewer who is their
  store's only one was reported as a cause of their own; the store and the
  interviewer are now reported as inseparable. And a log with no misses at all
  crashed the holdout sizing; found by fuzzing.
