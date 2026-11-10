#!/usr/bin/env python3
"""
Onboarding Drop-off Diagnostic: the engine.

    python3 scripts/dropoff.py --hires hires.csv [--steps steps.csv] [--as-of 2026-10-31] [--md | --json]
    python3 scripts/dropoff.py --demo
    python3 scripts/dropoff.py --test

Reads one row per accepted offer (the hires file) and, best, one row per
onboarding step per hire (the steps file). Counts the loss between offer and
first shift honestly, reads the offer-to-first-shift gap first, finds which
step people are waiting on when they leave and whose side each wait is on,
tests every candidate cause inside strata, and writes the fixes the survivors
call for. Same files, same answer, every time.

Exit codes: 0 read, 3 input refused, 4 the engine itself failed.
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
SAMPLE_HIRES = os.path.join(SAMPLE_DIR, "bramblewood_hires.csv")
SAMPLE_STEPS = os.path.join(SAMPLE_DIR, "bramblewood_steps.csv")
EXPECTED = os.path.join(SAMPLE_DIR, "bramblewood_expected.json")
SAMPLE_AS_OF = "2026-10-31"

MAX_ROWS = 400_000
MIN_ARM = 30
MIN_DECIDED = 200
MIN_EFFECT = 0.03
ALPHA = 0.05
Z95 = 1.959964
LANDMARK_DAYS = 7
SILENCE_DAYS = 5
LONG_GAP = 10
GAP_BANDS = [("0-3 days", 0, 3), ("4-6 days", 4, 6), ("7-9 days", 7, 9),
             ("10-13 days", 10, 13), ("14+ days", 14, 10_000)]


class Refused(Exception):
    """The input cannot be read honestly. Exit 3 with the reason."""


# =============================================================== reading ====

ALIASES = {
    "hire_id": ["candidate_id", "applicant_id", "application_id", "worker_id",
                "new_hire_id", "employee_id", "id"],
    "offer_accepted_at": ["offer_accepted", "accepted_at", "offer_accepted_date",
                          "offer_at", "offer_date", "hired_at", "hire_date"],
    "first_shift_scheduled_at": ["first_shift_at", "scheduled_first_shift_at",
                                 "first_shift", "start_date", "scheduled_start",
                                 "start_at", "first_shift_date"],
    "outcome": ["status", "result", "onboarding_status", "final_status"],
    "withdrawn_at": ["withdrew_at", "dropped_at", "declined_at", "reneged_at",
                     "withdrawal_date"],
    "rescinded_at": ["revoked_at", "offer_rescinded_at"],
    "location_id": ["site_id", "store_id", "location", "site", "store"],
    "recruiter_id": ["recruiter", "coordinator_id", "hiring_manager_id",
                     "owner_id"],
    "commute_band_km": ["commute_band", "distance_band"],
    "step": ["step_name", "task", "task_name", "item", "onboarding_step"],
    "requested_at": ["sent_at", "started_at", "ordered_at", "assigned_at",
                     "created_at", "initiated_at"],
    "completed_at": ["done_at", "finished_at", "cleared_at", "returned_at",
                     "submitted_at"],
    "vendor": ["provider", "vendor_name", "screening_vendor"],
    "method": ["collection_method", "mode", "test_method"],
    "needs_hire": ["hire_action", "needs_candidate", "candidate_action"],
}
ALIAS_OF = {a: k for k, v in ALIASES.items() for a in v}

PII_EXACT = {"name", "address", "street", "street_address", "postcode",
             "post_code", "zip", "zip_code", "zipcode", "postal_code", "dob",
             "date_of_birth", "birth_date", "birthdate", "ssn",
             "social_security", "social_security_number", "national_insurance",
             "nin", "note", "notes", "comment", "comments", "free_text",
             "ip_address", "reason_text"}
NAME_OK = {"store_name", "site_name", "location_name", "role_name",
           "source_name", "job_name", "brand_name", "region_name",
           "position_name", "campaign_name", "company_name", "step_name",
           "task_name", "vendor_name"}
EMAIL_RE = re.compile(r"[^@\s,;]+@[^@\s,;]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"^\+?\d{0,3}[\s.\-]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}$"
                      r"|^\+\d[\d\s.\-()]{8,}\d$")
PERSON_RE = re.compile(r"^[A-Z][a-z]+(?:[-'][A-Za-z]+)? [A-Z][a-z]+(?:[-'][A-Za-z]+)?$")

OUTCOME_WORDS = {
    "started": ["started", "start", "hired", "active", "worked_first_shift",
                "first_shift_completed", "completed", "complete", "showed",
                "onboarded", "employed"],
    "withdrew": ["withdrew", "withdrawn", "candidate_withdrew", "declined",
                 "reneged", "ghosted", "dropped", "dropped_out", "quit",
                 "quit_before_start", "abandoned", "no_longer_interested",
                 "accepted_other_offer"],
    "no_show": ["no_show", "noshow", "ncns", "no_call_no_show",
                "first_shift_no_show", "did_not_start", "dns", "no_start",
                "missed_first_shift"],
    "rescinded": ["rescinded", "offer_rescinded", "revoked", "failed_check",
                  "failed_background", "failed_drug_test", "not_cleared",
                  "employer_withdrew", "employer_rescinded", "ineligible",
                  "not_eligible"],
    "pending": ["", "pending", "in_progress", "open", "onboarding",
                "in_onboarding", "scheduled", "waiting"],
}
OUTCOME_OF = {w: k for k, ws in OUTCOME_WORDS.items() for w in ws}

STEP_WORDS = {
    "background_check": ["background_check", "background", "bgc", "bg_check",
                         "background_screen", "background_screening",
                         "criminal_check", "bg"],
    "drug_test": ["drug_test", "drug_screen", "drug", "drug_screening",
                  "drug_testing"],
    "i9_section1": ["i9_section1", "i9", "i_9", "i9_s1", "i_9_section_1",
                    "i9_section_1", "form_i9"],
    "i9_section2": ["i9_section2", "i9_s2", "i_9_section_2", "i9_section_2",
                    "i9_documents", "work_authorization_documents"],
    "tax_forms": ["tax_forms", "w4", "w_4", "tax", "paperwork", "new_hire_forms",
                  "new_hire_paperwork", "forms"],
    "uniform": ["uniform", "uniform_order", "uniform_fit", "equipment"],
    "orientation": ["orientation", "induction", "day_one", "onboarding_session"],
    "food_handler_card": ["food_handler_card", "food_handler", "food_safety",
                          "food_handlers_card", "servsafe"],
}
STEP_OF = {w: k for k, ws in STEP_WORDS.items() for w in ws}
STEP_LABEL = {"background_check": "Background check", "drug_test": "Drug test",
              "i9_section1": "I-9 Section 1", "i9_section2": "I-9 documents",
              "tax_forms": "Tax and new-hire forms", "uniform": "Uniform",
              "orientation": "Orientation", "food_handler_card": "Food handler card"}
HIRE_ACTION_DEFAULT = {"drug_test", "i9_section1", "i9_section2", "tax_forms",
                       "food_handler_card", "orientation"}
DONE_WORDS = {"done", "complete", "completed", "cleared", "passed", "pass",
              "signed", "submitted", "received", "clear", "ok", "yes"}
FAIL_WORDS = {"failed", "fail", "not_cleared", "adverse", "positive",
              "consider", "rejected"}
LAB_WORDS = {"lab", "laboratory", "offsite", "off_site", "clinic",
             "collection_site", "external"}
YES = {"yes", "y", "1", "true", "t"}


def norm_header(h):
    h = re.sub(r"[\s\-]+", "_", h.strip().lower().lstrip(chr(0xFEFF)))
    return ALIAS_OF.get(h, h)


def norm_word(v):
    return re.sub(r"[\s\-/]+", "_", (v or "").strip().lower())


def pii_header(h):
    if h in NAME_OK:
        return False
    if h in PII_EXACT or h.endswith("name"):
        return True
    return any(w in h for w in ("email", "e_mail", "phone", "mobile",
                                "telephone", "cellphone", "birth"))


def read_table(path, what):
    """(headers, rows as dicts). Refuses what cannot be read honestly."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        raise Refused(f"cannot open the {what} file {path}: {e.strerror}")
    if not raw.strip():
        raise Refused(f"the {what} file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refused(f"the {what} file is not UTF-8. Re-export it as CSV UTF-8.")
    if "\x00" in text:
        raise Refused(f"the {what} file holds binary data, not a CSV")
    first = text.split("\n", 1)[0]
    delim = max([",", ";", "\t"], key=first.count)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delim)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise Refused(f"the {what} file has no header row")
    headers = [norm_header(h) for h in header]
    if len(set(headers)) != len(headers):
        dup = sorted({h for h in headers if headers.count(h) > 1})
        raise Refused(f"the {what} file repeats column names after reading "
                      f"aliases: {', '.join(dup)}")
    bad = [h for h in headers if pii_header(h)]
    if bad:
        raise Refused(f"the {what} file has columns that look personal ("
                      + ", ".join(bad) + "). Re-export with opaque ids only: "
                      "no names, emails, phone numbers, addresses or notes.")
    rows = []
    try:
        for rec in reader:
            if not any(c.strip() for c in rec):
                continue
            if len(rows) >= MAX_ROWS:
                raise Refused(f"the {what} file has more than {MAX_ROWS:,} rows. "
                              "Export one region or one half-year at a time.")
            rec = rec + [""] * (len(headers) - len(rec))
            rows.append({h: rec[i].strip() for i, h in enumerate(headers)})
    except csv.Error as e:
        raise Refused(f"the {what} file is a malformed CSV: {e}")
    if not rows:
        raise Refused(f"the {what} file has a header and no rows")
    for h in ("hire_id", "recruiter_id"):
        if h in headers:
            vals = [r[h] for r in rows[:20_000] if r.get(h)]
            if vals and sum(1 for v in vals if PERSON_RE.match(v)) / len(vals) > 0.05:
                raise Refused(f"'{h}' in the {what} file holds what look like "
                              "people's names. Use opaque ids that do not resolve "
                              "to a person outside your systems.")
    for r in rows:
        for h, v in r.items():
            if not v or h.endswith("_at"):
                continue
            if "@" in v and EMAIL_RE.search(v):
                raise Refused(f"column '{h}' in the {what} file holds an email "
                              "address. Re-export with opaque ids only.")
            if PHONE_RE.match(v):
                raise Refused(f"column '{h}' in the {what} file holds a phone "
                              "number. Re-export with opaque ids only.")
    return headers, rows


ISO_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})"
                    r"(?::(\d{2})(?:\.\d+)?)?\s*([AaPp][Mm])?\s*"
                    r"(?:Z|[+-]\d{2}:?\d{2})?)?$")
SLASH_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})(?:[ T](\d{1,2}):(\d{2})"
                      r"(?::(\d{2}))?\s*([AaPp][Mm])?)?$")


def slash_order(values):
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
    v = v.strip()
    m = ISO_RE.match(v)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mm, ss, ap = m.group(4), m.group(5), m.group(6), m.group(7)
    else:
        m = SLASH_RE.match(v)
        if not m:
            return None
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        mo, d = (a, b) if order == "mdy" else (b, a)
        hh, mm, ss, ap = m.group(4), m.group(5), m.group(6), m.group(7)
    try:
        if hh is None:
            return dt.datetime(y, mo, d)
        h = int(hh)
        if ap:
            if not 1 <= h <= 12:
                return None
            h = h % 12 + (12 if ap.lower() == "pm" else 0)
        return dt.datetime(y, mo, d, h, int(mm), int(ss or 0))
    except ValueError:
        return None


def parse_dates(rows, cols, what, required=()):
    """Parses date columns in place. Refuses a column where more than 1% of
    the filled cells cannot be read."""
    vals = [r[c] for r in rows for c in cols if r.get(c)]
    order = slash_order(vals)
    for col in cols:
        filled = bad = 0
        for r in rows:
            v = r.get(col, "")
            if not v:
                r[col] = None
                continue
            filled += 1
            when = parse_when(v, order)
            if when is None or not (2000 <= when.year <= 2100):
                bad += 1
                r[col] = None
                continue
            r[col] = when
        if filled and bad / filled > 0.01:
            raise Refused(f"{bad:,} of {filled:,} values in '{col}' in the {what} "
                          "file are not dates I can read. Use YYYY-MM-DD or "
                          "YYYY-MM-DD HH:MM.")
        if col in required and filled == 0:
            raise Refused(f"'{col}' in the {what} file is empty")


def load(hires_path, steps_path=None, as_of=None):
    headers, rows = read_table(hires_path, "hires")
    need = ["hire_id", "offer_accepted_at", "first_shift_scheduled_at", "outcome"]
    missing = [c for c in need if c not in headers]
    if missing:
        hint = ""
        if "outcome" in missing and "stage_reached" in headers:
            hint = (" This looks like a pipeline export (one row per application). "
                    "For the whole funnel use funnel-drop-off-analyst; this skill "
                    "needs one row per accepted offer with its outcome.")
        raise Refused("the hires file is missing required columns: "
                      + ", ".join(missing) + "." + hint)
    date_cols = [c for c in ("offer_accepted_at", "first_shift_scheduled_at",
                             "withdrawn_at", "rescinded_at") if c in headers]
    parse_dates(rows, date_cols, "hires", required=("offer_accepted_at",))
    seen = set()
    unknown = collections.Counter()
    for r in rows:
        if not r["hire_id"]:
            raise Refused("a row in the hires file has no hire_id")
        if r["hire_id"] in seen:
            raise Refused(f"hire_id {r['hire_id']} appears twice in the hires file. "
                          "One row per accepted offer: a rehire gets a new id.")
        seen.add(r["hire_id"])
        w = norm_word(r["outcome"])
        if w not in OUTCOME_OF:
            unknown[r["outcome"]] += 1
        r["outcome"] = OUTCOME_OF.get(w)
    if sum(unknown.values()) > 0.01 * len(rows):
        top = ", ".join(f"'{k}'" for k, _ in unknown.most_common(5))
        raise Refused(f"{sum(unknown.values()):,} outcomes I cannot read ({top}). "
                      "Map them to started, withdrew, no_show, rescinded or "
                      "pending (blank).")
    steps = None
    sheaders = []
    if steps_path:
        sheaders, steps = read_table(steps_path, "steps")
        if "outcome" in sheaders and "result" not in sheaders:
            # status / result on a step row is the step's result, not the hire's
            sheaders = ["result" if x == "outcome" else x for x in sheaders]
            for s in steps:
                s["result"] = s.pop("outcome")
        smiss = [c for c in ("hire_id", "step", "requested_at") if c not in sheaders]
        if smiss:
            raise Refused("the steps file is missing required columns: "
                          + ", ".join(smiss) + ".")
        parse_dates(steps, [c for c in ("requested_at", "completed_at")
                            if c in sheaders], "steps", required=("requested_at",))
        orphans = sum(1 for s in steps if s["hire_id"] not in seen)
        if orphans > 0.05 * len(steps):
            raise Refused(f"{orphans:,} of {len(steps):,} step rows belong to no "
                          "hire in the hires file. Export both files for the "
                          "same hires and period.")
        steps = [s for s in steps if s["hire_id"] in seen]
        for s in steps:
            w = norm_word(s["step"])
            s["step"] = STEP_OF.get(w, w or "unnamed")
            s["result"] = norm_word(s.get("result", ""))
            s["vendor"] = s.get("vendor", "") or None
            m = norm_word(s.get("method", ""))
            s["method"] = m or None
            nh = norm_word(s.get("needs_hire", ""))
            s["needs_hire"] = (nh in YES) if nh else (s["step"] in HIRE_ACTION_DEFAULT)
    if as_of:
        cutoff = parse_when(as_of)
        if cutoff is None:
            raise Refused("--as-of must be a date, YYYY-MM-DD")
        if cutoff.hour == 0 and cutoff.minute == 0 and len(as_of.strip()) <= 10:
            cutoff = cutoff.replace(hour=23, minute=59)
        as_of_source = "given"
    else:
        stamps = [r[c] for r in rows for c in ("offer_accepted_at", "withdrawn_at",
                                                 "rescinded_at") if r.get(c)]
        if steps:
            stamps += [s[c] for s in steps for c in ("requested_at", "completed_at")
                       if s.get(c)]
        cutoff = max(stamps).replace(hour=23, minute=59)
        as_of_source = "the latest date in the files"
    return build(rows, headers, steps, sheaders, cutoff, as_of_source)


# ============================================================== building ====

def build(rows, headers, steps, sheaders, as_of, as_of_source):
    by_hire = collections.defaultdict(list)
    for s in steps or []:
        by_hire[s["hire_id"]].append(s)
    bad_order = 0
    no_first = 0
    hires = []
    for r in rows:
        offer, first = r["offer_accepted_at"], r.get("first_shift_scheduled_at")
        if offer is None:
            continue
        if first is None:
            no_first += 1
        elif first.date() < offer.date():
            bad_order += 1
            first = None
        h = {"id": r["hire_id"], "offer": offer, "first": first,
             "gap": (first.date() - offer.date()).days if first else None,
             "outcome": r["outcome"], "withdrawn": r.get("withdrawn_at"),
             "rescinded": r.get("rescinded_at"),
             "site": r.get("location_id") or None, "role": r.get("role") or None,
             "source": r.get("source") or None, "rec": r.get("recruiter_id") or None,
             "region": r.get("region") or None,
             "commute": r.get("commute_band_km") or None,
             "steps": sorted(by_hire.get(r["hire_id"], []),
                             key=lambda s: s["requested_at"] or dt.datetime.max)}
        hires.append(h)
    checked = sum(1 for r in rows if r["offer_accepted_at"] and r.get("first_shift_scheduled_at"))
    if checked and bad_order > 0.01 * checked:
        raise Refused(f"{bad_order:,} hires have a first shift before their offer "
                      "was accepted. Check that the two date columns are not swapped.")
    data = {"hires": hires, "as_of": as_of, "as_of_source": as_of_source,
            "has_steps": bool(steps), "headers": headers, "step_headers": sheaders,
            "no_first": no_first, "bad_order": bad_order}
    classify(data)
    return data


def classify(data):
    """Decided hires are the denominator: started, withdrew or no-show, with a
    first shift already due. Everything else is counted and set aside."""
    as_of = data["as_of"]
    decided, pending, future_withdrew, rescinded, no_date = [], [], [], [], []
    for h in data["hires"]:
        o = h["outcome"]
        if o == "rescinded":
            rescinded.append(h)
            continue
        if h["first"] is None:
            (no_date if o in ("started", "withdrew", "no_show") else pending).append(h)
            continue
        if h["first"] > as_of:
            (future_withdrew if o == "withdrew" else pending).append(h)
            continue
        if o in ("started", "withdrew", "no_show"):
            h["lost"] = o != "started"
            decided.append(h)
        else:
            pending.append(h)
    # Hires who withdrew before a first shift was ever scheduled have no gap,
    # but they are losses. They count in the loss once their offer is old
    # enough that everyone accepted with them would have been decided by now
    # (the 90th percentile gap); before that, counting them would count the
    # recent losses and not the recent starts.
    gaps = sorted(h["gap"] for h in decided)
    horizon = gaps[int(.9 * (len(gaps) - 1))] if gaps else 14
    early = [h for h in no_date if h["outcome"] == "withdrew"
             and h["offer"] + dt.timedelta(days=horizon) <= as_of]
    long_gap = LONG_GAP
    if gaps and (sum(g >= LONG_GAP for g in gaps) < MIN_ARM
                 or sum(g < LONG_GAP for g in gaps) < MIN_ARM):
        long_gap = max(1, int(median(gaps)) + 1)
    data.update(decided=decided, pending=pending, future_withdrew=future_withdrew,
                rescinded=rescinded, no_date=no_date, early_undated=early,
                horizon=horizon, long_gap=long_gap)
    for h in decided:
        h["month"] = h["offer"].strftime("%Y-%m")
        h["gap_s"] = min(max(h["gap"], 1), 18)
        h["bg_vendor"] = next((s["vendor"] for s in h["steps"]
                               if s["step"] == "background_check" and s["vendor"]), None)
        dts = [s for s in h["steps"] if s["step"] == "drug_test" and s["method"]]
        h["lab"] = (dts[0]["method"] in LAB_WORDS) if dts else None
        h["silence"] = silence(h) if data["has_steps"] else None


def end_of_wait(h):
    """When the hire stopped waiting: withdrawal, first shift, whichever first."""
    ends = [x for x in (h.get("withdrawn"), h.get("first")) if x]
    return min(ends) if ends else None


def silence(h):
    """Longest stretch with no logged event in the first LANDMARK_DAYS after
    the offer, for hires still waiting at the end of that week; None for
    everyone else. A landmark: measuring silence over the whole wait would
    read short silences for the people who left early, because their log
    stops when they do."""
    if not h["steps"] or h["gap"] is None or h["gap"] <= LANDMARK_DAYS:
        return None
    mark = h["offer"] + dt.timedelta(days=LANDMARK_DAYS)
    if h["withdrawn"] and h["withdrawn"] < mark:
        return None
    ts = [h["offer"], mark]
    for s in h["steps"]:
        for c in ("requested_at", "completed_at"):
            t = s.get(c)
            if t and h["offer"] <= t <= mark:
                ts.append(t)
    ts.sort()
    return max((b - a).total_seconds() / 86400 for a, b in zip(ts, ts[1:]))


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
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    out = set()
    for rank, i in enumerate(order):
        if pvals[i] <= alpha / (m - rank):
            out.add(i)
        else:
            break
    return out


def median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def quantile(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def days(a, b):
    return (b - a).total_seconds() / 86400


def pct(x, digits=0):
    return f"{100 * x:.{digits}f}%"


def pts(x):
    return f"{100 * x:+.1f} pts"


def points(x):
    return f"{abs(100 * x):.1f} points"


def cap(text):
    return text[:1].upper() + text[1:] if text else text


def gap_band(g):
    for name, lo, hi in GAP_BANDS:
        if lo <= g <= hi:
            return name
    return GAP_BANDS[-1][0]


# ============================================================== analysis ====

def count_section(data):
    d = data["decided"]
    lost = [h for h in d if h["lost"]]
    early = len(data["early_undated"])
    out = {
        "accepted": len(data["hires"]),
        "early_undated": early,
        "loss_all": (len(lost) + early) / (len(d) + early) if d or early else None,
        "decided": len(d),
        "started": sum(1 for h in d if h["outcome"] == "started"),
        "withdrew": sum(1 for h in d if h["outcome"] == "withdrew"),
        "no_show": sum(1 for h in d if h["outcome"] == "no_show"),
        "lost": len(lost),
        "loss_rate": len(lost) / len(d) if d else None,
        "loss_range": wilson(len(lost), len(d)) if d else None,
        "rescinded": len(data["rescinded"]),
        "pending": len(data["pending"]),
        "future_withdrew": len(data["future_withdrew"]),
        "no_date": len(data["no_date"]) - early,
        "as_of": data["as_of"].strftime("%Y-%m-%d"),
        "as_of_source": data["as_of_source"],
    }
    w_time = [h for h in d if h["outcome"] == "withdrew" and h["withdrawn"]]
    out["withdrawn_dated"] = len(w_time)
    out["median_days_to_withdraw"] = median([days(h["offer"], h["withdrawn"]) for h in w_time])
    return out


def gap_section(data):
    rows = []
    for name, lo, hi in GAP_BANDS:
        g = [h for h in data["decided"] if lo <= h["gap"] <= hi]
        if not g:
            continue
        lost = sum(h["lost"] for h in g)
        rows.append({"band": name, "n": len(g), "lost": lost, "rate": lost / len(g),
                     "withdrew": sum(h["outcome"] == "withdrew" for h in g) / len(g),
                     "no_show": sum(h["outcome"] == "no_show" for h in g) / len(g)})
    gaps = [h["gap"] for h in data["decided"]]
    return {"bands": rows, "median_gap": median(gaps),
            "share_long": (sum(1 for x in gaps if x >= data["long_gap"]) / len(gaps)) if gaps else None,
            "long": data["long_gap"]}


def step_section(data):
    """Whose side each wait is on: your queue (offer to request) and the
    turnaround (request to done), per step, per vendor and per method."""
    per = collections.defaultdict(lambda: {"queue": [], "turn": [], "n": 0,
                                           "hire": 0, "failed": 0})
    vend = collections.defaultdict(list)
    meth = collections.defaultdict(list)
    for h in data["decided"] + data["rescinded"]:
        for s in h["steps"]:
            if not s["requested_at"]:
                continue
            p = per[s["step"]]
            p["n"] += 1
            p["hire"] += s["needs_hire"]
            p["queue"].append(days(h["offer"], s["requested_at"]))
            if s["result"] in FAIL_WORDS:
                p["failed"] += 1
            if s.get("completed_at") and s["completed_at"] >= s["requested_at"]:
                t = days(s["requested_at"], s["completed_at"])
                p["turn"].append(t)
                if s["vendor"]:
                    vend[(s["step"], s["vendor"])].append(t)
                if s["method"]:
                    meth[(s["step"], "lab" if s["method"] in LAB_WORDS else s["method"])].append(t)
    steps = []
    for k, p in per.items():
        steps.append({"step": k, "label": STEP_LABEL.get(k, k.replace("_", " ").capitalize()),
                      "n": p["n"], "needs_hire": p["hire"] > p["n"] / 2,
                      "queue_median": median(p["queue"]), "turn_median": median(p["turn"]),
                      "turn_p90": quantile(p["turn"], .9), "failed": p["failed"]})
    steps.sort(key=lambda s: -(s["turn_median"] or 0))
    vendors = []
    by_step = collections.defaultdict(list)
    for (step, v), ts in vend.items():
        if len(ts) >= MIN_ARM:
            by_step[step].append((v, len(ts), median(ts), quantile(ts, .9)))
    for step, vs in by_step.items():
        fastest = min(m for _, _, m, _ in vs)
        for v, n, m, p90 in sorted(vs):
            vendors.append({"step": step, "vendor": v, "n": n, "median": m, "p90": p90,
                            "slow": len(vs) > 1 and m >= 1.5 * fastest and m - fastest >= 1,
                            "ratio": m / fastest if fastest else None})
    methods = [{"step": st, "method": m, "n": len(ts), "median": median(ts)}
               for (st, m), ts in sorted(meth.items()) if len(ts) >= MIN_ARM]
    return {"steps": steps, "vendors": vendors, "methods": methods}


def after_check_section(data):
    """Hire-action steps requested only after the background check came back.
    That is the usual source of a silent first week."""
    per_site = collections.defaultdict(lambda: [0, 0])
    total = [0, 0]
    for h in data["decided"]:
        bg = next((s for s in h["steps"] if s["step"] == "background_check"
                   and s.get("completed_at")), None)
        paper = [s for s in h["steps"] if s["step"] in ("i9_section1", "tax_forms")
                 and s["requested_at"]]
        if not bg or not paper:
            continue
        after = min(s["requested_at"] for s in paper) >= bg["completed_at"]
        total[0] += after
        total[1] += 1
        if h["site"]:
            per_site[h["site"]][0] += after
            per_site[h["site"]][1] += 1
    if not total[1]:
        return None
    sites = sorted(((s, a / n, n) for s, (a, n) in per_site.items() if n >= MIN_ARM),
                   key=lambda x: (-x[1], x[0]))
    return {"share": total[0] / total[1], "n": total[1], "sites": sites[:6]}


def leave_section(data):
    """Which step a hire was waiting on when they withdrew, and the rate of
    withdrawal per 100 hire-days spent waiting on each step. Steps open at
    the same time share the days, so a step is a lead, not a verdict."""
    open_at = collections.Counter()
    exposure = collections.Counter()
    events = collections.Counter()
    n_with = 0
    for h in data["decided"]:
        end = end_of_wait(h)
        if end is None or not h["steps"]:
            continue
        w = h["withdrawn"] if h["outcome"] == "withdrew" else None
        if w:
            n_with += 1
        for s in h["steps"]:
            if not s["requested_at"] or s["requested_at"] >= end:
                continue
            done = s.get("completed_at") or end
            stop = min(done, end)
            if stop <= s["requested_at"]:
                continue
            exposure[s["step"]] += days(s["requested_at"], stop)
            if w and s["requested_at"] <= w and (not s.get("completed_at") or s["completed_at"] > w):
                open_at[s["step"]] += 1
                events[s["step"]] += 1
    rows = []
    for step, e in exposure.items():
        if e < 50:
            continue
        rows.append({"step": step, "label": STEP_LABEL.get(step, step),
                     "open_at_withdrawal": open_at[step],
                     "share": open_at[step] / n_with if n_with else None,
                     "per_100_days": 100 * events[step] / e, "hire_days": e})
    rows.sort(key=lambda r: -r["open_at_withdrawal"])
    nothing_open = 0
    for h in data["decided"]:
        if h["outcome"] == "withdrew" and h["withdrawn"] and h["steps"]:
            if not any(s["requested_at"] and s["requested_at"] <= h["withdrawn"]
                       and (not s.get("completed_at") or s["completed_at"] > h["withdrawn"])
                       for s in h["steps"]):
                nothing_open += 1
    return {"withdrawals_dated": n_with, "steps": rows, "nothing_open": nothing_open}


def rescind_section(data):
    res = data["rescinded"]
    allh = data["decided"] + res
    per_site = collections.defaultdict(lambda: [0, 0])
    for h in allh:
        if h["site"]:
            per_site[h["site"]][0] += h["outcome"] == "rescinded"
            per_site[h["site"]][1] += 1
    tot = len(res) / len(allh) if allh else 0
    flagged = []
    for s, (k, n) in per_site.items():
        if n >= MIN_ARM and k:
            lo, hi = wilson(k, n)
            if lo > tot:
                flagged.append({"site": s, "rate": k / n, "n": n})
    flagged.sort(key=lambda x: -x["rate"])
    by_step = collections.Counter()
    for h in res:
        failed = [s["step"] for s in h["steps"] if s["result"] in FAIL_WORDS]
        by_step[failed[0] if failed else "not logged"] += 1
    return {"n": len(res), "rate": tot, "sites": flagged, "by_step": dict(by_step)}


# ---------------------------------------------------------------- drivers ---

def make_drivers(data):
    recs = data["decided"]
    n = len(recs)
    has = {f: n and sum(1 for r in recs if r.get(f) is not None) >= 0.9 * n
           for f in ("site", "role", "source", "rec", "commute", "bg_vendor", "lab")}
    has["silence"] = sum(1 for r in recs if r.get("silence") is not None) >= 2 * MIN_ARM
    strat = {"site": lambda r: r["site"], "role": lambda r: r["role"],
             "gap": lambda r: r["gap_s"], "month": lambda r: r["month"],
             # how the hire was processed: the gap, lab or not, silent first
             # week or not, all at once. Held one at a time, a site with long
             # gaps and lab tests keeps whichever of the two is not held.
             # A site or a recruiter that only looks worse because of how it
             # runs onboarding is named for that, not for itself.
             "practice": lambda r: (r["gap_s"], r["lab"], None if r["silence"] is None
                                    else r["silence"] >= SILENCE_DAYS)}
    has["practice"] = data["has_steps"] and (has["lab"] or has["silence"])

    def checks(*names):
        return [x for x in names if x in ("gap", "month") or has.get(x)]


    D = []
    lg = data["long_gap"]
    D.append(("gap_long", f"A gap of {lg} days or more from offer to first shift",
              lambda r: r["gap"] >= lg, checks("site", "role", "month"), None))
    if has["silence"]:
        D.append(("silence_5plus", f"{SILENCE_DAYS} days or more with no contact in the first week",
                  lambda r: (r["silence"] >= SILENCE_DAYS) if r["silence"] is not None else None,
                  checks("gap", "site"), None))
    if has["lab"] or sum(1 for r in recs if r.get("lab") is not None) >= 0.5 * n:
        D.append(("drug_lab", "Drug test at an outside lab (against on site)",
                  lambda r: r["lab"], checks("gap", "site"), None))
    if has["commute"]:
        D.append(("far_commute", "Commute band over 20 km",
                  lambda r: (r["commute"] in ("21-40", "40+", ">40", "40_plus"))
                  if r["commute"] else None, checks("gap", "site"), None))
    fam = [("site", "site", "Site", ("gap", "month", "practice")),
           ("bg_vendor", "vendor", "Background check vendor", ("gap", "month")),
           ("role", "role", "Role", ("gap", "site")),
           ("source", "source", "Source", ("gap", "site")),
           ("rec", "recruiter", "Recruiter", ("gap", "site", "practice"))]
    for field, key, label, chk in fam:
        if not has.get(field):
            continue
        vals = collections.Counter(r[field] for r in recs if r[field])
        if len(vals) < 2 or len(vals) > 400:
            continue
        for v, k in sorted(vals.items(), key=lambda kv: str(kv[0])):
            if k < MIN_ARM:
                continue
            D.append((f"{key}:{v}", f"{label}: {v}",
                      (lambda field, v: lambda r: r[field] == v if r[field] else None)(field, v),
                      checks(*chk), key))
    return D, strat


def run_drivers(data, outcome_key="lost"):
    recs = data["decided"]
    drivers, strat = make_drivers(data)
    tested = []
    for key, label, fn, chks, family in drivers:
        a1 = n1 = a0 = n0 = 0
        for r in recs:
            e = fn(r)
            if e is None:
                continue
            m = r[outcome_key]
            if e:
                a1 += m; n1 += 1
            else:
                a0 += m; n0 += 1
        rec = {"key": key, "label": label, "family": family, "n_exposed": n1,
               "n_rest": n0, "rate_exposed": a1 / n1 if n1 else None,
               "rate_rest": a0 / n0 if n0 else None, "checks": []}
        if n1 < MIN_ARM or n0 < MIN_ARM:
            rec.update(verdict="thin", raw=None, p=None)
        else:
            d, se = rd_raw(a1, n1, a0, n0)
            rec.update(raw=d, p=p_two_sided(d / se) if se > 0 else 1.0)
        tested.append((rec, fn, chks))
    idx = [i for i, (rec, _, _) in enumerate(tested) if rec.get("p") is not None]
    flagged = {idx[j] for j in holm([tested[i][0]["p"] for i in idx])}
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
            rec["verdict"] = "fewer losses"
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
                m = r[outcome_key]
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
                chk.update(adjusted=adj, p=p, result="survives" if ok else "explained")
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
            rec["recoverable"] = (rec["adjusted"] * rec["n_exposed"] if rec["adjusted"] > 0
                                  else -rec["adjusted"] * rec["n_rest"])
        results.append(rec)
    results.sort(key=lambda r: (-(r.get("recoverable") or 0), r["key"]))
    return results


def site_split(data, site):
    g = [h for h in data["decided"] if h["site"] == site]
    rest = [h for h in data["decided"] if h["site"] != site]
    f = lambda xs, o: sum(h["outcome"] == o for h in xs) / len(xs) if xs else 0
    return {"no_show": f(g, "no_show"), "no_show_rest": f(rest, "no_show"),
            "withdrew": f(g, "withdrew"), "withdrew_rest": f(rest, "withdrew")}


EXPLAIN_WORD = {"gap": "the gap", "site": "the site", "role": "the role",
                "month": "the month",
                "practice": "how its hires were processed (gap, lab tests, silent weeks)"}


def cannot_section(data):
    out = []
    h, s = set(data["headers"]), set(data["step_headers"])
    if not data["has_steps"]:
        out.append(("which step people leave on, whose side each wait is on, "
                    "the silent first week and vendor turnaround",
                    "a steps file: hire_id, step, requested_at, completed_at"))
    else:
        if "completed_at" not in s:
            out.append(("turnaround per step and vendor", "completed_at in the steps file"))
        if "vendor" not in s:
            out.append(("whether one background check vendor is slower", "vendor"))
        if "method" not in s:
            out.append(("lab against on-site drug tests", "method on the drug test step"))
    if "withdrawn_at" not in h:
        out.append(("when people leave, and what they were waiting on",
                    "withdrawn_at"))
    for col, what in (("location_id", "site effects, and the check by site"),
                      ("role", "role effects, and the check by role"),
                      ("source", "source effects"), ("recruiter_id", "recruiter effects")):
        if col not in h:
            out.append((what, col))
    if data["no_first"]:
        out.append((f"the gap for {data['no_first']:,} hires with no first shift date",
                    "first_shift_scheduled_at on every row"))
    out.append(("why anyone left in their own words: a reason field is mostly what people "
                "say on the way out", None))
    return out


def analyse(data):
    c = count_section(data)
    a = {"version": VERSION, "count": c, "gap": gap_section(data)}
    if data["has_steps"]:
        a["steps"] = step_section(data)
        a["after_check"] = after_check_section(data)
        a["leave"] = leave_section(data)
    a["rescinded"] = rescind_section(data)
    if c["decided"] >= MIN_DECIDED:
        a["drivers"] = run_drivers(data)
        for d in a["drivers"]:
            if d["verdict"] == "survives" and d["family"] == "site":
                d["split"] = site_split(data, d["key"].split(":", 1)[1])
    else:
        a["drivers"] = None
        a["drivers_note"] = (f"{c['decided']} decided hires: too few to test causes "
                             f"(I need {MIN_DECIDED}). Counts and timings only.")
    a["cannot"] = cannot_section(data)
    a["plan"] = plan(a)
    return a


# ------------------------------------------------------------------- plan ---

def find(a, key):
    for d in a.get("drivers") or []:
        if d["key"] == key:
            return d
    return None


def plan(a):
    """Fixes from what survived, never from what was explained away."""
    out = []
    surv = [d for d in a.get("drivers") or [] if d["verdict"] == "survives" and d["adjusted"] > 0]
    keys = {d["key"] for d in surv}
    g = find(a, "gap_long")
    lg = a["gap"]["long"]
    if "gap_long" in keys:
        slow = [v for v in a.get("steps", {}).get("vendors", []) if v["slow"]]
        why = ""
        if slow:
            v = slow[0]
            fast = min(x["median"] for x in a["steps"]["vendors"] if x["step"] == v["step"])
            why = (f" The longest wait you control is {v['vendor']}: a median "
                   f"{v['median']:.1f} days to return a {STEP_LABEL.get(v['step'], v['step']).lower()}, "
                   f"against {fast:.1f}. Put a turnaround in the contract, or move "
                   "those sites to the faster vendor.")
        out.append({"rule": f"Schedule the first shift within {max(lg - 1, 1)} days of the offer.",
                    "because": f"Hires waiting {lg} days or more were lost "
                               f"{points(g['adjusted'])} more often at the same site, role and month "
                               f"(about {g['recoverable']:.0f} hires)." + why})
        chained = [s for s in a.get("steps", {}).get("steps", [])
                   if s["step"] == "food_handler_card" and s["turn_median"] is not None]
        if chained:
            out.append({"rule": "Start any certificate the role needs at the offer, not after "
                                "the background check, unless a rule requires the order.",
                        "because": "A certificate started after the check adds its whole "
                                   f"turnaround (median {chained[0]['turn_median']:.1f} days for the "
                                   "food handler card) to the gap."})
    if "silence_5plus" in keys:
        s = find(a, "silence_5plus")
        ac = a.get("after_check")
        more = ""
        if ac:
            more = (f" {pct(ac['share'])} of hires got their forms only after the check came back"
                    + (f"; most at {', '.join(x[0] for x in ac['sites'][:3])}." if ac["sites"] else "."))
        out.append({"rule": "Never leave a hire 3 days without hearing from you. Send the forms and "
                            "order the uniform at the offer, not after the check.",
                    "because": f"A first week with {SILENCE_DAYS} silent days cost {points(s['adjusted'])} "
                               f"at the same gap and site (about {s['recoverable']:.0f} hires)." + more})
    if "drug_lab" in keys:
        s = find(a, "drug_lab")
        out.append({"rule": "Use a rapid test on site where your policy and state allow it; where a "
                            "lab is required, book the visit for the hire and send the address.",
                    "because": f"Lab tests lost {points(s['adjusted'])} more at the same gap and site "
                               f"(about {s['recoverable']:.0f} hires). It is a trip the hire makes "
                               "on their own time."})
    for d in surv:
        if d["family"] == "site":
            site = d["key"].split(":", 1)[1]
            sp = d.get("split", {})
            if sp and sp["no_show"] - sp["no_show_rest"] > sp["withdrew"] - sp["withdrew_rest"]:
                rule = (f"{site}: check what new hires are told about the first shift: where, "
                        "when, which door, who meets them.")
                because = (f"{points(d['adjusted'])} more lost at the same gap and month, almost all of it on "
                           f"the day: {pct(sp['no_show'])} first-shift no-shows against "
                           f"{pct(sp['no_show_rest'])} elsewhere.")
            else:
                rule = f"{site}: sit in on its onboarding for a week."
                because = f"{points(d['adjusted'])} more lost at the same gap and month."
            out.append({"rule": rule, "because": because})
        elif d["family"] in ("role", "source", "recruiter", "vendor"):
            out.append({"rule": f"{d['label']}: look at what differs before changing anything.",
                        "because": f"{points(d['adjusted'])} more lost after every check."})
    if not out:
        out.append({"rule": "No fix is called for by these files.",
                    "because": "Nothing cleared the bar once the gap and the site were held equal. "
                               "The counts and timings above still show where the days go."})
    return out


# ================================================================ report ====

def md_report(a):
    c = a["count"]
    L = []
    w = L.append
    w("# Onboarding drop-off: offer to first shift")
    w("")
    w(f"Read as of {c['as_of']} ({c['as_of_source']}). Engine {a['version']}.")
    w("")
    w("## 1. The loss, counted honestly")
    w("")
    if c["decided"]:
        lo, hi = c["loss_range"]
        w(f"Of **{c['decided']:,}** hires whose first shift is already due, **{c['lost']:,} "
          f"({pct(c['loss_rate'])}) never worked it**: {c['withdrew']:,} withdrew before the "
          f"day and {c['no_show']:,} did not turn up on it (95% range {pct(lo)} to {pct(hi)}).")
    else:
        w("No hire in these files has a first shift that is already due, so there is no loss to count yet.")
    w("")
    w("Set aside, and why:")
    w("")
    w(f"- **{c['rescinded']:,} rescinded.** You withdrew the offer, mostly on a failed check. "
      "That is a decision, not a drop-off, and it is reported in section 6.")
    w(f"- **{c['pending']:,} still in onboarding**, first shift not yet due.")
    if c["future_withdrew"]:
        w(f"- **{c['future_withdrew']:,} already marked withdrew whose first shift is not yet due.** "
          "Counting them would count the recent losses and none of the recent starts, which "
          "inflates the rate for the latest weeks.")
    if c["no_date"]:
        w(f"- **{c['no_date']:,} with no first shift date**, so no gap.")
    if c["early_undated"]:
        w("")
        w(f"**{c['early_undated']:,} more withdrew before a first shift was ever scheduled.** They are "
          f"losses too: counting them, {pct(c['loss_all'])} of accepted offers never reached a first "
          "shift. They have no gap, so the causes below are read without them, and the earliest "
          "leavers are the ones most often missing from a read like this.")
    if c.get("median_days_to_withdraw") is not None:
        w("")
        w(f"Half of those who withdrew did so within {c['median_days_to_withdraw']:.1f} days of accepting.")
    w("")
    w("## 2. The gap first")
    w("")
    w("The gap is measured from the offer to the **scheduled** first shift, which is known "
      "before anyone leaves. A gap measured to the day people actually started describes only "
      "the people who stayed.")
    w("")
    w("| Offer to first shift | Hires | Lost | Withdrew | No-show on the day |")
    w("|---|---:|---:|---:|---:|")
    for b in a["gap"]["bands"]:
        w(f"| {b['band']} | {b['n']:,} | {pct(b['rate'])} | {pct(b['withdrew'])} | {pct(b['no_show'])} |")
    if a["gap"]["median_gap"] is not None:
        w("")
        w(f"Median gap {a['gap']['median_gap']:.0f} days; {pct(a['gap']['share_long'])} of hires waited "
          f"{a['gap']['long']} days or more.")
    w("")
    if "steps" in a:
        st = a["steps"]
        w("## 3. Where the days go, and whose side they are on")
        w("")
        w("*Your queue* is offer to request: time on your side before the step even starts. "
          "*Turnaround* is request to done: the vendor's or the hire's side.")
        w("")
        w("| Step | Hires | Your queue (median) | Turnaround (median) | Turnaround (90th) | Needs the hire |")
        w("|---|---:|---:|---:|---:|---|")
        for s in st["steps"]:
            q = f"{s['queue_median']:.1f} d" if s["queue_median"] is not None else "n/a"
            t = f"{s['turn_median']:.1f} d" if s["turn_median"] is not None else "n/a"
            p = f"{s['turn_p90']:.1f} d" if s["turn_p90"] is not None else "n/a"
            w(f"| {s['label']} | {s['n']:,} | {q} | {t} | {p} | {'yes' if s['needs_hire'] else 'no'} |")
        if st["vendors"]:
            w("")
            for v in st["vendors"]:
                flag = f" **{v['ratio']:.1f} times the fastest.**" if v["slow"] else ""
                w(f"- {STEP_LABEL.get(v['step'], v['step'])}, {v['vendor']}: median {v['median']:.1f} days, "
                  f"90th {v['p90']:.1f}, {v['n']:,} checks.{flag}")
        if st["methods"]:
            for m in st["methods"]:
                w(f"- {STEP_LABEL.get(m['step'], m['step'])}, {m['method']}: median {m['median']:.1f} days, "
                  f"{m['n']:,} tests.")
        ac = a.get("after_check")
        if ac:
            w("")
            sites = ", ".join(f"{s} {pct(r)}" for s, r, _ in ac["sites"][:4])
            w(f"**{pct(ac['share'])} of hires got their forms only after the background check came back.** "
              f"Highest: {sites}. While the check runs, those hires hear nothing.")
        lv = a.get("leave")
        if lv and lv["withdrawals_dated"]:
            w("")
            w("## 4. What people were waiting on when they left")
            w("")
            w(f"{lv['withdrawals_dated']:,} withdrawals have a date. Several steps are usually open at once, "
              "so the shares add up to more than 100% and a step here is a lead, not a verdict. "
              "Section 5 tests the causes.")
            w("")
            w("| Step open at withdrawal | Withdrawals | Share | Per 100 hire-days waiting |")
            w("|---|---:|---:|---:|")
            for s in lv["steps"]:
                w(f"| {s['label']} | {s['open_at_withdrawal']:,} | {pct(s['share'])} | {s['per_100_days']:.2f} |")
            if lv["nothing_open"]:
                w("")
                w(f"{lv['nothing_open']:,} left with nothing open: every step was done and they were "
                  "waiting only for the day.")
            w("")
    w("## 5. What drives it, tested within strata")
    w("")
    if a["drivers"] is None:
        w(a["drivers_note"])
    else:
        surv = [d for d in a["drivers"] if d["verdict"] == "survives"]
        expl = [d for d in a["drivers"] if d["verdict"] == "explained"]
        cant = [d for d in a["drivers"] if d["verdict"] == "cannot separate"]
        if surv:
            w("A cause is named only if it clears Holm at 5% across everything tested, keeps its "
              "sign and at least 40% of its size inside every check.")
            w("")
            w("| Cause | Hires | Raw | After checks | Hires recoverable |")
            w("|---|---:|---:|---:|---:|")
            for d in surv:
                w(f"| {d['label']} | {d['n_exposed']:,} | {pts(d['raw'])} | {pts(d['adjusted'])} | "
                  f"~{d['recoverable']:.0f} |")
            for d in surv:
                if d.get("split"):
                    sp = d["split"]
                    w("")
                    w(f"{d['label']}: first-shift no-shows {pct(sp['no_show'])} against {pct(sp['no_show_rest'])} "
                      f"elsewhere; withdrawals {pct(sp['withdrew'])} against {pct(sp['withdrew_rest'])}.")
        else:
            w("Nothing cleared the bar.")
        if expl:
            w("")
            w("**Explained by something else** (no fix is built on these):")
            w("")
            for d in expl:
                w(f"- {d['label']}: {pts(d['raw'])} raw, explained by {EXPLAIN_WORD.get(d['explained_by'], d['explained_by'])}.")
        if cant:
            w("")
            w("**Cannot be separated in these files:**")
            w("")
            for d in cant:
                w(f"- {d['label']}: {pts(d['raw'])} raw, inseparable from {', '.join(d['inseparable_from'])}.")
    w("")
    r = a["rescinded"]
    w("## 6. Rescinded offers")
    w("")
    line = f"{r['n']:,} offers rescinded ({pct(r['rate'], 1)}), not counted as losses above."
    if r["by_step"]:
        line += " By failed step: " + ", ".join(
            f"{STEP_LABEL.get(k, k)} {v:,}" for k, v in
            sorted(r["by_step"].items(), key=lambda kv: -kv[1])) + "."
    w(line)
    if r["sites"]:
        w("")
    for s in r["sites"]:
        w(f"- {s['site']}: {pct(s['rate'])} of its offers rescinded ({s['n']:,} offers). "
          "Worth a look at how it screens before the offer, but it is not a site losing hires.")
    w("")
    w("## 7. What I could not determine")
    w("")
    for what, col in a["cannot"]:
        w(f"- {cap(what)}" + (f": needs {col}." if col else ". No onboarding log holds that."))
    w("")
    w("## 8. The fixes")
    w("")
    for i, p in enumerate(a["plan"], 1):
        w(f"{i}. **{p['rule']}** {p['because']}")
    w("")
    w("**Measure it:** the share of decided hires lost each month, and the median gap, by site. "
      "Read them again on the same files four weeks after a change.")
    return "\n".join(L) + "\n"


def jsonable(x):
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    if isinstance(x, (dt.datetime, dt.date)):
        return x.isoformat()
    return x


# ================================================================= tests ====

def _write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)


def _gen():
    sys.path.insert(0, SAMPLE_DIR)
    import generate
    return generate


def run_tests():
    results = []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))

    def refused(fn):
        try:
            fn()
        except Refused as e:
            return str(e)
        return None

    exp = json.load(open(EXPECTED, encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="odd-test-")

    def run(hires, steps=None, as_of=SAMPLE_AS_OF, tag="x"):
        hp = os.path.join(tmp, f"{tag}_h.csv")
        _write_csv(hp, hires)
        sp = None
        if steps:
            sp = os.path.join(tmp, f"{tag}_s.csv")
            _write_csv(sp, steps)
        return analyse(load(hp, sp, as_of))

    # --- the sample, against what was planted
    data = load(SAMPLE_HIRES, SAMPLE_STEPS, SAMPLE_AS_OF)
    a = analyse(data)
    c = a["count"]
    for k, v in exp["count"].items():
        ok(f"count: {k} = {v}", c[k] == v, f"got {c[k]}")
    ok("loss rate excludes rescinded and pending",
       abs(c["loss_rate"] - c["lost"] / (c["started"] + c["lost"])) < 1e-9)
    surv = {d["key"] for d in a["drivers"] if d["verdict"] == "survives"}
    for k in exp["survives"]:
        ok(f"planted cause found: {k}", k in surv)
    ok("nothing else survives", surv == set(exp["survives"]), f"survivors {sorted(surv)}")
    for k in exp["survives"]:
        d = find(a, k)
        ok(f"{k} raises the loss", d and d.get("adjusted", 0) > 0)
    for k, by in exp["explained"].items():
        d = find(a, k)
        ok(f"herring {k} explained by {by}", d and d["verdict"] == "explained"
           and d.get("explained_by") == by, d and (d["verdict"], d.get("explained_by")))
    for k in exp["null"]:
        d = find(a, k)
        ok(f"null {k} not named", d is None or d["verdict"] != "survives")
    lab_sites = {"LOC-02", "LOC-05", "LOC-08", "LOC-13", "LOC-16", "LOC-18",
                 "LOC-22", "LOC-24", "LOC-27", "LOC-29"}
    ok("no site named for its lab tests or its long gaps",
       not {k for k in surv if k.startswith("site:") and k[5:] in lab_sites | {
           f"LOC-{i}" for i in range(21, 31)}})
    ok("high-rescind site is not a losing site",
       f"site:{exp['rescind_site']}" not in surv)
    ok("high-rescind site named under rescinded",
       a["rescinded"]["sites"] and a["rescinded"]["sites"][0]["site"] == exp["rescind_site"])
    ok("rescinds are attributed to the failed step",
       a["rescinded"]["by_step"].get("background_check", 0) > a["rescinded"]["by_step"].get("drug_test", 0))
    slow = [v for v in a["steps"]["vendors"] if v["slow"]]
    ok("slow vendor found from turnaround", [v["vendor"] for v in slow] == [exp["slow_vendor"]])
    ok("slow vendor at least twice as slow", slow and slow[0]["ratio"] >= 2)
    meth = {m["method"]: m["median"] for m in a["steps"]["methods"]}
    ok("lab tests take longer than on site", meth.get("lab", 0) > 2 * meth.get("onsite", 99))
    ok("forms-after-check sites found",
       a["after_check"] and set(exp["after_check_sites"]) <= {s for s, _, _ in a["after_check"]["sites"]})
    ok("background check is the step most often open at withdrawal",
       a["leave"]["steps"][0]["step"] == "background_check")
    split = find(a, f"site:{exp['no_show_site']}").get("split", {})
    ok("planted site shows as first-shift no-shows",
       split and split["no_show"] > 3 * split["no_show_rest"])
    rules = " ".join(p["rule"] for p in a["plan"])
    ok("plan sets a gap rule", f"within {LONG_GAP - 1} days" in rules)
    ok("gap threshold is 10 days on the sample", a["gap"]["long"] == LONG_GAP)
    ok("plan says forms at the offer", "at the offer" in rules)
    ok("plan addresses the lab test", "rapid test" in rules)
    ok("plan names the no-show site", exp["no_show_site"] in rules)
    ok("plan builds nothing on the vendor herring by itself",
       not any(p["rule"].startswith("Background check vendor") for p in a["plan"]))
    md = md_report(a)
    ok("report renders every section", all(f"## {i}." in md for i in range(1, 9)))
    ok("same files, same answer",
       json.dumps(jsonable(a), sort_keys=True) == json.dumps(jsonable(analyse(
           load(SAMPLE_HIRES, SAMPLE_STEPS, SAMPLE_AS_OF))), sort_keys=True))

    # --- a world with nothing planted, and the sample with outcomes shuffled
    gen = _gen()
    for seed in (11, 12):
        h0, s0 = gen.make(seed=seed, effects=gen.PLAIN)
        a0 = run(h0, s0, tag=f"plain{seed}")
        s = [d["key"] for d in a0["drivers"] if d["verdict"] == "survives"]
        ok(f"null world {seed}: no cause named", not s, s)
    hires = list(csv.DictReader(open(SAMPLE_HIRES, encoding="utf-8")))
    steps = list(csv.DictReader(open(SAMPLE_STEPS, encoding="utf-8")))
    for seed in (1, 2, 3):
        rng = random.Random(seed)
        hh = [dict(r) for r in hires]
        idx = [i for i, r in enumerate(hh) if r["outcome"] in ("started", "no_show")
               or (r["outcome"] == "withdrew")]
        outs = [(hh[i]["outcome"], hh[i]["withdrawn_at"]) for i in idx]
        rng.shuffle(outs)
        for i, (o, wd) in zip(idx, outs):
            hh[i]["outcome"], hh[i]["withdrawn_at"] = o, wd
            if wd and wd < hh[i]["offer_accepted_at"]:
                hh[i]["withdrawn_at"] = ""
        a1 = run(hh, None, tag=f"shuf{seed}")
        s = [d["key"] for d in a1["drivers"] if d["verdict"] == "survives"]
        ok(f"shuffled outcomes {seed}: no cause named", not s, s)

    # --- the gap must be the scheduled one
    hh = [dict(r) for r in hires]
    a2 = run(hh, None, tag="hiresonly")
    ok("hires only: gap still found", "gap_long" in
       {d["key"] for d in a2["drivers"] if d["verdict"] == "survives"})
    ok("hires only: says what the steps file would add",
       any(col and "steps file" in col for _, col in a2["cannot"]))
    ok("hires only: no step sections", "steps" not in a2 and "leave" not in a2)

    # --- the withdrew-before-due trap
    hh = [dict(r) for r in hires]
    late = [r for r in hh if r["first_shift_scheduled_at"] > SAMPLE_AS_OF + " 23:59"
            and r["outcome"] == "withdrew"]
    ok("sample holds withdrew-but-not-due hires", len(late) == exp["count"]["future_withdrew"])

    # --- aliases and formats
    hh = []
    for r in hires[:1500]:
        hh.append({"Candidate ID": r["hire_id"],
                   "Hire Date": r["offer_accepted_at"][:10],
                   "Start Date": r["first_shift_scheduled_at"][:10],
                   "Status": {"started": "Hired", "withdrew": "Declined", "no_show": "NCNS",
                              "rescinded": "Revoked", "": "In Progress"}[r["outcome"]],
                   "Store": r["location_id"], "Role": r["role"]})
    a3 = run(hh, None, tag="alias")
    ok("aliases and date-only exports read", a3["count"]["decided"] > 1000)

    # --- refusals
    base = [dict(r) for r in hires[:400]]
    cases = {
        "email column": [dict(r, email="a@b.com") for r in base],
        "names as ids": [dict(r, hire_id="Maria Lopez") for r in base],
        "unknown outcomes": [dict(r, outcome="maybe") for r in base],
        "duplicate ids": base + base[:1],
        "swapped dates": [dict(r, offer_accepted_at=r["first_shift_scheduled_at"],
                               first_shift_scheduled_at=r["offer_accepted_at"]) for r in base],
        "notes column": [dict(r, notes="called twice") for r in base],
        "no outcome": [{k: v for k, v in r.items() if k != "outcome"} for r in base],
    }
    for name, rows in cases.items():
        hp = os.path.join(tmp, "ref.csv")
        _write_csv(hp, rows)
        ok(f"refuses: {name}", refused(lambda: load(hp, None, SAMPLE_AS_OF)))
    hp = os.path.join(tmp, "ref_h.csv")
    _write_csv(hp, base)
    sp = os.path.join(tmp, "ref_s.csv")
    _write_csv(sp, [dict(s, hire_id="X" + s["hire_id"]) for s in steps[:500]])
    ok("refuses: steps for other hires", refused(lambda: load(hp, sp, SAMPLE_AS_OF)))
    pipe = os.path.join(tmp, "pipe.csv")
    _write_csv(pipe, [{"application_id": "A1", "applied_at": "2026-01-01",
                       "stage_reached": "offer_extended"}])
    msg = refused(lambda: load(pipe, None))
    ok("refuses a pipeline export and points to the funnel skill",
       msg and "funnel-drop-off-analyst" in msg)
    empty = os.path.join(tmp, "empty.csv")
    open(empty, "w").close()
    ok("refuses: empty file", refused(lambda: load(empty)))
    small = run(base[:80], None, tag="small")
    ok("too few hires: counts, no causes", small["drivers"] is None and small["count"]["decided"] > 0)

    # --- a steps file with dates only, no times
    sd = [dict(x, requested_at=x["requested_at"][:10], completed_at=x["completed_at"][:10])
          for x in steps]
    a4 = run(hires, sd, tag="dateonly")
    s4 = {d["key"] for d in a4["drivers"] if d["verdict"] == "survives"}
    ok("date-only steps: gap and lab still found", {"gap_long", "drug_lab"} <= s4, sorted(s4))

    # --- early leavers with no first shift date are still losses
    ed = [dict(r) for r in hires]
    blanked = 0
    for r in ed:
        if (r["outcome"] == "withdrew" and r["withdrawn_at"] < "2026-09-30"
                and blanked < 120):
            r["first_shift_scheduled_at"] = ""
            blanked += 1
    a6 = run(ed, None, tag="undated")
    ok("withdrew before a first shift was scheduled: counted as losses",
       a6["count"]["early_undated"] == blanked and a6["count"]["loss_all"] > a6["count"]["loss_rate"],
       (blanked, a6["count"]["early_undated"]))
    rec = [dict(r, offer_accepted_at="2026-10-30 10:00", first_shift_scheduled_at="",
                outcome="withdrew", withdrawn_at="2026-10-30 18:00") for r in hires[:40]]
    a7 = run([dict(r) for r in hires[40:]] + rec, None, tag="recentundated")
    ok("recent undated withdrawals are not counted yet", a7["count"]["early_undated"] == 0)

    # --- a company whose gaps are all long still gets a gap read
    lg = [dict(r) for r in hires]
    for r in lg:
        o = dt.datetime.strptime(r["offer_accepted_at"], "%Y-%m-%d %H:%M")
        f = dt.datetime.strptime(r["first_shift_scheduled_at"], "%Y-%m-%d %H:%M")
        r["first_shift_scheduled_at"] = (f + dt.timedelta(days=12)).strftime("%Y-%m-%d %H:%M")
    a8 = run(lg, None, as_of="2026-11-14", tag="longgaps")
    ok("all gaps long: the threshold moves to the median", a8["gap"]["long"] > LONG_GAP)
    ok("date-only steps: no site or recruiter named but the planted one",
       {k for k in s4 if k.startswith(("site:", "recruiter:"))} <= {f"site:{exp['no_show_site']}"},
       sorted(s4))

    # --- no withdrawal dates: the leave section says so instead of guessing
    nw = [{k: v for k, v in r.items() if k != "withdrawn_at"} for r in hires]
    a5 = run(nw, steps, tag="nowd")
    ok("no withdrawn_at: no step blamed for leaving", a5["leave"]["withdrawals_dated"] == 0)
    ok("no withdrawn_at: named as missing", any(col == "withdrawn_at" for _, col in a5["cannot"]))

    # --- damaged files never crash the engine
    rng = random.Random(7)
    crashes = []
    for i in range(60):
        rows = [dict(r) for r in rng.sample(hires, 300)]
        for r in rows:
            for k in list(r):
                u = rng.random()
                if u < .03:
                    r[k] = ""
                elif u < .045:
                    r[k] = rng.choice(["n/a", "2026-13-45", "  ", "0", "-1", "31/12/2026",
                                       "2026-02-30 25:61", "été", "None"])
        if rng.random() < .3:
            for r in rows:
                r.pop(rng.choice(list(r)), None)
        hp = os.path.join(tmp, f"fz{i}.csv")
        keys = sorted({k for r in rows for k in r})
        with open(hp, "w", newline="", encoding="utf-8") as fh:
            wr = csv.DictWriter(fh, fieldnames=keys)
            wr.writeheader()
            for r in rows:
                wr.writerow({k: r.get(k, "") for k in keys})
        try:
            md_report(analyse(load(hp, None, SAMPLE_AS_OF)))
        except Refused:
            pass
        except Exception as e:                       # noqa: BLE001
            crashes.append(f"{i}: {type(e).__name__}: {e}")
    ok("60 damaged hires files: refused or read, never a crash", not crashes, crashes[:3])
    crashes = []
    hp = os.path.join(tmp, "fzh.csv")
    _write_csv(hp, hires[:600])
    ids = {r["hire_id"] for r in hires[:600]}
    mine = [x for x in steps if x["hire_id"] in ids]
    for i in range(40):
        rows = [dict(x) for x in mine]
        for x in rows:
            for k in list(x):
                u = rng.random()
                if u < .04:
                    x[k] = ""
                elif u < .06:
                    x[k] = rng.choice(["n/a", "2026-13-45", "lab", "yes", "-3",
                                       "2020-01-01", "2031-01-01 07:00", "failed"])
        sp = os.path.join(tmp, f"fzs{i}.csv")
        _write_csv(sp, rows)
        try:
            md_report(analyse(load(hp, sp, SAMPLE_AS_OF)))
        except Refused:
            pass
        except Exception as e:                       # noqa: BLE001
            crashes.append(f"{i}: {type(e).__name__}: {e}")
    ok("40 damaged steps files: refused or read, never a crash", not crashes, crashes[:3])

    failed = [r for r in results if not r[1]]
    for name, good, detail in results:
        print(("PASS " if good else "FAIL ") + name + ("" if good or detail == "" else f"  ({detail})"))
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 0 if not failed else 1


# ================================================================== main ====

def main(argv=None):
    ap = argparse.ArgumentParser(description="Onboarding drop-off diagnostic")
    ap.add_argument("--hires")
    ap.add_argument("--steps")
    ap.add_argument("--as-of")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--md", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args(argv)
    try:
        if args.test:
            return run_tests()
        if args.demo:
            args.hires, args.steps, args.as_of = SAMPLE_HIRES, SAMPLE_STEPS, SAMPLE_AS_OF
        if not args.hires:
            ap.error("--hires is required (or --demo, or --test)")
        a = analyse(load(args.hires, args.steps, args.as_of))
        if args.json:
            print(json.dumps(jsonable(a), indent=2))
        else:
            print(md_report(a))
        return 0
    except Refused as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 3
    except Exception as e:                           # noqa: BLE001
        print(f"ENGINE FAILURE: {type(e).__name__}: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
