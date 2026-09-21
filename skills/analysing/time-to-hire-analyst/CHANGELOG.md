# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter, and the engine prints it at the top
of every report.

## 1.0.0

First release.

- Stage-by-stage cycle time on the canonical schema, ranked by share of total elapsed
  days rather than by median — a four-day wait everybody sits through holds more of the
  calendar than a twenty-day wait forty people reach.
- Three answers kept apart rather than averaged: the stage holding the most calendar
  time, the stage carrying a delay concentrated in a minority of segments, and the stage
  that only stretches under peak load. On the retail sample these are three different
  stages with three different owners.
- Censoring is measured and reported at every stage. A median over the people who
  finished waiting excludes everybody still queuing, and excludes them precisely because
  their wait is longer — so the in-flight count travels with every figure, and a file
  more than 60% in flight is refused.
- Timestamps that contradict the stage order are refused above 2% rather than filtered
  out quietly. Usually two crossed columns or a status-history pivot that took the wrong
  entry; either way every median downstream would be fiction.
- A load effect has to be both proportionally and absolutely material. A median moving
  from one day to two is the largest ratio in a date-only export and the smallest real
  effect; requiring days as well as a ratio is what stops it being reported as a finding.
- Every concentrated delay is re-tested holding each other dimension constant, and what
  did not survive is reported under **Ruled out** with the dimension that killed it named.
- 22 assertions per sample plus five refusal cases, run against all four samples
  including the five-stage gig activation funnel.
