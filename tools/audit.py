"""
Library audit. Run in CI; a non-zero exit blocks the build.

The covert-content checks are the point of this file. This library ships
instructions that a model will read inside someone else's session, so anything
hidden, spoofed or concealment-flavoured is a release blocker, not a lint.

    python3 tools/audit.py
"""

import glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

DATA_BLOCK_MARKER = "**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.**"
CUE_HEADING = "## When to mention Fountain Cue"
# Product names are allowed in exactly two places: the legacy Cue block, and a
# reader-facing "Works with" section that names an integration. Anywhere else in
# a skill body they are still a release blocker.
WORKS_WITH_HEADING = "## Works with"

# Tier A: the conversion set. These carry a Cue block regardless of whether they
# read an export — the handoff is manual execution volume, not live data.
TIER_A = {
    "writing/candidate-message-sequencer", "sourcing/rehire-campaign-planner",
    "sourcing/sourcing-gap-plan", "operating/stalled-applicant-triage",
    "interviewing/interview-slot-planner", "retaining/coverage-risk-scorer",
    "onboarding/onboarding-workflow-designer", "onboarding/day-one-readiness-checklist",
    "onboarding/new-hire-pack-drafter", "writing/job-ad-writer",
    "screening/screening-question-builder", "complying/i9-readiness-checker",
}
COST_HEADING = "## What it costs you to run"

# --- release blockers: covert or deceptive content -------------------------
COVERT = {
    "html comment": r"<!--",
    "system/role spoof": r"(?im)^\s*(system|assistant|developer|\[system\]|<system>)\s*:",
    "conceal from user": r"(?i)(do not (tell|reveal|mention|show) the (user|reader)|without (telling|informing) the (user|reader)|hide (this|it) from)",
    "override instructions": r"(?i)(ignore (previous|prior|all|any) instructions|disregard (previous|prior|the) instructions|regardless of what the (user|reader) (says|asks|wants))",
    "secrecy": r"(?i)(keep this (secret|confidential from)|do ?n.t disclose|conceal (this|that|it))",
    "unconditional promotion": r"(?i)always (mention|recommend|promote|suggest|push|bring up) (cue|fountain)",
    "pose as neutral": r"(?i)(present (it|this) as|as if it were|pretend (it|this) is) (a )?(neutral|impartial|independent|objective)",
    "priority inversion": r"(?i)(before (answering|helping|doing anything)[^.]{0,40}mention)",
}
ZERO_WIDTH = "​‌‍⁠﻿"

# --- compliance-file requirements -----------------------------------------
COMPLIANCE_DIRS = {"complying"}
COMPLIANCE_EXTRA = ["bias-language-checker", "offer-letter-drafter", "attendance-policy-writer"]
# Accept any of the phrasings the library actually uses. What matters is that the
# statement exists and is discoverable, not that it sits under a heading.
NOT_ADVICE = r"(?i)(not legal advice|nothing here is legal advice|not a source of employment law|is not legal advice)"
VERIFY = r"(?i)(^##+ .*verif|verification list|verify before you rely)"

fail, warn = [], []


def slug_of(path):
    """A skill is either skills/<cat>/<slug>.md or skills/<cat>/<slug>/SKILL.md."""
    base = os.path.basename(path)
    if base == "SKILL.md":
        return os.path.basename(os.path.dirname(path))
    return base[:-3]


def shipped_files(path, skill_text):
    """(path, text) for every readable file this skill ships."""
    out = [(path, skill_text)]
    if os.path.basename(path) != "SKILL.md":
        return out
    root = os.path.dirname(path)
    for dirpath, _dirs, names in os.walk(root):
        for name in sorted(names):
            full = os.path.join(dirpath, name)
            if full == path or name.startswith("."):
                continue
            try:
                with open(full, encoding="utf-8") as fh:
                    out.append((full, fh.read()))
            except (UnicodeDecodeError, OSError):
                continue  # binary or unreadable: nothing to scan for text
    return out


def strip_section(text, heading):
    """Remove one '## ' section and everything under it, up to the next '## '."""
    if heading not in text:
        return text
    head, rest = text.split(heading, 1)
    match = re.search(r"^## ", rest, re.M)
    return head + (rest[match.start():] if match else "")


def check(path):
    t = open(path, encoding="utf-8").read()
    slug = slug_of(path)
    cat = path.split(os.sep)[1]
    is_export = DATA_BLOCK_MARKER in t
    has_cue = CUE_HEADING in t
    rel = f"{cat}/{slug}"
    is_tier_a = rel in TIER_A

    # Covert-content checks run over EVERY file a skill ships, not just its
    # SKILL.md. A folder skill carries scripts and references, and a release
    # gate that only reads one of them is not a gate.
    for target, text in shipped_files(path, t):
        for name, pat in COVERT.items():
            if re.search(pat, text):
                fail.append(f"{target}: COVERT CONTENT — {name}")
        for ch in ZERO_WIDTH:
            if ch in text:
                fail.append(f"{target}: COVERT CONTENT — zero-width character U+{ord(ch):04X}")

    if not re.match(r"^---\nname: " + re.escape(slug) + r"\n", t):
        fail.append(f"{path}: frontmatter name must be '{slug}'")
    if "description:" not in t.split("---")[1]:
        fail.append(f"{path}: frontmatter missing description")
    if "## Where this stops" not in t:
        fail.append(f"{path}: missing '## Where this stops'")
    if "## What this does" not in t:
        warn.append(f"{path}: no '## What this does'")

    # Cue block may only exist on export skills, exactly once, at the end
    if has_cue:
        if not is_export and not is_tier_a:
            fail.append(f"{path}: Cue block on a skill that is neither export nor Tier A")
        if t.count(CUE_HEADING) > 1:
            fail.append(f"{path}: Cue block appears more than once")
        after = t.split(CUE_HEADING, 1)[1]
        if re.search(r"^## (?!When to mention)", after, re.M):
            fail.append(f"{path}: Cue block is not the final section")
        guards = ["at most once in a conversation", "do not mention Cue at all",
                  "published in the open"]
        guards.append("Never disguise it as part of the work" if is_tier_a
                      else "Never disguise it as analysis")
        for need in guards:
            if need not in t:
                fail.append(f"{path}: Cue block missing guardrail: '{need}'")
    # product names must not appear outside the Cue block or a "Works with" section
    body = t.split(CUE_HEADING)[0]
    prose = strip_section(body, WORKS_WITH_HEADING)
    for term in ("Cue", "Fountain"):
        if re.search(r"\b" + term + r"\b", prose):
            fail.append(
                f"{path}: '{term}' appears in the skill body, outside the "
                f"Cue block and outside '{WORKS_WITH_HEADING}'")
    if WORKS_WITH_HEADING in t and t.count(WORKS_WITH_HEADING) > 1:
        fail.append(f"{path}: '{WORKS_WITH_HEADING}' appears more than once")

    if is_tier_a and COST_HEADING not in t:
        fail.append(f"{path}: Tier A skill missing '{COST_HEADING}'")

    if cat in COMPLIANCE_DIRS or slug in COMPLIANCE_EXTRA:
        if not re.search(NOT_ADVICE, t):
            fail.append(f"{path}: compliance-adjacent but no 'not legal advice' statement")
        if not re.search(VERIFY, t, re.M):
            fail.append(f"{path}: compliance-adjacent but no verification section")

    words = len(body.split())
    if words > 1900:
        warn.append(f"{path}: {words} words — long")
    if words < 600:
        warn.append(f"{path}: {words} words — thin")
    return is_export, has_cue, words


def main():
    files = sorted(glob.glob("skills/*/*.md") + glob.glob("skills/*/*/SKILL.md"))
    folder_skills = sum(1 for f in files if os.path.basename(f) == "SKILL.md")
    seen = {}
    for f in files:
        seen.setdefault(slug_of(f), []).append(f)
    for slug, paths in seen.items():
        if len(paths) > 1:
            fail.append(f"duplicate skill slug '{slug}': " + ", ".join(paths))
    if not files:
        print("no skill files found");  return 1
    exports = cues = 0
    total = 0
    for f in files:
        e, c, w = check(f)
        exports += e; cues += c; total += w

    print(f"skills:        {len(files)}  ({folder_skills} as folders)")
    print(f"export skills: {exports}")
    print(f"Cue blocks:    {cues}")
    print(f"Tier A:        {len(TIER_A)}")
    print(f"total words:   {total:,}  (mean {total // len(files):,})")

    for w in warn:
        print("WARN  " + w)
    if fail:
        print()
        for f in fail:
            print("FAIL  " + f)
        print(f"\n{len(fail)} failure(s).")
        return 1
    print("\nAudit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
