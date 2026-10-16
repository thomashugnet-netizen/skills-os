# Career Site Builder

> Ask it to redo your careers page and it builds a modern, on-brand landing page with a working job search, then checks it for search, AI visibility, accessibility and honesty before handover.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Say *"Redo our careers page"* with your company name and website. It fills in a fixed brief for your company and shows it to you, researches your brand, proposes the structure and design direction, and once you approve, builds the page: hero and job search, career areas, why work here, benefits, growth, locations, the hiring process, FAQ and a talent community, in your colours.

Links to pages beyond the landing page (each career area, each job, application status) open a short dialog explaining what that page would be in the full version, so nothing in the preview dead-ends.

Or say *"Show me a demo"*: it builds the page for a fictional convenience-store chain in about two minutes, no questions asked.

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
- *"Redo our careers page: [company], [website]."*
- *"Audit our careers page: [URL]."*

You get a styled preview in the chat, the full site as a zip, and the check report.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/sourcing/career-site-builder ~/.claude/skills/
```

**Prerequisites:** Python 3, which the Claude app already has. Standard library only, nothing to install.

## Running the scripts yourself

```bash
python3 scripts/fill_brief.py --company "Acme" --colour red \
        --segments "store team members, drivers" --pages "Store Careers|Driving"
python3 scripts/build_site.py --site my-site --demo                 # the demo, plus my-site-preview.html and my-site.zip
python3 scripts/build_site.py --site my-site --examples roles.csv   # landing page with example roles
python3 scripts/build_site.py --site my-site --jobs open_jobs.csv \
        --base-url https://careers.yourcompany.com                   # a page per real job and location
python3 scripts/check_site.py --site my-site                        # check a site
python3 scripts/check_site.py --page saved-careers-page.html        # audit one page
```

## What the checker looks at

47 checks in seven areas: search, AI visibility, conversion, accessibility, legal, honesty and speed, with the evidence for each in `references/sources.md`. Blocking checks include links that go nowhere, an inaccessible preview dialog, JobPosting required fields, one h1 per page, a mobile viewport, labelled form fields, visible focus, colour contrast, no lorem ipsum, a sitemap that lists every page, and content that exists in the HTML rather than only in JavaScript. The full list is in `references/rubric.md`.

It reports a count, not a score. A missing posting date is not worth a number of points, and nothing elsewhere makes up for a blocking failure.

## Verifying this

```bash
python3 scripts/check_site.py --test
```

Builds the demo landing page and a full site, asserts both pass every check and that the brief is filled word for word, then breaks them 39 ways, one at a time, and asserts each break is caught for its named reason and nothing else.

## Where this stops

It builds and checks static files. It does not host the site, connect to an applicant tracking system live, or update itself when jobs change. It cannot confirm that a fact is true, only that unconfirmed facts are marked and listed. The pay-transparency notes are not legal advice.

## Licence

MIT. Use it, fork it, ship it inside your own tooling.
