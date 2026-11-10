#!/usr/bin/env python3
"""
Interview No-Show Playbook: the engine.

    python3 scripts/noshow.py --log bookings.csv [--as-of 2026-10-31] [--md | --json]
    python3 scripts/noshow.py --log bookings.csv --playbook facts.json [--md | --json]
    python3 scripts/noshow.py --playbook facts.json          # untuned, says so
    python3 scripts/noshow.py --check messages.json          # your own sequence
    python3 scripts/noshow.py --demo
    python3 scripts/noshow.py --test

Reads either a booking log (one row per booked interview) or a pipeline export
(one row per application). Counts the miss honestly, reads the wait between
booking and interview first, tests every other candidate cause inside strata,
reads what happens after a miss, and writes the slot rules and the message
sequence the diagnosis calls for. Same file, same answer, every time.

Exit codes: 0 read / sequence ready, 1 sequence not ready, 3 input refused,
4 the engine itself failed. Python 3, standard library only.
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

VERSION = "1.0.0"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SAMPLE_DIR = os.path.join(SKILL, "references", "sample")
SAMPLE_LOG = os.path.join(SAMPLE_DIR, "fernhill_bookings.csv")
SAMPLE_FACTS = os.path.join(SAMPLE_DIR, "fernhill_facts.json")
FIXTURES = os.path.join(SKILL, "references", "fixtures")

MAX_ROWS = 300_000
Z95 = 1.959964
MIN_ARM = 30
MIN_EFFECT = 0.03
ALPHA = 0.05
LAG_BANDS = [("same day", 0, 0), ("1 day", 1, 1), ("2-3 days", 2, 3),
             ("4-7 days", 4, 7), ("8+ days", 8, 10_000)]
HOUR_BANDS = [("before 10:00", 0, 9), ("10:00-10:59", 10, 10),
              ("11:00-13:59", 11, 13), ("14:00-16:59", 14, 16),
              ("17:00 or later", 17, 23)]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]


class Refused(Exception):
    """The input cannot be read honestly. Exit 3 with the reason."""


# =============================================================== reading ====

ALIASES = {
    "application_id": ["candidate_id", "applicant_id", "app_id", "application"],
    "location_id": ["site_id", "store_id", "location", "site", "store"],
    "hiring_manager_id": ["interviewer_id", "interviewer", "manager_id"],
    "booked_at": ["booking_created_at", "created_at", "booked_on",
                  "booking_date", "booking_at", "booked"],
    "interview_at": ["appointment_at", "interview_datetime", "interview_time",
                     "slot_at", "scheduled_for", "interview_date", "appointment"],
    "outcome": ["status", "result", "attendance"],
    "mode": ["scheduling_mode", "booked_by", "scheduled_by"],
    "format": ["interview_format", "interview_type"],
    "slots_offered": ["slots", "slots_shown", "options_offered"],
    "reminder_24h": ["reminder_sent", "reminded"],
    "confirmed": ["reply", "reminder_reply", "confirmation"],
    "commute_band_km": ["commute_band", "distance_band"],
    "cancelled_at": ["canceled_at", "cancellation_at", "rescheduled_at"],
}
ALIAS_OF = {a: k for k, v in ALIASES.items() for a in v}

PII_EXACT = {"name", "address", "street", "street_address", "postcode",
             "post_code", "zip", "zip_code", "zipcode", "postal_code", "dob",
             "date_of_birth", "birth_date", "birthdate", "ssn",
             "social_security", "social_security_number", "national_insurance",
             "nin", "note", "notes", "comment", "comments", "free_text",
             "ip_address"}
NAME_OK = {"store_name", "site_name", "location_name", "role_name",
           "source_name", "job_name", "brand_name", "region_name",
           "position_name", "campaign_name", "company_name"}
EMAIL_RE = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"^\+?\d{0,3}[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}$"
                      r"|^\+\d[\d\s.\-()]{8,}\d$")

OUTCOME_WORDS = {
    "attended": ["attended", "completed", "complete", "showed", "show", "held",
                 "interviewed", "done", "occurred", "attended_interview"],
    "no_show": ["no_show", "noshow", "missed", "did_not_attend", "dna",
                "absent", "ghosted", "no_call_no_show", "ncns",
                "interview_no_show", "no_show_interview", "missed_interview"],
    "cancelled": ["cancelled", "canceled", "candidate_cancelled",
                  "candidate_canceled", "cancelled_by_candidate",
                  "canceled_by_candidate", "withdrew", "withdrawn"],
    "rescheduled": ["rescheduled", "moved", "reschedule",
                    "rescheduled_by_candidate"],
    "employer_cancelled": ["employer_cancelled", "employer_canceled",
                           "cancelled_by_employer", "canceled_by_employer",
                           "interviewer_cancelled", "interviewer_canceled",
                           "cancelled_by_interviewer", "store_cancelled",
                           "recruiter_cancelled", "rescheduled_by_employer"],
    "open": ["", "scheduled", "booked", "upcoming", "pending", "confirmed",
             "open"],
}
OUTCOME_OF = {w: k for k, ws in OUTCOME_WORDS.items() for w in ws}
MODE_OF = {"self": "self", "self_scheduled": "self", "self_service": "self",
           "candidate": "self", "link": "self", "online": "self",
           "recruiter": "recruiter", "recruiter_scheduled": "recruiter",
           "coordinator": "recruiter", "manual": "recruiter",
           "staff": "recruiter", "manager": "recruiter", "phone": "recruiter"}
FORMAT_OF = {"in_person": "in person", "onsite": "in person",
             "on_site": "in person", "store": "in person", "in_store": "in person",
             "video": "video", "virtual": "video", "zoom": "video",
             "teams": "video", "phone": "phone", "call": "phone",
             "telephone": "phone"}
YES = {"yes", "y", "1", "true", "sent", "t"}
REPLY_COMING = {"yes", "y", "1", "true", "confirmed", "coming", "c"}
REPLY_MOVE = {"move", "reschedule", "2", "cancel", "change", "m"}
REPLY_NONE = {"", "no", "n", "0", "false", "none", "no_reply"}
STAGES = ["applied", "screened", "interview_scheduled", "interview_completed",
          "offer_extended", "onboarding_started", "started"]


def norm_header(h):
    h = re.sub(r"[\s\-]+", "_", h.strip().lower().lstrip(chr(0xFEFF)))
    return ALIAS_OF.get(h, h)


def norm_word(v):
    return re.sub(r"[\s\-]+", "_", (v or "").strip().lower())


def pii_header(h):
    if h in NAME_OK:
        return False
    if h in PII_EXACT or h.endswith("name"):
        return True
    return any(w in h for w in ("email", "e_mail", "phone", "mobile",
                                "telephone", "cellphone", "birth"))


def read_table(path):
    """(headers, rows as dicts). Refuses what cannot be read honestly."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise Refused(f"cannot open {path}: {e.strerror}")
    if not raw.strip():
        raise Refused("the file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refused("the file is not UTF-8. Re-export it as CSV UTF-8.")
    if "\x00" in text:
        raise Refused("the file holds binary data, not a CSV")
    first = text.split("\n", 1)[0]
    delim = max([",", ";", "\t"], key=first.count)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise Refused("no header row")
    headers = [norm_header(h) for h in header]
    if len(set(headers)) != len(headers):
        dup = sorted({h for h in headers if headers.count(h) > 1})
        raise Refused(f"repeated column names after reading aliases: {', '.join(dup)}")
    bad = [h for h in headers if pii_header(h)]
    if bad:
        raise Refused("the file has columns that look personal ("
                      + ", ".join(bad) + "). Re-export with opaque ids only: "
                      "no names, emails, phone numbers, addresses or notes.")
    rows = []
    try:
        for rec in reader:
            if not any(c.strip() for c in rec):
                continue
            if len(rows) >= MAX_ROWS:
                raise Refused(f"more than {MAX_ROWS:,} rows. Export one region "
                              "or one half-year at a time.")
            rec = rec + [""] * (len(headers) - len(rec))
            rows.append({h: rec[i].strip() for i, h in enumerate(headers)})
    except csv.Error as e:
        raise Refused(f"the CSV is malformed: {e}")
    if not rows:
        raise Refused("the file has a header and no rows")
    person = re.compile(r"^[A-Z][a-z]+(?:[-'][A-Za-z]+)? [A-Z][a-z]+(?:[-'][A-Za-z]+)?$")
    for h in ("application_id", "hiring_manager_id"):
        if h in headers:
            vals = [r[h] for r in rows[:20_000] if r.get(h)]
            if vals and sum(1 for v in vals if person.match(v)) / len(vals) > 0.05:
                raise Refused(f"'{h}' holds what look like people's names. Use opaque "
                              "ids that do not resolve to a person outside your systems.")
    for r in rows:
        for h, v in r.items():
            if not v or h.endswith("_at") or h == "booked":
                continue
            if "@" in v and EMAIL_RE.search(v):
                raise Refused(f"column '{h}' holds an email address. Re-export "
                              "with opaque ids only.")
            if PHONE_RE.match(v):
                raise Refused(f"column '{h}' holds a phone number. Re-export "
                              "with opaque ids only.")
    return headers, rows


ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})"
                    r"(?::(\d{2})(?:\.\d+)?)?\s*([AaPp][Mm])?\s*"
                    r"(?:Z|[+-]\d{2}:?\d{2})?)?$")
SLASH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})(?:[ T](\d{1,2}):(\d{2})"
                      r"(?::(\d{2}))?\s*([AaPp][Mm])?)?$")


def slash_order(values):
    """'mdy' or 'dmy' for slash dates, from proof in the data."""
    dmy = mdy = False
    for v in values:
        m = SLASH_RE.match(v)
        if not m:
            continue
        a, b = int(m.group(1)), int(m.group(2))
        dmy |= a > 12
        mdy |= b > 12
    if dmy and mdy:
        raise Refused("slash dates are written both day-first and month-first. "
                      "Re-export dates as YYYY-MM-DD.")
    return "dmy" if dmy else "mdy"


def parse_when(v, order="mdy"):
    """(datetime, has_time) or (None, False). A UTC offset is dropped and the
    wall-clock time kept: morning or evening is what decides attendance."""
    v = v.strip()
    m = ISO_RE.match(v)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm, ss, ap = m.group(4), m.group(5), m.group(6), m.group(7)
    else:
        m = SLASH_RE.match(v)
        if not m:
            return None, False
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        mo, d = (a, b) if order == "mdy" else (b, a)
        hh, mm, ss, ap = m.group(4), m.group(5), m.group(6), m.group(7)
    try:
        if hh is None:
            return dt.datetime(y, mo, d), False
        h = int(hh)
        if ap:
            if not 1 <= h <= 12:
                return None, False
            h = h % 12 + (12 if ap.lower() == "pm" else 0)
        return dt.datetime(y, mo, d, h, int(mm), int(ss or 0)), True
    except ValueError:
        return None, False


def parse_column(rows, col, order, required):
    """Parses one date column in place. Refuses if more than 1% of the filled
    cells cannot be read."""
    filled = bad = 0
    timed = 0
    for r in rows:
        v = r.get(col, "")
        if not v:
            r[col] = None
            continue
        filled += 1
        when, has_time = parse_when(v, order)
        if when is None or not (2000 <= when.year <= 2100):
            bad += 1
            r[col] = None
            continue
        r[col] = when
        timed += has_time
    if filled and bad / filled > 0.01:
        raise Refused(f"{bad:,} of {filled:,} values in '{col}' are not dates "
                      "I can read. Use YYYY-MM-DD or YYYY-MM-DD HH:MM.")
    if required and filled == 0:
        raise Refused(f"'{col}' is empty")
    return {"filled": filled, "unreadable": bad,
            "timed": filled - bad > 0 and timed >= 0.9 * (filled - bad)}


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def load(path, as_of=None):
    headers, rows = read_table(path)
    cols = set(headers)
    if {"booked_at", "interview_at", "outcome", "application_id"} <= cols:
        return load_bookings(path, headers, rows, as_of)
    if {"interview_scheduled_at", "stage_reached", "application_id"} <= cols:
        return load_pipeline(path, headers, rows, as_of)
    if "stage_reached" in cols and not any("interview" in c for c in cols):
        raise Refused("this export has no interview stage (it looks like a sign-up "
                      "or onboarding funnel), so there is no booked interview to read.")
    if {"booked_at", "interview_at", "outcome"} & cols:
        missing = {"application_id", "booked_at", "interview_at",
                   "outcome"} - cols
        raise Refused("a booking log needs application_id, booked_at, "
                      "interview_at and outcome; missing: "
                      + ", ".join(sorted(missing)))
    raise Refused("I need either a booking log (application_id, booked_at, "
                  "interview_at, outcome: one row per booked interview) or a "
                  "pipeline export (application_id, interview_scheduled_at, "
                  "stage_reached, exit_reason). Found: " + ", ".join(headers[:12]))


def date_cols_order(rows, cols):
    values = []
    for c in cols:
        values.extend(r.get(c, "") for r in rows[:50_000] if r.get(c))
    return slash_order(values)


def base_record(r):
    return {
        "app": r.get("application_id") or None,
        "site": r.get("location_id") or None,
        "role": r.get("role") or None,
        "source": r.get("source") or None,
        "mgr": r.get("hiring_manager_id") or None,
        "commute": r.get("commute_band_km") or None,
    }


def load_bookings(path, headers, rows, as_of):
    date_cols = [c for c in ("booked_at", "interview_at", "cancelled_at")
                 if c in headers]
    order = date_cols_order(rows, date_cols)
    info = {c: parse_column(rows, c, order, c != "cancelled_at") for c in date_cols}
    out, notes = [], []
    unknown = collections.Counter()
    dropped = negative = 0
    for r in rows:
        rec = base_record(r)
        word = norm_word(r.get("outcome"))
        outcome = OUTCOME_OF.get(word)
        if outcome is None:
            unknown[r.get("outcome")] += 1
            continue
        if not rec["app"] or r["booked_at"] is None or r["interview_at"] is None:
            dropped += 1
            continue
        booked, appt = r["booked_at"], r["interview_at"]
        timed = info["booked_at"]["timed"] and info["interview_at"]["timed"]
        if appt.date() < booked.date() or (timed and appt < booked):
            negative += 1
            continue
        mode = MODE_OF.get(norm_word(r.get("mode"))) if r.get("mode") else None
        fmt = FORMAT_OF.get(norm_word(r.get("format"))) if r.get("format") else None
        reminder = None
        if "reminder_24h" in headers:
            reminder = norm_word(r.get("reminder_24h")) in YES
        reply = None
        if "confirmed" in headers:
            w = norm_word(r.get("confirmed"))
            reply = ("coming" if w in REPLY_COMING else "move" if w in REPLY_MOVE
                     else "none" if w in REPLY_NONE else None)
        rec.update(booked=booked, appt=appt, outcome=outcome, mode=mode,
                   fmt=fmt, slots=to_int(r.get("slots_offered")),
                   reminder=reminder, reply=reply,
                   cancelled_at=r.get("cancelled_at"))
        out.append(rec)
    total = len(rows)
    bad_outcomes = sum(unknown.values())
    if bad_outcomes / total > 0.01:
        top = ", ".join(f"'{k}'" for k, _ in unknown.most_common(5))
        raise Refused(f"{bad_outcomes:,} rows have an outcome I cannot read "
                      f"({top}). Use attended, no_show, cancelled, rescheduled, "
                      "employer_cancelled, or blank for upcoming.")
    if negative / total > 0.05:
        raise Refused(f"{negative:,} rows have the interview before the booking. "
                      "booked_at must be when the slot was booked, interview_at "
                      "when the interview was due.")
    if not out:
        raise Refused("no readable bookings")
    if bad_outcomes:
        notes.append(f"{bad_outcomes} rows with an unreadable outcome left out")
    if negative:
        notes.append(f"{negative} rows with the interview before the booking left out")
    if dropped:
        notes.append(f"{dropped} rows with no id or no date left out")
    stamps = [b["booked"] for b in out]
    as_of_d = as_of or max(stamps).date()
    stale = sum(1 for b in out if b["outcome"] == "open"
                and b["appt"].date() < as_of_d - dt.timedelta(days=1))
    if stale:
        notes.append(f"{stale} interviews dated before {as_of_d.isoformat()} have no "
                     "outcome. They are left out; if they were misses nobody logged, "
                     "the miss rate here is too low")
    timed = info["interview_at"]["timed"]
    return {
        "kind": "bookings", "path": path, "rows": total, "records": finish(out),
        "headers": headers, "notes": notes, "as_of": as_of_d,
        "appt_timed": timed, "booked_timed": info["booked_at"]["timed"],
        "slash_order": order,
    }


def load_pipeline(path, headers, rows, as_of):
    date_cols = [c for c in ("screened_at", "interview_scheduled_at",
                             "interview_completed_at", "interview_at")
                 if c in headers]
    order = date_cols_order(rows, date_cols)
    info = {c: parse_column(rows, c, order, c == "interview_scheduled_at")
            for c in date_cols}
    ids = [r.get("application_id") for r in rows if r.get("application_id")]
    if ids and (len(ids) - len(set(ids))) / len(ids) > 0.01:
        raise Refused("application_id repeats in more than 1% of rows: this "
                      "looks like a status history. Export one row per "
                      "application, or a booking log with one row per booking.")
    out, never, notes = [], collections.Counter(), []
    never_site = collections.defaultdict(collections.Counter)
    screened_site = collections.Counter()
    other = 0
    for r in rows:
        rec = base_record(r)
        if r.get("screened_at") is not None:
            screened_site[rec["site"]] += 1
        stage = norm_word(r.get("stage_reached"))
        sidx = STAGES.index(stage) if stage in STAGES else None
        exit_word = norm_word(r.get("exit_reason"))
        if r.get("interview_scheduled_at") is None:
            if r.get("screened_at") is not None and stage == "screened":
                reason = exit_word or "still open"
                never[reason] += 1
                never_site[rec["site"]][reason] += 1
            continue
        booked = r["interview_scheduled_at"]
        appt = r.get("interview_at")
        if r.get("interview_completed_at") is not None or (sidx is not None and sidx > 2):
            outcome = "attended"
        elif OUTCOME_OF.get(exit_word) == "no_show":
            outcome = "no_show"
        elif OUTCOME_OF.get(exit_word) == "cancelled":
            outcome = "cancelled"
        elif not exit_word:
            outcome = "open"
        else:
            other += 1
            continue
        if appt is not None and appt.date() < booked.date():
            appt = None
        rec.update(booked=booked, appt=appt, outcome=outcome, mode=None,
                   fmt=None, slots=None, reminder=None, reply=None,
                   cancelled_at=None, screened=r.get("screened_at"))
        out.append(rec)
    if not out:
        raise Refused("no application in this export reached a booked interview")
    if other:
        notes.append(f"{other} applications left at the booked stage for another "
                     "reason (not a no-show, not a cancellation) are left out")
    has_appt = "interview_at" in headers and sum(1 for o in out if o["appt"]) >= 0.9 * len(out)
    as_of_d = as_of or max(o["booked"] for o in out).date()
    return {
        "kind": "pipeline", "path": path, "rows": len(rows), "records": finish(out),
        "headers": headers, "notes": notes, "as_of": as_of_d,
        "appt_timed": has_appt and info.get("interview_at", {}).get("timed", False),
        "booked_timed": False, "has_appt": has_appt,
        "never_booked": dict(never), "never_site": {k: dict(v) for k, v in never_site.items()},
        "screened_site": dict(screened_site),
        "screened_col": "screened_at" in headers,
    }


# ================================================================= stats ====

def wilson(k, n, z=Z95):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, mid - half), min(1.0, mid + half))


def p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2))


def arm_var(a, n):
    p = (a + 0.5) / (n + 1)
    return p * (1 - p) / n


def rd_raw(a1, n1, a0, n0):
    d = a1 / n1 - a0 / n0
    se = math.sqrt(arm_var(a1, n1) + arm_var(a0, n0))
    return d, se


def rd_strat(cells):
    """Mantel-Haenszel-weighted risk difference over strata.
    cells: {stratum: [a1, n1, a0, n0]}. Returns (rd, se, coverage, strata)."""
    num = den = var = 0.0
    used_n1 = all_n1 = 0
    k = 0
    for a1, n1, a0, n0 in cells.values():
        all_n1 += n1
        if n1 == 0 or n0 == 0:
            continue
        w = n1 * n0 / (n1 + n0)
        num += w * (a1 / n1 - a0 / n0)
        den += w
        var += w * w * (arm_var(a1, n1) + arm_var(a0, n0))
        used_n1 += n1
        k += 1
    if den == 0:
        return None, None, 0.0, 0
    return num / den, math.sqrt(var) / den, (used_n1 / all_n1 if all_n1 else 0.0), k


def holm(pvals, alpha=ALPHA):
    """Holm-Bonferroni over everything tested: the set of indexes that would be
    flagged by chance less than one time in twenty, all tests together."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    out = set()
    for rank, i in enumerate(order):
        if pvals[i] <= alpha / (m - rank):
            out.add(i)
        else:
            break
    return out


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}%"


def pts(x):
    return f"{100 * x:+.1f} pts"


def points(x):
    return f"{abs(100 * x):.0f} points"


def cap(text):
    return text[:1].upper() + text[1:] if text else text


# ============================================================== analysis ====

def lag_days(rec):
    return rec["lag"]


def lag_band(lag):
    for name, lo, hi in LAG_BANDS:
        if lo <= lag <= hi:
            return name
    return LAG_BANDS[-1][0]


def hour_band(h):
    for name, lo, hi in HOUR_BANDS:
        if lo <= h <= hi:
            return name
    return HOUR_BANDS[-1][0]


def spans_weekend(rec):
    d = rec["booked"].date() + dt.timedelta(days=1)
    end = rec["appt"].date()
    while d < end:
        if d.weekday() >= 5:
            return True
        d += dt.timedelta(days=1)
    return False


def week_key(rec):
    return rec["week"]


def finish(records):
    """Computes once what every pass reads: the wait in days and the booking week."""
    for r in records:
        r["lag"] = (r["appt"].date() - r["booked"].date()).days if r["appt"] else None
        y, w, _ = r["booked"].isocalendar()
        r["week"] = f"{y}-W{w:02d}"
    return records


def standing(records):
    """Appointments still standing on the day: held or silently missed."""
    return [r for r in records if r["outcome"] in ("attended", "no_show")]


def first_standing(data):
    """Each candidate's first appointment that went ahead. Causes are read on
    these; a rebooking after a miss is a different population (a recruiter
    chasing someone who already missed) and is read in the recovery section."""
    if "_first" not in data:
        best = {}
        for r in data["records"]:
            if r["outcome"] not in ("attended", "no_show"):
                continue
            k = r["app"]
            if k not in best or (r["booked"], r["appt"] or r["booked"]) < (
                    best[k]["booked"], best[k]["appt"] or best[k]["booked"]):
                best[k] = r
        data["_first"] = sorted(best.values(), key=lambda r: (r["booked"], str(r["app"])))
    return data["_first"]


def count_section(data):
    recs = data["records"]
    c = collections.Counter(r["outcome"] for r in recs)
    due = sum(c[k] for k in ("attended", "no_show", "cancelled", "rescheduled"))
    held, miss = c["attended"], c["no_show"]
    out = {
        "bookings": len(recs), "open": c["open"],
        "employer_cancelled": c["employer_cancelled"], "due": due,
        "attended": held, "no_show": miss, "cancelled": c["cancelled"],
        "rescheduled": c["rescheduled"],
        "miss_rate": miss / (held + miss) if held + miss else None,
        "separated": c["cancelled"] + c["rescheduled"] > 0,
    }
    # Per application: the first appointment against what finally happened.
    by_app = collections.defaultdict(list)
    for r in recs:
        if r["outcome"] != "open":
            by_app[r["app"]].append(r)
    first_miss = rescued = lost = 0
    for app, rs in by_app.items():
        rs.sort(key=lambda r: (r["booked"], r["appt"]))
        first = next((r for r in rs if r["outcome"] in ("attended", "no_show")), None)
        if first is None or first["outcome"] != "no_show":
            continue
        first_miss += 1
        later = [r for r in rs if r["booked"] >= first["booked"] and r is not first]
        if any(r["outcome"] == "attended" for r in later):
            rescued += 1
        else:
            lost += 1
    out.update(applications=len(by_app), first_miss=first_miss,
               rescued=rescued, lost_after_miss=lost)
    # Month table
    months = collections.defaultdict(collections.Counter)
    for r in recs:
        if r["outcome"] in ("attended", "no_show", "cancelled", "rescheduled"):
            months[r["appt"].strftime("%Y-%m") if r["appt"] else
                   r["booked"].strftime("%Y-%m")][r["outcome"]] += 1
    out["months"] = [{"month": m, **{k: v[k] for k in ("attended", "no_show",
                                                          "cancelled", "rescheduled")},
                      "miss_rate": (v["no_show"] / (v["attended"] + v["no_show"])
                                    if v["attended"] + v["no_show"] else None)}
                     for m, v in sorted(months.items())]
    return out


def lag_section(data):
    st = [r for r in first_standing(data) if r["appt"] is not None]
    if not st:
        return None
    bands = []
    for name, lo, hi in LAG_BANDS:
        rs = [r for r in st if lo <= lag_days(r) <= hi]
        k = sum(r["outcome"] == "no_show" for r in rs)
        cancels = [r for r in data["records"] if r["appt"] is not None
                   and r["outcome"] in ("cancelled", "rescheduled")
                   and lo <= lag_days(r) <= hi]
        bands.append({"band": name, "lo": lo, "hi": hi, "n": len(rs), "missed": k,
                      "miss_rate": k / len(rs) if rs else None,
                      "range": wilson(k, len(rs)) if rs else None,
                      "cancelled_ahead": len(cancels)})
    lags = sorted(lag_days(r) for r in st)
    med = lags[len(lags) // 2]
    beyond = sum(1 for l in lags if l >= 4)
    return {"bands": bands, "median_days": med, "n": len(st),
            "share_4plus": beyond / len(st), "n_4plus": beyond}


def calendar_section(data, peak_weeks):
    """Names the calendar behind long waits, site by site."""
    recs = [r for r in data["records"] if r["appt"] is not None
            and r["outcome"] != "open"]
    if not recs or not any(r["site"] for r in recs):
        return None
    allshare = sum(lag_days(r) >= 4 for r in recs) / len(recs)
    sites = []
    by_site = collections.defaultdict(list)
    for r in recs:
        by_site[r["site"]].append(r)
    for site, rs in sorted(by_site.items(), key=lambda kv: str(kv[0])):
        if site is None or len(rs) < MIN_ARM:
            continue
        lags = sorted(lag_days(r) for r in rs)
        share4 = sum(l >= 4 for l in lags) / len(lags)
        if share4 < max(0.40, allshare + 0.15):
            continue
        wd = collections.Counter(r["appt"].weekday() for r in rs)
        top_day, top_n = wd.most_common(1)[0]
        mgrs = {r["mgr"] for r in rs if r["mgr"]}
        slots = [r["slots"] for r in rs if r["slots"] is not None]
        one_slot = (sum(s == 1 for s in slots) / len(slots)) if slots else None
        causes = []
        if top_n / len(rs) >= 0.7:
            causes.append(f"interviews on {WEEKDAYS[top_day]} only "
                          f"({pct(top_n / len(rs))} of appointments)")
        if one_slot is not None and one_slot >= 0.4:
            causes.append(f"one slot offered to {pct(one_slot)}")
        if len(mgrs) == 1:
            causes.append("one interviewer")
        eff = site_effect(data, site)
        sites.append({"site": site, "n": len(rs), "median_days": lags[len(lags) // 2],
                      "raw": eff[0], "after_wait": eff[1],
                      "share_4plus": share4, "top_weekday": WEEKDAYS[top_day],
                      "top_weekday_share": top_n / len(rs), "interviewers": len(mgrs),
                      "one_slot_share": one_slot, "causes": causes})
    peak = None
    if peak_weeks:
        pk = [lag_days(r) for r in recs if week_key(r) in peak_weeks]
        off = [lag_days(r) for r in recs if week_key(r) not in peak_weeks]
        if len(pk) >= MIN_ARM and len(off) >= MIN_ARM:
            pk.sort(), off.sort()
            eff = exposure_effect(data, lambda r: week_key(r) in peak_weeks)
            peak = {"median_peak": pk[len(pk) // 2], "median_other": off[len(off) // 2],
                    "raw": eff[0], "after_wait": eff[1],
                    "share4_peak": sum(l >= 4 for l in pk) / len(pk),
                    "share4_other": sum(l >= 4 for l in off) / len(off)}
    return {"overall_share_4plus": allshare, "sites": sites, "peak": peak}


def exposure_effect(data, fn):
    """(raw, wait-adjusted) difference in miss rate for an exposure."""
    st = [r for r in first_standing(data) if r["appt"] is not None]
    a1 = n1 = a0 = n0 = 0
    cells = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in st:
        e = fn(r)
        m = r["outcome"] == "no_show"
        c = cells[min(lag_days(r), 14)]
        if e:
            a1 += m; n1 += 1; c[0] += m; c[1] += 1
        else:
            a0 += m; n0 += 1; c[2] += m; c[3] += 1
    if not n1 or not n0:
        return None, None
    adj = rd_strat(cells)[0]
    return a1 / n1 - a0 / n0, adj


def site_effect(data, site):
    return exposure_effect(data, lambda r: r["site"] == site)


def busy_weeks(records):
    vol = collections.Counter(week_key(r) for r in records)
    if len(vol) < 8:
        return set()
    weeks = sorted(vol)
    inner = weeks[1:-1]                       # first and last weeks are partial
    vals = sorted(vol[w] for w in inner)
    med = vals[len(vals) // 2]
    return {w for w in inner if vol[w] >= 1.25 * med}


# ---------------------------------------------------------------- drivers ----

def make_drivers(data, peak_weeks):
    """(key, label, exposure fn, checks, family[, (field, value)])."""
    recs = first_standing(data)
    filled = {f: sum(1 for r in recs if r.get(f) is not None) >= 0.9 * len(recs)
              for f in ("site", "role", "source", "mgr", "commute", "mode", "fmt", "slots")}
    has = filled.get
    has_appt = all(r["appt"] is not None for r in recs) if recs else False
    D = []
    lag_ok = has_appt
    strat = {
        "site": lambda r: r["site"],
        "role": lambda r: r["role"],
        "wait": (lambda r: min(lag_days(r), 14)) if lag_ok else None,
        "week": week_key,
        "format": lambda r: r["fmt"],
    }

    def checks(*names):
        return [n for n in names if strat.get(n) is not None
                and (n not in ("site", "role", "format") or has(
                    {"site": "site", "role": "role", "format": "fmt"}[n]))]

    if lag_ok:
        D.append(("wait_4plus", "A wait of 4 days or more between booking and interview",
                  lambda r: lag_days(r) >= 4, checks("site", "role", "week"), None))
        D.append(("weekend_wait", "A weekend inside the wait",
                  lambda r: spans_weekend(r) if 1 <= lag_days(r) <= 7 else None,
                  checks("wait", "site"), None))
    elif data["kind"] == "pipeline" and data.get("screened_col"):
        D.append(("slow_booking", "4 days or more from screen to booking",
                  lambda r: (r["booked"].date() - r["screened"].date()).days >= 4
                  if r.get("screened") else None, checks("site", "week"), None))
    if has("mode"):
        D.append(("self_scheduled", "Self-scheduled (against booked by a recruiter)",
                  lambda r: r["mode"] == "self" if r["mode"] else None,
                  checks("wait", "role"), None))
    if has("slots"):
        D.append(("one_slot", "One slot offered (against a choice of two or more)",
                  lambda r: r["slots"] == 1 if r["slots"] is not None else None,
                  checks("wait", "site"), None))
    if has_appt and data["appt_timed"]:
        for name, lo, hi in HOUR_BANDS:
            D.append((f"hour:{name}", f"Slots {name}" if name[0].isalpha() else f"Slots at {name}",
                      (lambda lo, hi: lambda r: lo <= r["appt"].hour <= hi)(lo, hi),
                      checks("role", "wait", "site"), "hour"))
    if has("fmt"):
        for f in sorted({r["fmt"] for r in recs if r["fmt"]}):
            D.append((f"format:{f}", f"{f.capitalize()} interviews",
                      (lambda f: lambda r: r["fmt"] == f if r["fmt"] else None)(f),
                      checks("role"), "format"))
    if peak_weeks:
        D.append(("busy_weeks", "Booked in the busiest weeks",
                  lambda r: week_key(r) in peak_weeks,
                  checks("wait", "site") if lag_ok else checks("site", "role"), None))
    if has("commute"):
        D.append(("far_commute", "Commute band over 20 km",
                  lambda r: (r["commute"] in ("21-40", "40+", ">40", "40_plus"))
                  if r["commute"] else None,
                  checks("site", "format") if has("fmt") else checks("site"), None))
    fam = [("site", "site", "Site", ("week", "wait") if lag_ok else ("week", "role")),
           ("mgr", "interviewer", "Interviewer", ("site", "wait") if lag_ok else ("site",)),
           ("source", "source", "Source", ("site", "wait") if lag_ok else ("site",)),
           ("role", "role", "Role", ("site", "wait") if lag_ok else ("site",))]
    for field, fam_key, label, chk in fam:
        if not has(field):
            continue
        vals = collections.Counter(r[field] for r in recs if r[field])
        if len(vals) < 2 or len(vals) > 400:
            continue
        for v, n in sorted(vals.items(), key=lambda kv: str(kv[0])):
            if n < MIN_ARM:
                continue
            D.append((f"{fam_key}:{v}", f"{label}: {v}",
                      (lambda field, v: lambda r: r[field] == v if r[field] else None)(field, v),
                      checks(*chk), fam_key, (field, v)))
    return D, strat


def run_drivers(data, peak_weeks):
    recs = first_standing(data)
    drivers, strat = make_drivers(data, peak_weeks)
    tested = []
    grouped = {}
    for d in drivers:
        if len(d) > 5 and d[5][0] not in grouped:
            field = d[5][0]
            g = collections.defaultdict(lambda: [0, 0])
            for r in recs:
                if r[field]:
                    g[r[field]][0] += r["outcome"] == "no_show"
                    g[r[field]][1] += 1
            grouped[field] = (g, sum(v[0] for v in g.values()), sum(v[1] for v in g.values()))
    for d in drivers:
        key, label, fn, chks, family = d[:5]
        if len(d) > 5:
            g, tm, tn = grouped[d[5][0]]
            a1, n1 = g[d[5][1]]
            a0, n0 = tm - a1, tn - n1
        else:
            a1 = n1 = a0 = n0 = 0
            for r in recs:
                e = fn(r)
                if e is None:
                    continue
                m = r["outcome"] == "no_show"
                if e:
                    a1 += m; n1 += 1
                else:
                    a0 += m; n0 += 1
        rec = {"key": key, "label": label, "family": family, "n_exposed": n1,
               "n_rest": n0, "rate_exposed": a1 / n1 if n1 else None,
               "rate_rest": a0 / n0 if n0 else None, "checks": []}
        if n1 < MIN_ARM or n0 < MIN_ARM:
            rec.update(verdict="thin", raw=None, p=None)
            tested.append((rec, fn, chks))
            continue
        d, se = rd_raw(a1, n1, a0, n0)
        rec.update(raw=d, raw_range=(d - Z95 * se, d + Z95 * se),
                   p=p_two_sided(d / se) if se > 0 else 1.0)
        tested.append((rec, fn, chks))
    idx = [i for i, (rec, _, _) in enumerate(tested) if rec.get("p") is not None]
    found = holm([tested[i][0]["p"] for i in idx])
    flagged = {idx[j] for j in found}
    results = []
    for i, (rec, fn, chks) in enumerate(tested):
        if rec.get("verdict") == "thin":
            results.append(rec)
            continue
        if i not in flagged or abs(rec["raw"]) < MIN_EFFECT:
            rec["verdict"] = "no effect"
            results.append(rec)
            continue
        if rec["family"] and rec["raw"] < 0:
            rec["verdict"] = "fewer misses"      # families: only the worse ones lead
            results.append(rec)
            continue
        fails, unrunnable = [], []
        for name in chks:
            sf = strat[name]
            cells = collections.defaultdict(lambda: [0, 0, 0, 0])
            for r in recs:
                e = fn(r)
                s = sf(r)
                if e is None or s is None:
                    continue
                m = r["outcome"] == "no_show"
                c = cells[s]
                if e:
                    c[0] += m; c[1] += 1
                else:
                    c[2] += m; c[3] += 1
            adj, se, cov, k = rd_strat(cells)
            chk = {"by": name, "coverage": cov, "strata": k}
            if adj is None or cov < 0.5:
                chk["result"] = "cannot separate"
                unrunnable.append(name)
            else:
                p = p_two_sided(adj / se) if se > 0 else 1.0
                ok = (p < ALPHA and adj * rec["raw"] > 0
                      and abs(adj) >= 0.4 * abs(rec["raw"]) and abs(adj) >= 0.02)
                chk.update(adjusted=adj, range=(adj - Z95 * se, adj + Z95 * se),
                           p=p, result="survives" if ok else "explained")
                if not ok:
                    fails.append((abs(adj) / abs(rec["raw"]) if adj * rec["raw"] > 0
                                  else -1, name))
            rec["checks"].append(chk)
        if fails:
            rec["verdict"] = "explained"
            rec["explained_by"] = min(fails)[1]
        elif unrunnable or not rec["checks"]:
            rec["verdict"] = "cannot separate"
            rec["inseparable_from"] = unrunnable or ["anything: no check applies"]
        else:
            rec["verdict"] = "survives"
            runs = [c["adjusted"] for c in rec["checks"] if c["result"] == "survives"]
            rec["adjusted"] = min(runs, key=abs)
            if rec["adjusted"] > 0:
                rec["recoverable"] = rec["adjusted"] * rec["n_exposed"]
            else:
                rec["recoverable"] = -rec["adjusted"] * rec["n_rest"]
        results.append(rec)
    results.sort(key=lambda r: (-(r.get("recoverable") or 0), r["key"]))
    return results


# ---------------------------------------------------------------- recovery ---

REBOOK_BANDS = [("within 2 hours", 0, 2), ("same day, later", 2, 24),
                ("next day", 24, 48), ("2-3 days", 48, 96), ("4+ days", 96, 10**9)]


def recovery_section(data):
    if data["kind"] != "bookings":
        return None
    recs = [r for r in data["records"] if r["outcome"] != "open"]
    by_app = collections.defaultdict(list)
    for r in data["records"]:
        by_app[r["app"]].append(r)
    timed = data["booked_timed"] and data["appt_timed"]
    cutoff = dt.datetime.combine(data["as_of"], dt.time()) - dt.timedelta(days=7)
    misses = []
    for app, rs in by_app.items():
        rs.sort(key=lambda r: (r["booked"], r["appt"]))
        for i, r in enumerate(rs):
            if r["outcome"] != "no_show":
                continue
            if any(x["outcome"] == "no_show" for x in rs[:i]):
                break                                # first miss only
            if r["appt"] > cutoff:
                break                                # too recent to judge
            nxt = next((x for x in rs[i + 1:]
                        if x["booked"] >= r["appt"] - dt.timedelta(hours=1)), None)
            if nxt is None:
                misses.append((r, None, None))
            else:
                if timed:
                    h = max(0.0, (nxt["booked"] - r["appt"]).total_seconds() / 3600)
                else:
                    h = 24.0 * max(0, (nxt["booked"].date() - r["appt"].date()).days)
                misses.append((r, nxt, h))
            break
    if not misses:
        return None
    bands = []
    for name, lo, hi in REBOOK_BANDS:
        if not timed and name in ("within 2 hours", "same day, later"):
            continue
        if not timed and name == "next day":
            lo = 0
        sel = [(m, n) for m, n, h in misses if n is not None and lo <= h < hi]
        done = [n for _, n in sel if n["outcome"] in ("attended", "no_show")]
        att = sum(n["outcome"] == "attended" for n in done)
        bands.append({"band": name if timed or name != "next day" else "same or next day",
                      "rebooked": len(sel), "share_of_misses": len(sel) / len(misses),
                      "attended": att, "attend_rate": att / len(done) if done else None})
    never = sum(1 for _, n, _ in misses if n is None)
    rebooked = len(misses) - never
    recovered = sum(1 for _, n, _ in misses if n is not None and n["outcome"] == "attended")
    by_site = collections.defaultdict(lambda: [0, 0])
    for m, n, _ in misses:
        if m["site"]:
            by_site[m["site"]][0] += 1
            by_site[m["site"]][1] += n is not None
    others_rate = None
    never_sites = sorted(s for s, (k, rb) in by_site.items() if k >= 15 and rb == 0)
    rest = [(k, rb) for s, (k, rb) in by_site.items() if s not in never_sites]
    if rest:
        tk = sum(k for k, _ in rest)
        others_rate = sum(rb for _, rb in rest) / tk if tk else None
    never_misses = sum(by_site[s][0] for s in never_sites)
    rec_per_rebook = recovered / rebooked if rebooked else None
    cancels = [r for r in recs if r["outcome"] == "cancelled" and r["appt"] <= cutoff]
    c_rebooked = 0
    for r in cancels:
        rs = by_app[r["app"]]
        if any(x["booked"] > r["booked"] for x in rs if x is not r):
            c_rebooked += 1
    return {
        "misses": len(misses), "never_rebooked": never, "rebooked": rebooked,
        "recovered": recovered, "bands": bands, "timed": timed,
        "never_sites": never_sites, "never_site_misses": never_misses,
        "others_rebook_rate": others_rate,
        "recoverable_at_never_sites": (never_misses * (others_rate or 0) *
                                       (rec_per_rebook or 0)),
        "cancelled": len(cancels), "cancelled_rebooked": c_rebooked,
        "window_days": 7,
    }


def reply_section(data):
    recs = [r for r in standing(data["records"]) if r["reply"] is not None]
    if not recs:
        return None
    use = [r for r in recs if (r["reminder"] if r["reminder"] is not None
                               else (r["appt"] - r["booked"]).total_seconds() >= 86400)]
    if len(use) < MIN_ARM:
        return None
    out = {}
    for status in ("coming", "none", "move"):
        rs = [r for r in use if r["reply"] == status]
        k = sum(r["outcome"] == "no_show" for r in rs)
        out[status] = {"n": len(rs), "missed": k,
                       "miss_rate": k / len(rs) if rs else None,
                       "range": wilson(k, len(rs)) if rs else None}
    total_miss = sum(r["outcome"] == "no_show" for r in use)
    caught = out["none"]["missed"] + out["move"]["missed"]
    out["share_of_misses_flagged"] = caught / total_miss if total_miss else None
    out["n"] = len(use)
    separate = (out["none"]["n"] >= MIN_ARM and out["coming"]["n"] >= MIN_ARM
                and out["none"]["range"][0] > out["coming"]["range"][1])
    out["separates"] = separate
    return out


def holdout_plan(count, weekly):
    p = count.get("miss_rate")
    if p is None or not weekly or p <= 0.0 or p >= 1.0:
        return None
    d = 0.05 if p >= 0.10 else p / 2
    p2 = max(p - d, 0.001)
    n = math.ceil((1.959964 + 0.841621) ** 2 * (p * (1 - p) + p2 * (1 - p2)) / d ** 2)
    return {"detect_points": d, "per_arm": n, "weekly_bookings": weekly,
            "weeks_20": math.ceil(n / (0.2 * weekly)),
            "weeks_50": math.ceil(n / (0.5 * weekly))}


def cannot_section(data):
    out = []
    h = set(data["headers"])
    if data["kind"] == "pipeline" and not data.get("has_appt"):
        out.append(("The wait between booking and interview",
                     "a missed interview has no interview date in this export, so a "
                     "wait computed from completed interviews only would describe "
                     "the people who came. Add the appointment date (`interview_at`) "
                     "for every booking."))
    if not data["appt_timed"]:
        out.append(("Time of day", "interview times are dates without a time. "
                    "Add the appointment time."))
    if "mode" not in h:
        out.append(("Self-scheduled against recruiter-booked", "add `mode`."))
    if "slots_offered" not in h:
        out.append(("Slot scarcity", "add `slots_offered` (how many slots the "
                    "candidate could choose from)."))
    if data["kind"] == "pipeline" or "outcome" in h and not any(
            r["outcome"] in ("cancelled", "rescheduled") for r in data["records"]):
        out.append(("Cancelled in advance against a silent miss",
                    "the export does not separate them, so the miss rate is "
                    "combined. Record cancellations and reschedules as outcomes."))
    if "confirmed" not in h:
        out.append(("Whether a reply to the reminder predicts a miss",
                    "add `confirmed` (the reply to the 24-hour reminder)."))
    if "format" not in h:
        out.append(("In person, video and phone", "add `format`."))
    if data["kind"] == "pipeline":
        out.append(("What happens after a miss", "a pipeline export keeps one "
                    "row per application, so rebookings are invisible. A booking "
                    "log with one row per booking shows them."))
    else:
        out.append(("Who was never booked", "a booking log only holds people "
                    "who got a slot. Run your pipeline export too for the count "
                    "of screened candidates who never got one."))
    out.append(("Whether the reminders work", "reminded and unreminded "
                "candidates differ in ways a send log cannot undo. It takes a "
                "holdout; see the measurement plan."))
    return [{"what": w, "why": y} for w, y in out]


def analyse(data):
    recs = data["records"]
    peak = busy_weeks([r for r in recs if r["outcome"] != "open"])
    count = count_section(data)
    lag = lag_section(data)
    cal = calendar_section(data, peak) if lag else None
    drivers = run_drivers(data, peak)
    if lag:
        w = next((d for d in drivers if d["key"] == "wait_4plus"), None)
        lag["rule_days"] = 3 if (w and w["verdict"] == "survives" and w["adjusted"] > 0) else None
    rec = recovery_section(data)
    reply = reply_section(data)
    weeks = {week_key(r) for r in recs}
    weekly = round(len(recs) / len(weeks)) if weeks else None
    timing = timing_section(data) if lag else None
    out = {
        "engine": f"interview-no-show-playbook {VERSION}",
        "input": {"kind": data["kind"], "file": os.path.basename(data["path"]),
                  "rows": data["rows"], "as_of": data["as_of"].isoformat(),
                  "appointment_times": data["appt_timed"], "notes": data["notes"]},
        "count": count, "lag": lag, "calendar": cal, "timing": timing,
        "drivers": drivers, "recovery": rec, "reply": reply,
        "busy_weeks": sorted(peak),
        "measurement": holdout_plan(count, weekly),
        "cannot": cannot_section(data),
    }
    if data["kind"] == "pipeline":
        nb = data["never_booked"]
        total = sum(nb.values())
        slot = sum(v for k, v in nb.items() if "slot" in k)
        rates = {}
        for site, n in data["screened_site"].items():
            if site is None or n < MIN_ARM:
                continue
            c = data["never_site"].get(site, {})
            rates[site] = (sum(v for kk, v in c.items() if "slot" in kk), n)
        conc = None
        if slot and rates:
            vals = sorted(k / n for k, n in rates.values())
            med = vals[len(vals) // 2]
            top = sorted(s for s, (k, n) in rates.items() if k / n >= max(0.05, 3 * med))
            if top and len(top) <= 0.5 * len(rates):
                conc = {"sites": top, "of_sites": len(rates),
                        "share": sum(rates[s][0] for s in top) / slot}
        out["never_booked"] = {"total": total, "reasons": dict(sorted(
            nb.items(), key=lambda kv: -kv[1])), "no_slot": slot, "no_slot_sites": conc,
            "against_misses": count["no_show"]}
    return out


def timing_section(data):
    st = [r for r in first_standing(data) if r["appt"] is not None]
    out = {"weekday": [], "hour": [], "weekend_wait": None}
    for d in range(7):
        rs = [r for r in st if r["appt"].weekday() == d]
        if rs:
            k = sum(r["outcome"] == "no_show" for r in rs)
            out["weekday"].append({"day": WEEKDAYS[d], "n": len(rs), "miss_rate": k / len(rs)})
    if data["appt_timed"]:
        for name, lo, hi in HOUR_BANDS:
            rs = [r for r in st if lo <= r["appt"].hour <= hi]
            if rs:
                k = sum(r["outcome"] == "no_show" for r in rs)
                out["hour"].append({"band": name, "n": len(rs), "miss_rate": k / len(rs)})
    slots = [r for r in st if r["slots"] is not None]
    if slots:
        rows = []
        for name, test in (("1", lambda s: s == 1), ("2-3", lambda s: 2 <= s <= 3),
                           ("4+", lambda s: s >= 4)):
            rs = [r for r in slots if test(r["slots"])]
            if rs:
                k = sum(r["outcome"] == "no_show" for r in rs)
                lags = sorted(lag_days(r) for r in rs)
                rows.append({"slots": name, "n": len(rs), "miss_rate": k / len(rs),
                             "median_wait": lags[len(lags) // 2]})
        out["slots"] = rows
    return out


# ============================================================== playbook ====

PLACEHOLDER_WIDTH = {"date": 9, "time": 7, "slot_1": 18, "slot_2": 18,
                     "link": 23, "day": 9}
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
           "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM7_EXT = set("^{}\\[~]|€")
LOGIN_WORDS = re.compile(r"\b(log ?in|sign ?in|portal|password|create an account|"
                         r"your account)\b", re.I)
BLAME_WORDS = re.compile(r"\b(no[- ]?show|failed to|you failed|unfortunately|"
                         r"disqualif|we regret)\b", re.I)


def sms_length(text):
    """(characters as the phone counts them, unicode?, offending character)."""
    t = re.sub(r"\{(\w+)\}", lambda m: "x" * PLACEHOLDER_WIDTH.get(m.group(1), 20), text)
    bad = next((ch for ch in t if ch not in GSM7 and ch not in GSM7_EXT), None)
    if bad:
        return len(t), True, bad
    return sum(2 if ch in GSM7_EXT else 1 for ch in t), False, None


def sms_limit(unicode):
    return 134 if unicode else 306          # two segments, as the phone splits them


def fill(text, facts):
    keep = set(PLACEHOLDER_WIDTH)
    def rep(m):
        k = m.group(1)
        if k in keep:
            return m.group(0)
        v = facts.get(k)
        return str(v) if v not in (None, "") else m.group(0)
    return re.sub(r"\{(\w+)\}", rep, text)


FACT_FIELDS = ["company", "role", "site", "landmark", "ask_for",
               "duration_minutes", "bring", "call_number"]


def read_facts(path):
    try:
        with open(path, encoding="utf-8") as fh:
            facts = json.load(fh)
    except UnicodeDecodeError:
        raise Refused("the facts file is not UTF-8")
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"cannot read the facts file: {e}")
    if not isinstance(facts, dict):
        raise Refused("the facts file must be a JSON object")
    missing = [f for f in FACT_FIELDS if not str(facts.get(f, "")).strip()]
    if missing:
        raise Refused("the facts file is missing " + ", ".join(missing)
                      + ". Every message names these; I will not invent them.")
    return facts


def plan_sequence(analysis):
    """Which touches, from the wait the data shows."""
    lag = (analysis or {}).get("lag") or {}
    max_ok = lag.get("rule_days")
    med = lag.get("median_days")
    long_wait = (med is not None and med >= 4) or (lag.get("share_4plus") or 0) >= 0.25
    reply = (analysis or {}).get("reply") or {}
    touches = ["confirm"]
    if long_wait or med is None:
        touches.append("reminder_48h")
    touches += ["reminder_24h", "morning_of", "missed", "second_offer", "close"]
    return touches, max_ok, reply


TEMPLATES = {
    "confirm": ("at_booking",
                "{company}: you're booked for your {role} interview, {date} at {time}, "
                "about {duration_minutes} min. Go to {landmark} and ask for {ask_for}. "
                "Bring {bring}. Need to move it? Reply 2. Reply STOP to opt out."),
    "reminder_48h": ("-48h",
                     "{company}: your {role} interview is {date} at {time}, at "
                     "{landmark}. Still good? Reply 2 if you need another time."),
    "reminder_24h": ("-24h",
                     "{company}: see you tomorrow at {time} for your {role} interview. "
                     "Reply 1 if you're coming, 2 if you need to move it."),
    "morning_of": ("day_of 08:00",
                   "{company}: today at {time}. {landmark}, ask for {ask_for}. "
                   "Running late or stuck? Call {call_number}."),
    "missed": ("+30m",
               "{company}: we missed you at {time}. Things happen. Want another "
               "{role} interview? Reply A for {slot_1} or B for {slot_2}."),
    "second_offer": ("on_reply",
                     "{company}: thanks for getting back to us. I can do {slot_1} "
                     "or {slot_2}. Reply A or B and you're booked."),
    "close": ("after_second_miss",
              "{company}: we've closed this {role} application for now. You're "
              "welcome to apply again whenever the timing works."),
}
POLICY_DEFAULT = {"reoffers_after_first_miss": 1, "second_offer_only_on_reply": True,
                  "close_after_silent_misses": 2, "reapply_eligible": True,
                  "reject_on_first_miss": False}


def build_playbook(analysis, facts):
    touches, max_ok, reply = plan_sequence(analysis)
    seq = []
    for t in touches:
        when, text = TEMPLATES[t]
        seq.append({"id": t, "when": when, "text": fill(text, facts)})
    policy = dict(POLICY_DEFAULT)
    if reply and reply.get("separates"):
        policy["release_unconfirmed_hours_before"] = 3
    rules = slot_rules(analysis, facts)
    doc = {"facts": facts, "touches": seq, "policy": policy, "rules": rules,
           "tuned": analysis is not None}
    doc["check"] = check_sequence(doc)
    return doc


def driver(analysis, key):
    for d in analysis.get("drivers", []):
        if d["key"] == key:
            return d
    return None


def slot_rules(analysis, facts):
    rules = []
    if analysis is None:
        rules.append({"rule": "Book every interview within 3 days.",
                      "why": "A default, not your data: no booking log was read."})
        rules.append({"rule": "Offer at least two slots.",
                      "why": "A default, not your data."})
        rules.append({"rule": "No overbooking unless someone can take a walk-in.",
                      "why": "A double-booked slot where both come costs a candidate."})
        return rules
    lag = analysis.get("lag")
    d = driver(analysis, "wait_4plus")
    if lag and d and d["verdict"] == "survives" and d["adjusted"] > 0:
        rules.append({
            "rule": "Book every interview within 3 days.",
            "why": (f"A wait of 4 days or more misses {points(d['adjusted'])} more often "
                    f"at the same site and in the same role. {pct(lag['share_4plus'])} of "
                    f"interviews waited that long: about {d['recoverable']:.0f} "
                    "interviews lost to the wait over the period.")})
    cal = (analysis.get("calendar") or {}).get("sites") or []
    for s in cal:
        if s["causes"]:
            rules.append({"rule": f"{s['site']}: open a second interview day.",
                          "why": (f"{cap('; '.join(s['causes']))}. Median wait "
                                  f"{s['median_days']} days, {pct(s['share_4plus'])} "
                                  "of bookings 4 or more days out.")})
    d = driver(analysis, "one_slot")
    if d and d["verdict"] == "survives":
        rules.append({"rule": "Offer at least two slots, always.",
                      "why": f"One-slot bookings miss {points(d['adjusted'])} more often at the same wait."})
    for x in analysis.get("drivers", []):
        if x["family"] == "hour" and x["verdict"] == "survives" and x["adjusted"] > 0:
            band = x["key"].split(":", 1)[1]
            rules.append({"rule": f"Stop offering {band} slots, or keep them for "
                                  "candidates who choose them.",
                          "why": f"They miss {points(x['adjusted'])} more often in the same role at the same wait."})
    d = driver(analysis, "weekend_wait")
    if d and d["verdict"] == "survives":
        rules.append({"rule": "When the wait would cross a weekend, offer the slot "
                              "before it first; if they take the later one, add the "
                              "48-hour touch.",
                      "why": f"A weekend inside the wait costs {points(d['adjusted'])} at the same wait."})
    for x in analysis.get("drivers", []):
        if x["family"] == "site" and x["verdict"] == "survives" and x["adjusted"] > 0:
            rules.append({"rule": f"{x['key'].split(':', 1)[1]}: write the door, not the "
                                  "address, into every confirmation, and check it with "
                                  "someone who has never been there.",
                          "why": f"It misses {points(x['adjusted'])} more often in the same week at "
                                 "the same wait: something about getting there."})
    for x in analysis.get("drivers", []):
        if x["family"] == "role" and x["verdict"] == "survives" and x["adjusted"] > 0:
            role = x["key"].split(":", 1)[1]
            rules.append({"rule": f"{role}: ask the last ten who missed why, before "
                                  "changing anything for this role.",
                          "why": f"It misses {points(x['adjusted'])} more often at the same "
                                 "site and wait, and nothing in the file explains it."})
    d = driver(analysis, "busy_weeks")
    if d and d["verdict"] == "survives" and d["adjusted"] > 0:
        rules.append({"rule": "Before your busy weeks, add interview slots and use the "
                              "48-hour touch for every booking.",
                      "why": f"Busy weeks miss {points(d['adjusted'])} more often at the "
                             "same site, beyond what the file can attribute to anything else."})
    nb = analysis.get("never_booked")
    if nb and nb.get("no_slot_sites"):
        c = nb["no_slot_sites"]
        rules.append({"rule": f"{', '.join(c['sites'])}: open more interview slots first.",
                      "why": f"{pct(c['share'])} of the {nb['no_slot']:,} screened candidates "
                             "who never got a slot were at these sites. A slot nobody is "
                             "offered cannot be attended."})
    reply = analysis.get("reply")
    if reply and reply.get("separates"):
        rules.append({"rule": "No reply to the 24-hour reminder by 3 hours before: "
                              "one call. Still nothing: release the slot to the "
                              "standby list.",
                      "why": (f"Unanswered reminders missed {pct(reply['none']['miss_rate'])} of the "
                              f"time, confirmed ones {pct(reply['coming']['miss_rate'])}.")})
    rec = analysis.get("recovery")
    if rec and rec["never_sites"]:
        rules.append({"rule": f"{', '.join(rec['never_sites'])}: rebook every first "
                              "miss within the hour.",
                      "why": (f"No miss there was ever rebooked ({rec['never_site_misses']} "
                              "misses). At the rate the other sites rebook and recover, "
                              f"about {rec['recoverable_at_never_sites']:.0f} more interviews.")})
    rules.append({"rule": "No overbooking unless someone can take a walk-in.",
                  "why": "A double-booked slot where both come costs a candidate."})
    return rules


# ================================================================== check ====

WHEN_RE = re.compile(r"^(at_booking|on_reply|after_second_miss|-(\d+)h|\+(\d+)m|"
                     r"day_of (\d{1,2}):(\d{2}))$")
REQUIRED = {
    "confirm": ["company", "role", "date", "time", "place", "ask_for", "duration",
                "bring", "move", "stop"],
    "reminder_48h": ["company", "date", "time", "place", "move"],
    "reminder_24h": ["company", "time", "reply_two"],
    "morning_of": ["company", "time", "place", "call"],
    "missed": ["company", "two_slots"],
    "second_offer": ["company", "two_slots"],
    "close": ["company", "reapply"],
}
ELEMENT_LABEL = {
    "company": "who is writing (the company)", "role": "the role",
    "date": "the date", "time": "the time",
    "place": "where to go (the landmark or door)", "ask_for": "who to ask for",
    "duration": "how long it takes", "bring": "what to bring",
    "move": "how to move it", "stop": "how to opt out (STOP)",
    "reply_two": "two reply options, coming and moving it",
    "call": "one number to call", "two_slots": "two concrete slots",
    "reapply": "that they can apply again",
}


def has_element(el, text, facts):
    t = text.lower()
    lit = lambda k: (bool(facts.get(k)) and str(facts[k]).lower() in t) or "{" + k + "}" in text
    if el == "company":
        return lit("company")
    if el == "role":
        return lit("role")
    if el == "date":
        return "{date}" in text or "tomorrow" in t or "today" in t
    if el == "time":
        return "{time}" in text
    if el == "place":
        return lit("landmark") or lit("address")
    if el == "ask_for":
        return lit("ask_for")
    if el == "duration":
        return lit("duration_minutes") and ("min" in t or "minute" in t)
    if el == "bring":
        return lit("bring")
    if el == "move":
        return ("{link}" in text or (
            bool(re.search(r"\b(reply|text|call)\b", t))
            and bool(re.search(r"\b(move|another time|reschedul|change)", t))))
    if el == "stop":
        return "stop" in t
    if el == "reply_two":
        body = re.sub(r"\{\w+\}", " ", text)
        codes = {c for c in re.findall(r"\b(?:[0-9]|[A-Z]{1,5})\b", body)
                 if c not in ("I", "STOP")}
        return (bool(re.search(r"\b(reply|text)\b", t)) and len(codes) >= 2
                and bool(re.search(r"(coming|confirm|see you|yes)", t))
                and bool(re.search(r"(move|another time|reschedul|change)", t)))
    if el == "call":
        return lit("call_number")
    if el == "two_slots":
        return ("{slot_1}" in text and "{slot_2}" in text)
    if el == "reapply":
        return bool(re.search(r"apply again|reapply|re-apply", t))
    return False


def check_sequence(doc):
    """Blocks a sequence, with the reason, until every rule passes."""
    findings = []
    facts = doc.get("facts") or {}
    touches = doc.get("touches")
    if not isinstance(touches, list) or not touches:
        return {"ready": False, "findings": [{"touch": "-", "rule": "structure",
                                              "problem": "no touches"}]}
    ids = []
    pre = 0
    for t in touches:
        if not isinstance(t, dict):
            findings.append({"touch": "-", "rule": "structure", "problem": "a touch is not an object"})
            continue
        tid = str(t.get("id", ""))
        text = t.get("text")
        when = str(t.get("when", ""))
        ids.append(tid)
        if not isinstance(text, str) or not text.strip():
            findings.append({"touch": tid, "rule": "text", "problem": "empty"})
            continue
        if tid not in REQUIRED:
            findings.append({"touch": tid, "rule": "kind",
                             "problem": "unknown touch; use " + ", ".join(REQUIRED)})
            continue
        m = WHEN_RE.match(when)
        if not m:
            findings.append({"touch": tid, "rule": "timing",
                             "problem": f"'{when}' is not a timing I can read"})
        else:
            if m.group(2):
                pre += 1
            if tid == "confirm" and when != "at_booking":
                findings.append({"touch": tid, "rule": "timing",
                                 "problem": "the confirmation goes at the moment of booking"})
            if tid == "reminder_24h" and not (m.group(2) and 18 <= int(m.group(2)) <= 30):
                findings.append({"touch": tid, "rule": "timing",
                                 "problem": "the reply reminder goes about 24 hours before"})
            if tid == "reminder_48h" and not (m.group(2) and 36 <= int(m.group(2)) <= 72):
                findings.append({"touch": tid, "rule": "timing",
                                 "problem": "the 48-hour touch goes 36 to 72 hours before"})
            if tid == "morning_of":
                ok = (m.group(4) and 8 <= int(m.group(4)) <= 11) or (
                    m.group(2) and 2 <= int(m.group(2)) <= 4)
                if not ok:
                    findings.append({"touch": tid, "rule": "timing",
                                     "problem": "the day-of message goes in the morning, "
                                                "from 08:00, at least 2 hours before"})
            if tid == "missed" and not (m.group(3) and int(m.group(3)) <= 60):
                findings.append({"touch": tid, "rule": "timing",
                                 "problem": "the re-offer goes within the hour of the missed slot"})
            if tid == "second_offer" and when != "on_reply":
                findings.append({"touch": tid, "rule": "timing",
                                 "problem": "a second offer goes only if they reply"})
        for el in REQUIRED[tid]:
            if not has_element(el, text, facts):
                findings.append({"touch": tid, "rule": "content",
                                 "problem": "missing " + ELEMENT_LABEL[el]})
        n, uni, bad = sms_length(text)
        limit = sms_limit(uni)
        if uni:
            findings.append({"touch": tid, "rule": "length",
                             "problem": f"'{bad}' switches the text to Unicode: "
                                        f"{n} characters against {limit} in two parts"})
        elif n > limit:
            findings.append({"touch": tid, "rule": "length",
                             "problem": f"{n} characters, over two text messages ({limit})"})
        if LOGIN_WORDS.search(text):
            findings.append({"touch": tid, "rule": "no login",
                             "problem": "asks them to log in or use a portal"})
        if tid in ("missed", "second_offer", "close") and BLAME_WORDS.search(text):
            findings.append({"touch": tid, "rule": "tone",
                             "problem": "blames the candidate; a miss is usually logistics"})
    for need in ("confirm", "reminder_24h", "morning_of", "missed"):
        if need not in ids:
            findings.append({"touch": need, "rule": "sequence", "problem": "missing"})
    if pre > 4:
        findings.append({"touch": "-", "rule": "sequence",
                         "problem": f"{pre} reminders before the interview; past three "
                                    "the returns are near zero. Shorten the wait instead."})
    if ids and ids[0] != "confirm":
        findings.append({"touch": ids[0], "rule": "sequence",
                         "problem": "the confirmation comes first"})
    policy = doc.get("policy") or {}
    if policy.get("reject_on_first_miss"):
        findings.append({"touch": "policy", "rule": "no auto-reject",
                         "problem": "rejecting at the first miss throws away a candidate "
                                    "you already paid for; re-offer once within the hour"})
    if policy.get("close_after_silent_misses") not in (2,):
        findings.append({"touch": "policy", "rule": "stop rule",
                         "problem": "close after the second silent miss, not sooner, not later"})
    if policy.get("reapply_eligible") is not True:
        findings.append({"touch": "policy", "rule": "stop rule",
                         "problem": "keep a closed candidate eligible to apply again"})
    return {"ready": not findings, "findings": findings}


def load_messages(path):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except UnicodeDecodeError:
        raise Refused("the messages file is not UTF-8")
    except (OSError, json.JSONDecodeError) as e:
        raise Refused(f"cannot read the messages file: {e}")
    if not isinstance(doc, dict) or not isinstance(doc.get("touches"), list):
        raise Refused("the messages file needs a \"touches\" list "
                      "(see references/sample/fernhill_messages.json)")
    facts = doc.get("facts")
    if not isinstance(facts, dict) or any(not str(facts.get(f, "")).strip()
                                          for f in FACT_FIELDS):
        raise Refused("the messages file needs \"facts\" (" + ", ".join(FACT_FIELDS)
                      + ") so I can check that each message names them")
    return doc


# =============================================================== render =====

def md_report(a):
    L = []
    inp = a["input"]
    c = a["count"]
    L.append("# Interview no-shows: the read")
    L.append("")
    kind = ("booking log, one row per booked interview" if inp["kind"] == "bookings"
            else "pipeline export, one row per application")
    L.append(f"{inp['file']}: {inp['rows']:,} rows ({kind}), read as of {inp['as_of']}.")
    for n in inp["notes"]:
        L.append(f"- {n}")
    L.append("")
    L.append("## 1. The miss, counted honestly")
    L.append("")
    L.append("| | Count | Share |")
    L.append("|---|---:|---:|")
    due = c["due"] or 1
    rows_shown = (("attended", "Held"), ("no_show", "Silent no-show"),
                  ("cancelled", "Cancelled in advance"), ("rescheduled", "Moved in advance"))
    for k, lab in rows_shown:
        if k in ("cancelled", "rescheduled") and not c["separated"]:
            continue
        if not c["separated"] and k == "no_show":
            lab = "Missed (silent or cancelled, not separated)"
        L.append(f"| {lab} | {c[k]:,} | {pct(c[k] / due)} |")
    L.append("")
    if c["miss_rate"] is not None:
        left = [f"{lab} ({c[k]:,})" for k, lab in (("employer_cancelled", "employer cancellations"),
                                                    ("open", "upcoming interviews")) if c[k]]
        L.append(f"Of interviews still standing on the day, **{pct(c['miss_rate'])} were "
                 f"missed** ({c['no_show']:,} of {c['attended'] + c['no_show']:,})."
                 + (f" Left out: {', '.join(left)}." if left else ""))
    if not c["separated"]:
        L.append("This export does not separate a cancellation from a silent miss, "
                 "so the rate above is combined.")
    if c["first_miss"] and inp["kind"] == "bookings":
        L.append(f"Per candidate: {c['first_miss']:,} missed their first interview; "
                 f"{c['rescued']:,} were rebooked and came, so "
                 f"{c['lost_after_miss']:,} were lost to a miss. Counting first "
                 "appointments alone overstates the loss and hides a reschedule path that works.")
    nb = a.get("never_booked")
    if nb:
        L.append("")
        why = ", ".join(f"{k.replace('_', ' ')} {v:,}" for k, v in list(nb["reasons"].items())[:5])
        L.append(f"**Never booked.** {nb['total']:,} candidates cleared screening and "
                 f"never got an interview ({why}): {nb['no_slot']:,} of them for want "
                 f"of a slot, against {nb['against_misses']:,} missed interviews.")
        if nb["no_slot_sites"]:
            s = nb["no_slot_sites"]
            L.append(f"{pct(s['share'])} of the no-slot losses sit at "
                     f"{len(s['sites'])} of {s['of_sites']} sites: {', '.join(s['sites'])}. "
                     "There is no point tuning attendance on a slot nobody was offered.")
    L.append("")
    lag = a.get("lag")
    L.append("## 2. The wait between booking and interview")
    L.append("")
    if not lag:
        L.append("Could not be read: a missed interview has no interview date in "
                 "this export. Computing the wait from completed interviews only "
                 "would describe the people who came. Add `interview_at` for every booking.")
    else:
        L.append("| Wait | Interviews | Missed | 95% range | Cancelled ahead |")
        L.append("|---|---:|---:|---|---:|")
        for b in lag["bands"]:
            if b["n"]:
                lo, hi = b["range"]
                L.append(f"| {b['band']} | {b['n']:,} | {pct(b['miss_rate'])} | "
                         f"{pct(lo)}-{pct(hi)} | {b['cancelled_ahead']:,} |")
        L.append("")
        L.append(f"Median wait {lag['median_days']} days.")
        L.append(f"{pct(lag['share_4plus'])} of interviews waited 4 days or more.")
        d = next((x for x in a["drivers"] if x["key"] == "wait_4plus"), None)
        if d and d["verdict"] == "survives":
            L.append(f"At the same site and in the same role, a wait of 4+ days costs "
                     f"{pts(d['adjusted'])}: about {d['recoverable']:.0f} interviews "
                     "over the period. A reminder cannot fix a wait; a slot rule can.")
        elif d:
            L.append("The wait does not survive its checks in this file.")
        cal = a.get("calendar") or {}
        if cal.get("sites"):
            L.append("")
            L.append("**The calendar behind it.**")
            L.append("")
            for s in cal["sites"]:
                why = "; ".join(s["causes"]) or "no single cause in the file"
                eff = ""
                if s["raw"] is not None and s["after_wait"] is not None:
                    if s["after_wait"] < 0.02:
                        verdict = "the wait is the problem, not the site."
                    elif s["after_wait"] >= 0.5 * s["raw"]:
                        verdict = "something beyond the wait too."
                    else:
                        verdict = "mostly the wait."
                    eff = (f" Misses {pts(s['raw'])} against the other sites, "
                           f"{pts(s['after_wait'])} at the same wait: {verdict}")
                L.append(f"- {s['site']}: median wait {s['median_days']} days, "
                         f"{pct(s['share_4plus'])} 4+ days out. {cap(why)}.{eff}")
        if cal.get("peak"):
            p = cal["peak"]
            eff = (f" Misses {pts(p['raw'])}, {pts(p['after_wait'])} at the same wait."
                   if p["raw"] is not None and p["after_wait"] is not None else "")
            L.append(f"- Busy weeks ({len(a['busy_weeks'])} weeks): median wait "
                     f"{p['median_peak']} days against {p['median_other']}; "
                     f"{pct(p['share4_peak'])} 4+ days out against {pct(p['share4_other'])}.{eff}")
    L.append("")
    t = a.get("timing")
    if t:
        L.append("## 3. Slots and timing")
        L.append("")
        if t["hour"]:
            L.append("| Slot | Interviews | Missed |")
            L.append("|---|---:|---:|")
            for h in t["hour"]:
                L.append(f"| {h['band']} | {h['n']:,} | {pct(h['miss_rate'])} |")
            L.append("")
        if t.get("slots"):
            L.append("| Slots offered | Interviews | Missed | Median wait |")
            L.append("|---|---:|---:|---:|")
            for s in t["slots"]:
                L.append(f"| {s['slots']} | {s['n']:,} | {pct(s['miss_rate'])} | "
                         f"{s['median_wait']} days |")
            L.append("")
        wd = ", ".join(f"{w['day'][:3]} {pct(w['miss_rate'])}" for w in t["weekday"]
                       if w["n"] >= MIN_ARM)
        if wd:
            L.append(f"By interview day: {wd}. Read it with the weekend driver in "
                     "section 4: a Monday interview usually has a weekend in its wait.")
            L.append("")
    L.append("## 4. What drives it, tested within strata")
    L.append("")
    surv = [d for d in a["drivers"] if d["verdict"] == "survives"]
    expl = [d for d in a["drivers"] if d["verdict"] == "explained"]
    insep = [d for d in a["drivers"] if d["verdict"] == "cannot separate"]
    if surv:
        L.append("| Driver | Raw | After checks | Interviews | Recoverable |")
        L.append("|---|---:|---:|---:|---:|")
        for d in surv:
            L.append(f"| {d['label']} | {pts(d['raw'])} | {pts(d['adjusted'])} | "
                     f"{d['n_exposed']:,} | ~{d['recoverable']:.0f} |")
        L.append("")
        L.append("After checks: the smallest effect left inside any one stratum check. "
                 "Recoverable: interviews held over the period if that one cause went; "
                 "they overlap and do not add up.")
    else:
        L.append("Nothing in the file survives its checks. The miss is spread evenly "
                 "enough that no single site, slot or channel explains it.")
    if expl:
        L.append("")
        L.append("**Explained by something else**, so no rule is built on them:")
        L.append("")
        for d in expl:
            L.append(f"- {d['label']}: {pts(d['raw'])} raw, explained by "
                     f"{'the wait' if d['explained_by'] == 'wait' else d['explained_by']}.")
    if insep:
        L.append("")
        for d in insep:
            L.append(f"- {d['label']} ({pts(d['raw'])} raw) cannot be separated "
                     f"from its {', '.join(d['inseparable_from'])} in this file.")
    L.append("")
    rec = a.get("recovery")
    if rec:
        L.append("## 5. After a miss")
        L.append("")
        L.append(f"{rec['misses']:,} first misses at least {rec['window_days']} days old: "
                 f"{rec['rebooked']:,} rebooked, {rec['recovered']:,} of them came; "
                 f"{rec['never_rebooked']:,} never rebooked.")
        L.append("")
        L.append("| Rebooked | Misses | Share | Then attended |")
        L.append("|---|---:|---:|---:|")
        for b in rec["bands"]:
            ar = pct(b["attend_rate"]) if b["attend_rate"] is not None else "-"
            L.append(f"| {b['band']} | {b['rebooked']:,} | {pct(b['share_of_misses'])} | {ar} |")
        L.append(f"| never | {rec['never_rebooked']:,} | "
                 f"{pct(rec['never_rebooked'] / rec['misses'])} | - |")
        L.append("")
        L.append("The log shows rebookings, not offers: an offer nobody took is "
                 "invisible, and someone who answers within the hour was keener to "
                 "begin with. Speed and interest are mixed in this table.")
        if rec["never_sites"]:
            L.append("")
            L.append(f"**What the log does prove:** at {', '.join(rec['never_sites'])} "
                     f"no first miss was ever rebooked ({rec['never_site_misses']:,} misses), "
                     f"while the other sites rebooked {pct(rec['others_rebook_rate'])}. "
                     "That is a rule, not candidate choice.")
        L.append("")
    rp = a.get("reply")
    if rp:
        L.append("## 6. The reply to the 24-hour reminder")
        L.append("")
        for k, lab in (("coming", "Replied coming"), ("none", "No reply"),
                       ("move", "Asked to move")):
            x = rp[k]
            if x["n"]:
                L.append(f"- {lab}: {x['n']:,} interviews, {pct(x['miss_rate'])} missed.")
        if rp["separates"]:
            L.append(f"A missing reply flags {pct(rp['share_of_misses_flagged'])} of the "
                     "misses a day ahead: early enough to call once and refill the slot. "
                     "This predicts a miss; it does not show the reminder causes anything.")
        L.append("")
    L.append("## 7. What I could not determine")
    L.append("")
    for x in a["cannot"]:
        L.append(f"- **{x['what']}**: {x['why']}")
    L.append("")
    m = a.get("measurement")
    if m:
        L.append("## 8. Measurement plan")
        L.append("")
        L.append(f"Watch two numbers weekly: misses by wait band, and interviews held "
                 f"per slot offered. To prove a new reminder works, keep the old one for "
                 f"a random share of bookings (by the last digit of the id) and compare: "
                 f"to see a {100 * m['detect_points']:.0f}-point change you need "
                 f"{m['per_arm']:,} bookings on each side. At {m['weekly_bookings']:,} "
                 f"bookings a week that is about {m['weeks_50']} weeks half and half, "
                 f"or {m['weeks_20']} weeks holding out 20%.")
    return "\n".join(L).rstrip() + "\n"


def md_playbook(pb):
    L = ["# The playbook", ""]
    if not pb["tuned"]:
        L.append("Not tuned to your data: no booking log was read, so the rules below "
                 "are defaults and the sequence assumes waits of several days.")
        L.append("")
    L.append("## Slot rules")
    L.append("")
    for i, r in enumerate(pb["rules"], 1):
        L.append(f"{i}. **{r['rule']}** {r['why']}")
    L.append("")
    L.append("## The sequence (SMS)")
    L.append("")
    when_label = {"at_booking": "At booking", "-48h": "48 hours before",
                  "-24h": "24 hours before", "day_of 08:00": "Morning of, 08:00",
                  "+30m": "30 minutes after a missed slot",
                  "on_reply": "Only if they reply", "after_second_miss": "After a second silent miss"}
    for t in pb["touches"]:
        n, uni, _ = sms_length(t["text"])
        L.append(f"**{when_label.get(t['when'], t['when'])}** ({t['id']}, about {n} characters)")
        L.append("")
        L.append(f"> {t['text']}")
        L.append("")
    p = pb["policy"]
    L.append("## The reschedule path")
    L.append("")
    L.append("- One re-offer within the hour of a missed slot, with two concrete slots.")
    L.append("- A second offer only if they reply.")
    L.append(f"- Close after the {p['close_after_silent_misses']}nd silent miss, record the "
             "reason, and keep them eligible to apply again.")
    if p.get("release_unconfirmed_hours_before"):
        L.append(f"- No reply to the 24-hour reminder by {p['release_unconfirmed_hours_before']} "
                 "hours before: one call, then release the slot to the standby list.")
    L.append("")
    ck = pb["check"]
    if ck["ready"]:
        L.append("**Check:** every message names who is writing, the role, when, where by "
                 "landmark, who to ask for and how to move it; two text messages at most; "
                 "no login; re-offer within the hour; stop rule set. READY.")
    else:
        L.append("**Check: NOT READY.**")
        for f in ck["findings"]:
            L.append(f"- {f['touch']}: {f['problem']}")
    return "\n".join(L).rstrip() + "\n"


def md_check(res):
    if res["ready"]:
        return "READY: every rule passes.\n"
    L = ["NOT READY. Fix these:"]
    for f in res["findings"]:
        L.append(f"- [{f['touch']}] {f['rule']}: {f['problem']}")
    return "\n".join(L) + "\n"


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, float):
        return round(x, 4)
    if isinstance(x, (dt.date, dt.datetime)):
        return x.isoformat()
    return x


# ================================================================== tests ====

def run_tests():
    import tempfile
    sys.dont_write_bytecode = True
    sys.path.insert(0, SAMPLE_DIR)
    import generate                                    # noqa: E402
    passed, failed = [0], []

    def ok(cond, name):
        if cond:
            passed[0] += 1
        else:
            failed.append(name)

    tmp = tempfile.mkdtemp(prefix="noshow-test-")

    def write_rows(name, rows, fields=None):
        p = os.path.join(tmp, name)
        fields = fields or list(rows[0].keys())
        with open(p, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        return p

    def refused(path, needle=""):
        try:
            load(path)
        except Refused as e:
            return needle.lower() in str(e).lower()
        return False

    # --- the planted world ------------------------------------------------
    exp = json.load(open(os.path.join(SAMPLE_DIR, "fernhill_expected.json"), encoding="utf-8"))
    a = analyse(load(SAMPLE_LOG, dt.date(2026, 10, 31)))
    ver = {d["key"]: d for d in a["drivers"]}
    for key in exp["survives"]:
        ok(ver.get(key, {}).get("verdict") == "survives", f"planted survives: {key}")
    for key, by in exp["explained"].items():
        d = ver.get(key, {})
        ok(d.get("verdict") == "explained" and d.get("explained_by") == by,
           f"planted explained: {key} by {by} (got {d.get('verdict')} {d.get('explained_by')})")
    surv_keys = {d["key"] for d in a["drivers"] if d["verdict"] == "survives"}
    ok(surv_keys == set(exp["survives"]), f"no other survivor: {sorted(surv_keys - set(exp['survives']))}")
    for key in exp["null"]:
        ok(ver.get(key, {}).get("verdict") in ("no effect", "thin", "fewer misses"),
           f"null stays null: {key}")
    bands = {b["band"]: b for b in a["lag"]["bands"]}
    ok(bands["8+ days"]["miss_rate"] - bands["1 day"]["miss_rate"] >= 0.12,
       "lag curve climbs")
    ok(a["lag"]["rule_days"] == 3, "3-day booking rule")
    cal_sites = {s["site"] for s in a["calendar"]["sites"]}
    ok(cal_sites == set(exp["one_day_sites"]), f"calendar names the one-day stores: {sorted(cal_sites)}")
    ok(all(any("only" in c for c in s["causes"]) for s in a["calendar"]["sites"]),
       "calendar names the weekday")
    ok(a["calendar"]["peak"]["median_peak"] > a["calendar"]["peak"]["median_other"],
       "busy weeks wait longer")
    ok(sorted(a["recovery"]["never_sites"]) == exp["never_rebook_sites"],
       f"never-rebook sites {a['recovery']['never_sites']}")
    rb = a["recovery"]["bands"]
    ok(rb[0]["attend_rate"] > rb[-1]["attend_rate"] + 0.15, "faster rebook, more attend")
    ok(a["reply"]["separates"] and a["reply"]["none"]["miss_rate"] > 0.3
       and a["reply"]["coming"]["miss_rate"] < 0.12, "no reply flags misses")
    ok(a["count"]["rescued"] > 0 and a["count"]["lost_after_miss"] < a["count"]["first_miss"],
       "per candidate, rescued counted")
    ok(a["count"]["open"] > 0, "upcoming interviews kept out")
    ok(not a["input"]["notes"], f"sample reads clean: {a['input']['notes']}")
    ok(len(a["busy_weeks"]) >= 4, "busy weeks found")
    ok(a["input"]["appointment_times"], "times read")
    ok(json.dumps(jsonable(a), sort_keys=True) ==
       json.dumps(jsonable(analyse(load(SAMPLE_LOG, dt.date(2026, 10, 31)))), sort_keys=True),
       "deterministic")
    md = md_report(a)
    for s in ("## 1.", "## 2.", "## 4.", "## 5.", "## 7.", "LOC-17", "explained by the wait"):
        ok(s in md, f"report shows {s}")
    for key, by in exp["cannot_separate"].items():
        d = ver.get(key, {})
        ok(d.get("verdict") == "cannot separate" and by in d.get("inseparable_from", []),
           f"cannot separate: {key} from {by}")
    ok("LOC-17" in [d["key"].split(":")[1] for d in a["drivers"]
                    if d["verdict"] == "survives" and d["family"] == "site"], "LOC-17 is the site")
    ok("interviewer:MGR-17A" not in surv_keys, "LOC-17's interviewer not reported apart from the site")

    # --- the null world and the shuffled world -------------------------------
    plain = generate.build(planted=False)
    p = write_rows("plain.csv", plain, generate.FIELDS)
    a0 = analyse(load(p))
    s0 = [d["key"] for d in a0["drivers"] if d["verdict"] == "survives"]
    ok(not s0, f"null world: nothing survives ({s0})")
    ok(not a0["recovery"]["never_sites"], "null world: no never-rebook site")
    ok(not a0["reply"]["separates"], "null world: reply does not separate")
    for seed in (1, 2, 3):
        rows = [dict(r) for r in csv.DictReader(open(SAMPLE_LOG, encoding="utf-8"))]
        idx = [i for i, r in enumerate(rows) if r["outcome"] in ("attended", "no_show")]
        outs = [rows[i]["outcome"] for i in idx]
        random.Random(seed).shuffle(outs)
        for i, o in zip(idx, outs):
            rows[i]["outcome"] = o
        ps = write_rows(f"shuffled{seed}.csv", rows, generate.FIELDS)
        s = [d["key"] for d in analyse(load(ps))["drivers"] if d["verdict"] == "survives"]
        ok(not s, f"shuffled outcomes ({seed}): nothing survives ({s})")

    # --- a reversal within strata is not reported -------------------------
    rows = []
    rng = random.Random(7)
    k = 0
    for site, share, base in (("S1", .9, .40), ("S2", .1, .10)):
        for _ in range(800):
            k += 1
            expo = rng.random() < share
            miss = rng.random() < base - (.05 if expo else 0)
            b = dt.datetime(2026, 5, 1 + k % 25, 10)
            rows.append({"application_id": f"A{k}", "location_id": site,
                         "slots_offered": 1 if expo else 3,
                         "booked_at": b.strftime("%Y-%m-%d %H:%M"),
                         "interview_at": (b + dt.timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                         "outcome": "no_show" if miss else "attended"})
    p = write_rows("simpson.csv", rows)
    d = {x["key"]: x for x in analyse(load(p))["drivers"]}.get("one_slot", {})
    ok(d.get("raw", 0) > 0.1 and d.get("verdict") == "explained" and d.get("explained_by") == "site",
       f"reversal within sites is explained by site ({d.get('verdict')}, {d.get('explained_by')})")

    # --- a wait that is really a site: explained by site ----------------------
    rows = []
    rng = random.Random(11)
    k = 0
    for site, waits, base in (("LONG", (5, 6, 7, 8, 9), .40), ("SHORT", (1, 2, 3), .15),
                              ("MIX", (1, 2, 5, 6), .25)):
        for _ in range(900):
            k += 1
            b = dt.datetime(2026, 4, 1) + dt.timedelta(days=k % 120, hours=9)
            w = rng.choice(waits)
            rows.append({"application_id": f"W{k}", "location_id": site,
                         "booked_at": b.strftime("%Y-%m-%d %H:%M"),
                         "interview_at": (b + dt.timedelta(days=w)).strftime("%Y-%m-%d %H:%M"),
                         "outcome": "no_show" if rng.random() < base else "attended"})
    p = write_rows("waitsite.csv", rows)
    aw = analyse(load(p))
    d = {x["key"]: x for x in aw["drivers"]}.get("wait_4plus", {})
    ok((d.get("verdict") == "explained" and d.get("explained_by") == "site")
       or (d.get("verdict") == "cannot separate" and "site" in d.get("inseparable_from", [])),
       f"a wait that is really a site is not reported as the wait ({d.get('verdict')})")
    pbw = build_playbook(aw, read_facts(SAMPLE_FACTS))
    ok(not any("within 3 days" in r["rule"] for r in pbw["rules"]), "no 3-day rule built on it")
    ok(pbw["check"]["ready"], "playbook still ready")

    # --- the smallest file I accept ---------------------------------------------
    rows = [{"application_id": f"M{i}", "booked_at": f"2026-05-{1 + i % 20:02d}",
             "interview_at": f"2026-05-{3 + i % 20:02d}",
             "outcome": "no_show" if i % 5 == 0 else "attended"} for i in range(120)]
    p = write_rows("minimal.csv", rows)
    am = analyse(load(p))
    ok(am["lag"] is not None and not am["input"]["appointment_times"],
       "minimal file reads, without times")
    ok("## 7." in md_report(am) and build_playbook(am, read_facts(SAMPLE_FACTS))["check"]["ready"],
       "minimal file: report and playbook")

    # --- reading -------------------------------------------------------------
    ok(parse_when("2026-03-02T17:15:00-05:00")[0] == dt.datetime(2026, 3, 2, 17, 15),
       "offset dropped, wall clock kept")
    ok(parse_when("3/2/2026 5:15 PM")[0] == dt.datetime(2026, 3, 2, 17, 15), "12-hour clock")
    ok(parse_when("2/3/2026", "dmy")[0] == dt.datetime(2026, 3, 2), "day-first when proven")
    ok(parse_when("2026-13-01")[0] is None, "impossible date unread")
    base = {"application_id": "A1", "location_id": "S1", "booked_at": "2026-05-01 10:00",
            "interview_at": "2026-05-03 11:00", "outcome": "attended"}
    def variant(name, change, fields=None, n=200):
        rs = []
        for i in range(n):
            r = dict(base, application_id=f"A{i}")
            change(r, i)
            rs.append(r)
        return write_rows(name, rs, fields)
    ok(refused(variant("pii1.csv", lambda r, i: r.update(candidate_name="x")), "personal"),
       "refuses a name column")
    ok(refused(variant("pii2.csv", lambda r, i: r.update(location_id="a.b@c.com" if i == 5 else "S1")),
               "email"), "refuses an email in a cell")
    ok(refused(variant("pii3.csv", lambda r, i: r.update(location_id="(555) 010-0199" if i == 9 else "S1")),
               "phone"), "refuses a phone number in a cell")
    ok(refused(variant("pii4.csv", lambda r, i: r.update(notes="ok")), "personal"),
       "refuses a notes column")
    ok(refused(variant("pii5.csv", lambda r, i: r.update(hiring_manager_id="Dana Whitfield")),
               "names"), "refuses names in an id column")
    ok(not refused(variant("ok2.csv", lambda r, i: r.update(hiring_manager_id="MGR-17A"))),
       "opaque interviewer ids are fine")
    ok(not refused(variant("ok1.csv", lambda r, i: r.update(store_name="Brookfield"))),
       "store_name is fine")
    ok(refused(variant("mixed.csv", lambda r, i: r.update(
        booked_at="13/05/2026" if i == 1 else "05/14/2026", interview_at="05/20/2026")),
        "both day-first"), "refuses mixed slash dates")
    ok(refused(variant("neg.csv", lambda r, i: r.update(
        interview_at="2026-04-20 10:00" if i % 5 == 0 else r["interview_at"])),
        "before the booking"), "refuses booked_at that is not the booking")
    ok(refused(variant("outc.csv", lambda r, i: r.update(outcome="maybe" if i % 10 == 0 else "attended")),
               "cannot read"), "refuses unknown outcomes")
    ok(refused(variant("dates.csv", lambda r, i: r.update(booked_at="soon" if i % 10 == 0 else r["booked_at"])),
               "not dates"), "refuses unreadable dates")
    pth = os.path.join(tmp, "latin.csv")
    with open(pth, "wb") as fh:
        fh.write("application_id,booked_at,interview_at,outcome\nA,2026-05-01,2026-05-02,annulé\n".encode("latin-1"))
    ok(refused(pth, "utf-8"), "refuses non-UTF-8")
    pth = os.path.join(tmp, "empty.csv")
    open(pth, "w").close()
    ok(refused(pth, "empty"), "refuses an empty file")
    ok(refused(variant("cols.csv", lambda r, i: r.pop("outcome")), "missing"), "names missing columns")
    p = variant("dateonly.csv", lambda r, i: r.update(interview_at="2026-05-03",
                                                       outcome="no_show" if i % 4 == 0 else "attended"))
    aa = analyse(load(p))
    ok(not aa["input"]["appointment_times"] and not any(
        d["family"] == "hour" for d in aa["drivers"]), "date-only: no hour test")
    ok(any(c["what"] == "Time of day" for c in aa["cannot"]), "date-only: says so")

    # --- censoring: a recent miss is not 'never rebooked' ----------------------
    rows = []
    for i in range(60):
        rows.append(dict(base, application_id=f"R{i}", location_id="S1",
                         booked_at="2026-05-27 10:00", interview_at="2026-05-29 10:00",
                         outcome="no_show"))
    for i in range(60):
        rows.append(dict(base, application_id=f"Q{i}", location_id="S2",
                         booked_at="2026-04-01 10:00", interview_at="2026-04-03 10:00",
                         outcome="attended"))
    p = write_rows("recent.csv", rows)
    r = analyse(load(p, dt.date(2026, 5, 31)))["recovery"]
    ok(r is None or r["misses"] == 0, "recent misses not judged")

    # --- the pipeline export ------------------------------------------------
    pipe = None
    for cand in (os.path.join(SKILL, "data", "frontline_pipeline_sample.csv"),
                 os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(SKILL))),
                              "data", "frontline_pipeline_sample.csv")):
        if os.path.exists(cand):
            pipe = cand
            break
    if pipe:
        ap = analyse(load(pipe))
        ok(ap["input"]["kind"] == "pipeline" and ap["lag"] is None, "pipeline: no lag curve")
        ok(any("interview date" in c["why"] for c in ap["cannot"]), "pipeline: says why")
        nb = ap["never_booked"]
        ok(nb["no_slot"] == 1000 and nb["no_slot_sites"]["share"] == 1.0
           and nb["no_slot_sites"]["sites"] == ["LOC-03", "LOC-07", "LOC-14", "LOC-19",
                                                 "LOC-25", "LOC-31", "LOC-36", "LOC-40"],
           f"pipeline: never-booked at the 8 scarce sites {nb['no_slot_sites']}")
        sv = {d["key"] for d in ap["drivers"] if d["verdict"] == "survives"}
        ok(sv == {"busy_weeks"}, f"pipeline: only the peak survives ({sorted(sv)})")
        ok(abs(ap["count"]["miss_rate"] - 1714 / (1714 + 5214)) < 0.002, "pipeline: miss rate")
        ok("## 2." in md_report(ap), "pipeline report renders")
        pbp = build_playbook(ap, read_facts(SAMPLE_FACTS))
        ok(pbp["check"]["ready"] and any("LOC-03" in r["rule"] for r in pbp["rules"]),
           "pipeline playbook: slots where nobody got one")
        root = os.path.dirname(pipe)
        for other in ("qsr", "logistics"):
            f = os.path.join(root, f"{other}_pipeline_sample.csv")
            if os.path.exists(f):
                ao = analyse(load(f))
                ok({d["key"] for d in ao["drivers"] if d["verdict"] == "survives"} == {"busy_weeks"}
                   and len(ao["never_booked"]["no_slot_sites"]["sites"]) == 8,
                   f"{other} sample: same structure found")
        f = os.path.join(root, "gig_pipeline_sample.csv")
        if os.path.exists(f):
            ok(refused(f, "no interview stage"), "gig sample: refused, no interview stage")

    # --- the playbook and the check ---------------------------------------------
    facts = read_facts(SAMPLE_FACTS)
    pb = build_playbook(a, facts)
    ok(pb["check"]["ready"], f"generated sequence passes: {pb['check']['findings']}")
    ok(any("within" in r["rule"] and "day" in r["rule"] for r in pb["rules"]), "max-wait rule")
    ok(any("LOC-04" in r["rule"] for r in pb["rules"]), "calendar rule")
    ok(any("two slots" in r["rule"] for r in pb["rules"]), "two-slot rule")
    ok(any("11:00-13:59" in r["rule"] for r in pb["rules"]), "hour rule")
    ok(any("LOC-06" in r["rule"] for r in pb["rules"]), "rebook rule names the sites")
    ok("reminder_48h" in [t["id"] for t in pb["touches"]], "long waits get a 48-hour touch")
    pb0 = build_playbook(None, facts)
    ok(pb0["check"]["ready"] and not pb0["tuned"], "untuned playbook passes and says so")
    ok(all(sms_length(t["text"])[0] <= 306 for t in pb["touches"]), "two texts at most")
    good = load_messages(os.path.join(SAMPLE_DIR, "fernhill_messages.json"))
    ok(check_sequence(good)["ready"], "sample messages pass")
    nofacts = os.path.join(tmp, "nofacts.json")
    json.dump({"touches": good["touches"], "policy": good["policy"]}, open(nofacts, "w"))
    try:
        load_messages(nofacts)
        ok(False, "messages without facts refused")
    except Refused:
        ok(True, "messages without facts refused")
    broken = json.load(open(os.path.join(FIXTURES, "broken_sequences.json"), encoding="utf-8"))
    for case in broken:
        doc = json.loads(json.dumps(good))
        for op in case["ops"]:
            kind, args = next(iter(op.items()))
            path = args[0]
            tgt = doc
            for k in path[:-1]:
                tgt = tgt[k]
            if kind == "set":
                tgt[path[-1]] = args[1]
            elif kind == "append":
                tgt[path[-1]].append(args[1])
        res = check_sequence(doc)
        hit = any(case["expect"] in (f["rule"] + ": " + f["problem"]) for f in res["findings"])
        ok(not res["ready"] and hit, f"broken sequence blocked: {case['name']}")
    ok(sms_length("café")[1] is False, "é is GSM-7")
    ok(sms_length("it’s")[1] is True, "curly apostrophe is Unicode")
    ok(sms_length("{link}")[0] == 23, "a link counts 23")

    print(f"{passed[0]} passed, {len(failed)} failed")
    for f in failed:
        print("  FAIL", f)
    return 0 if not failed else 1


# ==================================================================== main ===

def main(argv=None):
    ap = argparse.ArgumentParser(description="Interview No-Show Playbook engine")
    ap.add_argument("--log", help="booking log or pipeline export (CSV)")
    ap.add_argument("--as-of", help="the export day, YYYY-MM-DD")
    ap.add_argument("--playbook", metavar="FACTS", help="facts JSON: write the playbook")
    ap.add_argument("--check", metavar="MESSAGES", help="check your own sequence (JSON)")
    ap.add_argument("--md", action="store_true", help="readable report (default)")
    ap.add_argument("--json", action="store_true", help="everything, as JSON")
    ap.add_argument("--demo", action="store_true", help="run on the planted sample")
    ap.add_argument("--test", action="store_true", help="run the test suite")
    ap.add_argument("--version", action="store_true")
    args = ap.parse_args(argv)
    if args.version:
        print(VERSION)
        return 0
    if args.test:
        return run_tests()
    try:
        as_of = None
        if args.as_of:
            try:
                as_of = dt.date.fromisoformat(args.as_of)
            except ValueError:
                raise Refused("--as-of must be YYYY-MM-DD")
        if args.demo:
            args.log, as_of, args.playbook = SAMPLE_LOG, dt.date(2026, 10, 31), SAMPLE_FACTS
        if args.check:
            res = check_sequence(load_messages(args.check))
            print(json.dumps(jsonable(res), indent=1) if args.json else md_check(res), end="")
            return 0 if res["ready"] else 1
        if not args.log and not args.playbook:
            ap.print_help()
            return 3
        analysis = analyse(load(args.log, as_of)) if args.log else None
        pb = build_playbook(analysis, read_facts(args.playbook)) if args.playbook else None
        if args.json:
            print(json.dumps(jsonable({"analysis": analysis, "playbook": pb}), indent=1))
        else:
            parts = []
            if analysis:
                parts.append(md_report(analysis))
            if pb:
                parts.append(md_playbook(pb))
            print("\n".join(parts), end="")
        return 0 if (pb is None or pb["check"]["ready"]) else 1
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:                       # the engine itself failed
        print(f"ENGINE ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(4)
