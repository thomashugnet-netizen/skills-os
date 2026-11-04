#!/usr/bin/env python3
"""
Recruiter capacity engine: rebuilds each recruiter's weekly load from the
applications they owned, finds the load where screening starts to slow down,
tells capacity from process, and ranks automation by hours returned.

    python3 capacity.py --export export.csv [--roster roster.csv] [--tasks tasks.csv]
                        [--target-days 2] [--owner-column recruiter_id]
                        [--html report.html] [--json report.json]
    python3 capacity.py --demo
    python3 capacity.py --test

export.csv  one row per application: application_id, recruiter_id (or owner_id),
            applied_at, screened_at; and when you have them role, region,
            interview_scheduled_at, reschedules, offer_at, hiring_manager_id,
            exit_reason. Opaque ids only.
roster.csv  week (the Monday), recruiter_id, available_days (0-5). Optional, but
            without it a recruiter on leave looks like a slow recruiter.
tasks.csv   task, data_key, per_month, minutes, automatable, effort, eliminate.
            Minutes are yours: without them tasks are ranked by frequency only.

What it reports:
  load       per recruiter per week: applications, screens, bookings,
             reschedules, offers, managers in play; per available day with a roster
  the knee   the weekly load above which the screening wait rises faster than
             load, fitted within each recruiter and role, or "cannot be located"
  checks     whether the knee survives inside ordinary weeks (season), without
             the role adjustment, and without the roster
  diagnosis  per recruiter: capacity, process (rework), upstream (volume that
             never progresses), individual, or room to spare
  headcount  only when the diagnosis is capacity, at the knee
  automation hours a month returned, ranked, with the eliminate-instead list

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
SAMPLE = os.path.join(SKILL_DIR, "references", "sample")

MIN_SCREENS_WEEK = 10     # a recruiter-week needs this many screens to carry a wait
MIN_SIDE = 12             # points needed each side of a knee
MIN_GAIN = 0.15           # the hinge must cut the residual error by this much
UPSTREAM_SHARE = 0.6      # applications never screened
REWORK_SHARE = 0.3        # reschedules per booking
INDIVIDUAL_DAYS = 1.0     # slower than the team at light load, role-adjusted
EFFORT = {"s": 1, "m": 2, "l": 4, "small": 1, "medium": 2, "large": 4}
NOMINATIVE = re.compile(r"(^|_)(first|last|full)?_?name($|_)|e-?mail|phone|mobile|address|street|zip|postcode|"
                        r"ssn|dob|birth|notes?$|comment", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ reading

def read_csv(path, what, people=True):
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
        header = [h.strip().lower().replace(" ", "_") for h in next(rows)]
    except StopIteration:
        raise Refusal(f"{what}: the file is empty.")
    for h in header if people else []:
        if NOMINATIVE.search(h):
            raise Refusal(f"{what}: column '{h}' looks like personal information. Re-export with opaque ids: "
                          "nothing here needs to know who anybody is, recruiters included.")
    out = [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)}
           for r in rows if any(c.strip() for c in r)]
    if EMAIL.search("".join(",".join(r.values()) for r in out[:3000])):
        raise Refusal(f"{what}: the file contains email addresses. Use opaque ids.")
    return header, out


def day(s):
    s = (s or "").strip()[:10]
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return None


def monday(d):
    return d - dt.timedelta(days=d.weekday())


def median(xs):
    s = sorted(xs)
    n = len(s)
    return None if not n else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else None


def quantile(xs, q):
    s = sorted(xs)
    if not s:
        return None
    i = (len(s) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


# ------------------------------------------------------------------ fitting

def lstsq(X, y):
    """Normal equations for a few columns; X is a list of rows."""
    k = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    b = [sum(r[i] * v for r, v in zip(X, y)) for i in range(k)]
    for i in range(k):                       # Gauss-Jordan with partial pivoting
        p = max(range(i, k), key=lambda r: abs(A[r][i]))
        if abs(A[p][i]) < 1e-12:
            return None
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        for r in range(k):
            if r != i:
                f = A[r][i] / A[i][i]
                A[r] = [a - f * c for a, c in zip(A[r], A[i])]
                b[r] -= f * b[i]
    coef = [b[i] / A[i][i] for i in range(k)]
    sse = sum((v - sum(c * x for c, x in zip(coef, r))) ** 2 for r, v in zip(X, y))
    return coef, sse


def fit_knee(points):
    """points: [(owner, load, wait)]. Each recruiter gets their own level; the load curve is shared.
    Returns the hinge model, or why it cannot be found, and the recruiter levels either way."""
    owners = sorted({p[0] for p in points})
    idx = {o: i for i, o in enumerate(owners)}

    def dummies(o):
        return [1.0 if idx[o] == i else 0.0 for i in range(len(owners))]
    if len(points) < 2 * MIN_SIDE:
        return {"found": False, "why": f"{len(points)} recruiter-weeks with enough screens; at least "
                                       f"{2 * MIN_SIDE} are needed.", "levels": {}}
    xs = [p[1] for p in points]
    y = [p[2] for p in points]
    mean_x = sum(xs) / len(xs)
    cv = math.sqrt(sum((x - mean_x) ** 2 for x in xs) / len(xs)) / mean_x if mean_x else 0
    lin = lstsq([dummies(o) + [x] for o, x, _ in points], y)
    levels = {o: round(lin[0][idx[o]], 3) for o in owners} if lin else {}
    if cv < 0.15:
        return {"found": False, "why": f"load barely varies across weeks (cv {cv:.2f}): there is no heavy week "
                                       "to compare a light one with.", "levels": levels}
    if lin is None:
        return {"found": False, "why": "load does not vary.", "levels": levels}
    best = None
    cands = sorted(set(round(quantile(xs, q / 100), 1) for q in range(15, 86, 2)))
    for k in cands:
        left = sum(1 for x in xs if x <= k)
        if left < MIN_SIDE or len(xs) - left < MIN_SIDE:
            continue
        f = lstsq([dummies(o) + [x, max(0.0, x - k)] for o, x, _ in points], y)
        if f and (best is None or f[1] < best[2]):
            best = (k, f[0], f[1])
    if best is None:
        return {"found": False, "why": "too few heavy or too few light weeks to place a knee.", "levels": levels}
    k, coef, sse = best
    c, b = coef[-2], coef[-1]
    gain = 1 - sse / lin[1] if lin[1] > 0 else 0
    after = c + b
    if gain < MIN_GAIN or b <= 0 or after < 3 * max(c, 0.002):
        return {"found": False, "why": f"the wait does not bend: a knee explains only {gain:.0%} more than a "
                                       "straight line.", "slope": round(lin[0][-1], 4), "levels": levels}
    return {"found": True, "knee": round(k, 1), "slope_before": round(c, 4), "slope_after": round(after, 4),
            "gain": round(gain, 2), "points": len(points), "above": sum(1 for x in xs if x > k),
            "levels": {o: round(coef[idx[o]], 3) for o in owners}}


# ------------------------------------------------------------------ analysis

def analyse(export, roster=None, tasks=None, target_days=2.0, owner_col=None):
    header, rows = read_csv(export, "export")
    oc = owner_col or next((c for c in ("recruiter_id", "owner_id", "recruiter") if c in header), None)
    if not oc or oc not in header:
        raise Refusal("export: no recruiter_id or owner_id column. Who owned each application is what this needs. "
                      "The library's pipeline samples have none: try the demo, or pass --owner-column "
                      "hiring_manager_id to read coordination load only.")
    for c in ("application_id", "applied_at"):
        if c not in header:
            raise Refusal(f"export: missing column '{c}'.")
    if "screened_at" not in header:
        raise Refusal("export: missing screened_at. The screening wait is the recruiter-controlled clock this "
                      "measures.")
    if len(rows) < 500:
        raise Refusal(f"export: {len(rows)} rows. At least 500 are needed to see load move.")

    avail = {}
    if roster:
        rh, rrows = read_csv(roster, "roster")
        for c in ("week", "recruiter_id", "available_days"):
            if c not in rh:
                raise Refusal(f"roster: missing column '{c}'.")
        for n, r in enumerate(rrows, 2):
            wk = day(r["week"])
            try:
                d = float(r["available_days"])
            except ValueError:
                raise Refusal(f"roster row {n}: available_days '{r['available_days']}' is not a number.")
            if wk is None or not 0 <= d <= 7:
                raise Refusal(f"roster row {n}: week must be a date and available_days 0 to 7.")
            avail[(monday(wk), r["recruiter_id"])] = d

    apps, seen = [], set()
    for r in rows:
        a = day(r["applied_at"])
        if a is None or not r.get(oc):
            continue
        if r["application_id"] in seen:
            raise Refusal(f"export: application_id {r['application_id']} appears twice.")
        seen.add(r["application_id"])
        s = day(r.get("screened_at", ""))
        try:
            res = int(float(r.get("reschedules") or 0))
        except ValueError:
            res = 0
        apps.append({"owner": r[oc], "week": monday(a), "applied": a, "screened": s,
                     "wait": (s - a).days if s and s >= a else None, "role": r.get("role") or "-",
                     "booked": bool(day(r.get("interview_scheduled_at", ""))), "res": max(0, res),
                     "offer": bool(day(r.get("offer_at", ""))), "mgr": r.get("hiring_manager_id") or None,
                     "month": a.strftime("%Y-%m")})
    if not apps:
        raise Refusal("export: no row has both an owner and a readable applied_at.")
    owners = sorted({x["owner"] for x in apps})
    if len(owners) < 2:
        raise Refusal("export: one recruiter only. Capacity is read against other recruiters and other weeks.")

    # role centring: a supervisor application takes longer to screen for everyone
    # means, not medians: waits are whole days, and a median of whole days moves in steps of one
    role_med = {}
    for role in {x["role"] for x in apps}:
        w = [x["wait"] for x in apps if x["role"] == role and x["wait"] is not None]
        role_med[role] = mean(w) if len(w) >= 30 else None
    overall = mean([x["wait"] for x in apps if x["wait"] is not None]) or 0
    for x in apps:
        rm = role_med.get(x["role"])
        x["cwait"] = None if x["wait"] is None else x["wait"] - ((rm - overall) if rm is not None else 0)

    # weekly load
    weeks = {}
    for x in apps:
        k = (x["owner"], x["week"])
        w = weeks.setdefault(k, {"owner": x["owner"], "week": x["week"], "apps": 0, "screens": 0, "booked": 0,
                                 "res": 0, "offers": 0, "mgrs": set(), "waits": [], "cwaits": []})
        w["apps"] += 1
        w["screens"] += 1 if x["screened"] else 0
        w["booked"] += 1 if x["booked"] else 0
        w["res"] += x["res"]
        w["offers"] += 1 if x["offer"] else 0
        if x["mgr"]:
            w["mgrs"].add(x["mgr"])
        if x["wait"] is not None:
            w["waits"].append(x["wait"])
            w["cwaits"].append(x["cwait"])
    for w in weeks.values():
        d = avail.get((w["week"], w["owner"]), 5.0)
        w["available"] = d
        w["load"] = w["apps"] * 5 / d if d > 0 else None
        w["wait"] = round(mean(w["waits"]), 2) if len(w["waits"]) >= MIN_SCREENS_WEEK else None
        w["cwait"] = mean(w["cwaits"]) if len(w["cwaits"]) >= MIN_SCREENS_WEEK else None
        w["mgrs"] = len(w["mgrs"])

    def points(key="cwait", use_roster=True, keep=None):
        pts = []
        for w in weeks.values():
            if w[key] is None or not w["load"]:
                continue
            if keep and not keep(w):
                continue
            pts.append((w["owner"], (w["load"] if use_roster else w["apps"]), w[key]))
        return pts

    knee = fit_knee(points())
    checks = {}
    team_week = {}
    for w in weeks.values():
        team_week[w["week"]] = team_week.get(w["week"], 0) + w["apps"]
    busy_cut = quantile(list(team_week.values()), 0.75)
    busy = {wk for wk, n in team_week.items() if n > busy_cut}
    ordinary = fit_knee(points(keep=lambda w: w["week"] not in busy))
    checks["season"] = {"busy_weeks": len(busy), "ordinary": ordinary}
    if knee["found"]:
        if ordinary["found"] and abs(ordinary["knee"] - knee["knee"]) <= 0.2 * knee["knee"]:
            checks["season"]["verdict"] = "survives"
        elif ordinary["found"]:
            checks["season"]["verdict"] = "moves"
        else:
            checks["season"]["verdict"] = "not_testable" if "too few" in ordinary["why"] or \
                "barely varies" in ordinary["why"] or "needed" in ordinary["why"] else "season"
    raw_role = fit_knee(points(key="wait"))
    checks["role"] = {"without_role_adjustment": raw_role}
    if roster:
        checks["roster"] = {"without_roster": fit_knee(points(use_roster=False))}

    # recruiter diagnosis
    base_c = knee.get("levels", {})
    team_base = median([v for v in base_c.values() if v is not None])
    per = {}
    for o in owners:
        ws = [w for w in weeks.values() if w["owner"] == o]
        n_apps = sum(w["apps"] for w in ws)
        never = sum(1 for x in apps if x["owner"] == o and not x["screened"])
        booked = sum(w["booked"] for w in ws)
        res = sum(w["res"] for w in ws)
        loads = [w["load"] for w in ws if w["load"]]
        above = sum(1 for l in loads if knee.get("found") and l > knee["knee"])
        raw = mean([x["wait"] for x in apps if x["owner"] == o and x["wait"] is not None])
        raw = None if raw is None else round(raw, 2)
        p = {"weeks": len(ws), "applications": n_apps, "median_load": round(median(loads), 1) if loads else None,
             "weeks_above_knee": above if knee.get("found") else None,
             "never_screened": round(never / n_apps, 2) if n_apps else None,
             "rework": round(res / booked, 2) if booked else None,
             "raw_wait": raw, "level_role_adjusted": None if base_c.get(o) is None else round(base_c[o], 2),
             "gap_to_team": None if base_c.get(o) is None or team_base is None else round(base_c[o] - team_base, 2)}
        reasons = []
        if p["never_screened"] is not None and p["never_screened"] >= UPSTREAM_SHARE:
            reasons.append("upstream")
        if p["rework"] is not None and p["rework"] >= REWORK_SHARE:
            reasons.append("process")
        if p["gap_to_team"] is not None and p["gap_to_team"] >= INDIVIDUAL_DAYS:
            reasons.append("individual")
        if knee.get("found") and loads and above / len(loads) >= 0.25:
            reasons.append("capacity")
        if "upstream" in reasons and "capacity" in reasons:
            reasons.remove("capacity")      # the load is mostly volume that never progresses: fix that, re-measure
        if not reasons:
            reasons.append("room" if knee.get("found") and loads and max(loads) <= knee["knee"] else "fine")
        p["diagnosis"] = reasons
        per[o] = p

    # how much of each recruiter's raw wait is the roles they hold
    expl = []
    for o, p in per.items():
        d = [x["wait"] - x["cwait"] for x in apps if x["owner"] == o and x["wait"] is not None]
        eff = mean(d) if d else 0
        p["role_effect"] = round(eff, 2)
        if eff >= 0.25 and "individual" not in p["diagnosis"]:
            expl.append((o, round(eff, 1)))
    checks["role"]["explained_by_role"] = expl

    # team-level process: slow even when light
    team_light = median([w["wait"] for w in weeks.values() if w["wait"] is not None and w["load"]
                         and (not knee.get("found") or w["load"] <= knee["knee"])])
    team_light = None if team_light is None else round(team_light, 2)
    team = {"light_week_wait": team_light, "target_days": target_days,
            "process_everywhere": team_light is not None and target_days is not None and team_light > target_days}

    # headcount, only if capacity is the diagnosis somewhere and the knee is known
    headcount = None
    if knee.get("found") and any("capacity" in p["diagnosis"] for p in per.values()):
        recent = sorted(team_week)[-8:]
        avg = sum(team_week[w] for w in recent) / len(recent)
        peak = max(team_week.values())
        cap = knee["knee"] * 0.9
        avail_fte = []
        for wk in recent:
            avail_fte.append(sum(avail.get((wk, o), 5.0) for o in owners if (o, wk) in weeks) / 5)
        upstream_apps = sum(per[o]["applications"] * per[o]["never_screened"] for o in owners
                            if "upstream" in per[o]["diagnosis"]) / max(1, len({x['week'] for x in apps}))
        headcount = {"weekly_applications_recent": round(avg), "weekly_applications_peak": peak,
                     "load_per_recruiter_at_90pct_knee": round(cap, 1),
                     "recruiters_needed_recent": round(avg / cap, 1), "recruiters_needed_peak": round(peak / cap, 1),
                     "recruiters_available_recent": round(sum(avail_fte) / len(avail_fte), 1),
                     "never_screened_per_week_upstream": round(upstream_apps)}

    # automation
    span_days = (max(x["applied"] for x in apps) - min(x["applied"] for x in apps)).days + 7
    months = span_days / 30.44
    freq = {"applications": len(apps), "screens": sum(1 for x in apps if x["screened"]),
            "bookings": sum(1 for x in apps if x["booked"]), "reschedules": sum(x["res"] for x in apps),
            "reminders": 2 * sum(1 for x in apps if x["booked"]), "offers": sum(1 for x in apps if x["offer"]),
            "manager_updates": sum(w["mgrs"] for w in weeks.values())}
    freq = {k: v / months for k, v in freq.items()}
    auto = None
    if tasks:
        th, trows = read_csv(tasks, "tasks", people=False)
        if "task" not in th:
            raise Refusal("tasks: missing column 'task'.")
        items = []
        for n, t in enumerate(trows, 2):
            key = t.get("data_key", "").strip().lower()
            pm = t.get("per_month", "").strip()
            try:
                per_month = float(pm) if pm else (freq[key] if key in freq else None)
            except ValueError:
                raise Refusal(f"tasks row {n}: per_month '{pm}' is not a number.")
            if key and key not in freq and not pm:
                raise Refusal(f"tasks row {n}: data_key '{key}' is not one of {', '.join(freq)}.")
            try:
                minutes = float(t["minutes"]) if t.get("minutes", "").strip() else None
                share = float(t["automatable"]) if t.get("automatable", "").strip() else None
            except ValueError:
                raise Refusal(f"tasks row {n}: minutes and automatable must be numbers.")
            if share is not None and not 0 <= share <= 1:
                raise Refusal(f"tasks row {n}: automatable is a share from 0 to 1.")
            if minutes is not None and minutes < 0:
                raise Refusal(f"tasks row {n}: minutes cannot be negative.")
            effort = EFFORT.get(t.get("effort", "").strip().lower(), 2)
            elim = t.get("eliminate", "").strip().lower() in ("yes", "y", "true", "1")
            hours = None
            if per_month is not None and minutes is not None:
                hours = per_month * minutes * (1.0 if elim else (share if share is not None else 0.5)) / 60
            items.append({"task": t["task"], "per_month": None if per_month is None else round(per_month),
                          "minutes": minutes, "automatable": share, "effort": effort, "eliminate": elim,
                          "hours": None if hours is None else round(hours, 1),
                          "score": None if hours is None else round(hours / effort, 1),
                          "derived": bool(key and not pm)})
        ranked = sorted([i for i in items if i["hours"] is not None and not i["eliminate"]],
                        key=lambda i: -i["score"])
        auto = {"ranked": ranked, "eliminate": [i for i in items if i["eliminate"]],
                "unpriced": [i for i in items if i["hours"] is None and not i["eliminate"]],
                "total_hours": round(sum(i["hours"] for i in items if i["hours"] is not None), 1)}

    return {"owner_column": oc, "recruiters": owners, "weeks": len({x["week"] for x in apps}),
            "applications": len(apps), "roster": bool(roster), "knee": knee, "checks": checks,
            "recruiter": per, "team": team, "headcount": headcount, "automation": auto,
            "frequencies_per_month": {k: round(v) for k, v in freq.items()},
            "weekly": [{"owner": w["owner"], "week": w["week"].isoformat(), "applications": w["apps"],
                        "screens": w["screens"], "bookings": w["booked"], "reschedules": w["res"],
                        "offers": w["offers"], "managers": w["mgrs"], "available_days": w["available"],
                        "load_per_available": None if w["load"] is None else round(w["load"], 1),
                        "median_wait": w["wait"]} for w in sorted(weeks.values(), key=lambda w: (w["owner"],
                                                                                                   w["week"]))]}


# ------------------------------------------------------------------ output

DIAG = {"capacity": "capacity: above the knee often enough that more hands or less demand is the fix",
        "process": "process: a large share of bookings are reschedules; the rework is the fix",
        "upstream": "upstream: most of the volume never gets past the form; fix sourcing or knockouts first",
        "individual": "individual: slower than the team at the same load, within role; a conversation, not a plan",
        "room": "room to spare: never above the knee",
        "fine": "no problem the data can see"}


def text(r):
    k = r["knee"]
    unit = "applications a week per available recruiter" if r["roster"] else "applications a week per recruiter"
    L = [f"Recruiter capacity: {len(r['recruiters'])} recruiters ({r['owner_column']}), {r['weeks']} weeks, "
         f"{r['applications']:,} applications."]
    if r["owner_column"] == "hiring_manager_id":
        L.append("Owners are hiring managers, not recruiters: this reads coordination load only.")
    if not r["roster"]:
        L.append("No roster: a recruiter on leave looks like a recruiter under load. Add one if you have it.")
    L.append("")
    if k["found"]:
        L.append(f"The knee: about {round(k['knee'])} {unit}. Below it the screening wait barely moves "
                 f"({k['slope_before'] * 10:+.2f} days per 10 more applications); above it, "
                 f"{k['slope_after'] * 10:+.2f} days per 10. {k['above']} of {k['points']} recruiter-weeks sat "
                 f"above it.")
    else:
        L.append(f"The knee cannot be located: {k['why']}")
    s = r["checks"].get("season", {})
    v = s.get("verdict")
    if v == "survives":
        L.append(f"  Season: refitted without the {s['busy_weeks']} busiest weeks, the knee is "
                 f"{round(s['ordinary']['knee'])}: it is load, not the calendar.")
    elif v == "moves":
        L.append(f"  Season: without the busiest weeks the knee moves to {round(s['ordinary']['knee'])}. Part of what "
                 "looked like load is the season.")
    elif v == "season":
        L.append("  Season: without the busiest weeks there is no knee. This is the calendar, not capacity.")
    elif v == "not_testable":
        L.append("  Season: too few ordinary weeks to refit; the knee is not tested against the calendar.")
    rr = r["checks"]["role"]["without_role_adjustment"]
    expl = r["checks"]["role"].get("explained_by_role", [])
    L.append("  Role mix: " + (f"without the role adjustment the knee reads {round(rr['knee'])}." if rr["found"]
                               else "without the role adjustment no knee appears: the role mix hides it.")
             + ("".join(f" {o}'s screening waits run {g:+.1f} days longer than on an average role mix: the roles "
                        f"they hold take longer for everyone, so this is not {o}." for o, g in expl)))
    if "roster" in r["checks"]:
        wr = r["checks"]["roster"]["without_roster"]
        L.append("  Leave: " + (f"without the roster the knee reads {round(wr['knee'])} (gain {wr['gain']:.0%} against "
                                f"{k.get('gain', 0):.0%} with it)." if wr["found"]
                                else "without the roster no knee appears: leave weeks hide it."))
    L.append("")
    L.append("Each recruiter")
    for o in r["recruiters"]:
        p = r["recruiter"][o]
        bits = [f"median load {p['median_load']:g}"]
        if p["weeks_above_knee"] is not None:
            bits.append(f"{p['weeks_above_knee']} of {p['weeks']} weeks above the knee")
        if p["never_screened"] is not None:
            bits.append(f"{round(p['never_screened'] * 100)}% never screened")
        if p["rework"] is not None:
            bits.append(f"{round(p['rework'] * 100)} reschedules per 100 bookings")
        if p["gap_to_team"] is not None:
            bits.append(f"{p['gap_to_team']:+.1f} days against the team at the same load, role-adjusted")
        L.append(f"  {o}: {'; '.join(DIAG[d] for d in p['diagnosis'])}")
        L.append(f"  {'':<{len(o)}}  ({', '.join(bits)})")
    t = r["team"]
    if t["process_everywhere"]:
        L.append(f"  The whole team waits {t['light_week_wait']:g} days to screen even in light weeks, above your "
                 f"{t['target_days']:g}-day target: a process problem. Adding people scales the delay.")
    h = r["headcount"]
    if h:
        L.append("")
        L.append("Headcount")
        L.append(f"  At 90% of the knee, a recruiter carries about {h['load_per_recruiter_at_90pct_knee']:g} "
                 f"applications a week. Recent weeks average {h['weekly_applications_recent']:,}: "
                 f"{h['recruiters_needed_recent']:g} recruiters, against {h['recruiters_available_recent']:g} "
                 f"available. The busiest week ({h['weekly_applications_peak']:,}) needs "
                 f"{h['recruiters_needed_peak']:g}.")
        if h["never_screened_per_week_upstream"]:
            L.append(f"  About {h['never_screened_per_week_upstream']:,} of those applications a week never get "
                     "past the form. Fix that before hiring against it.")
    a = r["automation"]
    if a:
        L.append("")
        L.append("Automation, ranked by hours a month returned per unit of effort")
        for i in a["ranked"]:
            src = " (frequency from your export)" if i["derived"] else ""
            eff = {1: "small", 2: "medium", 4: "large"}.get(i["effort"], "medium")
            L.append(f"  {i['hours']:>6g} h  {i['task']}: {i['per_month']:,}/month x {i['minutes']:g} min x "
                     f"{round((i['automatable'] if i['automatable'] is not None else 0.5) * 100)}% automatable, "
                     f"{eff} effort{src}")
        for i in a["eliminate"]:
            L.append(f"  Eliminate, do not automate: {i['task']}"
                     + (f" ({i['hours']:g} h a month back)" if i["hours"] is not None else ""))
        for i in a["unpriced"]:
            L.append(f"  Not ranked, no minutes given: {i['task']}"
                     + (f" ({i['per_month']:,} a month)" if i["per_month"] is not None else ""))
    L.append("")
    L.append("This reads weeks that have happened. It cannot see today's queue, check a handling time you gave it, "
             "or tell a slow week from a house move.")
    return "\n".join(L)


def render(r, path):
    e = html.escape
    rows = "".join(f"<tr><td>{e(o)}</td><td>{r['recruiter'][o]['median_load']}</td>"
                   f"<td>{e(', '.join(r['recruiter'][o]['diagnosis']))}</td></tr>" for o in r["recruiters"])
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Recruiter capacity</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px}}pre{{white-space:pre-wrap;font-size:13px}}</style>
<h1>Recruiter capacity</h1><table><tr><th>Recruiter</th><th>Median load</th><th>Diagnosis</th></tr>{rows}</table>
<pre>{e(text(r))}</pre></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

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
            print(f"FAIL {name}" + (f"  [{detail}]" if detail != "" else ""))

    exp = json.load(open(os.path.join(SAMPLE, "northline_expected.json"), encoding="utf-8"))
    ex = os.path.join(SAMPLE, "northline_recruiting.csv")
    ro = os.path.join(SAMPLE, "northline_roster.csv")
    ta = os.path.join(SAMPLE, "northline_tasks.csv")
    r = analyse(ex, ro, ta)
    k = r["knee"]
    check("sample: the knee is found", k["found"], k)
    check(f"sample: the knee is within 10% of the planted {exp['knee']}",
          k["found"] and abs(k["knee"] - exp["knee"]) <= 0.1 * exp["knee"], k.get("knee"))
    check("sample: flat below, steep above", k["found"] and k["slope_after"] >= 5 * max(k["slope_before"], 0.002))
    check("sample: the knee survives without the busiest weeks", r["checks"]["season"].get("verdict") == "survives",
          r["checks"]["season"])
    diag = {o: sorted(p["diagnosis"]) for o, p in r["recruiter"].items()}
    for o, want in exp["diagnosis"].items():
        check(f"sample: {o} diagnosed as planted", diag[o] == sorted(want), diag[o])
    check("sample: REC-02 looks slow raw but not role-adjusted",
          r["recruiter"]["REC-02"]["raw_wait"] > r["recruiter"]["REC-01"]["raw_wait"]
          and "individual" not in diag["REC-02"])
    check("sample: headcount offered, because capacity is a diagnosis", r["headcount"] is not None)
    check("sample: headcount names the volume that never gets past the form",
          r["headcount"] and r["headcount"]["never_screened_per_week_upstream"] > 0)
    top = r["automation"]["ranked"][0]["task"] if r["automation"]["ranked"] else None
    check(f"sample: the top automation is the one planted ({top})", top == exp["top_automation"])
    check("sample: eliminate-instead list as planted",
          [i["task"] for i in r["automation"]["eliminate"]] == exp["eliminate"])
    check("sample: a task with no minutes is not ranked", [i["task"] for i in r["automation"]["unpriced"]]
          == exp["unpriced"])
    nr = analyse(ex)
    check("without the roster, the leave weeks are not above the knee per day",
          not nr["roster"] and nr["knee"]["found"])
    t = text(r)
    check("text says what it cannot see", "cannot see today's queue" in t)

    tmp = tempfile.mkdtemp(prefix="rcp-")

    def write(name, rows_):
        p = os.path.join(tmp, name)
        with open(p, "w", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerows(rows_)
        return p
    try:
        rows = list(csv.reader(open(ex, encoding="utf-8")))
        hdr = rows[0]
        ai, si, oi = hdr.index("applied_at"), hdr.index("screened_at"), hdr.index("recruiter_id")
        rng = random.Random(3)
        # flat world: wait does not depend on load -> no knee
        flat = [hdr]
        for row in rows[1:]:
            row = list(row)
            if row[si]:
                a = dt.date.fromisoformat(row[ai])
                row[si] = (a + dt.timedelta(days=rng.choice([0, 1, 1, 2, 2, 3]))).isoformat()
            flat.append(row)
        f = analyse(write("flat.csv", flat))
        check("no load effect planted: no knee, and no headcount", not f["knee"]["found"] and f["headcount"] is None,
              f["knee"])
        # a straight line, no bend -> no knee
        loads = {}
        for row in rows[1:]:
            wk = monday(dt.date.fromisoformat(row[ai]))
            loads[(row[oi], wk)] = loads.get((row[oi], wk), 0) + 1
        lin = [hdr]
        for row in rows[1:]:
            row = list(row)
            if row[si]:
                a = dt.date.fromisoformat(row[ai])
                L_ = loads[(row[oi], monday(a))]
                row[si] = (a + dt.timedelta(days=max(0, round(L_ * 0.03 + rng.gauss(0, 0.5))))).isoformat()
            lin.append(row)
        l2 = analyse(write("lin.csv", lin))
        check("a straight-line effect is not called a knee", not l2["knee"]["found"], l2["knee"])
        # season only: busy weeks slower whatever the load -> knee must not survive
        tw = {}
        for row in rows[1:]:
            wk = monday(dt.date.fromisoformat(row[ai]))
            tw[wk] = tw.get(wk, 0) + 1
        cut = quantile(list(tw.values()), 0.75)
        sea = [hdr]
        for row in rows[1:]:
            row = list(row)
            if row[si]:
                a = dt.date.fromisoformat(row[ai])
                extra = 4 if tw[monday(a)] > cut else 0
                row[si] = (a + dt.timedelta(days=rng.choice([0, 1, 1, 2]) + extra)).isoformat()
            sea.append(row)
        s2 = analyse(write("sea.csv", sea))
        check("a pure season effect is never passed off as capacity",
              not s2["knee"]["found"] or s2["checks"]["season"].get("verdict") in ("season", "moves", "not_testable"),
              (s2["knee"], s2["checks"]["season"].get("verdict")))
        # everyone slow even in light weeks: process everywhere, and no headcount case built on it alone
        slow = [hdr]
        for row in rows[1:]:
            row = list(row)
            if row[si]:
                row[si] = (dt.date.fromisoformat(row[si]) + dt.timedelta(days=3)).isoformat()
            slow.append(row)
        sl = analyse(write("slow.csv", slow), ro)
        check("everyone slow at every load is a process problem", sl["team"]["process_everywhere"])
        check("the role check names REC-02 as explained by role",
              any(o == "REC-02" for o, _ in r["checks"]["role"]["explained_by_role"]))
        # an individual made out of a light recruiter: REC-07 two days slower
        ind = [hdr]
        for row in rows[1:]:
            row = list(row)
            if row[si] and row[oi] == "REC-07":
                row[si] = (dt.date.fromisoformat(row[si]) + dt.timedelta(days=2)).isoformat()
            ind.append(row)
        i2 = analyse(write("ind.csv", ind), ro)
        check("a slow recruiter who is never busy is still individual, not capacity",
              i2["recruiter"]["REC-07"]["diagnosis"] == ["individual"], i2["recruiter"]["REC-07"]["diagnosis"])
        # refusals
        def refused(fn):
            try:
                fn()
                return False
            except Refusal:
                return True
        check("refuses an export with no owner column",
              refused(lambda: analyse(write("no.csv", [[c for j, c in enumerate(rw) if j != oi] for rw in rows]))))
        check("refuses a name column", refused(lambda: analyse(write("n.csv", [hdr + ["recruiter_name"]] +
                                                                     [rw + ["x"] for rw in rows[1:]]))))
        check("refuses emails", refused(lambda: analyse(write("e.csv", [hdr + ["ref"]] +
                                                                [rw + ["a@b.co"] for rw in rows[1:]]))))
        check("refuses a thin file", refused(lambda: analyse(write("t.csv", rows[:200]))))
        check("refuses duplicate ids", refused(lambda: analyse(write("d.csv", rows + rows[1:3]))))
        check("refuses one recruiter", refused(lambda: analyse(write("one.csv", [hdr] + [rw for rw in rows[1:]
                                                                                       if rw[oi] == "REC-01"]))))
        check("refuses a bad roster", refused(lambda: analyse(ex, write("r.csv", [["week", "recruiter_id",
                                                                                  "available_days"],
                                                                                 ["2025-06-02", "REC-01", "nine"]]))))
        check("refuses a bad task share", refused(lambda: analyse(ex, None, write("tk.csv", [
            ["task", "data_key", "minutes", "automatable"], ["Book", "bookings", "4", "1.5"]]))))
        check("refuses an unknown data_key", refused(lambda: analyse(ex, None, write("tk2.csv", [
            ["task", "data_key", "minutes"], ["Book", "teleport", "4"]]))))
        mg = analyse(ex, owner_col="hiring_manager_id")
        check("--owner-column hiring_manager_id runs and says it is coordination only",
              "coordination load only" in text(mg))
        hp = os.path.join(tmp, "r.html")
        render(r, hp)
        check("html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        check("json serialisable", bool(json.dumps(r, default=str)))
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: demo exits 0", main(["--demo"]) == 0)
            check("main: missing file exits 3", main(["--export", os.path.join(tmp, "x.csv")]) == 3)
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
            argv = argv + ["--export", os.path.join(SAMPLE, "northline_recruiting.csv"),
                           "--roster", os.path.join(SAMPLE, "northline_roster.csv"),
                           "--tasks", os.path.join(SAMPLE, "northline_tasks.csv")]
        if opt("--export"):
            td = opt("--target-days")
            try:
                td = float(td) if td else 2.0
            except ValueError:
                raise Refusal("--target-days is a number of days.")
            r = analyse(opt("--export"), opt("--roster"), opt("--tasks"), td, opt("--owner-column"))
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
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, not a finding "
              "about your team.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
