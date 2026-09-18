# Running this on Replit

One process serves the whole library: the per-skill pages, the real `.zip` downloads,
and the email gate for the full pack.

## Import

1. New Repl → **Import from GitHub** → `thomashugnet-netizen/skills-os`.
2. Press **Run**. Replit installs Flask from `requirements.txt` and starts `main.py`.

Import from GitHub rather than from a zip, so that what runs here and what is versioned
stay the same thing. Commit from Replit and the history lands in the repo.

First boot builds what is missing — the 9 skill pages and the 43 packages — and prints
what it did. Packaging runs each skill's own test suite inside a scratch copy before
accepting the archive, so a failing build is telling you something real.

Nothing else to configure.

## What is where

| Path | What it is |
|---|---|
| `main.py` | The web server. Routes, the email gate, build-on-boot. |
| `skills/` | The 43 skills. One folder per skill for the newer ones, one `.md` for the rest. |
| `tools/audit.py` | The release gate. Blocks hidden or deceptive content. Run it before you ship. |
| `tools/package.py` | Builds the installable `.zip` for each skill. |
| `tools/gen_readme.py` | Regenerates the README's tables from the skill frontmatter. |
| `site/build.py` | Generates the marketing page for each skill. Content is hand-written in `SKILLS`. |
| `data/` | The synthetic dataset and the generator that produces it. |
| `dist/`, `site/out/` | Build output. Not committed; rebuilt on boot. |

## Routes

| Route | |
|---|---|
| `/claude-skills` | Index of all 43, grouped by category |
| `/claude-skills/<slug>` | The full page, for the 9 that have one |
| `/download/<slug>.zip` | The installable file |
| `/pack` | Email gate, then the whole library |
| `/data/frontline_pipeline_sample.csv` | The synthetic dataset |
| `/healthz` | Counts of skills, pages and packages |

## Changing things

**A skill's text** — edit its `SKILL.md`, then:

```bash
python3 tools/audit.py          # must pass, it is a release gate not a linter
python3 tools/gen_readme.py     # if you changed the frontmatter description
python3 tools/package.py <slug> # rebuild just that archive
```

**A skill's analysis engine** — edit `scripts/analyze.py` inside the skill folder, then
run its suite. It checks the engine against the traps planted in the sample data:

```bash
python3 skills/analysing/funnel-drop-off-analyst/scripts/analyze.py --test
```

**A marketing page** — the content lives in the `SKILLS` list in `site/build.py`, written
by hand per skill. Add an entry there, then `python3 site/build.py`. Restarting the Repl
with `BUILD=always` rebuilds everything.

**Adding a skill** — create `skills/<category>/<slug>/SKILL.md` (or a flat `<slug>.md`),
run the audit, run `tools/package.py`. A new category also needs adding to `ORDER` and
`TITLES` in `gen_readme.py` — it refuses to run otherwise rather than silently dropping
your skills, which is a bug it used to have.

## Shipping a change

**Adding or editing a skill.** Edit it, then:

```bash
python3 tools/audit.py          # the release gate — must pass
python3 tools/gen_readme.py     # if you changed a frontmatter description
python3 tools/package.py <slug> # rebuild that archive
git add -A && git commit && git push
```

Then `git pull` in the Repl's Shell **and press Run again**. On start-up the server
compares the mtime of everything under `skills/` and `data/` against the built output and
regenerates whatever is stale — you will see `[build] packages (sources changed)` in the
console. A restart with nothing changed skips the build entirely, so this costs nothing
when there is nothing to do. It will not rebuild under a running process, so the restart
is the part to remember.

The browse page shows **when each skill was last updated**, taken from git history rather
than file dates — a pull rewrites every file's mtime, which would otherwise report all 43
skills as changed today. That date is the only signal someone has that the copy they
installed is out of date, so it is worth it being right.

A brand-new skill appears on `/claude-skills` with no code change, because the index
reads the folder at request time. What it does **not** get automatically is a detailed
marketing page — those are hand-written entries in the `SKILLS` list in `site/build.py`.
A new category also has to be added to `ORDER` and `TITLES` in `gen_readme.py`, which
refuses to run otherwise rather than dropping your skills silently.

**Versions matter more here than in most projects.** A skill installed in someone's
Claude never updates itself — their copy is frozen at whatever they uploaded. So bump
`version` in the skill's frontmatter and add a `CHANGELOG.md` entry whenever behaviour
changes. The version shows on the index, in `/healthz`, and at the top of every report
the engine produces, which is the only way to know what someone was running when they
report a problem.

Two consequences worth designing around: the email list on `/pack` is your only channel
for telling people to re-download, and an organisation-wide install is far better than
individual ones, because an admin re-uploads once for everybody.

## Two things to know before this carries real traffic

**The server is Flask's development server.** Fine for a prototype and for sharing a link
with the team. Put a real WSGI server in front of it before it takes public traffic —
`pip install gunicorn`, then `gunicorn -b 0.0.0.0:8080 main:app`, and move the build step
into the deployment build command, which `.replit` already declares.

**Captured emails go to `data/leads.jsonl`.** A file, on the Repl's disk. It survives
restarts but not a redeploy on some Replit plans, and nothing backs it up. Before you
run a real campaign, write them somewhere durable instead — the account already has a
Supabase connector, and swapping the six lines in `pack_submit()` for an insert is the
whole change.

## How the site gets the library

One repository. No keys, no copying, no second place for anything to go stale.

`.github/workflows/publish.yml` runs on every push to `main`. If the gates pass it
regenerates `catalogue.json` and `README.md`, commits them back here, and attaches
the skill archives and sample datasets to the `latest` release.

The site reads two public URLs. Both are permanent and need no credentials:

```
catalogue   https://raw.githubusercontent.com/thomashugnet-netizen/skills-os/main/catalogue.json
a download   https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/<file>
```

`latest` is a moving tag, so a link the site publishes today still resolves after
every future release. Nothing needs updating on the site when the library changes.

If a gate fails, nothing is published and the previous release stays up. Stale
beats broken.

`catalogue.json` lives at the repo root rather than in `dist/` because it is not a
build artifact, it is the published contract: the one file the site reads, visible
to anyone who wants to check what the site is being told. **It is generated. Never
edit it by hand** — the next publish overwrites it.

To see what would be published, without pushing:

```
python3 tools/audit.py && python3 tools/package.py && python3 tools/catalogue.py
python3 tools/site_assets.py --zip     # -> dist/site-assets.zip
```

## Where the unreleased skills live

Only what has passed its gate is in this repository. Everything else — the
skills still being written, the authoring contracts, the old Python site — is in
a **separate private repository**, because this one is meant to be public and 40
unproven files in `skills/` would read as 40 products.

`roadmap.json` carries their names, titles, categories and one-line
descriptions, and nothing else. `tools/catalogue.py` folds it into
`catalogue.json` as `coming_soon`, so the site can show where the library is
going without a line of unreleased content leaving the private repo.

When a skill graduates: move its file here, build it into a folder skill with
its own tests, then regenerate the roadmap from the private repo so it stops
being announced as coming soon.

```
python3 tools/roadmap.py --from <private repo>/skills
```

`tools/roadmap.py` also holds `HELD`: three skills deliberately kept out of the
roadmap because they contradict guidance Fountain's own product gives. That is a
decision about what this library says, not a technical exclusion — announcing
them commits us to shipping them. Removing a name from `HELD` announces it.
