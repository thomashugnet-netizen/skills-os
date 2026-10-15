#!/usr/bin/env python3
"""
Roster engine for schedule-photo-to-roster.

The model reads the photo. This script does everything after that, so the
numbers are arithmetic rather than impressions: same roster in, same findings
out, every run.

    python3 roster.py --roster roster.csv [--needs needs.csv] [--rules oregon]
                      [--rate 17.50] [--html report.html] [--json findings.json]
                      [--clean roster_clean.csv]
    python3 roster.py --list-rules
    python3 roster.py --test

Roster columns (one row per shift; days off have no row):
    person, role, date, start, end, break_minutes, confidence, note
    date YYYY-MM-DD; start/end HH:MM 24h; an end at or before the start means
    the shift runs past midnight. confidence is "high" or "low"; a low cell is
    one the photo did not make certain.

Needs columns (optional; without them only gaps and lone working are checked):
    day, start, end, min_staff, role
    day is a date, a weekday (mon..sun) or "all"; role is optional and, when
    given, only that role counts toward the need.

Standard library only, so it runs wherever the skill lands.
"""

import csv
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
RULES_PATH = os.path.join(SKILL, "references", "rules.json")
SAMPLE = os.path.join(SKILL, "references", "sample")
FIXTURES = os.path.join(SKILL, "references", "fixtures")

SLOT = 15                     # minutes; every coverage figure is built from these
MAX_SHIFT_HOURS = 16          # longer than this is almost always a misread
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
REQUIRED = ["person", "date", "start", "end"]
# A schedule needs a first name. It never needs a way to reach the person.
NOMINATIVE = re.compile(r"(?i)(phone|mobile|cell|e-?mail|address|ssn|social|dob|birth|national)")
EMAIL_VALUE = re.compile(r"[^\s@]+@[a-z0-9-]+\.[a-z]", re.I)


def looks_like_contact(value):
    """An email, or a run of nine or more digits written like a phone number."""
    if EMAIL_VALUE.search(value):
        return True
    return any(len(re.sub(r"\D", "", chunk)) >= 9
               for chunk in re.findall(r"\+?[\d][\d\s().-]{7,}\d", value))


class Refusal(Exception):
    """Input the engine will not analyse. The message says what to fix."""


# ------------------------------------------------------------------ loading

def _clock(value, row_no, field):
    v = (value or "").strip().lower().replace(".", ":")
    m = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?", v)
    if not m:
        raise Refusal(f"row {row_no}: {field} '{value}' is not a 24-hour time (HH:MM). "
                      "Convert am/pm before running, and leave nothing to interpretation.")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if h > 24 or mi > 59 or (h == 24 and mi):
        raise Refusal(f"row {row_no}: {field} '{value}' is not a valid time.")
    return h * 60 + mi


def _date(value, row_no):
    try:
        return datetime.strptime((value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        raise Refusal(f"row {row_no}: date '{value}' must be YYYY-MM-DD. "
                      "Use the week shown on the sheet to turn weekday columns into dates.")


def load_roster(path):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        cols = [c.strip().lower() for c in (reader.fieldnames or [])]
        rows = list(reader)
    if not cols:
        raise Refusal("the roster file is empty.")
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise Refusal("missing column(s): " + ", ".join(missing))
    bad = [c for c in cols if NOMINATIVE.search(c)]
    if bad:
        raise Refusal("column(s) " + ", ".join(bad) + " hold contact or identity details. "
                      "A schedule needs a first name or initials, never a way to reach "
                      "the person. Remove the column and run again.")
    shifts = []
    for i, raw in enumerate(rows, start=2):
        r = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        if not any(r.values()):
            continue
        for k, v in r.items():
            if k not in ("date", "start", "end", "break_minutes") and looks_like_contact(v):
                raise Refusal(f"row {i}: '{k}' looks like a phone number or email. "
                              "Remove contact details from the roster.")
        if not r.get("person"):
            raise Refusal(f"row {i}: no person.")
        d = _date(r.get("date"), i)
        s = _clock(r.get("start"), i, "start")
        e = _clock(r.get("end"), i, "end")
        start = datetime(d.year, d.month, d.day) + timedelta(minutes=s)
        end = datetime(d.year, d.month, d.day) + timedelta(minutes=e)
        if end <= start:
            end += timedelta(days=1)          # runs past midnight
        brk = r.get("break_minutes", "")
        shifts.append({
            "row": i,
            "person": r["person"],
            "role": r.get("role", "") or "",
            "date": d,
            "start": start,
            "end": end,
            "break": int(brk) if brk.isdigit() else None,
            "confidence": (r.get("confidence") or "high").lower(),
            "note": r.get("note", ""),
        })
    if not shifts:
        raise Refusal("the roster has no shifts.")
    return shifts


def load_needs(path):
    if not path:
        return []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    needs = []
    for i, raw in enumerate(rows, start=2):
        r = {k.strip().lower(): (v or "").strip() for k, v in raw.items() if k}
        day = r.get("day", "all").lower()[:10]
        if day not in WEEKDAYS + ["all"]:
            _date(day, i)
        if not r.get("min_staff", "").isdigit():
            raise Refusal(f"needs row {i}: min_staff must be a whole number.")
        needs.append({"day": day, "start": _clock(r.get("start"), i, "start"),
                      "end": _clock(r.get("end"), i, "end"),
                      "min": int(r["min_staff"]), "role": r.get("role", "")})
    return needs


def load_rules(key):
    data = json.load(open(RULES_PATH, encoding="utf-8"))
    table = data["jurisdictions"]
    key = (key or "none").lower()
    if key not in table:
        raise Refusal(f"unknown rules '{key}'. Known: " + ", ".join(sorted(table)))
    rule = dict(table[key])
    parent = rule.get("inherits")
    while parent:
        base = dict(table[parent])
        base.update({k: v for k, v in rule.items() if v is not None or k not in base})
        rule, parent = base, table[parent].get("inherits")
    rule["key"] = key
    rule["checked"] = data["checked"]
    return rule


# ----------------------------------------------------------------- analysis

def hours(minutes):
    return round(minutes / 60, 2)


def check_data(shifts):
    """Problems with the roster itself. These are reported first because every
    later number inherits them."""
    out = []
    for s in shifts:
        length = (s["end"] - s["start"]).total_seconds() / 3600
        if length > MAX_SHIFT_HOURS:
            out.append({"kind": "implausible_shift", "person": s["person"], "row": s["row"],
                        "date": s["date"].isoformat(), "hours": round(length, 2),
                        "text": f"{s['person']} on {s['date']:%a %d %b}: a {length:.1f}-hour shift. "
                                "Almost always a misread time. Check the photo."})
    low = [s for s in shifts if s["confidence"] == "low"]
    for s in low:
        out.append({"kind": "low_confidence", "person": s["person"], "row": s["row"],
                    "date": s["date"].isoformat(),
                    "text": f"{s['person']} on {s['date']:%a %d %b} "
                            f"({s['start']:%H:%M}-{s['end']:%H:%M}) was hard to read"
                            + (f": {s['note']}" if s["note"] else "") + ". Confirm it."})
    seen = defaultdict(list)
    for s in shifts:
        key = (s["person"].lower(), s["start"], s["end"])
        seen[key].append(s)
    for key, group in seen.items():
        if len(group) > 1:
            out.append({"kind": "duplicate", "person": group[0]["person"],
                        "row": group[1]["row"], "date": group[0]["date"].isoformat(),
                        "text": f"{group[0]['person']} appears twice for the same shift on "
                                f"{group[0]['date']:%a %d %b}. Counted once."})
    return out


def dedupe(shifts):
    keep, seen = [], set()
    for s in shifts:
        key = (s["person"].lower(), s["start"], s["end"])
        if key not in seen:
            seen.add(key)
            keep.append(s)
    return keep


def by_person(shifts):
    people = defaultdict(list)
    for s in shifts:
        people[s["person"]].append(s)
    for p in people:
        people[p].sort(key=lambda s: s["start"])
    return people


def paid_minutes(s):
    length = (s["end"] - s["start"]).total_seconds() / 60
    return length - (s["break"] or 0)


def check_people(shifts, rule):
    out = []
    people = by_person(shifts)
    min_rest = rule.get("min_rest_hours")
    weekly = rule.get("weekly_overtime_hours")
    daily = rule.get("daily_overtime_hours")
    double = rule.get("daily_double_time_hours")
    totals = {}
    for person, mine in people.items():
        total = sum(paid_minutes(s) for s in mine)
        totals[person] = total
        # conflicts: the same person in two places at once
        for a, b in zip(mine, mine[1:]):
            if b["start"] < a["end"]:
                out.append({"kind": "double_booked", "person": person,
                            "date": b["date"].isoformat(),
                            "text": f"{person} is on two overlapping shifts on {b['date']:%a %d %b} "
                                    f"({a['start']:%H:%M}-{a['end']:%H:%M} and "
                                    f"{b['start']:%H:%M}-{b['end']:%H:%M}). One of them is not real, "
                                    "and the coverage that depends on it is not either."})
        # rest between shifts
        for a, b in zip(mine, mine[1:]):
            gap = (b["start"] - a["end"]).total_seconds() / 3600
            if 0 <= gap < (min_rest or 0) and b["start"].date() != a["start"].date():
                out.append({"kind": "short_rest", "person": person, "date": b["date"].isoformat(),
                            "rest_hours": round(gap, 2), "threshold": min_rest,
                            "legal": bool(rule.get("rest_is_legal_rule")),
                            "text": f"{person} finishes {a['end']:%a %H:%M} and starts again "
                                    f"{b['start']:%a %H:%M}: {gap:.1f} hours between shifts "
                                    f"(threshold {min_rest:g})."})
        # daily overtime (California-shaped rules) then weekly on what is left
        daily_ot = double_ot = 0.0
        regular = 0.0
        per_day = defaultdict(float)
        for s in mine:
            per_day[s["start"].date()] += paid_minutes(s) / 60
        for d, h in per_day.items():
            if daily and h > daily:
                over = h - daily
                if double and h > double:
                    double_ot += h - double
                    over -= h - double
                daily_ot += over
                regular += min(h, daily)
            else:
                regular += h
        weekly_ot = max(0.0, regular - weekly) if weekly else 0.0
        if weekly_ot or daily_ot or double_ot:
            parts = []
            if weekly_ot:
                parts.append(f"{weekly_ot:g} over the {weekly:g}-hour week")
            if daily_ot:
                parts.append(f"{daily_ot:g} past {daily:g} hours in a day")
            if double_ot:
                parts.append(f"{double_ot:g} past {double:g} hours in a day")
            out.append({"kind": "overtime", "person": person, "hours_total": round(total / 60, 2),
                        "weekly_ot": round(weekly_ot, 2), "daily_ot": round(daily_ot, 2),
                        "double_ot": round(double_ot, 2),
                        "text": f"{person} is scheduled {total / 60:g} hours: "
                                + ", ".join(parts) + "."})
        # consecutive days
        days = sorted({s["start"].date() for s in mine})
        run = best = 1
        for a, b in zip(days, days[1:]):
            run = run + 1 if (b - a).days == 1 else 1
            best = max(best, run)
        if len(days) and best >= 7:
            out.append({"kind": "no_day_off", "person": person, "days": best,
                        "text": f"{person} works {best} days in a row with no day off."})
        # long shift, no break written down
        for s in mine:
            if paid_minutes(s) > 6 * 60 and s["break"] is None:
                out.append({"kind": "no_break_recorded", "person": person,
                            "date": s["date"].isoformat(),
                            "text": f"{person} on {s['date']:%a %d %b}: "
                                    f"{paid_minutes(s) / 60:g} hours with no break written on the schedule."})
    return out, totals


def slots_for(shifts):
    """Headcount per 15-minute slot, overall and by role."""
    total, roles = defaultdict(int), defaultdict(lambda: defaultdict(int))
    for s in shifts:
        t = s["start"]
        while t < s["end"]:
            total[t] += 1
            roles[s["role"].lower()][t] += 1
            t += timedelta(minutes=SLOT)
    return total, roles


def need_for(needs, t, role=None):
    day = t.date()
    best = None
    for n in needs:
        if (n["role"] or "").lower() != (role or ""):
            continue
        if n["day"] not in ("all", WEEKDAYS[day.weekday()], day.isoformat()):
            continue
        m = t.hour * 60 + t.minute
        end = n["end"] if n["end"] > n["start"] else 24 * 60
        if n["start"] <= m < end:
            best = n["min"] if best is None else max(best, n["min"])
    return best


def check_coverage(shifts, needs):
    total, roles = slots_for(shifts)
    days = sorted({s["start"].date() for s in shifts})
    out, grid = [], {}
    for d in days:
        if needs:
            open_slots = [datetime(d.year, d.month, d.day) + timedelta(minutes=m)
                          for m in range(0, 24 * 60, SLOT)
                          if need_for(needs, datetime(d.year, d.month, d.day) + timedelta(minutes=m)) is not None]
        else:
            mine = [s for s in shifts if s["start"].date() == d]
            first = min(s["start"] for s in mine)
            last = max(s["end"] for s in mine)
            open_slots = []
            t = first
            while t < last:
                open_slots.append(t)
                t += timedelta(minutes=SLOT)
        for t in open_slots:
            have = total.get(t, 0)
            need = need_for(needs, t) if needs else None
            grid[t] = (have, need)
        # windows: contiguous runs of a condition, reported as clock ranges
        def runs(cond):
            found, cur = [], None
            for t in open_slots:
                if cond(t):
                    cur = [t, t] if cur is None else [cur[0], t]
                else:
                    if cur:
                        found.append(cur)
                    cur = None
            if cur:
                found.append(cur)
            return found

        if needs:
            for a, b in runs(lambda t: grid[t][1] is not None and grid[t][0] < grid[t][1]):
                slots = []
                t = a
                while t <= b:
                    slots.append(grid[t])
                    t += timedelta(minutes=SLOT)
                gap = sum(n - h for h, n in slots) * SLOT / 60
                out.append({"kind": "understaffed", "date": d.isoformat(),
                            "from": a.strftime("%H:%M"),
                            "to": (b + timedelta(minutes=SLOT)).strftime("%H:%M"),
                            "person_hours": round(gap, 2),
                            "worst": min(h - n for h, n in slots),
                            "text": f"{d:%a %d %b} {a:%H:%M}-{b + timedelta(minutes=SLOT):%H:%M}: "
                                    f"short by up to {-min(h - n for h, n in slots)} "
                                    f"({gap:g} person-hours missing)."})
            # Surplus is only worth a line when it is two or more people for
            # two hours or more. One extra head at a handover is how shifts
            # overlap, not waste.
            for a, b in runs(lambda t: grid[t][1] is not None and grid[t][0] - grid[t][1] >= 2):
                slots = []
                t = a
                while t <= b:
                    slots.append(grid[t])
                    t += timedelta(minutes=SLOT)
                extra = sum(h - n for h, n in slots) * SLOT / 60
                if len(slots) * SLOT >= 120:
                    out.append({"kind": "overstaffed", "date": d.isoformat(),
                                "from": a.strftime("%H:%M"),
                                "to": (b + timedelta(minutes=SLOT)).strftime("%H:%M"),
                                "person_hours": round(extra, 2),
                                "text": f"{d:%a %d %b} {a:%H:%M}-{b + timedelta(minutes=SLOT):%H:%M}: "
                                        f"{extra:g} person-hours above what you said you need."})
            for role in sorted({(n["role"] or "").lower() for n in needs if n["role"]}):
                for a, b in runs(lambda t: need_for(needs, t, role) is not None
                                 and roles[role].get(t, 0) < need_for(needs, t, role)):
                    out.append({"kind": "role_gap", "date": d.isoformat(), "role": role,
                                "from": a.strftime("%H:%M"),
                                "to": (b + timedelta(minutes=SLOT)).strftime("%H:%M"),
                                "text": f"{d:%a %d %b} {a:%H:%M}-{b + timedelta(minutes=SLOT):%H:%M}: "
                                        f"no {role} on the floor."})
        else:
            for a, b in runs(lambda t: grid[t][0] == 0):
                out.append({"kind": "uncovered", "date": d.isoformat(), "from": a.strftime("%H:%M"),
                            "to": (b + timedelta(minutes=SLOT)).strftime("%H:%M"),
                            "text": f"{d:%a %d %b} {a:%H:%M}-{b + timedelta(minutes=SLOT):%H:%M}: "
                                    "nobody scheduled, between people who are."})
            for a, b in runs(lambda t: grid[t][0] == 1):
                length = ((b - a).total_seconds() / 60 + SLOT) / 60
                if length >= 1:
                    out.append({"kind": "lone_working", "date": d.isoformat(),
                                "from": a.strftime("%H:%M"),
                                "to": (b + timedelta(minutes=SLOT)).strftime("%H:%M"),
                                "text": f"{d:%a %d %b} {a:%H:%M}-{b + timedelta(minutes=SLOT):%H:%M}: "
                                        "one person alone on site."})
    return out, grid


def analyse(roster_path, needs_path=None, rules_key=None, rate=None):
    shifts = load_roster(roster_path)
    needs = load_needs(needs_path)
    rule = load_rules(rules_key)
    data = check_data(shifts)
    shifts = dedupe(shifts)
    people, totals = check_people(shifts, rule)
    coverage, grid = check_coverage(shifts, needs)
    findings = data + coverage + people

    under = sum(f["person_hours"] for f in findings if f["kind"] == "understaffed")
    over = sum(f["person_hours"] for f in findings if f["kind"] == "overstaffed")
    ot = sum(f["weekly_ot"] + f["daily_ot"] + f["double_ot"] for f in findings if f["kind"] == "overtime")
    dt = sum(f["double_ot"] for f in findings if f["kind"] == "overtime")
    headline = {
        "shifts": len(shifts),
        "people": len(totals),
        "scheduled_hours": round(sum(totals.values()) / 60, 2),
        "understaffed_person_hours": round(under, 2),
        "overstaffed_person_hours": round(over, 2),
        "overtime_hours": round(ot, 2),
        "short_rest": sum(1 for f in findings if f["kind"] == "short_rest"),
        "double_booked": sum(1 for f in findings if f["kind"] == "double_booked"),
        "to_confirm": sum(1 for f in findings if f["kind"] in ("low_confidence", "implausible_shift")),
    }
    if rate:
        # Premium only: the straight-time half of an overtime hour is pay you
        # would owe whoever worked it. The premium is what the schedule adds.
        headline["overtime_premium"] = round((ot - dt) * rate * 0.5 + dt * rate * 1.0, 2)
    spare = sorted((round(m / 60, 2), p) for p, m in totals.items())
    ot_people = {f["person"] for f in findings if f["kind"] == "overtime"}
    role_of = {s["person"]: s["role"] for s in shifts}
    moves = []
    for f in findings:
        if f["kind"] != "overtime":
            continue
        pool = [p for h, p in spare if h <= 32 and p not in ot_people
                and role_of.get(p, "").lower() == role_of.get(f["person"], "").lower()]
        if pool:
            moves.append({"from": f["person"], "candidates": pool[:3]})
    return {
        "rules": {k: rule.get(k) for k in ("key", "label", "checked", "min_rest_hours",
                                           "weekly_overtime_hours", "daily_overtime_hours",
                                           "daily_double_time_hours", "rest_is_legal_rule",
                                           "covers", "source")},
        "headline": headline,
        "findings": findings,
        "hours_by_person": {p: round(m / 60, 2) for p, m in sorted(totals.items())},
        "roles": role_of,
        "moves": moves,
        "_grid": grid,
        "_shifts": shifts,
    }


# ------------------------------------------------------------------ output

ORDER = ["implausible_shift", "low_confidence", "duplicate", "double_booked", "understaffed",
         "role_gap", "uncovered", "lone_working", "overtime", "short_rest", "no_day_off",
         "no_break_recorded", "overstaffed"]
TITLES = {
    "implausible_shift": "Check the photo first", "low_confidence": "Check the photo first",
    "duplicate": "Check the photo first", "double_booked": "Conflicts",
    "understaffed": "Short-staffed", "role_gap": "Short-staffed", "uncovered": "Gaps",
    "lone_working": "Alone on site", "overtime": "Overtime", "short_rest": "Short rest between shifts",
    "no_day_off": "No day off", "no_break_recorded": "Breaks", "overstaffed": "Hours you could move",
}


def text_report(r):
    h = r["headline"]
    lines = [f"{h['shifts']} shifts, {h['people']} people, {h['scheduled_hours']:g} hours scheduled.",
             f"Rules: {r['rules']['label']} (checked {r['rules']['checked']})."]
    nums = [f"{h['understaffed_person_hours']:g} person-hours short",
            f"{h['overtime_hours']:g} overtime hours",
            f"{h['short_rest']} short rests",
            f"{h['double_booked']} double bookings"]
    if "overtime_premium" in h:
        nums.append(f"overtime premium about {h['overtime_premium']:,.2f}")
    lines.append("Headline: " + ", ".join(nums) + ".")
    if h["to_confirm"]:
        lines.append(f"{h['to_confirm']} shift(s) to confirm against the photo before trusting the rest.")
    current = None
    for f in sorted(r["findings"], key=lambda f: (ORDER.index(f["kind"]), f.get("date", ""), f.get("from", ""))):
        if TITLES[f["kind"]] != current:
            current = TITLES[f["kind"]]
            lines.append("\n" + current)
        lines.append("  - " + f["text"])
    if r["moves"]:
        lines.append("\nWho could take the overtime hours (same role, 32 hours or fewer):")
        for m in r["moves"]:
            lines.append(f"  - {m['from']}: " + ", ".join(m["candidates"]))
    return "\n".join(lines)


def clean_csv(r, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["person", "role", "date", "start", "end", "break_minutes", "paid_hours",
                    "confidence", "note"])
        for s in sorted(r["_shifts"], key=lambda s: (s["start"], s["person"])):
            w.writerow([s["person"], s["role"], s["date"].isoformat(), s["start"].strftime("%H:%M"),
                        s["end"].strftime("%H:%M"), "" if s["break"] is None else s["break"],
                        round(paid_minutes(s) / 60, 2), s["confidence"], s["note"]])


def html_report(r, path, title="Schedule check"):
    """One self-contained page: the week as a grid, the numbers that matter,
    then every finding. No scripts, no external files."""
    grid = r["_grid"]
    days = sorted({t.date() for t in grid})
    hours_axis = sorted({t.hour for t in grid})
    e = html.escape
    h = r["headline"]

    def cell(d, hr):
        vals = [grid[t] for t in grid if t.date() == d and t.hour == hr]
        if not vals:
            return '<td class="c closed"></td>'
        have = min(v[0] for v in vals)
        need = max((v[1] for v in vals if v[1] is not None), default=None)
        if need is None:
            cls = "zero" if have == 0 else ("one" if have == 1 else "ok")
            label = str(have)
        else:
            diff = min(v[0] - v[1] for v in vals if v[1] is not None)
            cls = "short" if diff < 0 else ("extra" if diff > 0 else "ok")
            label = f"{have}/{need}"
        return f'<td class="c {cls}" title="{d:%a} {hr:02d}:00 {label}">{label}</td>'

    rows = "".join(
        f"<tr><th>{d:%a %d}</th>" + "".join(cell(d, hr) for hr in hours_axis) + "</tr>"
        for d in days)
    head = "<tr><th></th>" + "".join(f"<th>{hr:02d}</th>" for hr in hours_axis) + "</tr>"

    stats = [("Person-hours short", f"{h['understaffed_person_hours']:g}"),
             ("Overtime hours", f"{h['overtime_hours']:g}"),
             ("Short rests", str(h["short_rest"])),
             ("Double bookings", str(h["double_booked"]))]
    if "overtime_premium" in h:
        stats.append(("Overtime premium at your rate", f"{h['overtime_premium']:,.0f}"))
    tiles = "".join(f'<div class="tile"><div class="n">{e(v)}</div><div class="l">{e(k)}</div></div>'
                    for k, v in stats)

    sections = []
    for f in sorted(r["findings"], key=lambda f: (ORDER.index(f["kind"]), f.get("date", ""), f.get("from", ""))):
        heading = TITLES[f["kind"]]
        if not sections or sections[-1][0] != heading:
            sections.append((heading, []))
        sections[-1][1].append(f["text"])
    findings_html = "".join(
        f"<h3>{e(t)}</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"
        for t, items in sections)

    top = max(r["hours_by_person"].values() or [1])
    weekly = r["rules"].get("weekly_overtime_hours") or 40
    bars = "".join(
        f'<div class="bar"><span class="who">{e(p)}</span>'
        f'<span class="track"><span class="fill{" ot" if v > weekly else ""}" '
        f'style="width:{v / max(top, weekly) * 100:.1f}%"></span>'
        f'<span class="mark" style="left:{weekly / max(top, weekly) * 100:.1f}%"></span></span>'
        f'<span class="v">{v:g}h</span></div>'
        for p, v in sorted(r["hours_by_person"].items(), key=lambda kv: -kv[1]))

    confirm = ""
    if h["to_confirm"]:
        confirm = (f'<p class="warn">{h["to_confirm"]} shift(s) to confirm against the photo '
                   "before acting on anything below.</p>")
    legend = ("<span class='k short'></span>short of need <span class='k ok'></span>on need "
              "<span class='k extra'></span>above need" if any(v[1] is not None for v in grid.values())
              else "<span class='k zero'></span>nobody <span class='k one'></span>one person "
                   "<span class='k ok'></span>two or more")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a65;--line:#e4e1d8;--short:#c8473b;--short-bg:#f6d9d5;
--ok-bg:#e3efe4;--extra-bg:#e2e8f3;--one-bg:#fbe9c8;--zero-bg:#f2c7c1;--card:#fff}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171715;--fg:#efede6;--mute:#a3a198;--line:#33322e;
--short:#ef7d70;--short-bg:#4a2420;--ok-bg:#1f3324;--extra-bg:#1f2a3a;--one-bg:#45391d;--zero-bg:#4f2621;--card:#201f1c}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px}} h3{{font-size:14px;margin:18px 0 6px}}
.sub{{color:var(--mute);margin:0 0 16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.tile .n{{font-size:26px;font-weight:650}} .tile .l{{color:var(--mute);font-size:13px}}
.wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table{{border-collapse:collapse;font-size:12px;min-width:640px;width:100%}}
th{{font-weight:600;color:var(--mute);padding:6px 4px;text-align:center;white-space:nowrap}}
td.c{{text-align:center;padding:6px 2px;border-left:1px solid var(--line)}}
.short{{background:var(--short-bg);color:var(--short);font-weight:650}} .ok{{background:var(--ok-bg)}}
.extra{{background:var(--extra-bg)}} .one{{background:var(--one-bg)}} .zero{{background:var(--zero-bg);font-weight:650}}
.closed{{background:transparent}}
.legend{{color:var(--mute);font-size:12px;margin:8px 0}} .k{{display:inline-block;width:10px;height:10px;border-radius:2px;margin:0 4px 0 10px;vertical-align:middle}}
.bar{{display:grid;grid-template-columns:90px 1fr 48px;gap:8px;align-items:center;margin:4px 0;font-size:13px}}
.track{{position:relative;height:10px;background:var(--line);border-radius:5px}}
.fill{{position:absolute;left:0;top:0;bottom:0;background:var(--mute);border-radius:5px}} .fill.ot{{background:var(--short)}}
.mark{{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--fg)}}
.warn{{background:var(--one-bg);border-radius:8px;padding:10px 12px}}
ul{{margin:0;padding-left:20px}} li{{margin:3px 0}}
.foot{{color:var(--mute);font-size:12px;margin-top:28px}}
</style></head><body><main>
<h1>{e(title)}</h1>
<p class="sub">{h['shifts']} shifts, {h['people']} people, {h['scheduled_hours']:g} hours.
Rules: {e(r['rules']['label'] or '')} (checked {e(r['rules']['checked'])}).</p>
{confirm}
<div class="tiles">{tiles}</div>
<h2>The week, hour by hour</h2>
<div class="wrap"><table>{head}{rows}</table></div>
<div class="legend">{legend}. Each cell shows the lowest point in that hour.</div>
<h2>What to fix</h2>
{findings_html or '<p>Nothing to flag.</p>'}
<h2>Hours per person</h2>
{bars}
<p class="foot">Computed by scripts/roster.py from the roster as confirmed. Rules are a
conservative default, not legal advice; check the source named in the rules file.</p>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)


# ------------------------------------------------------------------- tests

def _kinds(r, kind):
    return [f for f in r["findings"] if f["kind"] == kind]


def run_tests():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL  {name}")

    s = os.path.join(SAMPLE, "northline_store14_truth.csv")
    n = os.path.join(SAMPLE, "northline_store14_needs.csv")
    r = analyse(s, n)
    who = lambda kind: sorted({f["person"] for f in _kinds(r, kind)})

    # planted in the sample week, and nothing else
    check("sample: overtime is Dana only", who("overtime") == ["Dana"])
    check("sample: Dana 46h, 6 over", any(f["person"] == "Dana" and f["weekly_ot"] == 6 for f in _kinds(r, "overtime")))
    check("sample: short rest is Marco only", who("short_rest") == ["Marco"])
    check("sample: Marco rest is 7h", any(f["rest_hours"] == 7 for f in _kinds(r, "short_rest")))
    check("sample: no day off is Leo only", who("no_day_off") == ["Leo"])
    check("sample: double booking is Priya on Wednesday",
          [(f["person"], f["date"]) for f in _kinds(r, "double_booked")] == [("Priya", "2026-10-21")])
    check("sample: one cell to confirm, Sam Thursday",
          [(f["person"], f["date"]) for f in _kinds(r, "low_confidence")] == [("Sam", "2026-10-22")])
    under = {(f["date"], f["from"]) for f in _kinds(r, "understaffed")}
    check("sample: Saturday opening is short", ("2026-10-24", "07:00") in under)
    check("sample: Sunday evening is short", any(d == "2026-10-25" and t >= "15:00" for d, t in under))
    check("sample: short windows only on Sat and Sun",
          {d for d, _ in under} == {"2026-10-24", "2026-10-25"})
    check("sample: Tuesday midday is overstaffed",
          any(f["date"] == "2026-10-20" and f["from"] >= "11:00" for f in _kinds(r, "overstaffed")))
    check("sample: shift lead missing Sunday evening",
          any(f["date"] == "2026-10-25" and f["role"] == "shift lead" for f in _kinds(r, "role_gap")))
    check("sample: no break flags (breaks are written)", not _kinds(r, "no_break_recorded"))
    check("sample: no implausible shifts", not _kinds(r, "implausible_shift"))
    check("sample: headline short hours > 0", r["headline"]["understaffed_person_hours"] > 0)
    check("sample: a same-role move is offered for Dana",
          any(m["from"] == "Dana" and m["candidates"] for m in r["moves"]))

    # a clean week must come back clean: the must-not half
    c = analyse(os.path.join(FIXTURES, "clean_week.csv"), os.path.join(FIXTURES, "clean_needs.csv"))
    for kind in ("overtime", "short_rest", "no_day_off", "double_booked", "understaffed",
                 "role_gap", "low_confidence", "duplicate", "no_break_recorded"):
        check(f"clean: no {kind}", not _kinds(c, kind))

    # overnight shifts: counted across midnight, rest measured correctly
    o = analyse(os.path.join(FIXTURES, "overnight.csv"))
    check("overnight: 22:00-06:00 is 8 hours", o["hours_by_person"].get("Ana") == 16)
    check("overnight: 22:00 to next 06:00 then 18:00 is a 12h rest, not flagged",
          not _kinds(o, "short_rest"))
    check("overnight: midnight slot covered", not _kinds(o, "uncovered"))

    # without needs: gaps and lone working
    g = analyse(os.path.join(FIXTURES, "gaps.csv"))
    check("no needs: hole between shifts is uncovered",
          [(f["from"], f["to"]) for f in _kinds(g, "uncovered")] == [("13:00", "14:00")])
    check("no needs: one person alone 2 hours is flagged", len(_kinds(g, "lone_working")) >= 1)

    # jurisdiction thresholds move the answer, which is the point of choosing one
    p = os.path.join(FIXTURES, "rest_9_5.csv")
    check("rest 9.5h: flagged against the default 10", len(_kinds(analyse(p), "short_rest")) == 1)
    check("rest 9.5h: not flagged under a 9-hour rule", not _kinds(analyse(p, rules_key="philadelphia"), "short_rest"))
    check("rest 9.5h: flagged under an 11-hour rule", len(_kinds(analyse(p, rules_key="evanston"), "short_rest")) == 1)

    # California-shaped daily overtime, and weekly overtime not double counted
    ca = analyse(os.path.join(FIXTURES, "daily_ot.csv"), rules_key="california")
    f = _kinds(ca, "overtime")
    check("CA: 10h day gives 2 daily OT", any(x["daily_ot"] == 2 for x in f if x["person"] == "Bo"))
    check("CA: 13h day gives 1 double time", any(x["double_ot"] == 1 for x in f if x["person"] == "Cy"))
    check("CA: 5 x 9h is 5 daily OT and no weekly OT",
          any(x["daily_ot"] == 5 and x["weekly_ot"] == 0 for x in f if x["person"] == "Di"))
    fed = analyse(os.path.join(FIXTURES, "daily_ot.csv"), rules_key="federal")
    check("federal: 5 x 9h is 5 weekly OT",
          any(x["weekly_ot"] == 5 for x in _kinds(fed, "overtime") if x["person"] == "Di"))
    check("federal: a 10h day alone is not overtime",
          not any(x["person"] == "Bo" for x in _kinds(fed, "overtime")))

    # duplicates counted once; misreads caught
    d = analyse(os.path.join(FIXTURES, "duplicates_and_misread.csv"))
    check("duplicate: reported", len(_kinds(d, "duplicate")) == 1)
    check("duplicate: counted once", d["hours_by_person"].get("Eve") == 8)
    check("misread: 19-hour shift flagged", len(_kinds(d, "implausible_shift")) == 1)
    check("no break: 8h with no break column flagged", len(_kinds(d, "no_break_recorded")) >= 1)

    # refusals
    for name, expect in (("refuse_phone_column.csv", "contact"),
                         ("refuse_phone_value.csv", "phone"),
                         ("refuse_ampm.csv", "24-hour"),
                         ("refuse_weekday_date.csv", "YYYY-MM-DD")):
        try:
            analyse(os.path.join(FIXTURES, name))
            check(f"refuses {name}", False)
        except Refusal as exc:
            check(f"refuses {name} for the right reason", expect in str(exc))
    try:
        load_rules("atlantis")
        check("refuses unknown rules", False)
    except Refusal:
        check("refuses unknown rules", True)

    # every rule names its source and coverage
    data = json.load(open(RULES_PATH, encoding="utf-8"))
    for key, rule in data["jurisdictions"].items():
        check(f"rules {key}: has a label", bool(rule.get("label")))
        if key != "none":
            check(f"rules {key}: names a source", str(rule.get("source", "")).startswith("https://")
                  or bool(rule.get("inherits")))

    # the report renders
    out = os.path.join(SAMPLE, ".report_test.html")
    try:
        html_report(r, out, "Test")
        body = open(out, encoding="utf-8").read()
        check("html: renders the grid", "<table>" in body and "Sat" in body)
        check("html: keeps the title it was given", "<h1>Test</h1>" in body)
        check("html: no external resources", "http://" not in body and "<script" not in body)
    finally:
        if os.path.exists(out):
            os.remove(out)

    total = passed + failed
    print(f"{passed}/{total} passed")
    return 0 if failed == 0 else 1


# -------------------------------------------------------------------- main

def main(argv):
    if "--test" in argv:
        return run_tests()
    if "--list-rules" in argv:
        data = json.load(open(RULES_PATH, encoding="utf-8"))
        for k, v in sorted(data["jurisdictions"].items()):
            print(f"{k:18} {v['label']}")
        return 0

    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None

    roster = opt("--roster")
    if not roster:
        print(__doc__)
        return 2
    try:
        rate = float(opt("--rate")) if opt("--rate") else None
        r = analyse(roster, opt("--needs"), opt("--rules"), rate)
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    print(text_report(r))
    if opt("--clean"):
        clean_csv(r, opt("--clean"))
    if opt("--html"):
        html_report(r, opt("--html"), opt("--title") or "Schedule check")
    if opt("--json"):
        public = {k: v for k, v in r.items() if not k.startswith("_")}
        json.dump(public, open(opt("--json"), "w", encoding="utf-8"), indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
