# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter, and the engine prints it at the top
of every report.

## 1.1.0

- Four sample datasets instead of one, matched to the segments this library is written
  for: retail, quick service restaurants, logistics and delivery, and gig delivery. Pick
  the one that looks like your operation.
- The gig sample runs a different funnel: a marketplace sign-up is never interviewed and
  never given an offer, so it has five stages (signed up, documents in, background clear,
  onboarding, first job) rather than seven. The engine detects which shape a file uses
  from its stage names; there is nothing to configure, and a file mixing the two
  vocabularies is refused rather than guessed at.
- The 29 regression assertions now run against all four samples, the gig one included. An
  engine that had memorised one file's answers fails the other three; two assertions that
  had quietly done exactly that were rewritten when the other samples exposed them.
- Stage positions in the engine are derived from the bound funnel rather than written as
  literal indices, so "reached the end" means started or activated depending on the file.

## 1.0.0

First release.

- Five-pass analysis engine (`scripts/analyze.py`), standard library only. Funnel,
  localisation, mechanism classification, stratified confound testing, sizing in hires.
- Mechanism classified inside each flagged segment rather than across the step — a step
  can read candidate-driven in aggregate while the sites carrying its loss are plainly
  capacity-driven.
- Wilson 95% intervals on every rate; 30-candidate floor before a segment is ranked;
  500-row floor below which the engine refuses rather than guessing.
- Findings describing the same people twice (a region and its own sites) are reported
  once, with the other recorded.
- Banded drivers reach the fix list, so the offer-to-first-shift gap is ranked rather
  than buried.
- `What it costs you to run` computed from the findings: sites touched, one-off changes,
  candidates per week in scope.
- 28 regression assertions against `data/frontline_pipeline_sample.csv`, including the
  planted confound (manager effect survives within role) and the planted red herring
  (weekend effect does not survive within source).
- Export recipes for eleven ATSs in `references/export-recipes.md`, with every claim
  marked as documented or inferred.
