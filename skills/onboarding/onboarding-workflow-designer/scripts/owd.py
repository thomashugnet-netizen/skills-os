#!/usr/bin/env python3
"""
Onboarding Workflow Designer: the checker, the renderer and the fallback log reader.

The workflow is a JSON file (shape in SKILL.md). Every claim the design makes is
something this script can test: who owns each step, when it must be done, what it
waits for, what happens when it stalls, and whether a person confirmed it.

    python3 owd.py check    workflow.json                 # findings, exit 1 if not ready
    python3 owd.py render   workflow.json --html out.html # timeline, category, owner views
    python3 owd.py render   workflow.json --md out.md     # terse document, PRD-ready
    python3 owd.py clone    past.json -o draft.json --name "..." [--states CA,TX]
    python3 owd.py confirm  draft.json --steps a,b | --all -o draft.json
    python3 owd.py log      workflow.json events.csv      # which fallbacks fire too often
    python3 owd.py --test

Standard library only. Same input, same output.
"""

import csv
import html
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
RULES_PATH = os.path.join(SKILL, "references", "compliance_rules.json")

CATEGORIES = [
    "Work authorization & legal filings",
    "Payroll & pay setup",
    "Policy acknowledgements",
    "Required training & certification",
    "Scheduling & first shift readiness",
    "Equipment & logistics",
    "Access & identity",
    "Connection & engagement",
]
TAGS = {
    "legally_required": "A law or regulation requires it",
    "blocks_first_shift": "The first shift cannot happen until it is done",
    "external_dependency": "Someone outside your team does it (vendor, agency, trainer)",
    "needs_hire_action": "The new hire has to do something",
    "can_follow_first_shift": "Allowed to finish after the first shift",
    "fixed_date": "Runs on fixed dates only (e.g. induction on Tuesdays)",
}
NEEDS_FALLBACK = {"blocks_first_shift", "external_dependency", "needs_hire_action"}
SHAPES = {
    "chase": "Late but not blocked: send a second request",
    "substitute": "Another route reaches the same outcome",
    "conditional_start": "Not blocking: finish during week one",
    "move_shift": "Blocking and will not clear in time: move the first shift",
    "stop": "Cannot clear: withdraw the offer and tell the hire that day",
}
SOURCES = {"user", "template", "cloned", "inferred"}
START = "offer_accepted"

VAGUE = [
    "ensure", "make sure", "as needed", "as soon as possible", "asap",
    "appropriate", "appropriately", "handle", "handled", "coordinate",
    "support", "follow up", "follow-up", "manage", "if possible", "try to",
    "etc", "various", "relevant", "timely", "promptly", "when possible",
    "as required", "where necessary", "tbd",
]
VAGUE_DONE = ["is complete", "is completed", "is done", "is finished",
              "has been done", "has been handled", "all good", "ready to go"]
NOT_AN_OWNER = {
    "", "hr", "human resources", "onboarding", "the team", "team", "everyone",
    "anyone", "tbd", "shared inbox", "ops", "operations", "management",
    "admin", "n/a", "na", "?",
}
GROUP_WORDS = re.compile(r"\b(team|teams|inbox|department|group|everyone|staff)\b(?!\s+(lead|leader|manager|member))", re.I)
TWO_OWNERS = re.compile(r"(/|&|,|\+|\band\b|\bor\b)", re.I)
# Reasons for making a step wait that protect effort, not the hire. The step is
# not wrong, but the wait costs days and the reason should be priced.
WEAK_NEEDS = re.compile(
    r"(waste|wasted|in case|might fail|may fail|save (money|cost|effort)|"
    r"always (been )?done|standard order|that'?s how|policy order|just in case)",
    re.I)

BLOCKING = "blocking"
CARE = "care"


class Refusal(Exception):
    """The file is not a workflow this script can reason about."""


# ---------------------------------------------------------------- loading

def load_rules(path=RULES_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_workflow(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise Refusal(f"{path} is not valid JSON: {e}")
    shape(data)
    return data


def shape(wf):
    """Refuse anything whose structure would make the findings meaningless.
    Every refusal names the field."""
    if not isinstance(wf, dict):
        raise Refusal("the workflow must be a JSON object")
    for key in ("workflow", "status", "offer_to_first_shift_days", "steps"):
        if key not in wf:
            raise Refusal(f"missing top-level field '{key}'")
    if wf["status"] not in ("draft", "final"):
        raise Refusal("'status' must be 'draft' or 'final'")
    gap = wf["offer_to_first_shift_days"]
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 0:
        raise Refusal("'offer_to_first_shift_days' must be a whole number of days, 0 or more")
    steps = wf["steps"]
    if not isinstance(steps, list) or not steps:
        raise Refusal("'steps' must be a non-empty list")
    seen = set()
    for i, s in enumerate(steps):
        where = f"steps[{i}]"
        if not isinstance(s, dict):
            raise Refusal(f"{where} must be an object")
        sid = s.get("id")
        if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9_]+", sid or ""):
            raise Refusal(f"{where}.id must be lowercase letters, digits and underscores")
        if sid == START:
            raise Refusal(f"{where}.id '{START}' is reserved for the moment the offer is accepted")
        if sid in seen:
            raise Refusal(f"duplicate step id '{sid}'")
        seen.add(sid)
        where = f"step '{sid}'"
        if s.get("category") not in CATEGORIES:
            raise Refusal(f"{where}.category must be one of: {', '.join(CATEGORIES)}")
        for key in ("duration_days", "due_day"):
            v = s.get(key)
            if not isinstance(v, int) or isinstance(v, bool):
                raise Refusal(f"{where}.{key} must be a whole number of days")
        if s["duration_days"] < 0:
            raise Refusal(f"{where}.duration_days cannot be negative")
        nb = s.get("not_before_day")
        if nb is not None and (not isinstance(nb, int) or isinstance(nb, bool)):
            raise Refusal(f"{where}.not_before_day must be a whole number of days")
        tags = s.get("tags", [])
        if not isinstance(tags, list) or any(t not in TAGS for t in tags):
            raise Refusal(f"{where}.tags must be a list drawn from: {', '.join(TAGS)}")
        after = s.get("after", [START])
        if not isinstance(after, list) or not after:
            raise Refusal(f"{where}.after must be a non-empty list of step ids or '{START}'")
        if s.get("source", "user") not in SOURCES:
            raise Refusal(f"{where}.source must be one of: {', '.join(sorted(SOURCES))}")
        if not isinstance(s.get("validated", False), bool):
            raise Refusal(f"{where}.validated must be true or false")
        fb = s.get("fallback")
        if fb is not None:
            if not isinstance(fb, dict):
                raise Refusal(f"{where}.fallback must be an object")
            if fb.get("shape") not in SHAPES:
                raise Refusal(f"{where}.fallback.shape must be one of: {', '.join(SHAPES)}")
            v = fb.get("after_days")
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise Refusal(f"{where}.fallback.after_days must be a whole number, 0 or more")
    for s in steps:
        for dep in s.get("after", [START]):
            if dep != START and dep not in seen:
                raise Refusal(f"step '{s['id']}' waits for unknown step '{dep}'")
    order(steps)  # raises on a cycle


def order(steps):
    """Topological order. A cycle is a refusal: there is no schedule to check."""
    by_id = {s["id"]: s for s in steps}
    state, out = {}, []

    def visit(sid, path):
        if state.get(sid) == 2:
            return
        if state.get(sid) == 1:
            loop = path[path.index(sid):] + [sid]
            raise Refusal("steps wait for each other in a loop: " + " -> ".join(loop))
        state[sid] = 1
        for dep in by_id[sid].get("after", [START]):
            if dep != START:
                visit(dep, path + [sid])
        state[sid] = 2
        out.append(sid)

    for s in steps:
        visit(s["id"], [])
    return out


# ---------------------------------------------------------------- schedule

def schedule(wf):
    """Day numbers relative to the first shift (day 0). The offer is accepted
    on day -gap. Each step starts when everything it waits for has finished."""
    steps = {s["id"]: s for s in wf["steps"]}
    gap = wf["offer_to_first_shift_days"]
    start, finish, parent = {}, {}, {}
    for sid in order(wf["steps"]):
        s = steps[sid]
        best, via = -gap, START
        for dep in s.get("after", [START]):
            t = -gap if dep == START else finish[dep]
            if t > best:
                best, via = t, dep
        nb = s.get("not_before_day")
        if nb is not None and nb > best:
            best, via = nb, START  # a fixed day, not a dependency, sets the start
        start[sid] = best
        finish[sid] = best + s["duration_days"]
        parent[sid] = via
    blockers = [sid for sid, s in steps.items() if "blocks_first_shift" in s.get("tags", [])]
    path, earliest = [], None
    if blockers:
        end = max(blockers, key=lambda x: (finish[x], x))
        earliest = finish[end] + gap  # shortest offer-to-first-shift the design allows
        node = end
        while node != START:
            path.append(node)
            node = parent[node]
        path.reverse()
    parallel = sorted(sid for sid, s in steps.items() if s.get("after", [START]) == [START])
    return {"start": start, "finish": finish, "critical_path": path,
            "earliest_gap": earliest, "parallel_block": parallel}


def ancestors(steps_by_id, sid):
    seen, stack = set(), list(steps_by_id[sid].get("after", [START]))
    while stack:
        d = stack.pop()
        if d == START or d in seen:
            continue
        seen.add(d)
        stack.extend(steps_by_id[d].get("after", [START]))
    return seen


# ---------------------------------------------------------------- check

def owner_problem(name):
    """None when `name` is one role or one person; otherwise the finding code."""
    n = str(name or "").strip()
    if n.lower() in NOT_AN_OWNER or GROUP_WORDS.search(n):
        return "NO_OWNER"
    if TWO_OWNERS.search(n):
        return "TWO_OWNERS"
    return None


def words(text):
    return len(str(text).split())


def vague_in(text, extra=()):
    low = " " + re.sub(r"[^a-z0-9/ -]", " ", str(text).lower()) + " "
    return [v for v in list(VAGUE) + list(extra)
            if re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", low)]


def check(wf, rules=None):
    rules = rules or load_rules()
    shape(wf)
    findings = []

    def add(code, severity, step, msg):
        findings.append({"code": code, "severity": severity, "step": step, "message": msg})

    steps = wf["steps"]
    by_id = {s["id"]: s for s in steps}
    sch = schedule(wf)
    gap = wf["offer_to_first_shift_days"]

    for s in steps:
        sid, tags = s["id"], set(s.get("tags", []))

        # Action and definition of done: short, concrete, testable.
        action = str(s.get("action", "")).strip()
        done = str(s.get("done_when", "")).strip()
        if not action:
            add("ACTION_MISSING", BLOCKING, sid, "no action written")
        else:
            if words(action) > 14:
                add("ACTION_LONG", CARE, sid, f"action is {words(action)} words; keep it to 14")
            v = vague_in(action)
            if v:
                add("VAGUE_ACTION", BLOCKING, sid, f"action uses '{v[0]}', which nobody can check")
        if not done:
            add("DONE_MISSING", BLOCKING, sid, "no done_when: nobody can say whether this step happened")
        else:
            v = vague_in(done, VAGUE_DONE)
            if words(done) < 3:
                add("VAGUE_DONE", BLOCKING, sid, f"done_when '{done}' does not say what proves it; name the record or event")
            elif v:
                add("VAGUE_DONE", BLOCKING, sid, f"done_when uses '{v[0]}'; name the record, document or event that proves it")
            elif done.lower() == action.lower():
                add("VAGUE_DONE", BLOCKING, sid, "done_when repeats the action; name what proves it happened")
            if words(done) > 20:
                add("DONE_LONG", CARE, sid, f"done_when is {words(done)} words; keep it to 20")

        # One owner, a role or a named person, never a team.
        owner = str(s.get("owner", "")).strip()
        prob = owner_problem(owner)
        if prob == "NO_OWNER":
            add("NO_OWNER", BLOCKING, sid,
                "no single owner" if not owner else f"'{owner}' is a group, not an owner; name one role or person")
        elif prob == "TWO_OWNERS":
            add("TWO_OWNERS", BLOCKING, sid, f"'{owner}' names more than one owner; two owners is nobody")

        # Why it waits.
        deps = [d for d in s.get("after", [START]) if d != START]
        if deps:
            needs = str(s.get("needs", "")).strip()
            if not needs:
                add("WAIT_UNEXPLAINED", BLOCKING, sid,
                    f"waits for {', '.join(deps)} but does not say what it needs from it")
            elif WEAK_NEEDS.search(needs):
                add("WAIT_TO_SAVE_EFFORT", CARE, sid,
                    f"waits for {', '.join(deps)} to save effort ('{needs}'); every day of wait is a day the hire can take another offer")

        # Timing against its own deadline and the first shift.
        fin, due = sch["finish"][sid], s["due_day"]
        if fin > due:
            add("LATE", BLOCKING, sid, f"earliest finish is day {fin:+d}, after its deadline day {due:+d}")
        if "blocks_first_shift" in tags:
            if "can_follow_first_shift" in tags:
                add("TAG_CONFLICT", BLOCKING, sid, "tagged both blocks_first_shift and can_follow_first_shift")
            if due > 0:
                add("BLOCKER_AFTER_START", BLOCKING, sid, f"blocks the first shift but is due on day {due:+d}")
            if fin > 0:
                add("BLOCKS_START", BLOCKING, sid,
                    f"blocks the first shift and cannot finish before day {fin:+d}; the first shift needs a gap of at least {fin + gap} days")
        if due > 0 and "can_follow_first_shift" not in tags and not s.get("rule"):
            add("UNTAGGED_AFTER_START", CARE, sid,
                f"due day {due:+d} is after the first shift but the step is not tagged can_follow_first_shift")

        # Every step that can stall gets a plan, and the plan is logged.
        fb = s.get("fallback")
        if tags & NEEDS_FALLBACK:
            if not fb:
                why = sorted(tags & NEEDS_FALLBACK)[0]
                add("NO_FALLBACK", BLOCKING, sid, f"tagged {why} but has no fallback")
        if fb:
            if owner_problem(fb.get("alert")):
                add("FALLBACK_NO_ALERT", BLOCKING, sid, "fallback does not name who is alerted")
            fa = str(fb.get("action", "")).strip()
            if not fa:
                add("FALLBACK_NO_ACTION", BLOCKING, sid, "fallback does not say what is done")
            elif vague_in(fa):
                add("VAGUE_FALLBACK", BLOCKING, sid, f"fallback uses '{vague_in(fa)[0]}'")
            if fb["shape"] in ("move_shift", "stop") and owner_problem(fb.get("decider")):
                add("FALLBACK_NO_DECIDER", BLOCKING, sid, f"a '{fb['shape']}' fallback needs one named decider")
            if fb["shape"] == "conditional_start" and "blocks_first_shift" in tags:
                add("TAG_CONFLICT", BLOCKING, sid, "a step that blocks the first shift cannot fall back to starting without it")
            if fb["after_days"] > max(s["duration_days"], 0) + 7:
                add("FALLBACK_SLOW", CARE, sid,
                    f"fallback fires {fb['after_days']} days after the step starts; a week past its normal duration is too late to help")

        # Legal steps carry a rule or a confirmed basis.
        if "legally_required" in tags and not s.get("rule") and words(s.get("legal_basis", "")) < 4:
            add("LEGAL_UNSOURCED", BLOCKING, sid,
                "tagged legally_required with neither a rule id nor a legal_basis that says what requires it")
        rid = s.get("rule")
        if rid and rid not in rules["rules"]:
            add("UNKNOWN_RULE", BLOCKING, sid, f"rule '{rid}' is not in compliance_rules.json")

        # Nothing unconfirmed goes into a final document.
        if not s.get("validated", False):
            add("UNVALIDATED", BLOCKING, sid,
                f"not confirmed by a person (source: {s.get('source', 'user')}); confirm it or change it")

    # Workflow-level rules.
    stop = wf.get("stop_rule") or {}
    if (not str(stop.get("when", "")).strip() or owner_problem(stop.get("who_tells_hire"))
            or owner_problem(stop.get("decider"))):
        add("NO_STOP_RULE", BLOCKING, None,
            "no stop rule (when, decider, who_tells_hire): without one, a hire who cannot clear waits in silence")

    findings.extend(compliance(wf, sch, by_id, rules))
    findings.extend(dead_air(wf, sch))

    blocking = [f for f in findings if f["severity"] == BLOCKING]
    unvalidated = sum(1 for f in findings if f["code"] == "UNVALIDATED")
    return {
        "workflow": wf["workflow"],
        "status": wf["status"],
        "ready": not blocking,
        "blocking": len(blocking),
        "care": len(findings) - len(blocking),
        "unvalidated": unvalidated,
        "earliest_gap": sch["earliest_gap"],
        "planned_gap": wf["offer_to_first_shift_days"],
        "critical_path": sch["critical_path"],
        "parallel_block": sch["parallel_block"],
        "findings": findings,
        "schedule": sch,
    }


def compliance(wf, sch, by_id, rules):
    out = []
    j = wf.get("jurisdiction") or {}
    if j.get("country") != "US":
        out.append({"code": "JURISDICTION_NOT_CHECKED", "severity": CARE, "step": None,
                    "message": "no rules for this country; every legal step stands on the legal_basis you give it"})
        return out
    active = {"US"} | ({"US_E_VERIFY"} if j.get("e_verify") else set())
    by_rule = {}
    for s in wf["steps"]:
        if s.get("rule"):
            by_rule.setdefault(s["rule"], []).append(s)
    for rid, rule in rules["rules"].items():
        if rule["applies"] not in active:
            continue
        found = by_rule.get(rid, [])
        if rule["required"] and not found:
            out.append({"code": "MISSING_REQUIRED", "severity": rule["severity"], "step": None,
                        "message": f"no step carries rule '{rid}' ({rule['title']}): {rule['plain']}"})
            continue
        for s in found:
            if "legally_required" not in s.get("tags", []):
                out.append({"code": "LEGAL_UNTAGGED", "severity": BLOCKING, "step": s["id"],
                            "message": f"carries rule '{rid}' but is not tagged legally_required"})
            if s["due_day"] > rule["due_day_max"]:
                out.append({"code": "LEGAL_LATE", "severity": rule["severity"], "step": s["id"],
                            "message": f"due day {s['due_day']:+d}, but {rule['title']} is due by day {rule['due_day_max']:+d}: {rule['plain']}"})
            if sch["finish"][s["id"]] > rule["due_day_max"]:
                out.append({"code": "LEGAL_CANNOT_FINISH", "severity": rule["severity"], "step": s["id"],
                            "message": f"cannot finish before day {sch['finish'][s['id']]:+d}; {rule['title']} is due by day {rule['due_day_max']:+d}"})
            anc_rules = {by_id[a].get("rule") for a in ancestors(by_id, s["id"])}
            for need in rule["after_rules"]:
                if need in by_rule and need not in anc_rules:
                    out.append({"code": "LEGAL_ORDER", "severity": BLOCKING, "step": s["id"],
                                "message": f"{rule['title']} must come after '{need}', but the step does not wait for it"})
    states = j.get("states") or []
    confirmed = wf.get("states_verified") or {}
    for st in states:
        if not str(confirmed.get(st, "")).strip():
            out.append({"code": "STATE_UNVERIFIED", "severity": BLOCKING, "step": None,
                        "message": f"{st}: state requirements not confirmed; check " + "; ".join(rules["state_checklist"])})
    return out


def dead_air(wf, sch):
    """A gap of more than max_silence_days with no contact with the hire is when
    people accept the other offer."""
    limit = wf.get("max_silence_days", 3)
    gap = wf["offer_to_first_shift_days"]
    touches = {-gap, 0}
    for s in wf["steps"]:
        tags = s.get("tags", [])
        if "needs_hire_action" in tags or s["category"] == "Connection & engagement":
            d = sch["start"][s["id"]]
            if -gap <= d <= 0:
                touches.add(d)
    days = sorted(touches)
    out = []
    for a, b in zip(days, days[1:]):
        if b - a > limit:
            out.append({"code": "DEAD_AIR", "severity": BLOCKING, "step": None,
                        "message": f"no contact with the hire from day {a:+d} to day {b:+d} ({b - a} days; limit {limit})"})
    return out


# ---------------------------------------------------------------- clone and confirm

def clone(past, name=None, states=None, gap=None):
    """Reuse a past workflow as a draft. Every value is kept, and every value is
    marked unconfirmed: reusing a decision saves typing, not checking."""
    wf = json.loads(json.dumps(past))
    wf["status"] = "draft"
    if name:
        wf["workflow"] = name
    if gap is not None:
        wf["offer_to_first_shift_days"] = gap
    if states is not None:
        wf.setdefault("jurisdiction", {})["states"] = states
    wf["states_verified"] = {}
    wf["cloned_from"] = past.get("workflow")
    for s in wf["steps"]:
        s["source"] = "cloned"
        s["validated"] = False
    shape(wf)
    return wf


def confirm(wf, ids=None, all_steps=False):
    known = {s["id"] for s in wf["steps"]}
    if ids:
        unknown = [i for i in ids if i not in known]
        if unknown:
            raise Refusal(f"unknown step id(s): {', '.join(unknown)}")
    for s in wf["steps"]:
        if all_steps or s["id"] in (ids or []):
            s["validated"] = True
    return wf


# ---------------------------------------------------------------- fallback log

LOG_OUTCOMES = {"primary", "fallback", "stop"}


def binom_sf(k, n, p):
    """P(X >= k) for X ~ Binomial(n, p), exact, standard library only."""
    if k <= 0:
        return 1.0
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0
    total = 0.0
    lp, lq = math.log(p), math.log1p(-p)
    for i in range(k, n + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                          + i * lp + (n - i) * lq)
    return min(1.0, total)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def bh(pvals, q=0.05):
    """Benjamini-Hochberg: indexes of the discoveries."""
    m = len(pvals)
    ranked = sorted(range(m), key=lambda i: pvals[i])
    cut = -1
    for rank, i in enumerate(ranked, 1):
        if pvals[i] <= q * rank / m:
            cut = rank
    return set(ranked[:cut]) if cut > 0 else set()


def read_log(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        cols = [c.strip() for c in (reader.fieldnames or [])]
        for need in ("hire_id", "step_id", "outcome"):
            if need not in cols:
                raise Refusal(f"log is missing the '{need}' column")
        for bad in ("name", "first_name", "last_name", "email", "phone", "ssn"):
            if bad in [c.lower() for c in cols]:
                raise Refusal(f"log has a '{bad}' column; remove personal details, hire_id is enough")
        rows = []
        for n, row in enumerate(reader, 2):
            row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
            if row["outcome"] not in LOG_OUTCOMES:
                raise Refusal(f"log line {n}: outcome must be one of {sorted(LOG_OUTCOMES)}, got '{row['outcome']}'")
            rows.append(row)
    return rows


def analyse_log(wf, rows):
    """Which steps fall back too often, overall and at particular sites.
    A rate on a handful of hires is not a finding: it needs a sample behind it."""
    cfg = wf.get("fallback_alert", {})
    alert_rate = cfg.get("rate", 0.15)
    min_n = cfg.get("min_hires", 20)
    min_site_n = cfg.get("min_site_hires", 10)
    steps = {s["id"]: s for s in wf["steps"]}
    per, unknown, worst = {}, {}, {}
    rank = {"primary": 0, "fallback": 1, "stop": 2}
    for r in rows:
        sid = r["step_id"]
        if sid not in steps:
            unknown[sid] = unknown.get(sid, 0) + 1
            continue
        # One hire is one observation per step, whatever happened to them:
        # a chase logged twice is still one hire whose primary failed.
        key = (sid, r["hire_id"])
        if key not in worst or rank[r["outcome"]] > rank[worst[key]["outcome"]]:
            worst[key] = r
    for (sid, _), r in sorted(worst.items()):
        per.setdefault(sid, []).append(r)

    report = {"steps": [], "site_flags": [], "unknown_steps": unknown,
              "unplanned": [], "alert_rate": alert_rate, "min_hires": min_n}
    cells, cell_p = [], []
    for sid in sorted(per):
        rs = per[sid]
        n = len(rs)
        k = sum(1 for r in rs if r["outcome"] != "primary")
        lo, hi = wilson(k, n)
        if n < min_n:
            verdict = "too_few"
        elif lo >= alert_rate:
            verdict = "primary_failing"
        else:
            verdict = "ok"
        report["steps"].append({"step": sid, "hires": n, "fallbacks": k, "rate": round(k / n, 4),
                                "ci_low": round(lo, 4), "ci_high": round(hi, 4), "verdict": verdict})
        if k and not steps[sid].get("fallback"):
            report["unplanned"].append({"step": sid, "fallbacks": k})
        # Site concentration: each site against the other sites on the same step.
        sites = {}
        for r in rs:
            if r.get("site"):
                sites.setdefault(r["site"], []).append(r)
        if len(sites) >= 2:
            for site, srs in sorted(sites.items()):
                sn = len(srs)
                if sn < min_site_n:
                    continue
                sk = sum(1 for r in srs if r["outcome"] != "primary")
                rest_n, rest_k = n - sn, k - sk
                base = (rest_k + 0.5) / (rest_n + 1)  # never exactly zero
                cells.append({"step": sid, "site": site, "hires": sn, "fallbacks": sk,
                              "rate": round(sk / sn, 4), "rest_rate": round(rest_k / rest_n, 4) if rest_n else None})
                cell_p.append(binom_sf(sk, sn, base))
    # One family across every step and every site: split it and the noise comes back.
    for i in sorted(bh(cell_p)):
        c = dict(cells[i])
        c["p"] = cell_p[i]
        report["site_flags"].append(c)
    report["site_flags"].sort(key=lambda c: (c["step"], c["site"]))
    report["cells_tested"] = len(cells)
    return report


# ---------------------------------------------------------------- render

def esc(x):
    return html.escape(str(x), quote=True)


def step_rows(wf, sch):
    out = []
    for s in sorted(wf["steps"], key=lambda s: (sch["start"][s["id"]], s["due_day"], s["id"])):
        out.append(s)
    return out


def cell(x):
    return str(x).replace("|", "/").replace("\n", " ")


def render_md(wf, result):
    sch = result["schedule"]
    L = []
    flag = "" if result["ready"] else f" (NOT READY: {result['blocking']} blocking, {result['unvalidated']} unconfirmed)"
    L.append(f"# {wf['workflow']}{flag}")
    L.append("")
    j = wf.get("jurisdiction") or {}
    L.append(f"Status: {wf['status']}. Offer accepted day {-wf['offer_to_first_shift_days']:+d}, first shift day 0. "
             f"Jurisdiction: {j.get('country', 'not set')} {', '.join(j.get('states', []))}.")
    if result["earliest_gap"] is not None:
        L.append(f"Shortest offer-to-first-shift this design allows: {result['earliest_gap']} days "
                 f"(planned: {result['planned_gap']}). Critical path: {' > '.join(result['critical_path'])}.")
    L.append(f"Start together when the offer is accepted: {', '.join(result['parallel_block'])}.")
    L.append("")
    L.append("## Steps")
    L.append("")
    L.append("| Step | Action | Done when | Owner | Category | Waits for | Days | Due | Tags | OK |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for s in step_rows(wf, sch):
        sid = s["id"]
        deps = ", ".join(d for d in s.get("after", [START]))
        L.append(f"| {sid} | {cell(s.get('action', ''))} | {cell(s.get('done_when', ''))} | {cell(s.get('owner', ''))} | "
                 f"{s['category']} | {deps} | {sch['start'][sid]:+d} to {sch['finish'][sid]:+d} | "
                 f"{s['due_day']:+d} | {', '.join(s.get('tags', []))} | {'yes' if s.get('validated') else 'NO'} |")
    L.append("")
    L.append("## Fallbacks (log every one: hire_id, step_id, outcome, site, date)")
    L.append("")
    L.append("| Step | Fires after | Shape | Alert | Action | Decides |")
    L.append("|---|---|---|---|---|---|")
    for s in step_rows(wf, sch):
        fb = s.get("fallback")
        if fb:
            L.append(f"| {s['id']} | {fb['after_days']} days | {fb['shape']} | {cell(fb.get('alert', ''))} | "
                     f"{cell(fb.get('action', ''))} | {cell(fb.get('decider', ''))} |")
    stop = wf.get("stop_rule") or {}
    if stop:
        L.append("")
        L.append(f"Stop rule: {stop.get('when', '')}. Decides: {stop.get('decider', '')}. "
                 f"Tells the hire the same day: {stop.get('who_tells_hire', '')}.")
    if result["findings"]:
        L.append("")
        L.append("## Findings")
        L.append("")
        for f in result["findings"]:
            L.append(f"- [{f['severity']}] {f['code']}" + (f" {f['step']}" if f["step"] else "") + f": {f['message']}")
    L.append("")
    return "\n".join(L)


CAT_COLOURS = ["#2f6f9f", "#7a4f9f", "#8a5a2b", "#2f8f5f", "#b23b3b", "#5f6b7a", "#3b9fb8", "#d9a400"]


def render_html(wf, result):
    sch = result["schedule"]
    gap = wf["offer_to_first_shift_days"]
    rows = step_rows(wf, sch)
    lo = -gap
    hi = max([0] + [sch["finish"][s["id"]] for s in rows] + [s["due_day"] for s in rows])
    span = max(hi - lo, 1)
    colour = {c: CAT_COLOURS[i % len(CAT_COLOURS)] for i, c in enumerate(CATEGORIES)}

    def pct(d):
        return 100.0 * (d - lo) / span

    def chips(s):
        return "".join(f'<span class="tag">{esc(t)}</span>' for t in s.get("tags", []))

    def unconf(s):
        return "" if s.get("validated") else '<span class="unconf">unconfirmed</span>'

    bars = []
    for s in rows:
        sid = s["id"]
        a, b = sch["start"][sid], sch["finish"][sid]
        left, width = pct(a), max(pct(b) - pct(a), 0.8)
        late = b > s["due_day"]
        bars.append(
            f'<div class="row"><div class="label">{esc(sid)} {unconf(s)}</div><div class="track">'
            f'<div class="bar{" late" if late else ""}" style="left:{left:.2f}%;width:{width:.2f}%;background:{colour[s["category"]]}" '
            f'title="{esc(s.get("action", ""))} | day {a:+d} to {b:+d}"></div>'
            f'<div class="due" style="left:{pct(s["due_day"]):.2f}%" title="due day {s["due_day"]:+d}"></div>'
            f'<div class="zero" style="left:{pct(0):.2f}%"></div>'
            f'</div></div>')
    zero = pct(0)
    axis = ('<div class="row"><div class="label"></div><div class="track axis">'
            + "".join(f'<span style="left:{pct(d):.2f}%">{d:+d}</span>' for d in sorted({lo, 0, hi}))
            + '</div></div>')

    def table(group_key, groups):
        parts = []
        for g in groups:
            members = [s for s in rows if group_key(s) == g]
            if not members:
                continue
            parts.append(f"<h3>{esc(g)}</h3><table><tr><th>Step</th><th>Action</th><th>Done when</th>"
                         f"<th>Owner</th><th>Days</th><th>Due</th><th>Tags</th></tr>")
            for s in members:
                sid = s["id"]
                parts.append(f"<tr><td>{esc(sid)} {unconf(s)}</td><td>{esc(s.get('action', ''))}</td>"
                             f"<td>{esc(s.get('done_when', ''))}</td><td>{esc(s.get('owner', ''))}</td>"
                             f"<td>{sch['start'][sid]:+d} to {sch['finish'][sid]:+d}</td><td>{s['due_day']:+d}</td>"
                             f"<td>{chips(s)}</td></tr>")
            parts.append("</table>")
        return "".join(parts)

    owners = sorted({str(s.get("owner", "")) or "(no owner)" for s in rows})
    findings = "".join(
        f"<li><b>{esc(f['code'])}</b>{(' ' + esc(f['step'])) if f['step'] else ''}: {esc(f['message'])}</li>"
        for f in result["findings"])
    status = ("Ready" if result["ready"]
              else f"Not ready: {result['blocking']} blocking finding(s), {result['unvalidated']} unconfirmed step(s)")
    legend = "".join(f'<span class="leg"><i style="background:{colour[c]}"></i>{esc(c)}</span>' for c in CATEGORIES)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(wf['workflow'])}</title>
<style>
body{{font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:16px;color:#1d2330;background:#fff}}
h1{{font-size:20px;margin:0 0 4px}} h2{{font-size:16px;margin:24px 0 8px}} h3{{font-size:14px;margin:16px 0 6px}}
.status{{padding:8px 10px;border-radius:6px;background:{'#e7f5ec' if result['ready'] else '#fdecec'};margin:8px 0}}
.tabs input{{display:none}} .tabs label{{display:inline-block;padding:6px 12px;border:1px solid #ccd;border-radius:6px 6px 0 0;cursor:pointer;margin-right:4px}}
.tabs input:checked+label{{background:#1d2330;color:#fff}} .view{{display:none;border-top:1px solid #ccd;padding-top:10px}}
#t1:checked~.v1,#t2:checked~.v2,#t3:checked~.v3{{display:block}}
.row{{display:flex;align-items:center;margin:3px 0}} .label{{width:200px;flex:none;font-size:12px;overflow:hidden;text-overflow:ellipsis}}
.track{{position:relative;flex:1;height:16px;background:#f3f4f7;border-radius:3px}}
.bar{{position:absolute;top:2px;height:12px;border-radius:3px}} .bar.late{{outline:2px solid #b23b3b}}
.due{{position:absolute;top:0;width:2px;height:16px;background:#1d2330}}
.zero{{position:absolute;top:-2px;height:20px;border-left:2px dashed #b23b3b}}
.axis{{background:none;height:14px}} .axis span{{position:absolute;font-size:11px;transform:translateX(-50%)}}
.tl{{position:relative}} .tag{{display:inline-block;font-size:11px;background:#eef;border-radius:3px;padding:0 5px;margin:1px}}
.unconf{{font-size:11px;color:#b23b3b;font-weight:600}} table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border-bottom:1px solid #e3e5ea;padding:4px 6px;text-align:left;vertical-align:top}}
.leg{{font-size:12px;margin-right:10px;white-space:nowrap}} .leg i{{display:inline-block;width:10px;height:10px;margin-right:4px;border-radius:2px}}
@media (max-width:600px){{.label{{width:110px}} table{{font-size:12px}}}}
</style></head><body>
<h1>{esc(wf['workflow'])}</h1>
<div>Offer accepted day {-gap:+d}. First shift day 0. Shortest gap this design allows: {result['earliest_gap']} days. Critical path: {esc(' > '.join(result['critical_path']))}.</div>
<div class="status">{esc(status)}</div>
<div class="tabs">
<input type="radio" name="v" id="t1" checked><label for="t1">Timeline</label>
<input type="radio" name="v" id="t2"><label for="t2">By category</label>
<input type="radio" name="v" id="t3"><label for="t3">By owner</label>
<div class="view v1"><div>{legend}</div><div class="tl">{axis}{''.join(bars)}</div>
<p style="font-size:12px">Bars run from earliest start to earliest finish; the black tick is the deadline; the red dashed line is the first shift (day 0); a red outline means late.</p></div>
<div class="view v2">{table(lambda s: s['category'], CATEGORIES)}</div>
<div class="view v3">{table(lambda s: str(s.get('owner', '')) or '(no owner)', owners)}</div>
</div>
<h2>Findings</h2><ul>{findings or '<li>None.</li>'}</ul>
</body></html>"""


# ---------------------------------------------------------------- text output

def text_check(r):
    L = [f"{r['workflow']}: {'READY' if r['ready'] else 'NOT READY'} "
         f"({r['blocking']} blocking, {r['care']} needs care, {r['unvalidated']} unconfirmed)"]
    if r["earliest_gap"] is not None:
        L.append(f"shortest offer-to-first-shift: {r['earliest_gap']} days (planned {r['planned_gap']}); "
                 f"critical path: {' > '.join(r['critical_path'])}")
    L.append(f"start together at offer acceptance: {', '.join(r['parallel_block'])}")
    for f in r["findings"]:
        L.append(f"  [{f['severity']}] {f['code']}" + (f" {f['step']}" if f["step"] else "") + f": {f['message']}")
    return "\n".join(L)


def text_log(rep):
    L = [f"fallback alert when the 95% lower bound reaches {rep['alert_rate']:.0%} on at least {rep['min_hires']} hires"]
    for s in rep["steps"]:
        L.append(f"  {s['step']:<24} {s['fallbacks']:>4}/{s['hires']:<5} {s['rate']:>6.1%}  "
                 f"[{s['ci_low']:.1%} to {s['ci_high']:.1%}]  {s['verdict']}")
    if rep["site_flags"]:
        L.append(f"sites where a step falls back far more than elsewhere ({rep['cells_tested']} site-step cells, Benjamini-Hochberg):")
        for c in rep["site_flags"]:
            L.append(f"  {c['step']} at {c['site']}: {c['fallbacks']}/{c['hires']} ({c['rate']:.0%}) vs {c['rest_rate']:.0%} elsewhere")
    for u in rep["unplanned"]:
        L.append(f"  fallback logged on {u['step']} ({u['fallbacks']}x) but the design has no fallback for it")
    for sid, n in sorted(rep["unknown_steps"].items()):
        L.append(f"  step '{sid}' is in the log ({n} rows) but not in the workflow")
    return "\n".join(L)


# ---------------------------------------------------------------- tests

def run_tests():
    passed, failed = 0, []

    def ok(name, cond):
        nonlocal passed
        if cond:
            passed += 1
        else:
            failed.append(name)

    sample = os.path.join(SKILL, "references", "sample")
    rules = load_rules()
    base = load_workflow(os.path.join(sample, "northline_store_associate.json"))
    r = check(base, rules)
    codes = {f["code"] for f in r["findings"]}
    ok("sample is ready", r["ready"])
    ok("sample has no findings at all", not r["findings"])
    ok("sample critical path", r["critical_path"] == ORACLE["critical_path"])
    ok("sample earliest gap", r["earliest_gap"] == ORACLE["earliest_gap"])
    ok("sample parallel block", r["parallel_block"] == ORACLE["parallel_block"])
    ok("deterministic", json.dumps(check(base, rules), sort_keys=True) == json.dumps(r, sort_keys=True))

    # Fixtures: each mutation must raise its codes and must not raise the others.
    cases = json.load(open(os.path.join(SKILL, "references", "fixtures", "cases.json"), encoding="utf-8"))
    for case in cases["cases"]:
        wf = mutate(base, case["changes"])
        if case.get("refuse"):
            try:
                check(wf, rules)
                ok(f"{case['name']}: refused", False)
            except Refusal as e:
                ok(f"{case['name']}: refused naming '{case['refuse']}'", case["refuse"] in str(e))
            continue
        try:
            got = {f["code"] for f in check(wf, rules)["findings"]}
        except Refusal as e:
            ok(f"{case['name']}: unexpected refusal {e}", False)
            continue
        for c in case.get("must", []):
            ok(f"{case['name']}: raises {c}", c in got)
        for c in case.get("must_not", []):
            ok(f"{case['name']}: does not raise {c}", c not in got)

    # Clone: everything reused, nothing trusted.
    draft = clone(base, name="Warehouse associate (draft)", states=["NV"])
    rd = check(draft, rules)
    ok("clone keeps every step", len(draft["steps"]) == len(base["steps"]))
    ok("clone is not ready", not rd["ready"])
    ok("clone: every step unconfirmed", rd["unvalidated"] == len(base["steps"]))
    ok("clone: new state unverified", "STATE_UNVERIFIED" in {f["code"] for f in rd["findings"]})
    ok("clone does not touch the original", check(base, rules)["ready"])
    confirmed = confirm(json.loads(json.dumps(draft)), all_steps=True)
    confirmed["states_verified"] = {"NV": "test"}
    ok("confirming all makes the clone ready again", check(confirmed, rules)["ready"])
    try:
        confirm(json.loads(json.dumps(draft)), ids=["no_such_step"])
        ok("confirm refuses unknown ids", False)
    except Refusal:
        ok("confirm refuses unknown ids", True)
    shipped_draft = load_workflow(os.path.join(sample, "northline_warehouse_draft.json"))
    ok("shipped draft is unconfirmed", check(shipped_draft, rules)["unvalidated"] == len(shipped_draft["steps"]))

    # Render: three views, every step, and unconfirmed steps marked.
    h = render_html(base, r)
    ok("html has three views", all(x in h for x in ("Timeline", "By category", "By owner")))
    ok("html lists every step", all(s["id"] in h for s in base["steps"]))
    ok("html has no script", "<script" not in h.lower())
    hd = render_html(draft, rd)
    ok("draft html marks unconfirmed", hd.count("unconfirmed") >= len(draft["steps"]))
    md = render_md(base, r)
    ok("md lists every step", all(f"| {s['id']} |" in md for s in base["steps"]))
    ok("md lists every fallback", all(f"| {s['id']} | {s['fallback']['after_days']} days |" in md
                                       for s in base["steps"] if s.get("fallback")))
    ok("draft md says not ready", "NOT READY" in render_md(draft, rd))

    # Fallback log: the planted answers, and only those.
    rows = read_log(os.path.join(sample, "northline_fallback_log.csv"))
    rep = analyse_log(base, rows)
    verdicts = {s["step"]: s["verdict"] for s in rep["steps"]}
    ok("log: failing primaries", {k for k, v in verdicts.items() if v == "primary_failing"} == set(ORACLE["primary_failing"]))
    ok("log: small sample not flagged", verdicts.get(ORACLE["too_few"]) == "too_few")
    ok("log: site flags", sorted((c["step"], c["site"]) for c in rep["site_flags"]) == sorted(map(tuple, ORACLE["site_flags"])))
    ok("log: the high-rate step has no site flags", not any(c["step"] == "bg_check" for c in rep["site_flags"]))
    ok("log: unknown step reported", set(rep["unknown_steps"]) == set(ORACLE["unknown_steps"]))
    ok("log: unplanned fallback reported", [u["step"] for u in rep["unplanned"]] == ORACLE["unplanned"])
    ok("log: site step not flagged overall", verdicts.get("uniform_fit") == "ok")
    for bad, msg in (("hire_id,step_id,result\n1,bg_check,primary\n", "outcome"),
                     ("hire_id,step_id,outcome,email\n1,bg_check,primary,a@b.c\n", "email"),
                     ("hire_id,step_id,outcome\n1,bg_check,failed\n", "outcome must be")):
        p = os.path.join(sample, ".tmp_log.csv")
        try:
            with open(p, "w", encoding="utf-8") as f:
                f.write(bad)
            try:
                read_log(p)
                ok(f"log refuses: {msg}", False)
            except Refusal as e:
                ok(f"log refuses: {msg}", msg in str(e))
        finally:
            if os.path.exists(p):
                os.remove(p)

    # The same pattern, redrawn: a suite that passes on one file has memorised it.
    import subprocess
    gen = os.path.join(sample, "make_log.py")
    tmp = os.path.join(sample, ".tmp_seed.csv")
    step_ok = found = chance = 0
    seeds = range(1, 41)
    try:
        for seed in seeds:
            with open(tmp, "w", encoding="utf-8") as f:
                subprocess.run([sys.executable, gen, str(seed)], stdout=f, check=True)
            rp = analyse_log(base, read_log(tmp))
            v = {x["step"]: x["verdict"] for x in rp["steps"]}
            step_ok += ({k for k, x in v.items() if x == "primary_failing"} == {"bg_check"}
                        and v.get("ladder_cert") == "too_few")
            flags = {(c["step"], c["site"]) for c in rp["site_flags"]}
            planted = {tuple(x) for x in ORACLE["site_flags"]}
            found += planted <= flags
            chance += bool(flags - planted)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    ok(f"40 draws: step verdicts right every time ({step_ok}/40)", step_ok == 40)
    ok(f"40 draws: both planted stores found in at least 80% ({found}/40)", found >= 32)
    ok(f"40 draws: a chance store flag in at most 20% ({chance}/40)", chance <= 8)

    dup = [{"hire_id": "H1", "step_id": "bg_check", "outcome": "fallback", "site": "S01"},
           {"hire_id": "H1", "step_id": "bg_check", "outcome": "fallback", "site": "S01"},
           {"hire_id": "H1", "step_id": "bg_check", "outcome": "primary", "site": "S01"},
           {"hire_id": "H2", "step_id": "bg_check", "outcome": "primary", "site": "S01"}]
    st = analyse_log(base, dup)["steps"][0]
    ok("log: one hire counts once, at its worst outcome", (st["hires"], st["fallbacks"]) == (2, 1))
    piped = mutate(base, [["step.w4.action", "Send W-4 | then call"]])
    ok("md escapes pipes", "Send W-4 / then call" in render_md(piped, check(piped, rules)))
    ok("html escapes markup", "&lt;b&gt;" in render_html(mutate(base, [["step.w4.action", "<b>x</b>"]]),
                                                         check(mutate(base, [["step.w4.action", "<b>x</b>"]]), rules)))

    # Statistics helpers.
    ok("wilson brackets the rate", wilson(24, 100)[0] < 0.24 < wilson(24, 100)[1])
    ok("binomial tail sane", abs(binom_sf(1, 1, 0.3) - 0.3) < 1e-9 and binom_sf(0, 5, 0.3) == 1.0)
    ok("bh keeps nothing in noise", bh([0.2, 0.5, 0.9, 0.04]) == set())

    # A file that is not UTF-8 is refused with exit 2, never a traceback.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        latin = os.path.join(tmp, "log.csv")
        with open(latin, "wb") as fh:
            fh.write("hire_id,step_id,outcome,site\nh1,w4,primary,Sa\xefd\n".encode("cp1252"))
        wide = os.path.join(tmp, "wf.json")
        with open(wide, "wb") as fh:
            fh.write(json.dumps(base).encode("utf-16"))
        quiet, sys.stderr = sys.stderr, open(os.devnull, "w")
        try:
            ok("non-UTF-8 log refused", main(["log", os.path.join(sample, "northline_store_associate.json"), latin]) == 2)
            ok("UTF-16 workflow refused", main(["check", wide]) == 2)
        finally:
            sys.stderr.close()
            sys.stderr = quiet

    total = passed + len(failed)
    for name in failed:
        print("FAIL", name)
    print(f"{passed}/{total} passed")
    return 0 if not failed else 1


# The planted answers, per the generator in references/sample/make_log.py.
ORACLE = {
    "critical_path": ["bg_consent", "bg_check", "system_access"],
    "earliest_gap": 8,
    "parallel_block": ["bg_consent", "direct_deposit", "handbook_ack", "i9_s1", "ladder_cert",
                       "safety_training", "schedule_shifts", "uniform_fit", "w4", "welcome_call"],
    "primary_failing": ["bg_check"],
    "too_few": "ladder_cert",
    "site_flags": [["uniform_fit", "S07"], ["uniform_fit", "S19"]],
    "unknown_steps": ["drug_test"],
    "unplanned": ["welcome_call"],
}


def mutate(base, changes):
    """changes: list of [path, value]. Paths: 'top.field', 'step.<id>.field',
    'step.<id>.fallback.field', 'drop.<id>', 'add' (value is a step).
    A value of null deletes the field."""
    wf = json.loads(json.dumps(base))
    by_id = {s["id"]: s for s in wf["steps"]}
    for path, value in changes:
        parts = path.split(".")
        if parts[0] == "drop":
            wf["steps"] = [s for s in wf["steps"] if s["id"] != parts[1]]
            continue
        if parts[0] == "add":
            wf["steps"].append(value)
            continue
        if parts[0] == "top":
            target, keys = wf, parts[1:]
        else:
            target, keys = by_id[parts[1]], parts[2:]
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        if value is None:
            target.pop(keys[-1], None)
        else:
            target[keys[-1]] = value
    return wf


# ---------------------------------------------------------------- cli

def main(argv):
    if "--test" in argv:
        return run_tests()
    if not argv:
        print(__doc__)
        return 2

    def opt(name):
        if name in argv:
            i = argv.index(name)
            if i + 1 < len(argv):
                return argv[i + 1]
            raise Refusal(f"{name} needs a value")
        return None

    cmd = argv[0]
    try:
        if cmd == "check":
            wf = load_workflow(argv[1])
            r = check(wf)
            if "--json" in argv:
                r = dict(r)
                r.pop("schedule")
                print(json.dumps(r, indent=2))
            else:
                print(text_check(r))
            return 0 if r["ready"] else 1
        if cmd == "render":
            wf = load_workflow(argv[1])
            r = check(wf)
            if opt("--html"):
                open(opt("--html"), "w", encoding="utf-8").write(render_html(wf, r))
            if opt("--md"):
                open(opt("--md"), "w", encoding="utf-8").write(render_md(wf, r))
            if not opt("--html") and not opt("--md"):
                print(render_md(wf, r))
            print(text_check(r), file=sys.stderr)
            return 0 if r["ready"] else 1
        if cmd == "clone":
            past = load_workflow(argv[1])
            states = opt("--states")
            gap = opt("--gap")
            wf = clone(past, name=opt("--name"),
                       states=[x.strip() for x in states.split(",")] if states else None,
                       gap=int(gap) if gap else None)
            out = opt("-o")
            text = json.dumps(wf, indent=2) + "\n"
            open(out, "w", encoding="utf-8").write(text) if out else print(text)
            return 0
        if cmd == "confirm":
            wf = load_workflow(argv[1])
            ids = opt("--steps")
            wf = confirm(wf, ids=[x.strip() for x in ids.split(",")] if ids else None,
                         all_steps="--all" in argv)
            out = opt("-o") or argv[1]
            open(out, "w", encoding="utf-8").write(json.dumps(wf, indent=2) + "\n")
            return 0
        if cmd == "log":
            wf = load_workflow(argv[1])
            rep = analyse_log(wf, read_log(argv[2]))
            print(json.dumps(rep, indent=2) if "--json" in argv else text_log(rep))
            return 0
    except Refusal as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    except (IndexError, FileNotFoundError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    except UnicodeDecodeError:
        # A spreadsheet saved as plain "CSV" on Windows, or as UTF-16 text.
        print("REFUSED: the file is not UTF-8 text; save it as \"CSV UTF-8\" "
              "(or the workflow as UTF-8 JSON) and try again", file=sys.stderr)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
