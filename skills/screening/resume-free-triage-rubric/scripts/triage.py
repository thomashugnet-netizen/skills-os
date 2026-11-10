#!/usr/bin/env python3
"""
Resume-Free Triage Rubric: the engine.

    python3 scripts/triage.py --rubric rubric.json
    python3 scripts/triage.py --rubric rubric.json --applicants applicants.csv
                              [--groups groups.csv] [--as-of 2026-10-30]
                              [--radius 10] [--out scored.csv] [--md | --json]
    python3 scripts/triage.py --demo [--revised]
    python3 scripts/triage.py --test

Checks a triage rubric for hourly roles where most applicants have no
resume, and blocks it until it passes: availability scored as overlap with
the shifts you are short of, never as a gate; travel scored on the plan for
the earliest shift, never on distance; no gaps, tenure or resume; knockouts
only for a minimum age, a licence the law requires, or work authorization.

Then scores an application export against it: a band for every open
applicant sized to the calls your team can make, a route instead of a
rejection when availability fits another site, and the fields to confirm on
the call instead of a zero for a blank. With past hires and their 30-day
outcome, it checks whether each signal earns its points; with a voluntary
self-ID file, whether the rubric calls one group less often, and which signal
does it. Same files, same answer, every time.

Exit codes: 0 read, 3 input refused or rubric blocked, 4 the engine itself failed.
Python 3, standard library only.
"""

import argparse
import collections
import csv
import datetime as dt
import io
import json
import math
import os
import random
import re
import sys
import tempfile

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(SKILL, "references", "sample")
SAMPLE_APPS = os.path.join(SAMPLE_DIR, "marlow_applicants.csv")
SAMPLE_GROUPS = os.path.join(SAMPLE_DIR, "marlow_groups.csv")
SAMPLE_RUBRIC = os.path.join(SAMPLE_DIR, "marlow_rubric.json")
SAMPLE_REVISED = os.path.join(SAMPLE_DIR, "marlow_rubric_revised.json")
EXPECTED = os.path.join(SAMPLE_DIR, "marlow_expected.json")
SAMPLE_AS_OF = "2026-10-30"

MAX_ROWS = 300_000
MIN_ARM = 30
MIN_OUTCOMES = 100
Z90 = 1.644854
FOUR_FIFTHS = 0.8
WEAK_SHARE = 0.15          # rota experience + certifications, of all points
OVERLAP_MIN_SHARE = 0.25   # shift overlap, of all points
ROUTE_LOW = 0.25           # below this at their own site, look elsewhere
ROUTE_OK = 0.5             # route if another site fits at least this well
BLANK_LIMIT = 0.40         # a signal blank this often is guesswork
STALE_DAYS = 7
DEFAULT_RADIUS = 10.0

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PARTS = ["early", "late", "night"]
BLOCKS = [f"{d}_{p}" for d in DAYS for p in PARTS]
DAY_WORDS = {"mon": "mon", "monday": "mon", "tue": "tue", "tues": "tue", "tuesday": "tue",
             "wed": "wed", "weds": "wed", "wednesday": "wed", "thu": "thu", "thur": "thu",
             "thurs": "thu", "thursday": "thu", "fri": "fri", "friday": "fri", "sat": "sat",
             "saturday": "sat", "sun": "sun", "sunday": "sun"}
PART_WORDS = {"early": "early", "morning": "early", "mornings": "early", "am": "early",
              "day": "early", "days": "early", "late": "late", "afternoon": "late",
              "evening": "late", "evenings": "late", "pm": "late", "swing": "late",
              "night": "night", "nights": "night", "overnight": "night", "graveyard": "night"}
ANY_WORDS = {"any", "all", "anytime", "flexible", "open", "fully_flexible"}

SIGNALS = ["shift_overlap", "start_latency", "travel", "reliability",
           "rota_experience", "certifications"]
SIGNAL_LABEL = {
    "shift_overlap": "Shift overlap", "start_latency": "Start latency",
    "travel": "Travel plan for the earliest shift", "reliability": "Reliability, asked concretely",
    "rota_experience": "Has worked to a rota", "certifications": "Certifications that save training",
}
TRAVEL_LEVELS = ["route_with_time", "own_transport", "route_no_time", "no_plan"]
TRAVEL_ALIASES = {"car": "own_transport", "drives": "own_transport", "own_car": "own_transport",
                  "own_vehicle": "own_transport", "drive": "own_transport",
                  "route_and_time": "route_with_time", "plan_with_time": "route_with_time",
                  "route": "route_no_time", "plan_no_time": "route_no_time",
                  "vague": "route_no_time", "none": "no_plan", "no": "no_plan",
                  "unknown_plan": "no_plan"}
LATENCY_BANDS = [(7, 1.0), (14, 0.7), (28, 0.35), (10 ** 6, 0.0)]
OVERLAP_BINS = [(0.0, 0.25, "under 25%"), (0.25, 0.5, "25-49%"), (0.5, 0.75, "50-74%"),
                (0.75, 1.01, "75-100%")]
LATENCY_BINS = [(0, 7, "0-7 days"), (8, 14, "8-14 days"), (15, 28, "15-28 days"),
                (29, 10 ** 6, "29+ days")]

# Signals a resume-free rubric must never score, and why.
FORBIDDEN = [
    (r"distance|radius|commute_?km|miles|km$|postcode|post_code|zip|address|neighbou?rhood",
     "distance",
     "Straight-line distance does not tell you who can arrive for the first shift, and a radius "
     "excludes people without a car, which tracks income, age and disability. Score the travel plan."),
    (r"gap|continuity|unemploy|time_out_of_work",
     "gap",
     "A gap is not evidence about work. Asking about it at triage invites health, caring and "
     "pregnancy into the record. Score rota_experience if continuity matters."),
    (r"tenure|years|job_count|jobs_held|job_hop|employers|stability",
     "tenure",
     "Tenure and job counts reflect the sector more than the person: warehouse and hospitality "
     "churn is structural. Not scored."),
    (r"resume|cv|cover_letter|attachment",
     "resume",
     "The rubric exists because most applicants have no resume. Scoring one rejects them."),
    (r"school|education|degree|diploma|gpa|grade",
     "education",
     "Education is not required for the role and filters out first jobs and older applicants."),
    (r"(^|_)age$|dob|birth|graduat",
     "age",
     "Only a minimum age the law sets can be asked, as a knockout ('18 or older')."),
    (r"reappl|previous\w*_(appl|reject)|prior\w*_(appl|reject)|rejected|returning",
     "reapplicant",
     "A rejection for a rota that no longer exists is not evidence about the person. "
     "Re-applicants are scored like anyone else."),
    (r"criminal|arrest|convict|felon|background",
     "criminal",
     "Criminal history is not a triage signal; where a check applies it comes after the offer."),
]
PREREQ_OK = re.compile(r"\b(1[68]|21) or older\b|\bat least (1[68]|21)\b|\blicen[cs]e\b|\bcdl\b|"
                       r"\bauthori[sz]ed to work\b|\bwork authori[sz]ation\b|\bcertif\w+\b|"
                       r"\bfood handler\b", re.I)
RISKY = [("age", r"\b(how old|your age|date of birth|birth ?(day|year)|what year did you graduate)\b"),
         ("citizenship", r"\b(are you a (u\.?s\.? )?citizen|citizenship|green card|where are you from|nationality)\b"),
         ("family", r"\b(children|kids|child ?care|babysitter|daycare|pregnan\w*|married|husband|wife)\b"),
         ("health", r"\b(health (condition|problem)|medical condition|disabilit\w*|medications?|injur\w*)\b"),
         ("religion", r"\b(church|religio\w*|pray\w*|sabbath)\b"),
         ("arrest", r"\b(arrested|criminal (record|history)|convicted|felon\w*)\b"),
         ("pay history", r"\b(current|previous|last) (salary|pay|wage|rate)\b|\bhow much (do|did) you (make|earn)\b"),
         ("gaps", r"\b(gaps? in (your )?(employment|work|cv|resume)|explain (the|any|your) gap|"
                  r"why did you leave|why were you out of work)\b")]
VAGUE_RELIABILITY = re.compile(r"\b(are you (reliable|dependable|punctual|hard[- ]?working|a team player)|"
                               r"do you have good attendance|rate your (reliability|punctuality)|"
                               r"would you describe yourself)\b", re.I)
DISTANCE_Q = re.compile(r"\b(how far|live within|within \d+ ?(km|miles?)|zip ?code|post ?code|"
                        r"what is your address|where do you live|can you get (here|to))\b", re.I)
HOW_TRAVEL = re.compile(r"\bhow (would|will|do) you get\b", re.I)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w-])(\+?\d[\d\s().-]{8,}\d)(?![\w-])")
NOMINATIVE = re.compile(r"(^|_)(first|last|full|given|family)?_?name($|_)|e-?mail|phone|mobile|address|"
                        r"street|postcode|ssn|social_security|dob|birth|notes?$|comment|resume_text", re.I)
NAME_LIKE = re.compile(r"^[A-Z][a-z]+(?: [A-Z][a-z'-]+)+$")


class Refused(Exception):
    """The input cannot be read honestly. Exit 3 with the reason."""


# ================================================================ helpers ====

def norm_key(s):
    return re.sub(r"[^a-z0-9]+", "_", str(s).strip().lower()).strip("_")


def yes_no(v):
    s = str(v or "").strip().lower()
    if s in ("yes", "y", "true", "1", "x", "checked", "t", "hired", "started", "active", "retained",
             "stayed", "employed"):
        return "yes"
    if s in ("no", "n", "false", "0", "f", "unchecked", "not hired", "rejected", "declined", "terminated",
             "quit", "left", "resigned", "no show", "no_show", "inactive"):
        return "no"
    return ""


def parse_date(v):
    s = str(v or "").strip()
    if not s:
        return None
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    try:
        if m:
            d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        else:
            m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
            if not m:
                return "bad"
            y = int(m.group(3))
            y = y + 2000 if y < 100 else y
            d = dt.date(y, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return "bad"
    if not (2000 <= d.year <= 2100):
        return "bad"
    return d


def wilson(k, n, z=Z90):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}%"


def pts(x):
    return f"{x:+.1f} pts"


def mh_rd(strata):
    """Stratified risk difference (exposed minus unexposed), 90% CI.
    strata: list of (k1, n1, k0, n0)."""
    num = den = var = 0.0
    n1t = n0t = 0
    for k1, n1, k0, n0 in strata:
        n1t += n1
        n0t += n0
        if n1 == 0 or n0 == 0:
            continue
        w = n1 * n0 / (n1 + n0)
        p1, p0 = k1 / n1, k0 / n0
        num += w * (p1 - p0)
        den += w
        # Small strata get a floor on the variance so a 0/3 cell is not "certain".
        v1 = max(p1 * (1 - p1), 0.25 / n1) / n1
        v0 = max(p0 * (1 - p0), 0.25 / n0) / n0
        var += w * w * (v1 + v0)
    if den == 0:
        return None
    rd = num / den
    se = math.sqrt(var) / den
    return {"rd": rd, "lo": rd - Z90 * se, "hi": rd + Z90 * se, "n1": n1t, "n0": n0t}


def auc(pos, neg):
    """Mann-Whitney AUC with a Hanley-McNeil 90% interval."""
    n1, n0 = len(pos), len(neg)
    if n1 == 0 or n0 == 0:
        return None
    allv = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    ranks = {}
    i = 0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        ranks[allv[i][0]] = (i + j + 1) / 2
        i = j
    r1 = sum(ranks[v] for v in pos)
    a = (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)
    q1, q2 = a / (2 - a), 2 * a * a / (1 + a)
    se = math.sqrt(max(0.0, (a * (1 - a) + (n1 - 1) * (q1 - a * a) + (n0 - 1) * (q2 - a * a)) / (n1 * n0)))
    return {"auc": a, "lo": a - Z90 * se, "hi": a + Z90 * se, "n_stayed": n1, "n_left": n0}


# ========================================================== rubric check ====

def load_rubric(path):
    try:
        with open(path, encoding="utf-8") as f:
            r = json.load(f)
    except UnicodeDecodeError:
        raise Refused("rubric: not UTF-8 text. Save it as UTF-8 JSON.")
    except json.JSONDecodeError as e:
        raise Refused(f"rubric: not valid JSON ({e.msg}, line {e.lineno}).")
    except OSError as e:
        raise Refused(f"rubric: cannot open {path} ({e.strerror}).")
    if not isinstance(r, dict):
        raise Refused("rubric: the file must hold one JSON object.")
    return r


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _forbidden(name):
    k = norm_key(name)
    for pat, code, why in FORBIDDEN:
        if re.search(pat, k):
            return code, why
    return None


def questions_of(r):
    out = []
    for name, spec in (r.get("signals") or {}).items():
        if isinstance(spec, dict) and isinstance(spec.get("question"), str):
            out.append((f"signal {name}", spec["question"]))
    for k in r.get("knockouts") or []:
        if isinstance(k, dict) and isinstance(k.get("question"), str):
            out.append((f"knockout {k.get('field')}", k["question"]))
    for q in r.get("form_questions") or []:
        if isinstance(q, str):
            out.append(("form question", q))
        elif isinstance(q, dict) and isinstance(q.get("question"), str):
            out.append(("form question", q["question"]))
    return out


def check_rubric(r):
    """Returns {"status", "blocks": [(code, text)], "advice": [(code, text)], "points": {...}}.
    Raises Refused only when the file is not a rubric at all."""
    blocks, advice = [], []

    def block(code, text):
        blocks.append((code, text))

    def adv(code, text):
        advice.append((code, text))

    # --- shape
    sites = r.get("sites")
    if not isinstance(sites, dict) or not sites:
        raise Refused('rubric: "sites" is missing. Give each site its shift gaps: '
                      '{"SITE-1": {"gaps": [{"block": "sat_night", "hours": 8, "shifts": 4}]}}.')
    signals = r.get("signals")
    if not isinstance(signals, dict) or not signals:
        raise Refused('rubric: "signals" is missing. Give each scored signal its points.')

    # --- capacity
    cap = r.get("calls_per_week")
    if not _num(cap) or cap < 1:
        block("no_capacity", "No calls_per_week. Every threshold is set by how many calls your team can make; "
                             "without it the rubric ranks but does not triage.")

    # --- sites and gaps
    for s, spec in sites.items():
        gaps = spec.get("gaps") if isinstance(spec, dict) else None
        if not isinstance(gaps, list) or not gaps:
            block("no_gaps", f"Site {s}: no shift gaps. Availability is scored against the shifts you are short of, "
                             "not against 'any hours'.")
            continue
        for g in gaps:
            if not isinstance(g, dict) or norm_key(g.get("block", "")) not in BLOCKS:
                block("bad_gap", f"Site {s}: gap {g!r} does not name a block such as 'sat_night' "
                                 f"(days mon-sun, parts early, late, night).")
            elif not _num(g.get("hours")) or g["hours"] <= 0 or not _num(g.get("shifts", 1)) or g.get("shifts", 1) < 1:
                block("bad_gap", f"Site {s}: gap {g.get('block')} needs positive hours and shifts.")
        for key in ("min_overlap", "required_blocks", "availability_required"):
            if isinstance(spec, dict) and key in spec:
                block("availability_gate", f"Site {s}: {key} turns availability into a filter. Score overlap and "
                                           "route partial availability to another site or the next rota.")
    for key in ("min_overlap", "required_blocks", "availability_required", "radius_km", "max_distance_km"):
        if key in r:
            code = "availability_gate" if "distance" not in key and "radius" not in key else "distance"
            block(code, f"Top-level {key}: "
                        + ("availability is scored as overlap, never as a gate." if code == "availability_gate"
                           else FORBIDDEN[0][2]))

    # --- signals
    total = 0.0
    points = {}
    for name, spec in signals.items():
        f = _forbidden(name) if norm_key(name) not in SIGNALS else None
        if f:
            block(f[0], f"Signal '{name}': {f[1]}")
            continue
        if norm_key(name) not in SIGNALS:
            block("unknown_signal", f"Signal '{name}' is not one of the six this rubric scores: "
                                    + ", ".join(SIGNALS) + ".")
            continue
        if not isinstance(spec, dict) or not _num(spec.get("points")) or spec["points"] < 0:
            block("bad_points", f"Signal '{name}': points must be a number, 0 or more.")
            continue
        if spec.get("knockout") or spec.get("required") or spec.get("min") is not None:
            block("availability_gate" if name == "shift_overlap" else "signal_gate",
                  f"Signal '{name}' is set as a gate. Signals score points; only a minimum age, a licence the law "
                  "requires, or work authorization can knock someone out.")
        points[name] = float(spec["points"])
        total += float(spec["points"])
    if total <= 0 and not blocks:
        block("bad_points", "No signal carries any points.")
    if points.get("shift_overlap", 0) <= 0:
        block("no_overlap", "Shift overlap carries no points. It is the strongest signal without a work history: "
                            "a mismatch here produces the hire who leaves in week three.")

    tr = signals.get("travel")
    if isinstance(tr, dict):
        levels = tr.get("levels")
        if not isinstance(levels, dict) or any(norm_key(k) not in TRAVEL_LEVELS for k in levels) \
                or not all(_num(v) and 0 <= v <= 1 for v in levels.values()):
            block("travel_levels", "Travel levels must map route_with_time, own_transport, route_no_time and no_plan "
                                   "to a share of the points between 0 and 1.")
        else:
            lv = {norm_key(k): float(v) for k, v in levels.items()}
            missing = [l for l in TRAVEL_LEVELS if l not in lv]
            if missing:
                block("travel_levels", "Travel levels missing: " + ", ".join(missing) + ".")
            elif lv["route_with_time"] < lv["route_no_time"] or lv["route_no_time"] < lv["no_plan"]:
                block("travel_order", "A stated route with a time must score at least a vague route, and a vague "
                                      "route at least no plan.")
            elif lv["own_transport"] - lv["route_with_time"] >= 0.2:
                adv("car_premium", f"Owning a car scores {lv['own_transport']:.0%} of the travel points and a route "
                                   f"with a time {lv['route_with_time']:.0%}. Both are plans for the earliest shift. "
                                   "A car premium calls fewer people without a car, who are disproportionately "
                                   "younger, lower-paid or disabled. Check it against your own outcomes.")
        q = tr.get("question", "")
        if isinstance(q, str) and DISTANCE_Q.search(q):
            block("distance", f"Travel question '{q}' asks about distance or ability, not the plan. "
                              "Ask 'How would you get here for a <earliest shift> start?'")
        elif isinstance(q, str) and q and not HOW_TRAVEL.search(q):
            adv("travel_question", f"Travel question '{q}': ask 'How would you get here for a <time> start?'. "
                                   "A route with a time in it is a different answer from 'yes, fine'.")
    lt = signals.get("start_latency")
    if isinstance(lt, dict) and lt.get("bands_days") is not None:
        b = lt["bands_days"]
        if not (isinstance(b, list) and len(b) == 3 and all(_num(x) and x > 0 for x in b) and b == sorted(b)):
            block("bad_points", "start_latency bands_days must be three increasing day counts, e.g. [7, 14, 28].")
    ce = signals.get("certifications")
    if isinstance(ce, dict) and not (isinstance(ce.get("bonus"), list) and ce["bonus"]):
        block("cert_list", "Certifications scored with no bonus list. Name the certificates that save training time.")

    rel = signals.get("reliability")
    if isinstance(rel, dict):
        q = rel.get("question", "")
        if not isinstance(q, str) or not q.strip():
            adv("reliability_question", "Reliability has no question. Ask something concrete, such as "
                                        "'Have you worked shifts that start before 7am?'")
        elif VAGUE_RELIABILITY.search(q):
            block("vague_reliability", f"Reliability question '{q}' asks for a self-rating. Everybody says yes. "
                                       "Ask about something they did: 'Have you worked shifts that start before 7am?'")

    # --- weights
    if total > 0:
        weak = points.get("rota_experience", 0) + points.get("certifications", 0)
        if weak / total > WEAK_SHARE:
            adv("weak_signal_heavy", f"Rota experience and certifications carry {weak / total:.0%} of the points. "
                                     "They are weak evidence without a work history: having done the job makes "
                                     "someone easier to train, and that is all. Keep them under "
                                     f"{WEAK_SHARE:.0%}.")
        if 0 < points.get("shift_overlap", 0) / total < OVERLAP_MIN_SHARE:
            adv("overlap_light", f"Shift overlap carries {points['shift_overlap'] / total:.0%} of the points. "
                                 f"It is the strongest signal; give it at least {OVERLAP_MIN_SHARE:.0%}.")

    # --- knockouts
    kos = r.get("knockouts") or []
    if not isinstance(kos, list):
        block("bad_knockout", '"knockouts" must be a list.')
        kos = []
    for k in kos:
        if not isinstance(k, dict) or not isinstance(k.get("field"), str) or not k.get("field").strip():
            block("bad_knockout", f"Knockout {k!r} needs a field name and a rule.")
            continue
        field, rule = k["field"], str(k.get("rule", ""))
        f = _forbidden(field)
        nk = norm_key(field)
        if nk in ("availability", "shift_overlap") or "avail" in nk or "shift" in nk:
            block("availability_gate", f"Knockout '{field}': availability is scored as overlap, never as a gate.")
        elif f and f[0] != "age":
            block(f[0], f"Knockout '{field}': {f[1]}")
        elif f and re.search(r"dob|birth", nk):
            block("risky_question", f"Knockout '{field}' collects a date of birth. Ask only whether they meet the "
                                    "minimum age: 'Are you 18 or older?'")
        elif nk in SIGNALS or nk in ("travel", "experience", "rota_experience"):
            block("signal_gate", f"Knockout '{field}' turns a scored signal into a filter.")
        elif not PREREQ_OK.search(rule):
            block("bad_knockout", f"Knockout '{field}' ({rule or 'no rule'}): a knockout is only a minimum age "
                                  "('18 or older'), a licence or certificate the law requires, or work authorization. "
                                  "Anything else is points.")
        elif re.search(r"licen|cert|cdl|food handler", rule, re.I) and not k.get("legal_basis"):
            block("cert_knockout", f"Knockout '{field}' ({rule}): a certificate is a knockout only where the law "
                                   "requires it for every shift. Name the requirement in legal_basis, or score it "
                                   "as a bonus.")
    if len(kos) > 3:
        block("too_many_knockouts", f"{len(kos)} knockouts. The list should be short enough to read aloud: three at "
                                    "most, the same gates the phone screen uses.")

    # --- every question in the rubric
    for where, q in questions_of(r):
        for topic, pat in RISKY:
            if re.search(pat, q, re.I):
                block("risky_question", f"{where}: '{q}' touches {topic}. Not asked at triage.")
    nq = len(questions_of(r))
    if nq > 8:
        adv("long_form", f"{nq} questions. Each one costs completed applications on a phone; "
                         "five or six carry nearly all the signal.")

    # --- bands fixed by hand
    bands = r.get("bands")
    if bands is not None:
        if not (isinstance(bands, dict) and _num(bands.get("call_today")) and _num(bands.get("call_if_dry"))
                and bands["call_today"] >= bands["call_if_dry"]):
            block("bad_bands", "bands needs call_today and call_if_dry scores, call_today the higher.")

    # --- first jobs must be able to reach the call
    if total > 0 and not any(c in ("bad_points", "unknown_signal") for c, _ in blocks):
        first = total - points.get("rota_experience", 0) - points.get("certifications", 0)
        if isinstance(bands, dict) and _num(bands.get("call_today")) and first < bands["call_today"]:
            block("first_job_shut_out", f"A first-job applicant with every other answer perfect scores {first:.0f}, "
                                        f"under the call-today line of {bands['call_today']:.0f}. No work history "
                                        "is one absent signal, not a low score.")

    status = "blocked" if blocks else ("advice" if advice else "ready")
    return {"status": status, "blocks": blocks, "advice": advice, "points": points, "total": total}


# ======================================================== reading files ====

ALIASES = {
    "applicant_id": ["candidate_id", "application_id", "applicantid", "id"],
    "applied_at": ["applied", "applied_on", "application_date", "submitted_at", "created_at", "apply_date"],
    "site": ["location_id", "location", "site_id", "store_id", "store", "facility"],
    "availability": ["shifts_available", "available_shifts", "availability_blocks"],
    "available_from": ["start_date", "earliest_start", "can_start", "available_start", "start_from"],
    "travel": ["travel_plan", "commute_plan", "getting_here", "transport"],
    "distance_km": ["distance", "commute_km", "distance_to_site_km"],
    "reliability": ["early_shifts", "worked_early_shifts", "reliability_answer"],
    "rota_experience": ["shift_experience", "worked_rota", "worked_shifts", "worked_shifts_before"],
    "certifications": ["certs", "licences", "licenses", "certificates"],
    "reapplicant": ["re_applicant", "returning", "returning_applicant"],
    "called": ["contacted", "screened", "phone_screened"],
    "hired": ["hire", "was_hired", "offer_accepted"],
    "hired_at": ["hire_date", "offer_accepted_at"],
    "started": ["first_shift_worked", "did_start"],
    "day30": ["retained_30", "day_30", "stayed_30", "retained_day30", "day_30_retained", "active_day_30"],
}


def map_columns(header, extra):
    keys = [norm_key(h) for h in header]
    out = {}
    for canon, alts in ALIASES.items():
        for cand in [canon] + alts:
            if cand in keys:
                out[canon] = header[keys.index(cand)]
                break
    for f in extra:
        nk = norm_key(f)
        if nk in keys:
            out[f] = header[keys.index(nk)]
    return out


def read_csv(path, what):
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise Refused(f"{what}: not UTF-8 text. Re-export as UTF-8 CSV.")
    except OSError as e:
        raise Refused(f"{what}: cannot open {path} ({e.strerror}).")
    if not text.strip():
        raise Refused(f"{what}: the file is empty.")
    try:
        sample = text[:4096]
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise Refused(f"{what}: a header and at least one row are needed.")
    if len(rows) - 1 > MAX_ROWS:
        raise Refused(f"{what}: {len(rows) - 1:,} rows, over the {MAX_ROWS:,} this reads at once. Split by site.")
    header = [h.strip() for h in rows[0]]
    for h in header:
        if NOMINATIVE.search(norm_key(h)):
            raise Refused(f"{what}: column '{h}' looks like a name, contact detail or free notes. Re-export with "
                          "opaque applicant ids only.")
    body = []
    for r in rows[1:]:
        r = (r + [""] * len(header))[:len(header)]
        for c in r:
            if EMAIL.search(c) or (PHONE.search(c) and not re.match(r"^\d{4}-\d{2}-\d{2}", c.strip())):
                raise Refused(f"{what}: a value looks like an email or phone number. Re-export with opaque ids only.")
        body.append(dict(zip(header, r)))
    return header, body


def parse_availability(s):
    """-> (set of blocks, generous flag, unknown token count, token count)"""
    s = str(s or "").strip()
    if not s:
        return None, False, 0, 0
    toks = [t for t in re.split(r"[;,|/]+", s.lower()) if t.strip()]
    got, unknown, generous = set(), 0, False
    for t in toks:
        t = t.strip()
        k = norm_key(t)
        if k in ANY_WORDS:
            got |= set(BLOCKS)
            generous = True
            continue
        if k in BLOCKS:
            got.add(k)
            continue
        parts = k.split("_")
        days = [DAY_WORDS[p] for p in parts if p in DAY_WORDS]
        prt = [PART_WORDS[p] for p in parts if p in PART_WORDS]
        if "weekends" in parts or "weekend" in parts:
            days += ["sat", "sun"]
        if "weekdays" in parts or "weekday" in parts:
            days += ["mon", "tue", "wed", "thu", "fri"]
        if days and prt:
            got |= {f"{d}_{p}" for d in days for p in prt}
        elif days:
            got |= {f"{d}_{p}" for d in days for p in PARTS}
        elif prt:
            got |= {f"{d}_{p}" for d in DAYS for p in prt}
        else:
            unknown += 1
    return got, generous, unknown, len(toks)


def read_applicants(path, rubric):
    ko_fields = [k["field"] for k in rubric.get("knockouts") or [] if isinstance(k, dict) and k.get("field")]
    header, body = read_csv(path, "applicants")
    cols = map_columns(header, ko_fields)
    for need in ("applicant_id", "applied_at", "site"):
        if need not in cols:
            raise Refused(f"applicants: no {need} column. Needed: applicant_id, applied_at, site, plus the "
                          "answers the rubric scores.")
    keys = [norm_key(h) for h in header]
    if "stage" in keys or "funnel_stage" in keys or "screen_completed_at" in keys:
        if "availability" not in cols and "travel" not in cols:
            raise Refused("applicants: this looks like a pipeline export (one row per stage). It needs the answers "
                          "applicants gave. For where people leave the funnel, use funnel-drop-off-analyst.")
    sites = rubric["sites"]
    apps, seen = [], set()
    bad_dates = unknown_tok = tok = 0
    travel_unknown = travel_given = 0
    for row in body:
        g = lambda c: (row.get(cols[c], "") if c in cols else "").strip()
        aid = g("applicant_id")
        if not aid:
            continue
        if NAME_LIKE.match(aid):
            raise Refused("applicants: the id column holds what look like people's names. Use opaque ids.")
        applied = parse_date(g("applied_at"))
        if applied in (None, "bad"):
            bad_dates += 1
            continue
        key = (aid, applied)
        if key in seen:
            continue
        seen.add(key)
        av, generous, unk, nt = parse_availability(g("availability"))
        unknown_tok += unk
        tok += nt
        tv_raw = norm_key(g("travel"))
        tv = TRAVEL_ALIASES.get(tv_raw, tv_raw)
        if tv_raw:
            travel_given += 1
            if tv not in TRAVEL_LEVELS:
                travel_unknown += 1
                tv = ""
        af = parse_date(g("available_from"))
        dist = None
        if "distance_km" in cols and g("distance_km"):
            try:
                dist = float(g("distance_km").replace(",", "."))
                if not math.isfinite(dist) or dist < 0:
                    dist = None
            except ValueError:
                dist = None
        hired = yes_no(g("hired"))
        started = yes_no(g("started"))
        d30 = yes_no(g("day30"))
        if hired == "yes" and started == "no" and not d30:
            d30 = "no"
        apps.append({
            "id": aid, "applied": applied, "site": g("site"), "avail": av, "generous": generous,
            "available_from": af if af != "bad" else None,
            "travel": tv, "distance": dist, "reliability": yes_no(g("reliability")),
            "rota_experience": yes_no(g("rota_experience")),
            "certs": {norm_key(c) for c in re.split(r"[;,|]+", g("certifications")) if c.strip()},
            "reapplicant": yes_no(g("reapplicant")),
            "ko": {f: yes_no(row.get(cols[f], "")) if f in cols else "" for f in ko_fields},
            "called": yes_no(g("called")), "hired": hired, "hired_at": parse_date(g("hired_at")),
            "started": started, "day30": d30 if hired == "yes" else "",
        })
    if not apps:
        raise Refused("applicants: no row has both an applicant id and a readable applied_at date.")
    if bad_dates > 0.2 * (len(apps) + bad_dates):
        raise Refused(f"applicants: {bad_dates} rows have no readable applied_at (use YYYY-MM-DD).")
    if tok and unknown_tok / tok > 0.2:
        raise Refused("applicants: availability is not in blocks the engine can read. Use day and part of day, "
                      "e.g. 'sat_night; sun_early'. Free text needs coding first.")
    if travel_given and travel_unknown / travel_given > 0.2:
        raise Refused("applicants: travel answers are free text or unknown codes. Code each one as route_with_time, "
                      "own_transport, route_no_time or no_plan before scoring; the skill does this from the answers.")
    unknown_sites = {a["site"] for a in apps} - set(sites)
    share = sum(a["site"] in unknown_sites for a in apps) / len(apps)
    if share > 0.5:
        raise Refused("applicants: most sites in the file are not in the rubric ("
                      + ", ".join(sorted(unknown_sites)[:5]) + "). Site names must match.")
    for k in ko_fields:
        if k not in cols:
            raise Refused(f"applicants: knockout field '{k}' is not a column. Every knockout must be collected.")
    return apps, cols, sorted(unknown_sites)


def read_groups(path, ids):
    header, body = read_csv(path, "groups")
    keys = [norm_key(h) for h in header]
    if "applicant_id" not in keys or "group" not in keys:
        raise Refused("groups: needs exactly applicant_id and group (voluntary self-ID, opaque labels).")
    if len(header) > 2:
        raise Refused("groups: only applicant_id and group. Keep self-ID apart from everything else.")
    ia, ig = header[keys.index("applicant_id")], header[keys.index("group")]
    out = {}
    for r in body:
        a, g = r[ia].strip(), r[ig].strip()
        if a and g:
            out[a] = g
    if len(set(out.values())) > 12:
        raise Refused("groups: more than 12 distinct groups. Use the self-ID categories as given.")
    matched = sum(1 for a in out if a in ids)
    if matched < 0.5 * len(out):
        raise Refused("groups: most ids do not match the applicants file.")
    return out


# ================================================================ scoring ====

def site_overlap(blocks, site, rubric):
    spec = rubric["sites"].get(site)
    if not spec or blocks is None:
        return None
    gaps = spec.get("gaps") or []
    total = sum(g["hours"] * g.get("shifts", 1) for g in gaps)
    if total <= 0:
        return None
    got = sum(g["hours"] * g.get("shifts", 1) for g in gaps if norm_key(g["block"]) in blocks)
    return got / total


def fractions(a, rubric, site=None):
    """Share of each signal's points earned, None when the answer is blank."""
    sig = rubric["signals"]
    out = {}
    if "shift_overlap" in sig:
        out["shift_overlap"] = site_overlap(a["avail"], site or a["site"], rubric)
    if "start_latency" in sig:
        if a["available_from"] is None:
            out["start_latency"] = None
        else:
            days = max(0, (a["available_from"] - a["applied"]).days)
            b = sig["start_latency"].get("bands_days") or [7, 14, 28]
            out["start_latency"] = 1.0 if days <= b[0] else 0.7 if days <= b[1] else 0.35 if days <= b[2] else 0.0
    if "travel" in sig:
        lv = {norm_key(k): float(v) for k, v in (sig["travel"].get("levels") or {}).items()}
        out["travel"] = lv.get(a["travel"]) if a["travel"] else None
    if "reliability" in sig:
        out["reliability"] = {"yes": 1.0, "no": 0.0}.get(a["reliability"])
    if "rota_experience" in sig:
        out["rota_experience"] = {"yes": 1.0, "no": 0.0}.get(a["rota_experience"])
    if "certifications" in sig:
        bonus = {norm_key(c) for c in sig["certifications"].get("bonus") or []}
        out["certifications"] = 1.0 if a["certs"] & bonus else 0.0
    return out


def score(a, rubric, site=None, blank_as=0.5):
    fr = fractions(a, rubric, site)
    total, confirm, parts = 0.0, [], {}
    for name, f in fr.items():
        p = float(rubric["signals"][name]["points"])
        if f is None:
            confirm.append(name)
            f = blank_as
        parts[name] = p * f
        total += p * f
    if a["generous"] and "shift_overlap" not in confirm:
        confirm.append("shift_overlap")
    return round(total, 2), confirm, parts, fr


def knocked_out(a, rubric):
    for k in rubric.get("knockouts") or []:
        if a["ko"].get(k["field"]) == "no":
            return k.get("rule") or k["field"]
    return None


def as_of_date(apps, given):
    if given:
        d = parse_date(given)
        if d in (None, "bad"):
            raise Refused(f"--as-of '{given}' is not a date (YYYY-MM-DD).")
        return d
    return max(a["applied"] for a in apps)


def triage(apps, rubric, as_of):
    qd = int(rubric.get("queue_days") or 14)
    cap = int(rubric["calls_per_week"])
    for a in apps:
        a["ko_reason"] = knocked_out(a, rubric)
        a["score"], a["confirm"], a["parts"], a["fr"] = score(a, rubric)
        a["route"] = None
        a["hold"] = None
    window = [a for a in apps if as_of - dt.timedelta(days=qd) <= a["applied"] <= as_of]
    queue = [a for a in window if a["hired"] != "yes" and a["called"] != "yes"]
    if not queue:
        queue = window
    # Routing: availability that fits another site is a route, not a rejection.
    sites = list(rubric["sites"])
    for a in queue:
        if a["ko_reason"] or a["avail"] is None:
            continue
        own = a["fr"].get("shift_overlap")
        if own is not None and own < ROUTE_LOW:
            best = max(((site_overlap(a["avail"], s, rubric) or 0, s) for s in sites if s != a["site"]),
                       default=(0, None))
            if best[0] >= ROUTE_OK:
                a["route"] = best[1]
                a["score"], a["confirm"], a["parts"], a["fr"] = score(a, rubric, site=best[1])
            elif own == 0 and best[0] < ROUTE_LOW:
                a["hold"] = "no overlap with any shift you are short of; keep for the next rota change"
    live = [a for a in queue if not a["ko_reason"] and not a["hold"]]
    live.sort(key=lambda a: (-a["score"], a["applied"], a["id"]))
    bands = rubric.get("bands")
    if isinstance(bands, dict):
        t_a, t_b, fixed = float(bands["call_today"]), float(bands["call_if_dry"]), True
    else:
        fixed = False
        if len(live) <= cap:
            t_a = min((a["score"] for a in live), default=0.0)
            t_b = t_a
        else:
            t_a = live[cap - 1]["score"]
            t_b = live[min(len(live), 2 * cap) - 1]["score"]
    for a in queue:
        if a["ko_reason"]:
            a["band"] = "knockout"
        elif a["hold"]:
            a["band"] = "hold"
        elif a["score"] >= t_a:
            a["band"] = "call_today"
        elif a["score"] >= t_b:
            a["band"] = "call_if_dry"
        else:
            a["band"] = "hold"
            weakest = min(a["parts"], key=lambda n: a["parts"][n] / max(1e-9, rubric["signals"][n]["points"])
                          if rubric["signals"][n]["points"] > 0 else 9)
            a["hold"] = f"below the call line; weakest: {SIGNAL_LABEL.get(weakest, weakest).lower()}"
    ranked = [a for a in live]
    for i, a in enumerate(ranked):
        a["rank"] = i + 1
    count = collections.Counter(a["band"] for a in queue)
    # What moving the line by five points does.
    move = {d: sum(1 for a in live if a["score"] >= t_a + d) for d in (-5, 5)}
    # Blanks scored as zero instead of a question for the call.
    drop = 0
    for a in live:
        if a["band"] == "call_today" and a["confirm"]:
            z, _, _, _ = score(a, rubric, site=a["route"], blank_as=0.0)
            if z < t_a:
                drop += 1
    total = sum(float(s["points"]) for s in rubric["signals"].values())
    first = total - float(rubric["signals"].get("rota_experience", {}).get("points", 0)) \
        - float(rubric["signals"].get("certifications", {}).get("points", 0))
    weeks = 4
    recent = [a for a in apps if as_of - dt.timedelta(days=7 * weeks) < a["applied"] <= as_of]
    per_week = len(recent) / weeks
    return {
        "as_of": as_of.isoformat(), "queue_days": qd, "capacity": cap, "queue": len(queue),
        "per_week": per_week, "fixed": fixed, "t_call_today": t_a, "t_call_if_dry": t_b,
        "bands": {k: count.get(k, 0) for k in ("call_today", "call_if_dry", "hold", "knockout")},
        "routed": sum(1 for a in queue if a["route"]),
        "held_for_rota": sum(1 for a in queue if a["hold"] and a["hold"].startswith("no overlap")),
        "line_minus_5": move[-5], "line_plus_5": move[5],
        "blank_zero_drop": drop,
        "confirm_in_call_today": sum(1 for a in queue if a["band"] == "call_today" and a["confirm"]),
        "stale_in_call_today": sum(1 for a in queue if a["band"] == "call_today"
                                   and (as_of - a["applied"]).days > STALE_DAYS),
        "first_job_max": first, "first_job_shut_out": first < t_a,
        "reapplicants_call_today": sum(1 for a in queue if a["band"] == "call_today" and a["reapplicant"] == "yes"),
        "can_call_everyone": len(live) <= cap and not fixed,
        "_queue": queue,
    }


# ============================================================ outcome read ====

def bin_of(sig, a):
    f = a["fr"].get(sig)
    if sig == "shift_overlap":
        if f is None:
            return None
        return next(lbl for lo, hi, lbl in OVERLAP_BINS if lo <= f < hi)
    if sig == "start_latency":
        if a["available_from"] is None:
            return None
        d = max(0, (a["available_from"] - a["applied"]).days)
        return next(lbl for lo, hi, lbl in LATENCY_BINS if lo <= d <= hi)
    if sig == "travel":
        return a["travel"] or None
    if sig in ("reliability", "rota_experience"):
        return a[sig] or None
    if sig == "certifications":
        return "has one" if f else "none"
    return None


def outcome_read(apps, rubric, t_a, t_b, as_of):
    hires = [a for a in apps if a["hired"] == "yes" and a["day30"] in ("yes", "no")]
    res = {"n": len(hires), "enough": len(hires) >= MIN_OUTCOMES}
    if not res["enough"]:
        return res
    for a in hires:
        a["score"], a["confirm"], a["parts"], a["fr"] = score(a, rubric)
    stay = lambda xs: (sum(1 for a in xs if a["day30"] == "yes"), len(xs))
    k, n = stay(hires)
    res["stayed"] = k / n
    res["auc"] = auc([a["score"] for a in hires if a["day30"] == "yes"],
                     [a["score"] for a in hires if a["day30"] == "no"])
    by_band = {}
    for name, cond in (("call_today", lambda s: s >= t_a), ("call_if_dry", lambda s: t_b <= s < t_a),
                       ("hold", lambda s: s < t_b)):
        xs = [a for a in hires if cond(a["score"])]
        kk, nn = stay(xs)
        by_band[name] = {"n": nn, "stayed": kk / nn if nn else None, "ci": wilson(kk, nn)}
    res["by_band"] = by_band
    sig = rubric["signals"]
    res["signals"] = {}
    for s in SIGNALS:
        levels = collections.defaultdict(list)
        for a in hires:
            b = bin_of(s, a)
            if b is not None:
                levels[b].append(a)
        table = {b: {"n": len(xs), "stayed": stay(xs)[0] / len(xs), "ci": wilson(*stay(xs))}
                 for b, xs in levels.items()}
        entry = {"in_rubric": s in sig, "levels": table}
        # High arm against low arm, by the share of points (or by the signal's own order if unscored).
        if s == "travel" and s in sig:
            lv = {norm_key(k): float(v) for k, v in sig[s]["levels"].items()}
            hi_set = {l for l in TRAVEL_LEVELS if lv.get(l, 0) >= 0.75}
            lo_set = {l for l in TRAVEL_LEVELS if lv.get(l, 0) <= 0.25}
            arm = lambda a: (1 if a["travel"] in hi_set else 0 if a["travel"] in lo_set else None)
        elif s == "travel":
            arm = lambda a: (1 if a["travel"] in ("route_with_time", "own_transport")
                             else 0 if a["travel"] == "no_plan" else None)
        elif s in ("shift_overlap", "start_latency"):
            def arm(a, s=s):
                f = fractions(a, rubric).get(s) if s in sig else None
                if f is None and s == "start_latency" and a["available_from"] is not None:
                    d = max(0, (a["available_from"] - a["applied"]).days)
                    f = 1.0 if d <= 7 else 0.0 if d > 28 else 0.5
                if f is None and s == "shift_overlap":
                    f = site_overlap(a["avail"], a["site"], rubric)
                return None if f is None else 1 if f >= 0.75 else 0 if f <= 0.35 else None
        elif s == "certifications":
            bonus = {norm_key(c) for c in (sig.get(s) or {}).get("bonus") or []}
            arm = lambda a, bonus=bonus: (1 if (a["certs"] & bonus if bonus else a["certs"]) else 0)
        else:
            arm = lambda a, s=s: {"yes": 1, "no": 0}.get(a[s])
        strat = (lambda a: a["travel"] or "blank") if s == "shift_overlap" else (lambda a: bin_of("shift_overlap", a) or "blank")
        cells = collections.defaultdict(lambda: [0, 0, 0, 0])
        for a in hires:
            x = arm(a)
            if x is None:
                continue
            c = cells[strat(a)]
            if x == 1:
                c[0] += a["day30"] == "yes"
                c[1] += 1
            else:
                c[2] += a["day30"] == "yes"
                c[3] += 1
        rd = mh_rd([tuple(c) for c in cells.values()])
        if rd is None or rd["n1"] < MIN_ARM or rd["n0"] < MIN_ARM:
            verdict = "too_few"
        elif rd["lo"] > 0:
            verdict = "earns"
        elif rd["hi"] < 0:
            verdict = "backwards"
        else:
            verdict = "no_separation"
        entry["rd"] = rd
        entry["verdict"] = verdict
        res["signals"][s] = entry
    # Travel levels scored apart that retain alike.
    res["travel_pairs"] = []
    if "travel" in sig:
        lv = {norm_key(k): float(v) for k, v in sig["travel"]["levels"].items()}
        for hi in TRAVEL_LEVELS:
            for lo in TRAVEL_LEVELS:
                if lv.get(hi, 0) - lv.get(lo, 0) < 0.2:
                    continue
                cells = collections.defaultdict(lambda: [0, 0, 0, 0])
                for a in hires:
                    if a["travel"] not in (hi, lo):
                        continue
                    c = cells[bin_of("shift_overlap", a) or "blank"]
                    if a["travel"] == hi:
                        c[0] += a["day30"] == "yes"
                        c[1] += 1
                    else:
                        c[2] += a["day30"] == "yes"
                        c[3] += 1
                rd = mh_rd([tuple(c) for c in cells.values()])
                if rd and rd["n1"] >= MIN_ARM and rd["n0"] >= MIN_ARM and rd["rd"] <= 0.02:
                    res["travel_pairs"].append({"higher": hi, "lower": lo, "points_gap": lv[hi] - lv[lo],
                                                "rd": rd})
    return res


def radius_read(apps, rubric, radius, tri, groups):
    have = [a for a in apps if a["distance"] is not None]
    if len(have) < 0.5 * len(apps):
        return None
    hires = [a for a in have if a["hired"] == "yes" and a["day30"] in ("yes", "no")]
    cells = collections.defaultdict(lambda: [0, 0, 0, 0])
    for a in hires:
        c = cells[a["travel"] or "blank"]
        if a["distance"] <= radius:
            c[0] += a["day30"] == "yes"
            c[1] += 1
        else:
            c[2] += a["day30"] == "yes"
            c[3] += 1
    rd = mh_rd([tuple(c) for c in cells.values()])
    queue = [a for a in tri["_queue"] if a["band"] in ("call_today", "call_if_dry") and a["distance"] is not None]
    cut = [a for a in queue if a["distance"] > radius]
    with_plan = sum(1 for a in cut if a["travel"] in ("route_with_time", "own_transport"))
    out = {"radius": radius, "hires": len(hires), "rd_inside_minus_outside": rd,
           "verdict": ("too_few" if not rd or rd["n1"] < MIN_ARM or rd["n0"] < MIN_ARM
                       else "no_difference" if rd["lo"] <= 0 <= rd["hi"] else
                       "inside_better" if rd["lo"] > 0 else "outside_better"),
           "would_cut": len(cut), "of_called": len(queue), "cut_with_plan": with_plan}
    return out


def adverse_impact(apps, rubric, t_a, groups):
    scored = [a for a in apps if not knocked_out(a, rubric)]
    for a in scored:
        if "parts" not in a:
            a["score"], a["confirm"], a["parts"], a["fr"] = score(a, rubric)
    out = {}
    if groups:
        by = collections.defaultdict(list)
        for a in scored:
            g = groups.get(a["id"])
            if g:
                by[g].append(a)
        rates = {g: {"n": len(xs), "rate": sum(a["score"] >= t_a for a in xs) / len(xs)}
                 for g, xs in by.items() if len(xs) >= MIN_ARM}
        out["groups"] = rates
        out["thin_groups"] = sorted(g for g, xs in by.items() if len(xs) < MIN_ARM)
        if len(rates) >= 2:
            top = max(rates, key=lambda g: rates[g]["rate"])
            flags = []
            for g, v in rates.items():
                if g == top or rates[top]["rate"] == 0:
                    continue
                ratio = v["rate"] / rates[top]["rate"]
                v["ratio"] = ratio
                if ratio < FOUR_FIFTHS:
                    # Which signal opens the gap, in mean points.
                    gaps = {}
                    for s in rubric["signals"]:
                        m = lambda xs: sum(a["parts"].get(s, 0) for a in xs) / len(xs)
                        gaps[s] = m(by[top]) - m(by[g])
                    driver = max(gaps, key=gaps.get)
                    flags.append({"group": g, "ratio": ratio, "reference": top, "driver": driver,
                                  "driver_points": gaps[driver], "gaps": gaps})
            rates[top]["ratio"] = 1.0
            out["flags"] = flags
    # Proxy without self-ID: applicants with a car against everyone with any other answer.
    car = [a for a in scored if a["travel"] == "own_transport"]
    other = [a for a in scored if a["travel"] in ("route_with_time", "route_no_time", "no_plan")]
    if len(car) >= MIN_ARM and len(other) >= MIN_ARM:
        rc = sum(a["score"] >= t_a for a in car) / len(car)
        ro = sum(a["score"] >= t_a for a in other) / len(other)
        out["car_proxy"] = {"car": rc, "no_car_answer": ro, "ratio": (ro / rc) if rc else None}
    return out


def collection_gaps(apps, rubric, cols, outcomes):
    out = []
    n = len(apps)
    colmap = {"shift_overlap": "availability", "start_latency": "available_from", "travel": "travel",
              "reliability": "reliability", "rota_experience": "rota_experience",
              "certifications": "certifications"}
    for s in SIGNALS:
        col = colmap[s]
        in_r = s in rubric["signals"]
        if col not in cols:
            out.append({"signal": s, "issue": "not collected" if not in_r else "in the rubric, not in the file"})
            continue
        if s == "certifications":
            continue
        blank = sum(1 for a in apps if (fractions(a, rubric).get(s) if in_r else bin_of(s, a)) is None)
        if blank / n > BLANK_LIMIT:
            out.append({"signal": s, "issue": f"blank on {blank / n:.0%} of applications"})
    order = {s: i for i, s in enumerate(SIGNALS)}
    eff = lambda s: -abs(((outcomes or {}).get("signals", {}).get(s, {}).get("rd") or {}).get("rd", 0))
    out.sort(key=lambda x: (eff(x["signal"]), order[x["signal"]]))
    return out


# =============================================================== the run ====

def run(rubric_path, apps_path=None, groups_path=None, as_of=None, radius=None, out_csv=None):
    rubric = load_rubric(rubric_path)
    chk = check_rubric(rubric)
    res = {"version": VERSION, "rubric": {k: v for k, v in chk.items()}}
    res["rubric"]["role"] = rubric.get("role")
    if chk["status"] == "blocked" or not apps_path:
        return res, rubric
    apps, cols, unknown_sites = read_applicants(apps_path, rubric)
    groups = read_groups(groups_path, {a["id"] for a in apps}) if groups_path else None
    d = as_of_date(apps, as_of)
    apps = [a for a in apps if a["applied"] <= d]
    tri = triage(apps, rubric, d)
    res["unknown_sites"] = unknown_sites
    res["triage"] = {k: v for k, v in tri.items() if not k.startswith("_")}
    res["outcomes"] = outcome_read(apps, rubric, tri["t_call_today"], tri["t_call_if_dry"], d)
    # outcome_read rescored hires at their own site; restore queue routing scores.
    for a in tri["_queue"]:
        if a["route"]:
            a["score"], a["confirm"], a["parts"], a["fr"] = score(a, rubric, site=a["route"])
    if "distance_km" in cols:
        res["radius"] = radius_read(apps, rubric, radius or DEFAULT_RADIUS, tri, groups)
    res["adverse_impact"] = adverse_impact(apps, rubric, tri["t_call_today"], groups)
    res["collection"] = collection_gaps(apps, rubric, cols, res["outcomes"])
    if out_csv:
        with open(out_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["applicant_id", "site", "route_to", "band", "rank", "score", "confirm_on_call", "reason"])
            for a in sorted(tri["_queue"], key=lambda a: (["call_today", "call_if_dry", "hold", "knockout"]
                                                          .index(a["band"]), a.get("rank", 10 ** 9))):
                w.writerow([a["id"], a["site"], a["route"] or "", a["band"], a.get("rank", ""),
                            f"{a['score']:.1f}", ";".join(a["confirm"]),
                            a["ko_reason"] and f"knockout: {a['ko_reason']}" or a["hold"] or ""])
    res["_queue"] = tri["_queue"]
    return res, rubric


# ================================================================ report ====

def text_report(res):
    L = []
    r = res["rubric"]
    L.append(f"# Resume-free triage: {r.get('role') or 'rubric'}")
    L.append("")
    tag = {"blocked": "BLOCKED", "advice": "READY, WITH ADVICE", "ready": "READY"}[r["status"]]
    L.append(f"## The rubric: {tag}")
    if r["points"]:
        tot = r["total"] or 1
        L.append("")
        L.append("| Signal | Points | Share |")
        L.append("|---|---:|---:|")
        for s in SIGNALS:
            if s in r["points"]:
                L.append(f"| {SIGNAL_LABEL[s]} | {r['points'][s]:g} | {r['points'][s] / tot:.0%} |")
    if r["blocks"]:
        L.append("")
        L.append("Fix before use:")
        for code, t in r["blocks"]:
            L.append(f"- [{code}] {t}")
    if r["advice"]:
        L.append("")
        L.append("Advice:")
        for code, t in r["advice"]:
            L.append(f"- [{code}] {t}")
    if "triage" not in res:
        if r["status"] != "blocked":
            L.append("")
            L.append("Rubric checked. Give an application export (--applicants) to band the queue against it.")
        return "\n".join(L) + "\n"
    t = res["triage"]
    L.append("")
    L.append(f"## The queue, as of {t['as_of']}")
    L.append("")
    L.append(f"{t['queue']} open applicants from the last {t['queue_days']} days; about {t['per_week']:.0f} "
             f"application{'' if round(t['per_week']) == 1 else 's'} a week; your team can make {t['capacity']} calls a week.")
    if t["can_call_everyone"]:
        L.append("You can call everyone in the queue this week. The rubric only sets the order.")
    L.append("")
    L.append("| Band | Applicants | What happens |")
    L.append("|---|---:|---|")
    L.append(f"| Call today | {t['bands']['call_today']} | score {t['t_call_today']:.1f} or more; call within the day |")
    L.append(f"| Call if the top band runs dry | {t['bands']['call_if_dry']} | score {t['t_call_if_dry']:.1f} or more; "
             f"this week |")
    L.append(f"| Hold, with the reason | {t['bands']['hold']} | kept, not rejected |")
    L.append(f"| Knockout | {t['bands']['knockout']} | a minimum age or work authorization answered no |")
    L.append("")
    L.append(f"- Moving the call-today line down 5 points puts {t['line_minus_5']} in it; up 5, {t['line_plus_5']}.")
    L.append(f"- {t['routed']} routed to another site whose gaps they fit; {t['held_for_rota']} held for the "
             "next rota change because nothing they can work is short this week.")
    L.append(f"- {t['confirm_in_call_today']} in call today have a blank to confirm on the call. Scored as zero, "
             f"{t['blank_zero_drop']} of them would have dropped out of the band.")
    if t["stale_in_call_today"]:
        L.append(f"- {t['stale_in_call_today']} in call today applied more than {STALE_DAYS} days ago. "
                 "Call them first or accept that most are hired elsewhere.")
    if t["first_job_shut_out"]:
        L.append(f"- A first-job applicant can score at most {t['first_job_max']:.0f}, under the call-today line. "
                 "Move points off rota experience and certifications.")
    else:
        L.append(f"- A first-job applicant can reach {t['first_job_max']:.0f} points and clear the call-today line.")
    if res.get("unknown_sites"):
        L.append(f"- Sites in the file but not in the rubric (scored with no overlap): "
                 + ", ".join(res["unknown_sites"]) + ".")

    o = res["outcomes"]
    L.append("")
    L.append("## Does each signal earn its points?")
    L.append("")
    if not o["enough"]:
        L.append(f"{o['n']} past hires with a 30-day outcome; at least {MIN_OUTCOMES} are needed. The weights are "
                 "the rubric's priors, not your evidence.")
    else:
        L.append(f"{o['n']} past hires with a 30-day outcome; {pct(o['stayed'])} reached day 30 "
                 "(started and still there). Every comparison is held within shift overlap (overlap itself "
                 "within the travel plan), with 90% ranges.")
        L.append("")
        L.append("| Signal | In rubric | Higher answer vs lower | Range | Verdict |")
        L.append("|---|---|---:|---|---|")
        words = {"earns": "earns its points", "backwards": "works against you",
                 "no_separation": "cannot be told apart", "too_few": "too few to read"}
        for s in SIGNALS:
            e = o["signals"][s]
            rd = e.get("rd")
            if rd:
                L.append(f"| {SIGNAL_LABEL[s]} | {'yes' if e['in_rubric'] else 'no'} | {pts(100 * rd['rd'])} | "
                         f"{100 * rd['lo']:+.1f} to {100 * rd['hi']:+.1f} | {words[e['verdict']]} |")
            else:
                L.append(f"| {SIGNAL_LABEL[s]} | {'yes' if e['in_rubric'] else 'no'} | | | too few to read |")
        for p in o["travel_pairs"]:
            rd = p["rd"]
            L.append("")
            L.append(f"Travel: '{p['higher']}' scores {p['points_gap']:.0%} of the travel points more than "
                     f"'{p['lower']}', but people who answered '{p['lower']}' stayed as well "
                     f"('{p['higher']}' {pts(100 * rd['rd'])}, range {100 * rd['lo']:+.1f} to "
                     f"{100 * rd['hi']:+.1f}). Your outcomes do not back the extra points.")
        a = o.get("auc")
        if a:
            L.append("")
            L.append(f"The rubric's score separates who stayed from who left with an AUC of {a['auc']:.2f} "
                     f"(range {a['lo']:.2f} to {a['hi']:.2f}; 0.50 is a coin).")
        bb = o["by_band"]
        L.append("")
        L.append("Past hires, banded by today's lines: " + "; ".join(
            f"{name.replace('_', ' ')} {pct(v['stayed'])} stayed (n={v['n']})" for name, v in bb.items()
            if v["n"]) + ".")
        L.append("")
        L.append("Read with care: only people you hired have an outcome. The applicants you never called are "
                 "invisible here, and once this rubric picks who gets called, a signal it never lets through "
                 "can no longer be checked. Call a small random slice of the hold band each month to keep "
                 "the check honest.")

    rr = res.get("radius")
    if rr:
        L.append("")
        L.append(f"## What a {rr['radius']:g} km radius would do")
        L.append("")
        rd = rr["rd_inside_minus_outside"]
        if rr["verdict"] == "too_few":
            L.append("Too few hires on each side of the radius to compare.")
        else:
            words = {"no_difference": "no difference anyone can measure",
                     "inside_better": "people inside stayed better", "outside_better": "people outside stayed better"}
            L.append(f"Among {rr['hires']} past hires, held within the travel plan: inside minus outside "
                     f"{pts(100 * rd['rd'])} (range {100 * rd['lo']:+.1f} to {100 * rd['hi']:+.1f}): "
                     f"{words[rr['verdict']]}.")
        L.append(f"It would remove {rr['would_cut']} of the {rr['of_called']} applicants this rubric calls this "
                 f"week, {rr['cut_with_plan']} of them with a car or a route with a time for the earliest shift.")

    ai = res["adverse_impact"]
    L.append("")
    L.append("## Who the call-today line reaches")
    L.append("")
    if ai.get("groups"):
        L.append("| Self-identified group | Applicants | Call today | Ratio to the highest |")
        L.append("|---|---:|---:|---:|")
        for g, v in sorted(ai["groups"].items()):
            L.append(f"| {g} | {v['n']} | {pct(v['rate'])} | {v.get('ratio', 1.0):.2f} |")
        for f in ai.get("flags", []):
            L.append("")
            L.append(f"{f['group']} reaches call today at {f['ratio']:.2f} of {f['reference']}'s rate, under the "
                     f"four-fifths line. The gap comes mostly from {SIGNAL_LABEL[f['driver']].lower()} "
                     f"({f['driver_points']:.1f} points apart on average).")
        if not ai.get("flags"):
            L.append("")
            L.append("No group falls under the four-fifths line.")
        if ai.get("thin_groups"):
            L.append(f"Too few to read: {', '.join(ai['thin_groups'])}.")
    else:
        L.append("No self-ID file. Proxy check only.")
    cp = ai.get("car_proxy")
    if cp:
        L.append("")
        L.append(f"Applicants who answered 'own transport' reach call today at {pct(cp['car'])}; everyone with "
                 f"another travel answer at {pct(cp['no_car_answer'])}"
                 + (f" (ratio {cp['ratio']:.2f})." if cp["ratio"] is not None else "."))
    L.append("")
    L.append("A flag, not a clearance: anything automated should be reviewed by someone qualified with your own "
             "legal position in front of them.")

    if res["collection"]:
        L.append("")
        L.append("## Fields to fix on the form")
        L.append("")
        for c in res["collection"]:
            L.append(f"- {SIGNAL_LABEL[c['signal']]}: {c['issue']}.")
    return "\n".join(L) + "\n"


def json_report(res):
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if not str(k).startswith("_")}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, float):
            return round(x, 4)
        if isinstance(x, (dt.date, set)):
            return str(x)
        return x
    return json.dumps(clean(res), indent=2, sort_keys=True)


# ================================================================= tests ====

def _gen():
    import importlib.util
    spec = importlib.util.spec_from_file_location("marlow_gen", os.path.join(SAMPLE_DIR, "generate.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run_tests():
    results = []

    def check(name, ok, detail=""):
        results.append((name, bool(ok), detail))

    exp = json.load(open(EXPECTED, encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="triage-test-")

    # --- the sample, as shipped
    res, rub = run(SAMPLE_RUBRIC, SAMPLE_APPS, SAMPLE_GROUPS, SAMPLE_AS_OF)
    e = exp["draft"]
    check("draft rubric: status advice", res["rubric"]["status"] == e["status"], res["rubric"]["status"])
    codes = [c for c, _ in res["rubric"]["advice"]]
    for c in e["advice_codes"]:
        check(f"draft rubric: advice {c}", c in codes, codes)
    check("draft rubric: car premium flagged", "car_premium" in codes, codes)
    sigs = res["outcomes"]["signals"]
    for s in e["signals_earning"]:
        check(f"sample: {s} earns its points", sigs[s]["verdict"] == "earns", sigs[s].get("rd"))
    for s in e["signals_not_earning"]:
        check(f"sample: {s} does not separate", sigs[s]["verdict"] in ("no_separation", "too_few"), sigs[s].get("rd"))
    check("sample: certifications do not separate", sigs["certifications"]["verdict"] != "earns")
    pairs = [f"{p['higher']} over {p['lower']}" for p in res["outcomes"]["travel_pairs"]]
    for p in e["travel_pays_for_nothing"]:
        check(f"sample: travel pair '{p}' pays for nothing", p in pairs, pairs)
    check("sample: no_plan is not excused", not any(p.endswith("over no_plan") for p in pairs), pairs)
    flags = res["adverse_impact"].get("flags", [])
    check("sample: draft flags a group under four-fifths", len(flags) == 1, flags)
    check("sample: the flag is driven by travel", flags and flags[0]["driver"] == e["adverse_impact_flag_signal"],
          flags and flags[0]["driver"])
    check("sample: radius shows no difference", res["radius"]["verdict"] == "no_difference", res["radius"])
    t = res["triage"]
    check("sample: call today sized to capacity", t["capacity"] <= t["bands"]["call_today"] <= t["capacity"] + 15,
          t["bands"])
    check("sample: some applicants routed to another site", t["routed"] > 0, t["routed"])
    check("sample: knockouts counted apart", t["bands"]["knockout"] > 0, t["bands"])
    check("sample: blanks matter (some would drop if zero)", t["blank_zero_drop"] > 0, t["blank_zero_drop"])
    check("sample: AUC above a coin", res["outcomes"]["auc"]["lo"] > 0.5, res["outcomes"]["auc"])

    res2, _ = run(SAMPLE_REVISED, SAMPLE_APPS, SAMPLE_GROUPS, SAMPLE_AS_OF)
    check("revised rubric: ready", res2["rubric"]["status"] == exp["revised"]["status"], res2["rubric"])
    check("revised rubric: no group under four-fifths", not res2["adverse_impact"].get("flags"),
          res2["adverse_impact"].get("flags"))
    check("revised rubric: separates at least as well",
          res2["outcomes"]["auc"]["auc"] >= res["outcomes"]["auc"]["auc"] - 0.005,
          (res2["outcomes"]["auc"]["auc"], res["outcomes"]["auc"]["auc"]))
    check("revised rubric: no travel pair pays for nothing", not res2["outcomes"]["travel_pairs"],
          res2["outcomes"]["travel_pairs"])

    # --- determinism
    a1 = json_report(run(SAMPLE_RUBRIC, SAMPLE_APPS, SAMPLE_GROUPS, SAMPLE_AS_OF)[0])
    a2 = json_report(run(SAMPLE_RUBRIC, SAMPLE_APPS, SAMPLE_GROUPS, SAMPLE_AS_OF)[0])
    check("same files, same answer", a1 == a2)

    # --- the scored list
    out = os.path.join(tmp, "scored.csv")
    run(SAMPLE_RUBRIC, SAMPLE_APPS, None, SAMPLE_AS_OF, out_csv=out)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    check("scored list: one row per open applicant", len(rows) == t["queue"], (len(rows), t["queue"]))
    check("scored list: every hold has a reason",
          all(r["reason"] for r in rows if r["band"] in ("hold", "knockout")))
    check("scored list: call today first, ranked", rows[0]["band"] == "call_today" and rows[0]["rank"] == "1")
    check("scored list: holds a routed applicant", any(r["route_to"] for r in rows))

    # --- broken rubrics: each blocked for the right reason
    base = load_rubric(SAMPLE_REVISED)

    def mutated(fn):
        r = json.loads(json.dumps(base))
        fn(r)
        return r

    def setp(path, value):
        def f(r):
            d = r
            for k in path[:-1]:
                d = d[k]
            d[path[-1]] = value
        return f

    cases = [
        ("distance signal", lambda r: r["signals"].update({"distance_km": {"points": 10}}), "distance"),
        ("radius at top level", setp(["radius_km"], 10), "distance"),
        ("commute question", setp(["signals", "travel", "question"], "Do you live within 10 miles of the site?"),
         "distance"),
        ("zip question", setp(["signals", "travel", "question"], "What is your zip code?"), "distance"),
        ("employment gap signal", lambda r: r["signals"].update({"employment_gap": {"points": 5}}), "gap"),
        ("gap question", lambda r: r.update({"form_questions": ["Please explain any gap in your employment."]}),
         "risky_question"),
        ("tenure signal", lambda r: r["signals"].update({"years_in_last_job": {"points": 5}}), "tenure"),
        ("resume signal", lambda r: r["signals"].update({"resume_attached": {"points": 5}}), "resume"),
        ("education signal", lambda r: r["signals"].update({"high_school_diploma": {"points": 5}}), "education"),
        ("reapplicant penalty", lambda r: r["signals"].update({"previously_rejected": {"points": -5}}),
         "reapplicant"),
        ("unknown signal", lambda r: r["signals"].update({"enthusiasm": {"points": 5}}), "unknown_signal"),
        ("availability as knockout", lambda r: r["knockouts"].append(
            {"field": "available_weekends", "rule": "must work weekends"}), "availability_gate"),
        ("min overlap at a site", lambda r: r["sites"]["MRL-01"].update({"min_overlap": 0.5}), "availability_gate"),
        ("overlap as a gate", setp(["signals", "shift_overlap", "min"], 0.5), "availability_gate"),
        ("no overlap points", setp(["signals", "shift_overlap", "points"], 0), "no_overlap"),
        ("experience knockout", lambda r: r["knockouts"].append(
            {"field": "years_experience", "rule": "2 years warehouse experience"}), "tenure"),
        ("criminal knockout", lambda r: r["knockouts"].append(
            {"field": "criminal_record", "rule": "no felony"}), "criminal"),
        ("knockout with no lawful basis", lambda r: r["knockouts"].append(
            {"field": "own_car", "rule": "has a car"}), "bad_knockout"),
        ("certificate knockout without law", lambda r: r["knockouts"].append(
            {"field": "forklift_cert", "rule": "forklift certification"}), "cert_knockout"),
        ("too many knockouts", lambda r: r["knockouts"].extend([
            {"field": "k1", "rule": "18 or older"}, {"field": "k2", "rule": "authorized to work"}]),
         "too_many_knockouts"),
        ("childcare question", lambda r: r.update({"form_questions": ["Do you have childcare for night shifts?"]}),
         "risky_question"),
        ("age question", setp(["knockouts", 0, "question"], "How old are you?"), "risky_question"),
        ("citizenship question", setp(["knockouts", 1, "question"], "Are you a US citizen?"), "risky_question"),
        ("health question", lambda r: r.update({"form_questions": ["Do you have any medical condition?"]}),
         "risky_question"),
        ("pay history question", lambda r: r.update({"form_questions": ["What was your previous pay rate?"]}),
         "risky_question"),
        ("self-rated reliability", setp(["signals", "reliability", "question"], "Are you reliable?"),
         "vague_reliability"),
        ("travel levels missing", setp(["signals", "travel", "levels"], {"own_transport": 1.0}), "travel_levels"),
        ("travel order inverted", setp(["signals", "travel", "levels"],
                                       {"own_transport": 1.0, "route_with_time": 0.2, "route_no_time": 0.5,
                                        "no_plan": 0.0}), "travel_order"),
        ("no capacity", lambda r: r.pop("calls_per_week"), "no_capacity"),
        ("site with no gaps", setp(["sites", "MRL-02", "gaps"], []), "no_gaps"),
        ("unknown block", setp(["sites", "MRL-02", "gaps", 0, "block"], "saturday-ish"), "bad_gap"),
        ("certifications with no list", setp(["signals", "certifications", "bonus"], []), "cert_list"),
        ("first job shut out", lambda r: (r["signals"]["rota_experience"].update({"points": 40}),
                                          r.update({"bands": {"call_today": 95, "call_if_dry": 60}})),
         "first_job_shut_out"),
        ("bad bands", lambda r: r.update({"bands": {"call_today": 40, "call_if_dry": 60}}), "bad_bands"),
        ("negative points", setp(["signals", "travel", "points"], -5), "bad_points"),
        ("date of birth knockout", lambda r: r["knockouts"].__setitem__(0, {"field": "date_of_birth",
                                                                             "rule": "18 or older"}),
         "risky_question"),
    ]
    for name, fn, code in cases:
        try:
            chk = check_rubric(mutated(fn))
            got = [c for c, _ in chk["blocks"]]
            check(f"blocked: {name}", code in got, got)
        except Refused as ex:
            check(f"blocked: {name}", False, f"refused: {ex}")
    # A certificate the law requires may be a knockout.
    ok = check_rubric(mutated(lambda r: r["knockouts"][:1].clear() or r["knockouts"].append(
        {"field": "cdl", "rule": "Class A CDL licence", "legal_basis": "FMCSA requires a CDL to drive the route"})))
    check("allowed: certificate knockout with its legal basis", ok["status"] in ("ready", "advice"), ok["blocks"])
    # A blocked rubric is never scored.
    p = os.path.join(tmp, "blocked.json")
    json.dump(mutated(lambda r: r["signals"].update({"distance_km": {"points": 10}})), open(p, "w"))
    rb, _ = run(p, SAMPLE_APPS)
    check("a blocked rubric scores nobody", "triage" not in rb)

    # --- scoring rules, one applicant at a time
    rv = base
    a0 = {"id": "X1", "applied": dt.date(2026, 10, 20), "site": "MRL-02",
          "avail": {"sat_early", "sun_early", "sat_late", "sun_late"}, "generous": False,
          "available_from": dt.date(2026, 10, 22), "travel": "route_with_time", "distance": 4.0,
          "reliability": "yes", "rota_experience": "yes", "certs": {"forklift"}, "reapplicant": "no",
          "ko": {"age_18_plus": "yes", "work_authorized": "yes"}, "called": "", "hired": "",
          "hired_at": None, "started": "", "day30": ""}
    s_full = score(a0, rv)[0]
    check("a perfect applicant scores every point", abs(s_full - 100) < 1e-9, s_full)
    b = dict(a0, travel="", reliability="")
    sb, conf, _, _ = score(b, rv)
    check("a blank is half points and a question for the call, not a zero",
          abs(sb - 85) < 1e-9 and set(conf) == {"travel", "reliability"}, (sb, conf))
    r_ = dict(a0, reapplicant="yes")
    check("a re-applicant scores exactly the same", score(r_, rv)[0] == s_full)
    fj = dict(a0, rota_experience="no", certs=set())
    check("a first job loses only the weak signals", abs(score(fj, rv)[0] - 90) < 1e-9, score(fj, rv)[0])
    car = dict(a0, travel="own_transport")
    check("revised rubric: a route with a time scores as a car", score(car, rv)[0] == s_full)
    far = dict(a0, distance=40.0)
    check("distance never moves the score", score(far, rv)[0] == s_full)
    gen = dict(a0, avail=set(BLOCKS), generous=True)
    check("'any availability' is confirmed on the call", "shift_overlap" in score(gen, rv)[1])
    av, g, u, n = parse_availability("Saturday nights; weekends early; mon pm")
    check("availability words are read", av == {"sat_night", "sat_early", "sun_early", "mon_late"} and u == 0, av)

    check("ATS words for outcomes are read", yes_no("Hired") == "yes" and yes_no("Terminated") == "no"
          and yes_no("Active") == "yes" and yes_no("maybe") == "")

    # routing
    apps = [dict(a0, id=f"R{i}", site="MRL-01", avail={"sat_early", "sun_early", "sat_late", "sun_late"})
            for i in range(3)] + [dict(a0, id="Z0", site="MRL-01", avail={"tue_late"})]
    tri = triage(apps, json.loads(json.dumps(dict(rv, calls_per_week=10))), dt.date(2026, 10, 30))
    q = {a["id"]: a for a in tri["_queue"]}
    check("no overlap here but full overlap at another site: routed, not rejected",
          q["R0"]["route"] == "MRL-02" and q["R0"]["band"] == "call_today", (q["R0"]["route"], q["R0"]["band"]))
    check("no overlap anywhere: held for the next rota, with the reason",
          q["Z0"]["band"] == "hold" and "next rota" in (q["Z0"]["hold"] or ""), q["Z0"]["hold"])
    ko = dict(a0, id="K1", ko={"age_18_plus": "no", "work_authorized": "yes"})
    ko_blank = dict(a0, id="K2", ko={"age_18_plus": "", "work_authorized": "yes"})
    tri = triage([ko, ko_blank], json.loads(json.dumps(dict(rv, calls_per_week=10))), dt.date(2026, 10, 30))
    q = {a["id"]: a for a in tri["_queue"]}
    check("a knockout answered no is a knockout", q["K1"]["band"] == "knockout")
    check("a knockout left blank is not", q["K2"]["band"] == "call_today")

    # --- worlds with nothing planted, and shuffles: no signal may earn
    gen_mod = _gen()
    false_pos = 0
    for seed in (11, 12, 13):
        d = os.path.join(tmp, f"null{seed}")
        rows, grp = gen_mod.generate(seed, plants=False)
        os.makedirs(d, exist_ok=True)
        _write_rows(os.path.join(d, "a.csv"), rows)
        _write_rows(os.path.join(d, "g.csv"), grp)
        rn, _ = run(SAMPLE_REVISED, os.path.join(d, "a.csv"), os.path.join(d, "g.csv"), SAMPLE_AS_OF)
        earned = [s for s, v in rn["outcomes"]["signals"].items() if v["verdict"] == "earns"]
        false_pos += len(earned)
        check(f"null world {seed}: no group flagged", not rn["adverse_impact"].get("flags"),
              rn["adverse_impact"].get("flags"))
    check("null worlds: at most one signal of 18 'earns' by chance", false_pos <= 1, false_pos)
    rows = list(csv.DictReader(open(SAMPLE_APPS, encoding="utf-8")))
    rng = random.Random(5)
    for k in range(2):
        outs = [r["day30"] for r in rows if r["hired"] == "yes"]
        rng.shuffle(outs)
        it = iter(outs)
        sh = [dict(r, day30=next(it)) if r["hired"] == "yes" else r for r in rows]
        p = os.path.join(tmp, f"shuf{k}.csv")
        _write_rows(p, sh)
        rs, _ = run(SAMPLE_REVISED, p, None, SAMPLE_AS_OF)
        earned = [s for s, v in rs["outcomes"]["signals"].items() if v["verdict"] == "earns"]
        check(f"outcomes shuffled ({k}): no signal earns", len(earned) <= 1, earned)

    # --- refusals
    def refused(rows_, name, rub=SAMPLE_RUBRIC, groups=None):
        p = os.path.join(tmp, name)
        _write_rows(p, rows_)
        try:
            run(rub, p, groups)
            return False
        except Refused:
            return True

    head = rows[:200]
    check("refused: a name column", refused([dict(r, first_name="Ann") for r in head], "n.csv"))
    check("refused: an email in a value", refused([dict(r, travel="x@y.com") if i == 3 else r
                                                    for i, r in enumerate(head)], "e.csv"))
    check("refused: a phone number in a value", refused([dict(r, certifications="+1 415 555 0134") if i == 3 else r
                                                         for i, r in enumerate(head)], "p.csv"))
    check("refused: names in the id column", refused([dict(r, applicant_id="Maria Lopez") for r in head], "i.csv"))
    check("refused: free-text travel", refused([dict(r, travel="bus 42 then walk") for r in head], "t.csv"))
    check("refused: free-text availability", refused([dict(r, availability="whenever really") for r in head],
                                                     "v.csv"))
    check("refused: no applied_at", refused([{k: v for k, v in r.items() if k != "applied_at"} for r in head],
                                            "d.csv"))
    check("refused: knockout field not collected",
          refused([{k: v for k, v in r.items() if k != "age_18_plus"} for r in head], "k.csv"))
    check("refused: sites that do not match", refused([dict(r, site="STORE-9") for r in head], "s.csv"))
    gp = os.path.join(tmp, "g3.csv")
    _write_rows(gp, [{"applicant_id": r["applicant_id"], "group": "group_1", "travel": r["travel"]} for r in head])
    check("refused: a groups file carrying other columns", refused(head, "h.csv", groups=gp))
    for bad in ("{", "[]", '{"sites": {}}'):
        p = os.path.join(tmp, "bad.json")
        open(p, "w").write(bad)
        try:
            run(p)
            ok_ = False
        except Refused:
            ok_ = True
        check(f"refused: rubric file {bad!r}", ok_)

    # --- damaged files never crash
    crashed = []
    frng = random.Random(99)
    cols = list(rows[0])
    for i in range(100):
        rr = [dict(r) for r in rows[:frng.randint(1, 400)]]
        for _ in range(frng.randint(1, 30)):
            r = frng.choice(rr)
            c = frng.choice(cols)
            r[c] = frng.choice(["", "n/a", "13/45/2026", "-3", "yes", "maybe", "sun_night;;", "9999-01-01",
                                "own_transport", "ÿ", "NaN", "1e309", "MRL-01", "  ", "any"])
        if frng.random() < 0.2:
            drop = frng.choice(cols)
            rr = [{k: v for k, v in r.items() if k != drop} for r in rr]
        p = os.path.join(tmp, f"fz{i}.csv")
        _write_rows(p, rr)
        try:
            run(SAMPLE_RUBRIC, p, None, SAMPLE_AS_OF, out_csv=os.path.join(tmp, "fz_out.csv"))
        except Refused:
            pass
        except Exception as ex:  # noqa: BLE001
            crashed.append(f"{i}: {type(ex).__name__}: {ex}")
    check("100 damaged files: refused or read, never a crash", not crashed, crashed[:3])

    passed = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        if not ok:
            print(f"FAIL  {name}  {str(detail)[:300]}")
    print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


def _write_rows(path, rows):
    if not rows:
        open(path, "w").close()
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


# ================================================================== main ====

def main(argv):
    ap = argparse.ArgumentParser(description="Resume-free triage rubric: check, score, validate.")
    ap.add_argument("--rubric")
    ap.add_argument("--applicants")
    ap.add_argument("--groups")
    ap.add_argument("--as-of")
    ap.add_argument("--radius", type=float)
    ap.add_argument("--out")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--revised", action="store_true")
    ap.add_argument("--test", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.test:
            return run_tests()
        if a.demo:
            res, _ = run(SAMPLE_REVISED if a.revised else SAMPLE_RUBRIC, SAMPLE_APPS, SAMPLE_GROUPS,
                         SAMPLE_AS_OF, a.radius, a.out)
        elif a.rubric:
            res, _ = run(a.rubric, a.applicants, a.groups, a.as_of, a.radius, a.out)
        else:
            ap.print_help()
            return 3
        print(json_report(res) if a.json else text_report(res), end="")
        return 3 if res["rubric"]["status"] == "blocked" else 0
    except Refused as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"The engine failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
