# Running this on Replit

One process serves the whole library: the per-skill pages, the real `.zip` downloads,
and the email gate for the full pack.

## Import

1. New Repl → **Import from upload** → drop `claude-skills-hr-ops.zip`.
2. Press **Run**. Replit installs Flask from `requirements.txt` and starts `main.py`.

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
