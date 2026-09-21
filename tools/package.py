"""
Builds the installable .zip for each skill.

A skill is installed by uploading a zip of its folder — Claude reads SKILL.md
at the top of that folder. So the archive must contain <slug>/SKILL.md, and
everything the skill needs must be inside it: a skill that reads the sample
dataset from the repo root works in the repo and breaks on someone's laptop.

    python3 tools/package.py                 # every skill
    python3 tools/package.py funnel-drop-off-analyst
    python3 tools/package.py --no-verify     # skip the standalone test run

Each export skill gets the sample dataset packaged inside it, and any skill
shipping a test suite is extracted to a scratch directory and run there before
the archive is accepted. Packaging something that only works in this repo is
the failure mode this script exists to prevent.
"""

import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
DIST = os.path.join(ROOT, "dist")
SAMPLES = ["data/frontline_pipeline_sample.csv", "data/sourcing_spend_sample.csv"]
DATA_BLOCK_MARKER = "**If your file contains a column that looks nominative"
SKIP = {"__pycache__", ".DS_Store"}


def discover():
    """(slug, category, skill_md_path, folder_or_None) for every skill."""
    found = []
    for path in sorted(glob.glob("skills/*/*.md")):
        found.append((os.path.basename(path)[:-3], path.split(os.sep)[1], path, None))
    for path in sorted(glob.glob("skills/*/*/SKILL.md")):
        folder = os.path.dirname(path)
        found.append((os.path.basename(folder), path.split(os.sep)[1], path, folder))
    return found


def version_of(skill_md):
    import re
    found = re.search(r"^version:\s*(.+)$",
                      open(skill_md, encoding="utf-8").read(), re.M)
    return found.group(1).strip() if found else None


def files_for(slug, skill_md, folder):
    """(archive_path, source_path) pairs. Archive paths are rooted at <slug>/."""
    out = [(f"{slug}/SKILL.md", skill_md)]
    if folder:
        for dirpath, dirs, names in os.walk(folder):
            dirs[:] = [d for d in dirs if d not in SKIP]
            for name in sorted(names):
                if name in SKIP or name == "SKILL.md" or name.startswith("."):
                    continue
                full = os.path.join(dirpath, name)
                out.append((f"{slug}/{os.path.relpath(full, folder)}", full))

    if DATA_BLOCK_MARKER in open(skill_md, encoding="utf-8").read():
        for sample in SAMPLES:
            if os.path.exists(sample):
                out.append((f"{slug}/data/{os.path.basename(sample)}", sample))
    return out


def verify_standalone(slug, members):
    """Extract to a scratch directory and run the skill's own test suite there.
    Proves the archive carries everything it needs."""
    # Any script in scripts/ that answers --test is this skill's suite. Keying
    # on analyze.py specifically meant a writing skill's checker was packaged
    # without ever being run from the archive -- which is exactly the failure
    # this function exists to catch.
    engine = next((a for a, _ in members
                   if "/scripts/" in a and a.endswith(".py")
                   and "--test" in open(_, encoding="utf-8").read()), None)
    if not engine:
        return True, "no test suite to run"

    tmp = tempfile.mkdtemp(prefix=f"pkg-{slug}-")
    try:
        for archive_path, source in members:
            target = os.path.join(tmp, archive_path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(source, target)
        proc = subprocess.run(
            [sys.executable, os.path.join(tmp, engine), "--test"],
            capture_output=True, text=True, timeout=300)
        if proc.returncode == 0:
            tail = [l for l in proc.stdout.strip().splitlines() if "passed" in l]
            return True, (tail[-1].strip() if tail else "tests passed")
        return False, (proc.stdout + proc.stderr).strip().splitlines()[-1][:120]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def build(slug, skill_md, folder, verify=True):
    members = files_for(slug, skill_md, folder)
    if verify:
        ok, detail = verify_standalone(slug, members)
        if not ok:
            return None, f"FAILED standalone verification: {detail}"
    else:
        detail = "verification skipped"

    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, f"{slug}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for archive_path, source in members:
            zf.write(source, archive_path)
    return out, detail


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    verify = "--no-verify" not in sys.argv

    skills = discover()
    if args:
        skills = [s for s in skills if s[0] in args]
        missing = set(args) - {s[0] for s in skills}
        if missing:
            print("unknown skill(s): " + ", ".join(sorted(missing)))
            return 1

    built, failed = [], []
    for slug, _cat, skill_md, folder in skills:
        out, detail = build(slug, skill_md, folder, verify)
        if out is None:
            failed.append((slug, detail))
            print(f"FAIL  {slug}: {detail}")
            continue
        built.append(out)
        size = os.path.getsize(out) / 1024
        note = f"  [{detail}]" if detail and "no test suite" not in detail else ""
        version = version_of(skill_md)
        stamp = f"  v{version}" if version else ""
        print(f"ok    {slug}.zip{stamp}  {size:>7.0f} KB{note}")

    print(f"\n{len(built)} packaged, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
