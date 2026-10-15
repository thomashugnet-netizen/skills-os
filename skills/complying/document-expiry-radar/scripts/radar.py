#!/usr/bin/env python3
"""
Expiry radar for document-expiry-radar.

Reads a list of the documents people need to work (one row per person per
document, with its expiry date) and answers three questions in dates, not
impressions: who cannot legally work today, who will lapse before a renewal
can come through unless it starts now, and which shifts that puts at risk.

    python3 radar.py --documents documents.csv [--shifts shifts.csv]
                     [--requirements requirements.csv] [--as-of 2026-10-19]
                     [--horizon 90] [--html report.html] [--json out.json]
    python3 radar.py --test

documents.csv   worker_id, site, role, doc_type, expires_on[, note]
shifts.csv      worker_id, date, hours            (optional)
requirements    role, doc_type[, lead_days]       (optional)

Opaque ids only. The engine refuses names, contact details, document numbers
and work-authorisation documents. Standard library only.
"""

import csv
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
TYPES_PATH = os.path.join(SKILL, "references", "doc_types.json")
SAMPLE = os.path.join(SKILL, "references", "sample")
FIXTURES = os.path.join(SKILL, "references", "fixtures")

REQUIRED = ["worker_id", "site", "doc_type", "expires_on"]
EMAIL = re.compile(r"[^\s@]+@[a-z0-9-]+(\.[a-z]|$)", re.I)
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
PHONE = re.compile(r"\+?\(?\d[\d\s().-]{6,}\d")
LETTERS_SPACE_LETTERS = re.compile(r"[^\W\d_]{2,}[\s,]+[^\W\d_]{2,}")
# Headers are read as words, so "site_number" and "role name" pass while
# "full name", "licence #" and "phonenumber" do not.
PERSON_WORDS = {"email", "mail", "phone", "mobile", "cellphone", "address", "addr", "ssn", "dob",
                "birth", "birthday", "passport", "holder", "surname", "firstname", "lastname",
                "fullname", "employeename", "workername", "phonenumber", "dl"}
NAME_OK_WITH = {"site", "store", "role", "dept", "department", "location", "job", "position",
                "team", "doc", "document", "file", "shift", "station", "branch", "region"}
DOC_WORDS = {"licence", "license", "cdl", "dl", "card", "document", "doc", "permit", "certificate",
             "cert", "passport", "ssn"}
NUMBER_WORDS = {"number", "no", "num", "nr"}
CLUSTER_MIN = 5            # a week needs at least this many expiries at one site to be a crunch


class Refusal(Exception):
    """Input the radar will not read. The message says what to fix."""


# ------------------------------------------------------------------ loading

def _norm(text):
    text = re.sub(r"['\u2019`]", "", (text or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _key(worker_id):
    return re.sub(r"\s+", " ", (worker_id or "").strip()).upper()


def _bad_header(col):
    raw = col.lower()
    words = set(re.findall(r"[a-z]+", raw))
    joined = re.sub(r"[^a-z]", "", raw)
    if words & PERSON_WORDS or joined in PERSON_WORDS:
        return "screen" not in words
    if "name" in words and not words & NAME_OK_WITH:
        return True
    if (words & DOC_WORDS or joined.startswith(("licen", "cdl"))) and (words & NUMBER_WORDS or "#" in raw
                                                                       or re.search(r"(no|num|number)$", joined)):
        return True
    return False


def _bad_value(value):
    v = value or ""
    if EMAIL.search(v) or SSN.search(v):
        return "an email or a social security number"
    for chunk in PHONE.findall(v):
        if len(re.sub(r"\D", "", chunk)) >= 9 and re.search(r"[\s().+-]", chunk):
            return "a phone number"
    return None


def load_types():
    data = json.load(open(TYPES_PATH, encoding="utf-8"))
    lookup = {}
    for key, t in data["types"].items():
        for name in [key, t["label"]] + t["aliases"]:
            lookup[_norm(name)] = key
    refused = {"exact": {_norm(a) for a in data["refused"]["aliases"]},
               "prefix": [_norm(a) for a in data["refused"]["prefixes"]]}
    return data, lookup, refused


def is_refused(raw_type, refused):
    n = _norm(raw_type)
    return n in refused["exact"] or any(n == p or n.startswith(p + " ") for p in refused["prefix"])


def _date(value, where):
    v = (value or "").strip()
    for fmt in ("%Y-%m-%d",):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"{where}: '{value}' is not a date in YYYY-MM-DD form")


def _read(path):
    try:
        text = open(path, encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        text = open(path, encoding="cp1252").read()
    reader = csv.DictReader(text.splitlines())
    cols = [(c or "").strip().lower() for c in (reader.fieldnames or [])]
    rows = []
    for i, r in enumerate(reader, start=2):
        if None in r:
            raise Refusal(f"{os.path.basename(path)} row {i} has more values than there are columns, "
                          "usually an unquoted comma in a note. Quote that field or remove the comma.")
        rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in r.items()})
    rows = [r for r in rows if any(r.values())]
    return cols, rows


def _check_identity(cols, rows, label):
    bad = [c for c in cols if c != "worker_id" and _bad_header(c)]
    if bad:
        raise Refusal(f"{label}: column(s) {', '.join(bad)} identify a person or a document. "
                      "Keep only an opaque worker_id, and never document numbers.")
    for i, r in enumerate(rows, start=2):
        dt = r.get("doc_type", "")
        if re.search(r"\d{5,}|[a-z]\d{3,}[- ]?\d{3,}", dt, re.I):
            raise Refusal(f"{label} row {i}: the document type seems to include a document number. "
                          "Write the type only, for example 'CDL'.")
        for col, value in r.items():
            why = _bad_value(value)
            if why:
                raise Refusal(f"{label} row {i}: the '{col}' column holds what looks like {why}. "
                              "Remove contact and identity details and run again.")
        if "worker_id" in r:
            wid = r["worker_id"]
            if not re.search(r"\d", wid) or LETTERS_SPACE_LETTERS.search(wid) or "." in wid:
                raise Refusal(f"{label} row {i}: that worker_id looks like a name, not an opaque id. "
                              "Use the id from your HR system; it must contain at least one digit.")


def load_documents(path, lookup, refused):
    cols, rows = _read(path)
    if not cols:
        raise Refusal("the documents file is empty.")
    missing = [c for c in REQUIRED if c not in cols]
    if missing:
        raise Refusal("documents file is missing column(s): " + ", ".join(missing))
    _check_identity(cols, rows, "documents file")
    docs, unreadable, unknown_types = [], [], Counter()
    for i, r in enumerate(rows, start=2):
        if not any(r.values()):
            continue
        raw_type = _norm(r["doc_type"])
        if is_refused(r["doc_type"], refused):
            raise Refusal(f"documents row {i}: '{r['doc_type']}' is a work-authorisation document. "
                          "Those are out of scope on purpose: remove every such row and run again.")
        key = lookup.get(raw_type)
        if not key:
            key = "other:" + raw_type
            unknown_types[r["doc_type"]] += 1
        try:
            exp = _date(r["expires_on"], f"row {i}")
        except ValueError as exc:
            unreadable.append({"row": i, "worker_id": r["worker_id"], "doc_type": r["doc_type"]})
            continue
        docs.append({"row": i, "worker": r["worker_id"], "key": _key(r["worker_id"]),
                     "site": r["site"], "role": r.get("role", ""),
                     "type": key, "expires": exp, "note": r.get("note", "")})
    return docs, unreadable, unknown_types


def load_shifts(path):
    if not path:
        return []
    cols, rows = _read(path)
    for c in ("worker_id", "date", "hours"):
        if c not in cols:
            raise Refusal(f"shifts file is missing column '{c}'.")
    _check_identity(cols, rows, "shifts file")
    out = []
    for i, r in enumerate(rows, start=2):
        if not any(r.values()):
            continue
        try:
            d = _date(r["date"], f"shifts row {i}")
        except ValueError as exc:
            raise Refusal(str(exc))
        try:
            h = float(r["hours"])
        except ValueError:
            raise Refusal(f"shifts row {i}: hours '{r['hours']}' is not a number.")
        if not 0 < h <= 24:
            raise Refusal(f"shifts row {i}: {h:g} hours is not a shift length.")
        out.append({"worker": r["worker_id"], "key": _key(r["worker_id"]), "date": d, "hours": h})
    return out


def load_requirements(path, lookup, refused):
    if not path:
        return []
    cols, rows = _read(path)
    for c in ("role", "doc_type"):
        if c not in cols:
            raise Refusal(f"requirements file is missing column '{c}'.")
    _check_identity(cols, rows, "requirements file")
    out = []
    for i, r in enumerate(rows, start=2):
        if not r.get("role") or not r.get("doc_type"):
            continue
        if is_refused(r["doc_type"], refused):
            raise Refusal(f"requirements row {i}: '{r['doc_type']}' is a work-authorisation document, "
                          "which this radar does not track.")
        key = lookup.get(_norm(r["doc_type"]), "other:" + _norm(r["doc_type"]))
        lead = r.get("lead_days", "")
        if lead and not lead.isdigit():
            raise Refusal(f"requirements row {i}: lead_days must be a whole number of days.")
        out.append({"role": _norm(r["role"]), "type": key, "lead": int(lead) if lead else None})
    return out


# ----------------------------------------------------------------- analysis

def label_of(key, types):
    if key.startswith("other:"):
        return key[6:]
    return types["types"][key]["label"]


def lead_for(key, role, types, reqs):
    for q in reqs:
        if q["type"] == key and q["role"] == _norm(role) and q["lead"] is not None:
            return q["lead"], "yours"
    if key in types["types"]:
        return types["types"][key]["lead_days"], "default"
    return types["default_lead_days"], "assumed"


def analyse(doc_path, shifts_path=None, req_path=None, as_of=None, horizon=90):
    types, lookup, refused = load_types()
    docs, unreadable, unknown_types = load_documents(doc_path, lookup, refused)
    shifts = load_shifts(shifts_path)
    reqs = load_requirements(req_path, lookup, refused)
    today = as_of or date.today()
    end = today + timedelta(days=horizon)

    # one current record per person per document: a renewal sits beside the
    # old row in most exports, and only the later date is true
    current, superseded, duplicates = {}, 0, 0
    for d in sorted(docs, key=lambda d: d["expires"]):
        k = (d["key"], d["type"])
        if k in current:
            if current[k]["expires"] == d["expires"]:
                duplicates += 1
            else:
                superseded += 1
        current[k] = d
    records = list(current.values())

    # only shifts from today on are still scheduled; earlier ones already happened
    shifts_by = defaultdict(list)
    for s in shifts:
        if s["date"] >= today:
            shifts_by[s["key"]].append(s)

    findings = []
    for d in records:
        lead, lead_src = lead_for(d["type"], d["role"], types, reqs)
        start_by = d["expires"] - timedelta(days=lead)
        days_left = (d["expires"] - today).days
        # a document is valid through its expiry date; the first day without it is the next one
        at_risk = [s for s in shifts_by.get(d["key"], []) if s["date"] > d["expires"]]
        base = {"worker": d["worker"], "key": d["key"], "site": d["site"], "role": d["role"], "type": d["type"],
                "label": label_of(d["type"], types), "expires": d["expires"].isoformat(),
                "days_left": days_left, "lead_days": lead, "lead_source": lead_src,
                "start_by": start_by.isoformat(),
                "shifts_at_risk": len(at_risk), "hours_at_risk": round(sum(s["hours"] for s in at_risk), 2),
                "first_shift_at_risk": min((s["date"] for s in at_risk), default=None)}
        if base["first_shift_at_risk"]:
            base["first_shift_at_risk"] = base["first_shift_at_risk"].isoformat()
        if d["expires"] < today:
            kind = "scheduled_while_expired" if at_risk else "expired"
        elif start_by <= today:
            kind = "start_now"
        elif d["expires"] <= end:
            kind = "due"
        else:
            continue
        base["kind"] = kind
        base["band"] = ("expired" if days_left < 0 else "0-30" if days_left <= 30
                        else "31-60" if days_left <= 60 else "61-90" if days_left <= 90 else "91+")
        base["_at_risk"] = at_risk
        findings.append(base)

    # missing: a role that needs a document, and a person in it with no record
    missing, unlisted = [], []
    people = {}
    for d in sorted(docs, key=lambda d: d["row"]):
        p = people.setdefault(d["key"], {"worker": d["worker"], "site": d["site"], "roles": set()})
        p["site"] = d["site"]                       # the latest row wins for the site
        if d["role"]:
            p["roles"].add(_norm(d["role"]))
    for u in unreadable:
        people.setdefault(_key(u["worker_id"]), {"worker": u["worker_id"], "site": "", "roles": set()})
    if reqs:
        have = {(d["key"], d["type"]) for d in records}
        have |= {(_key(u["worker_id"]), lookup.get(_norm(u["doc_type"]), "other:" + _norm(u["doc_type"])))
                 for u in unreadable}
        # a person who has held several roles is checked against all of them
        for k, p in sorted(people.items()):
            for q in reqs:
                if q["role"] in p["roles"] and (k, q["type"]) not in have:
                    at_risk = shifts_by.get(k, [])
                    missing.append({"kind": "missing", "worker": p["worker"], "key": k, "site": p["site"],
                                    "role": next((r for r in p["roles"] if r == q["role"]), q["role"]),
                                    "type": q["type"], "label": label_of(q["type"], types),
                                    "shifts_at_risk": len(at_risk),
                                    "hours_at_risk": round(sum(s["hours"] for s in at_risk), 2),
                                    "_at_risk": at_risk})
    # on the schedule, absent from the documents export: the easiest one to miss
    if shifts:
        for k in sorted(set(shifts_by) - set(people)):
            at_risk = shifts_by[k]
            unlisted.append({"kind": "unlisted", "worker": at_risk[0]["worker"], "key": k,
                             "shifts_at_risk": len(at_risk),
                             "hours_at_risk": round(sum(s["hours"] for s in at_risk), 2), "_at_risk": at_risk})

    # crunches: many expiries at one site in one week, usually one training cohort
    weekly = Counter()
    for d in records:
        if today <= d["expires"] <= end:
            monday = d["expires"] - timedelta(days=d["expires"].weekday())
            weekly[(d["site"], d["type"], monday)] += 1
    clusters = [{"kind": "cluster", "site": s, "type": t, "label": label_of(t, types),
                 "week_of": m.isoformat(), "count": n}
                for (s, t, m), n in sorted(weekly.items()) if n >= CLUSTER_MIN]

    by_kind = Counter(f["kind"] for f in findings)
    unique_shifts = {}
    for f in findings + missing + unlisted:
        for s in f["_at_risk"]:
            unique_shifts[(f["key"], s["date"], id(s))] = s["hours"]
    headline = {
        "as_of": today.isoformat(),
        "horizon_days": horizon,
        "people": len({d["key"] for d in docs}),
        "documents": len(records),
        "cannot_work_today": len({f["worker"] for f in findings
                                  if f["kind"] in ("expired", "scheduled_while_expired")}),
        "scheduled_while_expired": len({f["key"] for f in findings if f["kind"] == "scheduled_while_expired"}),
        "start_renewal_now": by_kind["start_now"],
        "lapse_in_30_days": sum(1 for f in findings if f["band"] == "0-30"),
        "due_in_horizon": sum(1 for f in findings if 0 <= f["days_left"] <= horizon),
        "missing": len(missing),
        "not_in_documents": len(unlisted),
        "shifts_at_risk": len(unique_shifts),
        "hours_at_risk": round(sum(unique_shifts.values()), 2),
    }
    for f in findings + missing + unlisted:
        f.pop("_at_risk", None)
    return {
        "headline": headline,
        "findings": findings,
        "missing": missing,
        "unlisted": unlisted,
        "clusters": clusters,
        "data": {"unreadable": unreadable, "superseded": superseded, "duplicates": duplicates,
                 "unknown_types": dict(unknown_types),
                 "lead_assumed": sorted({f["label"] for f in findings if f["lead_source"] == "assumed"})},
        "_records": records,
        "_types": types,
    }


# ------------------------------------------------------------------ output

PRIORITY = ["scheduled_while_expired", "expired", "start_now", "due"]


def ordered(r):
    return sorted(r["findings"], key=lambda f: (PRIORITY.index(f["kind"]), f["expires"], f["site"], f["worker"]))


def sentence(f):
    if f["kind"] == "scheduled_while_expired":
        return (f"{f['worker']} ({f['site']}, {f['role']}): {f['label']} expired {f['expires']}, "
                f"and {f['shifts_at_risk']} shift(s) are still scheduled from today, the first on {f['first_shift_at_risk']}.")
    if f["kind"] == "expired":
        return f"{f['worker']} ({f['site']}, {f['role']}): {f['label']} expired {f['expires']}."
    if f["kind"] == "start_now":
        tail = (f". {f['shifts_at_risk']} scheduled shift(s) fall after the expiry" if f["shifts_at_risk"] else "")
        return (f"{f['worker']} ({f['site']}, {f['role']}): {f['label']} expires {f['expires']} "
                f"({f['days_left']} days). A renewal takes about {f['lead_days']} days, so it should "
                f"have started by {f['start_by']}{tail}.")
    return (f"{f['worker']} ({f['site']}, {f['role']}): {f['label']} expires {f['expires']}; "
            f"start the renewal by {f['start_by']}.")


def text_report(r):
    h = r["headline"]
    out = [f"As of {h['as_of']}: {h['people']} people, {h['documents']} current documents.",
           f"Cannot work today: {h['cannot_work_today']} ({h['scheduled_while_expired']} still on the schedule). "
           f"Start renewal now: {h['start_renewal_now']}. Lapse in 30 days: {h['lapse_in_30_days']}. "
           f"Missing a required document: {h['missing']}. "
           + (f"On the schedule with no documents at all: {h['not_in_documents']}. " if h["not_in_documents"] else "")
           + 
           f"Shifts at risk: {h['shifts_at_risk']} ({h['hours_at_risk']:g} hours)."]
    titles = {"scheduled_while_expired": "Expired and still scheduled", "expired": "Expired",
              "start_now": "Start the renewal now", "due": f"Due within {h['horizon_days']} days"}
    current = None
    for f in ordered(r):
        if f["kind"] != current:
            current = f["kind"]
            out.append("\n" + titles[current])
        out.append("  - " + sentence(f))
    if r["missing"]:
        out.append("\nNo record of a required document")
        for m in r["missing"]:
            out.append(f"  - {m['worker']} ({m['site']}, {m['role']}): no {m['label']} on file"
                       + (f"; {m['shifts_at_risk']} shift(s) scheduled." if m["shifts_at_risk"] else "."))
    if r["unlisted"]:
        out.append("\nOn the schedule but not in the documents export")
        for u in r["unlisted"]:
            out.append(f"  - {u['worker']}: {u['shifts_at_risk']} shift(s) scheduled, no documents on file at all.")
    if r["clusters"]:
        out.append("\nCrunch weeks")
        for c in r["clusters"]:
            out.append(f"  - {c['site']}: {c['count']} {c['label']} expiries in the week of {c['week_of']}.")
    d = r["data"]
    notes = []
    if d["unreadable"]:
        notes += [f"row {u['row']} ({u['worker_id']}): expiry date unreadable (not YYYY-MM-DD), left out"
                  for u in d["unreadable"]]
    if d["duplicates"]:
        notes.append(f"{d['duplicates']} exact duplicate row(s) counted once")
    if d["superseded"]:
        notes.append(f"{d['superseded']} older record(s) replaced by a later expiry for the same person and document")
    if d["unknown_types"]:
        notes.append("document types I do not recognise (renewal time assumed): " + ", ".join(sorted(d["unknown_types"])))
    if notes:
        out.append("\nAbout the file")
        out += ["  - " + n for n in notes]
    return "\n".join(out)


def html_report(r, path, title="Document expiry radar"):
    e = html.escape
    h = r["headline"]
    today = date.fromisoformat(h["as_of"])
    weeks = [today - timedelta(days=today.weekday()) + timedelta(weeks=i)
             for i in range(min(27, h["horizon_days"] // 7 + 1))]
    sites = sorted({d["site"] for d in r["_records"]})
    grid = Counter()
    expired_by_site = Counter()
    for d in r["_records"]:
        if d["expires"] < today:
            expired_by_site[d["site"]] += 1
            continue
        monday = d["expires"] - timedelta(days=d["expires"].weekday())
        if monday in weeks:
            grid[(d["site"], monday)] += 1
    peak = max(list(grid.values()) + [1])

    def cell(n, cls=""):
        if not n:
            return '<td class="c"></td>'
        level = 1 + min(3, int(3 * n / peak)) if not cls else 4
        return f'<td class="c l{level} {cls}">{n}</td>'

    head = "<tr><th>Site</th><th>Expired</th>" + "".join(f"<th>{w:%d %b}</th>" for w in weeks) + "</tr>"
    rows = "".join(
        f"<tr><th>{e(s)}</th>{cell(expired_by_site[s], 'bad')}"
        + "".join(cell(grid[(s, w)]) for w in weeks) + "</tr>" for s in sites)
    tiles = [("Cannot work today", h["cannot_work_today"]), ("Start renewal now", h["start_renewal_now"]),
             ("Lapse in 30 days", h["lapse_in_30_days"]), ("Missing a document", h["missing"]),
             ("Shifts at risk", h["shifts_at_risk"])]
    tiles_html = "".join(f'<div class="tile"><div class="n">{v}</div><div class="l">{e(k)}</div></div>' for k, v in tiles)

    titles = {"scheduled_while_expired": "Expired and still scheduled", "expired": "Expired",
              "start_now": "Start the renewal now", "due": f"Due within {h['horizon_days']} days"}
    sections, cur = [], None
    for f in ordered(r):
        if f["kind"] != cur:
            cur = f["kind"]
            sections.append((titles[cur], []))
        sections[-1][1].append(sentence(f))
    if r["missing"]:
        sections.append(("No record of a required document",
                         [f"{m['worker']} ({m['site']}, {m['role']}): no {m['label']} on file" for m in r["missing"]]))
    if r["unlisted"]:
        sections.append(("On the schedule but not in the documents export",
                         [f"{u['worker']}: {u['shifts_at_risk']} shift(s) scheduled, no documents on file" for u in r["unlisted"]]))
    if r["clusters"]:
        sections.append(("Crunch weeks", [f"{c['site']}: {c['count']} {c['label']} expiries in the week of {c['week_of']}."
                                          for c in r["clusters"]]))
    body = "".join(f"<h3>{e(t)}</h3><ul>" + "".join(f"<li>{e(x)}</li>" for x in items) + "</ul>"
                   for t, items in sections)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a65;--line:#e4e1d8;--card:#fff;--bad:#c8473b;--bad-bg:#f6d9d5;
--l1:#fdf0d5;--l2:#f9dca3;--l3:#f2bd63;--l4:#e39a2e}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171715;--fg:#efede6;--mute:#a3a198;--line:#33322e;--card:#201f1c;
--bad:#ef7d70;--bad-bg:#4a2420;--l1:#3a3020;--l2:#544222;--l3:#7a5a22;--l4:#a06f1f}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px}} h3{{font-size:14px;margin:18px 0 6px}}
.sub{{color:var(--mute);margin:0 0 16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.tile .n{{font-size:26px;font-weight:650}} .tile .l{{color:var(--mute);font-size:13px}}
.wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table{{border-collapse:collapse;font-size:12px;min-width:720px;width:100%}}
th{{font-weight:600;color:var(--mute);padding:6px 6px;text-align:center;white-space:nowrap}}
td.c{{text-align:center;padding:6px 2px;border-left:1px solid var(--line)}}
.l1{{background:var(--l1)}} .l2{{background:var(--l2)}} .l3{{background:var(--l3)}} .l4{{background:var(--l4);font-weight:650}}
td.bad{{background:var(--bad-bg);color:var(--bad);font-weight:650}}
ul{{margin:0;padding-left:20px}} li{{margin:3px 0}}
.foot{{color:var(--mute);font-size:12px;margin-top:28px}}
</style></head><body><main>
<h1>{e(title)}</h1>
<p class="sub">As of {e(h['as_of'])}: {h['people']} people, {h['documents']} current documents, next {h['horizon_days']} days.</p>
<div class="tiles">{tiles_html}</div>
<h2>Expiries by site and week</h2>
<div class="wrap"><table>{head}{rows}</table></div>
<h2>What to do, in order</h2>
{body or '<p>Nothing expires in this window.</p>'}
<p class="foot">Computed by scripts/radar.py from the file as given. Renewal times are planning defaults
unless you set your own. Not legal advice: confirm each requirement with its issuing body.</p>
</main></body></html>"""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(page)


# ------------------------------------------------------------------- tests

def run_tests():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL  {name}")

    as_of = date(2026, 10, 19)
    S = lambda n: os.path.join(SAMPLE, n)
    F = lambda n: os.path.join(FIXTURES, n)
    r = analyse(S("northline_documents.csv"), S("northline_shifts.csv"), S("northline_requirements.csv"), as_of)
    kinds = lambda k: [f for f in r["findings"] if f["kind"] == k]
    who = lambda k: sorted(f["worker"] for f in kinds(k))

    # what is planted, and nothing else
    check("sample: two expired and still scheduled, both STN-03 DOT cards",
          [(f["worker"], f["site"], f["type"]) for f in sorted(kinds("scheduled_while_expired"), key=lambda f: f["worker"])]
          == [("W-0311", "STN-03", "dot_medical_card"), ("W-0312", "STN-03", "dot_medical_card")])
    check("sample: one expired with no shifts", who("expired") == ["W-0415"])
    check("sample: cannot work today is three people", r["headline"]["cannot_work_today"] == 3)
    check("sample: five DOT cards must start now",
          len(kinds("start_now")) == 5 and {f["type"] for f in kinds("start_now")} == {"dot_medical_card"})
    check("sample: start-now cards have shifts after expiry",
          sum(1 for f in kinds("start_now") if f["shifts_at_risk"]) == 3)
    check("sample: the STN-05 forklift crunch, 14 in one week",
          [(c["site"], c["type"], c["week_of"], c["count"]) for c in r["clusters"]]
          == [("STN-05", "forklift_certification", "2026-11-23", 14)])
    check("sample: three STN-02 drivers have no DOT card",
          sorted((m["worker"], m["site"], m["type"]) for m in r["missing"])
          == [("W-0204", "STN-02", "dot_medical_card"), ("W-0208", "STN-02", "dot_medical_card"),
              ("W-0211", "STN-02", "dot_medical_card")])
    check("sample: the renewed card is not reported (W-0110)",
          not any(f["worker"] == "W-0110" for f in r["findings"]))
    check("sample: one superseded record", r["data"]["superseded"] == 1)
    check("sample: one unreadable expiry, row reported", len(r["data"]["unreadable"]) == 1
          and r["data"]["unreadable"][0]["worker_id"] == "W-0506")
    check("sample: due in 90 days is the crunch plus the trickle",
          len(kinds("due")) == 14 + 6)
    check("sample: nothing at STN-06 at all", not any(f["site"] == "STN-06" for f in r["findings"]))
    check("sample: hours at risk are counted", r["headline"]["hours_at_risk"] > 0)
    check("sample: no type assumed", not r["data"]["lead_assumed"] and not r["data"]["unknown_types"])

    # the start-now rule turns on lead time, not on a fixed window
    t = analyse(F("lead_times.csv"), as_of=as_of)
    by = {f["worker"]: f["kind"] for f in t["findings"]}
    check("lead: food card in 6 days with 7-day lead starts now", by.get("A1") == "start_now")
    check("lead: food card in 10 days with 7-day lead is only due", by.get("A2") == "due")
    check("lead: DOT card in 20 days with 21-day lead starts now", by.get("A3") == "start_now")
    check("lead: DOT card in 25 days is only due", by.get("A4") == "due")
    check("lead: beyond the horizon is not listed", "A5" not in by)
    t2 = analyse(F("lead_times.csv"), req_path=F("lead_override.csv"), as_of=as_of)
    by2 = {f["worker"]: f for f in t2["findings"]}
    check("lead: your own lead time wins (30 days makes A4 start now)",
          by2["A4"]["kind"] == "start_now" and by2["A4"]["lead_source"] == "yours")
    t3 = analyse(F("unknown_type.csv"), as_of=as_of)
    check("lead: an unknown type is kept, with the lead assumed and said so",
          t3["findings"] and t3["data"]["unknown_types"] and t3["data"]["lead_assumed"])
    check("aliases: 'Med Card' and 'CDL' resolve",
          {f["type"] for f in analyse(F("aliases.csv"), as_of=as_of)["findings"]}
          == {"dot_medical_card", "driver_license"})

    # a clean file comes back clean
    c = analyse(F("clean.csv"), F("clean_shifts.csv"), as_of=as_of)
    check("clean: nothing flagged", not c["findings"] and not c["clusters"] and not c["missing"])
    check("clean: zero at risk", c["headline"]["shifts_at_risk"] == 0)

    # refusals
    for name, expect in (("refuse_name_column.csv", "identify"),
                         ("refuse_doc_number.csv", "identify"),
                         ("refuse_name_value.csv", "looks like a name"),
                         ("refuse_work_permit.csv", "work-authorisation"),
                         ("refuse_i9.csv", "work-authorisation"),
                         ("refuse_missing_column.csv", "missing column")):
        try:
            analyse(F(name), as_of=as_of)
            check(f"refuses {name}", False)
        except Refusal as exc:
            check(f"refuses {name} for the right reason", expect in str(exc))

    # edge cases found by an adversarial pass before release; each one was wrong once
    import tempfile
    tmp = tempfile.mkdtemp(prefix="radar-test-")

    def write(name, text, encoding="utf-8"):
        path = os.path.join(tmp, name)
        with open(path, "w", encoding=encoding, newline="") as fh:
            fh.write(text)
        return path

    H = "worker_id,site,role,doc_type,expires_on,note\n"
    SH = "worker_id,date,hours\n"
    e = analyse(write("d1.csv", H + "A1,S1,Driver,med card,2026-10-19,\n"),
                write("s1.csv", SH + "A1,2026-10-19,8\nA1,2026-10-20,8\n"), as_of=as_of)
    check("edge: valid through its expiry day, so not 'cannot work'", e["headline"]["cannot_work_today"] == 0)
    check("edge: the shift on the expiry day is fine, the next day is at risk", e["headline"]["shifts_at_risk"] == 1)
    e = analyse(write("d2.csv", H + "A1,S1,Driver,med card,2026-10-01,\n"),
                write("s2.csv", SH + "A1,2026-10-05,8\n"), as_of=as_of)
    check("edge: a shift already worked is not 'still scheduled'",
          [f["kind"] for f in e["findings"]] == ["expired"] and e["headline"]["shifts_at_risk"] == 0)
    e = analyse(write("d3.csv", H + "A1,S1,Driver,med card,2026-10-01,\nA1,S1,Driver,cdl,2026-10-02,\n"),
                write("s3.csv", SH + "A1,2026-10-20,8\nA1,2026-10-21,8\n"), as_of=as_of)
    check("edge: one person, two expired documents, shifts counted once",
          e["headline"]["shifts_at_risk"] == 2 and e["headline"]["hours_at_risk"] == 16
          and e["headline"]["scheduled_while_expired"] == 1 and e["headline"]["cannot_work_today"] == 1)
    e = analyse(write("d4.csv", H + "A1,S1,Driver,Driver\u2019s licence,2026-11-10,\nA2,S1,Driver,CDL-A,2026-11-10,\n"
                      "A3,S1,Lead,CPR/First Aid,2026-11-10,\nA4,S1,Cook,Food Handler's Card,2026-11-10,\n"), as_of=as_of)
    check("aliases: apostrophes, CDL-A, CPR/First Aid resolve", not e["data"]["unknown_types"])
    e = analyse(write("d5.csv", H + "A1,S1,Delivery  Driver,cdl,2027-06-01,\nA2,S1,delivery-driver,cdl,2027-06-01,\n"),
                req_path=write("r5.csv", "role,doc_type\nDelivery Driver,med card\n,\n"), as_of=as_of)
    check("roles: spacing, case and hyphens match; blank requirement rows skipped",
          sorted(m["worker"] for m in e["missing"]) == ["A1", "A2"] and all(m["label"] for m in e["missing"]))
    e = analyse(write("d6.csv", H + "w-0001,S1,Driver,med card,2026-10-01,\nW-0001,S1,Driver,med card,2027-10-01,\n"),
                write("s6.csv", SH + "W-0001,2026-10-20,8\n"), as_of=as_of)
    check("ids: case differences are the same person", e["headline"]["people"] == 1 and not e["findings"]
          and e["data"]["superseded"] == 1)
    e = analyse(write("d7.csv", H + "A1,S1,Warehouse associate,forklift,2027-01-01,\nA1,S2,Driver,cdl,2027-06-01,\n"),
                req_path=write("r7.csv", "role,doc_type\nDriver,med card\n"), as_of=as_of)
    check("roles: a person who moved roles is checked against the new one",
          [m["worker"] for m in e["missing"]] == ["A1"])
    e = analyse(write("d8.csv", H + "A1,S1,Driver,cdl,2026/11/01,\n"),
                req_path=write("r8.csv", "role,doc_type\nDriver,cdl\n"), as_of=as_of)
    check("unreadable: an unreadable date is not also 'missing'", not e["missing"] and len(e["data"]["unreadable"]) == 1)
    check("unreadable: the raw value is not echoed", "2026/11/01" not in json.dumps(e["data"]))
    e = analyse(write("d9.csv", H + "A1,S1,Driver,cdl,2027-06-01,\n"),
                write("s9.csv", SH + "NEW1,2026-10-20,8\n"), as_of=as_of)
    check("unlisted: on the schedule, absent from the export, is reported",
          [u["worker"] for u in e["unlisted"]] == ["NEW1"] and e["headline"]["shifts_at_risk"] == 1)
    e = analyse(write("d10.csv", H + "A1,S1,Driver,cdl,2027-06-01,\nA1,S1,Driver,cdl,2027-06-01,\n"), as_of=as_of)
    check("duplicates: an exact duplicate is not called a renewal",
          e["data"]["duplicates"] == 1 and e["data"]["superseded"] == 0)
    e = analyse(write("d11.csv", H + "A1,S1,Cook,food handler card,2026-10-25,caf\xe9 shift\n", "cp1252"), as_of=as_of)
    check("encoding: a cp1252 export is read", len(e["findings"]) == 1)
    e = analyse(write("d12.csv", "worker_id,site,site_number,role,doc_type,expires_on\n"
                      "123456789,Store 14,14,Welder,Hot work permit,2026-11-01\n"
                      "987654321,Store 14,14,Cook,Food passport,2026-11-02\n"), as_of=as_of)
    check("no false refusals: 9-digit ids, site_number, hot work permit, food passport", len(e["findings"]) == 2)
    leaks = [
        ("worker_id,full name,site,role,doc_type,expires_on\nA1,Ana,S1,D,cdl,2027-01-01\n", "identify"),
        ("worker_id,site,role,doc_type,expires_on,licence #\nA1,S1,D,cdl,2027-01-01,X1\n", "identify"),
        ("worker_id,site,role,doc_type,expires_on,phonenumber\nA1,S1,D,cdl,2027-01-01,1\n", "identify"),
        ("worker_id,site,role,doc_type,expires_on,Date of birth\nA1,S1,D,cdl,2027-01-01,1\n", "identify"),
        (H + "jsmith,S1,D,cdl,2027-01-01,\n", "looks like a name"),
        (H + "Jos\u00e9 Garc\u00eda 1,S1,D,cdl,2027-01-01,\n", "looks like a name"),
        (H + "john.smith1,S1,D,cdl,2027-01-01,\n", "looks like a name"),
        (H + "A2,jane.doe@acme.com,D,cdl,2027-01-01,\n", "email"),
        (H + "A2,S1,D,cdl,2027-01-01,SSN 123-45-6789\n", "social security"),
        (H + "A2,S1,D,cdl,2027-01-01,call (415) 555-0134\n", "phone"),
        (H + "A2,S1,D,CDL D123-4567-8901,2027-01-01,\n", "document number"),
        (H + "A1,S1,D,cdl,2026-11-01,late, see manager\n", "unquoted comma"),
    ]
    for i, (text, expect) in enumerate(leaks):
        try:
            analyse(write(f"leak{i}.csv", text), as_of=as_of)
            check(f"refuses leak case {i} ({expect})", False)
        except Refusal as exc:
            check(f"refuses leak case {i} ({expect})", expect in str(exc))
    for name, text, kind in (("rq_email.csv", "role,doc_type,owner\nDriver,cdl,jane.doe@acme.com\n", "req"),
                             ("rq_permit.csv", "role,doc_type\nDriver,work permit\n", "req"),
                             ("sh_neg.csv", "worker_id,date,hours\nA1,2026-10-20,-8\n", "shift")):
        try:
            d = write("ok.csv", H + "A1,S1,Driver,cdl,2027-01-01,\n")
            if kind == "req":
                analyse(d, req_path=write(name, text), as_of=as_of)
            else:
                analyse(d, write(name, text), as_of=as_of)
            check(f"refuses {name}", False)
        except Refusal:
            check(f"refuses {name}", True)
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    # every known type carries a lead time and its shape; sourced ones are https
    types = json.load(open(TYPES_PATH, encoding="utf-8"))
    for k, v in types["types"].items():
        check(f"types {k}: lead and shape", isinstance(v["lead_days"], int) and bool(v["validity_shape"]))
        check(f"types {k}: source is https or absent", v["source"] is None or v["source"].startswith("https://"))

    out = os.path.join(SAMPLE, ".radar_test.html")
    try:
        html_report(r, out, "Test")
        body = open(out, encoding="utf-8").read()
        check("html: renders", "<table>" in body and "STN-05" in body and "<h1>Test</h1>" in body)
        check("html: self-contained", "<script" not in body and "http://" not in body)
    finally:
        if os.path.exists(out):
            os.remove(out)

    print(f"{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


# -------------------------------------------------------------------- main

def main(argv):
    if "--test" in argv:
        return run_tests()

    def opt(name):
        return argv[argv.index(name) + 1] if name in argv else None

    if not opt("--documents"):
        print(__doc__)
        return 2
    try:
        as_of = date.fromisoformat(opt("--as-of")) if opt("--as-of") else None
        r = analyse(opt("--documents"), opt("--shifts"), opt("--requirements"), as_of,
                    int(opt("--horizon") or 90))
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    print(text_report(r))
    if opt("--html"):
        html_report(r, opt("--html"), opt("--title") or "Document expiry radar")
    if opt("--json"):
        json.dump({k: v for k, v in r.items() if not k.startswith("_")},
                  open(opt("--json"), "w", encoding="utf-8"), indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
