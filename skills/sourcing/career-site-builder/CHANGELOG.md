# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release.

- Two modes: audit an existing careers page, or build a complete site from an employer
  name and website. A demo mode builds a site for a fictional employer with no input.
- `references/starter/`: a design system and five hand-written page templates. One
  file, `css/tokens.css`, changes per brand.
- `scripts/build_site.py`, standard library only: job pages with JobPosting markup,
  location pages, the job list in plain HTML, FAQ markup, sitemap, robots.txt and
  llms.txt, all generated from one jobs CSV. Rebuilding is idempotent. Also writes a
  self-contained preview of the home page, which opens styled in a chat, and the whole
  site as a zip.
- `scripts/check_site.py`, standard library only: 37 checks across search, AI
  visibility, conversion, accessibility, honesty and speed. Reports a count per area,
  not a score, and lists every fact marked for the employer to confirm.
- 37 tests: a clean demo build that must pass everything, a single-page audit that must
  skip site-wide checks rather than fail them, and 26 planted faults, each caught for
  its named reason and nothing else.
