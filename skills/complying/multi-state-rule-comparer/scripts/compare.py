#!/usr/bin/env python3
"""Multi-State Rule Comparer engine.

Reads a list of sites (state, city, headcount, industry, whether minors work there),
looks up every state and city rule in references/rules.json, works out which ones apply
at your size, and writes the comparison grid, the strictest rule per category, the rules
site by site, what changes in the next 18 months, and a research checklist ordered by
exposure. Not legal advice: every rule names its source and the date it was checked.

    python3 scripts/compare.py --sites sites.csv [--total-employees N] [--locations N]
                               [--as-of YYYY-MM-DD] [--md out.md] [--html out.html] [--json out.json]
    python3 scripts/compare.py --states CA,NY,TX          # compare states without a site list
    python3 scripts/compare.py --state CA                 # every rule held for one state
    python3 scripts/compare.py --demo                     # the sample employer
    python3 scripts/compare.py --test                     # the test suite

Exit codes: 0 report written, 2 input refused.
"""
import argparse, csv, datetime as dt, html, io, json, os, random, re, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RULES_PATH = os.path.join(ROOT, "references", "rules.json")
SAMPLE = os.path.join(ROOT, "references", "sample", "harbor_pine_sites.csv")
SAMPLE_TOTAL = 2350
STALE_DAYS = 180
HORIZON_DAYS = 548          # upcoming changes shown up to 18 months ahead
MAX_ROWS = 2000

INDUSTRIES = {"retail", "food_service", "hospitality", "warehouse", "healthcare", "manufacturing",
              "building_services", "construction", "office", "other"}
INDUSTRY_ALIASES = {
    "grocery": "retail", "store": "retail", "retail store": "retail", "restaurant": "food_service",
    "qsr": "food_service", "fast food": "food_service", "quick service": "food_service", "cafe": "food_service",
    "food service": "food_service", "food": "food_service", "hotel": "hospitality", "lodging": "hospitality",
    "distribution": "warehouse", "dc": "warehouse", "distribution center": "warehouse", "logistics": "warehouse",
    "fulfillment": "warehouse", "hospital": "healthcare", "clinic": "healthcare", "home care": "healthcare",
    "plant": "manufacturing", "factory": "manufacturing", "janitorial": "building_services",
    "security": "building_services", "corporate": "office", "hq": "office", "headquarters": "office",
}
COLUMN_ALIASES = {
    "site_id": ["site_id", "site", "location", "location_id", "store", "store_id", "store_number", "branch", "facility"],
    "state": ["state", "st", "state_code", "province"],
    "city": ["city", "town", "municipality"],
    "county": ["county", "parish", "borough"],
    "headcount": ["headcount", "employees", "employee_count", "staff", "hc", "fte", "workers", "people"],
    "industry": ["industry", "type", "site_type", "format", "business"],
    "minors": ["minors", "under_18", "has_minors", "minor_workers", "employs_minors"],
    "tipped": ["tipped", "tipped_roles", "has_tipped"],
}
# Columns that describe a person rather than a site. A file that has them is an employee
# list, not a site list, and is refused.
PERSONAL = re.compile(r"(^|_)(first_?name|last_?name|full_?name|name|email|e_mail|phone|mobile|cell|ssn|social|"
                      r"dob|birth|birthdate|employee_?id|emp_?id|worker_?id|applicant|candidate|salary|"
                      r"hourly_?rate|pay_?rate|home_?address|manager|supervisor)($|_)")
NOT_PERSONAL = re.compile(r"^(site|store|location|branch|facility|brand|business|company|district|region|city|county|"
                          r"state|banner|unit|dept|department)_?name$|^(avg|average|median|mean|min|max)_")


def is_personal(h):
    return bool(PERSONAL.search(h)) and not NOT_PERSONAL.search(h)
YES = {"yes", "y", "true", "1", "x", "oui"}
NO = {"no", "n", "false", "0", ""}
STATUS_MARK = {"applies": "●", "below": "○", "not_covered": "○", "none": "–", "check": "?", "upcoming": "→",
               "repealed": "–", "partial": "◐", "local": "◆"}
CONF_WEIGHT = {"official": 1, "secondary": 2, "lead": 3}


class Refused(Exception):
    pass


# --------------------------------------------------------------------------------------- loading
def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def norm(s):
    s = (s or "").strip().lower()
    s = s.replace("’", "'").replace(".", "")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^saint ", "st ", s)
    return s


def state_code(value, rules):
    v = (value or "").strip()
    if not v:
        return None
    up = v.upper().replace(".", "")
    if up in rules["states"]:
        return up
    if up in ("WASHINGTON DC", "WASHINGTON, DC", "DISTRICT OF COLUMBIA", "D C"):
        return "DC"
    for code, st in rules["states"].items():
        if norm(st["name"]) == norm(v):
            return code
    return None


def read_sites(path, rules):
    """Return (sites, notes). Raises Refused with a reason a person can act on."""
    try:
        raw = open(path, "rb").read()
    except OSError as e:
        raise Refused(f"cannot open {path}: {e.strerror}")
    if not raw.strip():
        raise Refused("the file is empty")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refused("the file is not UTF-8 text. Save it as CSV UTF-8 and try again")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise Refused("no site rows under the header")
    header = [re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_") for h in rows[0]]
    personal = [rows[0][i] for i, h in enumerate(header) if is_personal(h)]
    if personal:
        raise Refused("these columns describe people, not sites: " + ", ".join(personal) +
                      ". I need one row per site with a headcount. Remove them (or aggregate by site) and re-export")
    col = {}
    for key, names in COLUMN_ALIASES.items():
        for i, h in enumerate(header):
            if h in names and key not in col:
                col[key] = i
    missing = [k for k in ("state", "headcount") if k not in col]
    if missing:
        raise Refused("missing column(s): " + ", ".join(missing) + ". Required: state, headcount. Optional: site_id, city, county, industry, minors")
    used = set(col.values())
    ignored = [rows[0][i] for i in range(len(header)) if i not in used and header[i]]
    notes = []
    if ignored:
        notes.append("Ignored columns: " + ", ".join(ignored) + ".")
    body = rows[1:]
    if len(body) > MAX_ROWS:
        raise Refused(f"{len(body)} rows. A site list over {MAX_ROWS} rows looks like an employee list; send one row per site")
    sites, seen = [], set()
    unknown_ind = set()
    for n, r in enumerate(body, start=2):
        get = lambda k: (r[col[k]].strip() if k in col and col[k] < len(r) else "")
        st = state_code(get("state"), rules)
        if not st:
            raise Refused(f"row {n}: '{get('state')}' is not a US state, DC or a two-letter code")
        hc_raw = get("headcount").replace(",", "")
        try:
            hc_f = float(hc_raw)
        except ValueError:
            raise Refused(f"row {n}: headcount '{get('headcount')}' is not a number")
        if hc_f < 0 or hc_f != hc_f or hc_f > 1_000_000:
            raise Refused(f"row {n}: headcount {get('headcount')} is out of range")
        hc = int(round(hc_f))
        sid = get("site_id") or f"site-{n - 1}"
        if sid in seen:
            raise Refused(f"row {n}: site '{sid}' appears twice. One row per site")
        seen.add(sid)
        ind_raw = norm(get("industry")).replace("-", " ")
        ind = ind_raw.replace(" ", "_") if ind_raw.replace(" ", "_") in INDUSTRIES else INDUSTRY_ALIASES.get(ind_raw)
        if ind_raw and not ind:
            unknown_ind.add(get("industry"))
        flag = {}
        for k in ("minors", "tipped"):
            v = norm(get(k))
            if v in YES:
                flag[k] = True
            elif v in NO:
                flag[k] = False if k in col else None
            else:
                raise Refused(f"row {n}: {k} '{get(k)}' should be yes or no")
        sites.append({"site_id": sid, "state": st, "city": get("city"), "county": re.sub(r"(?i)\s+county$", "", get("county")),
                      "headcount": hc, "industry": ind, "minors": flag["minors"], "tipped": flag["tipped"]})
    if unknown_ind:
        notes.append("Industry not recognised, treated as unknown: " + ", ".join(sorted(unknown_ind)) +
                     ". Use one of: " + ", ".join(sorted(INDUSTRIES)) + ".")
    if "minors" not in col:
        notes.append("No minors column: I cannot tell where people under 18 work, so work permits are listed for every state.")
    if all(s["headcount"] == 0 for s in sites):
        raise Refused("every headcount is zero")
    return sites, notes


# --------------------------------------------------------------------------------------- logic
def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


class Context:
    def __init__(self, rules, sites, total=None, locations=None, as_of=None, headcounts_known=True):
        self.rules = rules
        self.sites = sites
        self.as_of = as_of or dt.date.today()
        self.headcounts_known = headcounts_known
        self.site_counts_known = headcounts_known and any(s["headcount"] for s in sites)
        sum_hc = sum(s["headcount"] for s in sites)
        if total is not None and total < sum_hc:
            raise Refused(f"--total-employees {total} is below the {sum_hc} people on your site list")
        self.total = total if total is not None else sum_hc
        self.total_given = total is not None
        self.locations = locations if locations is not None else len(sites)
        self.locations_given = locations is not None
        self.in_state = {}
        for s in sites:
            self.in_state[s["state"]] = self.in_state.get(s["state"], 0) + s["headcount"]
        self.states = sorted(self.in_state, key=lambda c: (-self.in_state[c], c))
        self.local_hc = {}
        self.site_locals = {s["site_id"]: match_locals(rules, s) for s in sites}
        for s in sites:
            for loc, how in self.site_locals[s["site_id"]]:
                if how == "match":
                    self.local_hc[loc["id"]] = self.local_hc.get(loc["id"], 0) + s["headcount"]

    def count(self, basis, state=None, local_id=None):
        if basis != "total" and not self.site_counts_known:
            return None
        if basis == "in_state":
            return self.in_state.get(state, 0)
        if basis == "local":
            return self.local_hc.get(local_id, 0)
        return self.total


def match_locals(rules, site):
    """[(local, 'match'|'check')] for one site."""
    out = []
    city, county = norm(site["city"]), norm(site["county"])
    for loc in rules["local"]:
        if loc["state"] != site["state"]:
            continue
        names = {norm(c) for c in loc["cities"]}
        counties = {norm(c) for c in loc["counties"]}
        if loc["scope"] == "city":
            if city and city in names:
                out.append((loc, "match"))
            elif not city and county and counties and county in counties:
                out.append((loc, "match"))
        elif loc["scope"] == "county":
            if county and county in counties:
                out.append((loc, "match"))
            elif not county and city and city in names:
                out.append((loc, "match"))
        elif loc["scope"] == "county_unincorporated":
            if county and county in counties:
                if not city or city in ("unincorporated", "uninc", "unincorporated area"):
                    out.append((loc, "match"))
    return out


def effective_cell(cell, as_of):
    """Apply a 'next' change that has already happened; report a future effective date."""
    c = dict(cell)
    nxt = c.get("next")
    if nxt and parse_date(nxt.get("date")) and parse_date(nxt["date"]) <= as_of:
        merged = dict(c)
        for k, v in nxt.items():
            if k in ("date", "summary"):
                continue
            merged[k] = v
        merged["summary"] = c.get("summary", "") + " Now in force: " + nxt.get("summary", "")
        if merged.get("status") == "upcoming":
            merged["status"] = "rule"
        merged.pop("next", None)
        merged["changed_on"] = nxt["date"]
        if "rate" in c and "rate" not in nxt:
            merged["status"] = "check"
            merged["summary"] = c.get("summary", "") + f" Changed on {nxt['date']} ({nxt.get('summary', '')}): the new amount is not in this file."
        c = merged
    eff = parse_date(c.get("effective"))
    if eff and eff > as_of and c.get("status") == "rule":
        c["status"] = "upcoming"
        c.setdefault("next", {"date": c["effective"], "summary": c["summary"]})
    return c


def evaluate(ctx, cell, state, local_id=None, sites=None):
    """Return dict(state=applies|below|not_covered|none|check|upcoming|repealed, why, cell, tier)."""
    c = effective_cell(cell, ctx.as_of)
    st = c.get("status")
    res = {"cell": c, "tier": None, "why": ""}
    if st in ("none", "repealed"):
        res["state"] = st
        return res
    if st == "check":
        res["state"] = "check"
        res["why"] = "not confirmed"
        return res
    if st == "upcoming":
        res["state"] = "upcoming"
        return res
    # industries
    if c.get("industries") and sites is not None:
        inds = {s["industry"] for s in sites}
        if inds & set(c["industries"]):
            pass
        elif None in inds:
            res["state"] = "check"
            res["why"] = "covers " + ", ".join(c["industries"]) + "; your site's industry is not given"
            return res
        else:
            res["state"] = "not_covered"
            res["why"] = "covers " + ", ".join(c["industries"]) + " only"
            return res
    if c.get("min_locations"):
        if ctx.locations < c["min_locations"]:
            res["state"] = "below" if ctx.locations_given else "check"
            res["why"] = f"{c['min_locations']}+ locations ({'you have ' + str(ctx.locations) if ctx.locations_given else 'location count not given; franchise networks may count'})"
            if res["state"] == "below":
                return res
            return res
    if c.get("tiers"):
        basis = c.get("count", "total")
        n = ctx.count(basis, state, local_id)
        if n is None:
            res["state"] = "check"
            res["why"] = f"depends on your {basis.replace('_', '-')} headcount"
            return res
        for t in sorted(c["tiers"], key=lambda t: -t["min"]):
            if n >= t["min"]:
                res["tier"] = t
                break
        if not ctx.headcounts_known:
            res["state"] = "check"
            res["why"] = "depends on headcount"
            return res
        if res["tier"] is None:
            res["state"] = "below"
            res["why"] = f"{basis.replace('_', '-')} headcount {n} is below the smallest tier"
            return res
        res["state"] = "applies"
        return res
    th = c.get("threshold")
    if th:
        n = ctx.count(th.get("count", "total"), state, local_id)
        if n is None and th["min"] > 1:
            res["state"] = "check"
            res["why"] = f"applies at {th['min']}+ employees ({th.get('count', 'total').replace('_', '-')})"
            return res
        n = n or 0
        if not ctx.headcounts_known and th["min"] > 1:
            res["state"] = "check"
            res["why"] = f"applies at {th['min']}+ employees"
            return res
        if n < th["min"]:
            res["state"] = "below"
            res["why"] = f"{th['min']}+ employees ({th.get('count', 'total').replace('_', '-')}); you have {n}"
            nxt = c.get("next")
            if nxt and nxt.get("threshold") and n >= nxt["threshold"]["min"]:
                res["state"] = "upcoming"
                res["why"] += f"; covers you from {nxt['date']}"
            return res
        if c.get("below") is not None:
            res["above_threshold"] = True
    elif c.get("below") is not None:
        pass
    res["state"] = "partial" if st == "partial" else "applies"
    return res


def state_cell_result(ctx, code, cat):
    cell = ctx.rules["states"][code]["rules"][cat]
    sites = [s for s in ctx.sites if s["state"] == code]
    r = evaluate(ctx, cell, code, sites=sites)
    c = r["cell"]
    # Washington fair chance: under the threshold the older rule still applies until next date
    if c.get("below") and r["state"] in ("below", "upcoming") and "employees" in r["why"]:
        r["state"] = "applies"
        r["why"] = ""
        r["cell"] = dict(c, summary=c["below"]["summary"], stage=c["below"]["stage"])
    return r


def site_min_wage(ctx, site):
    """(rate or None, label, notes) for one site: highest of federal, state (regional), local."""
    rules = ctx.rules
    fed = rules["federal_min_wage"]
    sc = effective_cell(rules["states"][site["state"]]["rules"]["minimum_wage"], ctx.as_of)
    rate, label, notes = fed, "federal", []
    srate = sc.get("rate")
    if sc.get("status") == "check":
        notes.append(f"{site['state']} rate changed on {sc.get('changed_on', '?')}: confirm the new amount")
    region = None
    for reg in sc.get("regions", []):
        if norm(site["county"]) in {norm(x) for x in reg.get("counties", [])} or norm(site["city"]) in {norm(x) for x in reg.get("cities", [])}:
            region = reg
            break
    if region:
        srate = region["rate"]
        if region.get("check"):
            notes.append(f"{site['state']} {region['label']}")
    elif sc.get("regions") and not site["county"]:
        notes.append(f"{site['state']} has regional rates and no county was given: confirm the rate")
    if srate is not None and srate > rate:
        rate, label = srate, site["state"]
    unknown_local = []
    for loc, how in ctx.site_locals[site["site_id"]]:
        lc = loc["rules"].get("minimum_wage")
        if not lc or how != "match":
            continue
        if loc["state"] in [p for p in []]:
            continue
        e = effective_cell(lc, ctx.as_of)
        if e.get("rate") is None or e.get("status") == "check":
            unknown_local.append(loc["name"])
            continue
        if e["rate"] > rate:
            rate, label = e["rate"], loc["name"]
    if unknown_local:
        notes.append("local rate not confirmed: " + ", ".join(unknown_local))
        return rate, label, notes, True
    return rate, label, notes, False


def compare(ctx):
    rules = ctx.rules
    order = rules["order"]
    cats = rules["categories"]
    out = {"as_of": ctx.as_of.isoformat(), "checked": rules["checked"], "total_employees": ctx.total, "headcounts_known": ctx.headcounts_known,
           "total_given": ctx.total_given, "locations": ctx.locations, "states": ctx.states,
           "in_state": ctx.in_state, "sites": len(ctx.sites), "grid": {}, "strictest": {}, "process": {},
           "site_tier": [], "upcoming": [], "checklist": [], "notes": []}
    age = (ctx.as_of - parse_date(rules["checked"])).days
    if age > STALE_DAYS:
        out["notes"].append(f"The rules file was checked on {rules['checked']}, {age} days before {ctx.as_of}. "
                            f"Everything in it is due for a re-check; treat every cell as a lead.")
    minors_known = any(s["minors"] is not None for s in ctx.sites)
    minors_states = {s["state"] for s in ctx.sites if s["minors"] or s["minors"] is None}

    # ---- grid -----------------------------------------------------------------------------
    for cat in order:
        row = {}
        for code in ctx.states:
            r = state_cell_result(ctx, code, cat)
            if cat == "minors_work_permit" and code not in minors_states and r["state"] in ("applies", "partial"):
                r = dict(r, state="not_covered", why="no site in this state employs minors")
            c = r["cell"]
            summary = c.get("summary", "")
            if r["tier"]:
                t = r["tier"]
                summary += f" Your tier: up to {t['cap']} hours" + (" (unpaid)" if t.get("paid") is False else " (paid only above $1M net income)" if t.get("paid") == "check" else " paid") + "."
            row[code] = {"result": r["state"], "why": r["why"], "summary": summary, "confidence": c.get("confidence"),
                         "source": source_ref(rules, c.get("source")), "citation": c.get("citation"),
                         "next": c.get("next"), "tier": r["tier"], "numbers": {k: c[k] for k in ("rate", "meal_after_hours", "days", "stage", "response_days", "accrual", "cap", "notice_days", "rest_hours", "daily_ot_after", "permit_under", "posting", "benefits", "state_form", "acknowledgment", "language_rule") if k in c}}
        out["grid"][cat] = row

    # ---- site tier --------------------------------------------------------------------------
    max_rate, max_site = 0, None
    for s in ctx.sites:
        rate, label, notes, unknown = site_min_wage(ctx, s)
        if rate > max_rate:
            max_rate, max_site = rate, s
        pre = {p["category"] for p in rules["states"][s["state"]]["preempts"]}
        locs = []
        for loc, how in ctx.site_locals[s["site_id"]]:
            for cat in order:
                lc = loc["rules"].get(cat)
                if not lc:
                    continue
                r = evaluate(ctx, lc, s["state"], local_id=loc["id"], sites=[s])
                locs.append({"local": loc["name"], "category": cat, "result": r["state"], "why": r["why"],
                             "summary": r["cell"].get("summary", ""), "confidence": r["cell"].get("confidence"),
                             "source": source_ref(rules, r["cell"].get("source")), "next": r["cell"].get("next"),
                             "numbers": {k: r["cell"][k] for k in ("rate", "stage", "response_days", "accrual", "cap", "notice_days", "rest_hours", "posting", "benefits") if k in r["cell"]}})
            if loc.get("note"):
                notes.append(loc["note"])
        out["site_tier"].append({"site_id": s["site_id"], "state": s["state"], "city": s["city"], "county": s["county"],
                                 "headcount": s["headcount"], "industry": s["industry"], "minors": s["minors"],
                                 "min_wage": rate, "min_wage_from": label, "min_wage_unknown": unknown,
                                 "notes": notes, "local": locs, "preempted": sorted(pre)})

    # ---- a state with no rule of its own can still hold a city or county rule that applies ------
    for cat in order:
        for code in ctx.states:
            v = out["grid"][cat][code]
            if v["result"] in ("none", "below", "not_covered", "repealed"):
                hits = sorted({l["local"] for st in out["site_tier"] if st["state"] == code for l in st["local"]
                               if l["category"] == cat and l["result"] in ("applies", "partial")})
                if hits:
                    v["state_result"] = v["result"]
                    v["result"] = "local"
                    v["why"] = ("state: " + v["why"] + "; " if v["why"] else "") + "applies in " + ", ".join(hits)

    # ---- strictest -----------------------------------------------------------------------------
    out["strictest"] = strictest(ctx, out, max_rate, max_site)
    for cat in order:
        applicable = [c for c, v in out["grid"][cat].items() if v["result"] in ("applies", "partial")]
        local_app = sorted({l["local"] for st in out["site_tier"] for l in st["local"] if l["category"] == cat and l["result"] in ("applies", "partial")})
        meta = cats[cat]
        out["process"][cat] = {"label": meta["label"], "process": meta["process"], "note": meta["process_note"],
                               "states": applicable, "local": local_app}

    # ---- upcoming ------------------------------------------------------------------------------
    horizon = ctx.as_of + dt.timedelta(days=HORIZON_DAYS)
    seen = set()
    for cat in order:
        for code in ctx.states:
            c = ctx.rules["states"][code]["rules"][cat]
            add_upcoming(out, ctx, cat, code, None, c, horizon, seen)
    for st in ctx.sites:
        for loc, how in ctx.site_locals[st["site_id"]]:
            if how != "match":
                continue
            for cat, c in loc["rules"].items():
                add_upcoming(out, ctx, cat, st["state"], loc["name"], c, horizon, seen)
    out["upcoming"].sort(key=lambda u: (u["date"], u["where"], u["category"]))

    # ---- checklist -----------------------------------------------------------------------------
    out["checklist"] = checklist(ctx, out, minors_states)
    return out


def source_ref(rules, src):
    if not src:
        return None
    if src in rules["sources"]:
        s = rules["sources"][src]
        return {"url": s["url"], "title": s["title"], "as_of": s["as_of"]}
    return {"url": src, "title": None, "as_of": None}


def add_upcoming(out, ctx, cat, code, local, cell, horizon, seen):
    cands = []
    nxt = cell.get("next")
    if nxt and parse_date(nxt.get("date")):
        cands.append((parse_date(nxt["date"]), nxt.get("summary", "")))
    eff = parse_date(cell.get("effective"))
    if eff and not nxt:
        cands.append((eff, cell.get("summary", "")))
    for d, text in cands:
        if ctx.as_of < d <= horizon:
            key = (cat, code, local, d)
            if key in seen:
                continue
            seen.add(key)
            out["upcoming"].append({"date": d.isoformat(), "category": cat, "label": ctx.rules["categories"][cat]["label"],
                                    "where": f"{local}, {code}" if local else ctx.rules["states"][code]["name"], "state": code,
                                    "summary": text, "headcount": ctx.in_state.get(code, 0)})


def strictest(ctx, out, max_rate, max_site):
    g = out["grid"]
    res = {}
    keep = ("applies", "partial", "local") + (() if ctx.headcounts_known else ("check",))
    applies = lambda cat: {c: v for c, v in g[cat].items() if v["result"] in keep and v.get("state_result") is None}
    loc_app = lambda cat: [l for st in out["site_tier"] for l in st["local"] if l["category"] == cat and l["result"] in ("applies", "partial")]
    unknown = [s["site_id"] for s in out["site_tier"] if s["min_wage_unknown"]]
    res["minimum_wage"] = (f"${max_rate:.2f} at {max_site['site_id']} ({max_site['city'] or max_site['state']}). "
                           f"One national rate would have to be at least this." + (f" Not counted: unconfirmed local rates at {', '.join(unknown)}." if unknown else "")) if max_site else None
    a = applies("overtime_daily")
    ot = [c for c, v in a.items() if v["numbers"].get("daily_ot_after")]
    res["overtime_daily"] = ("Daily overtime in " + ", ".join(ot) + (". California's 8/12 rule is the strictest." if "CA" in ot else ".")) if ot else "Weekly overtime only, in every state on your list."
    a = applies("meal_breaks")
    meal = sorted(((v["numbers"]["meal_after_hours"], c) for c, v in a.items() if v["numbers"].get("meal_after_hours")))
    res["meal_breaks"] = (f"A meal by the end of hour {meal[0][0]:g} ({meal[0][1]}). " + ("California also owes a premium for each missed meal." if "CA" in a else "")).strip() if meal else "No state meal break rule for adults in your states."
    a = applies("rest_breaks")
    res["rest_breaks"] = ("Paid 10 minutes per 4 hours worked (" + ", ".join(sorted(a)) + ").") if a else "No state paid rest break rule in your states."
    a = applies("paid_sick_leave")
    caps, accr = [], []
    for c, v in a.items():
        t = v.get("tier")
        cap = t["cap"] if t else v["numbers"].get("cap")
        acc = (t or {}).get("accrual") or v["numbers"].get("accrual")
        if cap:
            caps.append((cap, c))
        if acc:
            accr.append((acc, c))
    for l in loc_app("paid_sick_leave"):
        if l["numbers"].get("cap"):
            caps.append((l["numbers"]["cap"], l["local"]))
        if l["numbers"].get("accrual"):
            accr.append((l["numbers"]["accrual"], l["local"]))
    if caps or accr:
        parts = []
        if accr:
            m = min(accr)
            parts.append(f"accrue 1 hour per {m[0]} worked ({m[1]})")
        if caps:
            m = max(caps)
            parts.append(f"allow at least {m[0]} hours a year ({m[1]})")
        nocap = [c for c, v in a.items() if "cap" in v["numbers"] and v["numbers"]["cap"] is None]
        res["paid_sick_leave"] = "One national policy would " + " and ".join(parts) + "." + (f" {', '.join(nocap)} sets no cap on use." if nocap else "")
    else:
        res["paid_sick_leave"] = "No paid sick leave law applies at your size in your states."
    sched = [(v["numbers"].get("notice_days", 0), v["numbers"].get("rest_hours", 0), c) for c, v in applies("predictive_scheduling").items()]
    sched += [(l["numbers"].get("notice_days", 0), l["numbers"].get("rest_hours", 0), l["local"]) for l in loc_app("predictive_scheduling")]
    if sched:
        nd = max(sched)
        rh = max(sched, key=lambda x: x[1])
        res["predictive_scheduling"] = f"{nd[0]} days' notice ({nd[2]}) and {rh[1]} hours between shifts ({rh[2]}) where an ordinance applies: " + ", ".join(sorted({x[2] for x in sched})) + "."
    else:
        res["predictive_scheduling"] = "No fair workweek ordinance applies to your sites as listed."
    a = applies("pay_transparency")
    la = loc_app("pay_transparency")
    posting = [c for c, v in a.items() if v["numbers"].get("posting")] + [l["local"] for l in la if l["numbers"].get("posting")]
    ben = [c for c, v in a.items() if v["numbers"].get("benefits")] + [l["local"] for l in la if l["numbers"].get("benefits")]
    if posting:
        res["pay_transparency"] = "A good-faith pay range in every posting, internal and external (" + ", ".join(sorted(set(posting))) + ")" + (", with a benefits description (" + ", ".join(sorted(set(ben))) + ")." if ben else ".")
    elif a:
        res["pay_transparency"] = "Pay range on request or before an offer (" + ", ".join(sorted(a)) + "); no posting duty."
    else:
        res["pay_transparency"] = "No pay range law applies in your states as listed."
    a = applies("salary_history")
    la = loc_app("salary_history")
    res["salary_history"] = ("Never ask about pay history, anywhere (" + ", ".join(sorted(set(list(a) + [l["local"] for l in la]))) + ").") if (a or la) else "No salary history ban applies in your states."
    fc = [(v["numbers"].get("stage", 0), v["numbers"].get("response_days", 0), c) for c, v in applies("fair_chance").items()]
    fc += [(l["numbers"].get("stage", 0), l["numbers"].get("response_days", 0), l["local"]) for l in loc_app("fair_chance")]
    stages = {0: "rule on timing", 1: "on the initial application", 2: "before the first interview", 3: "before a conditional offer"}
    if fc:
        top = max(fc)
        rd = max(fc, key=lambda x: x[1])
        strict = sorted({x[2] for x in fc if x[0] == top[0]})
        res["fair_chance"] = f"No criminal history questions {stages[top[0]]} ({', '.join(strict)})." + (f" Before withdrawing an offer, the longest response window is {rd[1]} business days ({rd[2]})." if rd[1] else "")
    else:
        res["fair_chance"] = "No fair chance rule applies to private employers in your states."
    a = applies("minors_work_permit")
    if a:
        res["minors_work_permit"] = "Work permits before a minor's first shift in " + ", ".join(f"{c} (under {v['numbers'].get('permit_under', '?')})" for c, v in sorted(a.items())) + "."
    else:
        res["minors_work_permit"] = "No work permit duty for the sites you flagged."
    a = applies("new_hire_reporting")
    if a:
        m = min((v["numbers"].get("days", 20), c) for c, v in a.items())
        res["new_hire_reporting"] = f"Report every hire within {m[0]} days ({m[1]}) to keep one process."
    a = applies("e_verify")
    res["e_verify"] = ("E-Verify required for new hires in " + ", ".join(sorted(a)) + ".") if a else "No state requires you to use E-Verify at your size."
    a = applies("wage_notice")
    forms = [c for c, v in a.items() if v["numbers"].get("state_form") or v["numbers"].get("language_rule")]
    ack = [c for c, v in a.items() if v["numbers"].get("acknowledgment")]
    if a:
        res["wage_notice"] = "One written pay notice at hire covering every state's items (" + ", ".join(sorted(a)) + ")" + (f"; own forms or language rules in {', '.join(sorted(forms))}" if forms else "") + (f"; signed acknowledgment in {', '.join(sorted(ack))}" if ack else "") + "."
    else:
        res["wage_notice"] = "No written pay notice at hire required in your states."
    a = applies("paid_family_leave")
    res["paid_family_leave"] = ("State programs in " + ", ".join(sorted(a)) + ": payroll set-up, notices and posters per state.") if a else "No state paid family leave program in your states."
    return res


def checklist(ctx, out, minors_states):
    items = []
    cats = ctx.rules["categories"]

    def add(kind, where, state, cat, question, source, hc, conf="secondary", force=0):
        meta = cats.get(cat, {"volatility": 2, "severity": 2, "label": "City and county rules"})
        score = max(hc, 1) * meta["volatility"] * meta["severity"] * CONF_WEIGHT.get(conf, 2)
        if cat == "minors_work_permit" or force:
            score += 10 ** 7
        items.append({"kind": kind, "where": where, "state": state, "category": cat, "label": meta["label"],
                      "question": question, "source": source, "headcount": hc, "confidence": conf, "score": score})

    for cat, row in out["grid"].items():
        for code, v in row.items():
            hc = ctx.in_state.get(code, 0)
            name = ctx.rules["states"][code]["name"]
            minors_pull = cat == "minors_work_permit" and code in minors_states
            if v["result"] == "check":
                add("confirm", name, code, cat, f"{cats[cat]['label']} in {name}: {v['summary']} ({v['why'] or 'unconfirmed'})", v["source"], hc, "lead")
            elif v["result"] in ("applies", "partial", "upcoming", "local") and v["confidence"] in ("secondary", "lead") and v.get("state_result") not in ("none", "below", "not_covered", "repealed"):
                lead = "Not confirmed anywhere yet" if v["confidence"] == "lead" else "Confirm at the official source"
                add("confirm", name, code, cat, f"{lead}: {v['summary']}", v["source"], hc, v["confidence"], force=minors_pull)
            elif v["result"] == "below" and v["confidence"] != "official" and hc:
                add("confirm", name, code, cat, f"Confirm the threshold and how it is counted ({v['why']}): {v['summary']}", v["source"], hc, v["confidence"])
            elif minors_pull and v["result"] in ("applies", "partial"):
                add("confirm", name, code, cat, f"Before a minor's first shift: {v['summary']} Hours and task limits are not covered here.", v["source"], hc, "official", force=1)
    for st in out["site_tier"]:
        where = f"{st['site_id']} ({st['city'] or 'no city'}, {st['state']})"
        for n in st["notes"]:
            if n.startswith("local rate not confirmed"):
                continue        # each unconfirmed local rate is its own item below
            n = n.rstrip(".")
            add("site", where, st["state"], "minimum_wage", n[0].upper() + n[1:] + ".", None, st["headcount"], "lead")
        for l in st["local"]:
            if l["result"] in ("applies", "partial", "check", "upcoming") and l["confidence"] in ("secondary", "lead"):
                add("site", where, st["state"], l["category"], f"{l['local']}: {l['summary']}" + (f" ({l['why']})" if l["why"] else ""), l["source"], st["headcount"], l["confidence"] if l["result"] != "check" else "lead")
        if not st["city"]:
            add("site", where, st["state"], "local_ordinances", "No city given: local ordinances (minimum wage, sick leave, scheduling, fair chance) cannot be checked for this site.", None, st["headcount"], "lead")
        elif not any(l for l in st["local"]):
            open_cats = [c for c in ("minimum_wage", "paid_sick_leave", "predictive_scheduling", "fair_chance", "pay_transparency", "salary_history") if c not in st["preempted"]]
            if open_cats and ctx.rules["states"][st["state"]]:
                add("site", where, st["state"], "local_ordinances", f"No ordinance for {st['city']} in my list. That is not proof there is none: check the city and county codes for " + ", ".join(cats[c]["label"].lower() for c in open_cats) + ".", None, st["headcount"] // 2, "lead")
    for u in out["upcoming"]:
        if "not confirmed" in u["summary"] or "confirm" in u["summary"].lower():
            add("upcoming", u["where"], u["state"], u["category"], f"On {u['date']}: {u['summary']}", None, u["headcount"], "lead")
    items.sort(key=lambda i: -i["score"])
    seen, dedup = set(), []
    for i in items:
        k = (i["where"], i["category"], i["question"])
        if k not in seen:
            seen.add(k)
            dedup.append(i)
    return dedup


# --------------------------------------------------------------------------------------- render
def render_text(out, rules, limit=12):
    L = []
    who = (f"{out['total_employees']} employees" + ("" if out["total_given"] else " (sum of the site list)")) if out["headcounts_known"] else "no headcounts, so thresholds are left to confirm"
    L.append(f"Multi-State Rule Comparer: {out['sites']} sites, {len(out['states'])} states, {who}. Rules checked {out['checked']}, compared as of {out['as_of']}. Not legal advice.")
    for n in out["notes"]:
        L.append("NOTE: " + n)
    n_app = sum(1 for cat in out["grid"].values() for v in cat.values() if v["result"] in ("applies", "partial"))
    n_loc = len({(l["local"], l["category"]) for s in out["site_tier"] for l in s["local"] if l["result"] in ("applies", "partial")})
    L.append(f"{n_app} state rules and {n_loc} city or county rules apply; {len(out['upcoming'])} changes in the next 18 months; {len(out['checklist'])} research items.")
    L.append("")
    L.append("STRICTEST RULE, IF YOU RUN ONE PROCESS")
    for cat in rules["order"]:
        if out["strictest"].get(cat):
            L.append(f"  {rules['categories'][cat]['label']}: {out['strictest'][cat]}")
    L.append("")
    L.append("UPCOMING")
    for u in out["upcoming"][:limit]:
        L.append(f"  {u['date']}  {u['where']}: {u['label']}. {u['summary']}")
    if not out["upcoming"]:
        L.append("  none in the next 18 months in this file")
    L.append("")
    L.append(f"RESEARCH FIRST (top {min(limit, len(out['checklist']))} of {len(out['checklist'])})")
    for i in out["checklist"][:limit]:
        L.append(f"  [{i['label']}] {i['where']}: {i['question']}")
    return "\n".join(L)


def md_escape(s):
    return (s or "").replace("|", "\\|").replace("\n", " ")


def render_md(out, rules):
    cats, order = rules["categories"], rules["order"]
    L = [f"# Multi-state rule comparison", "",
         f"{out['sites']} sites in {len(out['states'])} states, {out['total_employees']} employees"
         + ("" if out["total_given"] else " (sum of the site list)") + f". Rules checked {out['checked']}; compared as of {out['as_of']}. Not legal advice.", ""]
    for n in out["notes"]:
        L += [f"> {n}", ""]
    L += ["## The grid", "", "● applies at your size · ◆ a city or county rule applies · ◐ partial duty · ○ below the threshold or not your industry · → coming · ? confirm · – no rule", ""]
    L.append("| | " + " | ".join(f"{c} ({out['in_state'][c]})" for c in out["states"]) + " |")
    L.append("|---|" + "---|" * len(out["states"]))
    for cat in order:
        L.append(f"| {cats[cat]['label']} | " + " | ".join(STATUS_MARK.get(out["grid"][cat][c]["result"], "?") for c in out["states"]) + " |")
    L += ["", "## The strictest rule, if you run one process", ""]
    for cat in order:
        p = out["process"][cat]
        tag = {"strictest": "one process works", "variant": "needs state or site variants", "mixed": "one process, with variants"}[p["process"]]
        L.append(f"- **{cats[cat]['label']}** ({tag}): {out['strictest'].get(cat) or ''} {p['note']}")
    L += ["", "## What changes in the next 18 months", ""]
    if out["upcoming"]:
        L += ["| Date | Where | Rule | Change |", "|---|---|---|---|"]
        for u in out["upcoming"]:
            L.append(f"| {u['date']} | {u['where']} | {u['label']} | {md_escape(u['summary'])} |")
    else:
        L.append("Nothing dated in this file.")
    L += ["", "## Site by site", "", "| Site | Place | People | Minimum wage | City and county rules |", "|---|---|---|---|---|"]
    for s in out["site_tier"]:
        locs = "; ".join(sorted({f"{l['local']}: {cats[l['category']]['label'].lower()} {STATUS_MARK.get(l['result'], '?')}" for l in s["local"]})) or "none in my list"
        pre = (" Preempted by the state: " + ", ".join(cats[c]["label"].lower() for c in s["preempted"]) + ".") if s["preempted"] else ""
        mw = f"${s['min_wage']:.2f} ({s['min_wage_from']})" + (" + unconfirmed local rate" if s["min_wage_unknown"] else "")
        L.append(f"| {md_escape(s['site_id'])} | {md_escape(s['city'] or '?')}, {s['state']} | {s['headcount']} | {mw} | {md_escape(locs + pre)} |")
    L += ["", "## Research checklist, by exposure", "", "Exposure = people affected × how fast the rule moves × what a breach costs × how sure the cell is. Anything about minors comes first.", "",
          "| # | Rule | Where | What to confirm | Start at |", "|---|---|---|---|---|"]
    for n, i in enumerate(out["checklist"], 1):
        src = f"[{(i['source'] or {}).get('title') or 'source'}]({i['source']['url']})" if i.get("source") else ("city and county code" if i["kind"] == "site" else "the state agency")
        L.append(f"| {n} | {i['label']} | {md_escape(i['where'])} | {md_escape(i['question'])} | {src} |")
    L += ["", "## Every cell, state by state", ""]
    for code in out["states"]:
        L += [f"### {rules['states'][code]['name']} ({out['in_state'][code]} people)", ""]
        st = rules["states"][code]
        if st.get("preempts"):
            L.append("Blocks local ordinances on: " + ", ".join(cats[p["category"]]["label"].lower() for p in st["preempts"]) + "." + (" " + st["preempt_note"] if st.get("preempt_note") else ""))
            L.append("")
        L += ["| Rule | | What it says | Sure? | Source |", "|---|---|---|---|---|"]
        for cat in order:
            v = out["grid"][cat][code]
            src = f"[{(v['source'] or {}).get('title') or 'page'}]({v['source']['url']})" if v.get("source") else "not confirmed"
            why = f" ({v['why']})" if v["why"] else ""
            L.append(f"| {cats[cat]['label']} | {STATUS_MARK.get(v['result'], '?')} | {md_escape(v['summary'] + why)} | {v['confidence']} | {src} |")
        L.append("")
    L += ["## Not covered by this file", ""] + [f"- {x}" for x in rules["not_covered"]]
    return "\n".join(L) + "\n"


def render_html(out, rules):
    cats, order = rules["categories"], rules["order"]
    e = html.escape
    color = {"applies": "#1f6f43", "partial": "#5b8c2a", "local": "#6b3fa0", "below": "#8a8f98", "not_covered": "#8a8f98", "none": "#c5c9d0",
             "check": "#b7791f", "upcoming": "#2b5fb3", "repealed": "#c5c9d0"}
    head = ("<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
            "<title>Multi-state rule comparison</title><style>body{font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1100px;padding:16px;color:#1d2330}"
            "table{border-collapse:collapse;width:100%;margin:8px 0 20px}td,th{border:1px solid #e1e4ea;padding:6px 8px;vertical-align:top;text-align:left}"
            "th{background:#f5f6f8}.m{display:inline-block;min-width:18px;text-align:center;color:#fff;border-radius:4px;padding:0 4px}"
            ".wrap{overflow-x:auto;max-width:100%}small{color:#5a6170}h2{margin-top:28px}li,td{overflow-wrap:anywhere}</style>")
    P = [head, f"<h1>Multi-state rule comparison</h1><p>{out['sites']} sites in {len(out['states'])} states, {out['total_employees']} employees. "
               f"Rules checked {e(out['checked'])}; compared as of {e(out['as_of'])}. <b>Not legal advice.</b> Every cell names its source.</p>"]
    for n in out["notes"]:
        P.append(f"<p><b>Note:</b> {e(n)}</p>")
    P.append("<h2>The grid</h2><div class=wrap><table><tr><th></th>" + "".join(f"<th>{c}<br><small>{out['in_state'][c]}</small></th>" for c in out["states"]) + "</tr>")
    for cat in order:
        P.append(f"<tr><th>{e(cats[cat]['label'])}</th>")
        for c in out["states"]:
            v = out["grid"][cat][c]
            P.append(f"<td title=\"{e(v['summary'] + (' (' + v['why'] + ')' if v['why'] else ''))}\"><span class=m style='background:{color.get(v['result'], '#999')}'>{STATUS_MARK.get(v['result'], '?')}</span></td>")
        P.append("</tr>")
    P.append("</table></div><small>● applies · ◆ city or county rule applies · ◐ partial · ○ below threshold or not your industry · → coming · ? confirm · – no rule. Hover a cell for the rule.</small>")
    P.append("<h2>The strictest rule, if you run one process</h2><ul>")
    for cat in order:
        P.append(f"<li><b>{e(cats[cat]['label'])}</b>: {e(out['strictest'].get(cat) or '')} <small>{e(out['process'][cat]['note'])}</small></li>")
    P.append("</ul><h2>Next 18 months</h2><div class=wrap><table><tr><th>Date</th><th>Where</th><th>Rule</th><th>Change</th></tr>")
    for u in out["upcoming"]:
        P.append(f"<tr><td>{u['date']}</td><td>{e(u['where'])}</td><td>{e(u['label'])}</td><td>{e(u['summary'])}</td></tr>")
    P.append("</table></div><h2>Site by site</h2><div class=wrap><table><tr><th>Site</th><th>Place</th><th>People</th><th>Minimum wage</th><th>City and county rules</th></tr>")
    for s in out["site_tier"]:
        locs = "<br>".join(sorted({e(f"{l['local']}: {cats[l['category']]['label'].lower()} {STATUS_MARK.get(l['result'], '?')}") for l in s["local"]})) or "none in my list"
        P.append(f"<tr><td>{e(s['site_id'])}</td><td>{e(s['city'] or '?')}, {s['state']}</td><td>{s['headcount']}</td><td>${s['min_wage']:.2f} <small>{e(s['min_wage_from'])}</small></td><td>{locs}</td></tr>")
    P.append("</table></div><h2>Research checklist, by exposure</h2><div class=wrap><table><tr><th>#</th><th>Rule</th><th>Where</th><th>What to confirm</th></tr>")
    for n, i in enumerate(out["checklist"], 1):
        link = f" <a href=\"{e(i['source']['url'])}\">source</a>" if i.get("source") else ""
        P.append(f"<tr><td>{n}</td><td>{e(i['label'])}</td><td>{e(i['where'])}</td><td>{e(i['question'])}{link}</td></tr>")
    P.append("</table></div><h2>Not covered</h2><ul>" + "".join(f"<li>{e(x)}</li>" for x in rules["not_covered"]) + "</ul>")
    return "".join(P)


def render_state(rules, code, as_of):
    st = rules["states"][code]
    L = [f"{st['name']} ({code}), rules checked {rules['checked']}, as of {as_of}. Not legal advice."]
    for cat in rules["order"]:
        c = effective_cell(st["rules"][cat], as_of)
        src = source_ref(rules, c.get("source"))
        L.append(f"- {rules['categories'][cat]['label']} [{c['status']}, {c['confidence']}]: {c.get('summary', '')}"
                 + (f" Next: {c['next']['date']}: {c['next']['summary']}" if c.get("next") else "")
                 + (f" ({src['url']})" if src else ""))
    locs = [l for l in rules["local"] if l["state"] == code]
    if locs:
        L.append("City and county ordinances held: " + ", ".join(l["name"] for l in locs) + ".")
    if st.get("preempts"):
        L.append("Blocks local ordinances on: " + ", ".join(rules["categories"][p["category"]]["label"].lower() for p in st["preempts"]) + ".")
    return "\n".join(L)


# --------------------------------------------------------------------------------------- run
def run(argv=None, rules=None):
    ap = argparse.ArgumentParser(description="Compare hiring and onboarding rules across the states and cities you operate in.")
    ap.add_argument("--sites")
    ap.add_argument("--states")
    ap.add_argument("--state")
    ap.add_argument("--total-employees", type=int)
    ap.add_argument("--locations", type=int)
    ap.add_argument("--as-of")
    ap.add_argument("--md")
    ap.add_argument("--html")
    ap.add_argument("--json")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args(argv)
    if a.test:
        return run_tests()
    rules = rules or load_rules()
    as_of = parse_date(a.as_of) if a.as_of else dt.date.today()
    if a.as_of and not as_of:
        print("REFUSED: --as-of must be YYYY-MM-DD", file=sys.stderr)
        return 2
    try:
        if a.state:
            code = state_code(a.state, rules)
            if not code:
                raise Refused(f"'{a.state}' is not a US state or DC")
            print(render_state(rules, code, as_of))
            return 0
        if a.demo:
            a.sites, a.total_employees = SAMPLE, a.total_employees or SAMPLE_TOTAL
        if a.sites:
            sites, notes = read_sites(a.sites, rules)
            ctx = Context(rules, sites, a.total_employees, a.locations, as_of)
        elif a.states:
            codes = []
            for part in a.states.split(","):
                code = state_code(part, rules)
                if not code:
                    raise Refused(f"'{part.strip()}' is not a US state or DC")
                codes.append(code)
            sites = [{"site_id": c, "state": c, "city": "", "county": "", "headcount": 0, "industry": None, "minors": None, "tipped": None} for c in codes]
            notes = ["No site list: thresholds are shown as 'confirm', and no city ordinance can be matched."]
            ctx = Context(rules, sites, a.total_employees, a.locations, as_of, headcounts_known=a.total_employees is not None)
        else:
            raise Refused("give --sites FILE, --states CA,NY or --state CA (or --demo)")
        out = compare(ctx)
        out["notes"] = notes + out["notes"]
    except Refused as e:
        print(f"REFUSED: {e}.", file=sys.stderr)
        return 2
    print(render_text(out, rules, a.limit))
    if a.md:
        open(a.md, "w", encoding="utf-8").write(render_md(out, rules))
    if a.html:
        open(a.html, "w", encoding="utf-8").write(render_html(out, rules))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1, default=str)
    return 0


# --------------------------------------------------------------------------------------- tests
def run_tests():
    import contextlib
    rules = load_rules()
    fails, passed = [], 0

    def ok(cond, label):
        nonlocal passed
        if cond:
            passed += 1
        else:
            fails.append(label)

    AS_OF = dt.date(2026, 11, 6)
    # 1. integrity of the rules file
    cats = set(rules["order"])
    ok(cats == set(rules["categories"]), "order matches categories")
    ok(len(rules["states"]) == 51, "51 jurisdictions")
    for code, st in rules["states"].items():
        ok(set(st["rules"]) == cats, f"{code} has every category")
        for cat, c in st["rules"].items():
            ok(c["status"] in ("rule", "none", "partial", "check", "upcoming", "repealed"), f"{code}.{cat} status")
            ok(c["confidence"] in ("official", "secondary", "lead"), f"{code}.{cat} confidence")
            ok(c["confidence"] == "lead" or c.get("source"), f"{code}.{cat} has a source unless a lead")
            src = c.get("source")
            ok(src is None or src in rules["sources"] or src.startswith("http"), f"{code}.{cat} source resolves")
            ok(bool(c.get("summary")), f"{code}.{cat} has a summary")
            if c.get("next"):
                ok(parse_date(c["next"]["date"]) is not None, f"{code}.{cat} next date parses")
            if c.get("threshold"):
                ok(isinstance(c["threshold"]["min"], int) and c["threshold"].get("count", "total") in ("total", "in_state", "local"), f"{code}.{cat} threshold shape")
        ok(isinstance(st["rules"]["minimum_wage"].get("rate"), (int, float)), f"{code} minimum wage numeric")
        ok(st["rules"]["new_hire_reporting"].get("days") in (7, 10, 14, 15, 20), f"{code} new hire days")
    ids = [l["id"] for l in rules["local"]]
    ok(len(ids) == len(set(ids)), "local ids unique")
    for l in rules["local"]:
        ok(l["state"] in rules["states"], f"{l['id']} state valid")
        ok(l["scope"] in ("city", "county", "county_unincorporated"), f"{l['id']} scope")
        for cat, c in l["rules"].items():
            ok(cat in cats, f"{l['id']}.{cat} category known")
            src = c.get("source")
            ok(c["confidence"] == "lead" or src, f"{l['id']}.{cat} source")
            ok(src is None or src in rules["sources"] or src.startswith("http"), f"{l['id']}.{cat} source resolves")
    for k, s in rules["sources"].items():
        ok(s["url"].startswith("https://") or s["url"].startswith("http://"), f"source {k} url")
    # facts that must not drift silently
    ok(rules["states"]["ME"]["rules"]["pay_transparency"]["threshold"]["min"] == 10, "ME pay transparency 10+")
    ok(rules["states"]["DE"]["rules"]["pay_transparency"]["next"]["date"] == "2027-09-26", "DE pay transparency date")
    ok(rules["states"]["FL"]["rules"]["e_verify"]["threshold"]["min"] == 25, "FL E-Verify 25+")
    ok(rules["states"]["NY"]["rules"]["minimum_wage"]["regions"][0]["rate"] == 17.0, "NY downstate rate")
    ok(rules["states"]["MO"]["rules"]["paid_sick_leave"]["status"] == "repealed", "MO sick leave repealed")

    def ctx_for(rows, total=None, locations=None, as_of=AS_OF):
        sites = []
        for i, r in enumerate(rows):
            d = {"site_id": f"s{i}", "city": "", "county": "", "headcount": 10, "industry": None, "minors": False, "tipped": None}
            d.update(r)
            sites.append(d)
        return Context(rules, sites, total, locations, as_of)

    # 2. thresholds and dates
    c = ctx_for([{"state": "CT", "headcount": 8}])
    r = state_cell_result(c, "CT", "paid_sick_leave")
    ok(r["state"] == "upcoming", f"CT sick leave below 11 before 2027 is upcoming (got {r['state']})")
    c = ctx_for([{"state": "CT", "headcount": 8}], as_of=dt.date(2027, 1, 2))
    ok(state_cell_result(c, "CT", "paid_sick_leave")["state"] == "applies", "CT sick leave covers 8 people in 2027")
    c = ctx_for([{"state": "CT", "headcount": 12}])
    ok(state_cell_result(c, "CT", "paid_sick_leave")["state"] == "applies", "CT sick leave 12 people now")
    c = ctx_for([{"state": "DE", "headcount": 40}])
    ok(state_cell_result(c, "DE", "pay_transparency")["state"] == "upcoming", "DE pay transparency upcoming")
    c = ctx_for([{"state": "DE", "headcount": 40}], as_of=dt.date(2027, 10, 1))
    ok(state_cell_result(c, "DE", "pay_transparency")["state"] == "applies", "DE pay transparency in force after date")
    c = ctx_for([{"state": "DE", "headcount": 20}], as_of=dt.date(2027, 10, 1))
    ok(state_cell_result(c, "DE", "pay_transparency")["state"] == "below", "DE pay transparency 20 people below 26")
    c = ctx_for([{"state": "NV", "headcount": 30}])
    r = state_cell_result(c, "NV", "paid_sick_leave")
    ok(r["state"] == "below" and "50+" in r["why"], "NV sick leave in-state 50+")
    c = ctx_for([{"state": "NV", "headcount": 30}, {"state": "TX", "headcount": 500}])
    ok(state_cell_result(c, "NV", "paid_sick_leave")["state"] == "below", "NV counts in-state, not total")
    c = ctx_for([{"state": "NC", "headcount": 20}, {"state": "TX", "headcount": 500}])
    ok(state_cell_result(c, "NC", "e_verify")["state"] == "below", "NC E-Verify counts NC employees")
    c = ctx_for([{"state": "FL", "headcount": 20}, {"state": "TX", "headcount": 500}])
    ok(state_cell_result(c, "FL", "e_verify")["state"] == "applies", "FL E-Verify counts all employees")
    c = ctx_for([{"state": "WA", "headcount": 10}])
    r = state_cell_result(c, "WA", "fair_chance")
    ok(r["state"] == "applies" and r["cell"]["stage"] == 2, "WA fair chance under 15 keeps older rule")
    c = ctx_for([{"state": "WA", "headcount": 10}, {"state": "OR", "headcount": 10}])
    ok(state_cell_result(c, "WA", "fair_chance")["cell"]["stage"] == 3, "WA threshold counts all employees, as recorded")
    c = ctx_for([{"state": "WA", "headcount": 30}])
    ok(state_cell_result(c, "WA", "fair_chance")["cell"]["stage"] == 3, "WA 15+ conditional offer")
    c = ctx_for([{"state": "WA", "headcount": 10}], as_of=dt.date(2027, 1, 2))
    ok(state_cell_result(c, "WA", "fair_chance")["cell"]["stage"] == 3, "WA all sizes from 2027")
    c = ctx_for([{"state": "NY", "headcount": 120}])
    r = state_cell_result(c, "NY", "paid_sick_leave")
    ok(r["tier"]["cap"] == 56, "NY 100+ tier 56")
    c = ctx_for([{"state": "NY", "headcount": 3}])
    ok(state_cell_result(c, "NY", "paid_sick_leave")["tier"]["paid"] == "check", "NY micro tier paid depends on income")
    c = ctx_for([{"state": "NE", "headcount": 9}])
    ok(state_cell_result(c, "NE", "paid_sick_leave")["state"] == "below", "NE 10 or fewer exempt")
    c = ctx_for([{"state": "MD", "headcount": 60, "industry": "retail"}])
    ok(state_cell_result(c, "MD", "meal_breaks")["state"] == "applies", "MD meal retail 50+")
    c = ctx_for([{"state": "MD", "headcount": 60, "industry": "warehouse"}])
    ok(state_cell_result(c, "MD", "meal_breaks")["state"] == "not_covered", "MD meal not warehouse")
    c = ctx_for([{"state": "MD", "headcount": 60, "industry": None}])
    ok(state_cell_result(c, "MD", "meal_breaks")["state"] == "check", "MD meal unknown industry is check")
    c = ctx_for([{"state": "OR", "headcount": 40, "industry": "retail"}], total=600)
    ok(state_cell_result(c, "OR", "predictive_scheduling")["state"] == "applies", "OR scheduling 500+ worldwide")
    c = ctx_for([{"state": "OR", "headcount": 40, "industry": "retail"}])
    ok(state_cell_result(c, "OR", "predictive_scheduling")["state"] == "below", "OR scheduling below 500")
    c = ctx_for([{"state": "MI", "headcount": 5}], as_of=dt.date(2027, 1, 2))
    ok(effective_cell(rules["states"]["MI"]["rules"]["minimum_wage"], dt.date(2027, 1, 2))["rate"] == 15.0, "MI $15 after Jan 2027")
    ok(effective_cell(rules["states"]["CA"]["rules"]["minimum_wage"], dt.date(2027, 1, 2))["rate"] == 17.40, "CA announced 2027 rate")
    ok(effective_cell(rules["states"]["VT"]["rules"]["minimum_wage"], dt.date(2027, 1, 2))["status"] == "check", "VT unannounced indexed rate becomes check in 2027")
    ok(effective_cell(rules["states"]["CA"]["rules"]["minimum_wage"], AS_OF)["status"] == "rule", "CA rate in force now")
    ok(state_cell_result(ctx_for([{"state": "MO"}]), "MO", "paid_sick_leave")["state"] == "repealed", "MO repealed")

    # 3. minimum wage by site
    def mw(row, as_of=AS_OF):
        c = ctx_for([row], as_of=as_of)
        return site_min_wage(c, c.sites[0])
    ok(mw({"state": "NY", "city": "Brooklyn"})[0] == 17.0, "Brooklyn $17")
    ok(mw({"state": "NY", "city": "Albany", "county": "Albany"})[0] == 16.0, "Albany $16")
    ok(mw({"state": "NY", "city": "Yonkers", "county": "Westchester"})[0] == 17.0, "Westchester $17")
    ok("no county" in " ".join(mw({"state": "NY", "city": "Albany"})[2]), "NY no county flagged")
    ok(mw({"state": "OR", "city": "Portland", "county": "Multnomah"})[0] == 16.8, "Portland OR metro")
    ok(mw({"state": "OR", "city": "Pendleton", "county": "Umatilla"})[0] == 14.55, "OR non-urban")
    ok(mw({"state": "OR", "city": "Salem", "county": "Marion"})[0] == 15.55, "OR standard")
    ok(mw({"state": "WA", "city": "Seattle"})[0] == 21.30, "Seattle $21.30")
    ok(mw({"state": "WA", "city": "Seattle"}, as_of=dt.date(2027, 1, 2))[0] == 22.14, "Seattle 2027")
    ok(mw({"state": "NY", "city": "Brooklyn"}, as_of=dt.date(2027, 1, 2))[0] == 17.0, "NY unchanged in 2027 (off-ramp)")
    ok(mw({"state": "WA", "city": "Spokane"})[0] == 17.13, "Spokane state rate")
    ok(mw({"state": "CA", "city": "San Francisco"})[0] == 19.61, "SF")
    ok(mw({"state": "CA", "city": "Fresno"})[0] == 16.90, "Fresno state")
    ok(mw({"state": "TX", "city": "Austin"})[0] == 7.25, "TX federal")
    ok(mw({"state": "GA", "city": "Atlanta"})[0] == 7.25, "GA federal over $5.15")
    ok(mw({"state": "IL", "city": "Chicago"})[0] == 17.05, "Chicago rate")
    ok(mw({"state": "TX", "city": "Lubbock"})[0] == 7.25 and rules["states"]["TX"]["rules"]["minimum_wage"]["status"] == "none", "TX shown as no rate above federal")
    ok(mw({"state": "CA", "city": "", "county": "Los Angeles"})[0] == 18.47, "LA County unincorporated")
    ok(mw({"state": "CA", "city": "Unincorporated", "county": "Los Angeles"})[0] == 18.47, "LA County unincorporated keyword")
    ok(mw({"state": "CA", "city": "Long Beach", "county": "Los Angeles"})[0] == 16.90, "Long Beach not unincorporated")
    ok(mw({"state": "MN", "city": "St. Paul"})[0] == 16.37, "St. Paul alias")
    ok(mw({"state": "ME", "city": "Portland"})[0] == 16.75, "Portland ME not Portland OR")
    ok(mw({"state": "CO", "city": "Boulder"}, as_of=dt.date(2027, 1, 5))[0] == 18.17, "Boulder 2027 step")

    # 4. locals and strictest
    c = ctx_for([{"state": "PA", "city": "Philadelphia", "industry": "warehouse", "headcount": 300}], total=900, locations=40)
    out = compare(c)
    pf = [l for l in out["site_tier"][0]["local"] if l["category"] == "predictive_scheduling"][0]
    ok(pf["result"] == "not_covered", "Philadelphia fair workweek does not cover warehouses")
    c = ctx_for([{"state": "PA", "city": "Philadelphia", "industry": "retail", "headcount": 300}], total=900, locations=40)
    pf = [l for l in compare(c)["site_tier"][0]["local"] if l["category"] == "predictive_scheduling"][0]
    ok(pf["result"] == "applies", "Philadelphia fair workweek covers retail 250+ and 30+ locations")
    c = ctx_for([{"state": "PA", "city": "Philadelphia", "industry": "retail", "headcount": 300}], total=900, locations=12)
    pf = [l for l in compare(c)["site_tier"][0]["local"] if l["category"] == "predictive_scheduling"][0]
    ok(pf["result"] == "below", "Philadelphia below 30 locations")
    c = ctx_for([{"state": "CA", "city": "Los Angeles", "headcount": 20, "industry": "retail"}, {"state": "TX", "city": "Dallas", "headcount": 10}], total=400)
    out = compare(c)
    ok("conditional offer" in out["strictest"]["fair_chance"], "strictest fair chance is conditional offer")
    ok(out["strictest"]["minimum_wage"].startswith("$18.42"), "strictest minimum wage is LA")
    ok("hour 5" in out["strictest"]["meal_breaks"], "strictest meal by hour 5")
    tx = [s for s in out["site_tier"] if s["state"] == "TX"][0]
    ok("paid_sick_leave" in tx["preempted"] and "minimum_wage" in tx["preempted"], "TX preemption listed")
    ok(out["grid"]["pay_transparency"]["CA"]["result"] == "applies" and out["grid"]["pay_transparency"]["TX"]["result"] == "none", "grid basics")
    c = ctx_for([{"state": "IL", "city": "Chicago", "headcount": 30, "industry": "retail"}], total=150)
    out = compare(c)
    ok(any("Chicago" in i["question"] or "Chicago" in i["where"] for i in out["checklist"]), "Chicago items in checklist")
    ok("hours" in out["strictest"]["predictive_scheduling"], "Chicago fair workweek strictest")
    c = ctx_for([{"state": "ME", "city": "Lewiston", "headcount": 20, "minors": True}, {"state": "TX", "city": "Houston", "headcount": 400}])
    out = compare(c)
    ok(out["checklist"][0]["category"] == "minors_work_permit", "minors pulled to the top of the checklist")
    ok(out["grid"]["minors_work_permit"]["TX"]["result"] in ("none", "not_covered"), "TX minors not flagged")
    c = ctx_for([{"state": "AZ", "headcount": 20, "minors": False}])
    ok(compare(c)["grid"]["minors_work_permit"]["AZ"]["result"] == "none", "AZ no certificates")
    c = ctx_for([{"state": "CA", "headcount": 20, "minors": False}])
    ok(compare(c)["grid"]["minors_work_permit"]["CA"]["result"] == "not_covered", "minors only where flagged")
    out = compare(ctx_for([{"state": "DE", "headcount": 40}]))
    ok(any(u["state"] == "DE" and u["category"] == "pay_transparency" for u in out["upcoming"]), "DE in upcoming")
    out = compare(ctx_for([{"state": "CA", "headcount": 40}], as_of=dt.date(2027, 8, 1)))
    ok(any("re-check" in n for n in out["notes"]), "stale file warned")

    # 5. reading the site file, refusals
    def write(text, binary=False):
        fd, p = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "wb") as fh:
            fh.write(text if binary else text.encode("utf-8"))
        return p

    def refused(text, label, binary=False):
        p = write(text, binary)
        try:
            read_sites(p, rules)
            ok(False, "should refuse: " + label)
        except Refused:
            ok(True, label)
        finally:
            os.unlink(p)

    refused("", "empty file")
    refused("state,headcount\n", "header only")
    refused("site,headcount\nA,10\n", "missing state")
    refused("state,city\nCA,LA\n", "missing headcount")
    refused("state,headcount\nZZ,10\n", "bad state")
    refused("state,headcount\nCA,ten\n", "headcount not a number")
    refused("state,headcount\nCA,-4\n", "negative headcount")
    refused("state,headcount,employee_name\nCA,1,Ana\n", "personal column name")
    refused("state,headcount,Email\nCA,1,a@b.c\n", "email column")
    refused("state,headcount,SSN\nCA,1,1\n", "ssn column")
    refused("state,headcount,date_of_birth\nCA,1,1\n", "dob column")
    refused("state,headcount,hourly_rate\nCA,1,17\n", "individual pay column")
    refused("state,headcount,store_manager\nCA,1,Ana\n", "manager name column")
    p = write("store_name,state,headcount,avg_hourly_rate,district\nMain St,CA,12,18.5,West\n")
    ok(len(read_sites(p, rules)[0]) == 1, "store_name and avg_hourly_rate are site data, not personal")
    os.unlink(p)
    refused("site_id,state,headcount\nA,CA,1\nA,NY,2\n", "duplicate site")
    refused("state,headcount\n" + "CA,1\n" * (MAX_ROWS + 1), "too many rows")
    refused("state,headcount\nCA,0\n", "all zero")
    refused("state,headcount,minors\nCA,4,maybe\n", "minors not yes/no")
    refused("state,headcount\nCalifornie,\xe9t\xe9\n".encode("latin-1"), "not utf-8", binary=True)
    p = write("Store #,State,City,County,Employees,Format,Under 18,Address\n1,California,San Francisco,,40,grocery,yes,1 Main St\n2,n.y.,Brooklyn,Kings,25,Cafe,no,x\n3,dc,Washington,,5,hotel,,\n")
    sites, notes = read_sites(p, rules)
    os.unlink(p)
    ok(len(sites) == 3 and sites[0]["state"] == "CA" and sites[1]["state"] == "NY" and sites[2]["state"] == "DC", "aliases and state names")
    ok(sites[0]["industry"] == "retail" and sites[1]["industry"] == "food_service" and sites[2]["industry"] == "hospitality", "industry aliases")
    ok(sites[0]["minors"] is True and sites[1]["minors"] is False, "minors parsed")
    ok(any("Address" in n for n in notes), "address column ignored with a note")
    p = write("state;headcount\nWA;12\n")
    ok(read_sites(p, rules)[0][0]["headcount"] == 12, "semicolon delimiter")
    os.unlink(p)
    try:
        Context(rules, [{"site_id": "a", "state": "CA", "city": "", "county": "", "headcount": 50, "industry": None, "minors": None, "tipped": None}], total=10)
        ok(False, "total below sum refused")
    except Refused:
        ok(True, "total below sum refused")

    # 6. the sample employer: planted findings
    sites, _ = read_sites(SAMPLE, rules)
    out = compare(Context(rules, sites, SAMPLE_TOTAL, None, AS_OF))
    tier = {s["site_id"]: s for s in out["site_tier"]}
    g = out["grid"]
    ok(len(sites) == 20 and len(out["states"]) == 15, f"sample: 20 sites in 15 states (got {len(sites)}, {len(out['states'])})")
    ok(out["strictest"]["minimum_wage"].startswith("$21.30"), "sample: Seattle sets the national rate")
    ok(g["paid_sick_leave"]["CT"]["result"] == "upcoming", "sample: CT sick leave becomes due January 2027")
    ok(g["paid_sick_leave"]["NV"]["result"] == "below", "sample: NV sick leave below 50 in-state")
    ok(g["pay_transparency"]["DE"]["result"] == "upcoming", "sample: DE pay transparency coming")
    ok(g["pay_transparency"]["ME"]["result"] == "applies", "sample: ME pay transparency applies")
    ok(g["e_verify"]["FL"]["result"] == "applies" and g["e_verify"]["GA"]["result"] == "applies", "sample: E-Verify FL and GA")
    ok(g["fair_chance"]["WA"]["numbers"]["stage"] == 3, "sample: WA conditional offer")
    phl = [l for l in tier["HP-PHL-DC1"]["local"] if l["category"] == "predictive_scheduling"]
    ok(phl and phl[0]["result"] == "not_covered", "sample: Philadelphia DC not covered by fair workweek")
    ok(g["paid_sick_leave"]["PA"]["result"] == "local" and "Philadelphia" in g["paid_sick_leave"]["PA"]["why"], "sample: PA sick leave row shows Philadelphia's ordinance")
    ok(g["predictive_scheduling"]["WA"]["result"] == "local" and g["predictive_scheduling"]["PA"]["result"] == "none", "sample: scheduling row shows cities, not Philadelphia's warehouse")
    ok(tier["HP-NYC-01"]["min_wage"] == 17.0 and tier["HP-ALB-01"]["min_wage"] == 16.0, "sample: NY regional rates")
    ok(tier["HP-CHI-01"]["min_wage"] == 17.05 and tier["HP-CHI-01"]["min_wage_from"] == "Chicago", "sample: Chicago $17.05")
    ok(tier["HP-LAX-02"]["min_wage"] == 18.47, "sample: LA County unincorporated rate")
    ok(any(l["local"] == "Los Angeles" and l["category"] == "predictive_scheduling" and l["result"] == "applies" for l in tier["HP-LAX-01"]["local"]), "sample: LA fair work week applies")
    ok(any(l["local"] == "Seattle" and l["category"] == "predictive_scheduling" and l["result"] == "applies" for l in tier["HP-SEA-01"]["local"]), "sample: Seattle secure scheduling applies")
    ok(tier["HP-ATX-01"]["preempted"] and any(l["result"] == "check" for l in tier["HP-ATX-01"]["local"]), "sample: Austin preempted topics and fair chance to check")
    ok(out["checklist"][0]["category"] == "minors_work_permit", "sample: minors first in checklist")
    ok(any(i["where"].startswith("HP-NOCITY") for i in out["checklist"]), "sample: site with no city flagged")
    ok(any(u["state"] == "VA" or u["state"] == "MI" or u["state"] == "CT" for u in out["upcoming"]), "sample: upcoming has dated changes")
    md = render_md(out, rules)
    ok("| Paid sick leave |" in md and "Research checklist" in md, "markdown renders")
    h = render_html(out, rules)
    ok(h.startswith("<!doctype html>") and "<script" not in h, "html renders without scripts")
    ok("Not legal advice" in render_text(out, rules) or "Rules checked" in render_text(out, rules), "text renders")

    # 7. states mode and state mode
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rc = run(["--states", "CA,New York,tx", "--as-of", "2026-11-06"], rules)
    pay_line = buf.getvalue().split("Pay range disclosure:")[1].split("\n")[0]
    ok(rc == 0 and "3 states" in buf.getvalue(), "states mode runs")
    ok("CA" in pay_line and "NY" in pay_line and "TX" not in pay_line, "states mode lists CA and NY pay range laws, not TX")
    sites3 = [{"site_id": c, "state": c, "city": "", "county": "", "headcount": 0, "industry": None, "minors": None, "tipped": None} for c in ("MA", "NV", "CT")]
    c3 = Context(rules, sites3, 5000, None, AS_OF, headcounts_known=True)
    ok(state_cell_result(c3, "MA", "pay_transparency")["state"] == "check", "states mode: in-state threshold is a check, not below")
    ok(state_cell_result(c3, "NV", "paid_sick_leave")["state"] == "check", "states mode: NV in-state 50+ is a check")
    ok(state_cell_result(c3, "CA" if False else "MA", "paid_sick_leave")["state"] == "applies", "states mode: total-count tiers use the given total")
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        rc = run(["--state", "maine", "--as-of", "2026-11-06"], rules)
    ok(rc == 0 and "622-A" in buf.getvalue(), "state mode")
    with contextlib.redirect_stderr(io.StringIO()):
        ok(run(["--state", "Atlantis"], rules) == 2, "state mode refuses unknown state")
        ok(run(["--as-of", "2026-13-40", "--demo"], rules) == 2, "bad as-of refused")

    # 8. fuzz: random site files never crash
    rnd = random.Random(7)
    codes = list(rules["states"])
    cities = ["Seattle", "Brooklyn", "", "Chicago", "Portland", "St Paul", "Los Angeles", "Austin", "Nowhere", "Unincorporated"]
    crashes = 0
    for k in range(300):
        rows = ["site_id,state,city,county,headcount,industry,minors"]
        for j in range(rnd.randint(1, 30)):
            rows.append(",".join([f"x{j}", rnd.choice(codes + ["", "ZZ", "Texas"]), rnd.choice(cities), rnd.choice(["", "Los Angeles", "Cook", "Kings", "Multnomah"]),
                                  str(rnd.choice([0, 1, 5, 14, 15, 49, 50, 99, 100, 499, 500, "", "x"])), rnd.choice(["", "retail", "warehouse", "spaceport"]), rnd.choice(["yes", "no", ""])]))
        p = write("\n".join(rows) + "\n")
        try:
            s, _ = read_sites(p, rules)
            o = compare(Context(rules, s, None, rnd.choice([None, 5, 50]), AS_OF + dt.timedelta(days=rnd.randint(0, 900))))
            render_md(o, rules)
            render_html(o, rules)
        except Refused:
            pass
        except Exception as e:      # a crash is a failure
            crashes += 1
            fails.append(f"fuzz crash {k}: {type(e).__name__}: {e}")
        finally:
            os.unlink(p)
    ok(crashes == 0, "fuzz: no crashes in 300 random files")

    total = passed + len(fails)
    if fails:
        print(f"{len(fails)} of {total} checks failed:")
        for f in fails[:40]:
            print("  FAIL", f)
        return 1
    print(f"all {total} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
