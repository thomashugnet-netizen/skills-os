#!/usr/bin/env python3
"""
Turns a careers site check into the advice an employer should act on, in order.

Why this exists
---------------
A list of forty findings is not advice. An employer needs to know which three
things to do first, why each one matters to them, who owns it and how big it
is. That ranking should not depend on the mood of a conversation, so it is
done here, from one catalogue (references/recommendations.json) and two
inputs: what check_site.py found, and the facts the employer gave.

Every recommendation serves the employer: more of the right applicants, less
legal exposure, less wasted work. A fact the employer never gave cannot fire a
recommendation; it becomes a question at the end of the plan instead, because
guessing whether someone is an E-Verify participant is worse than asking.

    advise.py --site SITE_DIR [--fact states=CA,TX --fact apply_minutes=12]
    advise.py --page saved_page.html [--facts facts.json] [--top 3] [--json out.json]
    advise.py --report check_report.json
    advise.py --test

Standard library only. No network.
"""

import argparse
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CATALOGUE = os.path.join(SKILL, "references", "recommendations.json")
TIERS = ["must", "should", "could"]
TIER_LABEL = {"must": "Must do", "should": "Should do", "could": "Could do"}
EFFORT = {"S": 0, "M": 1, "L": 2}


def load_catalogue(path=CATALOGUE):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_checker():
    spec = importlib.util.spec_from_file_location("check_site", os.path.join(HERE, "check_site.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_fact(text):
    """key=value from the command line. Booleans, numbers and comma lists."""
    if "=" not in text:
        raise SystemExit(f"advise: facts are key=value, got '{text}'")
    key, raw = text.split("=", 1)
    raw = raw.strip()
    low = raw.lower()
    if low in ("true", "yes", "y"):
        value = True
    elif low in ("false", "no", "n"):
        value = False
    else:
        try:
            value = float(raw) if "." in raw else int(raw)
        except ValueError:
            value = [x.strip() for x in raw.split(",") if x.strip()] if "," in raw or key.strip() in ("states", "languages") else raw
    return key.strip(), value


def fact_true(trigger, facts, data):
    """None when the fact was never given, otherwise whether the trigger holds."""
    key = trigger["fact"]
    if key not in facts or facts[key] is None:
        return None if trigger["op"] != "not_true" else True
    v = facts[key]
    op = trigger["op"]
    if op == "true":
        return v is True
    if op == "false":
        return v is False
    if op == "not_true":
        return v is not True
    if op == ">":
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v > trigger["value"]
    if op == "equals":
        return str(v).lower() == str(trigger["value"]).lower()
    if op == "in":
        return str(v).lower() in [str(x).lower() for x in trigger["value"]]
    if op == "nonempty":
        return bool(v) if isinstance(v, list) else bool(str(v).strip())
    if op == "intersects":
        pool = {x.upper() for x in data[trigger["data"]]}
        vals = v if isinstance(v, list) else [v]
        return any(str(x).upper() in pool for x in vals)
    raise ValueError(f"unknown op {op}")


def advise(report, facts=None, catalogue=None):
    catalogue = catalogue or load_catalogue()
    facts = facts or {}
    fails = report.get("fails", {})
    data = catalogue.get("data", {})
    fired, questions = [], {}
    for rec in catalogue["recommendations"]:
        because = []
        for t in rec["triggers"]:
            if "check" in t and t["check"] in fails:
                because.append({"check": t["check"], "examples": fails[t["check"]][:3]})
            elif t.get("report") == "to_confirm" and report.get("to_confirm"):
                because.append({"report": "to_confirm", "count": len(report["to_confirm"])})
        for t in rec["triggers"]:
            if "fact" not in t:
                continue
            if rec.get("facts_only_without_job_pages") and report.get("job_pages", 0) > 0:
                continue
            ok = fact_true(t, facts, data)
            if ok is None:
                questions.setdefault(t["fact"], set()).add(rec["id"])
            elif ok:
                because.append({"fact": t["fact"], "value": facts.get(t["fact"])})
        if because:
            fired.append(dict(rec, because=because))
    fired.sort(key=lambda r: (TIERS.index(r["tier"]), -r["impact"], EFFORT.get(r["effort"], 1), r["id"]))
    fired_ids = {r["id"] for r in fired}
    open_questions = [{"fact": k, "question": catalogue["facts"].get(k, k),
                       "could_add": sorted(v - fired_ids)}
                      for k, v in sorted(questions.items()) if v - fired_ids]
    return {"recommendations": fired, "questions": open_questions}


def render(plan, top=3):
    recs = plan["recommendations"]
    out = []
    if not recs:
        out.append("No recommendations fired. Answer the questions below to check what else applies.")
    else:
        out.append(f"Start with these {min(top, len(recs))}:")
        for i, r in enumerate(recs[:top], 1):
            out.append(f"  {i}. {r['title']} ({TIER_LABEL[r['tier']].lower()}, {r['owner']}, effort {r['effort']})")
        for tier in TIERS:
            group = [r for r in recs if r["tier"] == tier]
            if not group:
                continue
            out += ["", f"{TIER_LABEL[tier]} ({len(group)})"]
            for r in group:
                out.append(f"- {r['title']}  [{r['owner']}, effort {r['effort']}]")
                out.append(f"    Why: {r['why']}")
                out.append(f"    How: {r['how']}")
                why = []
                for b in r["because"]:
                    if "check" in b:
                        why.append(b["check"] + (f" ({b['examples'][0]})" if b["examples"] else ""))
                    elif "fact" in b:
                        val = b["value"]
                        shown = ("not known yet" if val is None else
                                 ", ".join(map(str, val)) if isinstance(val, list) else val)
                        why.append(f"{b['fact']}: {shown}")
                    else:
                        why.append(f"{b['count']} facts marked for confirmation")
                out.append(f"    Found: {'; '.join(why)}")
                if r.get("source"):
                    out.append(f"    Source: {r['source']}")
    if plan["questions"]:
        out += ["", "Questions that would change this plan:"]
        for q in plan["questions"]:
            out.append(f"- {q['question']}")
    return "\n".join(out)


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def run_tests():
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        print(f"  {'ok  ' if ok else 'FAIL'} {name}" + (f"  {detail}" if detail and not ok else ""))
        if ok:
            passed += 1
        else:
            failed += 1

    cat = load_catalogue()
    checker = load_checker()
    recs = cat["recommendations"]
    print("Catalogue")
    ids = [r["id"] for r in recs]
    check("recommendation ids are unique", len(ids) == len(set(ids)))
    check("every tier is must, should or could", all(r["tier"] in TIERS for r in recs))
    used = {t["check"] for r in recs for t in r["triggers"] if "check" in t}
    unknown = sorted(used - set(checker.CHECKS))
    check("every check a recommendation cites exists", not unknown, str(unknown))
    orphan = sorted(set(checker.CHECKS) - used)
    check("every check has a recommendation, so no finding goes without advice", not orphan, str(orphan))
    facts_used = {t["fact"] for r in recs for t in r["triggers"] if "fact" in t}
    check("every fact a trigger uses is declared", facts_used <= set(cat["facts"]), str(facts_used - set(cat["facts"])))
    check("every data list a trigger uses exists",
          all(t["data"] in cat["data"] for r in recs for t in r["triggers"] if "data" in t))
    check("every recommendation says why, how, who and how big",
          all(r.get("why") and r.get("how") and r.get("owner") and r.get("effort") in EFFORT for r in recs))
    must_unsourced = [r["id"] for r in recs if r["tier"] == "must" and not r.get("source")
                      and not all("check" in t or "report" in t for t in r["triggers"])]
    check("every must that rests on a fact cites a source", not must_unsourced, str(must_unsourced))

    print("\nDecisions")
    clean = {"fails": {}, "to_confirm": [], "job_pages": 0}
    plan = advise(clean, {"accessibility_audit": True}, cat)
    check("a clean site with nothing known fires nothing", not plan["recommendations"],
          str([r["id"] for r in plan["recommendations"]]))
    check("unknown facts become questions, not assumptions",
          {"apply_minutes", "e_verify", "states"} <= {q["fact"] for q in plan["questions"]})
    plan = advise(clean, {}, cat)
    check("a manual accessibility audit is recommended until one is done",
          [r["id"] for r in plan["recommendations"]] == ["manual-accessibility-audit"])

    plan = advise({"fails": {"conv.pay_shown": ["jobs/a.html"], "content.cliche": ["index.html (rockstar)"]},
                   "job_pages": 3}, {"accessibility_audit": True}, cat)
    order = [r["id"] for r in plan["recommendations"]]
    check("a finding fires its recommendation, must before could",
          order == ["pay-on-every-job", "plain-specific-copy"], str(order))

    def fired(facts, job_pages=0, fails=None):
        p = advise({"fails": fails or {}, "job_pages": job_pages}, dict(facts, accessibility_audit=True), cat)
        return {r["id"] for r in p["recommendations"]}
    check("hiring in California brings pay and benefits rules", {"pay-on-every-job", "benefits-on-every-job"} <= fired({"states": ["CA"]}))
    check("hiring in Texas alone brings neither", not ({"pay-on-every-job", "benefits-on-every-job"} & fired({"states": ["TX"]})))
    check("Colorado brings pay but not the benefits description",
          "pay-on-every-job" in fired({"states": ["CO"]}) and "benefits-on-every-job" not in fired({"states": ["CO"]}))
    check("once job pages exist and show pay, the state alone does not repeat the advice",
          "pay-on-every-job" not in fired({"states": ["CA"]}, job_pages=5))
    check("a twelve-minute application is flagged", "five-minute-apply" in fired({"apply_minutes": 12}))
    check("a three-minute application with no account and no resume is not",
          "five-minute-apply" not in fired({"apply_minutes": 3, "account_required": False, "resume_required_hourly": False}))
    check("E-Verify participants get the notices", "e-verify-notices" in fired({"e_verify": True}))
    check("non-participants do not", "e-verify-notices" not in fired({"e_verify": False}))
    check("a manual jobs feed brings automation", "keep-jobs-current" in fired({"jobs_feed": "manual"}))
    check("stock photos bring real photography", "real-photos-and-stories" in fired({"photos": "stock"}))
    check("Spanish-speaking candidates bring translation", "candidates-language" in fired({"languages": ["Spanish"]}))

    print("\nInputs")
    check("command-line facts parse", [parse_fact("states=CA,NY"), parse_fact("apply_minutes=12"),
                                        parse_fact("e_verify=yes"), parse_fact("states=TX"),
                                        parse_fact("jobs_feed=manual")] ==
          [("states", ["CA", "NY"]), ("apply_minutes", 12), ("e_verify", True), ("states", ["TX"]), ("jobs_feed", "manual")])

    import tempfile
    tmp = tempfile.mkdtemp(prefix="advise-")
    page = os.path.join(tmp, "careers.html")
    with open(page, "w", encoding="utf-8") as f:
        f.write('<!doctype html><html><head><title>Careers</title></head><body><div id="app"></div>'
                '<script src="/static/app.js"></script></body></html>')
    report = checker.run(page=page)
    plan = advise(report, {}, cat)
    ids = [r["id"] for r in plan["recommendations"]]
    check("auditing a JavaScript-only page puts the blocking fixes first",
          "content-in-html" in ids and ids.index("candidate-privacy-notice") < ids.index("content-in-html"), str(ids))
    check("the plan reads as text with a top three", render(plan).startswith("Start with these 3:"))

    print(f"\n{passed} passed, {failed} failed")
    ok = failed == 0
    if os.path.exists(os.path.join(HERE, "build_site.py")):
        # Where the site builder lives too, its suite is part of this one.
        print("\nSite checker suite")
        ok = checker.run_tests() and ok
    return ok


def main():
    ap = argparse.ArgumentParser(description="Rank what an employer should fix on its careers site.")
    ap.add_argument("--site", help="a site folder to check")
    ap.add_argument("--page", help="one saved HTML page to check")
    ap.add_argument("--report", help="a JSON report written by check_site.py --json")
    ap.add_argument("--facts", help="a JSON file of facts the employer gave")
    ap.add_argument("--fact", action="append", default=[], help="key=value, repeatable")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", help="also write the plan as JSON here")
    ap.add_argument("--test", action="store_true", help="run the self-test suite")
    a = ap.parse_args()
    if a.test:
        sys.exit(0 if run_tests() else 1)
    if a.report:
        report = json.load(open(a.report, encoding="utf-8"))
    elif a.site or a.page:
        report = load_checker().run(site=a.site, page=a.page)
    else:
        ap.error("give --site, --page or --report")
    facts = json.load(open(a.facts, encoding="utf-8")) if a.facts else {}
    facts.update(dict(parse_fact(x) for x in a.fact))
    plan = advise(report, facts)
    print(render(plan, a.top))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2, default=list)


if __name__ == "__main__":
    main()
