#!/usr/bin/env python3
"""
Turnover engine.

Deterministic analysis of early attrition in a frontline workforce, by tenure
band. Standard library only - no pandas, no numpy, no network. The same input
always produces the same output, which is the point: the statistics in this
skill are computed here, not improvised in prose.

    analyze.py --input export.csv [--out report.json]
    analyze.py --test

The input must be mapped to the canonical schema in references/schema.json.

The question this engine answers is not "what is our turnover rate". It is
whether your attrition is a hiring-and-first-month problem or a job problem,
because those have different owners and nothing in a single percentage tells
them apart. It answers that by looking for segment structure in each tenure
band separately and asking whether the structure found early persists later.

What it refuses to do:
  - analyse a file carrying nominative columns
  - compute a 90-day rate over people hired six weeks ago
  - report a segment effect that did not survive its confound check
  - claim exit reasons explain a segment when a permutation test says the
    mix is indistinguishable from chance
"""

import argparse
import csv
import json
import math
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(SKILL_DIR, "references", "schema.json")

with open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

STAGE_PROFILES = SCHEMA["stage_profiles"]
PROFILE_NAMES = [k for k in STAGE_PROFILES if not k.startswith("$")]

PROFILE = None
PROFILE_NAME = None
STAGES = []
STAGE_IX = {}
START_COL = ""
START_NOUN = ""

TT = SCHEMA["turnover_thresholds"]
BANDS = TT["bands"]
MIN_HIRES = TT["min_hires"]
MIN_COHORT = TT["min_cohort"]
MIN_SEG = TT["min_segment_cohort"]
FLAG_RATIO = TT["flag_ratio"]
FLAG_MIN_POINTS = TT["flag_min_points"]
FDR_Q = TT["fdr_q"]
COLLINEAR = TT["collinear_threshold"]
MIN_ELIGIBLE = TT["min_eligible_share"]
PERMUTATIONS = TT["permutations"]
PERM_SEED = TT["permutation_seed"]
DISCRIM_PCTL = TT["discriminates_percentile"]
Z = SCHEMA["thresholds"]["wilson_z"]
KILL_FRACTION = SCHEMA["thresholds"]["confound_kill_fraction"]

SEGMENT_DIMS = ["hiring_manager_id", "location_id", "region", "role", "source"]


def _skill_version():
    try:
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            found = re.search(r"^version:\s*(.+)$", fh.read(2000), re.M)
        return found.group(1).strip() if found else "unknown"
    except OSError:
        return "unknown"


SKILL_VERSION = _skill_version()


class Refusal(Exception):
    """Raised when the engine will not analyse the input. Not an error."""


def bind_profile(name):
    global PROFILE, PROFILE_NAME, STAGES, STAGE_IX, START_COL, START_NOUN
    PROFILE = STAGE_PROFILES[name]
    PROFILE_NAME = name
    STAGES = PROFILE["stages"]
    STAGE_IX = {s: i for i, s in enumerate(STAGES)}
    START_COL = PROFILE["stage_dates"][-1]
    START_NOUN = PROFILE["start_noun"]


def detect_profile(rows):
    seen = {(r.get("stage_reached") or "").strip() for r in rows}
    seen.discard("")
    if not seen:
        raise Refusal("No stage_reached values found. There is no workforce to analyse.")
    scored = sorted(((len(seen & set(STAGE_PROFILES[n]["stages"])), n)
                     for n in PROFILE_NAMES), reverse=True)
    best_n, best = scored[0]
    if best_n == 0:
        raise Refusal(
            "None of the stage_reached values match a funnel this engine knows: "
            + ", ".join(sorted(seen)[:8]) + ". Map them onto one of the schema's "
            "stage lists first.")
    unknown = seen - set(STAGE_PROFILES[best]["stages"])
    if unknown:
        raise Refusal(
            f"Read as the '{best}' funnel, but these stage_reached values do not "
            "belong to it: " + ", ".join(sorted(unknown)) + ". Mixed stage "
            "vocabularies produce a hire population that is wrong in a way that "
            "still looks plausible, so this will not run.")
    return best


bind_profile("hire")


# --------------------------------------------------------------- primitives

def probit(p):
    """Inverse standard normal CDF (Acklam's rational approximation).

    Needed because the confidence level has to move with the number of
    segments being tested, and the table of z values that would cover it is
    not a table -- it is a function of how many managers you happen to have."""
    if not 0.0 < p < 1.0:
        raise ValueError("probit needs 0 < p < 1")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def normal_sf(z):
    """P(Z > z). math.erfc is exact enough and costs no dependency."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def two_proportion_p(k1, n1, k2, n2):
    """One-sided p for 'this segment leaves more often than the rest'.

    One-sided because the question is never whether a segment is unusual in
    either direction -- nobody acts on a location that retains people better
    than average, and testing two-sided here would halve the power for
    nothing."""
    if not n1 or not n2:
        return 1.0
    p1, p2 = k1 / n1, k2 / n2
    if p1 <= p2:
        return 1.0
    pool = (k1 + k2) / (n1 + n2)
    denom = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if denom == 0:
        return 1.0
    return normal_sf((p1 - p2) / denom)


def benjamini_hochberg(pairs, q=None):
    """Which of these segments survive screening, controlling the false
    discovery rate at q.

    Screening forty managers across four dimensions and three bands is two
    hundred tests, and at the 5% level that is ten findings in a file with
    nothing in it -- which is exactly what this engine did before this
    function existed. Bonferroni fixes that and costs most of the real
    findings with it: on one sample it went from five planted managers to
    three. Benjamini-Hochberg asks the useful question instead -- of the
    things I am about to report, what share are expected to be wrong -- and
    keeps the power to find them. Returns the set of keys that survive."""
    q = FDR_Q if q is None else q
    ordered = sorted(pairs, key=lambda kp: kp[1])
    m = len(ordered)
    cutoff = 0
    for i, (_key, p) in enumerate(ordered, start=1):
        if p <= (i / m) * q:
            cutoff = i
    return {key for key, _p in ordered[:cutoff]}


def wilson(k, n, z=Z):
    if not n:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom))


def rate_block(k, n):
    if not n:
        return {"n": 0, "k": 0, "rate": None, "ci": [None, None], "conclusive": False}
    lo, hi = wilson(k, n)
    return {"n": n, "k": k, "rate": round(k / n, 4),
            "ci": [round(lo, 4), round(hi, 4)], "conclusive": n >= MIN_SEG}


def parse_date(value):
    if not value:
        return None
    try:
        parts = value.strip()[:10].split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def tenure_of(row):
    raw = (row.get("tenure_days") or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def reached_end(row):
    return STAGE_IX.get((row.get("stage_reached") or "").strip()) == len(STAGES) - 1


def ratio(a, b):
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 3)


# --------------------------------------------------------------- ingest

def check_columns(columns):
    banned = set(SCHEMA["refuses"]["nominative_columns"])
    banned_tokens = {b for b in banned if "_" not in b}
    offenders = []
    for col in columns:
        norm = col.strip().lower()
        tokens = {t for t in norm.replace("-", "_").replace(" ", "_").split("_") if t}
        if norm in banned or (tokens & banned_tokens):
            offenders.append(col)
    if offenders:
        raise Refusal(
            "This export carries columns that look nominative: "
            + ", ".join(sorted(offenders))
            + ". Re-export without them - drop or hash names, emails, phone numbers, "
            "addresses, dates of birth and free-text notes. Nothing in a turnover "
            "analysis needs to know who anybody is.")


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        rows = list(reader)
    if not columns:
        raise Refusal("That file has no header row.")
    check_columns(columns)

    missing = [c for c, spec in SCHEMA["columns"].items()
               if spec.get("required") and c not in columns]
    if missing:
        raise Refusal("Missing required columns: " + ", ".join(missing) + ".")

    bind_profile(detect_profile(rows))

    if "tenure_days" not in columns:
        raise Refusal(
            "This export has no `tenure_days` column, so there is nothing to measure. "
            "Turnover needs how long each person stayed, not just that they left. If "
            "your system reports a separation date instead, send `separation_at` "
            f"alongside `{START_COL}` and compute the difference before exporting.")
    if START_COL not in columns:
        raise Refusal(
            f"This export has no `{START_COL}` column. Without the date someone "
            f"actually had their {START_NOUN}, a tenure band cannot be given a cohort "
            "that has had time to reach it, and every rate below would be understated "
            "by however many people were hired last week.")

    hires = [r for r in rows if reached_end(r) and parse_date(r.get(START_COL))]
    if len(hires) < MIN_HIRES:
        raise Refusal(
            f"Only {len(hires):,} people in this file actually reached {STAGES[-1]}. "
            f"Below {MIN_HIRES:,} hires a band rate moves several points on a handful "
            "of records, so this will not run. Export a longer period.")
    return columns, rows, hires


def observation_end(rows):
    """The last date anything happened. Used as 'today' for cohort eligibility,
    because an export's own horizon is what limits what it can have observed."""
    latest = None
    for row in rows:
        for col, value in row.items():
            if not col.endswith("_at"):
                continue
            d = parse_date(value)
            if d and (latest is None or d > latest):
                latest = d
    return latest


# ------------------------------------------------------------ cohort logic

def cohort_for(hires, band, as_of):
    """Who was actually at risk of leaving during this band.

    Two filters, and both matter.

    Observation: someone hired three weeks before the export closed cannot be
    recorded as a 90-day leaver. Counting them in the denominator is not
    conservative, it is wrong in the flattering direction, by exactly as much
    as you have been hiring lately.

    At risk: someone who left on day 20 was never going to leave between days
    31 and 90. Leaving them in the denominator makes each band's rate depend
    on the band before it -- a segment with terrible first-month attrition
    gets an artificially low 31-90 rate because its denominator is full of
    people who had already gone. A band rate is a conditional hazard: of the
    people who reached the start of this band, how many left during it."""
    edge = band["hi"] if band["hi"] is not None else band["lo"]
    out = []
    for row in hires:
        started = parse_date(row.get(START_COL))
        if not started or (as_of - started).days < edge:
            continue
        tenure = tenure_of(row)
        if tenure is not None and tenure < band["lo"]:
            continue
        out.append(row)
    return out


def left_in_band(row, band):
    t = tenure_of(row)
    if t is None:
        return False
    if t < band["lo"]:
        return False
    return band["hi"] is None or t <= band["hi"]


# --------------------------------------------------------------- pass 1

def pass1_bands(hires, as_of):
    """The rate in each tenure band, each over its own eligible cohort, with
    the naive rate reported beside it so the size of the correction is visible
    rather than merely applied."""
    out = []
    for band in BANDS:
        cohort = cohort_for(hires, band, as_of)
        k = sum(1 for r in cohort if left_in_band(r, band))
        naive_k = sum(1 for r in hires if left_in_band(r, band))
        block = dict(band)
        block["cohort"] = rate_block(k, len(cohort))
        block["eligible_share"] = round(len(cohort) / len(hires), 4) if hires else None
        block["excluded_too_recent"] = len(hires) - len(cohort)
        block["naive_rate"] = round(naive_k / len(hires), 4) if hires else None
        block["understated_by"] = (
            round((k / len(cohort)) - (naive_k / len(hires)), 4)
            if cohort and hires else None)
        block["conclusive"] = len(cohort) >= MIN_COHORT
        # A band where nobody at all is recorded as leaving is almost never a
        # workforce nobody leaves. It is a tenure field that stops counting,
        # or an export whose window is shorter than the band. Reporting 0.0%
        # as though it were measured invites exactly the wrong conclusion.
        if len(cohort) and k == 0:
            block["no_events_recorded"] = True
            block["conclusive"] = False
            block["note"] = (
                f"No separations at all are recorded in the {band['label']} across "
                f"{len(cohort):,} people who reached it. Read this as the data "
                "stopping rather than as nobody leaving: usually `tenure_days` is "
                "only populated for early leavers, or the export window is shorter "
                "than the band.")
        out.append(block)
    return out


# --------------------------------------------------------------- pass 2

def segments_in_band(hires, band, as_of, dim):
    cohort = cohort_for(hires, band, as_of)
    buckets = defaultdict(list)
    for row in cohort:
        key = (row.get(dim) or "").strip()
        if key:
            buckets[key].append(row)
    eligible = {k: v for k, v in buckets.items() if len(v) >= MIN_SEG}
    if len(eligible) < 2:
        return None

    table, tests = [], []
    for key, bucket in sorted(eligible.items()):
        rest = [r for k2, v in eligible.items() if k2 != key for r in v]
        k = sum(1 for r in bucket if left_in_band(r, band))
        k_rest = sum(1 for r in rest if left_in_band(r, band))
        mine = k / len(bucket)
        theirs = (k_rest / len(rest)) if rest else None
        pval = two_proportion_p(k, len(bucket), k_rest, len(rest)) if rest else 1.0
        entry = {"segment": key, "n": len(bucket), "k": k, "rate": round(mine, 4),
                 "rest_rate": round(theirs, 4) if theirs is not None else None,
                 "ratio": ratio(mine, theirs),
                 "excess_points": round(mine - theirs, 4) if theirs is not None else None,
                 "p_value": round(pval, 6)}
        table.append(entry)
        tests.append((key, pval))

    table.sort(key=lambda e: -(e["rate"] or 0))
    return {"dimension": dim, "segments": len(eligible), "table": table,
            "_tests": tests}


def collinear_dimensions(rows):
    """Which dimensions cut this file the same way.

    In most frontline exports one manager runs one site, so location_id and
    hiring_manager_id are the same column wearing two names. Screened
    separately they double the number of tests and then report one finding
    twice, which reads as corroboration and is not. Detected by asking
    whether one dimension's values map onto the other's as a function."""
    def functional(rows, a, b):
        mapping, consistent, total = {}, 0, 0
        for row in rows:
            ka, kb = (row.get(a) or "").strip(), (row.get(b) or "").strip()
            if not ka or not kb:
                continue
            total += 1
            mapping.setdefault(ka, kb)
            consistent += 1 if mapping[ka] == kb else 0
        return (consistent / total if total else 0.0), len(mapping)

    pairs = []
    for i, a in enumerate(SEGMENT_DIMS):
        for b in SEGMENT_DIMS[i + 1:]:
            ab, n_a = functional(rows, a, b)
            ba, n_b = functional(rows, b, a)
            # Both directions, and similar cardinality. One-directional is not
            # enough: every manager sits in exactly one region, which makes
            # manager -> region a perfect function and says nothing at all --
            # forty managers and four regions are not the same cut of the
            # data. Calling them collinear would collapse a real finding.
            if (ab >= COLLINEAR and ba >= COLLINEAR and min(n_a, n_b) > 1
                    and min(n_a, n_b) / max(n_a, n_b) >= COLLINEAR):
                pairs.append({"dimensions": [a, b],
                              "agreement": round(min(ab, ba), 4),
                              "values": [n_a, n_b],
                              "reads": (f"`{a}` and `{b}` partition this file the "
                                        "same way, so a finding on one is the same "
                                        "finding on the other, not a second one.")})
    return pairs


def pass2_segments(hires, bands, as_of):
    """Screen each band once, across every dimension at the same time.

    The screening family is the band, not the dimension. A reader looking at
    the 31-90 band asks one question -- is anything unusual in here -- and
    that question is answered by a hundred and sixty tests, not by four
    separate exercises of forty. Splitting them into four families let each
    one spend the full error budget, which is how a band with nothing planted
    in it produced findings on one sample and not on the other three."""
    out = []
    for band in bands:
        if not band["conclusive"]:
            continue
        dims, family = {}, []
        for dim in SEGMENT_DIMS:
            block = segments_in_band(hires, band, as_of, dim)
            if block:
                dims[dim] = block
                family.extend(((dim, key), p) for key, p in block.pop("_tests"))
        survivors = benjamini_hochberg(family) if family else set()

        for dim, block in dims.items():
            block["flagged"] = sorted(
                (e for e in block["table"]
                 if (dim, e["segment"]) in survivors
                 and e["ratio"] is not None and e["ratio"] >= FLAG_RATIO
                 and e["excess_points"] is not None
                 and e["excess_points"] >= FLAG_MIN_POINTS),
                key=lambda e: -(e["excess_points"] or 0))
            block["table"] = block["table"][:12]

        out.append({"band": band["name"], "label": band["label"],
                    "screened": len(family), "survived_screening": len(survivors),
                    "fdr_q": FDR_Q, "by": dims,
                    "any_structure": any(d["flagged"] for d in dims.values())})
    return out


# --------------------------------------------------------------- pass 3

def confound_check(cohort, band, dim, flagged_names, confounders, derived=None):
    """Does a segment's higher attrition survive holding another dimension
    constant? Weighted within-stratum differences, compared to the raw one."""
    flagged = set(flagged_names)
    inside = [r for r in cohort if (r.get(dim) or "").strip() in flagged]
    outside = [r for r in cohort if (r.get(dim) or "").strip() not in flagged]
    if not inside or not outside:
        return {}
    rate = lambda rs: sum(1 for r in rs if left_in_band(r, band)) / len(rs)
    raw_diff = rate(inside) - rate(outside)

    keyed = {c: (lambda r, c=c: (r.get(c) or "").strip())
             for c in confounders if c != dim}
    keyed.update(derived or {})

    results = {}
    for conf, keyfn in keyed.items():
        strata = defaultdict(lambda: ([], []))
        for row in cohort:
            key = keyfn(row)
            if not key:
                continue
            strata[key][0 if (row.get(dim) or "").strip() in flagged else 1].append(row)
        weighted = weight = used = 0
        for key, (a, b) in strata.items():
            if len(a) < MIN_SEG or len(b) < MIN_SEG:
                continue
            weighted += (rate(a) - rate(b)) * (len(a) + len(b))
            weight += len(a) + len(b)
            used += 1
        if not weight or used < 2 or not raw_diff:
            results[conf] = {"testable": False,
                             "reason": "not enough strata with both groups present"}
            continue
        adjusted = weighted / weight
        results[conf] = {
            "testable": True, "strata_used": used,
            "raw_excess_points": round(raw_diff, 4),
            "adjusted_excess_points": round(adjusted, 4),
            "retained": round(adjusted / raw_diff, 3),
            "survived": bool(abs(adjusted) >= abs(raw_diff) * KILL_FRACTION),
        }
    return results


def pass3_confounds(hires, bands, segments, as_of):
    band_by_name = {b["name"]: b for b in bands}
    out = []
    for block in segments:
        band = band_by_name[block["band"]]
        cohort = cohort_for(hires, band, as_of)

        # Individual managers rarely carry thirty hires in both groups, so
        # stratifying on hiring_manager_id silently returns "not testable" and
        # a role effect that is really a manager effect walks through
        # unchallenged. The group the engine has just identified does carry
        # the volume, so that is what every other dimension is tested against.
        mgr_block = block["by"].get("hiring_manager_id")
        weak = {f["segment"] for f in mgr_block["flagged"]} if mgr_block else set()

        for dim, data in block["by"].items():
            if not data["flagged"]:
                continue
            names = [f["segment"] for f in data["flagged"]]
            derived = {}
            if weak and dim != "hiring_manager_id":
                derived["manager group"] = lambda r: (
                    "above-baseline"
                    if (r.get("hiring_manager_id") or "").strip() in weak
                    else "baseline")
            checks = confound_check(cohort, band, dim, names, SEGMENT_DIMS, derived)
            testable = [c for c in checks.values() if c.get("testable")]
            out.append({
                "band": block["band"], "label": block["label"], "dimension": dim,
                "segments": names[:12], "segment_count": len(names),
                "checks": checks,
                "survives_all": bool(testable) and all(c["survived"] for c in testable),
                "killed_by": [k for k, c in checks.items()
                              if c.get("testable") and not c["survived"]],
            })
    return out


# --------------------------------------------------------------- pass 4

def pass4_band_contrast(hires, bands, confirmed, as_of):
    """The pass the whole skill is built around.

    Take the segments that carry attrition in the first band and ask what they
    do in the next one. If the gap disappears, the people who were going to
    leave have already left, and what you are looking at is a hiring and
    first-month problem: who you selected, what you told them, what their first
    week was like. If the gap persists, the same segments keep losing people
    who already survived a month, and that is the job itself - pay, schedule,
    supervision. The two have different owners, and a single turnover
    percentage reports neither."""
    band_by_name = {b["name"]: b for b in bands}
    early = BANDS[0]["name"]
    later = [b["name"] for b in BANDS[1:]]
    out = []
    for finding in confirmed:
        if finding["band"] != early:
            continue
        dim, names = finding["dimension"], set(finding["segments"])
        row = {"dimension": dim, "segments": sorted(names)[:12],
               "early_band": early, "bands": {}}
        for name in [early] + later:
            band = band_by_name.get(name)
            if not band or not band["conclusive"]:
                continue
            cohort = cohort_for(hires, band, as_of)
            inside = [r for r in cohort if (r.get(dim) or "").strip() in names]
            outside = [r for r in cohort if (r.get(dim) or "").strip() not in names]
            if len(inside) < MIN_SEG or len(outside) < MIN_SEG:
                continue
            a = sum(1 for r in inside if left_in_band(r, band)) / len(inside)
            b = sum(1 for r in outside if left_in_band(r, band)) / len(outside)
            row["bands"][name] = {
                "flagged": rate_block(sum(1 for r in inside if left_in_band(r, band)), len(inside)),
                "rest": rate_block(sum(1 for r in outside if left_in_band(r, band)), len(outside)),
                "excess_points": round(a - b, 4),
            }
        first = row["bands"].get(early, {}).get("excess_points")
        after = [v["excess_points"] for k, v in row["bands"].items() if k != early]
        if first is None or not after:
            continue
        worst_after = max(after)
        row["persists"] = bool(worst_after >= first * KILL_FRACTION)
        row["early_excess_points"] = first
        row["later_excess_points"] = round(worst_after, 4)
        row["verdict"] = "job" if row["persists"] else "hiring_and_first_month"
        row["reads"] = (
            (f"These {dim} values lose {first:.1%} more people in the {BANDS[0]['label']} "
             f"than the rest, and {worst_after:+.1%} thereafter. The gap does not "
             "persist past the first month, so this is a hiring and first-month "
             "problem - selection, expectation-setting, the first week - not the job.")
            if not row["persists"] else
            (f"These {dim} values lose {first:.1%} more people in the "
             f"{BANDS[0]['label']} and {worst_after:.1%} more afterwards too. The gap "
             "persists past the first month, so it is the job - pay, schedule, "
             "supervision - not only who was hired."))
        out.append(row)
    return out


# --------------------------------------------------------------- pass 5

def exit_reason_test(cohort, band, dim, names, rng):
    """Do the flagged segments leave for different stated reasons?

    A permutation test, because the honest answer is usually no and the naive
    comparison will not say so. With five reason categories and a few hundred
    leavers, two random halves of the same population routinely differ by ten
    points on some category, so 'attendance is 11% here and 18% there' means
    nothing until you know what chance produces. Labels are reshuffled a
    fixed number of times, seeded, and the observed distance is placed against
    that null."""
    leavers = [r for r in cohort if left_in_band(r, band)
               and (r.get("separation_reason") or "").strip()]
    inside = [r for r in leavers if (r.get(dim) or "").strip() in names]
    if len(inside) < MIN_SEG or len(leavers) - len(inside) < MIN_SEG:
        return {"testable": False, "reason": "too few leavers with a stated reason"}

    reasons = sorted({(r.get("separation_reason") or "").strip() for r in leavers})

    def tvd(group_a, group_b):
        ca, cb = Counter(), Counter()
        for r in group_a:
            ca[(r.get("separation_reason") or "").strip()] += 1
        for r in group_b:
            cb[(r.get("separation_reason") or "").strip()] += 1
        na, nb = len(group_a), len(group_b)
        return 0.5 * sum(abs(ca[x] / na - cb[x] / nb) for x in reasons)

    outside = [r for r in leavers if (r.get(dim) or "").strip() not in names]
    observed = tvd(inside, outside)

    pool = list(leavers)
    k = len(inside)
    null = []
    for _ in range(PERMUTATIONS):
        rng.shuffle(pool)
        null.append(tvd(pool[:k], pool[k:]))
    null.sort()
    beat = sum(1 for v in null if v < observed)
    percentile = beat / len(null)
    return {
        "testable": True, "leavers_tested": len(leavers),
        "reasons": reasons,
        "observed_distance": round(observed, 4),
        "null_median": round(null[len(null) // 2], 4),
        "null_95th": round(null[int(len(null) * 0.95)], 4),
        "percentile": round(percentile, 4),
        "permutations": PERMUTATIONS,
        "discriminates": bool(percentile >= DISCRIM_PCTL),
        "mix": {
            "flagged": {x: round(sum(1 for r in inside
                                     if (r.get("separation_reason") or "").strip() == x)
                                 / len(inside), 3) for x in reasons},
            "rest": {x: round(sum(1 for r in outside
                                  if (r.get("separation_reason") or "").strip() == x)
                              / len(outside), 3) for x in reasons},
        },
    }


def pass5_exit_reasons(hires, bands, confirmed, as_of):
    if not any("separation_reason" in (r or {}) for r in hires[:1]):
        return {"available": False,
                "reason": "no separation_reason column in this export"}
    rng = random.Random(PERM_SEED)
    band_by_name = {b["name"]: b for b in bands}
    tests = []
    for finding in confirmed:
        band = band_by_name.get(finding["band"])
        if not band:
            continue
        cohort = cohort_for(hires, band, as_of)
        result = exit_reason_test(cohort, band, finding["dimension"],
                                  set(finding["segments"]), rng)
        result.update({"band": finding["band"], "dimension": finding["dimension"]})
        tests.append(result)
    testable = [t for t in tests if t.get("testable")]
    return {
        "available": True, "tests": tests,
        "any_discriminates": any(t["discriminates"] for t in testable),
        "reads": ("No flagged segment's stated exit reasons differ from everyone "
                  "else's by more than chance produces. Exit reasons will not tell "
                  "you which segment is the problem, and a programme built on the "
                  "reason mix would be built on noise."
                  if testable and not any(t["discriminates"] for t in testable)
                  else "At least one flagged segment leaves for a measurably "
                       "different mix of stated reasons."),
    }


# --------------------------------------------------------------- pass 6

def pass6_size(hires, bands, confirmed, as_of):
    """Hires lost to the excess, at baseline parity. Stated as people, because
    a percentage of a segment is not a number anybody can staff against."""
    band_by_name = {b["name"]: b for b in bands}
    out = []
    for finding in confirmed:
        band = band_by_name.get(finding["band"])
        if not band:
            continue
        cohort = cohort_for(hires, band, as_of)
        names = set(finding["segments"])
        inside = [r for r in cohort if (r.get(finding["dimension"]) or "").strip() in names]
        adjusted = [c["adjusted_excess_points"] for c in finding["checks"].values()
                    if c.get("testable")]
        if not adjusted or not inside:
            continue
        excess = min(adjusted)
        if excess <= 0:
            continue
        out.append({
            "band": finding["band"], "label": finding["label"],
            "dimension": finding["dimension"],
            "segments": sorted(names)[:12], "segment_count": len(names),
            "cohort": len(inside),
            "excess_points": round(excess, 4),
            "people_lost_to_excess": int(round(excess * len(inside))),
            "reads": (f"{len(names)} {finding['dimension']} value(s) lose "
                      f"{excess:.1%} more of their hires in the {finding['label']} "
                      f"than the rest. Across {len(inside):,} hires in that cohort "
                      f"that is about {int(round(excess * len(inside))):,} people."),
        })
    out.sort(key=lambda p: -p["people_lost_to_excess"])
    return out


# --------------------------------------------------------------- assembly

def collapse_collinear(items, collinear):
    """Report a finding once, naming the columns it could equally be read on.

    Without this, a file where one manager runs one site reports the same
    forty-eight lost hires twice and the reader double-counts the prize."""
    alias = {}
    for pair in collinear:
        a, b = pair["dimensions"]
        keep = SEGMENT_DIMS.index(a) < SEGMENT_DIMS.index(b) and a or b
        drop = b if keep == a else a
        alias.setdefault(drop, keep)

    kept, seen = [], {}
    for item in items:
        dim = item.get("dimension")
        primary = alias.get(dim, dim)
        signature = (item.get("band"), primary, tuple(sorted(item.get("segments") or [])))
        if dim != primary:
            # Same finding read on the other column; fold it into the one kept.
            existing = seen.get((item.get("band"), primary))
            if existing is not None:
                existing.setdefault("also_reads_as", []).append(dim)
                continue
        seen[(item.get("band"), primary)] = item
        kept.append(item)
    return kept


def analyse(path):
    columns, rows, hires = load(path)
    as_of = observation_end(rows)
    if as_of is None:
        raise Refusal("No usable dates anywhere in this file.")

    first = BANDS[0]
    eligible_share = len(cohort_for(hires, first, as_of)) / len(hires)
    if eligible_share < MIN_ELIGIBLE:
        raise Refusal(
            f"Only {eligible_share:.0%} of the hires in this file were hired more "
            f"than {first['hi']} days before it closes, so most of them could not "
            f"yet have been recorded as leaving in the {first['label']}. A rate over "
            "that population understates itself by however much you have been hiring "
            "lately. Export a window that ends at least a quarter before today.")

    bands = pass1_bands(hires, as_of)
    segments = pass2_segments(hires, bands, as_of)
    collinear = collinear_dimensions(hires)
    confounds = pass3_confounds(hires, bands, segments, as_of)
    confirmed = [c for c in confounds if c["survives_all"]]
    contrast = collapse_collinear(
        pass4_band_contrast(hires, bands, confirmed, as_of), collinear)
    reasons = pass5_exit_reasons(hires, bands, confirmed, as_of)
    prizes = collapse_collinear(pass6_size(hires, bands, confirmed, as_of), collinear)

    verdicts = {c["verdict"] for c in contrast}
    return {
        "meta": {
            "skill": "turnover-analyst",
            "skill_version": SKILL_VERSION,
            "funnel_profile": PROFILE_NAME,
            "hires_analysed": len(hires),
            "rows_in_file": len(rows),
            "observation_end": as_of.isoformat(),
            "source_file": os.path.basename(path),
        },
        "headline": {
            "bands": {b["name"]: b["cohort"]["rate"] for b in bands if b["conclusive"]},
            "where_the_structure_is": [b["band"] for b in segments if b["any_structure"]],
            "verdict": ("hiring_and_first_month" if verdicts == {"hiring_and_first_month"}
                        else "job" if verdicts == {"job"}
                        else "mixed" if verdicts else "no_confirmed_structure"),
            "exit_reasons_discriminate": reasons.get("any_discriminates"),
        },
        "bands": bands,
        "segments": segments,
        "collinear_dimensions": collinear,
        "confounds": confounds,
        "band_contrast": contrast,
        "exit_reasons": reasons,
        "prizes": prizes,
        "discarded": [
            {"band": c["band"], "dimension": c["dimension"], "segments": c["segments"],
             "killed_by": c["killed_by"],
             "reads": (f"Higher {c['label']} attrition for these {c['dimension']} "
                       f"values did not survive holding {', '.join(c['killed_by'])} "
                       f"constant, so it is reported as explained by "
                       f"{', '.join(c['killed_by'])} rather than as a "
                       f"{c['dimension']} problem.")}
            for c in confounds if not c["survives_all"] and c["killed_by"]
        ],
    }


# --------------------------------------------------------------- test suite

def _find_sample():
    candidates = [
        os.path.join(SKILL_DIR, "data", "frontline_pipeline_sample.csv"),
        os.path.join(HERE, "..", "..", "..", "..", "data", "frontline_pipeline_sample.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return os.path.abspath(candidates[0])


SAMPLE = _find_sample()

# P5: five managers carry ~3x baseline 30-day attrition, and their sites skew
# to one role. SCARCE_SITES is the P2 scheduling-capacity group, which has no
# attrition component at all -- it is here as a negative control, because a
# turnover engine that flags it is flagging a queue.
WEAK_MANAGERS = {"MGR-004", "MGR-012", "MGR-021", "MGR-029", "MGR-038"}
SCARCE_SITES = {"LOC-03", "LOC-07", "LOC-14", "LOC-19", "LOC-25", "LOC-31", "LOC-36", "LOC-40"}


class Checks:
    def __init__(self):
        self.passed, self.failed = [], []

    def ok(self, label, condition, detail=""):
        (self.passed if condition else self.failed).append((label, detail))
        print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def datasets():
    here = os.path.dirname(SAMPLE)
    found = [SAMPLE]
    for name in ("qsr", "logistics", "gig"):
        path = os.path.join(here, f"{name}_pipeline_sample.csv")
        if os.path.exists(path):
            found.append(path)
    return found


def band_named(report, name):
    return next((b for b in report["bands"] if b["name"] == name), None)


def flagged_in(report, band_name, dim):
    for block in report["segments"]:
        if block["band"] == band_name and dim in block["by"]:
            return {f["segment"] for f in block["by"][dim]["flagged"]}
    return set()


EARLY = BANDS[0]["name"]
LATER = BANDS[1]["name"]


def run_suite(sample):
    report = analyse(sample)
    c = Checks()
    print(f"\nProfile: {report['meta']['funnel_profile']}  "
          f"hires={report['meta']['hires_analysed']:,}  "
          f"as of {report['meta']['observation_end']}")

    print("\nA  The five weak managers are found in the first month")
    mgrs = flagged_in(report, EARLY, "hiring_manager_id")
    c.ok("at least four of the five weak managers flagged",
         len(mgrs & WEAK_MANAGERS) >= 4, f"found {len(mgrs & WEAK_MANAGERS)}/5")
    c.ok("no manager flagged who was not planted weak",
         not (mgrs - WEAK_MANAGERS), ",".join(sorted(mgrs - WEAK_MANAGERS)) or "none")

    print("\nB  The manager effect survives the role it is entangled with")
    mgr_finding = next((f for f in report["confounds"]
                        if f["band"] == EARLY and f["dimension"] == "hiring_manager_id"), None)
    c.ok("a manager finding was raised", bool(mgr_finding))
    if mgr_finding:
        role_check = mgr_finding["checks"].get("role", {})
        c.ok("it was testable against role", role_check.get("testable", False),
             role_check.get("reason", ""))
        c.ok("it survived within role", role_check.get("survived", False),
             f"retained {role_check.get('retained')}")
        c.ok("it survived every confound it could be tested against",
             mgr_finding["survives_all"],
             "killed by " + ",".join(mgr_finding["killed_by"]) if mgr_finding["killed_by"] else "survived")

    print("\nC  The role effect collapses inside the manager group")
    # The trap. Those managers sit on sites heavy in one role, so a naive role
    # cut inherits most of the manager gap. Held constant, it should lose most
    # of it -- and the engine must report the role as explained, not as a
    # finding of its own.
    # The generator plants a real but small role penalty on top of the large
    # manager one, so the correct outcome is not that the role effect vanishes
    # -- it is that it loses far more of itself to the manager than the
    # manager loses to it. Asserting the comparison rather than a threshold on
    # either one is what makes this a test of the confound machinery and not a
    # memory of one file's arithmetic.
    role_finding = next((f for f in report["confounds"]
                         if f["band"] == EARLY and f["dimension"] == "role"), None)
    if role_finding and mgr_finding:
        role_vs_mgr = role_finding["checks"].get("manager group", {})
        mgr_vs_role = mgr_finding["checks"].get("role", {})
        c.ok("the role finding was tested against the manager group",
             role_vs_mgr.get("testable", False), role_vs_mgr.get("reason", ""))
        if role_vs_mgr.get("testable") and mgr_vs_role.get("testable"):
            c.ok("the role effect loses more to the manager than the manager loses to the role",
                 role_vs_mgr["retained"] < mgr_vs_role["retained"],
                 f"role keeps {role_vs_mgr['retained']}, manager keeps {mgr_vs_role['retained']}")
            c.ok("the manager keeps most of its effect within role",
                 mgr_vs_role["retained"] >= 0.7, str(mgr_vs_role["retained"]))
    else:
        c.ok("no standalone role finding was raised", role_finding is None,
             "role never flagged")

    print("\nD  All of it is a first-month problem, and the engine says so")
    early, later = band_named(report, EARLY), band_named(report, LATER)
    c.ok("the first-month band carries segment structure",
         any(b["band"] == EARLY and b["any_structure"] for b in report["segments"]))
    # Not "the later band is empty". Screening eighty segments in a band where
    # nothing is planted will occasionally return one, and a suite that
    # demanded zero would be asserting that a statistical procedure never has
    # a bad day. What the planted data does guarantee is that none of the five
    # managers is among whatever turns up, and that the later band carries far
    # less than the first.
    later_mgrs = flagged_in(report, LATER, "hiring_manager_id")
    c.ok("no weak manager reappears in the 31-90 band",
         not (later_mgrs & WEAK_MANAGERS),
         ",".join(sorted(later_mgrs & WEAK_MANAGERS)) or "none")
    count = lambda name: sum(len(d["flagged"]) for b in report["segments"]
                             if b["band"] == name for d in b["by"].values())
    c.ok("the first month carries more structure than the 31-90 band",
         count(EARLY) > count(LATER), f"{count(EARLY)} vs {count(LATER)}")
    contrast = report["band_contrast"]
    c.ok("a band contrast was computed", bool(contrast))
    if contrast:
        mgr_contrast = next((x for x in contrast if x["dimension"] == "hiring_manager_id"), None)
        c.ok("the manager gap does not persist past the first month",
             mgr_contrast is not None and not mgr_contrast["persists"],
             f"early {mgr_contrast['early_excess_points']:+.3f} vs later "
             f"{mgr_contrast['later_excess_points']:+.3f}" if mgr_contrast else "no contrast")
        c.ok("the verdict is a hiring and first-month problem",
             report["headline"]["verdict"] == "hiring_and_first_month",
             report["headline"]["verdict"])

    print("\nE  The scheduling-capacity sites are not reported as a turnover problem")
    sites = flagged_in(report, EARLY, "location_id")
    c.ok("the scarce-slot sites are not flagged for attrition",
         len(sites & SCARCE_SITES) <= 2, f"{len(sites & SCARCE_SITES)}/8 flagged")

    print("\nF  Exit reasons are tested against chance, and do not discriminate")
    er = report["exit_reasons"]
    c.ok("the exit-reason column was found and tested", er.get("available", False))
    testable = [t for t in er.get("tests", []) if t.get("testable")]
    c.ok("at least one permutation test ran", bool(testable),
         f"{len(testable)} test(s)")
    if testable:
        t = testable[0]
        c.ok("the observed mix is within what reshuffling produces",
             not t["discriminates"],
             f"observed {t['observed_distance']} vs null 95th {t['null_95th']}, "
             f"pctl {t['percentile']}")
        c.ok("the report says exit reasons will not identify the segment",
             er["any_discriminates"] is False)

    print("\nG  Cohorts, not raw denominators")
    # The correction that makes the bands comparable. The 90-day band must
    # exclude materially more people than the 30-day one, because fewer hires
    # have had ninety days to leave -- and the naive rate must be lower.
    c.ok("every band reports its eligible cohort share",
         all(b["eligible_share"] is not None for b in report["bands"]))
    later_band = band_named(report, LATER)
    c.ok("the later band excludes more people than the first",
         later_band["excluded_too_recent"] > early["excluded_too_recent"],
         f"{later_band['excluded_too_recent']:,} vs {early['excluded_too_recent']:,}")
    c.ok("the naive first-month rate understates the cohort rate",
         early["understated_by"] is not None and early["understated_by"] > 0,
         f"{early['naive_rate']:.3f} naive vs {early['cohort']['rate']:.3f} cohort")

    print("\nH  Sizing is in people, from the adjusted excess")
    c.ok("at least one prize is reported", bool(report["prizes"]))
    if report["prizes"]:
        p = report["prizes"][0]
        c.ok("it is sized in people, not percentages", p["people_lost_to_excess"] > 0,
             f"{p['people_lost_to_excess']:,} people")
        c.ok("it uses the confound-adjusted excess, not the raw gap",
             p["excess_points"] <= max(
                 f["checks"]["role"]["raw_excess_points"]
                 for f in report["confounds"]
                 if f["dimension"] == p["dimension"] and f["checks"].get("role", {}).get("testable")),
             f"{p['excess_points']}")

    print(f"\n  {len(c.passed)} passed, {len(c.failed)} failed")
    return len(c.passed), len(c.failed)


# ------------------------------------------------------------ refusal tests

def _tmp_csv(rows, columns):
    import tempfile
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    fh.close()
    return fh.name


def _read_sample():
    with open(SAMPLE, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames), list(reader)


def refusal_tests():
    print(f"\n{'=' * 62}\nrefusals\n{'=' * 62}")
    c = Checks()
    columns, rows = _read_sample()

    path = _tmp_csv([dict(r, candidate_name="A B") for r in rows],
                    columns + ["candidate_name"])
    try:
        analyse(path); c.ok("refuses a nominative column", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a nominative column", "nominative" in str(stop).lower())
    os.unlink(path)

    keep = [c2 for c2 in columns if c2 != "tenure_days"]
    path = _tmp_csv(rows, keep)
    try:
        analyse(path); c.ok("refuses a file with no tenure column", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file with no tenure column", "tenure_days" in str(stop))
    os.unlink(path)

    keep = [c2 for c2 in columns if c2 != "first_shift_at"]
    path = _tmp_csv(rows, keep)
    try:
        analyse(path); c.ok("refuses a file with no start date", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file with no start date", "first_shift_at" in str(stop))
    os.unlink(path)

    # An export cut too close to today: shift every start date forward so almost
    # nobody has had thirty days to leave.
    fresh = []
    for row in rows:
        row = dict(row)
        started = parse_date(row.get("first_shift_at"))
        if started:
            row["first_shift_at"] = "2026-09-20"
        fresh.append(row)
    path = _tmp_csv(fresh, columns)
    try:
        analyse(path); c.ok("refuses an export cut too close to today", False, "it ran")
    except Refusal as stop:
        c.ok("refuses an export cut too close to today", "days before it closes" in str(stop))
    os.unlink(path)

    thin = [r for r in rows if (r.get("stage_reached") or "") != "started"][:600]
    path = _tmp_csv(thin, columns)
    try:
        analyse(path); c.ok("refuses a file with too few actual hires", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file with too few actual hires", "reached" in str(stop))
    os.unlink(path)

    print(f"\n  {len(c.passed)} passed, {len(c.failed)} failed")
    return len(c.passed), len(c.failed)


def run_tests():
    if not os.path.exists(SAMPLE):
        print(f"sample dataset not found at {SAMPLE}")
        return 1
    print(f"turnover-analyst v{SKILL_VERSION}")
    print("Ground truth is P5 (five managers, entangled with role) from")
    print("data/generate.py, plus two negative controls: the 31-90 band, where")
    print("nothing is planted, and the P2 scheduling sites, which are a queue.")

    total_p = total_f = 0
    for path in datasets():
        print(f"\n{'=' * 62}\n{os.path.basename(path)}\n{'=' * 62}")
        p, f = run_suite(path)
        total_p += p; total_f += f
    p, f = refusal_tests()
    total_p += p; total_f += f
    print(f"\n{'=' * 62}")
    print(f"{total_p} passed, {total_f} failed  ({len(datasets())} dataset(s) + refusals)")
    return 1 if total_f else 0


def main():
    ap = argparse.ArgumentParser(description="Turnover engine.")
    ap.add_argument("--input", help="CSV mapped to the canonical schema")
    ap.add_argument("--out", help="write the JSON report here instead of stdout")
    ap.add_argument("--test", action="store_true", help="run the regression suite")
    args = ap.parse_args()

    if args.test:
        return run_tests()
    if not args.input:
        ap.error("one of --input or --test is required")

    try:
        report = analyse(args.input)
    except Refusal as stop:
        print(json.dumps({"refused": True, "reason": str(stop)}, indent=2))
        return 2

    text = json.dumps(report, indent=2, default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"report written to {args.out}  ({report['meta']['hires_analysed']:,} hires, "
              f"skill v{SKILL_VERSION})")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
