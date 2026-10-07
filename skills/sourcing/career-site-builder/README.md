# Career Site Builder

> Builds a complete careers site for a frontline employer, or audits the one you already have, and proves before handover that search engines and AI assistants can read every job on it.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Give it an employer's name and website. It researches the brand, then builds the site: a home page with a job search, career-area pages that say what the work is really like, a hiring process page, a FAQ, and one page per job and per location, generated from a jobs export.

Or give it the careers site you have. It saves the page, runs the checker, and tells you how many checks it passes, area by area, before offering the rebuild.

Or say "show me a demo". It builds a complete site for a fictional convenience-store chain in about two minutes.

## Why it exists

A careers site is read by machines before it is read by candidates, and the machines do not look at the design.

- **Search engines** list jobs directly in results, but only jobs with complete JobPosting markup on their own page.
- **AI assistants** answer "who is hiring near me", but many of their crawlers do not run JavaScript. A careers site rendered entirely in the browser can look empty to them.
- **Candidates** on a phone leave when pay is missing, when Search jobs is buried in a menu, or when Apply suddenly opens a site that looks like someone else's.

Every one of those is mechanical, so the skill generates them with code and checks them with code.

## Install

**1. Download** [career-site-builder.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/career-site-builder.zip). Do not unzip it.

**2. Check two settings** in the Claude app, under Settings, Capabilities:

- **Code execution and file creation** must be on. Skills need it, and this one runs two scripts.
- **Web search** should be on, so it can research the employer. Without it, it asks you to paste your About and Benefits pages instead.

On a Team or Enterprise plan, an owner may need to turn these on, and can provision the skill to everyone from Organization settings, Skills.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Works on Free, Pro, Max, Team and Enterprise.

**4. Try it.** Start a new chat and type one of these:

- *"Show me a demo of the career site builder."* Two minutes, no input needed.
- *"Build a careers site for [company], [website]."*
- *"Audit our careers site: [URL]."*

You get a styled preview in the chat, the full site as a zip, and the check report.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/sourcing/career-site-builder ~/.claude/skills/
```

**Prerequisites:** Python 3, which the Claude app already has. Standard library only, nothing to install.

## Running the scripts yourself

```bash
python3 scripts/build_site.py --site my-site --demo                 # the demo, plus my-site-preview.html and my-site.zip
python3 scripts/build_site.py --site my-site --jobs open_jobs.csv \
        --base-url https://careers.yourcompany.com                   # your jobs
python3 scripts/check_site.py --site my-site                        # check a site
python3 scripts/check_site.py --page saved-careers-page.html        # audit one page
```

## What the checker looks at

37 checks in six areas: search, AI visibility, conversion, accessibility, honesty and speed. Blocking checks include JobPosting required fields, one h1 per page, a mobile viewport, labelled form fields, visible focus, colour contrast, no lorem ipsum, a sitemap that lists every page, and content that exists in the HTML rather than only in JavaScript. The full list is in `references/rubric.md`.

It reports a count, not a score. A missing posting date is not worth a number of points, and nothing elsewhere makes up for a blocking failure.

## Verifying this

```bash
python3 scripts/check_site.py --test
```

Builds the demo site and asserts it passes every check, then breaks it 26 ways, one at a time, and asserts each break is caught for its named reason and nothing else.

## Where this stops

It builds and checks static files. It does not host the site, connect to an applicant tracking system live, or update itself when jobs change. It cannot confirm that a fact is true, only that unconfirmed facts are marked and listed. The pay-transparency notes are not legal advice.

## Licence

MIT. Use it, fork it, ship it inside your own tooling.
