#!/usr/bin/env python3
"""
Checks a new-hire check-in plan (day 1, day 7, day 30) before anyone runs it,
and reads the one-line log supervisors keep once it is running.

    python3 checkins.py --plan plan.json [--html plan.html]
    python3 checkins.py --log log.csv [--as-of 2026-11-03] [--html report.html] [--json report.json]
    python3 checkins.py --demo
    python3 checkins.py --test

plan.json  the three scripts, owners, escalation routes and close-the-loop
           lines, in the shape of references/sample/northline_plan.json.
log.csv    one row per check-in due:
           site,hire,touchpoint,due,done[,tier,theme,raised,answered]
           hire is an opaque id, never a name. touchpoint is 1, 7 or 30.
           tier is 24h, week, log or grievance when something came back.

The plan check is a rubric the code enforces: three touchpoints that answer
three different questions, four to six questions each, under three minutes
read aloud, an owner and a fallback, every answer routed to a tier, the
answers that must be acted on within 24 hours all present, conduct routed out
of the check-in, every fix one the site can authorise, the loop closed within
seven days, and no question that strays into health, family, age, religion
or immigration.

Exit codes:
    0  plan ready, or log read
    1  plan not ready
    2  no mode given
    3  input refused
    4  the checker itself failed
Standard library only.
"""

import csv
import datetime as dt
import html
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")

DAYS = (1, 7, 30)
TIERS = ("24h", "week", "log", "grievance")
MAX_SECONDS = 180
WORDS_PER_SECOND = 2.5      # read aloud, at a normal pace
ANSWER_SECONDS = 15         # a closed answer, per question
MAX_QUESTION_WORDS = 20     # one breath
LOOP_DAYS = 7
DEADLINE = {"24h": 1, "week": 7, "grievance": 7}
GRACE = {1: 1, 7: 3, 30: 5}  # days after due before a check-in counts as late
MIN_DUE = 10                # below this, a site's completion is not judged

# What must come back as "act within 24 hours", wherever it is asked.
MUST_ACT = {
    "kit": r"\b(kit|ppe|uniform|boots?|gloves?|vest|equipment|locker)\b",
    "next shift": r"\b(next shift|rota|schedule|when (do|are) you (back|in)|tomorrow)\b",
    "break": r"\bbreaks?\b",
    "pay": r"\b(pay|paid|paycheck|payslip|pay stub|wages?)\b",
    "safety": r"\b(safe|safety|unsafe|injur\w*|hurt)\b",
}
CONDUCT = re.compile(r"\b(harass\w*|bull(y|ied|ying)|discriminat\w*|racis\w*|sexis\w*|yell\w*|shout\w*|threat\w*|"
                     r"touch\w*|inappropriate|conduct|abus\w*|slur\w*|hostile)\b", re.I)
NEVER_LOG = re.compile(r"\b(pay|paid|wages?|unsafe|safety|injur\w*|hurt)\b", re.I)

# Friendly small talk on a first week drifts here. Each is matched only when
# the question is about the worker ("you", "your"), not a customer or a place.
RISKY = [
    ("health", r"\b(sick|ill|illness|health|medical|medication|meds|doctor|pain|condition|disab\w*|therapy|"
               r"pregnan\w*|expecting)\b",
     "Ask about the job's demands instead: 'Is the lifting what you expected?' Health stays with the worker unless "
     "they raise it, and then it goes to your accommodation process, not the check-in."),
    ("family and caring", r"\b(kids?|children|child|childcare|babysitter|daycare|husband|wife|partner|married|"
                          r"family|mom|dad|mum)\b",
     "Ask about the schedule, the same way for everyone: 'Do these shift times still work for you?'"),
    ("age", r"\b(how old|your age|retire\w*|young|too old|year were you born|birthday)\b",
     "Leave it out. Nothing in a check-in needs it."),
    ("religion", r"\b((your|go to|attend\w*|at)\s+(church|mosque|temple|synagogue|services?)|religio\w*|pray\w*|"
                 r"sabbath)\b",
     "Ask about days and times: 'Are there days you can't work that we should know about?'"),
    ("immigration and origin", r"\b(visa|papers|citizen\w*|immigra\w*|where are you from|accent|green card|"
                               r"born)\b",
     "Leave it out. Work authorisation is checked once, by the right process, never in conversation."),
]
ABOUT_THEM = re.compile(r"\b(you|your|you're|youre|u|ur)\b", re.I)
OTHERS = re.compile(r"\b(customer|guest|shopper|store|aisle|site|driver|team ?mate|co-?worker|visitor)"
                    r"(?:'s|s'|s)?\s+\w+", re.I)
# Places and things on site that share a word with a risky topic.
FACILITY = re.compile(r"\b(family (restroom|room|bathroom|pack|size)|prayer room|first aid|medical (aisle|kit|bay)|"
                      r"baby (aisle|food|wipes|formula))\b", re.I)
CLOSED_OPENERS = re.compile(r"^(did|do|does|is|are|was|were|has|have|can|could|will|would|how many|how long|"
                            r"which|what time|when|who|where)\b", re.I)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{8,}\d)(?!\w)")
PERSON_COLS = re.compile(r"name|e-?mail|phone|mobile|ssn|dob|birth|address", re.I)


DATEISH = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$|^\d{1,2}/\d{1,2}/\d{2,4}$")


def has_phone(text):
    """A run of 10 to 15 digits with phone punctuation, that is not a date."""
    for m in PHONE.finditer(text):
        cand = m.group(1).strip()
        digits = re.sub(r"\D", "", cand)
        if 10 <= len(digits) <= 15 and not DATEISH.match(cand):
            return True
    return False


class Refusal(Exception):
    pass


def words(s):
    return len(re.findall(r"[A-Za-z0-9']+", s or ""))


# ------------------------------------------------------------------ the plan

def need(obj, key, kind, where):
    if not isinstance(obj, dict) or key not in obj or not isinstance(obj[key], kind):
        raise Refusal(f"plan: {where} needs \"{key}\" ({'text' if kind is str else kind.__name__}).")
    return obj[key]


def load_plan(path):
    try:
        plan = json.load(open(path, encoding="utf-8-sig"))
    except OSError:
        raise Refusal(f"plan: file not found ({path}).")
    except ValueError as exc:
        raise Refusal(f"plan: not valid JSON ({exc}).")
    validate_shape(plan)
    return plan


def validate_shape(plan):
    if not isinstance(plan, dict):
        raise Refusal("plan: expected an object with \"touchpoints\".")
    need(plan, "role", str, "the plan")
    need(plan, "site_can_fix", list, "the plan")
    if not all(isinstance(x, str) for x in plan["site_can_fix"]):
        raise Refusal("plan: site_can_fix must be a list of text.")
    for k in ("escalation_owners", "close_the_loop"):
        if k in plan and not isinstance(plan[k], dict):
            raise Refusal(f"plan: \"{k}\" must be an object.")
    tps = need(plan, "touchpoints", list, "the plan")
    if not tps:
        raise Refusal("plan: \"touchpoints\" is empty.")
    for t in tps:
        if not isinstance(t, dict) or not isinstance(t.get("day"), int):
            raise Refusal("plan: every touchpoint needs a whole-number \"day\".")
        where = f"day {t['day']}"
        for k in ("owner", "fallback", "when", "opening", "closing"):
            need(t, k, str, where)
        qs = need(t, "questions", list, where)
        for i, q in enumerate(qs, 1):
            need(q, "text", str, f"{where} question {i}")
            routes = need(q, "routes", list, f"{where} question {i}")
            for j, r in enumerate(routes, 1):
                need(r, "answer", str, f"{where} question {i} route {j}")
                need(r, "tier", str, f"{where} question {i} route {j}")
                for k in ("to", "fix", "action"):
                    if k in r and not isinstance(r[k], str):
                        raise Refusal(f"plan: {where} question {i} route {j}: \"{k}\" must be text.")
            if "probe" in q and not isinstance(q["probe"], str):
                raise Refusal(f"plan: {where} question {i}: \"probe\" must be text.")


def risky(text):
    if not ABOUT_THEM.search(text):
        return []
    found = []
    stripped = FACILITY.sub(" ", OTHERS.sub(" ", text))
    for topic, pattern, alt in RISKY:
        m = re.search(pattern, stripped, re.I)
        if m:
            # "a customer's kids" is about the customer; the pattern only counts when it is not attached to one
            found.append({"topic": topic, "word": m.group(0), "instead": alt})
    return found


def seconds(t):
    spoken = words(t.get("opening")) + words(t.get("closing")) + sum(words(q["text"]) for q in t["questions"])
    return round(spoken / WORDS_PER_SECOND + ANSWER_SECONDS * len(t["questions"]))


def check_plan(plan):
    validate_shape(plan)
    block, warn = [], []
    can_fix = [str(x).strip().lower() for x in plan["site_can_fix"]]
    owners = plan.get("escalation_owners") or {}
    by_day = {}
    for t in plan["touchpoints"]:
        if t["day"] in by_day:
            block.append(f"Day {t['day']} appears twice.")
        by_day[t["day"]] = t
    for d in DAYS:
        if d not in by_day:
            block.append(f"No day {d} check-in." + (" Day 7 is the one nobody else catches: keep it if you keep "
                                                    "only one." if d == 7 else ""))
    extra = sorted(set(by_day) - set(DAYS))
    if extra:
        warn.append(f"Extra touchpoint(s) on day {', '.join(map(str, extra))}: checked like the others. Add a "
                    "touchpoint rather than lengthen one, but four is the most a site will keep up.")

    covered = {k: False for k in MUST_ACT}
    for d, t in sorted(by_day.items()):
        n = len(t["questions"])
        if not 4 <= n <= 6:
            block.append(f"Day {d}: {n} questions. Four to six, or it will not get run on a shift.")
        secs = seconds(t)
        t["_seconds"] = secs
        if secs > MAX_SECONDS:
            block.append(f"Day {d}: about {secs} seconds read aloud with answers. Under {MAX_SECONDS}, or it gets "
                         "skipped after the first few hires. Cut a question or move it to the probes.")
        if t["owner"].strip().lower() == t["fallback"].strip().lower():
            block.append(f"Day {d}: the fallback is the owner. Name someone else for the days the owner is off.")
        for i, q in enumerate(t["questions"], 1):
            txt = q["text"].strip()
            tag = f"Day {d} Q{i}"
            if words(txt) > MAX_QUESTION_WORDS:
                block.append(f"{tag}: {words(txt)} words. One breath is {MAX_QUESTION_WORDS} or fewer; move the "
                             "rest to the probe.")
            if txt.count("?") > 1:
                block.append(f"{tag}: two questions in one. The answer will be to one of them.")
            if not CLOSED_OPENERS.search(txt):
                warn.append(f"{tag}: open question ('{txt[:40]}...'). Closed or near-closed answers are what a "
                            "supervisor can route in 30 seconds.")
            for hit in risky(txt) + risky(q.get("probe", "")):
                block.append(f"{tag}: strays into {hit['topic']} ('{hit['word']}'). {hit['instead']}")
            if not q["routes"]:
                block.append(f"{tag}: no answer is routed. Something that comes back with nowhere to go teaches "
                             "a new hire that saying something is pointless.")
            for r in q["routes"]:
                tier = r["tier"].strip().lower()
                ans = r["answer"] + " " + str(r.get("action", ""))
                if tier not in TIERS:
                    block.append(f"{tag}: tier '{r['tier']}' is not one of {', '.join(TIERS)}.")
                    continue
                if CONDUCT.search(ans) and tier != "grievance":
                    block.append(f"{tag}: '{r['answer']}' is about someone's conduct and is routed to {tier}. "
                                 "Conduct leaves the check-in for your grievance route, with a named owner.")
                if tier == "log" and NEVER_LOG.search(ans):
                    block.append(f"{tag}: '{r['answer']}' is only logged. Pay and safety are never a theme to "
                                 "aggregate; they need a response.")
                if tier == "24h":
                    for k, pat in MUST_ACT.items():
                        if re.search(pat, ans, re.I):
                            covered[k] = True
                if tier in ("24h", "week"):
                    to = str(r.get("to", "")).strip()
                    fix = str(r.get("fix", "")).strip().lower()
                    if not to:
                        block.append(f"{tag}: '{r['answer']}' goes to nobody. Name the role that acts.")
                    if fix and fix != "escalate" and fix not in can_fix:
                        block.append(f"{tag}: the fix '{r.get('fix')}' is not something the site can do without "
                                     "permission (site_can_fix). Route it to someone who can authorise it, or add "
                                     "it to the list if a site really can.")
                    if not fix:
                        block.append(f"{tag}: '{r['answer']}' has no fix. Say what the site does, or 'escalate'.")
                if tier == "grievance" and not owners.get("grievance"):
                    block.append("A grievance route is used but escalation_owners has no \"grievance\" owner.")
    for k, ok in covered.items():
        if not ok:
            block.append(f"Nothing about {k} is routed to 'act within 24 hours'. It is the kind of answer that "
                         "loses a hire in a week if it waits.")
    if 7 in by_day and 30 in by_day and \
            by_day[7]["owner"].strip().lower() == by_day[30]["owner"].strip().lower():
        block.append("Day 30 has the same owner as day 7. By day 30 the supervisor is one of the things worth "
                     "asking about: give day 30 to their manager or a neighbouring site lead.")
    loop = plan.get("close_the_loop") or {}
    for k in ("done", "in_progress", "declined"):
        if not str(loop.get(k, "")).strip():
            block.append(f"No close-the-loop line for '{k}'. Every escalated answer gets one back, including "
                         "the ones you refuse.")
    within = loop.get("within_days")
    if not isinstance(within, int) or within > LOOP_DAYS or within < 1:
        block.append(f"close_the_loop.within_days must be 1 to {LOOP_DAYS}. A worker who hears nothing for two "
                     "weeks stops saying anything.")
    for k in ("24h", "week"):
        if not str(owners.get(k, "")).strip():
            block.append(f"escalation_owners has no '{k}' owner.")
    return {"ready": not block, "blocking": block, "warnings": warn,
            "seconds": {d: by_day[d].get("_seconds") for d in sorted(by_day)}}


def text_plan(res, plan):
    out = [f"Check-in plan: {plan['role']}"]
    for d, s in res["seconds"].items():
        out.append(f"  Day {d}: about {s} seconds")
    out.append("")
    if res["ready"]:
        out.append("READY to run.")
    else:
        out.append(f"NOT READY: {len(res['blocking'])} thing(s) to fix.")
        out += [f"  - {b}" for b in res["blocking"]]
    if res["warnings"]:
        out.append("Notes:")
        out += [f"  - {w}" for w in res["warnings"]]
    return "\n".join(out)


def render_plan(plan, path):
    e = html.escape
    cards = []
    tier_word = {"24h": "Act within 24 hours", "week": "This week, site lead", "log": "Log the theme",
                 "grievance": "Grievance route"}
    for t in sorted(plan["touchpoints"], key=lambda x: x["day"]):
        qs = "".join(f"<li>{e(q['text'])}" + (f"<div class=probe>If there's time: {e(q['probe'])}</div>"
                                                if q.get("probe") else "") + "</li>" for q in t["questions"])
        routes = "".join(
            f"<tr><td>{e(r['answer'])}</td><td class=t-{e(r['tier'])}>{e(tier_word.get(r['tier'], r['tier']))}</td>"
            f"<td>{e(str(r.get('to', '')))}</td><td>{e(str(r.get('action', '')))}</td></tr>"
            for q in t["questions"] for r in q["routes"])
        cards.append(f"""<section><h2>Day {t['day']}: {e(t['when'])}</h2>
<p class=who>Asked by <b>{e(t['owner'])}</b>; if they are off, <b>{e(t['fallback'])}</b>. About {seconds(t)} seconds.</p>
<p class=say>{e(t['opening'])}</p><ol>{qs}</ol><p class=say>{e(t['closing'])}</p>
<table><tr><th>If the answer is</th><th>Then</th><th>Who</th><th>What</th></tr>{routes}</table></section>""")
    loop = plan["close_the_loop"]
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>New-hire check-ins</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;color:#111}}
section{{border-top:2px solid #111;margin-top:24px;page-break-inside:avoid}}.say{{font-style:italic}}
.probe{{color:#555;font-size:13px}}table{{border-collapse:collapse;width:100%;font-size:13px}}
td,th{{border:1px solid #ccc;padding:4px 6px;text-align:left;vertical-align:top}}
.t-24h{{background:#fde2e2}}.t-week{{background:#fff3cd}}.t-grievance{{background:#e7e0f7}}</style>
<h1>New-hire check-ins: {e(plan['role'])}</h1>
{''.join(cards)}
<section><h2>Closing the loop, within {loop['within_days']} days</h2><ul>
<li><b>Done:</b> {e(loop['done'])}</li><li><b>In progress:</b> {e(loop['in_progress'])}</li>
<li><b>Not possible:</b> {e(loop['declined'])}</li></ul>
<p>Whoever asked the question owns the answer back.</p></section></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ the log

def read_csv(path, required):
    if not path or not os.path.exists(path):
        raise Refusal(f"log: file not found ({path}).")
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="strict")
    if EMAIL.search(text):
        raise Refusal("log: the file contains an email address. Use an opaque hire id, never contact details.")
    if has_phone(text):
        raise Refusal("log: the file contains what looks like a phone number. Remove it and try again.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise Refusal("log: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    for h in header:
        if PERSON_COLS.search(h):
            raise Refusal(f"log: column '{h}' looks like personal information. The log needs an opaque hire id "
                          "only.")
    miss = [c for c in required if c not in header]
    if miss:
        raise Refusal(f"log: missing column(s) {', '.join(miss)}. Expected: {', '.join(required)}.")
    return [({h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)}, n)
            for n, r in enumerate(rows[1:], start=2)]


def parse_date(s, where):
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    raise Refusal(f"{where}: '{s}' is not a date (use YYYY-MM-DD).")


def wilson(k, n, z=1.645):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def read_log(path, as_of=None):
    rows = read_csv(path, ["site", "hire", "touchpoint", "due", "done"])
    if not rows:
        raise Refusal("log: no rows under the header.")
    checks, escal = {}, []
    latest = None
    for r, n in rows:
        where = f"log row {n}"
        try:
            tp = int(r["touchpoint"].lower().replace("day", "").strip())
        except ValueError:
            raise Refusal(f"{where}: touchpoint '{r['touchpoint']}' should be 1, 7 or 30.")
        if tp not in DAYS:
            raise Refusal(f"{where}: touchpoint {tp} should be 1, 7 or 30.")
        if not r["hire"] or not r["site"]:
            raise Refusal(f"{where}: site and hire are both needed.")
        if len(r["hire"].split()) > 1 and all(w[:1].isupper() for w in r["hire"].split()):
            raise Refusal(f"{where}: hire '{r['hire']}' looks like a name. Use an opaque id.")
        due = parse_date(r["due"], where)
        if due is None:
            raise Refusal(f"{where}: no due date.")
        done = parse_date(r["done"], where)
        if done and done < due - dt.timedelta(days=1):
            raise Refusal(f"{where}: done on {done}, before it was due ({due}).")
        latest = max(d for d in (latest, due, done) if d)
        key = (r["site"], r["hire"], tp)
        c = checks.setdefault(key, {"site": r["site"], "hire": r["hire"], "tp": tp, "due": due, "done": None})
        if c["due"] != due:
            raise Refusal(f"{where}: {r['hire']} day {tp} has two different due dates.")
        if done and (c["done"] is None or done < c["done"]):
            c["done"] = done
        tier = r.get("tier", "").strip().lower()
        if tier:
            if tier not in TIERS:
                raise Refusal(f"{where}: tier '{tier}' should be one of {', '.join(TIERS)}.")
            raised = parse_date(r.get("raised", ""), where) or done
            if raised is None:
                raise Refusal(f"{where}: something was escalated but the check-in has no done or raised date.")
            ans = parse_date(r.get("answered", ""), where)
            if ans and ans < raised:
                raise Refusal(f"{where}: answered before it was raised.")
            escal.append({"site": r["site"], "hire": r["hire"], "tp": tp, "tier": tier,
                          "theme": r.get("theme", "").strip(), "raised": raised, "answered": ans})
    as_of = as_of or latest
    return checks, escal, as_of


def analyse_log(checks, escal, as_of):
    sites = sorted({c["site"] for c in checks.values()})
    completion, flags = {}, []
    pool = {}
    for tp in DAYS:
        due = [c for c in checks.values() if c["tp"] == tp and c["due"] + dt.timedelta(days=GRACE[tp]) <= as_of]
        k = sum(1 for c in due if c["done"])
        pool[tp] = (k, len(due))
    for s in sites:
        completion[s] = {}
        for tp in DAYS:
            due = [c for c in checks.values() if c["site"] == s and c["tp"] == tp
                   and c["due"] + dt.timedelta(days=GRACE[tp]) <= as_of]
            k = sum(1 for c in due if c["done"])
            late = sum(1 for c in due if c["done"] and c["done"] > c["due"] + dt.timedelta(days=GRACE[tp]))
            lo, hi = wilson(k, len(due))
            row = {"due": len(due), "done": k, "late": late, "rate": round(k / len(due), 2) if due else None,
                   "ci90": [round(lo, 2), round(hi, 2)], "judged": len(due) >= MIN_DUE}
            completion[s][tp] = row
            pk, pn = pool[tp]
            if row["judged"] and pn and hi < 0.5:
                flags.append({"type": "low_completion", "site": s, "touchpoint": tp, "rate": row["rate"],
                              "say": f"{s} ran {k} of {len(due)} day-{tp} check-ins ({round(k / len(due) * 100)}%, "
                                     f"90% range {round(lo * 100)}-{round(hi * 100)}%). Below half even at the top "
                                     f"of the range: that is staffing or span of control, not the script. A "
                                     f"shorter script will not fix it; fewer hires per supervisor will."})
    # escalations
    open_late, late_closed, by_tier, misrouted = [], [], {}, []
    themes = {}
    for e in escal:
        t = e["tier"]
        b = by_tier.setdefault(t, {"raised": 0, "answered_in_time": 0, "open": 0})
        b["raised"] += 1
        limit = DEADLINE.get(t)
        if t == "log":
            month = e["raised"].strftime("%Y-%m")
            themes.setdefault(e["theme"] or "(no theme)", {}).setdefault(month, 0)
            themes[e["theme"] or "(no theme)"][month] += 1
            if CONDUCT.search(e["theme"]) or NEVER_LOG.search(e["theme"]):
                misrouted.append(e)
            continue
        if e["answered"] is None:
            b["open"] += 1
            if (as_of - e["raised"]).days > limit:
                open_late.append(e)
        elif (e["answered"] - e["raised"]).days <= limit:
            b["answered_in_time"] += 1
        else:
            late_closed.append(e)
    for e in misrouted:
        what = "conduct" if CONDUCT.search(e["theme"]) else "pay or safety"
        flags.append({"type": "misrouted", "site": e["site"], "hire": e["hire"], "theme": e["theme"],
                      "say": f"{e['site']}, hire {e['hire']}, day {e['tp']}: '{e['theme']}' was logged as a theme. "
                             f"It is {what}: it needed a response, "
                             + ("through the grievance route with a named owner." if what == "conduct"
                                else "within 24 hours.")})
    for e in open_late:
        flags.append({"type": "overdue", "site": e["site"], "hire": e["hire"], "tier": e["tier"],
                      "say": f"{e['site']}, hire {e['hire']}: a {e['tier']} item raised {e['raised']} "
                             f"('{e['theme'] or 'no theme'}') has no answer after {(as_of - e['raised']).days} "
                             f"days. The deadline was {DEADLINE[e['tier']]}."})
    # sites that answer 24h items late, as a pattern
    per_site = {}
    for e in escal:
        if e["tier"] != "24h":
            continue
        d = per_site.setdefault(e["site"], [0, 0])
        d[1] += 1
        if e["answered"] and (e["answered"] - e["raised"]).days <= 1:
            d[0] += 1
    for s, (ok, n) in sorted(per_site.items()):
        if n >= 4 and ok / n < 0.5:
            flags.append({"type": "slow_24h", "site": s, "ok": ok, "n": n,
                          "say": f"{s} answered {ok} of {n} act-within-24-hours items on time. The escalation "
                                 f"tier is only as real as the person receiving it: find out who that is at {s} "
                                 f"and whether their inbox is read on a shift day."})
    top = sorted(((sum(m.values()), t) for t, m in themes.items() if t not in {e["theme"] for e in misrouted}),
                 reverse=True)[:5]
    return {"as_of": as_of.isoformat(), "sites": sites, "completion": completion,
            "pool": {tp: {"done": k, "due": n} for tp, (k, n) in pool.items()},
            "escalations": by_tier, "flags": flags,
            "themes": [{"theme": t, "count": c, "by_month": themes[t]} for c, t in top]}


def text_log(r):
    out = [f"Check-in log, as of {r['as_of']}", "", "Completion (due and past its grace period)"]
    out.append(f"  {'site':<14}" + "".join(f"{'day ' + str(d):>16}" for d in DAYS))
    for s in r["sites"]:
        cells = []
        for d in DAYS:
            c = r["completion"][s][d]
            cells.append(f"{c['done']}/{c['due']}" + ("" if c["judged"] else "*"))
        out.append(f"  {s:<14}" + "".join(f"{x:>16}" for x in cells))
    out.append(f"  * under {MIN_DUE} due: not judged.")
    out.append("")
    out.append("Escalations")
    for t in ("24h", "week", "grievance"):
        b = r["escalations"].get(t)
        if b:
            out.append(f"  {t:<10} {b['raised']} raised, {b['answered_in_time']} answered within "
                       f"{DEADLINE[t]} day(s), {b['open']} still open")
    out.append("")
    out.append("What needs attention")
    out += [f"  - {f['say']}" for f in r["flags"]] or ["  - Nothing."]
    if r["themes"]:
        out.append("")
        out.append("Themes logged (for the monthly review)")
        for t in r["themes"]:
            out.append(f"  {t['count']:>3}  {t['theme']}")
    out.append("")
    out.append("This shows whether check-ins happen and get answered. It cannot show whether they changed who "
               "stayed: that needs hires who got them compared with hires who did not, from your own records.")
    return "\n".join(out)


def render_log(r, path):
    e = html.escape
    rows = "".join(
        f"<tr><td>{e(s)}</td>" + "".join(
            f"<td class={'low' if any(f['type'] == 'low_completion' and f['site'] == s and f['touchpoint'] == d for f in r['flags']) else ''}>"
            f"{r['completion'][s][d]['done']}/{r['completion'][s][d]['due']}</td>" for d in DAYS) + "</tr>"
        for s in r["sites"])
    flags = "".join(f"<li>{e(f['say'])}</li>" for f in r["flags"]) or "<li>Nothing.</li>"
    themes = "".join(f"<li>{t['count']} &middot; {e(t['theme'])}</li>" for t in r["themes"])
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Check-in log</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:760px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px}}.low{{background:#fde2e2}}</style>
<h1>Check-in log, as of {e(r['as_of'])}</h1><h2>Completion</h2>
<table><tr><th>Site</th>{''.join(f'<th>Day {d}</th>' for d in DAYS)}</tr>{rows}</table>
<h2>What needs attention</h2><ul>{flags}</ul><h2>Themes</h2><ul>{themes}</ul></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

def run_tests():
    import copy
    import shutil
    import tempfile
    import contextlib
    passed = failed = 0

    def check(name, ok):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print("FAIL " + name)

    plan = load_plan(os.path.join(SAMPLE, "northline_plan.json"))
    res = check_plan(copy.deepcopy(plan))
    check(f"sample plan is ready ({res['blocking']})", res["ready"])
    check("sample: every touchpoint under three minutes", all(s <= MAX_SECONDS for s in res["seconds"].values()))

    # broken plans: each must fail for exactly the named reason
    broken = json.load(open(os.path.join(FIXTURES, "broken_plans.json"), encoding="utf-8"))
    for case in broken["cases"]:
        p = copy.deepcopy(plan)
        for op in case["ops"]:
            target = p
            path = op["path"]
            for k in path[:-1]:
                target = target[k]
            if op["op"] == "set":
                target[path[-1]] = op["value"]
            elif op["op"] == "del":
                del target[path[-1]]
            elif op["op"] == "append":
                target[path[-1]].append(op["value"])
        try:
            r = check_plan(p)
            ok = (not r["ready"]) and any(case["expect"].lower() in b.lower() for b in r["blocking"])
            if not ok:
                print(f"   got: {r['blocking']}")
            check(f"broken plan caught: {case['name']}", ok)
        except Refusal as exc:
            check(f"broken plan caught: {case['name']} (refused: {exc})", case.get("refuse", False))

    # risky phrasings and the safe ones next to them
    qs = json.load(open(os.path.join(FIXTURES, "questions.json"), encoding="utf-8"))
    for q in qs["risky"]:
        check(f"risky caught: {q}", bool(risky(q)))
    for q in qs["safe"]:
        check(f"safe not flagged: {q}", not risky(q))

    # the log
    exp = json.load(open(os.path.join(SAMPLE, "northline_log_expected.json"), encoding="utf-8"))
    c, e, asof = read_log(os.path.join(SAMPLE, "northline_log.csv"), dt.date.fromisoformat(exp["as_of"]))
    r = analyse_log(c, e, asof)
    got = sorted((f["type"], f["site"]) for f in r["flags"])
    want = sorted(tuple(x) for x in exp["flags"])
    check(f"log: flags exactly as planted (got {got})", got == want)
    check("log: top theme as planted", r["themes"] and r["themes"][0]["theme"] == exp["top_theme"])
    check("log: misrouted conduct is never shown as a theme",
          all(not CONDUCT.search(t["theme"]) for t in r["themes"]))
    check("log: text says it cannot show retention", "cannot show whether" in text_log(r))

    tmp = tempfile.mkdtemp(prefix="cid-")

    def w(name, text):
        p = os.path.join(tmp, name)
        open(p, "w", encoding="utf-8").write(text)
        return p

    head = "site,hire,touchpoint,due,done,tier,theme,raised,answered\n"
    try:
        def refused(text):
            try:
                read_log(w("x.csv", text))
                return False
            except Refusal:
                return True
        check("log refuses an email", refused(head + "A,h1,1,2026-10-01,2026-10-01,,,,\nA,jo@x.com,1,2026-10-01,,,,,\n"))
        check("log refuses a phone", refused(head + "A,h1,1,2026-10-01,,,call 555 201 3344,,\n"))
        check("log refuses a name column", refused("site,name,touchpoint,due,done\nA,Jo,1,2026-10-01,\n"))
        check("log refuses a name as a hire id", refused(head + "A,Maria Lopez,1,2026-10-01,,,,,\n"))
        check("log refuses touchpoint 14", refused(head + "A,h1,14,2026-10-01,,,,,\n"))
        check("log refuses a bad date", refused(head + "A,h1,1,yesterday,,,,,\n"))
        check("log refuses done before due", refused(head + "A,h1,7,2026-10-10,2026-10-01,,,,\n"))
        check("log refuses answered before raised",
              refused(head + "A,h1,7,2026-10-10,2026-10-10,24h,boots,2026-10-10,2026-10-05\n"))
        check("log refuses an unknown tier", refused(head + "A,h1,7,2026-10-10,2026-10-10,urgent,x,,\n"))
        check("log refuses a missing column", refused("site,hire,due,done\nA,h1,2026-10-01,\n"))
        check("log refuses an empty file", refused(""))
        c, e, a = read_log(w("d.csv", head + "A,h1,day 7,10/02/2026,10/02/2026,,,,\n"))
        check("log reads 'day 7' and US dates", list(c.values())[0]["tp"] == 7)
        c, e, a = read_log(w("s.csv", head.replace(",", ";") + "A;h1;1;2026-10-01;2026-10-01;;;;\n"))
        check("log reads semicolons", len(c) == 1)
        # small sites are never judged
        rows = "".join(f"S,h{i},7,2026-09-01,,,,,\n" for i in range(9))
        c, e, a = read_log(w("sm.csv", head + rows))
        r = analyse_log(c, e, dt.date(2026, 11, 1))
        check("9 due check-ins, none done: not judged", not any(f["type"] == "low_completion" for f in r["flags"]))
        rows = "".join(f"S,h{i},7,2026-09-01,,,,,\n" for i in range(12))
        c, e, a = read_log(w("sm2.csv", head + rows))
        r = analyse_log(c, e, dt.date(2026, 11, 1))
        check("12 due, none done: flagged", any(f["type"] == "low_completion" for f in r["flags"]))
        # not yet due is not missing
        rows = "".join(f"S,h{i},30,2026-10-30,,,,,\n" for i in range(15))
        c, e, a = read_log(w("nd.csv", head + rows))
        r = analyse_log(c, e, dt.date(2026, 11, 1))
        check("check-ins inside their grace period are not counted missing", r["completion"]["S"][30]["due"] == 0)
        # outputs
        c, e, asof = read_log(os.path.join(SAMPLE, "northline_log.csv"))
        r = analyse_log(c, e, asof)
        hp = os.path.join(tmp, "r.html")
        render_log(r, hp)
        check("log html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        render_plan(plan, os.path.join(tmp, "p.html"))
        body = open(os.path.join(tmp, "p.html"), encoding="utf-8").read()
        check("plan html shows every question", all(html.escape(q["text"]) in body
                                                    for t in plan["touchpoints"] for q in t["questions"]))
        check("json serialisable", bool(json.dumps(r, default=str)))
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: missing plan exits 3", main(["--plan", os.path.join(tmp, "nope.json")]) == 3)
            check("main: demo exits 0", main(["--demo"]) == 0)
            w("bad.json", "{oops")
            check("main: broken JSON exits 3", main(["--plan", os.path.join(tmp, "bad.json")]) == 3)
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
        if "--demo" in argv:
            plan = load_plan(os.path.join(SAMPLE, "northline_plan.json"))
            print(text_plan(check_plan(plan), plan))
            print()
            exp = json.load(open(os.path.join(SAMPLE, "northline_log_expected.json"), encoding="utf-8"))
            c, e, a = read_log(os.path.join(SAMPLE, "northline_log.csv"), dt.date.fromisoformat(exp["as_of"]))
            print(text_log(analyse_log(c, e, a)))
            return 0
        if opt("--plan"):
            plan = load_plan(opt("--plan"))
            res = check_plan(plan)
            print(text_plan(res, plan))
            if opt("--html"):
                if res["ready"]:
                    render_plan(plan, opt("--html"))
                else:
                    print("No sheet written: fix the blocking items first.")
            return 0 if res["ready"] else 1
        if opt("--log"):
            as_of = opt("--as-of")
            as_of = parse_date(as_of, "--as-of") if as_of else None
            c, e, a = read_log(opt("--log"), as_of)
            r = analyse_log(c, e, a)
            print(text_log(r))
            if opt("--html"):
                render_log(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1, default=str)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the checker failed ({type(exc).__name__}: {exc}). This is a bug in the checker, "
              "not a finding about your plan.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
