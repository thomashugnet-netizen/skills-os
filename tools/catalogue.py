#!/usr/bin/env python3
"""
Writes dist/catalogue.json: one machine-readable description of the library.

Why this exists
---------------
The public site used to restate what each skill is -- its name, its category,
its description, whether it needs a data export, whether it is ready. Two
places describing the same object drift, and ours drifted within a day: the
site told readers to attach one .md file long after the skill had become a
zipped folder.

So the repo publishes the facts and the site reads them. Anything a visitor is
told about a skill should be derivable from this file, and anything that is not
in here is something the site had to invent.

    python3 tools/catalogue.py            # -> dist/catalogue.json
    python3 tools/catalogue.py --print    # to stdout instead
"""

import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Every download the site offers, as a URL it can use verbatim. Release assets
# are flat -- there are no folders in a GitHub release -- so a site building its
# own links from a repo path would 404 on every one of them. Publishing the
# finished URL removes the chance to get it wrong.
RELEASE = ("https://github.com/thomashugnet-netizen/skills-os"
           "/releases/latest/download")
DIST = os.path.join(ROOT, "dist")
DATA = os.path.join(ROOT, "data")

# A skill that carries this sentence is one that reads a candidate export. It is
# the same marker the audit gate keys on, so the two can never disagree.
DATA_BLOCK_MARKER = ("**If your file contains a column that looks nominative, I will "
                     "stop and ask you to re-export rather than analyse it.**")

# The four samples, in the order a reader should be offered them.
DATASETS = [
    ("frontline", "Retail & multi-site", "hire",
     "42 stores, a seasonal peak, heavy job-board reliance."),
    ("qsr", "Quick service restaurants", "hire",
     "42 restaurants, the shortest funnel - apply to first shift in days."),
    ("logistics", "Logistics & delivery", "hire",
     "42 stations, drug screens and DOT medicals before day one."),
    ("gig", "Delivery & courier (gig)", "activation",
     "42 markets, no interview and no offer - activation, not hiring."),
]


def git_date(rel):
    """Commit date, never file mtime: a clone rewrites every mtime, which would
    report the whole library as changed today."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", rel],
                             cwd=ROOT, capture_output=True, text=True, timeout=20)
        return (out.stdout.strip() or None)
    except (OSError, subprocess.SubprocessError):
        return None


def size(path):
    return os.path.getsize(path) if os.path.exists(path) else None


def rows(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8-sig") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def skills():
    paths = (sorted(glob.glob(os.path.join(ROOT, "skills", "*", "*.md")))
             + sorted(glob.glob(os.path.join(ROOT, "skills", "*", "*", "SKILL.md"))))
    out = []
    for path in paths:
        parts = os.path.relpath(path, ROOT).split(os.sep)
        category = parts[1]
        folder = os.path.dirname(path)
        is_folder = os.path.basename(path) == "SKILL.md"
        slug = os.path.basename(folder) if is_folder else parts[-1][:-3]
        text = open(path, encoding="utf-8").read()

        def field(key):
            found = re.search(rf"^{key}:\s*(.+)$", text, re.M)
            return found.group(1).strip() if found else None

        heading = re.search(r"^# (.+)$", text, re.M)
        zip_path = os.path.join(DIST, slug + ".zip")
        # "Available" means there is something to download that passed the
        # gates, not that the file exists. The gate differs by kind -- an
        # analysis skill proves itself against planted patterns in the sample
        # data, a writing skill against fixtures with planted faults -- but
        # every available skill ships code that says what "correct" means for
        # it and a suite the packager ran from inside the archive.
        has_engine = bool(glob.glob(os.path.join(folder, "scripts", "*.py")))
        available = has_engine and os.path.exists(zip_path)

        out.append({
            "slug": slug,
            "title": heading.group(1).strip() if heading else slug,
            "category": category,
            "description": field("description") or "",
            "version": field("version"),
            "updated": git_date(os.path.relpath(path, ROOT).replace(os.sep, "/")),
            "available": available,
            "tested_code": has_engine,
            "needs_dataset": DATA_BLOCK_MARKER in text,
            "download": ({"path": f"skills/{slug}.zip",
                          "file": f"{slug}.zip",
                          "url": f"{RELEASE}/{slug}.zip",
                          "bytes": size(zip_path)}
                         if available else None),
        })
    return sorted(out, key=lambda s: (s["category"], s["slug"]))


def datasets():
    out = []
    for slug, label, funnel, blurb in DATASETS:
        pipeline = os.path.join(DATA, f"{slug}_pipeline_sample.csv")
        if not os.path.exists(pipeline):
            continue
        spend = os.path.join(DATA, f"{slug}_spend_sample.csv")
        if slug == "frontline":
            spend = os.path.join(DATA, "sourcing_spend_sample.csv")
        out.append({
            "slug": slug,
            "label": label,
            "blurb": blurb,
            "funnel": funnel,
            "rows": rows(pipeline),
            "pipeline": {"path": f"data/{os.path.basename(pipeline)}",
                         "file": os.path.basename(pipeline),
                         "url": f"{RELEASE}/{os.path.basename(pipeline)}",
                         "bytes": size(pipeline)},
            "spend": ({"path": f"data/{os.path.basename(spend)}",
                       "file": os.path.basename(spend),
                       "url": f"{RELEASE}/{os.path.basename(spend)}",
                       "bytes": size(spend)}
                      if os.path.exists(spend) else None),
        })
    return out


def coming_soon():
    """Names only, of what exists but is not published. It lives in
    roadmap.json because the skills themselves are in a private repository:
    a reader gets to see where the library is going, and not a line of
    unreleased content."""
    path = os.path.join(ROOT, "roadmap.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("coming_soon", [])


def build():
    items = skills()
    soon = coming_soon()
    return {
        "$comment": "Generated by tools/catalogue.py. Do not edit by hand, and do "
                    "not restate any of it elsewhere -- read it.",
        "schema_version": 1,
        # Deliberately no generated_at. A wall-clock stamp changes on every run,
        # so the file would never match itself twice and the CI check that keeps
        # it honest could never pass. Each skill's own "updated" comes from git
        # history and carries the information a timestamp here pretended to.
        "library": {
            "name": "Claude Skills for HR Ops",
            "publisher": "Fountain",
            "skills": len(items) + len(soon),
            "available": sum(1 for s in items if s["available"]),
            "coming_soon": len(soon),
            "categories": sorted({s["category"] for s in items}
                                 | {s["category"] for s in soon}),
        },
        "source": {
            "repo": "https://github.com/thomashugnet-netizen/skills-os",
            "catalogue": "https://raw.githubusercontent.com/thomashugnet-netizen"
                         "/skills-os/main/catalogue.json",
            "downloads": RELEASE,
        },
        "install": {
            "format": "zip",
            "steps": [
                "Download the .zip - do not unzip it.",
                "In Claude, open Settings, then Customize, then Skills.",
                "Press + and upload the .zip.",
                "Start a new conversation and describe your problem. "
                "Claude picks the skill up on its own.",
            ],
            "note": "An installed skill never updates itself. Re-upload the zip "
                    "to move to a newer version.",
        },
        "skills": items,
        "coming_soon": soon,
        "datasets": datasets(),
    }


if __name__ == "__main__":
    doc = build()
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if "--print" in sys.argv:
        print(text)
    else:
        # At the repo root, not in dist/. It is not a build artifact -- it is the
        # published contract, the one file the site reads. Keeping it in the tree
        # means anyone can see what the site is being told, and the site can fetch
        # it straight from GitHub with no build step and no credentials.
        for target in (os.path.join(ROOT, "catalogue.json"),
                       os.path.join(DIST, "catalogue.json")):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(text)
        print(f"catalogue.json  {doc['library']['available']} available, "
              f"{doc['library']['coming_soon']} coming soon, "
              f"{len(doc['datasets'])} datasets")
