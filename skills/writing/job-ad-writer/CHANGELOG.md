# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one — so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release as a folder.

- `scripts/check_ad.py`, standard library only: checks an ad against the standards this
  skill already promised in prose. Pay stated rather than gestured at, shift pattern
  present and above the fold, a searchable location, a way to apply, channel length
  limits, reading grade, sentence length, corporate verbs, gendered role language,
  years-of-experience filters, requirements that proxy for something else.
- `references/rubric.json` holds every rule as a versioned contract. A rule that is not
  also in `SKILL.md` means one of the two is wrong.
- No score. A missing pay rate is not two thirds of a long sentence, and a number would
  imply the checks trade off against each other.
- Seven fixtures in `references/fixtures/`, each written to fail in one named way, plus
  two that must pass cleanly. The suite asserts both — catching the planted fault and
  inventing nothing on the clean ads.
- The reader-facing `## Works with` section replaces the assistant-directed Cue block.
