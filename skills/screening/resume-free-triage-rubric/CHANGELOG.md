# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Darrell Clack.

- Builds a triage rubric for hourly roles where most applicants have no resume:
  shift overlap with the shifts each site is short of, start latency, the travel
  plan for the earliest shift, one concrete reliability answer, and, lightly, rota
  experience and certifications.
- Checks the rubric and blocks it until it passes: no distance, radius, gaps,
  tenure, resume, education or past rejection; no signal as a gate; knockouts only
  for a minimum age, a licence the law requires with its legal basis, or work
  authorization, three at most; no question about age, family, health, religion,
  citizenship, arrests, pay history or gaps; no reliability self-rating; a first job
  must be able to reach the call-today line.
- Bands the open queue to the calls your team can make, routes applicants whose
  availability fits another site, holds those who fit nowhere this week for the
  next rota, and turns blanks into questions for the call.
- With past hires and their 30-day outcome, says whether each signal earns its
  points within the same shift overlap, names travel levels scored apart that
  retain alike, and shows what a radius would cut. With voluntary self-ID, reads
  each group's call-today rate against the four-fifths line and names the signal
  that opens the gap.
- Refuses files with names, emails, phone numbers, addresses or notes, names in id
  columns, free-text travel or availability it cannot read, and a self-ID file
  carrying anything but the group.
- An adversarial pass before release found four things, all kept as tests. A
  scored signal called `previously_rejected` slipped past the re-applicant rule
  and was reported only as unknown. A knockout collecting a date of birth passed
  because its rule said "18 or older". ATS outcome words (Hired, Terminated,
  Active) were read as blank, so a real export showed no past hires. And a travel
  level was named as not backing its extra points whenever the comparison was
  underpowered; it is now named only when the lower-scored answer stayed as well.
