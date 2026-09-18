#!/usr/bin/env python3
"""
Writes README.md entirely from dist/catalogue.json.

It used to regenerate only the tables and leave the prose around them by hand,
which is how the README came to announce 43 skills and tell people to attach a
.md file to a conversation, months after neither was true. Anything stated here
about the library is now derived; if a fact is missing from the catalogue, it
does not go in the README.

    python3 tools/catalogue.py && python3 tools/gen_readme.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOGUE = os.path.join(ROOT, "dist", "catalogue.json")

ORDER = ["writing", "sourcing", "screening", "interviewing", "analysing",
         "onboarding", "complying", "retaining", "operating"]
TITLES = {
    "writing": "Writing — the words that go out",
    "sourcing": "Sourcing — where the applicants come from",
    "screening": "Screening — who gets through",
    "interviewing": "Interviewing — run by non-recruiters",
    "analysing": "Analysing — where the numbers are",
    "onboarding": "Onboarding — apply to first shift",
    "complying": "Complying — preparation, never advice",
    "retaining": "Retaining — after the first shift",
    "operating": "Operating — running the function",
}


def mb(n):
    return f"{n / 1_000_000:.1f} MB" if n >= 100_000 else f"{n // 1000} KB"


def main():
    if not os.path.exists(CATALOGUE):
        raise SystemExit("No dist/catalogue.json. Run tools/catalogue.py first.")
    with open(CATALOGUE, encoding="utf-8") as fh:
        cat = json.load(fh)
    lib, install = cat["library"], cat["install"]
    live = [s for s in cat["skills"] if s["available"]]
    soon = cat["coming_soon"]

    unlisted = sorted({s["category"] for s in live + soon} - set(ORDER))
    if unlisted:
        raise SystemExit("category not in ORDER: " + ", ".join(unlisted)
                         + " — add it to ORDER and TITLES or its skills vanish.")

    o = [f"# {lib['name']}", ""]
    o.append("Skills that make Claude useful to a frontline hiring team — high-volume "
             "hourly hiring, multi-site operations, shift work.")
    o.append("")
    o.append(f"**{lib['available']} ready now. {lib['coming_soon']} more on the way.** "
             "Every one that ships carries the code that decides what *correct* means "
             "for it, and a test suite that proves it — run them yourself, they are in "
             "the box.")
    o.append("")

    o.append("## Installing one")
    o.append("")
    for i, step in enumerate(install["steps"], 1):
        o.append(f"{i}. {step}")
    o.append("")
    o.append(f"*{install['note']}*")
    o.append("")

    o.append("## Ready now")
    o.append("")
    o.append("| Skill | What it does | |")
    o.append("|---|---|---|")
    for s in sorted(live, key=lambda s: (s["category"], s["slug"])):
        folder = f"skills/{s['category']}/{s['slug']}/"
        need = "needs a CSV export" if s["needs_dataset"] else "no data needed"
        o.append(f"| [`{s['slug']}`]({folder}) | {s['description']} | {need}, "
                 f"{mb(s['download']['bytes'])} |")
    o.append("")

    if cat["datasets"]:
        o.append("## Sample datasets")
        o.append("")
        o.append("Nobody should hand real candidate data to a tool they have not "
                 "watched work. Every sample is synthetic, carries no personal data "
                 "of any kind, and has real causal structure buried in it — including "
                 "two traps for anything that mistakes correlation for cause.")
        o.append("")
        o.append("| Dataset | Rows | Shape |")
        o.append("|---|---|---|")
        for d in cat["datasets"]:
            o.append(f"| [`{d['slug']}`](data/{os.path.basename(d['pipeline']['path'])}) "
                     f"| {d['rows']:,} | {d['label']} — {d['blurb']} |")
        o.append("")

    if soon:
        o.append("## Coming soon")
        o.append("")
        o.append("Written, not yet through their gate. They ship when they pass it.")
        o.append("")
        by_cat = {}
        for s in soon:
            by_cat.setdefault(s["category"], []).append(s)
        for c in ORDER:
            if c not in by_cat:
                continue
            o.append(f"**{TITLES[c]}**")
            o.append("")
            for s in sorted(by_cat[c], key=lambda s: s["slug"]):
                tag = " *(needs a CSV export)*" if s["needs_dataset"] else ""
                o.append(f"- `{s['slug']}` — {s['description']}{tag}")
            o.append("")

    o.append("## How this is built")
    o.append("")
    o.append("`tools/audit.py` blocks hidden or deceptive content across every file a "
             "skill ships. `tools/package.py` extracts each archive to a scratch "
             "directory and runs that skill's own suite from inside it, so a package "
             "that only works in this repository is not a package. Nothing reaches the "
             "site unless both pass — see `REPLIT.md`.")
    o.append("")
    o.append(f"Published by {lib['publisher']}. MIT licensed.")
    o.append("")

    with open(os.path.join(ROOT, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(o))
    print(f"README regenerated: {lib['available']} ready, {lib['coming_soon']} coming soon")
    return 0


if __name__ == "__main__":
    sys.exit(main())
