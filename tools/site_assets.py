#!/usr/bin/env python3
"""
Assembles dist/site-assets/ -- everything the public site is allowed to serve.

Run tools/audit.py, tools/package.py and tools/catalogue.py first; this copies
their output, it does not produce it.

The point of a separate step
----------------------------
The site should not reach into this repo and take what it likes. It gets a
folder, and the folder is built from catalogue.json: a skill's zip is copied
because the catalogue says that skill is available, and the catalogue says it
is available because the packager ran its test suite from inside the archive.
So a download the site offers cannot exist unless something proved it works.

The inverse matters as much. Nothing else travels -- not the authoring
contracts in tools/, not the generator, not the site code. The published
surface is this folder and nothing but.

    python3 tools/site_assets.py            # -> dist/site-assets/
    python3 tools/site_assets.py --zip      # and dist/site-assets.zip
"""

import glob
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DIST, "site-assets")


def build():
    catalogue_path = os.path.join(DIST, "catalogue.json")
    if not os.path.exists(catalogue_path):
        raise SystemExit("No dist/catalogue.json. Run tools/catalogue.py first.")
    with open(catalogue_path, encoding="utf-8") as fh:
        cat = json.load(fh)

    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "skills"))
    os.makedirs(os.path.join(OUT, "data"))
    shutil.copy2(catalogue_path, os.path.join(OUT, "catalogue.json"))

    copied = []
    for skill in cat["skills"]:
        if not skill["available"]:
            continue
        name = os.path.basename(skill["download"]["path"])
        source = os.path.join(DIST, name)
        if not os.path.exists(source):
            # The catalogue and the dist folder disagreeing is not something to
            # paper over: the site would advertise a download that 404s.
            raise SystemExit(
                f"{skill['slug']} is available in the catalogue but {name} is "
                "not in dist/. Run tools/package.py.")
        shutil.copy2(source, os.path.join(OUT, "skills", name))
        copied.append(name)

    datasets = []
    for ds in cat["datasets"]:
        for key in ("pipeline", "spend"):
            entry = ds.get(key)
            if not entry:
                continue
            name = os.path.basename(entry["path"])
            source = os.path.join(DATA, name)
            if not os.path.exists(source):
                raise SystemExit(f"{name} is in the catalogue but not in data/.")
            shutil.copy2(source, os.path.join(OUT, "data", name))
            datasets.append(name)

    return copied, datasets


def main():
    skills, datasets = build()
    total = sum(os.path.getsize(p) for p in glob.glob(os.path.join(OUT, "**", "*"),
                                                      recursive=True)
                if os.path.isfile(p))
    print(f"site-assets  {len(skills)} skill(s), {len(datasets)} data file(s), "
          f"{total / 1_000_000:.1f} MB")
    for name in skills:
        print(f"  skills/{name}")
    if "--zip" in sys.argv:
        archive = shutil.make_archive(OUT, "zip", DIST, "site-assets")
        print(f"  -> {os.path.relpath(archive, ROOT)} "
              f"({os.path.getsize(archive) / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
