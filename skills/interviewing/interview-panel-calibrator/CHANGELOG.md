# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Taylar Ashleigh Martin.

- Builds and checks a calibration pack: three answers per question at different levels,
  one deliberate borderline, shuffled. Prints a scoring sheet that never shows the
  intended level, and writes the key to keep back.
- Reads the panel's scores: for each answer, agree, one or two outside, split, scattered
  or borderline; for the guide, anchors with two readings, a middle anchor that says
  nothing, and answers the panel reads differently from their author.
- Profiles each interviewer against the others with that person left out: aligned,
  lenient, severe, range-restricted or inconsistent, and says how far the number of
  answers supports it (nothing under four, a pattern from four to seven, consistent
  from eight).
- Optional live check: pass rate per interviewer against the pool with a 90% range,
  nothing flagged under twenty interviews, and whether pass rate follows open roles
  across at least four sites.
- Refuses files with emails, phone numbers or candidate columns.
- An adversarial pass before release found a reversed scorer, a whole panel shifted
  against the key, a lone contrarian, case differences in names and items, and noise
  read as a pattern. All are fixed and kept as tests.
