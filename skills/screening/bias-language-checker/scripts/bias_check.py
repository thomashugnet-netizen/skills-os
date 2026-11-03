#!/usr/bin/env python3
"""
Checks every candidate-facing text for wording that excludes people you would
hire, or that asks about something you may not ask about: job ads, application
questions, text and email templates, offer letters, interview guides and
careers pages. Reads one text, or a whole template library at once and ranks
the fixes by how many candidates each line reaches.

    python3 bias_check.py --text ad.txt [--type ad] [--html report.html]
    python3 bias_check.py --library templates.csv [--html report.html] [--json report.json]
    python3 bias_check.py --library folder/  (every .txt and .md in it)
    python3 bias_check.py --demo
    python3 bias_check.py --test

templates.csv  id,type,text[,uses]   type is ad, question, message, offer,
               guide or page; uses is how many requisitions, sends or
               applications the template reaches (default 1).

Every finding quotes the line, names the class (protected, proxy, coded,
requirement), the severity, why it matters and what to say instead. Gendered
titles get a direct replacement. Ads for physical jobs that state no physical
demand are flagged too: leaving the demands out is not more inclusive.

It flags; it does not clear. No match means no rule matched, in English.
Text in another language is reported as not checked.

Exit codes:
    0  no high-severity finding
    1  at least one high-severity finding, or a text that could not be checked
    2  no mode given
    3  input refused
    4  the checker itself failed
Standard library only. Not legal advice.
"""

import csv
import html
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")
TYPES = ("ad", "question", "message", "offer", "guide", "page")
TYPE_ALIASES = {"job ad": "ad", "job_ad": "ad", "posting": "ad", "ads": "ad", "application": "question",
                "form": "question", "screening": "question", "questions": "question", "sms": "message",
                "email": "message", "text": "message", "messages": "message", "offer letter": "offer",
                "offer_letter": "offer", "interview": "guide", "script": "guide", "careers page": "page",
                "career page": "page", "career_site": "page", "any": "any", "": "any"}
SEV = {"high": 0, "medium": 1, "low": 2}
PERSON_COLS = re.compile(r"candidate|applicant|first.?name|last.?name|full.?name|e-?mail|phone|dob|birth|ssn",
                         re.I)
ENGLISH = set("the a an and or to of in on for with you your we our is are be will can at this that it as "
              "from by if not have has do what when where how who all shift shifts pay hour hours work job "
              "apply store team per week".split())


FOREIGN = set("el los las del que y en una por para con es su gracias hola puedes usted les al se lo muy "
              "trabajo turno semana pago horas tienda le du des et est pour avec vous nous merci bonjour "
              "travail heures não você obrigado com uma trabalho".split())


class Refusal(Exception):
    pass


def load_rules():
    d = json.load(open(os.path.join(REF, "rules.json"), encoding="utf-8"))
    for k in ("eeo_guard", "about_them", "others", "driving_job", "physical_job", "physical_demands"):
        d[k + "_re"] = re.compile(d[k], re.I)
    for r in d["rules"]:
        r["_p"] = [re.compile(p, re.I) for p in r["patterns"]]
        r["_g"] = [re.compile(g, re.I) for g in r.get("guards", [])]
    return d


def sentences(text):
    out = []
    for ln, line in enumerate(text.splitlines(), 1):
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9¿¡\"'(])", line):
            part = part.strip()
            if part:
                out.append((ln, part))
    return out


def english(text):
    """False only on positive evidence of another language: an inverted mark,
    or more Spanish, French or Portuguese function words than English ones."""
    if re.search(r"[¿¡]", text):
        return False
    words = re.findall(r"[a-záàâçéèêëíîïóôúûüñãõ']+", text.lower())
    if len(words) < 5:
        return True
    foreign = sum(1 for w in words if w in FOREIGN)
    native = sum(1 for w in words if w in ENGLISH)
    return not (foreign >= 3 and foreign > native)


def check_text(text, kind, rules):
    kind = TYPE_ALIASES.get(kind.strip().lower(), kind.strip().lower()) if kind else "any"
    if kind not in TYPES + ("any",):
        raise Refusal(f"type '{kind}' should be one of {', '.join(TYPES)}.")
    if not text.strip():
        return {"type": kind, "checked": False, "reason": "empty", "findings": []}
    if not english(text):
        return {"type": kind, "checked": False, "reason": "not English", "findings": []}
    low_text = text.lower()
    driving = bool(rules["driving_job_re"].search(low_text))
    findings = []
    for ln, sent in sentences(text):
        low = sent.lower()
        eeo = bool(rules["eeo_guard_re"].search(low))
        stripped = rules["others_re"].sub(" ", low)
        for r in rules["rules"]:
            applies = r["applies"]
            if applies != "all" and kind != "any" and kind not in applies:
                continue
            if eeo and r["class"] in ("protected", "coded"):
                continue
            if r.get("text_guard") == "driving_job" and driving:
                continue
            if any(g.search(low) for g in r["_g"]):
                continue
            target = stripped if r.get("about_them") else low
            if r.get("about_them") and not rules["about_them_re"].search(low):
                continue
            hit = next((m for p in r["_p"] for m in [p.search(target)] if m), None)
            if not hit:
                continue
            word = hit.group(0)
            f = {"rule": r["id"], "class": r["class"], "severity": r["severity"], "line": ln, "text": sent,
                 "match": word, "why": r["why"], "instead": r["instead"], "source": r.get("source")}
            rep = r.get("replace", {})
            key = word.lower().strip()
            if key in rep:
                f["rewrite"] = re.sub(re.escape(word), rep[key], sent, count=1, flags=re.I)
            findings.append(f)
    if kind in ("ad", "any") and rules["physical_job_re"].search(low_text) \
            and not rules["physical_demands_re"].search(low_text) and kind == "ad":
        findings.append({"rule": "unstated_demands", "class": "requirement", "severity": "medium", "line": None,
                         "text": None, "match": rules["physical_job_re"].search(low_text).group(0),
                         "why": "A physical job whose ad states no physical demand is not more inclusive: it takes "
                                "away the applicant's chance to judge for themselves, buys first-week exits, and "
                                "removes the opening for an accommodation conversation.",
                         "instead": "State demands as tasks and frequencies: 'on your feet for 8-hour shifts; lift "
                                    "cases up to 40 lbs, about 50 times a shift; work in a 34°F cooler for part of "
                                    "the night'. Not 'must be physically fit'.",
                         "source": None})
    findings.sort(key=lambda f: (SEV[f["severity"]], f["line"] or 0))
    return {"type": kind, "checked": True, "findings": findings}


# ------------------------------------------------------------------ library

def read_library(path):
    if os.path.isdir(path):
        items = []
        for root, _d, names in os.walk(path):
            for n in sorted(names):
                if n.lower().endswith((".txt", ".md")):
                    full = os.path.join(root, n)
                    kind = "any"
                    parent = os.path.basename(root).lower()
                    for t in TYPES:
                        if parent.startswith(t) or n.lower().startswith(t + "_") or n.lower().startswith(t + "-"):
                            kind = t
                    items.append({"id": os.path.relpath(full, path), "type": kind,
                                  "text": read_text(full), "uses": 1})
        if not items:
            raise Refusal("library: no .txt or .md files in that folder.")
        return items
    if not os.path.exists(path):
        raise Refusal(f"library: file not found ({path}).")
    text = read_text(path)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise Refusal("library: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    for h in header:
        if PERSON_COLS.search(h):
            raise Refusal(f"library: column '{h}' looks like candidate information. The library is templates "
                          "only: never paste applications or notes.")
    for c in ("id", "text"):
        if c not in header:
            raise Refusal(f"library: missing column '{c}'. Expected: id,type,text[,uses].")
    items, seen = [], set()
    for n, r in enumerate(rows[1:], 2):
        r = r + [""] * (len(header) - len(r))
        row = {h: r[i] for i, h in enumerate(header)}
        tid = row["id"].strip()
        if not tid:
            raise Refusal(f"library row {n}: no id.")
        if tid in seen:
            raise Refusal(f"library row {n}: id '{tid}' appears twice.")
        seen.add(tid)
        uses = row.get("uses", "").strip()
        try:
            uses = int(float(uses)) if uses else 1
        except ValueError:
            raise Refusal(f"library row {n}: uses '{row['uses']}' is not a number.")
        if uses < 0:
            raise Refusal(f"library row {n}: uses cannot be negative.")
        items.append({"id": tid, "type": row.get("type", "") or "any", "text": row["text"], "uses": uses})
    return items


def read_text(path):
    try:
        raw = open(path, "rb").read()
    except OSError:
        raise Refusal(f"file not found ({path}).")
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def check_library(items, rules):
    results = []
    for it in items:
        r = check_text(it["text"], it["type"], rules)
        r.update(id=it["id"], uses=it["uses"])
        results.append(r)
    # the same line in many templates: fix the master once
    groups = {}
    for r in results:
        for f in r["findings"]:
            k = (f["rule"], re.sub(r"\W+", " ", (f["text"] or f["match"]).lower()).strip())
            g = groups.setdefault(k, {"rule": f["rule"], "class": f["class"], "severity": f["severity"],
                                      "text": f["text"], "match": f["match"], "why": f["why"],
                                      "instead": f["instead"], "rewrite": f.get("rewrite"), "source": f["source"],
                                      "templates": [], "reach": 0})
            if r["id"] not in g["templates"]:
                g["templates"].append(r["id"])
                g["reach"] += r["uses"]
    fix = sorted(groups.values(), key=lambda g: (SEV[g["severity"]], -g["reach"], -len(g["templates"])))
    return {"templates": results, "fix_first": fix,
            "counts": {s: sum(1 for g in fix if g["severity"] == s) for s in SEV},
            "not_checked": [r["id"] for r in results if not r["checked"]],
            "total_reach": sum(r["uses"] for r in results)}


# ------------------------------------------------------------------ output

WORD = {"protected": "protected characteristic", "proxy": "proxy requirement", "coded": "coded wording",
        "requirement": "requirement to challenge"}


def text_single(r):
    out = []
    if not r["checked"]:
        return f"NOT CHECKED ({r['reason']}). The rules are written for English; this text was not read."
    if not r["findings"]:
        return ("No rule matched. That is not a clearance: the rules match known phrasings in English, and wording "
                "is only half of it. Whether your screening excludes people shows up in outcomes, not text.")
    for f in r["findings"]:
        where = f"line {f['line']}" if f["line"] else "whole ad"
        out.append(f"[{f['severity'].upper()}] {WORD[f['class']]}, {where}: \"{f['text'] or f['match']}\"")
        out.append(f"    Why: {f['why']}")
        out.append(f"    Instead: {f['instead']}")
        if f.get("rewrite"):
            out.append(f"    Rewrite: \"{f['rewrite']}\"")
        if f.get("source"):
            out.append(f"    Source: {f['source']}")
    out.append("")
    out.append("A rewritten line is a lower-risk line, not a cleared one. Nothing here is an approval.")
    return "\n".join(out)


def text_library(L):
    c = L["counts"]
    out = [f"Library: {len(L['templates'])} templates reaching {L['total_reach']:,} candidates or sends. "
           f"{c['high']} high, {c['medium']} medium and {c['low']} low findings, counted once per line."]
    if L["not_checked"]:
        out.append(f"Not checked (not English or empty): {', '.join(L['not_checked'])}. Have someone who reads "
                   "the language review them.")
    out.append("")
    out.append("Fix first (severity, then how many candidates the line reaches)")
    for g in L["fix_first"]:
        n = len(g["templates"])
        out.append(f"  [{g['severity'].upper()}] \"{g['text'] or g['match']}\"")
        out.append(f"      {WORD[g['class']]} · in {n} template{'s' if n > 1 else ''} "
                   f"({', '.join(g['templates'])}) · reaches {g['reach']:,}")
        out.append(f"      Instead: {g['instead']}")
        if g.get("rewrite"):
            out.append(f"      Rewrite: \"{g['rewrite']}\"")
        if n > 1:
            out.append("      The same line sits in several templates: fix the master they were copied from.")
    if not L["fix_first"]:
        out.append("  No rule matched. That is not a clearance.")
    out.append("")
    out.append("Nothing here is an approval. A rewritten line is lower-risk, not cleared, and whether your screening "
               "excludes people shows up in your outcomes by group, which this cannot see.")
    return "\n".join(out)


def render(L, path):
    e = html.escape
    rows = "".join(
        f"<tr class=s-{g['severity']}><td>{e(g['severity'])}</td><td>{e(g['text'] or g['match'])}"
        + (f"<div class=rw>Rewrite: {e(g['rewrite'])}</div>" if g.get("rewrite") else "")
        + f"</td><td>{e(WORD[g['class']])}</td><td>{len(g['templates'])}</td><td>{g['reach']:,}</td>"
        f"<td>{e(g['instead'])}</td></tr>" for g in L["fix_first"])
    nc = (f"<p><b>Not checked:</b> {e(', '.join(L['not_checked']))}</p>" if L["not_checked"] else "")
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Candidate wording check</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse;font-size:14px}}td,th{{border:1px solid #ccc;padding:5px 8px;text-align:left;vertical-align:top}}
.s-high td:first-child{{background:#fde2e2}}.s-medium td:first-child{{background:#fff3cd}}.rw{{color:#0a5;margin-top:4px}}</style>
<h1>Candidate wording check</h1>
<p>{len(L['templates'])} templates, reaching {L['total_reach']:,}. Not legal advice. Nothing here is an approval.</p>{nc}
<table><tr><th>Severity</th><th>Line</th><th>Class</th><th>Templates</th><th>Reach</th><th>Instead</th></tr>{rows}</table>
</html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

def run_tests():
    import contextlib
    import shutil
    import tempfile
    rules = load_rules()
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {name}" + (f"  [{detail}]" if detail != "" else ""))

    fx = json.load(open(os.path.join(FIXTURES, "phrases.json"), encoding="utf-8"))
    for case in fx["flag"]:
        r = check_text(case["text"], case.get("type", "any"), rules)
        got = {f["rule"] for f in r["findings"]}
        check(f"flags [{case['rule']}]: {case['text'][:60]}", case["rule"] in got, sorted(got))
    for case in fx["pass"]:
        r = check_text(case["text"], case.get("type", "any"), rules)
        bad = [f["rule"] for f in r["findings"] if f["rule"] not in case.get("allow", [])]
        check(f"does not flag: {case['text'][:60]}", r["checked"] and not bad, bad)
    for case in fx["not_english"]:
        check(f"not checked, never passed: {case[:40]}", not check_text(case, "message", rules)["checked"])

    # the sample library comes back as planted
    exp = json.load(open(os.path.join(SAMPLE, "northline_expected.json"), encoding="utf-8"))
    L = check_library(read_library(os.path.join(SAMPLE, "northline_templates.csv")), rules)
    per = {r["id"]: sorted({f["rule"] for f in r["findings"]}) for r in L["templates"]}
    for tid, want in exp["templates"].items():
        check(f"sample {tid}: findings as planted", per.get(tid) == sorted(want), per.get(tid))
    check("sample: not-checked templates as planted", sorted(L["not_checked"]) == sorted(exp["not_checked"]),
          L["not_checked"])
    top = L["fix_first"][0]
    check("sample: the first fix is the planted one", (top["rule"], top["reach"]) == tuple(exp["first_fix"]),
          (top["rule"], top["reach"]))
    own = [g for g in L["fix_first"] if g["rule"] == "own_car"]
    check("sample: 'own car' grouped across the ads it was copied into, the driver ad left out",
          len(own) == 1 and sorted(own[0]["templates"]) == sorted(exp["own_car_templates"]),
          own and own[0]["templates"])

    # every 'instead' the rules suggest is itself clean
    for r in rules["rules"]:
        ins = check_text(r["instead"].replace("'", " "), "any", rules)
        bad = [f["rule"] for f in ins["findings"] if f["rule"] != "experience_years"]
        check(f"the advice for {r['id']} does not trip a rule itself", not bad, bad)
    for r in rules["rules"]:
        for k, v in r.get("replace", {}).items():
            out = check_text(f"We are hiring a {v} for our store.", "ad", rules)
            check(f"replacement '{v}' is clean", not [f for f in out["findings"] if f["rule"] == r["id"]])

    # gendered titles come with a rewrite
    r = check_text("We are hiring a salesman for our Dayton store.", "ad", rules)
    check("a gendered title gets a direct rewrite", r["findings"] and
          r["findings"][0].get("rewrite") == "We are hiring a sales associate for our Dayton store.")

    # unstated demands only for ads of physical jobs
    phys = "Warehouse associate, nights, $18/hr. Apply today at Northline."
    check("warehouse ad with no demands is flagged", any(f["rule"] == "unstated_demands"
                                                         for f in check_text(phys, "ad", rules)["findings"]))
    check("the same ad with demands stated is not",
          not any(f["rule"] == "unstated_demands" for f in check_text(
              phys + " You'll be on your feet and lift boxes up to 35 lbs.", "ad", rules)["findings"]))
    check("an offer letter for the same job is not asked for demands",
          not any(f["rule"] == "unstated_demands" for f in check_text(phys, "offer", rules)["findings"]))

    tmp = tempfile.mkdtemp(prefix="blc-")

    def w(name, text, mode="w"):
        p = os.path.join(tmp, name)
        if mode == "wb":
            open(p, "wb").write(text)
        else:
            open(p, "w", encoding="utf-8").write(text)
        return p

    try:
        def refused(fn):
            try:
                fn()
                return False
            except Refusal:
                return True
        check("refuses a candidate column", refused(lambda: read_library(
            w("c.csv", "id,type,text,candidate_name\nA,ad,hello,Jo\n"))))
        check("refuses a missing text column", refused(lambda: read_library(w("m.csv", "id,type\nA,ad\n"))))
        check("refuses duplicate ids", refused(lambda: read_library(w("d.csv", "id,text\nA,x\nA,y\n"))))
        check("refuses negative uses", refused(lambda: read_library(w("n.csv", "id,text,uses\nA,x,-3\n"))))
        check("refuses an unknown type", refused(lambda: check_text("hello there", "tweet", rules)))
        check("refuses a missing file", refused(lambda: read_library(os.path.join(tmp, "nope.csv"))))
        folder = os.path.join(tmp, "lib")
        os.makedirs(os.path.join(folder, "ads"))
        open(os.path.join(folder, "ads", "stocker.txt"), "w").write("Stocker. Must have own car. Start 5am.")
        open(os.path.join(folder, "question_app.md"), "w").write("Are you a US citizen?")
        L2 = check_library(read_library(folder), rules)
        check("reads a folder, types from folder and file names",
              {r["id"]: r["type"] for r in L2["templates"]} == {os.path.join("ads", "stocker.txt"): "ad",
                                                                "question_app.md": "question"})
        p16 = w("u16.csv", "id,type,text\nA,ad,Must have own car.\n".encode("utf-16"), "wb")
        check("reads UTF-16", check_library(read_library(p16), rules)["fix_first"][0]["rule"] == "own_car")
        check("reads semicolons", len(read_library(w("s.csv", "id;type;text\nA;ad;hello\n"))) == 1)
        L3 = check_library(read_library(os.path.join(SAMPLE, "northline_templates.csv")), rules)
        hp = os.path.join(tmp, "r.html")
        render(L3, hp)
        body = open(hp, encoding="utf-8").read()
        check("html self-contained", "<script" not in body)
        check("text never says clean or approved", all(x not in text_library(L3).lower()
                                                       for x in ("is clean", "approved", "compliant")))
        check("no match is reported as not a clearance",
              "not a clearance" in text_single(check_text("Shifts start at 6am.", "ad", rules)))
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: missing file exits 3", main(["--text", os.path.join(tmp, "nope.txt")]) == 3)
            check("main: demo exits 1 (the sample has high findings)", main(["--demo"]) == 1)
            check("main: a clean text exits 0", main(["--text", w("ok.txt", "Shifts start at 6am."),
                                                     "--type", "ad"]) == 0)
            check("main: a non-English text exits 1",
                  main(["--text", w("es.txt", "Hola, gracias por aplicar. ¿Puedes venir el martes a las diez?")]) == 1)
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
        rules = load_rules()
        if "--demo" in argv:
            argv = argv + ["--library", os.path.join(SAMPLE, "northline_templates.csv")]
        if opt("--library"):
            L = check_library(read_library(opt("--library")), rules)
            print(text_library(L))
            if opt("--html"):
                render(L, opt("--html"))
            if opt("--json"):
                json.dump(L, open(opt("--json"), "w", encoding="utf-8"), indent=1)
            return 1 if (L["counts"]["high"] or L["not_checked"]) else 0
        if opt("--text"):
            r = check_text(read_text(opt("--text")), opt("--type") or "any", rules)
            print(text_single(r))
            if opt("--html"):
                render(check_library([{"id": os.path.basename(opt("--text")), "type": r["type"],
                                       "text": read_text(opt("--text")), "uses": 1}], rules), opt("--html"))
            return 1 if (not r["checked"] or any(f["severity"] == "high" for f in r["findings"])) else 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the checker failed ({type(exc).__name__}: {exc}). This is a bug in the checker, not a "
              "finding about your text.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
