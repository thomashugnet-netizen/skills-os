# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Hernan Chiosso.

- Guided design that starts from a past workflow (`clone`) or proposes steps, and marks everything unconfirmed until a person says yes.
- `check`: owners, deadlines, definitions of done, waits, fallbacks, stop rule, dead air with the hire, and five federal US deadlines. Exits non-zero when not ready.
- `render`: a terse document, and a page with timeline, by-category and by-owner views.
- `log`: fallback rates per step with a sample-size floor, and a site screen with a Benjamini-Hochberg correction.
- Test suite: 59 fixture cases with must and must-not findings, and the log reader checked against 40 redrawn logs.
- A workflow or log that is not UTF-8 text is refused with a reason instead of a crash.
