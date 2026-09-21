# How work gets into this repository

The rules, in one place, because they were previously in four heads and a chat log.

## The line

**Anything that changes what people download — a skill, a dataset — goes through a
pull request.** Everything else — tooling, docs, workflows — goes straight to `main`.

One line to remember, and it means a Merge button only gets clicked when it matters.

## Building or changing a skill

1. **Branch.** `skill/<slug>` for a new one, `fix/<slug>-<what>` for a change.
2. **Build it**, with the gates run locally: `tools/audit.py`, then
   `tools/package.py <slug>`, which runs that skill's own suite from inside its
   archive.
3. **Commit on the branch.** Claude does this; Claude cannot push — the GitHub
   credentials live in Thomas's terminal, not in the Cowork session. Thomas runs
   `git push -u origin <branch>`.
4. **Open a pull request.** `.github/workflows/audit.yml` runs on it, so the PR
   shows a tick or a cross before anyone reads a line.
5. **Review it there.** The PR renders the skill readably and takes comments line
   by line. A branch on its own gives neither.
6. **Merge only on green.** A red cross means a test failed. Fix it; do not merge
   past it. Every other guarantee in this repository rests on this one.
7. **Merging publishes.** `.github/workflows/publish.yml` fires on `main` only, so
   a branch never reaches the site. It needs no secret: GitHub issues the workflow
   its own token, and the site reads this repository's public URLs directly.

## Changing a skill that people already have

An installed skill never updates itself. Someone who downloaded v1.0.0 keeps it
until they upload a newer zip, and nothing in this repository can reach them.

So every change to a shipped skill carries two more things, in the same commit:

- **bump `version:`** in the frontmatter — patch for wording, minor for new
  behaviour, major when an old instruction stops being true
- **an entry in that skill's `CHANGELOG.md`**, written for someone deciding
  whether their copy is worth replacing

Without those, the only honest thing to tell a user is "re-download and hope".

## When a skill graduates from the private repository

`skills-os-internal` holds what is written but unproven. When one of them ships:

1. build it here as a folder skill with its own tests
2. **delete it there** — otherwise it is announced as coming soon *and* available
3. `python3 tools/roadmap.py --from <private repo>/skills`, and commit the new
   `roadmap.json`

## Generated files — never edit these

| File | Made by | Where |
|---|---|---|
| `README.md` | `tools/gen_readme.py` | here |
| `catalogue.json` | `tools/catalogue.py` | repo root — the published contract |
| `README.md` (again) | regenerate **before committing**; CI fails if it is stale | |
| `dist/site-assets/` | `tools/site_assets.py` | built in CI, not committed |
| the `latest` release | `publish.yml` | GitHub releases |

`roadmap.json` is the one exception: it is generated, but from the *private*
repository, so CI cannot rebuild it. Regenerate it by hand when that repo changes.

Editing any of the others by hand works right up until the next build silently
overwrites it — which is the correct behaviour, and an unpleasant way to spend an
afternoon.

## When the catalogue gains a field

The site reads `catalogue.json` from this repository's raw URL and ignores what it
does not recognise, in silence.
A new field nobody mentions to the site never appears, and the hour spent looking
for why is entirely avoidable. Adding a field means telling whoever maintains the
site, in the same breath.

## Regenerate before you commit

CI checks that `catalogue.json` and `README.md` are what the sources produce and
fails the build if they are not. It does not fix them: a workflow that commits
to `main` puts a commit there after every publish, and the next push from a
laptop is rejected with a conflict in a generated file. Checking instead costs
one command:

```
python3 tools/catalogue.py && python3 tools/gen_readme.py
```

Run it in the same commit as any change to a skill, a dataset or `roadmap.json`.

## Running the gates locally

```
python3 tools/audit.py                 # covert content, structure, slugs
python3 tools/package.py               # packages all, runs each suite from its zip
python3 tools/catalogue.py             # -> dist/catalogue.json
python3 tools/gen_readme.py            # -> README.md
python3 tools/site_assets.py --zip     # exactly what the site would receive
```
