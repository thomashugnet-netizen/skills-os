#!/usr/bin/env python3
"""
Pay competitiveness checker.

Places each posted hourly rate on the local wage ladder for the same
occupation, using the U.S. Bureau of Labor Statistics OEWS estimates bundled
in references/wages.csv, and says which postings are priced to stay open.

    python3 checker.py --postings postings.csv [--as-of 2026-10-19]
                       [--hours-per-week 30] [--uplift 3.5]
                       [--html report.html] [--json out.json]
    python3 checker.py --test

postings.csv  job_title, pay[, soc][, city, state | area][, site][, openings]
              pay is hourly ("17.25", "$17.25/hr", a range "16-18") or annual
              ("$38,000/yr", converted at 2,080 hours and said so).

The checker never guesses an occupation silently: a title maps to a code only
through references/occupations.json or a soc column you supply, and every
mapping is printed for you to confirm. Standard library only.
"""

import csv
import html
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")
POINTS = [(10, "p10"), (25, "p25"), (50, "median"), (75, "p75"), (90, "p90")]
THIN_EMPLOYMENT = 100      # below this many jobs in the area, the estimate is fragile
SPREAD_FLAG = 1.00         # same job, same metro, pay differing by this much per hour
EMAIL = re.compile(r"[^\s@]+@[a-z0-9-]+\.[a-z]", re.I)


class Refusal(Exception):
    """Input the checker will not read. The message says what to fix."""


# ------------------------------------------------------------------ data

def _norm(text):
    text = re.sub(r"['’`.]", "", (text or "").lower())
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def load_wages(wages_path=None, meta_path=None):
    wages_path = wages_path or os.path.join(REF, "wages.csv")
    meta_path = meta_path or os.path.join(os.path.dirname(wages_path), "wages_meta.json")
    table, areas = {}, {}
    with open(wages_path, encoding="utf-8", newline="") as fh:
        for r in csv.DictReader(fh):
            row = {k: (float(r[k]) if r.get(k) else None) for _, k in POINTS}
            row["mean"] = float(r["mean"]) if r.get("mean") else None
            row["employment"] = int(r["employment"]) if r.get("employment") else None
            table[(r["area_code"], r["soc"])] = row
            areas[r["area_code"]] = {"code": r["area_code"], "title": r["area_title"],
                                     "type": r.get("area_type", ""), "state": r.get("state", "")}
    meta = json.load(open(meta_path, encoding="utf-8"))
    return table, areas, meta


# Single words specific enough to match inside a longer title. Every other
# one-word alias ("crew", "guard", "cook", "server", "checker") matches only a
# title that is exactly that word: "Cleaning Crew" is not fast food work.
CONTAINABLE = {"cashier", "stocker", "dishwasher", "bartender", "janitor", "custodian", "housekeeper",
               "barista", "busser", "waiter", "waitress", "caregiver", "cna", "csr"}
# Words that change the job: a "Cashier Supervisor" is a supervisor, a
# "Delivery Driver Helper" is a helper. These go to confirmation, not to the
# occupation named in the rest of the title.
QUALIFIERS = {"supervisor", "lead", "manager", "helper", "assistant", "trainer", "trainee", "instructor",
              "head", "director", "coordinator", "engineer", "foreman"}


def load_occupations():
    data = json.load(open(os.path.join(REF, "occupations.json"), encoding="utf-8"))["occupations"]
    aliases = {}
    for code, o in data.items():
        for t in [o["title"]] + o["titles"]:
            aliases[_norm(t)] = code
    return data, aliases


STATES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
          "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC", "florida": "FL",
          "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
          "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
          "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
          "montana": "MT", "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
          "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", "ohio": "OH",
          "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
          "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
          "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
          "puerto rico": "PR", "guam": "GU", "virgin islands": "VI"}
CITY_ALIASES = {"nyc": "new york", "new york city": "new york", "honolulu": "urban honolulu",
                "boise": "boise city", "louisville jefferson county": "louisville"}


def _city(text):
    c = " " + _norm(text) + " "
    c = c.replace(" saint ", " st ").replace(" ft ", " fort ").replace(" mt ", " mount ")
    c = c.strip()
    return CITY_ALIASES.get(c, c)


def city_index(areas):
    """Principal cities of each metro, from its title: 'Dallas-Fort Worth-Arlington, TX'.
    Hyphens separate cities but also sit inside some names (Winston-Salem,
    Wilkes-Barre), so every run of consecutive parts is indexed. A metro that
    spans several states is marked so the match can be confirmed."""
    idx = defaultdict(set)
    multi = set()
    for code, a in areas.items():
        title = a["title"]
        if "," not in title:
            continue
        cities, states = title.rsplit(",", 1)
        states = [s.strip().upper() for s in re.split(r"[-\s]+", states) if s.strip()]
        if len(states) > 1:
            multi.add(code)
        for chunk in re.split(r"--|/", cities):
            parts = [p for p in chunk.split("-") if p.strip()]
            for i in range(len(parts)):
                for j in range(i + 1, min(len(parts), i + 3) + 1):
                    name = _city(" ".join(parts[i:j]))
                    for st in states:
                        idx[(name, st)].add(code)
    return idx, multi


# ------------------------------------------------------------------ input

class PayError(ValueError):
    """A pay value this posting cannot be placed with. The row is reported, the rest still run."""


UNITS = [  # checked against the words right after the number
    ("hour", r"^\s*(/\s*(h|hr|hrs|hour)\b|per\s+hour|an\s+hour|hourly|ph\b)"),
    ("year", r"^\s*(/\s*(y|yr|year)\b|per\s+(year|annum)|a\s+year|annual(ly)?\b|yearly|salary)"),
    ("week", r"^\s*(/\s*(wk|week)\b|per\s+week|a\s+week|weekly)"),
    ("month", r"^\s*(/\s*(mo|month)\b|per\s+month|a\s+month|monthly)"),
    ("day", r"^\s*(/\s*(day|shift)\b|per\s+(day|shift)|a\s+(day|shift)|daily)"),
]
AMOUNT = r"\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b)?"


def parse_pay(raw):
    """(low, high, note) as hourly figures, or PayError with the reason."""
    v = (raw or "").strip().lower()
    if not v:
        raise PayError("no pay: a posting without a number cannot be placed on the ladder")
    if re.search(r"\btips?\b|\bgratuit", v):
        raise PayError("a tipped wage: the base rate alone is not comparable with what the job pays")
    # the pay is the first amount that is not a bonus, a sign-on or an add-on
    m = None
    for cand in re.finditer(AMOUNT + r"(?:\s*(?:-|\u2013|to)\s*" + AMOUNT + r")?", v):
        before, after = v[:cand.start()], v[cand.end():cand.end() + 20]
        if re.search(r"\+\s*$", before) or re.search(r"^\s*(sign|bonus|referral|retention|shift diff|diff)", after):
            continue
        if re.search(r"^\s*(st|nd|rd|th)\b", after):
            continue                                    # "2nd shift"
        m = cand
        break
    if not m:
        raise PayError(f"'{raw}' has no pay rate in it")
    if re.search(r"\b(up\s+to|max(imum)?)\s*$", v[:m.start()]):
        raise PayError("a ceiling ('up to'), not a rate an applicant can count on; give the starting rate")

    def amount(num, k):
        return float(num.replace(",", "")) * (1000 if k else 1)

    low = amount(m.group(1), m.group(2))
    high = amount(m.group(3), m.group(4) or m.group(2)) if m.group(3) else low
    if m.group(4) and not m.group(2) and low < 1000:
        low = amount(m.group(1), "k")                  # "15-17k" is 15k to 17k
    tail = v[m.end():m.end() + 25]
    unit = next((u for u, pat in UNITS if re.search(pat, tail)), None)
    if unit is None and (m.group(2) or m.group(4)):
        unit = "year"
    note = ""
    if unit is None:
        if low > 300:
            unit, note = "year", "no unit given; read as an annual salary and converted at 2,080 hours"
        else:
            unit = "hour"
    if unit == "day":
        raise PayError("a day or shift rate: give the hourly rate, or the hours, to place it")
    divisor = {"hour": 1, "year": 2080, "week": 40, "month": 2080 / 12}[unit]
    if unit != "hour" and not note:
        note = {"year": "annual pay converted at 2,080 hours", "week": "weekly pay converted at 40 hours",
                "month": "monthly pay converted at 173 hours"}[unit]
    low, high = low / divisor, high / divisor
    if high < low:
        raise PayError(f"'{raw}' reads as a range whose top is below its bottom")
    if not 5 <= low <= 200:
        raise PayError(f"'{raw}' reads as ${low:,.2f} an hour, which is not a plausible frontline rate")
    return round(low, 2), round(high, 2), note


def resolve_area(r, areas, cities, row_no, multi_state=frozenset()):
    if r.get("area"):
        a = r["area"].strip()
        if a in areas:
            return a, "area code"
        if re.fullmatch(r"\d+(\.0+)?", a):
            # a spreadsheet drops leading zeros and adds ".0"
            n = int(float(a))
            for code in areas:
                if code.isdigit() and int(code) == n:
                    return code, "area code"
        by_title = [c for c, x in areas.items() if _norm(x["title"]) == _norm(a)]
        if by_title:
            return by_title[0], "area name"
        return None, f"area '{a}' is not in the wage table"
    city = _city(r.get("city", ""))
    state = (r.get("state") or "").strip()
    state = STATES.get(state.lower(), state.upper())
    if not city or not state:
        return None, "no city and state, and no area"
    if len(state) != 2:
        return None, f"state '{r.get('state')}' is not a state; use its 2-letter code"
    found = sorted(cities.get((city, state), []))
    if len(found) == 1:
        if found[0] in multi_state:
            return found[0], "principal city (the metro spans several states: confirm the city is in it)"
        return found[0], "principal city"
    if len(found) > 1:
        return None, f"{r.get('city')}, {state} sits in more than one area; give the area"
    return None, (f"{r.get('city')}, {state} is not a principal city of a metro area in the wage table. "
                  "Give the metro area it belongs to (the area column), so nothing is guessed")


def map_title(r, occupations, aliases):
    soc = (r.get("soc") or "").strip()
    if soc:
        if soc in occupations:
            return soc, "your SOC code"
        return None, f"SOC {soc} is not one of the occupations in the wage table"
    raw = r.get("job_title") or ""
    t = _norm(raw)
    if t in aliases:
        return aliases[t], "title"
    if re.search(r"[/&+]|\band\b", raw, re.I) and len(t.split()) > 1:
        return None, "the title names more than one job; split it or give the occupation"
    # the longest listed title contained in the posting title, as whole words
    best = None
    for alias, code in aliases.items():
        if " " not in alias and alias not in CONTAINABLE:
            continue
        if re.search(r"\b" + re.escape(alias) + r"\b", t) and (best is None or len(alias) > len(best[0])):
            best = (alias, code)
    if best:
        extra = (set(t.split()) & QUALIFIERS) - set(best[0].split())
        if extra:
            return None, (f"the title contains '{best[0]}' but also '{sorted(extra)[0]}', which usually "
                          "means a different occupation; confirm it or give the SOC code")
        return best[1], f"title contains '{best[0]}'"
    return None, "title not recognised; add a soc column or confirm the occupation"


def load_postings(path):
    if not os.path.exists(path):
        raise Refusal(f"no file at {path}.")
    try:
        text = open(path, encoding="utf-8-sig").read()
    except UnicodeDecodeError:
        text = open(path, encoding="cp1252").read()
    reader = csv.DictReader(text.splitlines())
    cols = [(c or "").strip().lower() for c in (reader.fieldnames or [])]
    for c in ("job_title", "pay"):
        if c not in cols:
            raise Refusal(f"postings file is missing column '{c}'.")
    rows = []
    for i, raw in enumerate(reader, start=2):
        if None in raw:
            raise Refusal(f"postings row {i} has more values than columns; quote any field containing a comma.")
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        if not any(r.values()):
            continue
        if any(EMAIL.search(v) for v in r.values()):
            raise Refusal(f"postings row {i} contains an email address. Postings need no contact details.")
        r["_row"] = i
        rows.append(r)
    if not rows:
        raise Refusal("the postings file has no rows.")
    return rows


# ----------------------------------------------------------------- analysis

def percentile_of(pay, w):
    """Where a rate sits on the published ladder, by straight lines between points."""
    pts = [(p, w[k]) for p, k in POINTS if w.get(k) is not None]
    if len(pts) < 2:
        return None, "too few published points"
    if pay < pts[0][1]:
        return pts[0][0] - 0.1, f"below the {ordinal(pts[0][0])}"
    if pay > pts[-1][1]:
        return pts[-1][0] + 0.1, f"above the {ordinal(pts[-1][0])}"
    # a rate equal to a published point sits at the highest point with that value:
    # where the 10th and the 25th are both $15.61, $15.61 is at the 25th, not the 10th
    equal = [p for p, v in pts if v == pay]
    if equal:
        return float(max(equal)), f"at the {ordinal(max(equal))}"
    for (p1, v1), (p2, v2) in zip(pts, pts[1:]):
        if v1 < pay < v2:
            pos = p1 + (pay - v1) / (v2 - v1) * (p2 - p1)
            return pos, f"about the {ordinal(int(pos))}"
    return None, "outside the published range"


def ordinal(n):
    n = int(round(n))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def band(pos):
    if pos is None:
        return "unknown"
    if pos < 10:
        return "bottom 10%"
    if pos < 25:
        return "below market"
    if pos < 50:
        return "under the median"
    if pos < 75:
        return "at or above the median"
    return "top quarter"


def months_between(a, b):
    return (b.year - a.year) * 12 + (b.month - a.month)


def analyse(postings_path, as_of=None, hours_per_week=30.0, uplift=None, wages_path=None):
    table, areas, meta = load_wages(wages_path)
    occupations, aliases = load_occupations()
    cities, multi_state = city_index(areas)
    rows = load_postings(postings_path)
    today = as_of or date.today()
    ref = date.fromisoformat(meta.get("reference_date") or "2025-05-15")
    if not 1 <= hours_per_week <= 80:
        raise Refusal(f"{hours_per_week:g} hours a week is not a working week; give 1 to 80.")
    if uplift is not None and not -20 <= uplift <= 50:
        raise Refusal(f"an uplift of {uplift:g}% is outside what a year or two of wage growth looks like.")
    if today < ref:
        raise Refusal(f"as-of {today} is before the data's reference period.")
    factor = 1 + (uplift or 0) / 100

    results, unresolved = [], []
    for r in rows:
        i = r["_row"]
        try:
            low, high, pay_note = parse_pay(r.get("pay"))
            pay_problem = None
        except PayError as exc:
            low = high = None
            pay_note, pay_problem = "", str(exc)
        soc, how_soc = map_title(r, occupations, aliases)
        area, how_area = resolve_area(r, areas, cities, i, multi_state)
        raw_open = (r.get("openings") or "").strip()
        openings = int(raw_open) if raw_open.isdigit() and int(raw_open) > 0 else 1
        if raw_open and not (raw_open.isdigit() and int(raw_open) > 0):
            pay_note = (pay_note + "; " if pay_note else "") + f"openings '{raw_open}' counted as 1"
        try:
            row_hours = float(r["hours_per_week"]) if r.get("hours_per_week") else hours_per_week
        except ValueError:
            row_hours = hours_per_week
        base = {"row": i, "job_title": r.get("job_title"), "site": r.get("site", ""),
                "openings": openings, "hours_per_week": row_hours,
                "pay_low": low, "pay_high": high, "pay_note": pay_note,
                "soc": soc, "occupation": occupations[soc]["title"] if soc else None, "mapped_by": how_soc,
                "area": area, "area_title": areas[area]["title"] if area else None, "area_by": how_area}
        if pay_problem or not soc or not area:
            base["problem"] = pay_problem or (how_soc if not soc else how_area)
            unresolved.append(base)
            continue
        w = table.get((area, soc))
        if not w or w.get("median") is None:
            base["problem"] = "BLS publishes no estimate for this occupation in this area"
            unresolved.append(base)
            continue
        w = {k: (v * factor if isinstance(v, float) and k != "employment" else v) for k, v in w.items()}
        pos, pos_text = percentile_of(low, w)
        if pos is None:
            base["problem"] = f"BLS publishes too few points for this occupation here ({pos_text})"
            unresolved.append(base)
            continue
        gap25 = round(max(0.0, (w["p25"] or w["median"]) - low), 2) if w.get("p25") else None
        gap50 = round(w["median"] - low, 2)
        hours_year = row_hours * 52
        base.update({
            "wages": {k: (round(v, 2) if isinstance(v, float) else v) for k, v in w.items()},
            "percentile": round(pos, 1), "percentile_text": pos_text, "band": band(pos),
            "gap_to_p25": gap25, "gap_to_median": gap50,
            "cost_to_p25_per_year": round((gap25 or 0) * hours_year * base["openings"], 0),
            "thin": w.get("employment") is not None and w["employment"] < THIN_EMPLOYMENT,
            "employment_withheld": w.get("employment") is None,
            "uplifted": uplift,
        })
        results.append(base)

    # the same job in the same metro, priced differently by your own sites
    spreads = []
    groups = defaultdict(list)
    for x in results:
        groups[(x["area"], x["soc"])].append(x)
    for (area, soc), xs in groups.items():
        lo, hi = min(xs, key=lambda x: x["pay_low"]), max(xs, key=lambda x: x["pay_low"])
        if hi["pay_low"] - lo["pay_low"] >= SPREAD_FLAG and (lo["site"] or lo["row"]) != (hi["site"] or hi["row"]):
            spreads.append({"area_title": areas[area]["title"], "occupation": occupations[soc]["title"],
                            "low": lo["pay_low"], "low_site": lo["site"] or lo["job_title"],
                            "high": hi["pay_low"], "high_site": hi["site"] or hi["job_title"],
                            "postings": len(xs)})

    below25 = [x for x in results if x["percentile"] is not None and x["percentile"] < 25]
    headline = {
        "as_of": today.isoformat(),
        "postings": len(rows),
        "placed": len(results),
        "unresolved": len(unresolved),
        "bottom_10": sum(1 for x in results if x["band"] == "bottom 10%"),
        "below_25th": len(below25),
        "openings_below_25th": sum(x["openings"] for x in below25),
        "cost_to_reach_25th_per_year": round(sum(x["cost_to_p25_per_year"] for x in below25), 0),
        "hours_per_week_assumed": hours_per_week,
        "data_period": meta.get("reference_period"),
        "data_age_months": months_between(ref, today),
        "uplift_percent": uplift,
    }
    return {"headline": headline, "results": results, "unresolved": unresolved,
            "spreads": spreads, "meta": meta}


# ------------------------------------------------------------------ output

def money(v):
    return "n/a" if v is None else f"${v:,.2f}"


def line(x):
    w = x["wages"]
    where = f"{x['site']}, " if x["site"] else ""
    rng = money(x["pay_low"]) + (f"-{money(x['pay_high'])}" if x["pay_high"] != x["pay_low"] else "")
    s = (f"{x['job_title']} ({where}{x['area_title']}): {rng}/h is {x['percentile_text']} percentile "
         f"for {x['occupation'].lower()} (median {money(w['median'])}, 25th {money(w['p25'])}).")
    if x["gap_to_p25"]:
        s += f" {money(x['gap_to_p25'])}/h short of the 25th."
    if x["thin"]:
        s += " Thin estimate: few jobs of this kind in the area."
    if x.get("employment_withheld"):
        s += " BLS withheld the job count for this one."
    if x.get("uplifted"):
        s += f" Market figures raised by your {x['uplifted']:g}% uplift."
    if x["pay_note"]:
        s += f" ({x['pay_note']})"
    return s


def text_report(r):
    h = r["headline"]
    out = [f"{h['placed']} of {h['postings']} postings placed on the local ladder.",
           f"Bottom 10%: {h['bottom_10']}. Below the 25th percentile: {h['below_25th']} "
           f"({h['openings_below_25th']} openings). Lifting them to the 25th: about "
           f"${h['cost_to_reach_25th_per_year']:,.0f} a year at {h['hours_per_week_assumed']:g} hours a week.",
           f"Wages: BLS OEWS {h['data_period']}, {h['data_age_months']} months old on {h['as_of']}"
           + (f", raised by your {h['uplift_percent']:g}% uplift." if h["uplift_percent"] else
              ". Not adjusted; market pay has likely moved since.")]
    for title, keep in (("Bottom 10%", lambda x: x["band"] == "bottom 10%"),
                        ("Below market (10th to 25th)", lambda x: x["band"] == "below market"),
                        ("Under the median", lambda x: x["band"] == "under the median"),
                        ("At or above the median", lambda x: x["band"] in ("at or above the median", "top quarter"))):
        xs = sorted([x for x in r["results"] if keep(x)], key=lambda x: x["percentile"])
        if xs:
            out.append("\n" + title)
            out += ["  - " + line(x) for x in xs]
    if r["spreads"]:
        out.append("\nSame job, same metro, different pay")
        for s in r["spreads"]:
            out.append(f"  - {s['occupation']} in {s['area_title']}: {money(s['low'])} at {s['low_site']} "
                       f"against {money(s['high'])} at {s['high_site']}.")
    if r["unresolved"]:
        out.append("\nNot placed, and why")
        for u in r["unresolved"]:
            out.append(f"  - row {u['row']} {u['job_title']}: {u['problem']}.")
    out.append("\nMappings used (confirm them)")
    for x in r["results"]:
        out.append(f"  - row {x['row']} {x['job_title']} -> {x['soc']} {x['occupation']} ({x['mapped_by']}); "
                   f"{x['area_title']} ({x['area_by']})")
    out.append("\nSource: U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics, "
               f"{h['data_period']}.")
    return "\n".join(out)


def html_report(r, path, title="Pay competitiveness"):
    e = html.escape
    h = r["headline"]
    rows = []
    for x in sorted(r["results"], key=lambda x: x["percentile"]):
        w = x["wages"]
        lo, hi = w["p10"] or w["median"], w["p90"] or w["median"]
        span = max(hi - lo, 0.01)
        pct = lambda v: max(0.0, min(100.0, (v - lo) / span * 100))
        marks = "".join(f'<span class="tick" style="left:{pct(w[k]):.1f}%"></span>'
                        for _, k in POINTS if w.get(k) is not None)
        cls = {"bottom 10%": "bad", "below market": "warn", "under the median": "mid"}.get(x["band"], "ok")
        rows.append(
            f"<tr><td><strong>{e(x['job_title'])}</strong><br><small>{e(x['site'] or '')} "
            f"{e(x['area_title'])}</small></td><td class='num'>{money(x['pay_low'])}</td>"
            f"<td class='ladder'><span class='track'>{marks}<span class='dot {cls}' style='left:{pct(x['pay_low']):.1f}%'>"
            f"</span></span><small>{money(lo)} 10th, {money(w['median'])} median, {money(hi)} 90th"
            f"{' (uplifted ' + format(x['uplifted'], 'g') + '%)' if x.get('uplifted') else ''}</small></td>"
            f"<td class='{cls}'>{e(x['percentile_text'])}</td>"
            f"<td class='num'>{money(x['gap_to_p25']) if x['gap_to_p25'] else '-'}</td></tr>")
    tiles = [("Bottom 10%", h["bottom_10"]), ("Below the 25th", h["below_25th"]),
             ("Openings below the 25th", h["openings_below_25th"]),
             ("To reach the 25th, per year", f"${h['cost_to_reach_25th_per_year']:,.0f}")]
    tiles_html = "".join(f'<div class="tile"><div class="n">{e(str(v))}</div><div class="l">{e(k)}</div></div>'
                         for k, v in tiles)
    extra = ""
    if r["spreads"]:
        extra += "<h2>Same job, same metro, different pay</h2><ul>" + "".join(
            f"<li>{e(s['occupation'])} in {e(s['area_title'])}: {money(s['low'])} at {e(s['low_site'])} "
            f"against {money(s['high'])} at {e(s['high_site'])}</li>" for s in r["spreads"]) + "</ul>"
    if r["unresolved"]:
        extra += "<h2>Not placed</h2><ul>" + "".join(
            f"<li>{e(u['job_title'])}: {e(u['problem'])}</li>" for u in r["unresolved"]) + "</ul>"
    age = (f"raised by your {h['uplift_percent']:g}% uplift" if h["uplift_percent"]
           else "not adjusted: market pay has likely moved since")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mute:#6b6a65;--line:#e4e1d8;--card:#fff;--bad:#c8473b;--warn:#b7791f;--ok:#2f7a4a;--track:#ece9e1}}
@media (prefers-color-scheme:dark){{:root{{--bg:#171715;--fg:#efede6;--mute:#a3a198;--line:#33322e;--card:#201f1c;
--bad:#ef7d70;--warn:#e0a84a;--ok:#6cc08b;--track:#2c2b28}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 48px}}
h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:16px;margin:28px 0 8px}}
.sub{{color:var(--mute);margin:0 0 16px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.tile .n{{font-size:26px;font-weight:650}} .tile .l{{color:var(--mute);font-size:13px}}
.wrap{{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}}
table{{border-collapse:collapse;width:100%;min-width:760px;font-size:13px}}
th,td{{padding:10px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}
th{{color:var(--mute);font-weight:600}} .num{{text-align:right;white-space:nowrap}}
td.ladder{{width:38%}} .track{{display:block;position:relative;height:10px;background:var(--track);border-radius:5px;margin:6px 0 4px}}
.tick{{position:absolute;top:-2px;width:1px;height:14px;background:var(--mute)}}
.dot{{position:absolute;top:-4px;width:18px;height:18px;margin-left:-9px;border-radius:50%;border:2px solid var(--card)}}
.dot.bad{{background:var(--bad)}} .dot.warn{{background:var(--warn)}} .dot.mid{{background:var(--mute)}} .dot.ok{{background:var(--ok)}}
td.bad{{color:var(--bad);font-weight:650}} td.warn{{color:var(--warn);font-weight:650}} td.mid{{color:var(--fg)}} td.ok{{color:var(--ok)}}
small{{color:var(--mute)}} ul{{padding-left:20px}}
.foot{{color:var(--mute);font-size:12px;margin-top:28px}}
</style></head><body><main>
<h1>{e(title)}</h1>
<p class="sub">{h['placed']} of {h['postings']} postings placed. Wages: BLS OEWS {e(h['data_period'] or '')},
{h['data_age_months']} months old on {e(h['as_of'])}, {e(age)}.</p>
<div class="tiles">{tiles_html}</div>
<h2>Every posting on its local ladder</h2>
<div class="wrap"><table><tr><th>Posting</th><th class="num">Pay</th><th>Local ladder, same occupation</th>
<th>Position</th><th class="num">Short of 25th</th></tr>{''.join(rows)}</table></div>
{extra}
<p class="foot">Source: U.S. Bureau of Labor Statistics, Occupational Employment and Wage Statistics,
{e(h['data_period'] or '')}. Cost to reach the 25th percentile assumes {h['hours_per_week_assumed']:g} hours a week per opening.
Computed by scripts/checker.py. Not legal advice and not a pay recommendation.</p>
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

    import tempfile, shutil
    tmp = tempfile.mkdtemp(prefix="pay-test-")
    fw = os.path.join(FIXTURES, "wages_fixture.csv")
    as_of = date(2026, 10, 19)

    def write(name, text):
        p = os.path.join(tmp, name)
        open(p, "w", encoding="utf-8").write(text)
        return p

    H = "job_title,pay,city,state,site,openings\n"
    # ladder: fixture area 11111 (Alpha-Beta, TX), cashier p10 10, p25 12, median 14, p75 16, p90 20
    r = analyse(write("a.csv", H + "Cashier,9.50,Alpha,TX,S1,2\nCashier,12,Beta,TX,S2,1\n"
                      "Cashier,13,Alpha,TX,S3,1\nCashier,15,Alpha,TX,S4,1\nCashier,21,Alpha,TX,S5,1\n"),
                as_of=as_of, wages_path=fw)
    pos = {x["site"]: x for x in r["results"]}
    check("ladder: below the 10th", pos["S1"]["band"] == "bottom 10%")
    check("ladder: exactly the 25th is not below market", pos["S2"]["percentile"] == 25 and pos["S2"]["band"] == "under the median")
    check("ladder: 13 is the 37.5th, by straight line", pos["S3"]["percentile"] == 37.5)
    check("ladder: 15 is the 62.5th", pos["S4"]["percentile"] == 62.5)
    check("ladder: above the 90th", pos["S5"]["band"] == "top quarter" and "above" in pos["S5"]["percentile_text"])
    check("gap: S1 is 2.50 short of the 25th", pos["S1"]["gap_to_p25"] == 2.5)
    check("cost: S1 two openings at 30h a week", pos["S1"]["cost_to_p25_per_year"] == round(2.5 * 30 * 52 * 2))
    check("headline: one bottom 10%, one below the 25th", r["headline"]["bottom_10"] == 1 and r["headline"]["below_25th"] == 1)
    check("headline: openings below the 25th counts openings", r["headline"]["openings_below_25th"] == 2)
    check("spread: same job, same metro, 9.50 to 21", len(r["spreads"]) == 1 and r["spreads"][0]["postings"] == 5)
    check("age: May 2025 data is 17 months old on 2026-10-19", r["headline"]["data_age_months"] == 17)

    u = analyse(write("u.csv", H + "Cashier,12,Alpha,TX,S1,1\n"), as_of=as_of, uplift=10, wages_path=fw)
    check("uplift: 10% moves the 25th to 13.20, so 12 is now below market",
          u["results"][0]["wages"]["p25"] == 13.2 and u["results"][0]["band"] == "below market")

    p = analyse(write("p.csv", H + "Cashier,$12.50/hr,Alpha,TX,A,1\nCashier,12-14,Alpha,TX,B,1\n"
                      "Cashier,\"$27,040/yr\",Alpha,TX,C,1\nCashier,27040,Alpha,TX,D,1\n"), as_of=as_of, wages_path=fw)
    pp = {x["site"]: x for x in p["results"]}
    check("pay: '$12.50/hr' reads as 12.50", pp["A"]["pay_low"] == 12.5)
    check("pay: a range is placed on its low end", pp["B"]["pay_low"] == 12 and pp["B"]["pay_high"] == 14)
    check("pay: an annual salary converts at 2,080 hours and says so",
          pp["C"]["pay_low"] == 13 and "2,080" in pp["C"]["pay_note"])
    check("pay: a bare 27040 is a salary", pp["D"]["pay_low"] == 13)

    m = analyse(write("m.csv", "job_title,pay,city,state,soc\nOvernight Stocker - Store 214,15,Alpha,TX,\n"
                      "Crew Member,13,Alpha,TX,\nUnicorn Wrangler,15,Alpha,TX,\nUnicorn Wrangler,15,Alpha,TX,53-7065\n"
                      "Cashier,13,Gamma,TX,\nCashier,13,Alpha,OK,\n"), as_of=as_of, wages_path=fw)
    by_row = {x["row"]: x for x in m["results"] + m["unresolved"]}
    check("titles: the longest listed title inside a posting title wins", by_row[2]["soc"] == "53-7065")
    check("titles: crew member maps to fast food and counter workers", by_row[3]["soc"] == "35-3023")
    check("titles: an unknown title is not guessed", by_row[4]["soc"] is None and "not recognised" in by_row[4]["problem"])
    check("titles: your SOC code wins", by_row[5]["soc"] == "53-7065")
    check("areas: a city that is not a principal city is not guessed", "not a principal city" in by_row[6]["problem"])
    check("areas: the right city in the wrong state is not matched", by_row[7]["area"] is None)
    a = analyse(write("ar.csv", "job_title,pay,area\nCashier,13,11111\nCashier,13,\"Alpha-Beta, TX\"\n"),
                as_of=as_of, wages_path=fw)
    check("areas: by code and by exact name", len(a["results"]) == 2)
    n = analyse(write("n.csv", H + "Dishwasher,13,Alpha,TX,S1,1\nStocker,15,Alpha,TX,S2,1\n"),
                as_of=as_of, wages_path=fw)
    check("data: no published estimate is said, not filled in",
          any("no estimate" in u["problem"] for u in n["unresolved"]))
    check("data: a thin estimate is flagged", any(x["thin"] for x in n["results"]))

    for name, text, expect in (("e1.csv", "job_title,city\nCashier,Alpha\n", "missing column"),
                               ("e4.csv", "job_title,pay,contact\nCashier,13,jane@acme.com\n", "email"),
                               ("e5.csv", "job_title,pay,note\nCashier,13,late, see manager\n", "more values")):
        try:
            analyse(write(name, text), as_of=as_of, wages_path=fw)
            check(f"refuses {name}", False)
        except Refusal as exc:
            check(f"refuses {name} ({expect})", expect in str(exc))

    # pay text found in the wild: each one was read wrongly once
    cases = [("$15/hr + 401k", (15, 15, "")), ("$15/hr, 40 hrs/week", (15, 15, "")),
             ("$16/hr annual bonus", (16, 16, "")), ("$15/hr, raise after a year", (15, 15, "")),
             ("$1,200/week", (30, 30, "weekly")), ("$2,500/month", (14.42, 14.42, "monthly")),
             ("$16/hr + $500 bonus", (16, 16, "")), ("$15/hour 2nd shift", (15, 15, "")),
             ("$15/hr + $2 night diff", (15, 15, "")), ("$62,400/yr ($30/hr)", (30, 30, "annual")),
             ("Up to $1,000 sign-on, $15/hr", (15, 15, "")), ("15.5 - 17.25 per hour", (15.5, 17.25, "")),
             ("$15 to $17", (15, 17, "")), ("15-17k", (7.21, 8.17, "annual")), ("38000", (18.27, 18.27, "no unit"))]
    for text, (lo, hi, note) in cases:
        try:
            got = parse_pay(text)
            check(f"pay '{text}'", got[0] == lo and got[1] == hi and (note in got[2] if note else got[2] == ""))
        except PayError as exc:
            check(f"pay '{text}' ({exc})", False)
    for text, why in (("Up to $18", "ceiling"), ("$2.13 + tips", "tipped"), ("$250/day", "day"),
                      ("$120/shift", "day"), ("17-15", "below its bottom"), ("DOE", "no pay rate"),
                      ("$0.50", "plausible"), ("", "no pay")):
        try:
            parse_pay(text)
            check(f"pay refuses '{text}'", False)
        except PayError as exc:
            check(f"pay refuses '{text}' ({why})", why in str(exc))
    e = analyse(write("rowerr.csv", H + "Cashier,DOE,Alpha,TX,S1,1\nCashier,13,Alpha,TX,S2,1\n"),
                as_of=as_of, wages_path=fw)
    check("pay: one bad pay value is reported on its row, the rest still run",
          len(e["results"]) == 1 and e["unresolved"][0]["row"] == 2)

    # the ladder with ties: the fixture 33333 has p10 = p25 = 15.00
    t = analyse(write("tie.csv", "job_title,pay,area,site\nCashier,15.00,33333,A\nCashier,14.99,33333,B\n"
                      "Cashier,13.99,11111,C\n"), as_of=as_of, wages_path=fw)
    tb = {x["site"]: x for x in t["results"]}
    check("ties: a rate equal to a tied 10th and 25th is at the 25th", tb["A"]["percentile"] == 25
          and tb["A"]["band"] == "under the median" and tb["A"]["gap_to_p25"] == 0)
    check("ties: one cent under it is bottom 10%", tb["B"]["band"] == "bottom 10%")
    check("bands: 13.99 against a 14.00 median is under the median, whatever rounding says",
          tb["C"]["band"] == "under the median" and "49th" in tb["C"]["percentile_text"])
    check("headline: cost counts only postings below the 25th",
          t["headline"]["cost_to_reach_25th_per_year"] == round(0.01 * 30 * 52))

    # titles that name a different job than the alias inside them
    tt = analyse(write("titles.csv", "job_title,pay,city,state\n" + "".join(
        f"{t},15,Alpha,TX\n" for t in ["Cashier Supervisor", "Delivery Driver Helper", "Cleaning Crew",
                                        "Night Guard", "Cashier/Stocker", "Price Checker", "Head Cashier",
                                        "Overnight Stocker", "Line Cook", "Crew"])), as_of=as_of, wages_path=fw)
    mapped = {x["job_title"]: x["soc"] for x in tt["results"] + tt["unresolved"]}
    for t in ["Cashier Supervisor", "Delivery Driver Helper", "Cleaning Crew", "Night Guard", "Cashier/Stocker",
              "Price Checker", "Head Cashier"]:
        check(f"titles: '{t}' is sent to confirmation, not guessed", mapped[t] is None)
    check("titles: 'Overnight Stocker', 'Line Cook' and plain 'Crew' still map",
          mapped["Overnight Stocker"] == "53-7065" and mapped["Line Cook"] == "35-2014" and mapped["Crew"] == "35-3023")

    # cities
    occs, aliases_ = load_occupations()
    _, areas_ = load_wages(fw)[0:2]
    idx, multi = city_index(areas_)
    check("cities: a hyphenated principal city matches whole", ("winston salem", "NC") in idx)
    check("cities: Ft and St are spelled out", _city("Ft. Worth") == "fort worth" and _city("Saint Louis") == "st louis")
    check("cities: a full state name is read", resolve_area({"city": "Alpha", "state": "Texas"}, areas_, idx, 2, multi)[0] == "11111")
    check("areas: a code a spreadsheet stripped of its zeros is found",
          resolve_area({"area": "33333.0"}, areas_, idx, 2, multi)[0] == "0033333")
    check("areas: a metro spanning states asks for confirmation",
          "confirm" in resolve_area({"city": "Winston-Salem", "state": "NC"}, areas_, idx, 2, multi)[1])

    for bad in ({"hours_per_week": 0}, {"uplift": -100}, {"as_of": date(2024, 1, 1)}):
        try:
            analyse(write("ok.csv", H + "Cashier,13,Alpha,TX,S1,1\n"), wages_path=fw,
                    **({"as_of": as_of} | bad))
            check(f"refuses {bad}", False)
        except Refusal:
            check(f"refuses {list(bad)[0]} out of range", True)
    sp = analyse(write("same.csv", H + "Cashier,13,Alpha,TX,S1,1\nCashier,15,Alpha,TX,S1,1\n"), as_of=as_of, wages_path=fw)
    check("spreads: two rates at the same site are not 'your sites differ'", not sp["spreads"])
    up = analyse(write("up.csv", H + "Cashier,13,Alpha,TX,S1,1\n"), as_of=as_of, uplift=5, wages_path=fw)
    check("uplift: every line says so", "uplift" in text_report(up).split("Below")[-1] or "uplift" in line(up["results"][0]))

    # the real table, if it is there, must be what the metadata says it is
    real = os.path.join(REF, "wages.csv")
    if os.path.exists(real):
        t, areas, meta = load_wages()
        check("real data: rows match the metadata", len(t) == meta["rows"])
        check("real data: every row has a median", all(v["median"] for v in t.values()))
        check("real data: percentiles never decrease", all(
            all(x <= y for x, y in zip(vals, vals[1:]))
            for vals in ([v[k] for _, k in POINTS if v[k] is not None] for v in t.values())))
        occ, _ = load_occupations()
        check("real data: only listed occupations", {s for _, s in t} <= set(occ))
        s = os.path.join(SAMPLE, "northline_postings.csv")
        if os.path.exists(s):
            run_sample_checks(check, as_of)

    out = os.path.join(tmp, "r.html")
    html_report(r, out, "Test")
    body = open(out, encoding="utf-8").read()
    check("html: renders with the title", "<h1>Test</h1>" in body and "<table>" in body)
    check("html: self-contained", "<script" not in body and "http://" not in body)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


def run_sample_checks(check, as_of):
    """Filled in once the sample is built against the real table."""
    expect = json.load(open(os.path.join(SAMPLE, "northline_expected.json"), encoding="utf-8"))
    r = analyse(os.path.join(SAMPLE, "northline_postings.csv"), as_of=as_of)
    bands = {x["row"]: x["band"] for x in r["results"]}
    for row, b in expect["bands"].items():
        check(f"sample: row {row} is {b}", bands.get(int(row)) == b)
    check("sample: unresolved rows are the planted ones",
          sorted(u["row"] for u in r["unresolved"]) == sorted(expect["unresolved"]))
    check("sample: the planted spread is found",
          [(s["area_title"], s["occupation"]) for s in r["spreads"]] == [tuple(x) for x in expect["spreads"]])


# -------------------------------------------------------------------- main

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
        if not opt("--postings"):
            print(__doc__)
            return 2
        try:
            as_of = date.fromisoformat(opt("--as-of")) if opt("--as-of") else None
        except ValueError:
            raise Refusal("--as-of must be a date in YYYY-MM-DD form.")
        try:
            hours = float(opt("--hours-per-week") or 30)
            uplift = float(opt("--uplift").rstrip("%")) if opt("--uplift") else None
        except ValueError:
            raise Refusal("--hours-per-week and --uplift take plain numbers, for example 30 and 3.5.")
        r = analyse(opt("--postings"), as_of, hours, uplift)
        for flag in ("--html", "--json"):
            if opt(flag) and not os.path.isdir(os.path.dirname(os.path.abspath(opt(flag)))):
                raise Refusal(f"the folder for {flag} does not exist.")
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    print(text_report(r))
    if opt("--html"):
        html_report(r, opt("--html"), opt("--title") or "Pay competitiveness")
    if opt("--json"):
        json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=2, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
