#!/usr/bin/env python3
"""
Funnel drop-off engine.

Deterministic analysis of a frontline hiring funnel export. Standard library
only - no pandas, no numpy, no network. The same input always produces the
same output, which is the point: the statistics in this skill are computed
here, not improvised in prose.

    analyze.py --input export.csv [--out report.json]
    analyze.py --test

The input must be mapped to the canonical schema in
references/schema.json. Every data lane - a CSV export, an MCP, anything -
maps into that schema first; this file reads nothing else.

What it refuses to do:
  - analyse a file carrying nominative columns (it stops and asks for a
    re-export)
  - report a finding from a segment too small to support one
  - present a correlation that did not survive its confound check
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(SKILL_DIR, "references", "schema.json")

with open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

STAGES = SCHEMA["stages"]
STAGE_IX = {s: i for i, s in enumerate(STAGES)}
MECHANISMS = SCHEMA["exit_reason_mechanisms"]
REASON_MECHANISM = {r: m for m, rs in MECHANISMS.items() for r in rs}
TH = SCHEMA["thresholds"]

MIN_ROWS = TH["min_rows_total"]
MIN_AT_STAGE = TH["min_rows_at_stage"]
MIN_SEG = TH["min_segment_volume"]
FLAG_RATIO = TH["flag_ratio"]
KILL_FRACTION = TH["confound_kill_fraction"]
Z = TH["wilson_z"]

# Timestamp column that marks arrival at each stage, index-aligned to STAGES.
STAGE_DATE = [
    "applied_at",
    "screened_at",
    "interview_scheduled_at",
    "interview_completed_at",
    "offer_at",
    "onboarding_started_at",
    "first_shift_at",
]

SEGMENT_DIMS = ["region", "location_id", "source", "role", "availability_match"]


class Refusal(Exception):
    """Raised when the engine will not analyse the input. Not an error."""


# --------------------------------------------------------------- primitives

def wilson(k, n, z=Z):
    """95% score interval. Returns (lo, hi) or (None, None) for an empty set."""
    if not n:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom))


def rate_block(k, n):
    """A rate with its interval and volume, or an explicit inconclusive."""
    if not n:
        return {"n": 0, "k": 0, "rate": None, "ci": [None, None], "conclusive": False}
    lo, hi = wilson(k, n)
    return {
        "n": n,
        "k": k,
        "rate": round(k / n, 4),
        "ci": [round(lo, 4), round(hi, 4)],
        "conclusive": n >= MIN_SEG,
    }


def parse_date(value):
    if not value:
        return None
    try:
        parts = value.strip()[:10].split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def median(values):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    mid = len(vals) // 2
    if len(vals) % 2:
        return float(vals[mid])
    return (vals[mid - 1] + vals[mid]) / 2.0


def stage_ix(row):
    return STAGE_IX.get((row.get("stage_reached") or "").strip())


# --------------------------------------------------------------- ingest

def check_columns(columns):
    """Stop on anything nominative. Conservative by design."""
    banned = set(SCHEMA["refuses"]["nominative_columns"])
    banned_tokens = {b for b in banned if "_" not in b}
    offenders = []
    for col in columns:
        norm = col.strip().lower()
        tokens = set(t for t in norm.replace("-", "_").replace(" ", "_").split("_") if t)
        if norm in banned or (tokens & banned_tokens):
            offenders.append(col)
    if offenders:
        raise Refusal(
            "This export carries columns that look nominative: "
            + ", ".join(sorted(offenders))
            + ". Re-export without them - drop or hash names, emails, phone numbers, "
            "addresses, dates of birth and free-text notes, and send a commute band "
            "instead of an address. Nothing in this analysis needs to know who "
            "anybody is."
        )


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        columns = list(reader.fieldnames or [])
        rows = [r for r in reader]
    if not columns:
        raise Refusal("That file has no header row.")
    check_columns(columns)

    missing_required = [
        c for c, spec in SCHEMA["columns"].items()
        if spec.get("required") and c not in columns
    ]
    if missing_required:
        raise Refusal(
            "Missing required columns: " + ", ".join(missing_required)
            + ". Without them there is no funnel to analyse."
        )

    kept = [r for r in rows if stage_ix(r) is not None]
    dropped = len(rows) - len(kept)
    if len(kept) < MIN_ROWS:
        raise Refusal(
            f"Only {len(kept):,} usable rows. Below {MIN_ROWS:,} this analysis "
            "reports noise as if it were signal, so it will not run. Export a "
            "longer period rather than accepting a thin answer."
        )
    return columns, kept, dropped


def coverage_report(columns, rows):
    """Which optional columns are absent, and what that costs."""
    present, absent = [], []
    for col, spec in SCHEMA["columns"].items():
        if col not in columns:
            if not spec.get("required"):
                absent.append({"column": col, "cost": spec.get("unlocks", "")})
            continue
        filled = sum(1 for r in rows if (r.get(col) or "").strip())
        entry = {"column": col, "filled": filled, "fill_rate": round(filled / len(rows), 3)}
        if filled == 0:
            absent.append({"column": col, "cost": spec.get("unlocks", "") + " (column present but empty)"})
        else:
            present.append(entry)
    return {"present": present, "absent": absent}


# --------------------------------------------------------------- pass 1

def pass1_funnel(rows):
    """Reached, step conversion, reach rate and - the number we rank on -
    absolute loss at every step."""
    total = len(rows)
    reached = [sum(1 for r in rows if stage_ix(r) >= i) for i in range(len(STAGES))]

    steps = []
    for i in range(len(STAGES) - 1):
        n, adv = reached[i], reached[i + 1]
        steps.append({
            "step": f"{STAGES[i]} -> {STAGES[i + 1]}",
            "from_stage": STAGES[i],
            "to_stage": STAGES[i + 1],
            "index": i,
            "reached": n,
            "advanced": adv,
            "absolute_loss": n - adv,
            "conversion": rate_block(adv, n),
            "reach_rate": round(n / total, 4) if total else None,
        })
    return {
        "total_applications": total,
        "reached": {STAGES[i]: reached[i] for i in range(len(STAGES))},
        "steps": steps,
    }


# --------------------------------------------------------------- pass 2

def pass2_localise(rows, funnel):
    """For each material loss, is it spread evenly or carried by a minority
    of segments? Concentrated losses are cheaper to fix."""
    out = []
    for step in funnel["steps"]:
        i = step["index"]
        at_stage = [r for r in rows if stage_ix(r) >= i]
        if len(at_stage) < MIN_AT_STAGE or step["absolute_loss"] == 0:
            continue
        pop_rate = step["conversion"]["rate"]
        if not pop_rate:
            continue

        dims = {}
        for dim in SEGMENT_DIMS:
            groups = defaultdict(list)
            for r in at_stage:
                key = (r.get(dim) or "").strip()
                if key:
                    groups[key].append(r)
            if len(groups) < 2:
                continue

            segments, inconclusive = [], 0
            for key, bucket in sorted(groups.items()):
                n = len(bucket)
                adv = sum(1 for r in bucket if stage_ix(r) >= i + 1)
                if n < MIN_SEG:
                    inconclusive += 1
                    continue
                seg_rate = adv / n
                segments.append({
                    "segment": key,
                    "conversion": rate_block(adv, n),
                    "loss": n - adv,
                    "ratio_to_population": round(pop_rate / seg_rate, 2) if seg_rate else None,
                    "underperforming": bool(seg_rate and pop_rate / seg_rate >= FLAG_RATIO),
                })
            if not segments:
                continue

            flagged = [s for s in segments if s["underperforming"]]
            flagged_loss = sum(s["loss"] for s in flagged)
            dims[dim] = {
                "segments_tested": len(segments),
                "segments_below_volume": inconclusive,
                "flagged": sorted(flagged, key=lambda s: -s["loss"]),
                "loss_carried_by_flagged": flagged_loss,
                "share_of_step_loss": round(flagged_loss / step["absolute_loss"], 3)
                if step["absolute_loss"] else None,
                "shape": "concentrated" if flagged and flagged_loss / step["absolute_loss"] >= 0.30
                         else "systemic",
            }

        if dims:
            out.append({"step": step["step"], "index": i,
                        "absolute_loss": step["absolute_loss"], "by": dims})
    return out


# --------------------------------------------------------------- pass 3

def classify(stoppers, advancers, index, conversion_rate):
    """Classify one loss. Works on the whole step or on a single segment -
    which matters, because a step can be candidate-driven overall while the
    segment carrying the loss is plainly capacity-driven."""
    reasons = Counter((r.get("exit_reason") or "").strip() for r in stoppers)
    reasons.pop("", None)
    mech = Counter()
    for reason, count in reasons.items():
        mech[REASON_MECHANISM.get(reason, "unclassified")] += count

    wait = None
    if index + 1 < len(STAGE_DATE):
        gaps = []
        for r in advancers:
            a = parse_date(r.get(STAGE_DATE[index]))
            b = parse_date(r.get(STAGE_DATE[index + 1]))
            if a and b:
                gaps.append((b - a).days)
        wait = median(gaps)

    labelled = sum(reasons.values())
    dominant, share = None, None
    if mech:
        dominant, count = mech.most_common(1)[0]
        share = round(count / labelled, 3) if labelled else None

    # A slow step that converts badly is capacity, whatever the labels say.
    if wait is not None and wait >= 5 and conversion_rate and conversion_rate < 0.6 \
            and dominant != "rule":
        dominant = "capacity"

    return {
        "mechanism": dominant,
        "mechanism_share": share,
        "labelled_exits": labelled,
        "unlabelled_exits": len(stoppers) - labelled,
        "top_reasons": reasons.most_common(4),
        "median_wait_days": wait,
    }


def pass3_mechanism(rows, funnel):
    """Population-level mechanism per step. Findings are re-classified
    within their own segment during assembly."""
    out = {}
    for step in funnel["steps"]:
        i = step["index"]
        stoppers = [r for r in rows if stage_ix(r) == i]
        if not stoppers:
            continue
        advancers = [r for r in rows if stage_ix(r) >= i + 1]
        out[step["step"]] = classify(stoppers, advancers, i, step["conversion"]["rate"])
    return out


# --------------------------------------------------------------- pass 4

def _split_rate(rows, split_fn, outcome_fn):
    inside = [r for r in rows if split_fn(r)]
    outside = [r for r in rows if not split_fn(r)]
    if len(inside) < MIN_SEG or len(outside) < MIN_SEG:
        return None
    ki = sum(1 for r in inside if outcome_fn(r))
    ko = sum(1 for r in outside if outcome_fn(r))
    return {
        "difference": ki / len(inside) - ko / len(outside),
        "inside": rate_block(ki, len(inside)),
        "outside": rate_block(ko, len(outside)),
    }


def stratified(rows, split_fn, outcome_fn, strat_fn):
    """The same comparison, held within each level of a confounder, then
    volume-weighted back together."""
    buckets = defaultdict(list)
    for r in rows:
        key = strat_fn(r)
        if key:
            buckets[key].append(r)

    weighted, weight, used = 0.0, 0.0, 0
    for bucket in buckets.values():
        res = _split_rate(bucket, split_fn, outcome_fn)
        if res is None:
            continue
        w = res["inside"]["n"] + res["outside"]["n"]
        weighted += res["difference"] * w
        weight += w
        used += 1
    if used < 2 or weight == 0:
        return None
    return {"difference": weighted / weight, "strata_used": used}


def confound_check(rows, label, split_fn, outcome_fn, confounders):
    """Crude effect, then the same effect within each confounder. If it
    does not survive, it is a passenger and is reported as ruled out."""
    crude = _split_rate(rows, split_fn, outcome_fn)
    if crude is None:
        return {"effect": label, "verdict": "inconclusive",
                "why": "not enough volume on one side of the comparison"}

    tests, killers = [], []
    for name, strat_fn in confounders.items():
        strat = stratified(rows, split_fn, outcome_fn, strat_fn)
        if strat is None:
            tests.append({"held_constant": name, "result": "could not test",
                          "why": "too few strata with volume on both sides"})
            continue
        retained = abs(strat["difference"]) / abs(crude["difference"]) if crude["difference"] else 0.0
        flipped = (strat["difference"] * crude["difference"]) < 0
        killed = flipped or retained < KILL_FRACTION
        if killed:
            killers.append(name)
        tests.append({
            "held_constant": name,
            "crude_difference": round(crude["difference"], 4),
            "stratified_difference": round(strat["difference"], 4),
            "effect_retained": round(retained, 3),
            "strata_used": strat["strata_used"],
            "result": "killed" if killed else "survived",
        })

    return {
        "effect": label,
        "verdict": "ruled_out" if killers else "survived",
        "killed_by": killers,
        "crude": {"difference": round(crude["difference"], 4),
                  "inside": crude["inside"], "outside": crude["outside"]},
        "tests": tests,
    }


# --------------------------------------------------------------- drivers

def band_gap(days):
    if days is None:
        return None
    if days <= 3:
        return "0-3 days"
    if days <= 7:
        return "4-7 days"
    if days <= 11:
        return "8-11 days"
    return "12+ days"


def offer_to_shift(row):
    a = parse_date(row.get("onboarding_started_at")) or parse_date(row.get("offer_at"))
    b = parse_date(row.get("scheduled_first_shift_at"))
    if a and b:
        return (b - a).days
    return None


def ordinal_driver(rows, label, band_fn, outcome_fn, order):
    """No-show rate across an ordered set of bands, plus the spread that lets
    two competing drivers be ranked against each other."""
    buckets = defaultdict(list)
    for r in rows:
        key = band_fn(r)
        if key:
            buckets[key].append(r)

    bands, rates = [], []
    for key in order:
        bucket = buckets.get(key, [])
        k = sum(1 for r in bucket if outcome_fn(r))
        block = rate_block(k, len(bucket))
        bands.append({"band": key, **block})
        if block["conclusive"]:
            rates.append(block["rate"])

    monotonic = all(rates[i] <= rates[i + 1] for i in range(len(rates) - 1)) if len(rates) > 1 else False
    return {
        "driver": label,
        "bands": bands,
        "spread": round(max(rates) - min(rates), 4) if len(rates) > 1 else None,
        "monotonic_increasing": monotonic,
    }


def first_shift_drivers(rows):
    """The two competing explanations for first-shift no-shows, ranked by
    the spread each one actually produces."""
    at_risk = [r for r in rows if stage_ix(r) >= 5]
    if len(at_risk) < MIN_AT_STAGE:
        return None
    no_show = lambda r: stage_ix(r) == 5

    gap = ordinal_driver(at_risk, "offer-to-first-shift gap",
                         lambda r: band_gap(offer_to_shift(r)), no_show,
                         ["0-3 days", "4-7 days", "8-11 days", "12+ days"])
    commute = ordinal_driver(at_risk, "commute band",
                             lambda r: (r.get("commute_band_km") or "").strip(), no_show,
                             SCHEMA["columns"]["commute_band_km"]["levels"])

    ranked = sorted([gap, commute], key=lambda d: -(d["spread"] or 0))
    long_gap = lambda r: (offer_to_shift(r) or 0) >= 8
    check = confound_check(
        at_risk, "long offer-to-first-shift gap raises first-shift no-shows",
        long_gap, no_show,
        {"commute band": lambda r: (r.get("commute_band_km") or "").strip(),
         "source": lambda r: (r.get("source") or "").strip(),
         "role": lambda r: (r.get("role") or "").strip()},
    )
    return {"ranked": ranked, "dominant": ranked[0]["driver"], "confound_check": check}


def weekend_effect(rows):
    """The classic false finding. Kept in the output whatever the verdict,
    because 'we ruled this out' is worth as much as a finding."""
    with_source = [r for r in rows if (r.get("source") or "").strip()]
    if len(with_source) < MIN_AT_STAGE:
        return None
    weekend = lambda r: (parse_date(r.get("applied_at")).weekday() >= 5
                         if parse_date(r.get("applied_at")) else False)
    return confound_check(
        with_source, "weekend applications convert worse to started",
        weekend, lambda r: stage_ix(r) >= 6,
        {"source": lambda r: (r.get("source") or "").strip(),
         "role": lambda r: (r.get("role") or "").strip(),
         "region": lambda r: (r.get("region") or "").strip()},
    )


def early_attrition(rows):
    """Post-hire, and the sharpest test of the confound machinery: manager
    and role are entangled, and only one of them survives."""
    hired = [r for r in rows if stage_ix(r) >= 6]
    if len(hired) < MIN_AT_STAGE or "hiring_manager_id" not in (rows[0] or {}):
        return None

    def quit30(r):
        raw = (r.get("tenure_days") or "").strip()
        if not raw:
            return False
        try:
            return float(raw) <= 30
        except ValueError:
            return False

    pop = sum(1 for r in hired if quit30(r)) / len(hired)

    by_manager = defaultdict(list)
    for r in hired:
        key = (r.get("hiring_manager_id") or "").strip()
        if key:
            by_manager[key].append(r)

    flagged = []
    for key, bucket in sorted(by_manager.items()):
        if len(bucket) < MIN_SEG:
            continue
        k = sum(1 for r in bucket if quit30(r))
        if pop and (k / len(bucket)) / pop >= FLAG_RATIO:
            flagged.append({"manager": key, **rate_block(k, len(bucket))})
    flagged.sort(key=lambda m: -(m["rate"] or 0))
    flagged_ids = {m["manager"] for m in flagged}

    result = {
        "population_30day_attrition": round(pop, 4),
        "hires_analysed": len(hired),
        "managers_tested": sum(1 for b in by_manager.values() if len(b) >= MIN_SEG),
        "managers_flagged": flagged,
    }

    if flagged_ids:
        result["manager_effect"] = confound_check(
            hired, f"{len(flagged_ids)} hiring managers run above-baseline 30-day attrition",
            lambda r: (r.get("hiring_manager_id") or "").strip() in flagged_ids, quit30,
            {"role": lambda r: (r.get("role") or "").strip(),
             "source": lambda r: (r.get("source") or "").strip(),
             "region": lambda r: (r.get("region") or "").strip()},
        )

    # The competing explanation: is it the role those managers happen to hire?
    by_role = defaultdict(list)
    for r in hired:
        key = (r.get("role") or "").strip()
        if key:
            by_role[key].append(r)
    worst_role, worst_rate = None, -1.0
    for key, bucket in by_role.items():
        if len(bucket) < MIN_SEG:
            continue
        rate = sum(1 for r in bucket if quit30(r)) / len(bucket)
        if rate > worst_rate:
            worst_role, worst_rate = key, rate
    if worst_role:
        confounders = {
            "source": lambda r: (r.get("source") or "").strip(),
            "hiring manager": lambda r: (r.get("hiring_manager_id") or "").strip(),
        }
        if flagged_ids:
            # Individual managers rarely carry enough volume to stratify on.
            # The group the engine just identified does.
            confounders["manager group"] = lambda r: (
                "above-baseline" if (r.get("hiring_manager_id") or "").strip() in flagged_ids
                else "baseline")
        result["role_effect"] = confound_check(
            hired, f"{worst_role} hires quit within 30 days more often",
            lambda r: (r.get("role") or "").strip() == worst_role, quit30, confounders,
        )
    return result


# --------------------------------------------------------------- pass 5

def pass5_size(funnel, localised):
    """Hires recoverable, using the reader's own better-performing segments
    as the target. The assumption is stated because it is arguable."""
    reached = funnel["reached"]
    started = reached[STAGES[-1]]
    findings = []

    for block in localised:
        i = block["index"]
        step = funnel["steps"][i]
        downstream = (started / reached[STAGES[i + 1]]) if reached[STAGES[i + 1]] else 0.0

        for dim, data in block["by"].items():
            if not data["flagged"]:
                continue
            flagged_n = sum(s["conversion"]["n"] for s in data["flagged"])
            flagged_k = sum(s["conversion"]["k"] for s in data["flagged"])
            rest_n = step["reached"] - flagged_n
            rest_k = step["advanced"] - flagged_k
            if rest_n < MIN_SEG or not flagged_n:
                continue
            target = rest_k / rest_n
            current = flagged_k / flagged_n
            recoverable = max(0.0, (target - current) * flagged_n * downstream)

            findings.append({
                "step": step["step"],
                "dimension": dim,
                "shape": data["shape"],
                "segments": [s["segment"] for s in data["flagged"]],
                "segment_count": len(data["flagged"]),
                "volume_at_step": flagged_n,
                "segment_conversion": round(current, 4),
                "target_conversion": round(target, 4),
                "share_of_step_loss": data["share_of_step_loss"],
                "hires_recoverable": int(round(recoverable)),
                "assumption": (
                    f"Assumes the flagged {dim} segments can reach "
                    f"{target:.1%} - the rate the rest of your estate already runs at - "
                    f"and that {downstream:.0%} of the extra advances go on to start. "
                    "Argue with both numbers before you spend anything."
                ),
            })
    findings.sort(key=lambda f: -f["hires_recoverable"])
    return findings


# --------------------------------------------------------------- source quality

def source_quality(rows):
    """Are you buying applicants who never convert? Volume next to
    end-to-end conversion, which is the only pairing that answers it."""
    groups = defaultdict(list)
    for r in rows:
        key = (r.get("source") or "").strip()
        if key:
            groups[key].append(r)
    if len(groups) < 2:
        return None

    out = []
    for key, bucket in groups.items():
        if len(bucket) < MIN_SEG:
            continue
        k = sum(1 for r in bucket if stage_ix(r) >= 6)
        out.append({"source": key, "volume_share": round(len(bucket) / len(rows), 4),
                    **rate_block(k, len(bucket))})
    if not out:
        return None
    out.sort(key=lambda s: s["rate"])
    return {"by_source": out, "worst": out[0]["source"], "best": out[-1]["source"]}


# --------------------------------------------------------------- execution cost

def execution_cost(rows, findings, funnel):
    """What acting on this report costs to carry out, counted rather than
    described. Nobody counts this before committing to a plan, and it is
    usually the number that decides whether the plan survives."""
    dates = [d for d in (parse_date(r.get("applied_at")) for r in rows) if d]
    weeks = max(1.0, ((max(dates) - min(dates)).days / 7.0)) if dates else 1.0

    items = []
    for f in findings:
        i = [st["step"] for st in funnel["steps"]].index(f["step"])
        seg = set(f["segments"])
        dim = f["dimension"]

        if dim in SEGMENT_DIMS:
            affected = [r for r in rows
                        if (r.get(dim) or "").strip() in seg and stage_ix(r) >= i]
        else:
            affected = [r for r in rows if stage_ix(r) >= i]

        sites = {(r.get("location_id") or "").strip() for r in affected}
        sites.discard("")
        per_week = len(affected) / weeks

        one_off, recurring = [], []
        if dim == "location_id":
            one_off.append(f"{len(seg)} site-level changes, applied one site at a time")
        elif dim in ("region", "availability_match", "role", "source"):
            one_off.append(
                f"1 policy or configuration change, rolled out to {len(sites)} sites"
                if len(sites) > 1 else "1 configuration change")
        else:
            one_off.append(
                f"1 scheduling change, rolled out to {len(sites)} sites" if len(sites) > 1
                else "1 scheduling change")

        if f.get("mechanism") in ("candidate", "capacity") or dim not in SEGMENT_DIMS:
            recurring.append(
                f"~{per_week:.0f} candidates a week pass through this step in the "
                "affected segments and would need chasing or monitoring")
        else:
            recurring.append(
                f"~{per_week:.0f} candidates a week flow through the affected segments; "
                "spot-check that the change is still applied")

        items.append({
            "finding": f"{f['step']} - {dim}",
            "sites_affected": len(sites),
            "candidates_per_week": round(per_week, 1),
            "one_off": one_off,
            "recurring": recurring,
        })

    total_sites = set()
    for f in findings:
        i = [st["step"] for st in funnel["steps"]].index(f["step"])
        seg, dim = set(f["segments"]), f["dimension"]
        pool = ([r for r in rows if (r.get(dim) or "").strip() in seg and stage_ix(r) >= i]
                if dim in SEGMENT_DIMS else [r for r in rows if stage_ix(r) >= i])
        total_sites |= {(r.get("location_id") or "").strip() for r in pool}
    total_sites.discard("")

    return {
        "weeks_covered": round(weeks, 1),
        "per_finding": items,
        "totals": {
            "distinct_sites_touched": len(total_sites),
            "one_off_changes": sum(len(x["one_off"]) for x in items),
            "candidates_per_week_in_scope": round(
                sum(x["candidates_per_week"] for x in items), 0),
        },
        "to_find_out_whether_it_worked": (
            "One fresh export and one re-run per cycle. In lane A that is manual "
            "every time, and nothing in this report updates itself."
        ),
    }


# --------------------------------------------------------------- assembly

OWNER = {
    "rule": "whoever owns the screening configuration",
    "capacity": "operations - slots, staffing, coverage",
    "candidate": "comms cadence and speed",
    "quality": "sourcing mix",
    "unclassified": "unassigned - the export did not carry exit reasons",
}


def analyse(path):
    columns, rows, dropped = load(path)

    funnel = pass1_funnel(rows)
    localised = pass2_localise(rows, funnel)
    mechanisms = pass3_mechanism(rows, funnel)
    sized = pass5_size(funnel, localised)

    drivers = first_shift_drivers(rows)
    weekend = weekend_effect(rows)
    attrition = early_attrition(rows)
    sources = source_quality(rows)

    ruled_out, could_not = [], []
    for check in [weekend,
                  (drivers or {}).get("confound_check"),
                  (attrition or {}).get("manager_effect"),
                  (attrition or {}).get("role_effect")]:
        if not check:
            continue
        if check["verdict"] == "ruled_out":
            ruled_out.append({"effect": check["effect"], "killed_by": check["killed_by"],
                              "detail": check["tests"]})
        elif check["verdict"] == "inconclusive":
            could_not.append(f"{check['effect']} - {check.get('why', 'inconclusive')}")

    coverage = coverage_report(columns, rows)
    for gap in coverage["absent"]:
        could_not.append(f"no {gap['column']} - {gap['cost']}")
    if dropped:
        could_not.append(f"{dropped:,} rows had no recognisable stage_reached and were excluded")

    findings, populations = [], []
    for f in sized:
        i = funnel["steps"][[st["step"] for st in funnel["steps"]].index(f["step"])]["index"]
        seg = set(f["segments"])
        dim = f["dimension"]
        in_seg = [r for r in rows if (r.get(dim) or "").strip() in seg]
        at_step = [r for r in in_seg if stage_ix(r) >= i]
        mech = classify([r for r in in_seg if stage_ix(r) == i],
                        [r for r in in_seg if stage_ix(r) >= i + 1],
                        i, f["segment_conversion"])
        findings.append({**f,
                         "mechanism": mech.get("mechanism"),
                         "mechanism_share": mech.get("mechanism_share"),
                         "median_wait_days": mech.get("median_wait_days"),
                         "top_exit_reasons": mech.get("top_reasons"),
                         "owner": OWNER.get(mech.get("mechanism"), OWNER["unclassified"]),
                         "confidence": confidence_of(f, mech)})
        populations.append((i, {r.get("application_id") for r in at_step}))

    findings, subsumed = deduplicate(findings, populations)

    banded = driver_finding(rows, drivers, funnel)
    if banded:
        i = len(STAGES) - 2
        mech = classify([r for r in rows if stage_ix(r) == i],
                        [r for r in rows if stage_ix(r) >= i + 1],
                        i, banded["segment_conversion"])
        findings.append({**banded,
                         "mechanism": mech.get("mechanism"),
                         "mechanism_share": mech.get("mechanism_share"),
                         "median_wait_days": mech.get("median_wait_days"),
                         "top_exit_reasons": mech.get("top_reasons"),
                         "owner": OWNER.get(mech.get("mechanism"), OWNER["unclassified"]),
                         "confidence": confidence_of(banded, mech)})
        findings.sort(key=lambda f: -f["hires_recoverable"])

    return {
        "meta": {
            "schema_version": SCHEMA["schema_version"],
            "rows_analysed": len(rows),
            "rows_excluded": dropped,
            "thresholds": TH,
        },
        "coverage": coverage,
        "funnel": funnel,
        "localisation": localised,
        "mechanisms": mechanisms,
        "source_quality": sources,
        "first_shift_drivers": drivers,
        "early_attrition": attrition,
        "findings": findings[:6],
        "execution_cost": execution_cost(rows, findings[:6], funnel),
        "ruled_out": ruled_out,
        "same_population_as_a_finding_above": subsumed,
        "could_not_determine": could_not,
        "fix_list": [
            {"rank": n + 1, "step": f["step"], "segments": f["segments"],
             "hires_recoverable": f["hires_recoverable"], "owner": f["owner"],
             "mechanism": f["mechanism"]}
            for n, f in enumerate(findings[:6])
        ],
    }


def driver_finding(rows, drivers, funnel):
    """A banded driver is a finding too. The offer-to-first-shift gap is not a
    region or a source, so pass 2 cannot see it - and on most exports it is the
    largest single recoverable number in the report."""
    if not drivers:
        return None
    top = drivers["ranked"][0]
    if drivers["confound_check"]["verdict"] != "survived" or not top["spread"]:
        return None

    bands = [b for b in top["bands"] if b["conclusive"]]
    if len(bands) < 2:
        return None
    best = min(bands, key=lambda b: b["rate"])
    at_risk = sum(b["n"] for b in bands)
    no_shows = sum(b["k"] for b in bands)
    if not at_risk:
        return None

    current = no_shows / at_risk
    recoverable = max(0.0, (current - best["rate"]) * at_risk)
    step = funnel["steps"][len(STAGES) - 2]

    return {
        "step": step["step"],
        "dimension": top["driver"],
        "shape": "systemic",
        "segments": [b["band"] for b in bands if b["band"] != best["band"]],
        "segment_count": len(bands) - 1,
        "volume_at_step": at_risk,
        "segment_conversion": round(1 - current, 4),
        "target_conversion": round(1 - best["rate"], 4),
        "share_of_step_loss": 1.0,
        "hires_recoverable": int(round(recoverable)),
        "assumption": (
            f"Assumes every hire could sit in the '{best['band']}' band, where your "
            f"no-show rate is already {best['rate']:.1%} against {current:.1%} overall. "
            "That is your own best-performing band, not a benchmark - but moving "
            "every hire into it is the optimistic end of the range."
        ),
    }


def deduplicate(findings, populations, overlap=0.70):
    """Midwest and the eleven Midwest sites are one finding, not two. Keeps
    the higher-ranked description and records what it absorbed rather than
    dropping it silently."""
    kept, kept_pops, absorbed = [], [], []
    for finding, (index, pop) in zip(findings, populations):
        if not pop:
            kept.append(finding); kept_pops.append((index, pop)); continue
        duplicate_of = None
        for other, (other_index, other_pop) in zip(kept, kept_pops):
            if other_index != index or not other_pop:
                continue
            if len(pop & other_pop) / len(pop) >= overlap:
                duplicate_of = other
                break
        if duplicate_of:
            absorbed.append({
                "step": finding["step"],
                "dimension": finding["dimension"],
                "segments": finding["segments"],
                "describes_the_same_people_as": {
                    "step": duplicate_of["step"], "dimension": duplicate_of["dimension"],
                    "segments": duplicate_of["segments"]},
                "note": "Reported once, under the description that is easier to act on.",
            })
        else:
            kept.append(finding); kept_pops.append((index, pop))
    return kept, absorbed


def confidence_of(finding, mech):
    if finding["volume_at_step"] >= 500 and finding["hires_recoverable"] >= 25 and mech.get("mechanism"):
        return "high"
    if finding["volume_at_step"] >= MIN_SEG * 3:
        return "medium"
    return "low"


# --------------------------------------------------------------- test suite

def _find_sample():
    """Works both inside this repo and inside a standalone installed copy,
    where the dataset is packaged into the skill folder."""
    candidates = [
        os.path.join(SKILL_DIR, "data", "frontline_pipeline_sample.csv"),
        os.path.join(HERE, "..", "..", "..", "..", "data", "frontline_pipeline_sample.csv"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return os.path.abspath(path)
    return os.path.abspath(candidates[0])


SAMPLE = _find_sample()

SCARCE_SITES = {"LOC-03", "LOC-07", "LOC-14", "LOC-19", "LOC-25", "LOC-31", "LOC-36", "LOC-40"}
WEAK_MANAGERS = {"MGR-004", "MGR-012", "MGR-021", "MGR-029", "MGR-038"}


class Checks:
    def __init__(self):
        self.passed, self.failed = [], []

    def ok(self, label, condition, detail=""):
        (self.passed if condition else self.failed).append((label, detail))
        mark = "PASS" if condition else "FAIL"
        print(f"  {mark}  {label}" + (f"  [{detail}]" if detail else ""))


def flagged_segments(report, step_index, dim):
    for block in report["localisation"]:
        if block["index"] == step_index and dim in block["by"]:
            return {s["segment"] for s in block["by"][dim]["flagged"]}, block["by"][dim]
    return set(), {}


def run_tests():
    if not os.path.exists(SAMPLE):
        print(f"sample dataset not found at {SAMPLE}")
        return 1
    print(f"Regression suite against {os.path.basename(SAMPLE)}")
    print("Ground truth is the P1-P8 patterns documented in data/generate.py.\n")
    r = analyse(SAMPLE)
    c = Checks()

    print("P1  Midwest availability knockout at screening")
    steps = r["funnel"]["steps"]
    biggest = max(steps, key=lambda s: s["absolute_loss"])
    c.ok("largest absolute loss is applied -> screened", biggest["index"] == 0, biggest["step"])
    regions, block = flagged_segments(r, 0, "region")
    c.ok("Midwest flagged as underperforming", "Midwest" in regions, ",".join(sorted(regions)) or "none")
    c.ok("no other region flagged", regions == {"Midwest"}, ",".join(sorted(regions)))
    mech = r["mechanisms"].get("applied -> screened", {})
    c.ok("classified rule-driven", mech.get("mechanism") == "rule", str(mech.get("mechanism")))
    reasons = [x[0] for x in (mech.get("top_reasons") or [])]
    c.ok("availability_mismatch among top exit reasons", "availability_mismatch" in reasons,
         ",".join(reasons[:3]))

    print("\nP2  Eight sites with scarce interview slots")
    sites, block = flagged_segments(r, 1, "location_id")
    c.ok("all eight scarce-slot sites flagged", SCARCE_SITES <= sites,
         f"found {len(sites & SCARCE_SITES)}/8")
    c.ok("no site flagged that was not scarce", not (sites - SCARCE_SITES),
         ",".join(sorted(sites - SCARCE_SITES)) or "none")
    c.ok("loss shape is concentrated", block.get("shape") == "concentrated",
         str(block.get("share_of_step_loss")))
    site_finding = next((f for f in r["findings"]
                         if f["step"] == "screened -> interview_scheduled"
                         and f["dimension"] == "location_id"), None)
    c.ok("the scarce-site finding is classified capacity-driven",
         bool(site_finding) and site_finding["mechanism"] == "capacity",
         str(site_finding and site_finding["mechanism"]))
    c.ok("its dominant exit reason is no_interview_slot",
         bool(site_finding) and site_finding["top_exit_reasons"][0][0] == "no_interview_slot",
         str(site_finding and site_finding["top_exit_reasons"][:2]))
    step_mech = r["mechanisms"].get("screened -> interview_scheduled", {}).get("mechanism")
    c.ok("and the step reads differently in aggregate, which is why segments are classified separately",
         step_mech != "capacity", f"step-level: {step_mech}")

    print("\nP3 / P6  Offer-to-first-shift gap beats commute distance")
    d = r["first_shift_drivers"]
    c.ok("gap is the dominant driver", d["dominant"] == "offer-to-first-shift gap", d["dominant"])
    gap = next(x for x in d["ranked"] if x["driver"] == "offer-to-first-shift gap")
    commute = next(x for x in d["ranked"] if x["driver"] == "commute band")
    c.ok("no-show rises monotonically across gap bands", gap["monotonic_increasing"],
         str([b["rate"] for b in gap["bands"]]))
    c.ok("gap spread exceeds commute spread", gap["spread"] > commute["spread"],
         f"{gap['spread']} vs {commute['spread']}")
    c.ok("gap effect survives its confound checks", d["confound_check"]["verdict"] == "survived",
         ",".join(d["confound_check"]["killed_by"]) or "none")

    print("\nP4  jobboard_c is high volume and converts worst")
    sq = r["source_quality"]
    c.ok("jobboard_c has the worst end-to-end conversion", sq["worst"] == "jobboard_c", sq["worst"])
    jb = next(s for s in sq["by_source"] if s["source"] == "jobboard_c")
    c.ok("jobboard_c is the largest single source by volume",
         jb["volume_share"] == max(s["volume_share"] for s in sq["by_source"]),
         f"{jb['volume_share']:.0%}")

    print("\nP5  Manager effect survives; the role it hires does not")
    a = r["early_attrition"]
    found = {m["manager"] for m in a["managers_flagged"]}
    c.ok("at least four of the five weak managers found", len(found & WEAK_MANAGERS) >= 4,
         f"{len(found & WEAK_MANAGERS)}/5, {len(found - WEAK_MANAGERS)} false positives")
    me = a["manager_effect"]
    c.ok("manager effect survives every confound", me["verdict"] == "survived",
         ",".join(me["killed_by"]) or "none")
    role_test = next(t for t in me["tests"] if t["held_constant"] == "role")
    c.ok("manager effect retained within role (>0.70)", role_test["effect_retained"] > 0.70,
         str(role_test["effect_retained"]))
    re_ = a["role_effect"]
    mgr_test = next(t for t in re_["tests"] if t["held_constant"] == "manager group")
    c.ok("apparent role effect collapses within manager (<0.60)",
         mgr_test["effect_retained"] < 0.60,
         f"{re_['effect']}: {mgr_test['effect_retained']}")

    print("\nP8  Weekend applications - the red herring")
    w = next((x for x in r["ruled_out"] if "weekend" in x["effect"]), None)
    c.ok("weekend effect is ruled out, not reported", w is not None)
    c.ok("source is named as what killed it", bool(w) and "source" in w["killed_by"],
         ",".join(w["killed_by"]) if w else "not ruled out")

    print("\nRanking  All three planted losses reach the fix list, largest first")
    fl = r["fix_list"]
    c.ok("fix list ranks by hires recoverable",
         all(fl[i]["hires_recoverable"] >= fl[i + 1]["hires_recoverable"] for i in range(len(fl) - 1)),
         str([f["hires_recoverable"] for f in fl]))
    mechs = {f["mechanism"] for f in fl[:3]}
    c.ok("top three cover rule, capacity and candidate mechanisms",
         {"rule", "capacity", "candidate"} <= mechs, ",".join(sorted(m or "?" for m in mechs)))
    c.ok("the offer-to-first-shift gap reaches the fix list",
         any("gap" in (f.get("segments") and str(f["segments"]) or "") or
             f["step"].startswith("onboarding_started") for f in fl),
         fl[0]["step"])

    print("\nRefusals")
    c.ok("refuses a nominative column", _refuses_nominative())
    c.ok("refuses a file too thin to analyse", _refuses_thin())

    print(f"\n{len(c.passed)} passed, {len(c.failed)} failed")
    if c.failed:
        print("\nFailures:")
        for label, detail in c.failed:
            print(f"  - {label}  [{detail}]")
        return 1
    print("Regression suite passed.")
    return 0


def _refuses_nominative():
    try:
        check_columns(["application_id", "applied_at", "stage_reached", "candidate_email"])
        return False
    except Refusal:
        return True


def _refuses_thin():
    import tempfile
    with open(SAMPLE, newline="", encoding="utf-8-sig") as fh:
        head = [next(fh) for _ in range(80)]
    tmp = os.path.join(tempfile.gettempdir(), "_thin_sample.csv")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.writelines(head)
    try:
        analyse(tmp)
        return False
    except Refusal:
        return True
    finally:
        os.remove(tmp)


# --------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description="Funnel drop-off engine.")
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
        print(f"report written to {args.out}  ({report['meta']['rows_analysed']:,} rows)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
