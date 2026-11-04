"""
The sections of a skill's public page, read from the files the skill already has.

Why this exists
---------------
The site's skill page used to say four things: a title, a description, who made
it and how to install it. Everything a reader needs to decide whether a skill is
for them -- what to give it, what comes back, how it works, where it stops --
was already written, in the skill's own SKILL.md and README.md, and the site had
no way to read it. The rule the site lives by is that it writes no skill text of
its own, so the choice was between a thin page and a second copy of the text.
This is the third option: the catalogue carries the sections, verbatim.

Nothing here is rewritten. A section is the markdown under one heading, with
relative links made absolute so they still work off GitHub. A section a skill
does not have is left out (None), and the site leaves that block out with it.

Where each block comes from:

    README.md   summary, why, audience, fit, verify
    SKILL.md    inputs, outputs, steps, pushback, cost, works_with, limits
    PAGE.md     example_prompt, example_output
    CHANGELOG   changelog (catalogue.py), dated from git

PAGE.md is the one file written for the page. It holds only what exists nowhere
else -- a prompt someone would type, and an excerpt of what the skill returned
on its own sample data -- and it is left out of the zip (tools/package.py), so
adding or editing it never changes what anyone downloads.
"""

import os
import posixpath
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOB = "https://github.com/thomashugnet-netizen/skills-os/blob/main"

# Headings vary a little between skills written months apart. First match wins.
ALIASES = {
    "summary":  ["What it does"],
    "summary_fallback": ["What this does"],
    "why":      ["Why it exists"],
    "audience": ["Who it's for"],
    "fit":      ["Where it fits, and where it does not", "Where it fits"],
    "verify":   ["Verifying this yourself", "Verifying it works", "Verifying this",
                 "Verify before you rely on it"],
    "inputs":   ["What to give me", "What I need from you"],
    "outputs":  ["What you get"],
    "steps":    ["How I work", "The rules I hold myself to"],
    "pushback": ["What I will push back on", "What I'll push back on",
                 "What I will not write"],
    "cost":     ["What it costs you to run"],
    "works":    ["Works with"],
    "limits":   ["Where this stops"],
}

STEP_PREFIX = re.compile(r"^(?:Step|Pass)\s+\d+\s*[:.—–-]?\s*", re.I)


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def sections(text, level=2):
    """{heading: body} for every heading at `level`, ignoring '#' lines inside
    fenced code, which a shell comment would otherwise turn into a section."""
    out, current, buf, fenced = {}, None, [], False
    mark = "#" * level + " "
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line.startswith(mark) and not line.startswith(mark + "#"):
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current, buf = line[len(mark):].strip(), []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def pick(secs, key):
    for name in ALIASES[key]:
        if secs.get(name):
            return secs[name]
    return None


def absolute_links(md, folder):
    """A README links to ../../../README.md and scripts/x.py. Off GitHub those
    are dead, so each becomes the file's URL on main."""
    if not md:
        return md
    base = os.path.relpath(folder, ROOT).replace(os.sep, "/")

    def fix(match):
        label, target = match.group(1), match.group(2)
        if re.match(r"^(https?:|mailto:|#)", target):
            return match.group(0)
        path, _, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(base, path))
        if resolved.startswith(".."):
            return label  # points outside the repo: keep the words, drop the link
        url = f"{BLOB}/{resolved}" + (f"#{anchor}" if anchor else "")
        return f"[{label}]({url})"

    return re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", fix, md)


def steps(md, folder):
    """How the skill runs, as titled steps. Most skills write each step as a
    ### heading; the older writing skills use bold-led paragraphs. Either way
    the text is the skill's own, with only the 'Step 3:' prefix removed, since
    the page numbers the steps itself."""
    if not md:
        return []
    subs = sections(md, level=3)
    if subs:
        return [{"title": STEP_PREFIX.sub("", title).strip(),
                 "markdown": absolute_links(body, folder)}
                for title, body in subs.items()]
    out = []
    for para in re.split(r"\n\s*\n", md):
        lead = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", para.strip(), re.S)
        if not lead:
            if out:  # a paragraph continuing the step above
                out[-1]["markdown"] += "\n\n" + absolute_links(para.strip(), folder)
            continue
        title = lead.group(1).strip().rstrip(".")
        out.append({"title": title, "markdown": absolute_links(lead.group(2).strip(), folder)})
    return out


def works_with(md, folder, slugs):
    """Each '- **Name.** text' bullet, plus the library skills it names, so
    the site can link to them without matching names itself."""
    if not md:
        return []
    out = []
    for item in re.split(r"\n(?=- )", md.strip()):
        item = item.strip()
        if not item.startswith("- "):
            continue
        item = item[2:]
        lead = re.match(r"^\*\*(.+?)\*\*[.,:]?\s*(?:[—–-]\s*)?(.*)$", item, re.S)
        name, rest = (lead.group(1), lead.group(2)) if lead else (item, "")
        named = [s for s in re.findall(r"`([a-z0-9-]+)`", name + " " + rest) if s in slugs]
        out.append({"name": re.sub(r"[`*]", "", name).strip().rstrip("."),
                    "markdown": absolute_links(rest.strip(), folder),
                    "skills": list(dict.fromkeys(named))})
    return out


def example(folder):
    """The two blocks only PAGE.md has. The output's first paragraph says where
    the excerpt came from; the site prints it as the caption."""
    secs = sections(read(os.path.join(folder, "PAGE.md")))
    prompt = secs.get("Example prompt")
    if prompt:
        prompt = re.sub(r"^>\s?", "", prompt, flags=re.M).strip().strip('"“”')
    output = None
    body = secs.get("Example output")
    if body:
        caption, _, rest = body.partition("\n\n")
        output = {"caption": caption.strip(),
                  "markdown": absolute_links(rest.strip(), folder)}
    return prompt or None, output


def fit(readme, folder):
    found = pick(readme, "fit")
    if found:
        return absolute_links(found, folder)
    yes, no = readme.get("What's supported"), readme.get("What's not supported")
    if not (yes or no):
        return None
    parts = []
    if yes:
        parts.append("**Supported**\n\n" + yes)
    if no:
        parts.append("**Not supported**\n\n" + no)
    return absolute_links("\n\n".join(parts), folder)


def page(folder, skill_text, slugs):
    if not folder:
        return None
    skill = sections(skill_text)
    readme = sections(read(os.path.join(folder, "README.md")))
    prompt, output = example(folder)
    summary = pick(readme, "summary") or pick(skill, "summary_fallback")

    def doc(secs, key):
        return absolute_links(pick(secs, key), folder)

    return {
        "summary": absolute_links(summary, folder),
        "why": doc(readme, "why"),
        "audience": doc(readme, "audience"),
        "fit": fit(readme, folder),
        "example_prompt": prompt,
        "inputs": doc(skill, "inputs"),
        "outputs": doc(skill, "outputs"),
        "example_output": output,
        "steps": steps(pick(skill, "steps"), folder),
        "pushback": doc(skill, "pushback"),
        "cost": doc(skill, "cost"),
        "works_with": works_with(pick(skill, "works"), folder, slugs),
        "limits": doc(skill, "limits"),
        "verify": doc(readme, "verify") or doc(skill, "verify"),
    }


def version_date(skill_md_rel, version):
    """When this version first appeared in SKILL.md: the oldest commit that
    added the line. Git history, never mtimes, for the reason catalogue.py
    gives."""
    try:
        out = subprocess.run(
            ["git", "log", "--format=%cI", f"-Sversion: {version}", "--", skill_md_rel],
            cwd=ROOT, capture_output=True, text=True, timeout=20)
        lines = out.stdout.strip().splitlines()
        return lines[-1] if lines else None
    except (OSError, subprocess.SubprocessError):
        return None


def changelog(folder, skill_md_rel, current):
    """Every '## X.Y.Z' entry, newest first, as the skill's CHANGELOG writes
    it. The site shows the version and this history, so it reads both from
    here rather than keeping its own."""
    if not folder:
        return []
    secs = sections(read(os.path.join(folder, "CHANGELOG.md")))
    out = []
    for heading, body in secs.items():
        found = re.match(r"^v?(\d+\.\d+\.\d+)\b", heading)
        if not found:
            continue
        version = found.group(1)
        out.append({"version": version,
                    "date": version_date(skill_md_rel, version),
                    "current": version == current,
                    "markdown": absolute_links(body, folder)})
    out.sort(key=lambda e: tuple(int(p) for p in e["version"].split(".")), reverse=True)
    return out
