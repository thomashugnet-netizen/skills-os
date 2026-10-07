# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 2.0.0

The default output changes, so this is a major version: what 1.0.0 told you it would
build is no longer what it builds by default.

- **"Redo our careers page" now starts from a fixed brief.** `references/brief.md` holds
  the brief word for word with four blanks (company, brand colour, talent segments,
  segment pages). `scripts/fill_brief.py` fills them and the filled brief is shown
  before anything else, ready to copy.
- **Direction is approved before building**, as the brief asks. The fast path, building
  straight after one screen of direction, now applies only to the demo.
- **The default output is one landing page** in the employer's brand, not a multi-page
  site. The separate FAQ, hiring process and career-area pages are now sections of the
  landing page, or links.
- **A preview dialog replaces missing pages.** Links to supporting pages, jobs,
  locations, application status and the talent community open an accessible dialog
  that says what the full version adds. Its copy lives at the top of `js/site.js`.
- **Two build modes.** `--examples roles.csv` (and `--demo`): job search over example
  roles, labelled as examples on the page. `--jobs export.csv`: one page per real job
  with JobPosting markup and one per location, as in 1.0.0.
- **Two new blocking checks**, 39 in all: every link goes somewhere (a section, a page,
  or the dialog), and the dialog has a name and a close button.
- **47 tests**, up from 37. Both modes must pass clean, the brief must fill word for
  word, switching modes must leave no stale pages, and 30 planted faults must each be
  caught for their named reason. The suite caught a real defect on the way: job pages
  copied the footer's dialog links without the dialog itself.

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
