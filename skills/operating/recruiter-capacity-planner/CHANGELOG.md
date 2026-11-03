# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Andrea Michelle Eighme.

- Rebuilds weekly load per recruiter from the applications they owned, per available
  day when a roster is given.
- Finds the knee: the load above which the screening wait rises faster than load,
  fitted with each recruiter's own level and each role's typical wait taken out, and
  reported only when it beats a straight line clearly, or "cannot be located".
- Checks the knee without the busiest weeks, names recruiters whose raw wait is the
  roles they hold, and shows the fit with and without leave.
- Diagnoses each recruiter: capacity, process (rework), upstream, individual or room
  to spare; flags a team slow even in light weeks as a process problem.
- Headcount only where capacity is the diagnosis, at 90% of the knee.
- Ranks automation by hours a month returned per unit of effort, with frequencies
  from the export and minutes from you, and lists what to eliminate instead.
- Refuses exports with name, email, phone, address or notes columns.
- An adversarial pass before release found that measuring each recruiter against
  their own lightest weeks manufactured a knee out of a straight line, and that
  medians of whole-day waits called a recruiter slow by a full day of rounding. Both
  were replaced (recruiter levels fitted jointly, mean waits) and kept as tests.
