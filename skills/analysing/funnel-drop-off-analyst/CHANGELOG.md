# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter, and the engine prints it at the top
of every report.

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
