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
| `catalogue.json` | `tools/catalogue.py` | `dist/`, then the release — not committed |
| `dist/site-assets/` | `tools/site_assets.py` | built in CI, not committed |
| the `latest` release | `publish.yml` | GitHub releases |

`roadmap.json` is the one exception: it is generated, but from the *private*
repository, so CI cannot rebuild it. Regenerate it by hand when that repo changes.

Editing any of the others by hand works right up until the next build silently
overwrites it — which is the correct behaviour, and an unpleasant way to spend an
afternoon.

## The slug is a public identifier

A skill's slug — the folder name, which the audit forces to match the frontmatter
`name` — is now the identifier three systems use:

| Where | Looks like |
|---|---|
| the download | `.../releases/latest/download/<slug>.zip` |
| the zip's own layout | `<slug>/SKILL.md` at the top level |
| **Import in Cue** | `https://cue.fountain.com/import/<slug>` |

There is deliberately **no second identifier and no mapping table.** A numeric id
with a table mapping it to a slug would be two records of one fact, and the one
kept by hand is the one that ends up wrong. The audit refuses a slug that is not
lowercase words joined by single hyphens, because all three systems above parse
it and they do not agree on underscores, capitals or spaces.

The consequence to know: **renaming a published skill breaks every link to it** —
the download, the site's page, and anyone's saved Cue import URL. It is not a
rename, it is a retirement plus a new skill. Get the slug right before the first
publish.

`catalogue.py` builds the Cue URL from one constant, `CUE_IMPORT`. Neither the
site nor Cue should assemble that URL from a base and a slug: that puts the route
in a second place, and the second place is the one still pointing at the old
route a month later. The site reads `skills[].cue.import_url` and renders the
button only when it is present — which is never for a coming-soon skill, so the
button cannot advertise something that does not exist.

## Cue reads this catalogue; it holds no copy

Cue receives a slug in the URL and resolves it by fetching
`catalogue.json` from the `latest` release, at the moment of the click. That
gives it three things for free:

- a skill that is not published cannot be imported — it is not in the file
- the version Cue records is whatever the file says at click time, which is the
  version it is actually importing
- nothing on the Cue side needs updating when the library changes

If Cue ever keeps its own list instead, that list will drift from this one. That
failure has already happened twice in this project, in both directions.

## When the catalogue gains a field

The site reads `catalogue.json` from the latest release and ignores what it does
not recognise, in silence.
A new field nobody mentions to the site never appears, and the hour spent looking
for why is entirely avoidable. Adding a field means telling whoever maintains the
site, in the same breath.

## Regenerate the README before you commit

`README.md` is generated and committed, so it goes stale unless it is rebuilt in
the same commit as any change to a skill, a dataset or `roadmap.json`:

```
python3 tools/catalogue.py && python3 tools/gen_readme.py
```

CI does not check it and does not fix it. A workflow that commits to `main` puts
a commit there after every publish, and the next push from a laptop is rejected
with a conflict in a generated file — which happened twice before this rule
replaced it.

## Running the gates locally

```
python3 tools/audit.py                 # covert content, structure, slugs
python3 tools/package.py               # packages all, runs each suite from its zip
python3 tools/catalogue.py             # -> dist/catalogue.json
python3 tools/gen_readme.py            # -> README.md
python3 tools/site_assets.py --zip     # exactly what the site would receive
```

## How the site gets the library

One repository. No keys, no copying, no second place for anything to go stale.

`.github/workflows/publish.yml` runs on every push to `main`. If the gates pass it
builds `catalogue.json` and attaches it to the `latest` release together with the
skill archives and the sample datasets it describes.

Everything the site needs is in that release, at permanent URLs that need no
credentials:

```
https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/catalogue.json
```

That one file names every other URL, so the site needs no second constant.
`latest` is a moving tag, so a link published today still resolves after every
future release, and nothing on the site needs updating when the library changes.

**CI never writes to this repository.** A publish puts no commit on `main`, so a
push from a laptop is never rejected by one. `catalogue.json` is not committed
either: it records each archive's byte size, and a zip is not byte-identical
across zlib versions, so a committed copy would drift from the one CI builds for
reasons nobody can act on. It ships inside the release, beside the archives it
describes, where the two cannot disagree.

If a gate fails, nothing is published and the previous release stays up. Stale
beats broken.

To see exactly what would be published, without pushing:

```
python3 tools/audit.py && python3 tools/package.py && python3 tools/catalogue.py
python3 tools/site_assets.py --zip     # -> dist/site-assets.zip
```

## Where the unreleased skills live

Only what has passed its gate is in this repository. Everything else — the skills
still being written, the authoring contracts, the retired Python site — is in a
separate private repository, because this one is public and forty unproven files
in `skills/` would read as forty products.

`roadmap.json` carries their names, titles, categories and one-line descriptions,
and nothing else. `tools/catalogue.py` folds it into `catalogue.json` as
`coming_soon`, so the site can show where the library is going without a line of
unreleased content leaving the private repo.

```
python3 tools/roadmap.py --from <private repo>/skills
```

`tools/roadmap.py` also holds `HELD`: three skills deliberately kept out of the
roadmap because they contradict guidance Fountain's own product gives. That is a
decision about what this library says, not a technical exclusion — announcing a
skill commits us to shipping it, so removing a name from `HELD` is a publication
decision.
