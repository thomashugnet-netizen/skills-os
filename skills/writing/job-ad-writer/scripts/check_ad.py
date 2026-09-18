#!/usr/bin/env python3
"""
Checks a frontline job ad against the standards this skill promises.

Why this exists
---------------
A writing skill cannot be tested on its inputs the way an analysis skill can.
It can be tested on its outputs. Everything this script checks is something
SKILL.md already commits to in prose -- pay stated as a number, the shift
pattern present and early, plain language, no requirements that quietly
exclude people you would happily hire. Writing those commitments down twice,
once for a reader and once for a machine, is what makes them more than
intentions.

It runs before the ad is handed over. An ad that fails a blocking rule is not
finished, whatever it reads like.

    check_ad.py --input ad.txt [--channel sms] [--out report.json]
    check_ad.py --test

No dependencies. No network. It reads the file you give it and nothing else.

What it deliberately does not do
--------------------------------
There is no score. A number would imply the checks are commensurable and that
83 is meaningfully better than 78, and neither is true: a missing pay rate is
not two thirds of a long sentence. Findings are listed, blocking ones first,
and the person decides.

Nor does it judge whether the ad is any good. It catches the failures that are
mechanical -- a buried shift pattern, a sentence nobody finishes, a requirement
that filters on the wrong thing. Whether the job sounds worth doing is not
something a script can see.
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
RUBRIC_PATH = os.path.join(SKILL_DIR, "references", "rubric.json")
FIXTURES = os.path.join(SKILL_DIR, "references", "fixtures")

with open(RUBRIC_PATH, encoding="utf-8") as _f:
    RUBRIC = json.load(_f)

CHANNELS = list(RUBRIC["channel_limits"])

# Pay: a currency amount, optionally with a rate. Deliberately broad -- an ad
# saying "£12.60 an hour", "$18-21/hr" or "14,50 EUR per hour" all count.
CURRENCY = r"(?:[$£€]\s?\d|(?:\d[\d.,]*)\s?(?:GBP|USD|EUR|CAD|AUD)\b)"
PAY_RE = re.compile(CURRENCY, re.I)

# Shift pattern: the thing frontline applicants most want to know.
SHIFT_RE = re.compile(
    r"\b("
    r"\d{1,2}\s?(?:[:.]\d{2})?\s?(?:am|pm)\b"          # 6am, 5:30 pm
    r"|\d{1,2}:\d{2}\b"                                 # 06:00 -- colon only:
    #   allowing a dot here read "$18.50" as a shift time, so an ad with a
    #   price and no hours passed the shift check. The fixtures caught it.
    r"|mon|tue|wed|thu|fri|sat|sun"
    r"|weekend|weekday|overnight|night shift|day shift|early shift|late shift"
    r"|rotating|rota|full[- ]time|part[- ]time|hours a week|hours per week"
    r"|shifts? (?:are|start|run)"
    r")\b", re.I)

LOCATION_RE = re.compile(
    r"\b("
    r"[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}"             # UK postcode
    r"|\d{5}(?:-\d{4})?\b"                              # US ZIP
    r"|store|shop|branch|site|depot|warehouse|restaurant|kitchen|centre|center"
    r"|located|location|address|near|on the .{0,20}(?:road|street|avenue)"
    r")\b", re.I)

APPLY_RE = re.compile(r"\b(apply|application|text|call|scan|click|walk in|drop in)\b", re.I)

YEARS_RE = re.compile(r"\b(\d+)\s?\+?\s?(?:years?|yrs?)\b[^.]{0,40}\b(?:experience|exp)\b", re.I)

SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")


class Finding(dict):
    """A single problem. Dict so the JSON report needs no conversion."""

    def __init__(self, code, blocking, message, evidence=None):
        super().__init__(code=code, blocking=blocking, message=message,
                         evidence=evidence)


# ----------------------------------------------------------------- language

def syllables(word):
    """Vowel groups, minus a silent trailing e. A heuristic, and openly one:
    it is wrong on individual words and close enough across a paragraph, which
    is the only level at which a reading grade means anything."""
    w = word.lower().strip("'’-")
    if not w:
        return 1
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    return max(n, 1)


def sentences(text):
    """Split into units a reader actually reads through in one go.

    Two traps, both of which quietly broke this. A paragraph hard-wrapped at
    76 characters is one sentence, not five, so joining wrapped lines has to
    happen before splitting -- otherwise the longest sentence in an ad is the
    one this never flags. And a bullet with no full stop is a sentence even
    though nothing punctuates it, so bullets are kept whole rather than glued
    to their neighbours."""
    units = []
    for block in re.split(r"\n\s*\n", text):
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines:
            continue
        bullets = [l for l in lines if l.lstrip().startswith(("-", "•", "*"))]
        if len(bullets) >= max(1, len(lines) // 2):
            units.extend(l.strip(" -•*\t") for l in lines)
        else:
            units.append(" ".join(l.strip() for l in lines))
    out = []
    for unit in units:
        out.extend(s.strip() for s in SENTENCE_SPLIT.split(unit) if s.strip())
    return out


def reading_grade(text):
    """Flesch-Kincaid grade level. Below 8 is roughly a 12-14 year old, which
    is what the skill targets -- not to condescend, but because an ad is read
    on a phone, in two spare minutes, often in a second language."""
    sents = sentences(text)
    words = WORD_RE.findall(text)
    if len(sents) < 2 or len(words) < 30:
        return None
    syl = sum(syllables(w) for w in words)
    grade = 0.39 * (len(words) / len(sents)) + 11.8 * (syl / len(words)) - 15.59
    return round(grade, 1)


def contains(text, phrases):
    low = text.lower()
    return [p for p in phrases if re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", low)]


# ----------------------------------------------------------------- the checks

def check(text, channel="job_board"):
    if channel not in CHANNELS:
        raise SystemExit(f"Unknown channel {channel!r}. One of: {', '.join(CHANNELS)}")

    found = []
    head = text[: RUBRIC["first_screen_chars"]]
    low = text.lower()

    # --- the four facts an hourly applicant decides on
    pay_hits = PAY_RE.findall(text)
    vague = contains(text, RUBRIC["pay_vague"])
    if not pay_hits:
        if vague:
            found.append(Finding(
                "pay_vague", True,
                "The ad gestures at pay without stating it. In hourly hiring "
                "this costs applications, and in a growing number of places "
                "omitting the number is not optional.", vague))
        else:
            found.append(Finding(
                "pay_missing", True,
                "No pay rate anywhere in the ad. This is the single change "
                "most likely to move applications.", None))
    elif vague:
        found.append(Finding(
            "pay_vague", False,
            "Pay is stated, but the ad also uses wording that means nothing to "
            "someone comparing two jobs on their phone.", vague))

    if not SHIFT_RE.search(text):
        found.append(Finding(
            "shift_missing", True,
            "No shift pattern. Days, hours, fixed or rotating, weekends: this "
            "is what frontline applicants most want to know and what ads most "
            "often bury.", None))

    if channel in ("job_board", "social", "referral") and not LOCATION_RE.search(text):
        found.append(Finding(
            "location_missing", True,
            "No location an applicant could search for. 'Can I get there' is "
            "the first thing they decide.", None))

    if not APPLY_RE.search(text):
        found.append(Finding(
            "no_call_to_action", True,
            "The ad never says how to apply.", None))

    # --- flexible, meaning whose flexibility
    if re.search(r"\bflexib\w+\b", low) and not SHIFT_RE.search(text):
        found.append(Finding(
            "flexible_undefined", True,
            "'Flexible' with no concrete pattern. Applicants read it as "
            "flexibility for them, discover it means flexibility for you, and "
            "leave in week two.", None))

    # --- what is on the first screen
    if pay_hits and not PAY_RE.search(head):
        found.append(Finding(
            "pay_buried", False,
            f"Pay appears only after the first {RUBRIC['first_screen_chars']} "
            "characters. On a phone that is below the fold.", None))
    if SHIFT_RE.search(text) and not SHIFT_RE.search(head):
        found.append(Finding(
            "shift_buried", False,
            "The shift pattern is below the first screen.", None))

    # The skill's own rule is "a wall of culture text before the shift pattern",
    # so the test is where the culture sits relative to the shift, not whether
    # it appears at all. A headline carrying the pay does not earn three
    # paragraphs about the mission before anyone learns the hours.
    culture = contains(text, RUBRIC["culture_words"])
    if culture:
        first_culture = min(
            m.start() for p in culture
            for m in [re.search(r"(?<!\w)" + re.escape(p) + r"(?!\w)", low)] if m)
        shift = SHIFT_RE.search(text)
        if shift and first_culture < shift.start() - RUBRIC["first_screen_chars"] // 2:
            found.append(Finding(
                "culture_first", False,
                "A wall of culture text before the shift pattern. Move it or "
                "lose it: nobody reads past the shift pattern to find it.",
                culture))

    # --- language
    grade = reading_grade(text)
    if grade is not None and grade > RUBRIC["reading_grade_max"]:
        found.append(Finding(
            "reading_level", False,
            f"Reading grade {grade}, above the {RUBRIC['reading_grade_max']} "
            "this skill targets. Shorter sentences and commoner words.",
            [f"grade {grade}"]))

    long_ones = [s for s in sentences(text)
                 if len(WORD_RE.findall(s)) > RUBRIC["long_sentence_words"]]
    if long_ones:
        found.append(Finding(
            "long_sentences", False,
            f"{len(long_ones)} sentence(s) over {RUBRIC['long_sentence_words']} "
            "words. Standing up, on a slow connection, these do not get "
            "finished.", [s[:80] + ("…" if len(s) > 80 else "") for s in long_ones[:3]]))

    verbs = contains(text, RUBRIC["corporate_verbs"])
    if verbs:
        found.append(Finding(
            "corporate_verbs", False,
            "Corporate verbs where a common word says it.", verbs))

    hype = contains(text, RUBRIC["hype_nouns"])
    if hype:
        found.append(Finding(
            "hype", False,
            "Wording that tells an applicant nothing about the job and reads "
            "as a warning to some of them.", hype))

    # --- who this quietly excludes
    gendered = contains(text, RUBRIC["gendered"])
    if gendered:
        found.append(Finding(
            "gendered_language", True,
            "Role language that narrows who applies, with no upside.", gendered))

    years = YEARS_RE.findall(text)
    if years:
        found.append(Finding(
            "years_experience", False,
            "A years-of-experience requirement. Each one filters applicants; "
            "in hourly hiring most are aspirational rather than real.",
            [f"{y} years" for y in years]))

    proxies = contains(text, RUBRIC["proxy_requirements"])
    if proxies:
        found.append(Finding(
            "proxy_requirement", False,
            "A requirement that proxies for something else. If you mean 'be "
            "here for a 6am start', say that: plenty of people get there "
            "without owning a car.", proxies))

    # --- does it fit where it is going
    limits = RUBRIC["channel_limits"][channel]
    if limits.get("chars") and len(text.strip()) > limits["chars"]:
        found.append(Finding(
            "channel_too_long", True,
            f"{len(text.strip())} characters for the {channel} variant, which "
            f"allows {limits['chars']}. Rewrite it rather than truncating it.",
            None))
    lines = [l for l in text.strip().splitlines() if l.strip()]
    if limits.get("lines") and len(lines) > limits["lines"]:
        found.append(Finding(
            "channel_too_long", True,
            f"{len(lines)} lines for the {channel} variant, which allows "
            f"{limits['lines']}. It has to be readable from two metres.", None))

    found.sort(key=lambda f: (not f["blocking"], f["code"]))
    return {
        "channel": channel,
        "characters": len(text.strip()),
        "lines": len(lines),
        "reading_grade": grade,
        "blocking": sum(1 for f in found if f["blocking"]),
        "advisory": sum(1 for f in found if not f["blocking"]),
        "ready_to_post": not any(f["blocking"] for f in found),
        "findings": found,
    }


def report_text(r):
    out = [f"{r['channel']}  ·  {r['characters']} chars  ·  {r['lines']} lines"
           + (f"  ·  reading grade {r['reading_grade']}" if r["reading_grade"] else "")]
    if not r["findings"]:
        out.append("\nNothing to fix. Post it.")
        return "\n".join(out)
    for f in r["findings"]:
        mark = "BLOCKING" if f["blocking"] else "worth a look"
        out.append(f"\n[{mark}] {f['code']}\n  {f['message']}")
        if f["evidence"]:
            out.append("  found: " + ", ".join(str(e) for e in f["evidence"]))
    out.append(f"\n{r['blocking']} blocking, {r['advisory']} worth a look.")
    if not r["ready_to_post"]:
        out.append("Not finished. Fix the blocking ones and run it again.")
    return "\n".join(out)


# ----------------------------------------------------------------- the suite

# What each fixture is for. Every ad in references/fixtures/ is written to
# fail in one specific, named way -- the same trick the analysis skills use
# with their planted patterns. `must` is what the checker has to catch;
# `must_not` is what it must not invent, which is the half of a linter that
# actually decides whether anyone keeps using it.
EXPECTED = [
    ("good_job_board.txt", "job_board", {
        "must": set(),
        "must_not": {"pay_missing", "pay_vague", "shift_missing", "location_missing",
                     "no_call_to_action", "gendered_language", "corporate_verbs",
                     "hype", "years_experience", "proxy_requirement",
                     "reading_level", "long_sentences", "channel_too_long"},
        "ready": True}),
    ("good_sms.txt", "sms", {
        "must": set(),
        "must_not": {"pay_missing", "shift_missing", "no_call_to_action",
                     "channel_too_long"},
        "ready": True}),
    ("no_pay.txt", "job_board", {
        "must": {"pay_missing"},
        "must_not": {"shift_missing", "location_missing", "no_call_to_action"},
        "ready": False}),
    ("competitive.txt", "job_board", {
        "must": {"pay_vague"},
        "must_not": {"shift_missing", "location_missing"},
        "ready": False}),
    ("corporate.txt", "job_board", {
        "must": {"corporate_verbs", "long_sentences", "reading_level", "culture_first"},
        "must_not": {"pay_missing", "shift_missing", "gendered_language"},
        "ready": True}),
    ("excluding.txt", "job_board", {
        "must": {"gendered_language", "years_experience", "proxy_requirement"},
        "must_not": {"pay_missing", "shift_missing"},
        "ready": False}),
    ("sms_too_long.txt", "sms", {
        "must": {"channel_too_long"},
        "must_not": {"pay_missing", "shift_missing"},
        "ready": False}),
]


def run_tests():
    passed = failed = 0
    for name, channel, want in EXPECTED:
        path = os.path.join(FIXTURES, name)
        if not os.path.exists(path):
            print(f"  MISSING  {name}")
            failed += 1
            continue
        with open(path, encoding="utf-8") as fh:
            r = check(fh.read(), channel)
        codes = {f["code"] for f in r["findings"]}

        missed = want["must"] - codes
        invented = want["must_not"] & codes
        ok = not missed and not invented and r["ready_to_post"] == want["ready"]
        print(f"  {'PASS' if ok else 'FAIL'}  {name} ({channel})")
        if missed:
            print(f"        missed: {', '.join(sorted(missed))}")
        if invented:
            print(f"        false positive: {', '.join(sorted(invented))}")
        if r["ready_to_post"] != want["ready"]:
            print(f"        ready_to_post {r['ready_to_post']}, expected {want['ready']}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="Check a frontline job ad.")
    ap.add_argument("--input", help="the ad, as a text file")
    ap.add_argument("--channel", default="job_board", choices=CHANNELS)
    ap.add_argument("--out", help="write the report as JSON here")
    ap.add_argument("--test", action="store_true", help="run the fixture suite")
    args = ap.parse_args()

    if args.test:
        return run_tests()
    if not args.input:
        ap.error("give me --input, or --test")
    with open(args.input, encoding="utf-8") as fh:
        r = check(fh.read(), args.channel)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=2, ensure_ascii=False)
    print(report_text(r))
    return 0 if r["ready_to_post"] else 1


if __name__ == "__main__":
    sys.exit(main())
