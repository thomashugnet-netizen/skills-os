#!/usr/bin/env python3
"""
Source ROI engine: joins channel spend to hiring outcomes and prices every
channel per start and per hire still there at 30 days, not per application.

    python3 roi.py --pipeline pipeline.csv --spend spend.csv [--as-of 2026-08-31]
                   [--screen-minutes 10 --hourly 18] [--shift 15]
                   [--html report.html] [--json report.json]
    python3 roi.py --demo
    python3 roi.py --test

pipeline.csv  one row per application: application_id, source, applied_at, and a
              start signal (first_shift_at or first_job_at, or stage_reached).
              Optional and used when present: stage timestamps, role,
              location_id, separation_at or tenure_days.
spend.csv     month (YYYY-MM), source, spend_usd [, applications].

What it does, in order:
  1. reconciles the two files: labels in one and not the other, months missing
     on either side, application counts that disagree, channels with no spend
  2. the cost ladder: cost per application, per stage, per start, and per hire
     still there at 30 days, with the rank change flagged
  3. retention by channel on starts with a full 30-day window only
  4. the mix check: start rate re-weighted to one role mix, one location mix
     and one month mix, so a channel is not charged for where it was bought
  5. elasticity, only where the spend history varies enough to read it
  6. a bounded reallocation with expected starts, a check date and a stop rule

Channels with no spend or almost none (referral, career site) are labelled
partial cost and never ranked or recommended as a destination: their price is
not in the file.

Exit codes: 0 report written, 2 no mode, 3 input refused, 4 engine failed.
Standard library only.
"""

import csv
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)

MIN_ROWS = 500
MIN_CELL = 30            # applications in a stratum before its rate is used
MIN_STARTS = 30          # starts before a channel's cost per start is ranked
MATURE_DAYS = 45         # an application this old has had time to start
WINDOW = 30              # retention window
PARTIAL_SHARE = 0.15     # cost per application under 15% of the paid median: partial cost
VOLUME_GAP = 0.05
STAGES = [               # canonical order; whichever are present make the ladder
    ("screened_at", "screen pass"),
    ("docs_submitted_at", "documents in"),
    ("interview_completed_at", "interview"),
    ("background_clear_at", "background clear"),
    ("offer_at", "offer"),
]
START_COLS = ("first_shift_at", "first_job_at")
STARTED_STAGES = {"started", "activated", "hired", "active", "first_shift", "first_job"}
NOMINATIVE = re.compile(r"(^|_)(first|last|full)?_?name($|_)|e-?mail|phone|mobile|address|street|zip|postcode|"
                        r"postal|ssn|social_security|national_insurance|dob|birth|notes?$|comment", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ reading

def read(path, what):
    if not path or not os.path.exists(path):
        raise Refusal(f"{what}: file not found ({path}).")
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = csv.reader(io.StringIO(text), dialect)
    try:
        header = next(rows)
    except StopIteration:
        raise Refusal(f"{what}: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in header]
    for h in header:
        if NOMINATIVE.search(h):
            raise Refusal(f"{what}: column '{h}' looks like personal information. Re-export without it: nothing "
                          "in this analysis needs to know who anybody is.")
    out = []
    for r in rows:
        if not any(c.strip() for c in r):
            continue
        out.append({h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)})
    sample = "".join(",".join(r.values()) for r in out[:2000])
    if EMAIL.search(sample):
        raise Refusal(f"{what}: the file contains email addresses. Re-export with opaque ids only.")
    return header, out


def day(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s[:10])
    except ValueError:
        for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
            try:
                return dt.datetime.strptime(s[:10], fmt).date()
            except ValueError:
                pass
    return "bad"


def key(label):
    return re.sub(r"[^a-z0-9]", "", label.lower())


def load(pipeline, spend):
    ph, prows = read(pipeline, "pipeline")
    for c in ("application_id", "source", "applied_at"):
        if c not in ph:
            raise Refusal(f"pipeline: missing column '{c}'. Needed: application_id, source, applied_at, and "
                          "first_shift_at, first_job_at or stage_reached.")
    start_col = next((c for c in START_COLS if c in ph), None)
    if not start_col and "stage_reached" not in ph:
        raise Refusal("pipeline: no start signal. Add first_shift_at (or first_job_at), or stage_reached.")
    if len(prows) < MIN_ROWS:
        raise Refusal(f"pipeline: {len(prows)} rows. At least {MIN_ROWS} are needed before cost per start means "
                      "anything.")
    sh, srows = read(spend, "spend")
    for c in ("month", "source", "spend_usd"):
        if c not in sh:
            raise Refusal(f"spend: missing column '{c}'. Needed: month, source, spend_usd.")
    stages = [(c, label) for c, label in STAGES if c in ph]
    apps, bad = [], 0
    seen = set()
    for r in prows:
        a = day(r["applied_at"])
        if a in (None, "bad"):
            bad += 1
            continue
        if r["application_id"] in seen:
            raise Refusal(f"pipeline: application_id {r['application_id']} appears twice. One row per application.")
        seen.add(r["application_id"])
        start = day(r.get(start_col, "")) if start_col else None
        if start == "bad":
            start = None
        started = bool(start) or (not start_col and r.get("stage_reached", "").lower() in STARTED_STAGES)
        sep = day(r.get("separation_at", ""))
        sep = None if sep == "bad" else sep
        ten = r.get("tenure_days", "")
        try:
            ten = float(ten) if ten != "" else None
            ten = ten if ten is None or math.isfinite(ten) else None
        except ValueError:
            ten = None
        apps.append({"source": r["source"], "applied": a, "start": start, "started": started,
                     "stages": {c: bool(day(r.get(c, "")) not in (None, "bad")) for c, _ in stages},
                     "role": r.get("role") or None, "location": r.get("location_id") or None,
                     "sep": sep, "tenure": ten})
    if bad > len(prows) * 0.05:
        raise Refusal(f"pipeline: {bad} rows have no readable applied_at date. Use YYYY-MM-DD.")
    spend_rows = []
    for n, r in enumerate(srows, 2):
        if not re.fullmatch(r"\d{4}-\d{2}", r["month"][:7]):
            raise Refusal(f"spend row {n}: month '{r['month']}' should look like 2026-03.")
        try:
            usd = float(r["spend_usd"].replace("$", "").replace(",", "")) if r["spend_usd"] else 0.0
        except ValueError:
            raise Refusal(f"spend row {n}: spend_usd '{r['spend_usd']}' is not a number.")
        if not math.isfinite(usd):
            raise Refusal(f"spend row {n}: spend_usd '{r['spend_usd']}' is not a number.")
        if usd < 0:
            raise Refusal(f"spend row {n}: negative spend.")
        n_apps = None
        if r.get("applications", "") != "":
            try:
                f = float(r["applications"])
                n_apps = int(f) if math.isfinite(f) and f >= 0 else None
            except ValueError:
                n_apps = None
        spend_rows.append({"month": r["month"][:7], "source": r["source"], "usd": usd, "apps": n_apps})
    if not spend_rows:
        raise Refusal("spend: no rows.")
    return apps, spend_rows, stages, {"start_col": start_col, "has_role": "role" in ph,
                                      "has_location": "location_id" in ph,
                                      "has_retention": "separation_at" in ph or "tenure_days" in ph}


# ------------------------------------------------------------------ maths

def wilson(k, n, z=1.645):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 4:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return None if den == 0 else num / den


def money(x):
    return "n/a" if x is None else f"${x:,.0f}" if x >= 100 else f"${x:,.2f}"


def month_of(d):
    return d.strftime("%Y-%m")


def month_end(m):
    y, mo = int(m[:4]), int(m[5:7])
    nxt = dt.date(y + (mo == 12), mo % 12 + 1, 1)
    return nxt - dt.timedelta(days=1)


# ------------------------------------------------------------------ analysis

def analyse(pipeline, spend, as_of=None, shift_pct=15, screen_minutes=None, hourly=None):
    apps, spend_rows, stages, has = load(pipeline, spend)
    as_of = as_of or max(max(a["applied"] for a in apps),
                         max((a["start"] for a in apps if a["start"]), default=dt.date.min))

    # 1. reconcile labels
    p_labels, s_labels = {}, {}
    for a in apps:
        p_labels.setdefault(key(a["source"]), set()).add(a["source"])
    for s in spend_rows:
        s_labels.setdefault(key(s["source"]), set()).add(s["source"])
    merged = []
    canon = {}
    for k in set(p_labels) | set(s_labels):
        names = sorted(p_labels.get(k, set()) | s_labels.get(k, set()))
        canon[k] = sorted(p_labels.get(k, set()) or names)[0]
        if len(names) > 1:
            merged.append(names)
    only_pipeline = sorted(canon[k] for k in p_labels if k not in s_labels)
    only_spend = sorted(canon[k] for k in s_labels if k not in p_labels)
    for a in apps:
        a["ch"] = canon[key(a["source"])]
    spend = {}
    vol_spend = {}
    for s in spend_rows:
        ch = canon[key(s["source"])]
        spend[(s["month"], ch)] = spend.get((s["month"], ch), 0.0) + s["usd"]
        if s["apps"] is not None:
            vol_spend[(s["month"], ch)] = vol_spend.get((s["month"], ch), 0) + s["apps"]

    p_months = sorted({month_of(a["applied"]) for a in apps})
    s_months = sorted({m for m, _ in spend})
    # analysis window: months in both files whose applications have had time to start
    mature_cut = as_of - dt.timedelta(days=MATURE_DAYS)
    window = [m for m in p_months if m in s_months and month_end(m) <= mature_cut]
    if not window:
        raise Refusal("No month is in both files and old enough for its applications to have started "
                      f"({MATURE_DAYS} days). Export a longer period.")
    missing_in_spend = [m for m in p_months if m not in s_months]
    missing_in_pipeline = [m for m in s_months if m not in p_months]
    immature = [m for m in p_months if m in s_months and m not in window]

    channels = sorted({a["ch"] for a in apps} | {c for _, c in spend})
    win = set(window)
    W = [a for a in apps if month_of(a["applied"]) in win]
    counts = {}
    for a in W:
        counts[(month_of(a["applied"]), a["ch"])] = counts.get((month_of(a["applied"]), a["ch"]), 0) + 1
    volume = []
    for (m, ch), n_spend in sorted(vol_spend.items()):
        if m not in win:
            continue
        n_pipe = counts.get((m, ch), 0)
        if n_pipe == 0 and n_spend == 0:
            continue
        gap = abs(n_spend - n_pipe) / max(n_pipe, 1)
        if gap > VOLUME_GAP:
            volume.append({"month": m, "channel": ch, "spend_file": n_spend, "pipeline": n_pipe,
                           "gap": round(gap, 2)})
    no_spend_rows = sorted({a["ch"] for a in W} - {c for (m, c) in spend if m in win})

    # 2. the ladder
    ladder = {}
    for ch in channels:
        rows = [a for a in W if a["ch"] == ch]
        usd = sum(v for (m, c), v in spend.items() if c == ch and m in win)
        n = len(rows)
        steps = []
        for col, label in stages:
            k = sum(1 for a in rows if a["stages"][col] or a["started"])
            steps.append({"stage": label, "count": k, "cost": usd / k if k else None})
        starts = sum(1 for a in rows if a["started"])
        ladder[ch] = {"spend": round(usd, 2), "applications": n, "steps": steps, "starts": starts,
                      "start_rate": round(starts / n, 4) if n else None,
                      "cpa": usd / n if n else None, "cps": usd / starts if starts else None}

    # partial cost: no spend, or a price per application far below the paid median
    paid = [v["cpa"] for v in ladder.values() if v["cpa"] and v["cpa"] > 0]
    median_cpa = sorted(paid)[len(paid) // 2] if paid else None
    for ch, v in ladder.items():
        v["partial_cost"] = bool(v["applications"]) and (not v["cpa"] or median_cpa is None
                                                          or v["cpa"] < PARTIAL_SHARE * median_cpa)
        v["ranked"] = not v["partial_cost"] and v["starts"] >= MIN_STARTS

    handling = (screen_minutes / 60.0 * hourly) if (screen_minutes and hourly) else None
    for ch, v in ladder.items():
        n, k = v["applications"], v["starts"]
        v["handling_per_app"] = handling
        v["allin_cps"] = (v["spend"] + n * handling) / k if (handling and k) else None

    # 3. retention, on starts with a full window
    ret = {}
    for ch in channels:
        cohort = [a for a in W if a["ch"] == ch and a["started"] and a["start"]
                  and a["start"] + dt.timedelta(days=WINDOW) <= as_of]
        stayed = 0
        for a in cohort:
            left = (a["sep"] and (a["sep"] - a["start"]).days <= WINDOW) or \
                   (a["tenure"] is not None and a["tenure"] <= WINDOW)
            stayed += 0 if left else 1
        lo, hi = wilson(stayed, len(cohort))
        v = ladder[ch]
        surv = stayed / len(cohort) if cohort else None
        ret[ch] = {"starts_with_window": len(cohort), "stayed_30": stayed,
                   "survival_30": None if surv is None else round(surv, 3), "ci90": [round(lo, 3), round(hi, 3)]}
        v["cprh"] = v["cps"] / surv if (v["cps"] and surv) else None
        v["allin_cprh"] = v["allin_cps"] / surv if (v["allin_cps"] and surv) else None
    excluded_recent = sum(1 for a in W if a["started"] and a["start"]
                          and a["start"] + dt.timedelta(days=WINDOW) > as_of)

    # rank changes along the ladder (ranked channels only)
    ranked = [c for c in channels if ladder[c]["ranked"]]
    def order(metric):
        return [c for c in sorted(ranked, key=lambda c: (ladder[c][metric] is None, ladder[c][metric] or 0))]
    by_cpa, by_cps = order("cpa"), order("cps")
    by_cprh = order("cprh") if has["has_retention"] else []
    by_allin = (order("allin_cprh") if has["has_retention"] else order("allin_cps")) if handling else []

    # break-even: the handling cost per application at which the media-cheapest
    # channel per start stops being the cheapest
    breakeven = None
    if len(by_cps) >= 2:
        c = by_cps[0]
        vc = ladder[c]
        best = None
        for d in by_cps[1:]:
            vd = ladder[d]
            load_c, load_d = vc["applications"] / vc["starts"], vd["applications"] / vd["starts"]
            if load_c > load_d:
                k = (vd["cps"] - vc["cps"]) / (load_c - load_d)
                if best is None or k < best[0]:
                    best = (k, d)
        breakeven = {"channel": c, "apps_per_start": round(vc["applications"] / vc["starts"], 1),
                     "dollars_per_application": None if best is None else round(best[0], 2),
                     "overtaken_by": None if best is None else best[1]}
    reorder = []
    for c in ranked:
        r1, r2 = by_cpa.index(c) + 1, by_cps.index(c) + 1
        r4 = (by_allin.index(c) + 1) if c in by_allin else None
        if r4 is not None and (abs(r1 - r4) >= 2 or (r1 == 1 and r4 != 1)) and not (abs(r1 - r2) >= 2 or (r1 == 1 and r2 != 1)):
            reorder.append({"channel": c, "rank_per_application": r1, "rank_per_start": r2,
                            "rank_per_retained": (by_cprh.index(c) + 1) if c in by_cprh else None,
                            "rank_all_in": r4})
            continue
        if abs(r1 - r2) >= 2 or (r1 == 1 and r2 != 1):
            reorder.append({"channel": c, "rank_per_application": r1, "rank_per_start": r2,
                            "rank_per_retained": (by_cprh.index(c) + 1) if c in by_cprh else None,
                            "rank_all_in": r4})

    # 4. the mix check
    def standardised(dim):
        cells = {}
        for a in W:
            g = a[dim]
            if g is None:
                return None
            cells.setdefault((a["ch"], g), [0, 0])
            cells[(a["ch"], g)][0] += 1
            cells[(a["ch"], g)][1] += 1 if a["started"] else 0
        mix = {}
        for a in W:
            mix[a[dim]] = mix.get(a[dim], 0) + 1
        tot = sum(mix.values())
        out, thin = {}, []
        for ch in channels:
            num = den = 0.0
            for g, w in mix.items():
                n, k = cells.get((ch, g), (0, 0))
                if n >= MIN_CELL:
                    num += w * k / n
                    den += w
            if den >= 0.6 * tot:
                out[ch] = num / den
            elif any(cells.get((ch, g)) for g in mix):
                thin.append(ch)
        return {"rates": out, "thin": thin}

    pooled = sum(1 for a in W if a["started"]) / len(W)
    dims = []
    if has["has_role"]:
        dims.append(("role", "role"))
    if has["has_location"]:
        dims.append(("location", "location"))
    for a in W:
        a["month"] = month_of(a["applied"])
    dims.append(("month", "application month"))
    mix_out = []
    explained = []
    for dim, label in dims:
        st = standardised(dim)
        if st is None:
            continue
        rows = []
        for ch in channels:
            raw = ladder[ch]["start_rate"]
            std = st["rates"].get(ch)
            if raw is None or std is None:
                continue
            gap_raw, gap_std = raw - pooled, std - pooled
            shrunk = abs(gap_raw) >= 0.02 and (abs(gap_std) < 0.5 * abs(gap_raw) or gap_std * gap_raw < 0)
            rows.append({"channel": ch, "raw": round(raw, 4), "standardised": round(std, 4),
                         "explained": shrunk})
            if shrunk:
                explained.append({"channel": ch, "by": label, "raw": round(raw, 4), "standardised": round(std, 4)})
        mix_out.append({"by": label, "rows": rows, "thin": st["thin"]})
    explained_channels = {e["channel"] for e in explained}

    # 5. elasticity, per channel, where spend varies
    elastic = []
    month_spend = {}
    for (m, ch), v in spend.items():
        if m in win:
            month_spend.setdefault(ch, {})[m] = v
    starts_m = {}
    for a in W:
        if a["started"]:
            starts_m[(a["month"], a["ch"])] = starts_m.get((a["month"], a["ch"]), 0) + 1
    top_months = {}
    for ch in ranked:
        ms = sorted(m for m, v in month_spend.get(ch, {}).items() if v > 0)
        xs = [month_spend[ch][m] for m in ms]
        if len(xs) < 6:
            elastic.append({"channel": ch, "read": "too_few_months", "months": len(xs)})
            continue
        mean = sum(xs) / len(xs)
        cv = math.sqrt(sum((x - mean) ** 2 for x in xs) / len(xs)) / mean if mean else 0
        if cv < 0.25:
            elastic.append({"channel": ch, "read": "flat_spend", "cv": round(cv, 2)})
            continue
        per_dollar = [starts_m.get((m, ch), 0) / month_spend[ch][m] for m in ms]
        rho = spearman(xs, per_dollar)
        q = sorted(ms, key=lambda m: -month_spend[ch][m])[:max(2, len(ms) // 4)]
        top_months[ch] = set(q)
        elastic.append({"channel": ch, "read": "falls" if rho is not None and rho <= -0.5 else "no_clear_fall",
                        "rho": None if rho is None else round(rho, 2), "cv": round(cv, 2),
                        "high_spend_months": sorted(q)})
    seasonal = False
    if len(top_months) >= 2:
        sets = list(top_months.values())
        common = set.intersection(*sets)
        seasonal = len(common) >= max(1, min(len(s) for s in sets) // 2)
        for e in elastic:
            if e.get("read") == "falls" and seasonal:
                e["read"] = "falls_but_seasonal"

    # 6. reallocation: from the weakest ranked channel to the best, by cost per retained hire
    if by_allin:
        metric = "allin_cprh" if has["has_retention"] else "allin_cps"
    else:
        metric = "cprh" if by_cprh else "cps"
    cand = [c for c in (by_allin or by_cprh or by_cps) if c not in explained_channels and ladder[c][metric]]
    proposal = None
    if len(cand) >= 2:
        best, worst = cand[0], cand[-1]
        b, w = ladder[best], ladder[worst]
        if w[metric] / b[metric] >= 1.25:
            months = max(1, len([m for m in window if (m, worst) in spend]))
            moved = w["spend"] / months * shift_pct / 100
            gained = moved / b["cps"]
            lost = moved / w["cps"]
            extra_apps = moved / b["cpa"] - moved / w["cpa"]
            proposal = {"from": worst, "to": best, "metric": metric, "shift_pct": shift_pct,
                        "extra_applications_per_month": round(extra_apps),
                        "survival_from": ret[worst]["survival_30"], "survival_to": ret[best]["survival_30"],
                        "monthly_amount": round(moved, 2), "starts_gained": round(gained, 1),
                        "starts_lost": round(lost, 1), "net_starts_per_month": round(gained - lost, 1),
                        "check_after_weeks": 6,
                        "stop_rule": (f"Stop and move it back if {best}'s cost per start rises more than 20% above "
                                      f"{money(b['cps'])}, or it delivers fewer than "
                                      f"{math.floor((gained) * 0.7 * 1.5)} extra starts in the six weeks."),
                        "assumption": (f"{best} keeps converting at its current rate at slightly higher spend. "
                                       "That is the assumption the check tests.")}

    return {"as_of": as_of.isoformat(), "window": [window[0], window[-1]], "months_in_window": len(window),
            "applications": len(W), "pooled_start_rate": round(pooled, 4), "stages": [l for _, l in stages],
            "reconcile": {"merged_labels": merged, "only_in_pipeline": only_pipeline, "only_in_spend": only_spend,
                          "months_missing_in_spend": missing_in_spend,
                          "months_missing_in_pipeline": missing_in_pipeline, "too_recent_months": immature,
                          "volume_gaps": volume, "no_spend_rows": no_spend_rows},
            "ladder": ladder, "retention": ret, "excluded_recent_starts": excluded_recent,
            "rank_by_application": by_cpa, "rank_by_start": by_cps, "rank_by_retained": by_cprh,
            "reorder": reorder, "rank_all_in": by_allin, "breakeven": breakeven,
            "handling": None if not handling else {"minutes": screen_minutes, "hourly": hourly,
                                                   "per_application": round(handling, 2)},
            "mix": mix_out, "explained_by_mix": explained,
            "elasticity": elastic, "seasonal_confound": seasonal, "proposal": proposal,
            "has": has}


# ------------------------------------------------------------------ output

def text(r):
    L = []
    rc = r["reconcile"]
    L.append(f"Source ROI: {r['applications']:,} applications, {r['window'][0]} to {r['window'][1]} "
             f"({r['months_in_window']} months), as of {r['as_of']}.")
    L.append("")
    L.append("1. Reconciliation")
    issues = []
    for names in rc["merged_labels"]:
        issues.append(f"Treated as one channel: {' / '.join(names)}. Check they really are the same.")
    if rc["only_in_pipeline"]:
        issues.append(f"In the pipeline but never in the spend file: {', '.join(rc['only_in_pipeline'])}. Their "
                      "cost is missing, not zero.")
    if rc["only_in_spend"]:
        issues.append(f"Spend with no applications: {', '.join(rc['only_in_spend'])}. Money that produced "
                      "nothing in this export, or a label that does not match.")
    if rc["months_missing_in_spend"]:
        issues.append(f"Months with applications and no spend: {', '.join(rc['months_missing_in_spend'])}.")
    if rc["too_recent_months"]:
        issues.append(f"Left out as too recent to have started ({MATURE_DAYS} days): "
                      f"{', '.join(rc['too_recent_months'])}.")
    for g in rc["volume_gaps"][:8]:
        issues.append(f"{g['month']} {g['channel']}: spend file says {g['spend_file']} applications, the pipeline "
                      f"has {g['pipeline']} ({round(g['gap'] * 100)}% apart). One side may count clicks or "
                      "duplicates.")
    if len(rc["volume_gaps"]) > 8:
        issues.append(f"... and {len(rc['volume_gaps']) - 8} more month-channel gaps.")
    L += [f"   - {i}" for i in issues] or ["   - The two files agree on labels, months and volumes."]
    L.append("")
    L.append("2. The cost ladder (ranked channels; partial cost shown below)")
    head = f"   {'channel':<16}{'spend':>10}{'apps':>8}{'per app':>10}" + \
           "".join(f"{'per ' + s:>18}" for s in r["stages"]) + f"{'starts':>8}{'per start':>11}{'per 30-day':>12}" + (f"{'all-in/start':>14}" if r["handling"] else "")
    L.append(head)
    for c in r["rank_by_start"] + [c for c in r["ladder"] if c not in r["rank_by_start"]]:
        v = r["ladder"][c]
        if not v["applications"]:
            continue
        tag = " (partial cost)" if v["partial_cost"] else (" (too few starts)" if not v["ranked"] else "")
        L.append(f"   {c:<16}{money(v['spend']):>10}{v['applications']:>8,}{money(v['cpa']):>10}"
                 + "".join(f"{money(s['cost']):>18}" for s in v["steps"])
                 + f"{v['starts']:>8,}{money(v['cps']):>11}{money(v.get('cprh')):>12}"
                 + (f"{money(v.get('allin_cps')):>14}" if r["handling"] else "") + tag)
    for x in r["reorder"]:
        L.append(f"   >> {x['channel']}: #{x['rank_per_application']} per application, #{x['rank_per_start']} per "
                 f"start" + (f", #{x['rank_per_retained']} per hire still there at 30 days"
                             if x["rank_per_retained"] else "")
                 + (f", #{x['rank_all_in']} once screening time is counted" if x.get("rank_all_in") else "") + ".")
    if r["handling"]:
        h = r["handling"]
        L.append(f"   All-in adds screening time: {h['minutes']:g} minutes an application at ${h['hourly']:g}/hour, "
                 f"{money(h['per_application'])} an application. Your figures, not measured.")
    be = r["breakeven"]
    if be and be["dollars_per_application"] is not None:
        L.append(f"   {be['channel']} is cheapest per start on media alone, but it takes {be['apps_per_start']} "
                 f"applications to get one start. Once handling an application costs more than "
                 f"{money(be['dollars_per_application'])} (about "
                 f"{round(be['dollars_per_application'] / (r['handling']['hourly'] if r['handling'] else 18) * 60)} "
                 f"minutes at ${(r['handling']['hourly'] if r['handling'] else 18):g}/hour"
                 + ("" if r["handling"] else ", an assumed rate") + f"), {be['overtaken_by']} is cheaper per start.")
    L.append("")
    L.append("3. Still there at 30 days (starts with a full 30-day window)")
    for c in r["rank_by_start"] + [c for c in r["ladder"] if c not in r["rank_by_start"]]:
        t = r["retention"][c]
        if t["starts_with_window"]:
            L.append(f"   {c:<16}{t['stayed_30']}/{t['starts_with_window']} "
                     f"({round(t['survival_30'] * 100)}%, 90% range {round(t['ci90'][0] * 100)}-"
                     f"{round(t['ci90'][1] * 100)}%)")
    L.append(f"   {r['excluded_recent_starts']} starts left out: their 30 days are not over yet."
             if r["excluded_recent_starts"] else "   Every start counted here has had its full 30 days.")
    L.append("")
    L.append("4. The channel, or the mix?")
    for m in r["mix"]:
        moved = [x for x in m["rows"] if x["explained"]]
        L.append(f"   By {m['by']}: " + ("; ".join(f"{x['channel']} {round(x['raw'] * 100, 1)}% raw, "
                                                   f"{round(x['standardised'] * 100, 1)}% on one mix"
                                                   for x in moved)
                                        if moved else "re-weighting to one mix leaves every channel's gap in place.")
                 + (f" Too thin to test: {', '.join(m['thin'])}." if m["thin"] else ""))
    if not r["explained_by_mix"]:
        L.append("   Nothing here is explained by mix: the differences belong to the channels.")
    L.append("")
    L.append("5. Does a channel get worse as you spend more?")
    for e in r["elasticity"]:
        if e["read"] == "too_few_months":
            L.append(f"   {e['channel']}: {e['months']} months, too few to read.")
        elif e["read"] == "flat_spend":
            L.append(f"   {e['channel']}: spend barely varies (cv {e['cv']}), so it cannot be read. Do not assume it "
                     "scales.")
        elif e["read"] == "falls_but_seasonal":
            L.append(f"   {e['channel']}: starts per dollar fall in its high-spend months (rank correlation "
                     f"{e['rho']}), but those are your peak months for every channel. Saturation and season cannot "
                     "be separated in this history.")
        elif e["read"] == "falls":
            L.append(f"   {e['channel']}: starts per dollar fall as spend rises (rank correlation {e['rho']}). "
                     "Its cost per start will get worse if you add budget.")
        else:
            L.append(f"   {e['channel']}: no clear fall in starts per dollar at higher spend (rank correlation "
                     f"{e['rho']}).")
    L.append("")
    L.append("6. Reallocation")
    p = r["proposal"]
    if p:
        what = {"cprh": "hire still there at 30 days", "cps": "start",
                "allin_cprh": "hire still there at 30 days", "allin_cps": "start"}[p["metric"]]
        L.append(f"   Move {p['shift_pct']}% of {p['from']}'s monthly spend ({money(p['monthly_amount'])} a month) "
                 f"to {p['to']}. Among fully priced channels, {p['from']} is the dearest per {what} and {p['to']} "
                 f"the cheapest" + (", screening time included." if p["metric"].startswith("allin") else "."))
        L.append(f"   Expected: about {p['starts_gained']} more starts a month from {p['to']}, about "
                 f"{p['starts_lost']} fewer from {p['from']}: {p['net_starts_per_month']:+} a month.")
        if p["extra_applications_per_month"] > 0 and not r["handling"]:
            L.append(f"   It also adds about {p['extra_applications_per_month']} applications a month to screen, and "
                     f"{p['to']} keeps {round((p['survival_to'] or 0) * 100)}% of its starts at 30 days against "
                     f"{round((p['survival_from'] or 0) * 100)}% for {p['from']}. If screening is your bottleneck, "
                     "price it with --screen-minutes and --hourly before acting.")
        L.append(f"   Assumption: {p['assumption']}")
        L.append(f"   Check after {p['check_after_weeks']} weeks. {p['stop_rule']}")
        L.append("   Keep the second channel alive: a single source of starts is a single point of failure.")
    else:
        L.append("   No move proposed: the fully priced channels are within 25% of each other, or too few are "
                 "ranked.")
    L.append("")
    L.append("What this cannot tell you")
    partial = [c for c, v in r["ladder"].items() if v["partial_cost"]]
    if partial:
        L.append(f"   - {', '.join(partial)}: partial cost. Referral bonuses, recruiter time and site costs are not in "
                 "the spend file, so they are not ranked.")
    L.append("   - Source labels are usually last touch. A channel with no direct spend often converts demand a paid "
             "channel created, and will not scale on its own.")
    L.append("   - Screening time, agency fees and check fees are not in these numbers unless they are in your spend "
             "file.")
    L.append("   - This reads closed months. It cannot see this month's bids or tell you whether a move already made "
             "worked.")
    return "\n".join(L)


def render(r, path):
    e = html.escape
    rows = []
    for c in r["rank_by_start"] + [c for c in r["ladder"] if c not in r["rank_by_start"]]:
        v = r["ladder"][c]
        if not v["applications"]:
            continue
        tag = "partial cost" if v["partial_cost"] else ("" if v["ranked"] else "too few starts")
        rows.append(f"<tr><td>{e(c)}</td><td>{money(v['spend'])}</td><td>{v['applications']:,}</td>"
                    f"<td>{money(v['cpa'])}</td><td>{v['starts']:,}</td><td>{money(v['cps'])}</td>"
                    f"<td>{money(v.get('cprh'))}</td><td>{e(tag)}</td></tr>")
    body = e(text(r))
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Source ROI</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:980px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}pre{{white-space:pre-wrap;font-size:13px}}</style>
<h1>Source ROI</h1><table><tr><th>Channel</th><th>Spend</th><th>Applications</th><th>Per application</th>
<th>Starts</th><th>Per start</th><th>Per hire at 30 days</th><th></th></tr>{''.join(rows)}</table>
<pre>{body}</pre></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

def _data_dir():
    for d in (os.path.join(SKILL_DIR, "data"), os.path.join(HERE, "..", "..", "..", "..", "data")):
        if os.path.exists(os.path.join(d, "frontline_pipeline_sample.csv")):
            return os.path.abspath(d)
    return None


# What data/generate.py planted that this skill must see: the cheap channel is
# the cheapest per application, converts worst, needs the most applications per
# start and keeps the fewest at 30 days; referral and career site carry no real
# price; source is drawn independently of role and site, so nothing about the
# channels is explained by mix; spend and volume peak in the same months.
# Not planted, and recorded here as found: on media cost alone the cheap channel
# stays cheapest per start in all four samples. Pricing screening at 10 minutes
# and $18 an hour takes the lead from it everywhere except logistics, where its
# media price gap is widest. A suite that asserted the reorder would be
# asserting a belief about channels rather than a fact about the data.
ORACLE = {
    "frontline": {"cheap": "jobboard_c", "partial": {"referral", "career_site"},
                  "spend": "sourcing_spend_sample.csv", "still_first_at_10": False},
    "qsr": {"cheap": "jobboard_c", "partial": {"referral", "career_site"}, "spend": "qsr_spend_sample.csv",
            "still_first_at_10": False},
    "logistics": {"cheap": "jobboard_c", "partial": {"referral", "career_site"},
                  "spend": "logistics_spend_sample.csv", "still_first_at_10": True},
    "gig": {"cheap": "paid_social", "partial": {"worker_referral", "app_store_organic"},
            "spend": "gig_spend_sample.csv", "still_first_at_10": False},
}


def run_tests():
    import contextlib
    import random
    import shutil
    import tempfile
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {name}" + (f"  [{detail}]" if detail else ""))

    data = _data_dir()
    if not data:
        print("sample dataset not found")
        return 1
    for stem, o in ORACLE.items():
        pipe = os.path.join(data, f"{stem}_pipeline_sample.csv")
        if not os.path.exists(pipe):
            continue
        sp = os.path.join(data, o["spend"])
        r = analyse(pipe, sp)
        L = r["ladder"]
        t = f"{stem}: "
        cheap = o["cheap"]
        live = {c: v for c, v in L.items() if v["applications"]}
        check(t + "the cheap channel is cheapest per application among ranked channels",
              r["rank_by_application"][0] == cheap, r["rank_by_application"])
        check(t + "it converts to started worst of all channels",
              min((v["start_rate"], c) for c, v in live.items())[1] == cheap)
        check(t + "it needs the most applications per start",
              max((v["applications"] / v["starts"], c) for c, v in live.items() if v["starts"])[1] == cheap)
        check(t + "it keeps the fewest starts at 30 days",
              min((r["retention"][c]["survival_30"], c) for c in live if r["retention"][c]["starts_with_window"])[1]
              == cheap)
        check(t + "partial-cost channels labelled", {c for c, v in live.items() if v["partial_cost"]} == o["partial"],
              {c for c, v in live.items() if v["partial_cost"]})
        check(t + "partial-cost channels never ranked", not (set(r["rank_by_start"]) & o["partial"]))
        check(t + "nothing explained by mix (source is drawn independently of role and site)",
              r["explained_by_mix"] == [], r["explained_by_mix"])
        check(t + "spend and volume peak together: the seasonal confound is named", r["seasonal_confound"])
        check(t + "no saturation claim is made without the season caveat",
              not any(e["read"] == "falls" for e in r["elasticity"]))
        check(t + "labels and volumes reconcile", not r["reconcile"]["only_in_pipeline"]
              and not r["reconcile"]["only_in_spend"] and not r["reconcile"]["volume_gaps"], r["reconcile"])
        p = r["proposal"]
        check(t + "a proposal never sends money to a partial-cost channel", p is None or p["to"] not in o["partial"])
        check(t + "a proposal is bounded and positive", p is None or (p["shift_pct"] <= 20
                                                                      and p["net_starts_per_month"] > 0))
        check(t + "a move towards the cheap channel says how many more applications it adds to screen",
              p is None or p["to"] != cheap or p["extra_applications_per_month"] > 0)
        # the break-even: just under it the cheap channel stays first, just over it it does not
        be = r["breakeven"]
        if r["rank_by_start"][0] == cheap and be and be["dollars_per_application"]:
            k = be["dollars_per_application"]
            lo = analyse(pipe, sp, screen_minutes=(k * 0.9) / 18 * 60, hourly=18)
            hi = analyse(pipe, sp, screen_minutes=(k * 1.1) / 18 * 60, hourly=18)
            lo_first = sorted(lo["rank_by_start"], key=lambda c: lo["ladder"][c]["allin_cps"])[0]
            hi_first = sorted(hi["rank_by_start"], key=lambda c: hi["ladder"][c]["allin_cps"])[0]
            check(t + "break-even is exact: 10% under it the cheap channel stays first", lo_first == cheap,
                  (k, lo_first))
            check(t + "and 10% over it, it does not", hi_first != cheap, (k, hi_first))
        check(t + "screening time priced at 10 min x $18 matches the planted lead",
              (analyse(pipe, sp, screen_minutes=10, hourly=18)["rank_all_in"][0] == cheap) == o["still_first_at_10"])
        early = analyse(pipe, sp, as_of=dt.date(2026, 8, 20))
        check(t + "starts without a full 30 days are left out, and counted", early["excluded_recent_starts"] > 0)

    pipe = os.path.join(data, "frontline_pipeline_sample.csv")
    spend = os.path.join(data, "sourcing_spend_sample.csv")
    tmp = tempfile.mkdtemp(prefix="sra-")
    try:
        rows = list(csv.reader(open(pipe, encoding="utf-8")))
        srows = list(csv.reader(open(spend, encoding="utf-8")))

        def write(name, rr):
            p = os.path.join(tmp, name)
            with open(p, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rr)
            return p

        # label mismatch: "Job Board A" in spend
        s2 = [srows[0]] + [[r[0], "Job Board A" if r[1] == "jobboard_a" else r[1]] + r[2:] for r in srows[1:]]
        r = analyse(pipe, write("s2.csv", s2))
        check("label variants are merged and reported", any("Job Board A" in m for m in r["reconcile"]["merged_labels"]))
        # a channel missing from spend
        s3 = [srows[0]] + [r for r in srows[1:] if r[1] != "jobboard_b"]
        r = analyse(pipe, write("s3.csv", s3))
        check("a channel with no spend rows is reported", "jobboard_b" in r["reconcile"]["only_in_pipeline"])
        check("and is labelled partial cost, not cheap", r["ladder"]["jobboard_b"]["partial_cost"])
        # a volume disagreement
        s4 = [srows[0]] + [[r[0], r[1], str(int(int(r[2]) * 1.4)) if (r[1] == "social" and r[0] == "2025-10")
                            else r[2], r[3]] for r in srows[1:]]
        r = analyse(pipe, write("s4.csv", s4))
        check("a 40% volume gap is reported", any(g["channel"] == "social" and g["month"] == "2025-10"
                                                  for g in r["reconcile"]["volume_gaps"]))
        # a missing month in spend
        s5 = [srows[0]] + [r for r in srows[1:] if r[0] != "2026-01"]
        r = analyse(pipe, write("s5.csv", s5))
        check("a month missing from spend is reported and left out",
              "2026-01" in r["reconcile"]["months_missing_in_spend"])
        # mix confound planted: make jobboard_b look bad only because it is bought for the hard role
        hdr = rows[0]
        si, ri, sti = hdr.index("source"), hdr.index("role"), hdr.index("stage_reached")
        fsi = hdr.index("first_shift_at")
        rng = random.Random(4)
        conf = [hdr]
        for row in rows[1:]:
            row = list(row)
            role_hard = row[ri] == "Seasonal Associate"
            if row[si] == "jobboard_b":
                row[ri] = "Seasonal Associate" if rng.random() < 0.85 else row[ri]
            elif role_hard and rng.random() < 0.6:
                row[ri] = "Sales Associate"
            if row[ri] == "Seasonal Associate" and row[fsi] and rng.random() < 0.55:
                row[fsi] = ""
                row[sti] = "onboarding_started"
            conf.append(row)
        r = analyse(write("conf.csv", conf), spend)
        check("a channel bought for the hardest role is explained by role mix",
              any(e["channel"] == "jobboard_b" and e["by"] == "role" for e in r["explained_by_mix"]),
              r["explained_by_mix"])
        check("a channel explained by mix is never the proposal's source or target",
              not r["proposal"] or "jobboard_b" not in (r["proposal"]["from"], r["proposal"]["to"]))

        def refused(prows_, srows_):
            try:
                analyse(write("rp.csv", prows_), write("rs.csv", srows_))
                return False
            except Refusal:
                return True
        check("refuses a name column", refused([rows[0] + ["candidate_name"]] + [r + ["x"] for r in rows[1:]], srows))
        check("refuses an email column", refused([rows[0] + ["email"]] + [r + [""] for r in rows[1:]], srows))
        check("refuses emails in a cell", refused([rows[0] + ["ref"]] + [r + ["jo@acme.com"] for r in rows[1:]], srows))
        check("refuses a thin file", refused(rows[:300], srows))
        check("refuses duplicate application ids", refused(rows + [rows[1]], srows))
        check("refuses a pipeline without a start signal",
              refused([[c for c in r[:fsi]] + r[fsi + 1:sti] + r[sti + 1:] for r in rows], srows))
        check("refuses negative spend", refused(rows, srows[:2] + [[srows[2][0], srows[2][1], srows[2][2], "-5"]]))
        check("refuses a bad month", refused(rows, srows[:2] + [["March", "jobboard_a", "10", "100"]]))
        check("refuses spend with no months in the pipeline window",
              refused(rows, [srows[0], ["2030-01", "jobboard_a", "10", "100"]]))
        # formats
        semi = os.path.join(tmp, "semi.csv")
        with open(semi, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh, delimiter=";").writerows(rows)
        check("reads a semicolon export", analyse(semi, spend)["applications"] > 0)
        s6 = [srows[0]] + [[r[0], r[1], r[2], "$" + f"{float(r[3]):,.2f}"] for r in srows[1:]]
        r = analyse(pipe, write("s6.csv", s6))
        check("reads '$1,234.56' spend", abs(r["ladder"]["jobboard_a"]["spend"]
                                             - analyse(pipe, spend)["ladder"]["jobboard_a"]["spend"]) < 0.01)
        # no retention columns: still works, no 30-day ranking
        cut = [c for c in ("separation_at", "tenure_days", "separation_reason")]
        idx = [i for i, h in enumerate(rows[0]) if h not in cut]
        r = analyse(write("noret.csv", [[row[i] for i in idx] for row in rows]), spend)
        check("without retention columns, ranks per start and says nothing per retained hire",
              r["rank_by_retained"] == [] and r["proposal"]["metric"] == "cps")
        # outputs
        r = analyse(pipe, spend)
        hp = os.path.join(tmp, "r.html")
        render(r, hp)
        check("html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        check("json serialisable", bool(json.dumps(r, default=str)))
        t = text(r)
        check("text names last-touch attribution", "last touch" in t)
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: missing file exits 3", main(["--pipeline", "nope.csv", "--spend", spend]) == 3)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


# ------------------------------------------------------------------ main

def main(argv):
    if "--test" in argv:
        return run_tests()

    def opt(name):
        if name not in argv:
            return None
        i = argv.index(name) + 1
        if i >= len(argv) or argv[i].startswith("--"):
            raise Refusal(f"{name} needs a value.")
        return argv[i]

    try:
        if "--demo" in argv:
            d = _data_dir()
            if not d:
                raise Refusal("the sample dataset is not in this copy of the skill.")
            argv = argv + ["--pipeline", os.path.join(d, "frontline_pipeline_sample.csv"),
                           "--spend", os.path.join(d, "sourcing_spend_sample.csv")]
        if opt("--pipeline") or opt("--spend"):
            if not (opt("--pipeline") and opt("--spend")):
                raise Refusal("both --pipeline and --spend are needed.")
            as_of = opt("--as-of")
            if as_of:
                try:
                    as_of = dt.date.fromisoformat(as_of)
                except ValueError:
                    raise Refusal("--as-of should look like 2026-08-31.")
            shift = opt("--shift")
            try:
                shift = int(shift) if shift else 15
            except ValueError:
                raise Refusal("--shift is a whole percentage.")
            if not 1 <= shift <= 20:
                raise Refusal("--shift is capped at 20%: move budget in increments and re-measure.")
            sm, hr = opt("--screen-minutes"), opt("--hourly")
            if bool(sm) != bool(hr):
                raise Refusal("--screen-minutes and --hourly go together.")
            try:
                sm, hr = (float(sm), float(hr)) if sm else (None, None)
            except ValueError:
                raise Refusal("--screen-minutes and --hourly are numbers.")
            if sm is not None and not (0 < sm <= 120 and 0 < hr <= 500):
                raise Refusal("--screen-minutes must be 1 to 120 and --hourly 1 to 500.")
            r = analyse(opt("--pipeline"), opt("--spend"), as_of, shift, sm, hr)
            print(text(r))
            if opt("--html"):
                render(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1, default=str)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, not a "
              "finding about your data.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
