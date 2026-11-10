# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Anita Chandrasekhar.

- Reads a hires file (one row per accepted offer) and, best, a steps file (one row
  per onboarding step per hire). Counts the loss between offer and first shift on
  hires whose first shift is already due, with withdrawals and first-shift no-shows
  apart. Rescinded offers are counted separately by failed step and site. Hires
  still in onboarding are set aside, including those already marked withdrew.
- Reads the gap from the offer to the scheduled first shift first, then, per step,
  your queue (offer to request) and the turnaround (request to done), by vendor and
  method, and the share of hires whose forms were sent only after the background
  check came back.
- Shows the steps open at each withdrawal, and withdrawals per 100 hire-days spent
  waiting on each step.
- Tests every suspect inside strata: a long gap within site, role and month; a silent
  first week and a lab drug test within gap and site; every site, vendor, role,
  source and recruiter within the gap, and sites and recruiters within the gap, lab
  and silence together. A cause is named only if it clears Holm at 5% across
  everything tested and keeps its sign and 40% of its size in every check.
- Writes the fixes from what survived, and what to measure.
- Refuses files with names, emails, phone numbers, addresses or notes, names in id
  columns, and pipeline exports (pointing to funnel-drop-off-analyst).
- An adversarial pass before release found five things, all kept as tests. A store
  with long gaps and lab tests was named as a cause of its own, because each check
  held one of the two and let the other through; sites and recruiters are now also
  checked with the gap, lab and silence held together, and across 20 redrawn worlds
  no store, vendor, role or recruiter was named for something it does not cause.
  Hires who withdrew before a first shift was scheduled were dropped with everyone
  else who had no date; they are losses, and are now counted once their cohort is
  decided. A company whose gaps were all longer than 10 days got no gap test at all;
  the threshold now moves to the median. On a steps file the step's `status` column
  was read as the hire's outcome, so no rescind was ever tied to the step that
  failed. And a log where the food handler card was never completed crashed the
  fixes; found by fuzzing.
