#!/usr/bin/env python3
"""
Checks a strategic leadership diagnostic before anyone reads it, against the
situation it was written from, then renders it.

    python3 diagnose.py --check diagnostic.json --situation situation.md
                        [--previous earlier_diagnostic.json] [--as-of 2026-11-11]
                        [--md report.md] [--html report.html] [--json check.json]
    python3 diagnose.py --demo
    python3 diagnose.py --test

situation.md    the person's own account, and their answers to the
                diagnostic's questions, kept word for word. Every piece of
                evidence the diagnostic cites must be found in it.
diagnostic.json the diagnostic, in the shape of
                references/sample/halden_diagnostic.json.

The check is a rubric the code enforces. All five values from The Power of HR
are examined, by their exact names. Every strength and development
opportunity rests on evidence quoted from the situation, never on silence:
where the account says nothing, the value is "not enough evidence" with the
questions to ask. Facts, observed results, interpretations and intentions are
kept apart, and a strength never rests on intentions alone. A missing
perspective is named with who to ask. Nothing judges the person as a leader
overall. There is one priority move. The executive brief names the issue, a
point of view with its evidence, trade-offs, the business and the people
impact, who decides by when, and an ask short enough to say. Each action has
a named owner, something you could observe or count, and a review date.
Things the person said that the diagnostic should challenge ("I already know
what the problem is") must be answered. On a return visit, every earlier
measure gets a result, and approval is never counted as a result.

Exit codes:
    0  diagnostic ready
    1  diagnostic not ready
    2  no mode given
    3  input refused
    4  the checker itself failed
Standard library only.
"""

import copy
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")

# The five values from Joey V. Price's The Power of HR. Exact names: the
# diagnostic is built on them and the check refuses a renamed or missing one.
VALUES = [
    "Own Your Expertise",
    "Be Part Coach, Part Cheerleader",
    "Ignite the Spark",
    "Bring Clarity From the Clouds",
    "Forward and Adaptive Beats Static and Slow",
]
FINDING_TYPES = ("strength", "opportunity", "not_enough_evidence")
KINDS = ("fact", "result", "interpretation", "intention")
AUTHORITY = ("mine", "needs_commitment")
RESULTS = ("met", "partly", "not_met", "not_observed")

MIN_QUOTE_WORDS = 4
MAX_QUOTE_WORDS = 60
ASK_MAX_WORDS = 80
ASK_WARN_WORDS = 60
PLAN_MAX = 6
REVIEW_MAX_DAYS = 120
REVIEW_WARN_DAYS = 90

VAGUE_OWNERS = {"we", "us", "everyone", "everybody", "all", "all of us", "team", "the team", "hr",
                "the hr team", "leadership", "management", "tbd", "tbc", "someone", "n/a", "na",
                "somebody", "anyone", "the business", "they"}
UNKNOWN_WORDS = {"", "unknown", "tbd", "tbc", "n/a", "na", "?", "not sure"}

# A measure has to be something you could count, or see happen.
OBSERVABLE = re.compile(
    r"\b(agree[sd]?|signs?|signed|approve[sd]?|decide[sd]?|publish(ed|es)?|hold|held|sends?|sent|"
    r"schedule[sd]?|complete[sd]?|document(ed|s)?|attend(ed|s)?|name[sd]?|assign(ed|s)?|"
    r"present(ed|s)?|share[sd]?|return(ed|s)?|deliver(ed|s)?|written|in writing|launch(ed|es)?|"
    r"record(ed|s)?|count(ed)?|rate|percent|on file|in place|filled|hired|started|run|ran)\b", re.I)
VAGUE_HEAD = re.compile(
    r"^\s*(a |an )?(better|improved?|stronger|more|increased?|greater|enhanced?|good|positive|"
    r"higher|clearer|deeper)\s+(sense of\s+)?(engagement|alignment|buy-?in|trust|morale|awareness|"
    r"understanding|communication|relationships?|culture|collaboration|partnership|confidence|"
    r"ownership|visibility|support)\b", re.I)

# Judging the person rather than the approach. One account cannot establish
# someone's overall effectiveness as a leader, in either direction.
TRAIT = [
    re.compile(r"\byou(?: are|'re| re)\s+(?:a |an )?(?:very |really |quite )?(?:weak|poor|bad|ineffective|"
               r"natural|born|strong|great|excellent|terrible|exceptional|gifted|"
               r"not (?:a |an )?(?:strategic|good|real|effective|credible))\b(?! (?:case|position|reason|"
               r"point|argument|basis|place|start|foundation|number|fit|choice|owner|candidate|sponsor))", re.I),
    re.compile(r"\byou (?:lack|have no|are lacking)\s+(?:any |real )?(?:leadership|executive presence|"
               r"strategic|confidence|credibility|influence|courage|vision)\b", re.I),
    re.compile(r"\byou (?:always|never|tend to|consistently) (?:avoid|struggle|fail|shy away|back down|overthink|"
               r"hesitate|get defensive|defer|cave|over-?promise|under-?deliver|freeze|lack)\w*\b", re.I),
    re.compile(r"\byour leadership(?: style)? (?:is|was) (?:weak|poor|ineffective|lacking|strong|"
               r"excellent|outstanding|inadequate)\b", re.I),
    re.compile(r"\b(?:poor|weak|bad|ineffective|natural|born|terrible|great) leader\b", re.I),
    re.compile(r"\bas a leader,? you (?:are|lack|fail|struggle)\b", re.I),
]

# Things the person says that the diagnostic must answer (the skill's
# "What it pushes back on"). Each is matched on the situation text.
PUSHBACK = {
    "certainty": [
        r"\bi (?:already |just )?know (?:what|exactly|why|that) (?:the |it |this |they )",
        r"\bthe (?:real|true|root|actual) (?:problem|issue|cause) is\b",
        r"\b(?:i'?m|i am) (?:sure|certain|convinced|positive) (?:that |it |the |this |they )",
        r"\bobviously\b",
        r"\bthere'?s no (?:question|doubt) (?:that|it|the)\b",
    ],
    "blame": [
        r"\b(?:leadership|executives?|the c-?suite|the ceo|the coo|the cfo|the business|management|"
        r"operations|ops|finance|they|he|she)\s+(?:just\s+|simply\s+|still\s+)?(?:do(?:es)?n'?t|do(?:es)? not|"
        r"never|won'?t|will not)\s+(?:really\s+)?(?:understand|get|value|listen to|care about|respect)\s+"
        r"(?:hr|us|people|what (?:we|hr)|the people side)\b",
        r"\bhr (?:is|gets) (?:never|not|rarely) (?:heard|listened to|taken seriously|at the table)\b",
    ],
    "avoidance": [
        r"\b(?:don'?t|do not|didn'?t) want to (?:upset|rock the boat|offend|make (?:it|things) awkward|"
        r"confront|step on)\b",
        r"\bavoid(?:ing)? (?:the|a|that|having the|having a) (?:hard |difficult |tough )?"
        r"(?:conversation|confrontation|discussion)\b",
        r"\bkeep the peace\b",
        r"\bnot my place to\b",
    ],
    "perfection": [
        r"\b(?:complete|perfect|full|total) (?:data|information|certainty|picture)\b",
        r"\bwait until\b[^.]{0,40}\b(?:sure|certain|all the data|everything|perfect)\b",
        r"\b(?:can'?t|cannot|won'?t) (?:act|move|do anything|decide) until\b",
        r"\bbefore (?:we|i) (?:do|change|try) anything\b",
    ],
    "approval": [
        r"\b(?:got|received|secured|won|had|have) (?:the |their |final |exec(?:utive)? )?"
        r"(?:approval|sign-?off|green light|budget approved)\b[^.]{0,60}\b(?:so|which means|"
        r"success|succeeded|worked|done|win)\b",
        r"\b(?:approved|signed off)(?: it)?,? so (?:it|we|the|that)\b",
        r"\b(?:was|is) (?:a )?success(?:ful)? because\b[^.]{0,60}\bapprov",
    ],
}
PUSHBACK_RE = {k: [re.compile(p, re.I) for p in v] for k, v in PUSHBACK.items()}

OVERCLAIM = re.compile(
    r"\b(clearly|obviously|undoubtedly|without (?:a )?doubt|definitely|certainly|"
    r"the (?:real|root|true|actual) (?:cause|problem|issue) is|we know (?:that|why)|"
    r"it is (?:clear|certain) that|proves?|proven)\b", re.I)
INTENT_MARK = re.compile(r"\b(will|plan to|planning to|going to|intend|hope to|want to|aim to|"
                         r"would like to|i'?d like to)\b", re.I)
OPINION_MARK = re.compile(r"\b(i think|i believe|i feel|i suspect|i guess|i'?m sure|i am sure|"
                          r"probably|it seems|seems like|my sense|my gut)\b", re.I)
APPROVAL_MARK = re.compile(r"\b(approv\w*|sign(?:ed)?[- ]?off|green[- ]light|agreed|agrees|"
                           r"budget (?:was )?(?:granted|released|approved))\b", re.I)
CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|(?<!\d)(?:\+?\d[\d ().-]{8,}\d)(?!\d)")


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ text helpers

def norm(s):
    """Lowercase, straight quotes, plain dashes, no markdown emphasis, one space."""
    s = unicodedata.normalize("NFKC", s or "")
    s = (s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
         .replace("–", "-").replace("—", "-").replace("…", "..."))
    s = re.sub(r"(?m)^\s*>\s?", " ", s)
    s = re.sub(r"[*_`]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def name_key(s):
    return re.sub(r"[^a-z0-9]+", " ", norm(s)).strip()


def words(s):
    return len(re.findall(r"[A-Za-z0-9$%][\w'$%.,-]*", s or ""))


def quote_found(quote, haystack):
    """The quote, or each part of it split on an ellipsis, appears in order."""
    parts = [p.strip(" .,;:-\"'") for p in re.split(r"\.\.\.|\[\.\.\.\]", norm(quote))]
    parts = [p for p in parts if p]
    if not parts:
        return False
    at = 0
    for p in parts:
        i = haystack.find(p, at)
        if i < 0:
            return False
        at = i + len(p)
    return True


def mentions(text, who):
    """Does `text` name the stakeholder `who`? Singular and plural both count,
    and so does the name without its qualifier ("store managers" for "Store
    managers at the six stores")."""
    t, w = name_key(text), name_key(who)
    if not w:
        return False
    head = re.split(r"\b(?:at|in|of|from|for|on|with|across|who|whose)\b", w)[0].strip()
    stems = set()
    for x in (w, head):
        if x:
            stems.update({x, x[:-1] if x.endswith("s") else x + "s"})
    return any(re.search(r"\b" + re.escape(x) + r"\b", t) for x in stems)


def outside_quotes(s):
    """The quote minus anything it reports in quotation marks: 'the COO said
    "I think we need more applicants"' is a fact about what he said."""
    s = norm(s)
    return re.sub(r'"[^"]*"|\'[^\']{6,}\'', " ", s)


def same_party(a, b):
    a, b = name_key(a), name_key(b)
    if not a or not b:
        return False
    a1 = a[:-1] if a.endswith("s") else a
    b1 = b[:-1] if b.endswith("s") else b
    return a1 == b1 or re.search(r"\b" + re.escape(a1), b) is not None or \
        re.search(r"\b" + re.escape(b1), a) is not None


def pushback_triggers(situation_text):
    t = norm(situation_text)
    found = {}
    for code, pats in PUSHBACK_RE.items():
        for p in pats:
            m = p.search(t)
            if m:
                found[code] = m.group(0)
                break
    return found


def trait_hit(text):
    for p in TRAIT:
        m = p.search(text or "")
        if m:
            return m.group(0)
    return None


def measure_vague(m):
    if re.search(r"\d", m or ""):
        return False
    if VAGUE_HEAD.search(m or ""):
        return True
    return not OBSERVABLE.search(m or "")


# ------------------------------------------------------------------ loading

def read_text(path, what):
    if not path or not os.path.exists(path):
        raise Refusal(f"{what} not found: {path}")
    raw = open(path, "rb").read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal(f"{what} is not UTF-8 text. Save it as UTF-8 (plain text or markdown) and try again.")


def load_json(path, what="the diagnostic"):
    text = read_text(path, what)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise Refusal(f"{what} is not valid JSON ({exc.msg}, line {exc.lineno}).")


def need(obj, key, kind, where):
    if not isinstance(obj, dict) or key not in obj:
        raise Refusal(f"{where} is missing '{key}'.")
    v = obj[key]
    if kind == "str" and not isinstance(v, str):
        raise Refusal(f"{where}.{key} must be text.")
    if kind == "list" and not isinstance(v, list):
        raise Refusal(f"{where}.{key} must be a list.")
    if kind == "dict" and not isinstance(v, dict):
        raise Refusal(f"{where}.{key} must be an object.")
    return v


def opt_str(obj, key):
    v = obj.get(key, "") if isinstance(obj, dict) else ""
    return v if isinstance(v, str) else ""


def str_list(obj, key, where):
    v = obj.get(key, []) if isinstance(obj, dict) else []
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        raise Refusal(f"{where}.{key} must be a list of text.")
    return v


def validate_shape(d):
    if not isinstance(d, dict):
        raise Refusal("the diagnostic must be a JSON object.")
    ctx = need(d, "context", "dict", "diagnostic")
    for k in ("role", "challenge", "decision"):
        need(ctx, k, "str", "context")
    sh = need(ctx, "stakeholders", "list", "context")
    for i, s in enumerate(sh):
        need(s, "who", "str", f"context.stakeholders[{i}]")
        if not isinstance(s.get("heard"), bool):
            raise Refusal(f"context.stakeholders[{i}].heard must be true or false.")
    ev = need(d, "evidence", "list", "diagnostic")
    ids = set()
    for i, e in enumerate(ev):
        eid = need(e, "id", "str", f"evidence[{i}]")
        need(e, "quote", "str", f"evidence[{i}]")
        need(e, "kind", "str", f"evidence[{i}]")
        if eid in ids:
            raise Refusal(f"evidence id '{eid}' is used twice.")
        ids.add(eid)
    un = need(d, "unknowns", "list", "diagnostic")
    for i, u in enumerate(un):
        uid = need(u, "id", "str", f"unknowns[{i}]")
        need(u, "question", "str", f"unknowns[{i}]")
        if uid in ids:
            raise Refusal(f"id '{uid}' is used twice.")
        ids.add(uid)
    fs = need(d, "findings", "list", "diagnostic")
    for i, f in enumerate(fs):
        need(f, "value", "str", f"findings[{i}]")
        need(f, "type", "str", f"findings[{i}]")
        f["evidence"] = str_list(f, "evidence", f"findings[{i}]")
        f["questions"] = str_list(f, "questions", f"findings[{i}]")
    pm = need(d, "priority_move", "dict", "diagnostic")
    need(pm, "action", "str", "priority_move")
    br = need(d, "brief", "dict", "diagnostic")
    br["evidence"] = str_list(br, "evidence", "brief")
    br["tradeoffs"] = str_list(br, "tradeoffs", "brief")
    plan = need(d, "plan", "list", "diagnostic")
    for i, a in enumerate(plan):
        need(a, "action", "str", f"plan[{i}]")
    pb = d.get("pushback") or []
    d["pushback"] = pb
    if not isinstance(pb, list) or not all(isinstance(p, dict) for p in pb):
        raise Refusal("pushback must be a list of objects.")
    rv = d.get("review") or []
    d["review"] = rv
    if not isinstance(rv, list) or not all(isinstance(r, dict) for r in rv):
        raise Refusal("review must be a list of objects.")
    for i, r in enumerate(rv):
        need(r, "measure", "str", f"review[{i}]")
        r["evidence"] = str_list(r, "evidence", f"review[{i}]")


def parse_date(s, where):
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


# ------------------------------------------------------------------ the check

def check(d, situation_text, as_of=None, previous=None):
    validate_shape(d)
    blocking, advice = [], []
    hay = norm(situation_text)
    if not hay:
        raise Refusal("the situation is empty. The diagnostic can only be checked against what was said.")
    if as_of is None:
        as_of = parse_date(opt_str(d, "as_of"), "as_of") or dt.date.today()

    def block(code, msg):
        blocking.append(f"{code}: {msg}")

    def warn(code, msg):
        advice.append(f"{code}: {msg}")

    if CONTACT.search(situation_text):
        warn("CONTACT_DETAILS", "the situation holds an email address or phone number. Roles are enough; "
             "take personal details out before sharing the report.")

    # --- context
    ctx = d["context"]
    for k in ("role", "challenge", "decision"):
        if not ctx[k].strip():
            block("CONTEXT_MISSING", f"context.{k} is empty. Step 01 establishes it before any finding.")
    stakeholders = ctx["stakeholders"]
    if not stakeholders:
        block("NO_STAKEHOLDERS", "no stakeholders named. A leadership approach is always toward someone.")

    # --- evidence
    ev = {}
    for e in d["evidence"]:
        eid, quote, kind = e["id"], e["quote"], e["kind"].strip().lower()
        ev[eid] = dict(e, kind=kind)
        if kind not in KINDS:
            block("EVIDENCE_KIND", f"{eid} is '{e['kind']}'; it must be one of {', '.join(KINDS)}.")
        if words(quote) < MIN_QUOTE_WORDS:
            block("EVIDENCE_TOO_SHORT", f"{eid} quotes fewer than {MIN_QUOTE_WORDS} words; "
                  "a fragment that short can be found anywhere and proves nothing.")
        elif not quote_found(quote, hay):
            block("EVIDENCE_NOT_FOUND", f"{eid} is not in the situation word for word: \"{quote[:80]}\". "
                  "Every finding must trace back to something the person said.")
        bare = outside_quotes(quote)
        if kind in ("fact", "result") and OPINION_MARK.search(bare):
            block("KIND_MISMATCH", f"{eid} is filed as a {kind} but reads as an opinion "
                  f"(\"{OPINION_MARK.search(bare).group(0)}\"). File it as an interpretation.")
        if kind == "result" and INTENT_MARK.search(bare):
            block("KIND_MISMATCH", f"{eid} is filed as an observed result but describes something intended "
                  f"(\"{INTENT_MARK.search(bare).group(0)}\"). File it as an intention.")
        if words(quote) > MAX_QUOTE_WORDS:
            warn("EVIDENCE_LONG", f"{eid} quotes {words(quote)} words. Quote the part that carries the point.")

    unknowns = {u["id"]: u for u in d["unknowns"]}
    for uid, u in unknowns.items():
        if not u["question"].strip():
            block("UNKNOWN_EMPTY", f"{uid} has no question.")
        if not opt_str(u, "ask").strip():
            block("UNKNOWN_NO_SOURCE", f"{uid} does not say who to ask or what to gather.")
    if not any(opt_str(u, "could_change").strip() for u in unknowns.values()):
        block("NO_ASSUMPTIONS", "nothing is named that could change the recommendation. "
              "Step 03 asks what remains uncertain and what would change the view.")

    def refs(ids, where):
        out = []
        for i in ids:
            if i in ev:
                out.append(ev[i])
            else:
                block("BAD_REFERENCE", f"{where} cites '{i}', which is not an evidence id.")
        return out

    # --- findings, value by value
    seen = {}
    vkeys = {name_key(v): v for v in VALUES}
    used = set()
    for n, f in enumerate(d["findings"]):
        where = f"findings[{n}]"
        value = vkeys.get(name_key(f["value"]))
        if not value:
            block("VALUE_UNKNOWN", f"{where} is filed under '{f['value']}', which is not one of the five values. "
                  f"Use the exact names: {'; '.join(VALUES)}.")
            continue
        where = f"{value} ({where})"
        t = f["type"].strip().lower()
        seen.setdefault(value, []).append(t)
        if t not in FINDING_TYPES:
            block("FINDING_TYPE", f"{where} is '{f['type']}'; it must be strength, opportunity or "
                  "not_enough_evidence.")
            continue
        cited = refs(f.get("evidence", []), where)
        used.update(f.get("evidence", []))
        behavior, step = opt_str(f, "behavior"), opt_str(f, "next_step")
        if t in ("strength", "opportunity"):
            if not cited:
                block("FINDING_NO_EVIDENCE", f"{where} is a {t} with no evidence. If the account says nothing, "
                      "it is not_enough_evidence, with the questions to ask.")
            if not behavior.strip():
                block("BEHAVIOR_MISSING", f"{where} does not name the observable behavior it rests on.")
            if not step.strip():
                block("NEXT_STEP_MISSING", f"{where} has no practical next step.")
            if t == "strength" and cited and all(c["kind"] == "intention" for c in cited):
                block("STRENGTH_ON_INTENTION", f"{where} is a strength resting only on intentions. "
                      "What someone plans to do is not yet what they did.")
        else:
            if not f.get("questions"):
                block("NO_QUESTIONS", f"{where} is not_enough_evidence but asks nothing. Say what to ask or gather.")
        for field in (behavior, step):
            hit = trait_hit(field)
            if hit:
                block("TRAIT_JUDGMENT", f"{where} judges the person, not the approach (\"{hit}\"). "
                      "One situation cannot establish anyone's overall effectiveness as a leader.")
    for v in VALUES:
        if v not in seen:
            block("VALUE_MISSING", f"'{v}' is not examined. All five values are part of every diagnostic; "
                  "if the account says nothing about one, mark it not_enough_evidence.")
    rated = [v for v, ts in seen.items() if any(t in ("strength", "opportunity") for t in ts)]
    if seen and not rated:
        warn("THIN", "every value is not_enough_evidence. That is an honest result: lead with the questions "
             "and run the diagnostic again once they are answered.")
    opportunities = {v for v, ts in seen.items() if "opportunity" in ts}

    # --- perspectives
    texts = [u["question"] + " " + opt_str(u, "ask") for u in unknowns.values()]
    texts += [" ".join(f.get("questions", [])) for f in d["findings"]]
    for s in stakeholders:
        if not s["heard"] and not any(mentions(t, s["who"]) for t in texts):
            block("PERSPECTIVE_MISSING", f"{s['who']} has not been heard and no question says how to hear them.")

    # --- pushback the situation calls for
    trig = pushback_triggers(situation_text)
    answered = {opt_str(p, "trigger").strip().lower(): opt_str(p, "response") for p in d.get("pushback", [])}
    for code, said in trig.items():
        if not answered.get(code, "").strip():
            block("PUSHBACK_UNADDRESSED", f"the situation says \"{said}\" ({code}) and the diagnostic does not "
                  "answer it.")
    for code in answered:
        if code not in PUSHBACK:
            block("PUSHBACK_TYPE", f"pushback '{code}' is not one of {', '.join(PUSHBACK)}.")
        elif code not in trig:
            warn("PUSHBACK_UNPROMPTED", f"pushback '{code}' answers something the situation does not say in "
                 "words the check recognises. Fine if it is there in other words.")

    # --- priority move
    pm = d["priority_move"]
    pv = vkeys.get(name_key(opt_str(pm, "value")))
    pu = opt_str(pm, "unknown")
    if not pm["action"].strip():
        block("PRIORITY_MISSING", "the priority move has no action.")
    if not opt_str(pm, "why").strip():
        block("PRIORITY_NO_WHY", "the priority move does not say why this one, of everything found.")
    if pu:
        if pu not in unknowns:
            block("BAD_REFERENCE", f"priority_move cites unknown '{pu}', which does not exist.")
    elif not pv:
        block("PRIORITY_NO_VALUE", "the priority move is not tied to one of the five values (or to an unknown "
              "to resolve first).")
    elif pv not in opportunities:
        block("PRIORITY_NOT_GAP", f"the priority move is under '{pv}', which has no development opportunity. "
              "The move goes where the approach most needs attention.")
    auth = opt_str(pm, "authority").strip().lower()
    if auth not in AUTHORITY:
        block("AUTHORITY_MISSING", "priority_move.authority must be 'mine' or 'needs_commitment'.")
    elif auth == "needs_commitment" and not any(same_party(opt_str(pm, "from"), s["who"]) for s in stakeholders):
        block("COMMITMENT_FROM_UNKNOWN", f"the priority move needs a commitment from '{opt_str(pm, 'from')}', "
              "who is not among the stakeholders.")
    for field in (pm["action"], opt_str(pm, "why")):
        hit = trait_hit(field)
        if hit:
            block("TRAIT_JUDGMENT", f"the priority move judges the person (\"{hit}\").")

    # --- executive brief
    br = d["brief"]
    for k, label in (("issue", "the business issue"), ("point_of_view", "your point of view"),
                     ("decision", "the decision needed"), ("ask", "the ask"),
                     ("business_impact", "the business impact"), ("people_impact", "the people impact")):
        if not opt_str(br, k).strip():
            block("BRIEF_INCOMPLETE", f"the brief has no {label}.")
    if not [t for t in br.get("tradeoffs", []) if t.strip()]:
        block("NO_TRADEOFFS", "the brief names no trade-off. An executive will; better that you do first.")
    decider, by_when = opt_str(br, "decider").strip(), opt_str(br, "by_when").strip()
    if not decider:
        block("NO_DECIDER", "the brief does not say who decides.")
    elif decider.lower() in UNKNOWN_WORDS:
        warn("DECIDER_UNKNOWN", "who decides is not known. Find out before the meeting, not in it.")
    if not by_when:
        block("NO_DEADLINE", "the brief does not say by when.")
    cited = refs(br.get("evidence", []), "brief")
    used.update(br.get("evidence", []))
    if opt_str(br, "point_of_view").strip() and not any(c["kind"] in ("fact", "result") for c in cited):
        block("POV_UNSUPPORTED", "the point of view cites no fact or observed result. An executive brief "
              "built on interpretation alone is an opinion.")
    over = OVERCLAIM.search(opt_str(br, "point_of_view") + " " + opt_str(br, "ask"))
    if over:
        if not any(c["kind"] in ("fact", "result") for c in cited):
            block("OVERCLAIM", f"the brief says \"{over.group(0)}\" with nothing factual under it.")
        else:
            warn("CERTAINTY", f"the brief says \"{over.group(0)}\". Check the facts carry that much certainty.")
    aw = words(opt_str(br, "ask"))
    if aw > ASK_MAX_WORDS:
        block("ASK_TOO_LONG", f"the ask is {aw} words. Keep it under {ASK_MAX_WORDS}, about thirty seconds "
              "said aloud.")
    elif aw > ASK_WARN_WORDS:
        warn("ASK_LONG", f"the ask is {aw} words. Shorter lands better.")

    # --- action plan
    plan = d["plan"]
    if not plan:
        block("PLAN_EMPTY", "there is no action plan.")
    if len(plan) > PLAN_MAX:
        warn("PLAN_LONG", f"{len(plan)} actions. More than {PLAN_MAX} rarely all happen; keep the ones that matter.")
    needing = 0
    for n, a in enumerate(plan):
        where = f"plan[{n}] ({a['action'][:40]})"
        if not a["action"].strip():
            block("ACTION_EMPTY", f"plan[{n}] has no action.")
        owner = opt_str(a, "owner").strip()
        if not owner or name_key(owner) in VAGUE_OWNERS:
            block("OWNER_VAGUE", f"{where} is owned by '{owner}'. Name one person or role.")
        m = opt_str(a, "measure")
        if not m.strip():
            block("NO_MEASURE", f"{where} has no success measure.")
        elif measure_vague(m):
            block("MEASURE_VAGUE", f"{where} is measured by \"{m}\", which nobody could observe or count.")
        rd = parse_date(opt_str(a, "review"), where)
        if rd is None:
            block("REVIEW_DATE", f"{where} has no review date as YYYY-MM-DD.")
        elif rd <= as_of:
            block("REVIEW_DATE", f"{where} is reviewed on {rd}, not after {as_of}.")
        elif (rd - as_of).days > REVIEW_MAX_DAYS:
            block("REVIEW_DATE", f"{where} is reviewed {(rd - as_of).days} days out. Look again within "
                  f"{REVIEW_MAX_DAYS} days.")
        elif (rd - as_of).days > REVIEW_WARN_DAYS:
            warn("REVIEW_LATE", f"{where} is reviewed {(rd - as_of).days} days out.")
        au = opt_str(a, "authority").strip().lower()
        if au not in AUTHORITY:
            block("AUTHORITY_MISSING", f"{where}: authority must be 'mine' or 'needs_commitment'.")
        elif au == "needs_commitment":
            needing += 1
            if not any(same_party(opt_str(a, "from"), s["who"]) for s in stakeholders):
                block("COMMITMENT_FROM_UNKNOWN", f"{where} needs a commitment from '{opt_str(a, 'from')}', "
                      "who is not among the stakeholders.")
    if plan and needing * 2 > len(plan):
        warn("DEPENDS_ON_OTHERS", f"{needing} of {len(plan)} actions need someone else's commitment. "
             "Make sure at least the first step is yours.")

    # --- revisit
    review = d.get("review", [])
    if previous is not None:
        prior = [opt_str(a, "measure") for a in previous.get("plan", []) if isinstance(a, dict)]
        got = {name_key(r["measure"]) for r in review}
        for m in prior:
            if m.strip() and name_key(m) not in got:
                block("REVIEW_MISSING", f"the earlier measure \"{m}\" has no result. Every one gets one, "
                      "including the ones that did not happen.")
    for n, r in enumerate(review):
        where = f"review[{n}] ({r['measure'][:40]})"
        res = opt_str(r, "result").strip().lower()
        if res not in RESULTS:
            block("RESULT_TYPE", f"{where}: result must be one of {', '.join(RESULTS)}.")
            continue
        cited = refs(r.get("evidence", []), where)
        used.update(r.get("evidence", []))
        if res != "not_observed" and not any(c["kind"] == "result" for c in cited):
            block("RESULT_NOT_OBSERVED", f"{where} is marked {res} without an observed result behind it.")
        if res in ("met", "partly") and cited and all(APPROVAL_MARK.search(c["quote"]) for c in cited) \
                and not APPROVAL_MARK.search(r["measure"]):
            block("APPROVAL_AS_RESULT", f"{where} counts approval as the result. Executive agreement is not "
                  "implementation, and implementation is not results.")
        if res != "met" and not opt_str(r, "adjust").strip():
            block("ADJUST_MISSING", f"{where} is {res} and says nothing about what to adjust.")

    unused = [e for e in ev if e not in used]
    if unused:
        warn("EVIDENCE_UNUSED", f"{len(unused)} evidence item(s) not cited anywhere: {', '.join(unused)}.")

    return {"ready": not blocking, "blocking": blocking, "advice": advice, "as_of": str(as_of),
            "values": {v: seen.get(v, []) for v in VALUES}, "pushback_triggers": trig}


# ------------------------------------------------------------------ output

READING = {"strength": "Strength", "opportunity": "Development opportunity",
           "not_enough_evidence": "Not enough evidence yet"}
KIND_LABEL = {"fact": "Facts", "result": "Observed results", "interpretation": "Interpretations",
              "intention": "Intentions"}


def text_check(res):
    out = []
    for v in VALUES:
        ts = res["values"][v]
        out.append(f"  {v:<44} {', '.join(READING.get(t, t) for t in ts) or 'not examined'}")
    if res["pushback_triggers"]:
        out.append("  Pushback the situation calls for: " + ", ".join(res["pushback_triggers"]))
    for b in res["blocking"]:
        out.append("BLOCKING " + b)
    for a in res["advice"]:
        out.append("advice   " + a)
    out.append("READY to share." if res["ready"] else f"NOT READY: {len(res['blocking'])} blocking item(s).")
    return "\n".join(out)


def _ev(d):
    return {e["id"]: e for e in d["evidence"]}


def render_md(d):
    ev = _ev(d)
    ctx, br, pm = d["context"], d["brief"], d["priority_move"]
    q = lambda ids: "; ".join(f"\"{ev[i]['quote']}\"" for i in ids if i in ev)
    L = [f"# Strategic leadership diagnostic", "",
         f"*{ctx['challenge']}*", "",
         f"Your role: {ctx['role']}  ", f"The decision ahead: {ctx['decision']}", ""]
    L += ["## 1. Strategic leadership profile", ""]
    order = [name_key(v) for v in VALUES]
    groups = (("strength", "Strengths"), ("opportunity", "Development opportunities"),
              ("not_enough_evidence", "Not enough evidence yet"))
    for t, title in groups:
        fs = [f for f in d["findings"] if f["type"].strip().lower() == t and name_key(f["value"]) in order]
        fs.sort(key=lambda f: order.index(name_key(f["value"])))
        if not fs:
            continue
        L += [f"### {title}", ""]
        for f in fs:
            v = VALUES[order.index(name_key(f["value"]))]
            if t == "not_enough_evidence":
                L += [f"**{v}.** Your account says nothing on this yet. To ask: " + " ".join(f.get("questions", [])), ""]
            else:
                L += [f"**{v}.** {f.get('behavior', '')}", "",
                      f"*Rests on:* {q(f.get('evidence', []))}", "",
                      f"*Next step:* {f.get('next_step', '')}", ""]
    L += ["## 2. Evidence and assumptions", ""]
    for k in KINDS:
        items = [e for e in d["evidence"] if e["kind"].strip().lower() == k]
        if items:
            L.append(f"**{KIND_LABEL[k]}**")
            L += [f"- \"{e['quote']}\"" for e in items]
            L.append("")
    if d["unknowns"]:
        L.append("**Still open, and what could change the recommendation**")
        for u in d["unknowns"]:
            extra = f" Could change: {u['could_change']}" if opt_str(u, "could_change") else ""
            L.append(f"- {u['question']} *Ask: {opt_str(u, 'ask')}.*{extra}")
        L.append("")
    if d.get("pushback"):
        L += ["**What I would challenge**"]
        L += [f"- {p.get('response', '')}" for p in d["pushback"]]
        L.append("")
    L += ["## 3. Priority leadership move", "",
          f"**{pm['action']}**", "", opt_str(pm, "why"), ""]
    L += ["## 4. Executive discussion brief", "",
          f"**The issue.** {opt_str(br, 'issue')}", "",
          f"**My point of view.** {opt_str(br, 'point_of_view')}", "",
          f"**What it means for the business.** {opt_str(br, 'business_impact')}", "",
          f"**What it means for people.** {opt_str(br, 'people_impact')}", "",
          "**Trade-offs.**"]
    L += [f"- {t}" for t in br.get("tradeoffs", [])]
    L += ["", f"**The decision.** {opt_str(br, 'decision')} Decided by {opt_str(br, 'decider')}, "
          f"by {opt_str(br, 'by_when')}.", "", f"**The ask.** \"{opt_str(br, 'ask')}\"", ""]
    L += ["## 5. Action plan", "", "| Action | Owner | You will see | Review |", "|---|---|---|---|"]
    for a in d["plan"]:
        own = opt_str(a, "owner") + (f", once {opt_str(a, 'from')} agrees"
                                     if opt_str(a, "authority").lower() == "needs_commitment" else "")
        L.append(f"| {a['action']} | {own} | {opt_str(a, 'measure')} | {opt_str(a, 'review')} |")
    if d.get("review"):
        L += ["", "## Since last time", "", "| Measure | Result | What to adjust |", "|---|---|---|"]
        for r in d["review"]:
            L.append(f"| {r['measure']} | {opt_str(r, 'result').replace('_', ' ')} | {opt_str(r, 'adjust')} |")
    L += ["", "*Built on the five values from Joey V. Price's The Power of HR. This reads one situation, "
          "as you described it; it is not a judgment of you as a leader.*", ""]
    return "\n".join(L)


def render_html(d, path):
    md = render_md(d)
    body, in_table, in_list = [], False, False
    inline = lambda s: re.sub(r"\*([^*]+)\*", r"<em>\1</em>",
                              re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", html.escape(s, quote=False)))
    for line in md.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-") for c in cells):
                continue
            if not in_table:
                body.append("<table><tr>" + "".join(f"<th>{inline(c)}</th>" for c in cells) + "</tr>")
                in_table = True
            else:
                body.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table:
            body.append("</table>")
            in_table = False
        if line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{inline(line[2:])}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False
        if line.startswith("### "):
            body.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            body.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{inline(line[2:])}</h1>")
        elif line.strip():
            body.append(f"<p>{inline(line.rstrip(' '))}</p>")
    if in_table:
        body.append("</table>")
    if in_list:
        body.append("</ul>")
    css = ("body{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:32px auto;padding:0 16px;color:#1b1b2f}"
           "h1{font-size:26px}h3{font-size:16px;margin:18px 0 4px;color:#4b3fd6}h2{font-size:19px;margin-top:28px;border-bottom:2px solid #4b3fd6;padding-bottom:4px}"
           "table{border-collapse:collapse;width:100%;margin:8px 0}th,td{border:1px solid #ddd;padding:6px 8px;"
           "vertical-align:top;text-align:left}th{background:#f3f2fd}@media print{body{margin:0}}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' "
                 f"content='width=device-width,initial-scale=1'><title>Strategic leadership diagnostic</title>"
                 f"<style>{css}</style></head><body>{''.join(body)}</body></html>")


# ------------------------------------------------------------------ tests

def run_tests():
    import tempfile
    passed = failed = 0

    def ok(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print("FAIL " + name + (f"\n   {detail}" if detail else ""))

    sit = read_text(os.path.join(SAMPLE, "halden_situation.md"), "sample situation")
    base = load_json(os.path.join(SAMPLE, "halden_diagnostic.json"))
    r = check(copy.deepcopy(base), sit)
    ok("sample diagnostic is ready", r["ready"], r["blocking"])
    ok("sample: all five values examined", all(r["values"][v] for v in VALUES))
    ok("sample: certainty pushback found in the situation", "certainty" in r["pushback_triggers"])
    ok("sample: no other pushback found", set(r["pushback_triggers"]) == {"certainty"}, r["pushback_triggers"])
    ok("sample: ask under the limit", words(base["brief"]["ask"]) <= ASK_MAX_WORDS)

    # the revisit sample: a return visit with results
    sit2 = read_text(os.path.join(SAMPLE, "halden_followup_situation.md"), "follow-up situation")
    fol = load_json(os.path.join(SAMPLE, "halden_followup_diagnostic.json"))
    r2 = check(copy.deepcopy(fol), sit2, previous=base)
    ok("follow-up diagnostic is ready", r2["ready"], r2["blocking"])

    # broken copies: each must fail for its named reason, and only become not ready
    cases = json.load(open(os.path.join(FIXTURES, "broken_diagnostics.json"), encoding="utf-8"))["cases"]
    for case in cases:
        src = fol if case.get("base") == "followup" else base
        d = copy.deepcopy(src)
        for op in case["ops"]:
            tgt = d
            for k in op["path"][:-1]:
                tgt = tgt[k]
            last = op["path"][-1]
            if op["op"] == "set":
                tgt[last] = op["value"]
            elif op["op"] == "del":
                del tgt[last]
            elif op["op"] == "append":
                tgt[last].append(op["value"])
        s = sit2 if case.get("base") == "followup" else sit
        s = s + case.get("situation_append", "")
        prev = base if case.get("base") == "followup" else None
        try:
            got = check(d, s, previous=prev)
            if case["expect"] == "REFUSED":
                ok(f"refused: {case['name']}", False, "was checked instead of refused")
                continue
            if case["expect"] == "READY":
                ok(f"passes: {case['name']}", got["ready"], got["blocking"])
                continue
            hit = any(b.startswith(case["expect"] + ":") for b in got["blocking"])
            ok(f"caught: {case['name']}", (not got["ready"]) and hit, got["blocking"])
        except Refusal as exc:
            ok(f"{'refused' if case['expect'] == 'REFUSED' else 'caught'}: {case['name']}",
               case["expect"] == "REFUSED", f"refused: {exc}")

    # phrase detectors: must and must-not
    ph = json.load(open(os.path.join(FIXTURES, "phrases.json"), encoding="utf-8"))
    for code, sets in ph["pushback"].items():
        for s in sets["must"]:
            ok(f"pushback {code} found: {s}", code in pushback_triggers(s), pushback_triggers(s))
        for s in sets["must_not"]:
            ok(f"pushback {code} not found: {s}", code not in pushback_triggers(s), pushback_triggers(s))
    for s in ph["trait"]["must"]:
        ok(f"trait judgment found: {s}", trait_hit(s) is not None)
    for s in ph["trait"]["must_not"]:
        ok(f"no trait judgment: {s}", trait_hit(s) is None, trait_hit(s))
    for s in ph["measure"]["vague"]:
        ok(f"vague measure: {s}", measure_vague(s))
    for s in ph["measure"]["observable"]:
        ok(f"observable measure: {s}", not measure_vague(s))

    # quotes: normalisation and ellipses
    hay = norm("He said “we’ll see” — and *nothing* happened after the   memo.")
    ok("quote: curly quotes and emphasis normalised", quote_found("we'll see\" - and nothing happened", hay))
    ok("quote: ellipsis joins parts in order", quote_found("we'll see ... after the memo", hay))
    ok("quote: ellipsis parts out of order fail", not quote_found("after the memo ... we'll see", hay))
    ok("quote: paraphrase fails", not quote_found("nothing happened after the email", hay))

    # files: refusals, not crashes
    with tempfile.TemporaryDirectory() as tmp:
        bad = os.path.join(tmp, "bad.md")
        open(bad, "wb").write("caf\xe9 au lait".encode("latin-1"))
        try:
            read_text(bad, "situation")
            ok("non-UTF-8 situation refused", False)
        except Refusal:
            ok("non-UTF-8 situation refused", True)
        bom = os.path.join(tmp, "bom.md")
        open(bom, "wb").write(b"\xef\xbb\xbf" + sit.encode("utf-8"))
        ok("BOM situation read", read_text(bom, "situation") == sit)
        j = os.path.join(tmp, "x.json")
        open(j, "w").write("{not json")
        try:
            load_json(j)
            ok("broken JSON refused", False)
        except Refusal:
            ok("broken JSON refused", True)
        try:
            check(copy.deepcopy(base), "   ")
            ok("empty situation refused", False)
        except Refusal:
            ok("empty situation refused", True)
        out_md, out_html = os.path.join(tmp, "r.md"), os.path.join(tmp, "r.html")
        open(out_md, "w", encoding="utf-8").write(render_md(base))
        render_html(base, out_html)
        md = open(out_md, encoding="utf-8").read()
        ok("render: five parts present", all(h in md for h in (
            "## 1. Strategic leadership profile", "## 2. Evidence and assumptions", "## 3. Priority leadership move",
            "## 4. Executive discussion brief", "## 5. Action plan")))
        ok("render: every value appears", all(v in md for v in VALUES))
        ok("render: html written", "<table>" in open(out_html, encoding="utf-8").read())
        ok("render: follow-up shows results", "## Since last time" in render_md(fol))

    # a random walk of broken diagnostics: refused or checked, never a crash
    import random
    rng = random.Random(7)
    crashes = 0
    leaves = []

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, path + [k])
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, path + [i])
        leaves.append(path)
    walk(base, [])
    junk = [None, 0, -1, "", " ", [], {}, "x" * 500, ["E99"], {"a": 1}, True, "2026-02-30", chr(0x200B), 3.5]
    for _ in range(1500):
        d = copy.deepcopy(base)
        for _ in range(rng.randint(1, 4)):
            p = rng.choice(leaves)
            if not p:
                continue
            tgt = d
            try:
                for k in p[:-1]:
                    tgt = tgt[k]
                if rng.random() < 0.3 and isinstance(tgt, dict):
                    del tgt[p[-1]]
                else:
                    tgt[p[-1]] = copy.deepcopy(rng.choice(junk))
            except (KeyError, IndexError, TypeError):
                pass
        try:
            check(d, sit)
            render_md(d) if check(d, sit)["ready"] else None
        except Refusal:
            pass
        except Exception as exc:
            crashes += 1
            if crashes <= 3:
                print(f"   crash: {type(exc).__name__}: {exc}")
    ok("1,500 randomly broken diagnostics: no crash", crashes == 0, f"{crashes} crashes")

    print(f"{passed} passed, {failed} failed")
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
            sit = read_text(os.path.join(SAMPLE, "halden_situation.md"), "sample situation")
            d = load_json(os.path.join(SAMPLE, "halden_diagnostic.json"))
            print("From the skill's demo: Halden Market (fictional), the sample situation and its diagnostic.\n")
            print(text_check(check(d, sit)))
            print()
            print(render_md(d))
            return 0
        if opt("--check"):
            d = load_json(opt("--check"))
            sit = read_text(opt("--situation"), "the situation") if opt("--situation") else None
            if sit is None:
                raise Refusal("--situation is required: the evidence is checked against it.")
            as_of = opt("--as-of")
            if as_of:
                as_of = parse_date(as_of, "--as-of")
                if as_of is None:
                    raise Refusal("--as-of must be YYYY-MM-DD.")
            prev = load_json(opt("--previous"), "the earlier diagnostic") if opt("--previous") else None
            if prev is not None and not isinstance(prev, dict):
                raise Refusal("the earlier diagnostic must be a JSON object.")
            res = check(d, sit, as_of, prev)
            print(text_check(res))
            if opt("--json"):
                with open(opt("--json"), "w", encoding="utf-8") as fh:
                    json.dump(res, fh, indent=1)
            for flag, fn in (("--md", None), ("--html", render_html)):
                if opt(flag):
                    if not res["ready"]:
                        print(f"No report written to {opt(flag)}: fix the blocking items first.")
                    elif fn:
                        fn(d, opt(flag))
                    else:
                        with open(opt(flag), "w", encoding="utf-8") as fh:
                            fh.write(render_md(d))
            return 0 if res["ready"] else 1
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the checker failed ({type(exc).__name__}: {exc}). This is a bug in the checker, "
              "not a finding about your diagnostic.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
