#!/usr/bin/env python3
"""
Cycle-time engine.

Deterministic analysis of how long a frontline hiring funnel takes, stage by
stage. Standard library only - no pandas, no numpy, no network. The same input
always produces the same output, which is the point: the statistics in this
skill are computed here, not improvised in prose.

    analyze.py --input export.csv [--md report.md] [--out report.json] [--as-of YYYY-MM-DD]
    analyze.py --demo
    analyze.py --test

Exit codes: 0 report written, 3 input refused, 4 the engine itself failed.

The input must be mapped to the canonical schema in references/schema.json.
Every data lane - a CSV export, an MCP, anything - maps into that schema
first; this file reads nothing else.

The question this engine answers is not "what is our time to hire". A single
number averages a queue that is long for one reason at one stage with a queue
that is short everywhere else, and points at nothing. It answers: which stage
holds the queue, for whom, and is that stage slow always or only under load.

What it refuses to do:
  - analyse a file carrying nominative columns
  - time a stage over arrivals so recent that only the fast ones have had time
    to finish it
  - count a candidate who left the funnel as one still waiting
  - present a segment effect that did not survive its confound check
  - trust a set of timestamps that contradicts its own stage order
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(SKILL_DIR, "references", "schema.json")

with open(SCHEMA_PATH, encoding="utf-8") as _f:
    SCHEMA = json.load(_f)

# Two funnel shapes live in the schema: a W2 hire ends at a first shift, a gig
# sign-up ends at a first completed job. The engine binds one profile per file,
# chosen from the values actually present in stage_reached, and every pass
# downstream is written against the bound names. No pass below knows which
# shape it is working on, and none may contain a literal stage index.
STAGE_PROFILES = SCHEMA["stage_profiles"]
PROFILE_NAMES = [k for k in STAGE_PROFILES if not k.startswith("$")]

PROFILE = None
PROFILE_NAME = None
STAGES = []
STAGE_IX = {}
STAGE_DATE = []
START_NOUN = ""

DT = SCHEMA["duration_thresholds"]
MIN_STEP = DT["min_completed_per_step"]
MIN_SEG = DT["min_segment_completed"]
SEG_RATIO = DT["segment_flag_ratio"]
SEG_MIN_DAYS = DT["segment_flag_min_days"]
LOAD_RATIO = DT["load_effect_ratio"]
LOAD_MIN_DAYS = DT["load_min_days"]
MAX_DISORDER = DT["max_out_of_order_share"]
CENSOR_WARN = DT["censoring_warn_share"]
CENSOR_REFUSE = DT["censoring_refuse_share"]
HORIZON_MIN = DT["open_horizon_min_days"]
HORIZON_MULT = DT["open_horizon_p90_multiple"]
MAX_DUP = DT["max_duplicate_id_share"]
MAX_BAD_DATES = DT["max_unreadable_date_share"]

EXIT_OK, EXIT_REFUSED, EXIT_FAILED = 0, 3, 4

# Set once per file by load(): how slash dates are ordered, the day the export
# ends, and what was dropped on the way in. Reset at the start of every load.
DATE_ORDER = "ymd"
AS_OF = None
INGEST = {}
MIN_ROWS = SCHEMA["thresholds"]["min_rows_total"]
KILL_FRACTION = SCHEMA["thresholds"]["confound_kill_fraction"]

SEGMENT_DIMS = ["location_id", "region", "source", "role"]
DIM_NOUN = {"location_id": ("site", "sites"), "region": ("region", "regions"),
            "source": ("source", "sources"), "role": ("role", "roles"),
            "hiring_manager_id": ("manager", "managers")}


def noun(dim, n):
    one, many = DIM_NOUN.get(dim, (dim, dim))
    return one if n == 1 else many


def _skill_version():
    """The version of the skill that produced this report. An installed copy
    never updates itself, so a report that cannot say what produced it is a
    report nobody can reproduce."""
    try:
        with open(os.path.join(SKILL_DIR, "SKILL.md"), encoding="utf-8") as fh:
            head = fh.read(2000)
        found = re.search(r"^version:\s*(.+)$", head, re.M)
        return found.group(1).strip() if found else "unknown"
    except OSError:
        return "unknown"


SKILL_VERSION = _skill_version()


class Refusal(Exception):
    """Raised when the engine will not analyse the input. Not an error."""


def bind_profile(name):
    """Bind the engine to one funnel shape for the duration of one analysis."""
    global PROFILE, PROFILE_NAME, STAGES, STAGE_IX, STAGE_DATE, START_NOUN
    PROFILE = STAGE_PROFILES[name]
    PROFILE_NAME = name
    STAGES = PROFILE["stages"]
    STAGE_IX = {s: i for i, s in enumerate(STAGES)}
    STAGE_DATE = PROFILE["stage_dates"]
    START_NOUN = PROFILE["start_noun"]


def detect_profile(rows):
    """Pick the funnel shape from the stage names the export actually uses.

    An export that mixes vocabularies is refused rather than guessed at. A
    cycle time measured against the wrong stage list is wrong in a way that
    still looks plausible, which is the worst kind of wrong."""
    seen = {(r.get("stage_reached") or "").strip().lower() for r in rows}
    seen.discard("")
    if not seen:
        raise Refusal("No stage_reached values found. There is no funnel to time.")
    scored = sorted(((len(seen & set(STAGE_PROFILES[n]["stages"])), n)
                     for n in PROFILE_NAMES), reverse=True)
    best_n, best = scored[0]
    if best_n == 0:
        raise Refusal(
            "None of the stage_reached values match a funnel this engine knows: "
            + ", ".join(sorted(seen)[:8]) + ". Map them onto one of the schema's "
            "stage lists first -- " + "; ".join(
                f"{n}: {' -> '.join(STAGE_PROFILES[n]['stages'])}" for n in PROFILE_NAMES) + ".")
    unknown = seen - set(STAGE_PROFILES[best]["stages"])
    if unknown:
        raise Refusal(
            f"Read as the '{best}' funnel, but these stage_reached values do not "
            "belong to it: " + ", ".join(sorted(unknown)) + ". Mixed stage "
            "vocabularies produce a cycle time that is wrong in a way that still "
            "looks plausible, so this will not run.")
    return best


bind_profile("hire")


# --------------------------------------------------------------- primitives

_ISO = re.compile(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?=$|[T\s])")
_SLASH = re.compile(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?=$|[T\s,])")


def parse_date(value):
    """A calendar date from an ISO date or datetime, or a day-first or
    month-first date once the file has shown which it uses. Anything else is
    None, and load() refuses a file where that happens to more than a sliver
    of a column rather than timing the rows it could read. A time and a UTC
    offset are dropped: the local calendar date is what a candidate waited."""
    if not value:
        return None
    v = value.strip()
    try:
        m = _ISO.match(v)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = _SLASH.match(v)
            if not m or DATE_ORDER == "ymd":
                return None
            a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            d, mo = (a, b) if DATE_ORDER == "dmy" else (b, a)
        if not 2000 <= y <= 2100:
            return None
        return date(y, mo, d)
    except ValueError:
        return None


def detect_date_order(rows, cols):
    """Day-first or month-first, decided from the file, never assumed. A file
    where every slash date has both parts at 12 or under could be either, and
    reading it the wrong way moves dates by months without an error."""
    dmy = mdy = slash = 0
    for row in rows:
        for col in cols:
            m = _SLASH.match((row.get(col) or "").strip())
            if not m:
                continue
            slash += 1
            a, b = int(m.group(1)), int(m.group(2))
            dmy += a > 12
            mdy += b > 12
    if not slash:
        return "ymd"
    if dmy and mdy:
        raise Refusal(
            "The stage dates mix day-first and month-first formats (some read as "
            "31/01, others as 01/31). Re-export them as YYYY-MM-DD; a date read "
            "the wrong way is wrong by months and looks fine.")
    if dmy:
        return "dmy"
    if mdy:
        return "mdy"
    raise Refusal(
        f"{slash:,} stage dates are written like 03/04/2026, and none of them "
        "shows whether that is 3 April or 4 March. Re-export the dates as "
        "YYYY-MM-DD; guessing would move them by months without an error.")


def quantile(values, q):
    """Nearest-rank on a sorted copy. Deterministic, and it returns a value that
    actually occurred rather than an interpolation between two that did not."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return float(vals[0])
    pos = q * (len(vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(vals) - 1)
    frac = pos - lo
    return round(vals[lo] * (1 - frac) + vals[hi] * frac, 2)


def median(values):
    return quantile(values, 0.5)


def spread(values):
    """The shape of a wait, not just its middle. p90 is what a candidate at the
    back of the queue actually experiences, and it is the number a median hides."""
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "median": None, "p75": None, "p90": None, "mean": None}
    return {
        "n": len(vals),
        "median": median(vals),
        "p75": quantile(vals, 0.75),
        "p90": quantile(vals, 0.90),
        "mean": round(sum(vals) / len(vals), 2),
    }


def stage_ix(row):
    return STAGE_IX.get((row.get("stage_reached") or "").strip().lower())


def ratio(a, b):
    """a/b, guarded. None when the comparison cannot be made rather than a
    fabricated 0 or infinity."""
    if a is None or b is None or b == 0:
        return None
    return round(a / b, 3)


# --------------------------------------------------------------- ingest

def check_columns(columns):
    """Stop on anything nominative. Conservative by design."""
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
            "addresses, dates of birth and free-text notes. Nothing in a cycle-time "
            "analysis needs to know who anybody is.")


def load(path, as_of=None):
    global DATE_ORDER, AS_OF, INGEST
    DATE_ORDER, AS_OF, INGEST = "ymd", None, {}
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            columns = [c.strip().lower() for c in (reader.fieldnames or [])]
            reader.fieldnames = columns
            rows = list(reader)
    except UnicodeDecodeError:
        raise Refusal("That file is not UTF-8 text. Save it again as 'CSV UTF-8' "
                      "and re-run.")
    except csv.Error as err:
        raise Refusal(f"That file could not be read as a CSV ({err}).")
    if not columns:
        raise Refusal("That file has no header row.")
    check_columns(columns)

    missing = [c for c, spec in SCHEMA["columns"].items()
               if spec.get("required") and c not in columns]
    if missing:
        raise Refusal("Missing required columns: " + ", ".join(missing)
                      + ". Without them there is no funnel to time.")

    bind_profile(detect_profile(rows))

    kept = [r for r in rows if stage_ix(r) is not None]
    no_id = [r for r in kept if not (r.get("application_id") or "").strip()]
    kept = [r for r in kept if (r.get("application_id") or "").strip()]
    INGEST["rows_without_id"] = len(no_id)

    # One row per application. A raw status-history log has one row per status
    # change, so the same id comes back once per stage: timing it would count
    # every candidate several times, and at different stages.
    seen, dupes, unique = set(), 0, []
    for r in kept:
        key = r["application_id"].strip()
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        unique.append(r)
    if kept and dupes / len(kept) > MAX_DUP:
        raise Refusal(
            f"{dupes:,} of {len(kept):,} rows repeat an application_id already "
            "seen. That is the shape of a status-history log (one row per status "
            "change), not one row per application. Pivot it first: one row per "
            "application, one date column per stage, taking the first time each "
            "stage was reached.")
    INGEST["duplicate_rows_dropped"] = dupes
    kept = unique
    if len(kept) < MIN_ROWS:
        raise Refusal(
            f"Only {len(kept):,} usable rows. Below {MIN_ROWS:,} a stage median "
            "moves several days on a handful of records, so it will not run. "
            "Export a longer period rather than accepting a thin answer.")

    present_dates = [c for c in STAGE_DATE if c in columns]
    if len(present_dates) < 2:
        raise Refusal(
            "This export carries fewer than two stage timestamp columns ("
            + (", ".join(present_dates) or "none") + "), so there is no interval "
            "to measure. A cycle-time analysis needs the date a candidate arrived "
            "at each stage, not just the stage they are in now. The stage columns "
            "for this funnel are: " + ", ".join(STAGE_DATE) + ".")

    DATE_ORDER = detect_date_order(kept, present_dates)
    INGEST["date_order"] = DATE_ORDER
    for col in present_dates:
        filled = [r.get(col) for r in kept if (r.get(col) or "").strip()]
        bad = [v for v in filled if parse_date(v) is None]
        if filled and len(bad) / len(filled) > MAX_BAD_DATES:
            raise Refusal(
                f"{len(bad):,} of {len(filled):,} values in {col} are not dates this "
                f"engine can read (for example {bad[0].strip()[:20]!r}). Spreadsheet "
                "serial numbers and text dates need converting to YYYY-MM-DD first. "
                "Timing only the rows that parsed would time a subset nobody chose.")

    latest = None
    for r in kept:
        for col in present_dates:
            d = parse_date(r.get(col))
            if d and (latest is None or d > latest):
                latest = d
    if as_of is not None:
        if latest and as_of < latest:
            raise Refusal(
                f"--as-of {as_of.isoformat()} is before the latest date in the file "
                f"({latest.isoformat()}). The export cannot end before its own data.")
        latest = as_of
    AS_OF = latest
    return columns, kept


# ---------------------------------------------------------- time integrity

def transitions(columns):
    """The consecutive stage pairs this export can actually measure, with the
    gaps named. Derived from the bound profile - never a literal index."""
    out = []
    for i in range(len(STAGES) - 1):
        a, b = STAGE_DATE[i], STAGE_DATE[i + 1]
        out.append({
            "index": i,
            "step": f"{STAGES[i]} -> {STAGES[i + 1]}",
            "from_stage": STAGES[i], "to_stage": STAGES[i + 1],
            "from_col": a, "to_col": b,
            "measurable": a in columns and b in columns,
        })
    return out


def gap(row, step):
    """Days between two stage timestamps. None when either is missing.
    A negative gap is returned as-is so the integrity check can count it;
    no pass downstream ever sees one."""
    a, b = parse_date(row.get(step["from_col"])), parse_date(row.get(step["to_col"]))
    if a is None or b is None:
        return None
    return (b - a).days


def integrity(rows, steps):
    """Timestamps that contradict the stage order are not noise to be filtered
    quietly. Above a small share they mean the export's dates do not mean what
    the column names say, and every median below would be fiction."""
    report, worst = [], 0.0
    for step in steps:
        if not step["measurable"]:
            continue
        gaps = [gap(r, step) for r in rows]
        seen = [g for g in gaps if g is not None]
        if not seen:
            continue
        bad = sum(1 for g in seen if g < 0)
        share = bad / len(seen)
        worst = max(worst, share)
        report.append({"step": step["step"], "pairs": len(seen),
                       "out_of_order": bad, "share": round(share, 4)})
    offenders = [r for r in report if r["share"] > MAX_DISORDER]
    if offenders:
        raise Refusal(
            "These timestamps contradict the stage order: "
            + "; ".join(f"{r['step']} has {r['out_of_order']:,} of {r['pairs']:,} "
                        f"rows ({r['share']:.1%}) arriving before they left"
                        for r in offenders)
            + ". Above " + f"{MAX_DISORDER:.0%}" + " this is a mapping problem, not "
            "data entry - usually two columns crossed, or a status-history pivot "
            "that did not take the first time each stage was reached. Every "
            "median computed on these dates would be fiction, so this will not run.")
    return {"steps": report, "worst_share": round(worst, 4)}


CUTOFF = {}          # step index -> last arrival date that has had time to finish


def horizon(gaps):
    """How long a step needs before most people who will finish it have: three
    times its p90, and never under two weeks. Arrivals later than that are
    counted, not timed, because only their fast ones have finished yet."""
    p90 = quantile(gaps, 0.90) if gaps else None
    return max(HORIZON_MIN, int(-(-(p90 or 0) * HORIZON_MULT // 1)))


def timed(row, step):
    """The wait at one step for one row, or None. None when either date is
    missing, when the dates run backwards (the integrity check counts those),
    or when the row arrived at the step too recently for its wait to be fair
    to time."""
    g = gap(row, step)
    if g is None or g < 0:
        return None
    cut = CUTOFF.get(step["index"])
    if cut is not None and parse_date(row.get(step["from_col"])) > cut:
        return None
    return g


def queue_state(rows, step, has_exit):
    """Everyone who arrived at this step, sorted by what became of them.

    The trap this avoids runs both ways. Count every candidate without the next
    date as still waiting, and the ones who were rejected or withdrew months ago
    swell a queue that does not exist (on the retail sample, 8,412 people
    "waiting" 270 days to be screened). Ignore the ones still open, and the
    median flatters the process. So: moved on; skipped (a later stage is dated,
    this one is not); undated (stage_reached says they moved on, the date is
    missing); left (closed with an exit reason); in flight (open, arrived inside
    the step's horizon); stale (open, no movement for longer than the horizon).
    Without an exit_reason column, left and open cannot be told apart, and the
    report says so."""
    later = [c for c in STAGE_DATE[step["index"] + 2:]]
    cut = CUTOFF.get(step["index"])
    counts = dict(arrived=0, completed=0, skipped=0, undated=0, left=0,
                  in_flight=0, stale_open=0)
    flight_ages, stale_ages = [], []
    for row in rows:
        a = parse_date(row.get(step["from_col"]))
        if a is None:
            continue
        counts["arrived"] += 1
        if parse_date(row.get(step["to_col"])) is not None:
            counts["completed"] += 1
            continue
        if any(parse_date(row.get(c)) for c in later):
            counts["skipped"] += 1
            continue
        ix = stage_ix(row)
        if ix is not None and ix > step["index"]:
            counts["undated"] += 1
            continue
        if has_exit and (row.get("exit_reason") or "").strip():
            counts["left"] += 1
            continue
        age = (AS_OF - a).days
        if cut is None or a > cut:
            counts["in_flight"] += 1
            flight_ages.append(age)
        else:
            counts["stale_open"] += 1
            stale_ages.append(age)
    arrived = counts["arrived"] or 1
    counts.update({
        "share_in_flight": round(counts["in_flight"] / arrived, 4),
        "share_stale": round(counts["stale_open"] / arrived, 4),
        "age_in_flight": spread(flight_ages),
        "age_stale": spread(stale_ages),
        "closure_known": has_exit,
        "as_of": AS_OF.isoformat() if AS_OF else None,
        "timed_arrivals_through": cut.isoformat() if cut else None,
        # Open applications older than the horizon either left without being
        # closed or are stuck. If they are stuck, they will finish slower than
        # anyone timed, so a large share of them makes the median optimistic.
        "biases_median": bool(has_exit and counts["stale_open"] / arrived >= CENSOR_WARN),
    })
    return counts


# --------------------------------------------------------------- pass 1

def pass1_clock(rows, steps, has_exit):
    """How long each stage takes, and what share of the whole it carries.

    Ranked by total days held, not by median. A stage with a four-day median
    that everybody passes through holds more of the calendar than a
    twenty-day median only forty people ever reach, and the first is where
    the time actually is."""
    out = []
    for step in steps:
        if not step["measurable"]:
            out.append(dict(step, measurable=False))
            continue
        raw = [g for g in (gap(r, step) for r in rows) if g is not None and g >= 0]
        days = horizon(raw)
        CUTOFF[step["index"]] = AS_OF - timedelta(days=days)
        gaps = [g for g in (timed(r, step) for r in rows) if g is not None]
        cen = queue_state(rows, step, has_exit)
        block = dict(step)
        block["horizon_days"] = days
        block["wait"] = spread(gaps)
        block["censoring"] = cen
        block["conclusive"] = len(gaps) >= MIN_STEP
        block["days_held"] = round(sum(gaps), 1) if gaps else 0.0
        out.append(block)

    total_held = sum(s.get("days_held", 0) for s in out) or 1
    for step in out:
        if "days_held" in step:
            step["share_of_elapsed"] = round(step["days_held"] / total_held, 4)
    return out


def end_to_end(rows):
    """Total elapsed time for everybody who reached the end of the funnel.
    Not the sum of the stage medians, which is a number nobody experienced."""
    first, last = STAGE_DATE[0], STAGE_DATE[-1]
    pairs = []
    for row in rows:
        a, b = parse_date(row.get(first)), parse_date(row.get(last))
        if a and b and (b - a).days >= 0:
            pairs.append((a, (b - a).days))
    days = horizon([g for _, g in pairs])
    cut = AS_OF - timedelta(days=days) if AS_OF else None
    gaps = [g for a, g in pairs if cut is None or a <= cut]
    block = spread(gaps)
    block["finished"] = len(pairs)
    block["horizon_days"] = days
    block["timed_applications_through"] = cut.isoformat() if cut else None
    block["from_stage"], block["to_stage"] = STAGES[0], STAGES[-1]
    block["start_noun"] = START_NOUN
    return block


# --------------------------------------------------------------- pass 2

def by_segment(rows, step, dim):
    """Median wait per segment on one dimension, and which segments carry a
    materially longer one than the rest of the file."""
    buckets = defaultdict(list)
    for row in rows:
        key = (row.get(dim) or "").strip()
        if not key:
            continue
        g = timed(row, step)
        if g is not None:
            buckets[key].append(g)

    eligible = {k: v for k, v in buckets.items() if len(v) >= MIN_SEG}
    if len(eligible) < 2:
        return None

    everything = [g for v in eligible.values() for g in v]
    flagged, table = [], []
    for key, vals in sorted(eligible.items()):
        # Against the rest of the file, not against the overall median, which
        # a large enough offender drags towards itself until it stops looking
        # like an offender.
        rest = [g for k, v in eligible.items() if k != key for g in v]
        mine, theirs = median(vals), median(rest)
        row = {"segment": key, "n": len(vals), "median": mine,
               "p90": quantile(vals, 0.90), "rest_median": theirs,
               "ratio": ratio(mine, theirs),
               "excess_days": round(mine - theirs, 2) if None not in (mine, theirs) else None}
        table.append(row)
        if (row["ratio"] is not None and row["ratio"] >= SEG_RATIO
                and row["excess_days"] is not None and row["excess_days"] >= SEG_MIN_DAYS):
            flagged.append(row)

    table.sort(key=lambda r: (r["median"] is None, -(r["median"] or 0)))
    return {
        "dimension": dim, "segments": len(eligible),
        "overall_median": median(everything),
        "flagged": sorted(flagged, key=lambda r: -(r["excess_days"] or 0)),
        "table": table[:12],
    }


def pass2_concentration(rows, clock):
    """Is a slow stage slow for everybody, or slow for a minority?

    The difference decides what you do about it. A stage that is slow
    everywhere is the process; a stage that is slow at eight sites out of
    forty-two is those eight sites, and fixing it does not mean redesigning
    anything."""
    out = []
    for step in clock:
        if not step.get("measurable") or not step.get("conclusive"):
            continue
        dims = {}
        for dim in SEGMENT_DIMS:
            block = by_segment(rows, step, dim)
            if block:
                dims[dim] = block
        if dims:
            out.append({"index": step["index"], "step": step["step"], "by": dims,
                        "concentrated": any(d["flagged"] for d in dims.values())})
    return out


# --------------------------------------------------------------- pass 3

def peak_months(rows):
    """The months carrying materially more volume than a typical month.
    Derived from the file, because one vertical's peak is another's trough."""
    # Calendar months, with the year: an export running September to
    # September must not add two Septembers together and call it a peak.
    counts = defaultdict(int)
    for row in rows:
        d = parse_date(row.get(STAGE_DATE[0]))
        if d:
            counts[f"{d.year:04d}-{d.month:02d}"] += 1
    if len(counts) < 6:
        return set(), dict(sorted(counts.items()))
    typical = median(list(counts.values()))
    peak = {m for m, n in counts.items() if typical and n > typical * 1.5}
    return peak, dict(sorted(counts.items()))


def pass3_load(rows, clock, peak):
    """Is this stage slow always, or slow when volume arrives?

    The distinction is the whole planning value of the analysis. A stage that
    lengthens under load has enough capacity for a normal month and not for a
    peak - you staff it, and it fixes itself in January. A stage that is long
    in every month is how the process is built, and no amount of staffing
    touches it. Told apart, they have different owners and different costs;
    averaged together, they look like one vague complaint about speed."""
    if not peak:
        return {"detected": False, "reason": "no month carries peak volume in this file",
                "steps": []}
    out = []
    for step in clock:
        if not step.get("measurable") or not step.get("conclusive"):
            continue
        hi, lo = [], []
        for row in rows:
            # The month the candidate arrived at this step, not the month they
            # applied: a peak in applications reaches the first-shift queue
            # weeks later.
            d = parse_date(row.get(step["from_col"]))
            g = timed(row, step)
            if d is None or g is None:
                continue
            (hi if f"{d.year:04d}-{d.month:02d}" in peak else lo).append(g)
        if len(hi) < MIN_SEG or len(lo) < MIN_SEG:
            continue
        mh, ml = median(hi), median(lo)
        r = ratio(mh, ml)
        out.append({
            "index": step["index"], "step": step["step"],
            "peak": {"n": len(hi), "median": mh}, "off_peak": {"n": len(lo), "median": ml},
            "ratio": r, "excess_days": round(mh - ml, 2) if None not in (mh, ml) else None,
            # A ratio alone flags a stage that moved from one day to two. In an
            # export whose timestamps are dates, that is a rounding boundary,
            # not a capacity problem -- so a load effect has to be both
            # proportionally and absolutely material before it is reported.
            "load_sensitive": bool(r is not None and r >= LOAD_RATIO
                                   and mh is not None and ml is not None
                                   and (mh - ml) >= LOAD_MIN_DAYS),
        })
    return {"detected": True, "peak_months": sorted(peak), "steps": out}


# --------------------------------------------------------------- pass 4

def confound_check(rows, step, dim, segments, confounders):
    """Does a segment's longer wait survive when you hold another dimension
    constant, or was it that other dimension all along?

    Within each stratum of the confounder, compare the flagged segments to the
    rest, then weight those within-stratum differences by stratum size. If the
    difference largely disappears, the confounder was the explanation."""
    results = {}
    flagged = set(segments)
    raw_hi = [g for r in rows if (r.get(dim) or "").strip() in flagged
              for g in [timed(r, step)] if g is not None]
    raw_lo = [g for r in rows if (r.get(dim) or "").strip() not in flagged
              for g in [timed(r, step)] if g is not None]
    raw_diff = (median(raw_hi) - median(raw_lo)) if raw_hi and raw_lo else None

    for conf in confounders:
        if conf == dim:
            continue
        strata = defaultdict(lambda: ([], []))
        for row in rows:
            key = (row.get(conf) or "").strip()
            g = timed(row, step)
            if not key or g is None:
                continue
            bucket = strata[key]
            bucket[0 if (row.get(dim) or "").strip() in flagged else 1].append(g)

        weighted, weight = 0.0, 0
        used = 0
        for key, (hi, lo) in strata.items():
            if len(hi) < MIN_SEG or len(lo) < MIN_SEG:
                continue
            d = median(hi) - median(lo)
            w = len(hi) + len(lo)
            weighted += d * w
            weight += w
            used += 1
        if not weight or not raw_diff or used < 2:
            results[conf] = {"testable": False,
                             "reason": "not enough strata with both groups present"}
            continue
        adjusted = weighted / weight
        # Same direction and at least this much of it. An effect that reverses
        # inside the strata has not survived, however large it is.
        survived = (adjusted / raw_diff) >= KILL_FRACTION
        results[conf] = {
            "testable": True, "strata_used": used,
            "raw_excess_days": round(raw_diff, 2),
            "adjusted_excess_days": round(adjusted, 2),
            "retained": round(adjusted / raw_diff, 3) if raw_diff else None,
            "survived": bool(survived),
        }
    return results


def pass4_confounds(rows, concentration):
    out = []
    for block in concentration:
        step = {"index": block["index"], "from_col": STAGE_DATE[block["index"]],
                "to_col": STAGE_DATE[block["index"] + 1]}
        for dim, data in block["by"].items():
            if not data["flagged"]:
                continue
            names = [f["segment"] for f in data["flagged"]]
            checks = confound_check(rows, step, dim, names, SEGMENT_DIMS)
            testable = [c for c in checks.values() if c.get("testable")]
            out.append({
                "index": block["index"], "step": block["step"], "dimension": dim,
                "segments": names[:12], "segment_count": len(names),
                "checks": checks,
                "survives_all": bool(testable) and all(c["survived"] for c in testable),
                "killed_by": [k for k, c in checks.items()
                              if c.get("testable") and not c["survived"]],
            })
    return out


# --------------------------------------------------------------- pass 5

def pass5_size(concentration, confirmed):
    """What comes off the calendar if each confirmed problem is fixed.

    Stated in days and in the number of people who wait them, and nothing
    else. Whether a shorter wait converts into more hires is a different
    question with a different answer per stage, and this engine does not have
    the evidence to claim it. Saying so is cheaper than being caught at it."""
    prizes = []

    for finding in confirmed:
        block = next((b for b in concentration if b["index"] == finding["index"]), None)
        if not block:
            continue
        data = block["by"][finding["dimension"]]
        flagged = {f["segment"]: f for f in data["flagged"]}
        affected = sum(f["n"] for f in flagged.values())
        # Use the confound-adjusted excess where one was computed: the raw gap
        # includes whatever the other dimensions were carrying.
        adjusted = [c["adjusted_excess_days"] for c in finding["checks"].values()
                    if c.get("testable")]
        excess = min(adjusted) if adjusted else median(
            [f["excess_days"] for f in flagged.values()])
        if excess is None or excess <= 0:
            continue
        prizes.append({
            "index": finding["index"], "step": finding["step"],
            "dimension": finding["dimension"], "segments": list(flagged)[:12],
            "segment_count": len(flagged),
            "people_affected": affected,
            "excess_days_each": round(excess, 2),
            "calendar_days_recovered": round(excess * affected, 1),
            "kind": "structural",
            "reads": (f"{len(flagged)} {noun(finding['dimension'], len(flagged))} hold candidates "
                      f"{excess:.1f} days longer than the rest at {finding['step']}. "
                      f"{affected:,} people waited there."),
        })

    prizes.sort(key=lambda p: -p["calendar_days_recovered"])
    return prizes


def load_prizes(load):
    """The load effect sized the same way, kept separate because the fix is
    different: staffing a peak, not changing a process."""
    out = []
    for step in load.get("steps", []):
        if not step["load_sensitive"] or not step["excess_days"]:
            continue
        out.append({
            "index": step["index"], "step": step["step"],
            "kind": "load",
            "peak_months": load["peak_months"],
            "people_affected": step["peak"]["n"],
            "excess_days_each": step["excess_days"],
            "calendar_days_recovered": round(step["excess_days"] * step["peak"]["n"], 1),
            "reads": (f"{step['step']} runs {step['excess_days']:.1f} days longer in "
                      f"peak months than off-peak ({step['peak']['median']} vs "
                      f"{step['off_peak']['median']} days). This is capacity, not "
                      f"process: it returns to baseline on its own."),
        })
    return sorted(out, key=lambda p: -p["calendar_days_recovered"])


# --------------------------------------------------------------- assembly

def headline(clock, concentration, structural, load_p):
    """The one sentence, and the reason it is not 'your time to hire is N days'.

    Deliberately reports two different stages when they differ: the one holding
    the most calendar time, and the one carrying a fixable concentration. A
    reader who only gets the first goes and optimises a stage that is slow for
    everybody by design."""
    measurable = [s for s in clock if s.get("conclusive")]
    if not measurable:
        return {"stage_holding_most_time": None, "fixable": None}
    longest = max(measurable, key=lambda s: s["days_held"])
    return {
        "stage_holding_most_time": {
            "step": longest["step"],
            "median_days": longest["wait"]["median"],
            "p90_days": longest["wait"]["p90"],
            "share_of_elapsed": longest.get("share_of_elapsed"),
        },
        "stage_with_concentrated_delay": (
            {"step": structural[0]["step"], "dimension": structural[0]["dimension"],
             "segment_count": structural[0]["segment_count"],
             "excess_days_each": structural[0]["excess_days_each"]}
            if structural else None),
        "same_stage": bool(structural and structural[0]["step"] == longest["step"]),
        "load_sensitive_stages": [p["step"] for p in load_p],
    }


def analyse(path, as_of=None):
    CUTOFF.clear()
    columns, rows = load(path, as_of)
    if AS_OF is None:
        raise Refusal("None of the stage dates could be read, so there is nothing "
                      "to time.")
    has_exit = "exit_reason" in columns
    steps = transitions(columns)
    integrity_report = integrity(rows, steps)

    clock = pass1_clock(rows, steps, has_exit)

    stuck = [s for s in clock if s.get("censoring")
             and s["censoring"]["arrived"] >= MIN_STEP
             and s["censoring"]["share_in_flight"] >= CENSOR_REFUSE]
    if stuck:
        raise Refusal(
            "Too much of this file is still in flight to time it: "
            + "; ".join(f"{s['step']} has {s['censoring']['in_flight']:,} of "
                        f"{s['censoring']['arrived']:,} arrivals from the last "
                        f"{s['horizon_days']} days still open "
                        f"({s['censoring']['share_in_flight']:.0%})" for s in stuck)
            + f". Above {CENSOR_REFUSE:.0%}, the people who have had time to finish "
            "are too few and too early to stand for the rest. Export a longer "
            "period, or one that ends a full cycle before today.")
    if not any(s.get("conclusive") for s in clock):
        raise Refusal(
            f"No step has {MIN_STEP} or more waits old enough to time fairly, so "
            "there is no stage median worth reporting. Export a longer period.")

    peak, monthly = peak_months(rows)
    concentration = pass2_concentration(rows, clock)
    load_report = pass3_load(rows, clock, peak)
    confounds = pass4_confounds(rows, concentration)
    confirmed = [c for c in confounds if c["survives_all"]]
    structural = pass5_size(concentration, confirmed)
    load_p = load_prizes(load_report)

    return {
        "meta": {
            "skill": "time-to-hire-analyst",
            "skill_version": SKILL_VERSION,
            "funnel_profile": PROFILE_NAME,
            "funnel_label": PROFILE["label"],
            "stages": STAGES,
            "rows_analysed": len(rows),
            "source_file": os.path.basename(path),
            "as_of": AS_OF.isoformat(),
            "exit_reason_present": has_exit,
            "ingest": dict(INGEST),
        },
        "headline": headline(clock, concentration, structural, load_p),
        "end_to_end": end_to_end(rows),
        "clock": clock,
        "integrity": integrity_report,
        "monthly_volume": monthly,
        "concentration": concentration,
        "load": load_report,
        "confounds": confounds,
        "prizes": {"structural": structural, "load": load_p},
        "discarded": [
            {"step": c["step"], "dimension": c["dimension"],
             "segments": c["segments"], "killed_by": c["killed_by"],
             "reads": (f"A longer wait at {c['step']} for these {c['dimension']} "
                       f"values did not survive holding "
                       f"{', '.join(c['killed_by'])} constant, so it is reported "
                       f"as explained by {', '.join(c['killed_by'])} rather than "
                       f"as a {c['dimension']} problem.")}
            for c in confounds if not c["survives_all"] and c["killed_by"]
        ],
    }


# --------------------------------------------------------------- report

def _d(x):
    """Days as a reader says them: 4, 6.7, never 4.0 or 6.67."""
    if x is None:
        return "-"
    x = round(float(x), 1)
    return str(int(x)) if x == int(x) else f"{x:.1f}"


def _pct(x):
    return "-" if x is None else f"{x:.0%}"


def render_md(report):
    """The report a person reads. Every figure is copied from the JSON; nothing
    here computes anything, so the two can never disagree."""
    m, h, e2e = report["meta"], report["headline"], report["end_to_end"]
    out = [f"# Where the hiring time goes",
           "",
           f"{m['rows_analysed']:,} applications, {m['funnel_label'].lower()} "
           f"({' > '.join(m['stages'])}), export ending {m['as_of']}. "
           f"time-to-hire-analyst {m['skill_version']}.",
           ""]

    longest = h.get("stage_holding_most_time")
    conc = h.get("stage_with_concentrated_delay")
    out += ["## The answer", ""]
    if longest:
        out.append(f"- **Most of the calendar:** {longest['step']}, median "
                   f"{_d(longest['median_days'])} days, p90 {_d(longest['p90_days'])}, "
                   f"{_pct(longest['share_of_elapsed'])} of all the days candidates spent "
                   "waiting between stages.")
    if conc:
        out.append(f"- **The delay you can fix:** {conc['step']}, where "
                   f"{conc['segment_count']} {noun(conc['dimension'], conc['segment_count'])} hold candidates "
                   f"{_d(conc['excess_days_each'])} days longer than everyone else, after "
                   "the confound checks.")
    else:
        out.append("- **No concentrated delay survived its checks.** Where a stage is "
                   "slow, it is slow for everybody: that is the process, not a site.")
    if longest and conc:
        peak_too = longest["step"] in (h.get("load_sensitive_stages") or [])
        out.append("- These are the same stage." if h["same_stage"] else
                   "- These are **different stages**. The first is long for everybody"
                   + (" (and longer still in peak months)" if peak_too else "")
                   + "; the second is a local fix.")
    if h.get("load_sensitive_stages"):
        out.append("- **Only slow in peak months:** " + ", ".join(h["load_sensitive_stages"])
                   + ". That is capacity, not process.")
    out += ["", f"End to end, {e2e['n']:,} people applied early enough to be timed to "
            f"their {e2e['start_noun']}: median {_d(e2e['median'])} days, p90 "
            f"{_d(e2e['p90'])}. That is not the sum of the stage medians below, which "
            "describe larger groups.", ""]

    out += ["## The clock, stage by stage", "",
            "| Stage | Median days | p90 | Timed | Share of waiting days | Moved on | Left | Still open |",
            "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for st in report["clock"]:
        if not st.get("measurable"):
            out.append(f"| {st['step']} | not in the export | | | | | | |")
            continue
        c, w = st["censoring"], st["wait"]
        flag = "" if st.get("conclusive") else " (too few to time)"
        out.append(f"| {st['step']}{flag} | {_d(w['median'])} | {_d(w['p90'])} | "
                   f"{w['n']:,} | {_pct(st.get('share_of_elapsed'))} | {c['completed']:,} | "
                   f"{c['left']:,} | {c['in_flight'] + c['stale_open']:,} |")
    out += ["", "Timed means arrived early enough to have finished: each stage is "
            "timed over arrivals at least its horizon (three times its p90, two "
            "weeks minimum) before the export ends.", ""]

    notes = []
    for st in report["clock"]:
        c = st.get("censoring")
        if not c:
            continue
        if c["stale_open"]:
            notes.append(f"{c['stale_open']:,} applications at {st['step']} are still "
                         f"open with no movement for over {st['horizon_days']} days "
                         f"(median {_d(c['age_stale']['median'])}). Either they left "
                         "and nobody closed them, or they are stuck."
                         + (" Enough of them to make this stage's median optimistic."
                            if c["biases_median"] else ""))
        if c["skipped"] or c["undated"]:
            notes.append(f"{c['skipped'] + c['undated']:,} candidates passed "
                         f"{st['step']} without a date for it; they are not timed there.")
    if not m["exit_reason_present"]:
        notes.append("There is no exit_reason column, so a candidate who left cannot "
                     "be told from one still open. Still open counts both.")

    if report["prizes"]["structural"]:
        out += ["## Confirmed delays", ""]
        for p in report["prizes"]["structural"]:
            out.append(f"- {p['reads']} About {p['calendar_days_recovered']:,.0f} "
                       f"candidate-days in this export. Segments: "
                       f"{', '.join(p['segments'])}.")
        out.append("")
    if report["prizes"]["load"]:
        out += ["## Peak-season delays", ""]
        for p in report["prizes"]["load"]:
            out.append(f"- {p['reads']} Peak months: {', '.join(p['peak_months'])}.")
        out.append("")
    if report["discarded"]:
        out += ["## Ruled out", ""]
        for d in report["discarded"]:
            out.append(f"- {d['reads']} ({', '.join(d['segments'][:6])}"
                       + ("..." if len(d["segments"]) > 6 else "") + ")")
        out.append("")
    if notes:
        out += ["## About the data", ""] + [f"- {n}" for n in notes] + [""]
    ing = m.get("ingest", {})
    if ing.get("duplicate_rows_dropped") or ing.get("rows_without_id"):
        out += [f"- Dropped {ing.get('duplicate_rows_dropped', 0):,} repeated "
                f"application ids and {ing.get('rows_without_id', 0):,} rows without one.", ""]
    out += ["## What this does not claim", "",
            "That a shorter wait means more hires. Long waits and drop-off travel "
            "together, but how much of one becomes the other is a drop-off question "
            "(funnel-drop-off-analyst). And a timestamp shows waiting, not work: four "
            "days of checks and four days of nothing look the same.", ""]
    return "\n".join(out)


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

# The eight sites the generator gave scarce scheduling capacity (P2), and the
# five weak managers (P5). The manager set is here as a negative control: P5 is
# an attrition pattern with no timing component, so a cycle-time engine that
# "finds" it is finding noise.
SCARCE_SITES = {"LOC-03", "LOC-07", "LOC-14", "LOC-19", "LOC-25", "LOC-31", "LOC-36", "LOC-40"}
WEAK_MANAGERS = {"MGR-004", "MGR-012", "MGR-021", "MGR-029", "MGR-038"}


class Checks:
    def __init__(self):
        self.passed, self.failed = [], []

    def ok(self, label, condition, detail=""):
        (self.passed if condition else self.failed).append((label, detail))
        print(f"  {'PASS' if condition else 'FAIL'}  {label}" + (f"  [{detail}]" if detail else ""))


def datasets():
    """Every industry sample present. The same timing structure is planted in
    each, so running the suite against all of them is what shows the engine is
    finding the real structure rather than one file's quirks. An installed copy
    ships only the frontline file; the suite runs on whatever is there."""
    here = os.path.dirname(SAMPLE)
    found = [SAMPLE]
    for name in ("qsr", "logistics", "gig"):
        path = os.path.join(here, f"{name}_pipeline_sample.csv")
        if os.path.exists(path):
            found.append(path)
    return found


def step_by_index(report, index):
    return next((s for s in report["clock"] if s.get("index") == index), None)


def flagged_on(report, index, dim):
    for block in report["concentration"]:
        if block["index"] == index and dim in block["by"]:
            return {f["segment"] for f in block["by"][dim]["flagged"]}
    return set()


# What the generator planted, expressed as positions derived from the bound
# funnel rather than as stage names or literal indices. In the hire funnel the
# scheduling queue is the second transition; in the gig projection the two
# stages it spans are collapsed, and the clearance queue sits in the same
# position. Both are "the step after the first screen", which is what the
# assertion says. Writing 1 here instead would have been a hidden assumption
# that happens to hold for both files today.
QUEUE_STEP = 1                 # screened -> interview_scheduled / docs -> background_clear


def last_step_index():
    return len(STAGES) - 2     # onboarding_started -> started / -> activated


# What each file makes true, where the funnel shape decides it. Recorded per
# dataset rather than asserted uniformly, because the alternative is a suite
# that demands one file's quirk everywhere.
#
# headline_stages_coincide: whether the stage holding the most calendar time is
# ALSO the stage carrying the concentrated delay. In the seven-stage hire
# funnel they are different -- the queue is at scheduling, the bulk of the
# calendar sits in the run-up to a first shift -- and that gap is the reason
# this skill exists. The gig projection collapses two stages into the clearance
# step, so the same eight sites' queue becomes the largest block of calendar
# time as well, and the two answers land together. Both are correct readings of
# their file; a test that demanded the first everywhere would be asserting a
# quirk of the hire shape.
ORACLE = {
    "frontline": {"headline_stages_coincide": False},
    "qsr": {"headline_stages_coincide": False},
    "logistics": {"headline_stages_coincide": False},
    "gig": {"headline_stages_coincide": True},
}


def oracle_for(sample):
    stem = os.path.basename(sample).split("_")[0]
    if stem not in ORACLE:
        raise SystemExit(f"No planted answers recorded for {stem!r}. A dataset "
                         "with no oracle cannot be a regression test.")
    return ORACLE[stem]


def run_suite(sample):
    report = analyse(sample)
    c = Checks()
    o = oracle_for(sample)
    queue = step_by_index(report, QUEUE_STEP)
    final = step_by_index(report, last_step_index())

    print(f"\nFunnel bound: {report['meta']['funnel_profile']} "
          f"({len(STAGES)} stages, {report['meta']['rows_analysed']:,} rows)")

    print(f"\nA  The scheduling queue is where site-level delay lives")
    sites = flagged_on(report, QUEUE_STEP, "location_id")
    c.ok("at least seven of the eight scarce-capacity sites flagged",
         len(sites & SCARCE_SITES) >= 7, f"found {len(sites & SCARCE_SITES)}/8")
    c.ok("no site flagged that was not scarce",
         not (sites - SCARCE_SITES), ",".join(sorted(sites - SCARCE_SITES)) or "none")

    print(f"\nB  And it lives there and nowhere else")
    # The discriminating claim. A weaker engine reports the same sites as slow
    # at every stage, because slow sites are slow. The generator only lengthened
    # one queue, so a correct engine flags them at one step.
    other_steps = [s["index"] for s in report["clock"]
                   if s.get("conclusive") and s["index"] != QUEUE_STEP]
    leaked = {i: flagged_on(report, i, "location_id") & SCARCE_SITES for i in other_steps}
    worst = max((len(v) for v in leaked.values()), default=0)
    c.ok("scarce sites are not flagged across the other stages",
         worst <= 2, f"worst other stage flags {worst}/8")
    c.ok("the queue step flags more scarce sites than any other stage",
         len(sites & SCARCE_SITES) > worst,
         f"{len(sites & SCARCE_SITES)} vs {worst}")

    print(f"\nC  The site effect is real, not a role or source mix")
    confirmed = [f for f in report["confounds"]
                 if f["index"] == QUEUE_STEP and f["dimension"] == "location_id"]
    c.ok("a location finding was raised at the queue step", bool(confirmed))
    if confirmed:
        f = confirmed[0]
        c.ok("it survived every confound it could be tested against",
             f["survives_all"], "killed by " + ",".join(f["killed_by"]) if f["killed_by"] else "survived")
        tested = [k for k, v in f["checks"].items() if v.get("testable")]
        c.ok("it was tested against role and source", {"role", "source"} <= set(tested),
             ",".join(sorted(tested)))

    print(f"\nD  Peak load lengthens the final stage, not the early ones")
    c.ok("a peak period was detected from the file", report["load"]["detected"],
         str(report["load"].get("peak_months")))
    load_steps = {s["index"]: s for s in report["load"]["steps"]}
    if final and final["index"] in load_steps:
        fl = load_steps[final["index"]]
        c.ok(f"the final stage is load-sensitive", fl["load_sensitive"],
             f"peak {fl['peak']['median']} vs off-peak {fl['off_peak']['median']}")
        early = [s for i, s in load_steps.items() if i < QUEUE_STEP]
        c.ok("the first stage is not load-sensitive",
             all(not s["load_sensitive"] for s in early),
             ",".join(f"{s['step']}={s['ratio']}" for s in early) or "none testable")
        if early:
            # Compared in days, not as a ratio. A first stage that moves from a
            # one-day median to a two-day one has the larger ratio of anything
            # in the file and the smallest real effect; comparing ratios here
            # would reintroduce exactly the artefact the engine's load guard
            # exists to suppress.
            worst_early = max((s["excess_days"] or 0) for s in early)
            c.ok("the final stage stretches more under load than the first does, in days",
                 (fl["excess_days"] or 0) > worst_early,
                 f"{fl['excess_days']}d vs {worst_early}d")

    print(f"\nE  Structural and load delay are told apart, not summed")
    kinds = {p["kind"] for p in report["prizes"]["structural"]} | \
            {p["kind"] for p in report["prizes"]["load"]}
    c.ok("both a structural and a load prize are reported", kinds == {"structural", "load"},
         ",".join(sorted(kinds)) or "none")
    c.ok("the two are attributed to different stages",
         bool(report["prizes"]["structural"]) and bool(report["prizes"]["load"])
         and report["prizes"]["structural"][0]["step"] != report["prizes"]["load"][0]["step"],
         f"{report['prizes']['structural'][0]['step'] if report['prizes']['structural'] else '-'}"
         f" / {report['prizes']['load'][0]['step'] if report['prizes']['load'] else '-'}")

    print(f"\nF  The headline does not collapse to one number")
    h = report["headline"]
    c.ok("a stage holding the most calendar time is named",
         bool(h["stage_holding_most_time"]),
         (h["stage_holding_most_time"] or {}).get("step", ""))
    c.ok("a concentrated delay is named separately",
         bool(h["stage_with_concentrated_delay"]),
         (h["stage_with_concentrated_delay"] or {}).get("step", ""))
    # The reason the skill exists: in the hire funnel, the stage carrying the
    # most calendar time is not the stage you can actually fix. Whether the two
    # coincide is a property of the funnel shape, so it is read from the oracle
    # rather than demanded everywhere.
    c.ok("the two coincide exactly where the funnel shape says they should",
         h["same_stage"] == o["headline_stages_coincide"],
         f"same_stage={h['same_stage']}, expected {o['headline_stages_coincide']}")

    print(f"\nG  Managers with poor retention are not reported as slow")
    mgr_hits = set()
    for block in report["concentration"]:
        if "hiring_manager_id" in block["by"]:
            mgr_hits |= {f["segment"] for f in block["by"]["hiring_manager_id"]["flagged"]}
    c.ok("no timing claim made about the weak-retention managers",
         not (mgr_hits & WEAK_MANAGERS), ",".join(sorted(mgr_hits & WEAK_MANAGERS)) or "none")

    print(f"\nH  Nobody who left is counted as waiting")
    parts = ("completed", "skipped", "undated", "left", "in_flight", "stale_open")
    c.ok("at every step, every arrival is accounted for exactly once",
         all(sum(s["censoring"][k] for k in parts) == s["censoring"]["arrived"]
             for s in report["clock"] if s.get("measurable")))
    # Every application in these samples is either started or closed with an
    # exit reason. The draft of this engine counted the closed ones as still
    # waiting -- 8,412 people "queuing" 270 days on the retail file -- and would
    # have refused any real export that loses most applicants at the first step.
    c.ok("closed applications are counted as left, not in flight",
         all(s["censoring"]["in_flight"] == 0 and s["censoring"]["stale_open"] == 0
             for s in report["clock"] if s.get("measurable")),
         str(max(s["censoring"]["in_flight"] + s["censoring"]["stale_open"]
                 for s in report["clock"] if s.get("measurable"))))
    first = report["clock"][0]["censoring"]
    c.ok("the first step's losses are reported as left",
         first["left"] > 0, f"{first['left']:,} left of {first['arrived']:,}")
    c.ok("every step is timed only over arrivals old enough to have finished",
         all(s["censoring"]["timed_arrivals_through"] and s["horizon_days"] >= HORIZON_MIN
             for s in report["clock"] if s.get("measurable")))

    print(f"\nI  End-to-end is measured, not summed from medians")
    e2e = report["end_to_end"]
    conclusive = [s for s in report["clock"] if s.get("conclusive")]
    stage_ns = [s["wait"]["n"] for s in conclusive]
    c.ok("end-to-end median is reported over people who finished", e2e["n"] > 0, f"n={e2e['n']:,}")
    # Each stage median is computed over everyone who cleared that stage; the
    # end-to-end median only over the few who cleared all of them. The two are
    # answers about different populations, which is why adding the stage
    # medians together produces a number describing nobody. Their sum may
    # happen to land on the end-to-end figure -- in three of these four files
    # it does -- so the population gap is what the suite asserts, not a
    # difference between the totals.
    c.ok("end-to-end covers a small fraction of the population the first stage does",
         bool(stage_ns) and e2e["n"] < max(stage_ns) / 2,
         f"e2e n={e2e['n']:,} vs widest stage n={max(stage_ns):,}")
    final_step = step_by_index(report, last_step_index())
    c.ok("everyone who finished is counted, and only those early enough are timed",
         final_step is not None and e2e["finished"] == final_step["censoring"]["completed"]
         and e2e["n"] <= e2e["finished"],
         f"timed {e2e['n']:,} of {e2e['finished']:,} finished" if final_step else "no final step")

    print(f"\nJ  The readable report says what the JSON says")
    md = render_md(report)
    hl = report["headline"]
    c.ok("it names the stage holding the most calendar",
         hl["stage_holding_most_time"]["step"] in md)
    c.ok("it names the concentrated delay when there is one",
         not hl["stage_with_concentrated_delay"]
         or hl["stage_with_concentrated_delay"]["step"] in md.split("## The clock")[0])

    print(f"\n  {len(c.passed)} passed, {len(c.failed)} failed")
    return len(c.passed), len(c.failed)


# ------------------------------------------------------------ refusal tests

def _tmp_csv(rows, columns):
    import tempfile
    fh = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="")
    writer = csv.DictWriter(fh, fieldnames=columns)
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
    print(f"\n{'=' * 62}\nrefusals and guards\n{'=' * 62}")
    c = Checks()
    columns, rows = _read_sample()

    path = _tmp_csv([dict(r, candidate_email="x@y.z") for r in rows[:800]],
                    columns + ["candidate_email"])
    try:
        analyse(path)
        c.ok("refuses a nominative column", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a nominative column", "nominative" in str(stop).lower())
    os.unlink(path)

    path = _tmp_csv(rows[:100], columns)
    try:
        analyse(path)
        c.ok("refuses a file too thin to time", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file too thin to time", "usable rows" in str(stop))
    os.unlink(path)

    # Timestamps that contradict the stage order. Swapping two columns on a
    # tenth of the rows is the shape of a real mapping error, and the engine
    # must stop rather than quietly drop them.
    broken = []
    for i, row in enumerate(rows):
        row = dict(row)
        if i % 10 == 0 and row.get("screened_at") and row.get("applied_at"):
            row["applied_at"], row["screened_at"] = row["screened_at"], row["applied_at"]
        broken.append(row)
    path = _tmp_csv(broken, columns)
    try:
        analyse(path)
        c.ok("refuses timestamps that contradict the stage order", False, "it ran")
    except Refusal as stop:
        c.ok("refuses timestamps that contradict the stage order",
             "contradict the stage order" in str(stop))
    os.unlink(path)

    # An export cut too close to today: most of the people who arrived at a
    # step did so in its last fortnight, are still open, and only the fast
    # ones have moved on.
    as_of = date(2026, 6, 30)
    fresh = []
    for i in range(1500):
        applied = as_of - timedelta(days=(i % 10))
        row = {k: "" for k in columns}
        row.update(application_id=f"N{i:05d}", location_id=f"LOC-{i % 9:02d}",
                   role="Associate", source="jobboard_a", stage_reached="applied",
                   applied_at=applied.isoformat())
        if i % 4 == 0:
            row.update(stage_reached="screened",
                       screened_at=(applied + timedelta(days=1)).isoformat())
        fresh.append(row)
    for i in range(300):
        applied = as_of - timedelta(days=60 + i % 30)
        row = {k: "" for k in columns}
        row.update(application_id=f"O{i:05d}", location_id=f"LOC-{i % 9:02d}",
                   role="Associate", source="jobboard_a", stage_reached="screened",
                   applied_at=applied.isoformat(),
                   screened_at=(applied + timedelta(days=2)).isoformat())
        fresh.append(row)
    path = _tmp_csv(fresh, columns)
    try:
        analyse(path)
        c.ok("refuses a file still mostly in flight", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file still mostly in flight", "still in flight" in str(stop), str(stop)[:80])
    os.unlink(path)

    # The same shape, but every non-mover closed with an exit reason. Losing
    # most applicants at the first step is normal; it is not a queue.
    for row in fresh:
        if not row["screened_at"]:
            row["exit_reason"] = "withdrew"
    path = _tmp_csv(fresh, columns)
    try:
        r = analyse(path)
        st = r["clock"][0]["censoring"]
        c.ok("a funnel that loses most people at step one is not refused",
             st["in_flight"] == 0 and st["left"] == 1125, f"left={st['left']}")
    except Refusal as stop:
        c.ok("a funnel that loses most people at step one is not refused", False, str(stop)[:80])
    os.unlink(path)

    # A raw status-history log: one row per status change.
    log = []
    for r in rows[:1500]:
        for stage, col in zip(STAGES, STAGE_DATE):
            if r.get(col):
                log.append(dict(r, stage_reached=stage))
    path = _tmp_csv(log, columns)
    try:
        analyse(path)
        c.ok("refuses a status-history log", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a status-history log", "status-history log" in str(stop))
    os.unlink(path)

    # Spreadsheet serial numbers where dates should be.
    serial = [dict(r) for r in rows[:2000]]
    for r in serial[::20]:
        if r.get("screened_at"):
            r["screened_at"] = "46021"
    path = _tmp_csv(serial, columns)
    try:
        analyse(path)
        c.ok("refuses dates it cannot read", False, "it ran")
    except Refusal as stop:
        c.ok("refuses dates it cannot read", "not dates" in str(stop))
    os.unlink(path)

    # Slash dates are read the way the file proves, and never guessed.
    def reformat(rs, fmt):
        out = []
        for r in rs:
            r = dict(r)
            for col in STAGE_DATE:
                d = parse_date(r.get(col)) if r.get(col) else None
                if d:
                    r[col] = d.strftime(fmt) + ("T09:30:00-05:00" if fmt == "iso" else "")
            out.append(r)
        return out
    base = analyse(SAMPLE)
    for fmt, label in (("%d/%m/%Y", "day-first"), ("%m/%d/%Y", "month-first")):
        path = _tmp_csv(reformat(rows, fmt), columns)
        r = analyse(path)
        c.ok(f"{label} dates give the same answer as ISO dates",
             r["headline"] == base["headline"] and r["end_to_end"] == base["end_to_end"],
             r["meta"]["ingest"]["date_order"])
        os.unlink(path)
    early = [r for r in rows if (parse_date(r.get("applied_at")) or date.max).day <= 12]
    amb = reformat(early, "%d/%m/%Y")
    for r in amb:
        for col in STAGE_DATE:
            if r.get(col):
                dd, mm, yy = r[col].split("/")
                if int(dd) > 12:
                    r[col] = ""
    path = _tmp_csv(amb, columns)
    try:
        analyse(path)
        c.ok("refuses slash dates that could be read either way", False, "it ran")
    except Refusal as stop:
        c.ok("refuses slash dates that could be read either way", "3 April or 4 March" in str(stop))
    os.unlink(path)

    # Not UTF-8.
    import tempfile
    fh = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
    fh.write(("application_id,applied_at,stage_reached\nA1,2026-01-01,appliqu\xe9\n").encode("latin-1"))
    fh.close()
    try:
        analyse(fh.name)
        c.ok("refuses a file that is not UTF-8", False, "it ran")
    except Refusal as stop:
        c.ok("refuses a file that is not UTF-8", "UTF-8" in str(stop))
    os.unlink(fh.name)

    # A site effect that is pure noise. Shuffle the site labels: the planted
    # queue now belongs to no site in particular, and none may be flagged.
    import random
    rng = random.Random(7)
    labels = [r["location_id"] for r in rows]
    rng.shuffle(labels)
    null = [dict(r, location_id=l) for r, l in zip(rows, labels)]
    path = _tmp_csv(null, columns)
    r = analyse(path)
    hits = flagged_on(r, QUEUE_STEP, "location_id")
    c.ok("no site is flagged once the site labels are shuffled", not hits,
         ",".join(sorted(hits)) or "none")
    os.unlink(path)

    # A site effect that reverses inside each role (Simpson's paradox): the
    # flagged sites look slower only because they hire more of the slow role,
    # and within each role they are faster. It must not survive.
    step = {"index": 99, "from_col": "a_at", "to_col": "b_at"}
    d0 = date(2026, 1, 5)
    syn = []
    for role, site_days, rest_days, n_site, n_rest in (("A", 1, 2, 40, 200), ("B", 4, 5, 200, 40)):
        for k in range(n_site + n_rest):
            site = "S" if k < n_site else f"R{k % 5}"
            days = site_days if site == "S" else rest_days
            syn.append({"role": role, "location_id": site, "a_at": d0.isoformat(),
                        "b_at": (d0 + timedelta(days=days)).isoformat()})
    res = confound_check(syn, step, "location_id", ["S"], ["role"])["role"]
    c.ok("an effect that reverses within roles does not survive",
         res["testable"] and not res["survived"],
         f"raw {res.get('raw_excess_days')}, adjusted {res.get('adjusted_excess_days')}")

    # Stage vocabularies from both profiles in one file.
    mixed = [dict(r) for r in rows[:900]]
    for row in mixed[:200]:
        row["stage_reached"] = "background_clear"
    path = _tmp_csv(mixed, columns)
    try:
        analyse(path)
        c.ok("refuses mixed stage vocabularies", False, "it ran")
    except Refusal as stop:
        c.ok("refuses mixed stage vocabularies", "do not belong to it" in str(stop))
    os.unlink(path)

    print(f"\n  {len(c.passed)} passed, {len(c.failed)} failed")
    return len(c.passed), len(c.failed)


def run_tests():
    if not os.path.exists(SAMPLE):
        print(f"sample dataset not found at {SAMPLE}")
        return 1
    print(f"time-to-hire-analyst v{SKILL_VERSION}")
    print("Ground truth is the P2 (scarce scheduling capacity) and P7 (peak load)")
    print("patterns documented in data/generate.py, plus P5 as a negative control.")

    total_passed = total_failed = 0
    for path in datasets():
        print(f"\n{'=' * 62}\n{os.path.basename(path)}\n{'=' * 62}")
        p, f = run_suite(path)
        total_passed += p
        total_failed += f
    p, f = refusal_tests()
    total_passed += p
    total_failed += f

    print(f"\n{'=' * 62}")
    print(f"{total_passed} passed, {total_failed} failed"
          f"  ({len(datasets())} dataset(s) + refusals)")
    return 1 if total_failed else 0


# --------------------------------------------------------------- cli

def main():
    ap = argparse.ArgumentParser(description="Cycle-time engine.")
    ap.add_argument("--input", help="CSV mapped to the canonical schema")
    ap.add_argument("--out", help="write the JSON report here")
    ap.add_argument("--md", help="write the readable report here")
    ap.add_argument("--as-of", dest="as_of",
                    help="the day the export ends (YYYY-MM-DD); default: the latest date in the file")
    ap.add_argument("--demo", action="store_true", help="run on the bundled sample")
    ap.add_argument("--test", action="store_true", help="run the regression suite")
    args = ap.parse_args()

    if args.test:
        return run_tests()
    if args.demo:
        args.input = SAMPLE
    if not args.input:
        ap.error("one of --input, --demo or --test is required")

    as_of = None
    if args.as_of:
        try:
            as_of = date.fromisoformat(args.as_of)
        except ValueError:
            print(json.dumps({"refused": True, "reason": "--as-of must be YYYY-MM-DD."}))
            return EXIT_REFUSED
    try:
        report = analyse(args.input, as_of)
    except Refusal as stop:
        print(json.dumps({"refused": True, "reason": str(stop)}, indent=2))
        return EXIT_REFUSED
    except FileNotFoundError:
        print(json.dumps({"refused": True, "reason": f"No file at {args.input}."}))
        return EXIT_REFUSED
    except Exception as err:   # the engine's fault, never the reader's
        print(json.dumps({"failed": True, "reason": f"{type(err).__name__}: {err}"}))
        return EXIT_FAILED

    text = json.dumps(report, indent=2, default=str)
    md = render_md(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    if not args.out and not args.md:
        print(md if args.demo else text)
    else:
        print(f"report written ({report['meta']['rows_analysed']:,} rows, "
              f"skill v{SKILL_VERSION})")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
