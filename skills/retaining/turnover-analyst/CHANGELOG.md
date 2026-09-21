# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter, and the engine prints it at the top
of every report.

## 1.0.0

First release.

- Attrition by tenure band — 1-30, 31-90, 91+ — each over its own at-risk cohort, with
  the uncorrected figure printed beside it so the size of the correction is visible
  rather than merely applied.
- Two denominator corrections, and both were load-bearing. Only people who have had time
  to reach a band are counted in it; and a band counts only people who reached its start,
  so a segment with heavy first-month attrition no longer inherits a flattering 90-day
  figure from a denominator full of people who had already gone. Applying the second one
  moved the 31-90 rate from roughly 6% to roughly 10% — which is where the sample data's
  planted value actually sits.
- Findings are screened with a Benjamini-Hochberg false-discovery-rate procedure across
  the whole band at once, not per dimension. Screening two hundred segments at the usual
  threshold produces about ten findings in a file containing nothing, and it did: the
  first version of this engine reported four managers in a band where the generator had
  planted nothing at all. Bonferroni fixed that and cost two of the five real managers
  with it; the FDR procedure keeps both.
- Every finding must also clear a materiality floor. Statistical screening and worthwhile
  size are separate questions and a finding has to pass both.
- The manager/role confound is tested in both directions, using the manager *group* as
  the stratum. Individual managers rarely carry thirty hires in both arms, so
  stratifying on manager id silently returns "not testable" and a role effect that is
  really a manager effect walks through unchallenged.
- Exit reasons get a seeded permutation test. On all four samples the observed mix is
  within what reshuffling produces, and the report says so — that exit reasons will not
  identify the segment, and a programme built on them would be built on noise.
- Collinear dimensions are detected and their findings reported once. One manager per
  site makes `hiring_manager_id` and `location_id` the same cut of the data, and printing
  both reads as corroboration. Detection requires a bijection, not merely a function:
  every manager sits in exactly one region too, and forty managers and four regions are
  not the same cut.
- A band where nobody at all is recorded as leaving is reported as the data stopping, not
  as a 0% rate — usually `tenure_days` populated only for early leavers, or a window
  shorter than the band.
- 26 assertions per sample plus five refusal cases, run against all four samples
  including the five-stage gig activation funnel.
