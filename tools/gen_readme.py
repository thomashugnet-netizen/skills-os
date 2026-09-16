"""Regenerates the README's skill tables from frontmatter, so they cannot drift."""
import glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
MARK = "**If your file contains a column that looks nominative"
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

rows = {}
for f in sorted(glob.glob("skills/*/*.md") + glob.glob("skills/*/*/SKILL.md")):
    t = open(f, encoding="utf-8").read()
    cat = f.split(os.sep)[1]
    if os.path.basename(f) == "SKILL.md":
        # A folder skill links to its directory, so GitHub renders its README.
        slug = os.path.basename(os.path.dirname(f))
        link = os.path.dirname(f) + "/"
    else:
        slug = os.path.basename(f)[:-3]
        link = f
    desc = re.search(r"^description:\s*(.+)$", t, re.M).group(1).strip()
    rows.setdefault(cat, []).append((slug, desc, MARK in t, link))

out = []
n_exp = sum(1 for v in rows.values() for r in v if r[2])
total = sum(len(v) for v in rows.values())
out.append(f"All {total} skills, grouped the way the library is laid out. "
           f"The {n_exp} marked **export** read a CSV you produce; the rest need no data.\n")
unlisted = sorted(set(rows) - set(ORDER))
if unlisted:
    raise SystemExit(
        "category on disk but missing from ORDER: " + ", ".join(unlisted)
        + " — add it to ORDER and TITLES, or the skills in it vanish from the README.")

for cat in ORDER:
    if cat not in rows:
        continue
    out.append(f"### {TITLES[cat]}\n")
    out.append("| Skill | What it does |")
    out.append("|---|---|")
    for slug, desc, exp, path in sorted(rows[cat]):
        tag = " **·export**" if exp else ""
        out.append(f"| [`{slug}`]({path}){tag} | {desc} |")
    out.append("")

readme = open("README.md", encoding="utf-8").read()
start = readme.index("## The skills")
# Must be a horizontal rule on its own line. Searching for bare "---" matches
# the |---|---| separator inside the first table, which leaves every old table
# in place below it — that is what duplicated this section 2-3x.
end = readme.index("\n---\n", start) + 1
new = "## The skills\n\n" + "\n".join(out) + "\n"
open("README.md", "w", encoding="utf-8").write(readme[:start] + new + readme[end:])
print(f"README regenerated: {total} skills, {n_exp} export")
