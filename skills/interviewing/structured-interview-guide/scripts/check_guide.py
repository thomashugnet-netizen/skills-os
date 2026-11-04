#!/usr/bin/env python3
"""
Checks interview questions and structured interview guides, and renders a
guide as a one-page sheet a manager can print.

    python3 check_guide.py --questions questions.txt [--html report.html]
    python3 check_guide.py --guide guide.json [--html guide.html]
    python3 check_guide.py --test

questions.txt  one question per line, as managers ask them today.
guide.json     the guide, in the shape of references/sample/overnight_stocker_guide.json.

Exit codes, so the check can gate printing:
    0  guide ready to print, or no question in the list is a legal risk
       (questions that need care are printed but do not change the code)
    1  guide not ready, or a question is a legal risk or could not be checked
    2  no mode given
    3  input refused: unreadable file or a guide in the wrong shape
    4  the checker itself failed

The rules match phrasings, in English. No match is not a clearance.
Standard library only.
"""

import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")

REQUIRED_PURPOSES = {"reliability", "preview", "availability"}
PURPOSES = REQUIRED_PURPOSES | {"role_behaviour", "their_questions"}
VAGUE = ["seems", "attitude", "vibe", "fit", "energy", "passion", "personality", "lazy", "motivated",
         "gut", "feel", "likeable", "nice", "professional", "presentable"]
MAX_GRADE = 8.0


class Refusal(Exception):
    """Input the checker will not read. The message says what to fix."""


def load_rules():
    data = json.load(open(os.path.join(REF, "question_rules.json"), encoding="utf-8"))
    for r in data["rules"]:
        r["_re"] = [re.compile(p, re.I) for p in r["patterns"]]
        r["_personal"] = [re.compile(p, re.I) for p in r.get("personal", [])]
    for w in data["weak"]:
        w["_re"] = re.compile(w["pattern"], re.I)
    data["_third"] = re.compile(data["third_party"], re.I)
    return data


# ------------------------------------------------------------------ questions

ENGLISH = set("""the a an you your to of and in is are do did does how what when where why who which can
could would will have has had for with on at it this that me i we our us about there be been was were
tell time job work shift if any or not no yes they he she them their his her one so as by from all out
without but some more most nor up down off over under then than just only very also every each other such
own same too can't don't didn't won't ever never again here now still yet after before while because until
into through between against during has having being its it's i'm you're they're there's let""".split())
NOT_ENGLISH_CHARS = re.compile(r"[¿¡ñçãõàèìòùâêîôûäöüßœ]|[^\x00-ɏ‘-”…–— -ÿ]")


def _clean(q):
    q = q.strip()
    q = re.sub(r"^\s*(\d+[.)]|[-*•])\s*", "", q)        # list numbering and bullets
    return q.strip()


def normalise(text):
    """Lower case, straight quotes, and the spellings people type: 'r u', 'd0', 'h0w'."""
    low = text.lower().replace("’", "'").replace("‘", "'").replace("`", "'")
    low = re.sub(r"(?<![\d])0(?![\d])", "o", low)        # a zero standing in for an o, not in 10pm or 40
    low = re.sub(r"(?<=[a-z])@|@(?=[a-z])", "a", low)
    low = re.sub(r"\bu\b", "you", low)
    low = re.sub(r"\bur\b", "your", low)
    low = re.sub(r"\br\b", "are", low)
    low = re.sub(r"\bya\b", "you", low)
    low = re.sub(r"\s+", " ", low)
    return low.strip()


def looks_english(text):
    """False for text the English rules cannot read. Rough: a run of words with no
    English function word in it, or letters from outside English."""
    words = re.findall(r"[^\W\d_]+", text.lower())
    if len(NOT_ENGLISH_CHARS.findall(text)) >= 2:
        return False
    if len(words) >= 5 and not (set(words) & ENGLISH):
        return False
    return True


def check_question(text, rules):
    """{text, level, risks[], weak[]} where level is blocking, caution, weak, unchecked or ok.
    'ok' means no rule matched, not that the question is cleared."""
    q = _clean(text)
    if not looks_english(q):
        return {"text": q, "level": "unchecked", "risks": [], "weak": []}
    low = normalise(q)
    third = bool(rules["_third"].search(low))
    risks = []
    for r in rules["rules"]:
        hit = any(rx.search(low) for rx in r["_re"]) or (
            not third and any(rx.search(low) for rx in r["_personal"]))
        if hit:
            risks.append({"id": r["id"], "level": r["level"], "topic": r["topic"], "why": r["why"],
                          "instead": r["instead"], "source": r["source"]})
    weak = [{"id": w["id"], "advice": w["advice"]} for w in rules["weak"] if w["_re"].search(low)]
    if any(r["level"] == "blocking" for r in risks):
        level = "blocking"
    elif risks:
        level = "caution"
    elif weak:
        level = "weak"
    else:
        level = "ok"
    return {"text": q, "level": level, "risks": risks, "weak": weak}


def read_text(path):
    """Reads a text file in UTF-8 or UTF-16 (what Word and Excel save as 'Unicode text')."""
    if not os.path.exists(path):
        raise Refusal(f"no file at {path}.")
    raw = open(path, "rb").read()
    try:
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return raw.decode("utf-16")
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise Refusal("the file is not readable text. Save it as UTF-8 text and try again.")


def check_questions(path, rules=None):
    rules = rules or load_rules()
    lines = [l for l in read_text(path).splitlines() if _clean(l)]
    if not lines:
        raise Refusal("the questions file is empty.")
    results = [check_question(l, rules) for l in lines]
    count = lambda lv: sum(1 for r in results if r["level"] == lv)
    return {"questions": results, "total": len(results), "blocking": count("blocking"),
            "caution": count("caution"), "weak": count("weak"), "unchecked": count("unchecked"),
            "ok": count("ok")}


# ---------------------------------------------------------------------- guide

def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n)


def reading_grade(text):
    """Flesch-Kincaid grade. Rough, and good enough to catch a question written
    for a board paper rather than for a candidate between shifts. Below five
    words the formula means nothing, so it returns 0; length is checked apart."""
    words = re.findall(r"[A-Za-z']+", text)
    if len(words) < 5:
        return 0.0
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    syl = sum(syllables(w) for w in words)
    return round(0.39 * len(words) / sentences + 11.8 * syl / len(words) - 15.59, 1)


def _shape(guide):
    """Refuses a guide the checker cannot read, naming the field, instead of crashing
    or quietly treating a string as a list of letters."""
    def bad(where, what):
        raise Refusal(f"the guide is not in the expected shape: {where} {what}. "
                      "Compare with references/sample/overnight_stocker_guide.json.")

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")

    if not isinstance(guide, dict):
        bad("the guide", "must be a JSON object, with role, minutes, questions and so on")
    for f in ("role", "opening", "closing", "interviewer", "format", "employer"):
        if f in guide and guide[f] is not None and not isinstance(guide[f], str):
            bad(f"'{f}'", "must be text")
    if "minutes" in guide and guide["minutes"] is not None:
        m = guide["minutes"]
        if isinstance(m, str) and re.fullmatch(r"\s*\d+(\.\d+)?\s*", m):
            guide["minutes"] = float(m) if "." in m else int(m)
        elif not is_num(m):
            bad("'minutes'", "must be a number, such as 15")
    if "questions" in guide and guide["questions"] is not None:
        qs = guide["questions"]
        if not isinstance(qs, list):
            bad("'questions'", "must be a list of questions")
        for i, q in enumerate(qs):
            where = f"question {i + 1}"
            if not isinstance(q, dict):
                bad(where, "must be an object with id, purpose, text, minutes, anchors and probes")
            for f in ("id", "purpose", "text"):
                if f in q and q[f] is not None and not isinstance(q[f], str):
                    bad(f"{where} '{f}'", "must be text")
            if "minutes" in q and q["minutes"] is not None:
                m = q["minutes"]
                if isinstance(m, str) and re.fullmatch(r"\s*\d+(\.\d+)?\s*", m):
                    q["minutes"] = float(m)
                elif not is_num(m):
                    bad(f"{where} 'minutes'", "must be a number, such as 2")
            if q.get("anchors") is not None:
                if not isinstance(q["anchors"], dict):
                    bad(f"{where} 'anchors'", 'must map "1", "2" and "3" to a description')
                q["anchors"] = {str(k): v for k, v in q["anchors"].items()}
                for k, v in q["anchors"].items():
                    if not isinstance(v, str):
                        bad(f"{where} anchor {k}", "must be text")
            if "probes" in q:
                if q["probes"] is None:
                    q["probes"] = []
                if not isinstance(q["probes"], list) or not all(isinstance(p, str) for p in q["probes"]):
                    bad(f"{where} 'probes'", "must be a list of follow-up questions, even when there is one")
    if "decision" in guide and guide["decision"] is not None:
        d = guide["decision"]
        if not isinstance(d, dict):
            bad("'decision'", "must be an object with advance_at, reject_below and middle")
        if d.get("middle") is not None and not isinstance(d["middle"], str):
            bad("decision 'middle'", "must be text")
    for kind in ("red_flags", "green_flags"):
        if kind in guide:
            if guide[kind] is None:
                guide[kind] = []
            if not isinstance(guide[kind], list) or not all(isinstance(f, str) for f in guide[kind]):
                bad(f"'{kind}'", "must be a list of sentences, even when there is one")
    if "do_not_ask" in guide:
        if guide["do_not_ask"] is None:
            guide["do_not_ask"] = []
        if not isinstance(guide["do_not_ask"], list):
            bad("'do_not_ask'", "must be a list of {question, instead} pairs")
        for i, item in enumerate(guide["do_not_ask"]):
            if not (isinstance(item, dict) and isinstance(item.get("question"), str)
                    and isinstance(item.get("instead"), str)):
                bad(f"do_not_ask item {i + 1}", "needs both a 'question' and an 'instead', as text")


def _whole(v):
    """An int from 12 or "12"; None for 12.9, "12.9", True or anything else."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    if isinstance(v, str) and re.fullmatch(r"\s*\d+\s*", v):
        return int(v)
    return None


def _same(text):
    return " ".join(re.findall(r"[a-z0-9']+", text.lower()))


def check_guide(guide, rules=None):
    rules = rules or load_rules()
    _shape(guide)
    block, warn = [], []

    def need(cond, msg, blocking=True):
        if not cond:
            (block if blocking else warn).append(msg)

    def filled(v):
        return v is not None and not (isinstance(v, str) and not v.strip()) and v != []

    for field in ("role", "minutes", "opening", "closing", "questions", "decision"):
        need(field in guide and filled(guide[field]), f"missing '{field}'")
    if block:
        return {"ready": False, "blocking": block, "warnings": warn, "questions": []}

    def risk_text(where, text, blocking_only=False):
        """Every piece of text on the sheet goes through the rules: anchors and flags
        decide the hire as much as the questions do."""
        c = check_question(text, rules)
        if c["level"] == "unchecked":
            need(False, f"{where} is not in English; the rules are written for English, so it was not checked. "
                        "Have someone check it by hand, or write the guide in English first")
            return c
        for r in c["risks"]:
            if r["level"] == "blocking":
                need(False, f"{where}: mentions {r['topic'].lower()}. {r['why']}")
            elif not blocking_only:
                warn.append(f"{where}: touches {r['topic'].lower()}. {r['why']}")
        return c

    qs = guide["questions"]
    scored = [q for q in qs if q.get("purpose") != "their_questions"]
    need(4 <= len(qs) <= 6, f"{len(qs)} questions: a fifteen-minute interview holds four to six")
    need(3 <= len(scored) <= 5, f"{len(scored)} scored questions: three to five, plus their questions")

    ids = [q.get("id") for q in qs]
    for n, q in enumerate(qs, start=1):
        if not (isinstance(q.get("id"), str) and q["id"].strip()):
            q["id"] = f"question {n}"
            need(False, f"question {n}: give it an id, such as q{n}")
    dup = sorted({i for i in ids if i and ids.count(i) > 1})
    need(not dup, f"two questions share the id {', '.join(dup)}")
    texts = [_same(q.get("text") or "") for q in qs if (q.get("text") or "").strip()]
    need(len(texts) == len(set(texts)), "the same question appears twice")

    purposes = {q.get("purpose") for q in qs}
    for p in sorted(REQUIRED_PURPOSES - purposes):
        need(False, f"no '{p}' question: reliability, a tested realistic preview and availability "
                    "confirmed out loud are the three that predict whether an hourly hire stays")
    for q in qs:
        need(q.get("purpose") in PURPOSES, f"{q['id']}: purpose '{q.get('purpose')}' is not one of "
                                           + ", ".join(sorted(PURPOSES)))

    planned = guide["minutes"]
    need(5 <= planned <= 30, f"the interview is planned at {planned:g} minutes; this guide is for "
                             "interviews of 5 to 30 minutes")
    minutes = sum(float(q.get("minutes") or 0) for q in qs)
    need(minutes + 2 <= planned,
         f"questions take {minutes:g} minutes plus about 2 to open and close, over the {planned:g} planned")
    for q in qs:
        need(0 < float(q.get("minutes") or 0) <= 5, f"{q['id']}: give each question 1 to 5 minutes")

    checked = []
    for q in qs:
        text = q.get("text") or ""
        if not text.strip():
            need(False, f"{q['id']}: the question has no text")
            continue
        words = len(text.split())
        need(words <= 60, f"{q['id']}: {words} words is too long to say out loud; keep a question under 60")
        need(text.count("?") <= 1, f"{q['id']}: two questions in one; the candidate answers the easier half")
        need("?" in text or re.match(r"\s*(tell|describe|walk|talk|give|share|show)\b", text, re.I),
             f"{q['id']}: '{text}' is a statement, not a question")
        g = reading_grade(text)
        need(g <= MAX_GRADE, f"{q['id']}: reads at grade {g:g}; keep questions at grade {MAX_GRADE:g} or below",
             blocking=False)
        c = check_question(text, rules)
        checked.append({"id": q["id"], **c})
        if c["level"] == "unchecked":
            risk_text(q["id"], text)
        for r in c["risks"]:
            need(r["level"] != "blocking", f"{q['id']}: asks about {r['topic'].lower()}. {r['why']}")
            if r["level"] == "caution":
                warn.append(f"{q['id']}: touches {r['topic'].lower()}. {r['why']}")
        for p in q.get("probes", []):
            if not p.strip():
                need(False, f"{q['id']}: one of the probes is empty")
                continue
            risk_text(f"{q['id']} probe '{p}'", p)
        a = q.get("anchors") or {}
        for k, v in a.items():
            risk_text(f"{q['id']} anchor {k}", v)
        if q.get("purpose") == "their_questions":
            continue
        need(set(a) == {"1", "2", "3"}, f"{q['id']}: anchors must be exactly 1, 2 and 3 (not 1 to 5: "
                                        "untrained interviewers cluster in the middle of a five-point scale)")
        vals = [str(a.get(k, "")).strip() for k in ("1", "2", "3")]
        need(all(len(set(_same(v).split())) >= 4 for v in vals),
             f"{q['id']}: every anchor needs a written description of what an answer at that level sounds like")
        need(len({_same(v) for v in vals}) == 3, f"{q['id']}: two anchors say the same thing")
        need(len(q.get("probes", [])) >= 1, f"{q['id']}: add a follow-up probe for the one-word answer",
             blocking=False)

    d = guide["decision"]
    top = 3 * len(scored)
    adv, rej = _whole(d.get("advance_at")), _whole(d.get("reject_below"))
    if adv is None or rej is None:
        need(False, "decision rule needs whole numbers for advance_at and reject_below")
    else:
        need(len(scored) < rej < adv <= top,
             f"decision rule: reject below {rej} and advance at {adv} must sit above {len(scored)} "
             f"(the lowest possible total) and at or below {top}")
    middle = d.get("middle") or ""
    need(bool(middle.strip()), "decision rule: say what happens to the scores in between")
    if middle.strip():
        risk_text("decision rule", middle)

    risk_text("the role title", guide["role"])
    for f in ("interviewer", "format"):
        if (guide.get(f) or "").strip():
            risk_text(f"'{f}'", guide[f])

    for kind in ("red_flags", "green_flags"):
        label = kind.replace("_", " ")
        flags = [f for f in guide.get(kind, []) if f.strip()]
        need(len(flags) == len(guide.get(kind, [])), f"{label}: one of them is empty")
        need(len(flags) >= 3, f"give three {label}", blocking=False)
        for f in flags:
            risk_text(f"{label} '{f}'", f)
            hit = [w for w in VAGUE if re.search(r"\b" + w + r"\b", f.lower())]
            need(not hit, f"{label}: '{f}' is an impression ('{hit[0] if hit else ''}'), "
                          "not something you can see or hear", blocking=False)

    for item in guide.get("do_not_ask", []):
        bad = check_question(item["question"], rules)
        need(bad["level"] in ("blocking", "caution"),
             f"do-not-ask '{item['question']}' is not a risky question; the list should hold the ones "
             "managers really reach for", blocking=False)
        alt = check_question(item["instead"], rules)
        need(item["instead"].strip() and alt["level"] not in ("blocking", "caution", "unchecked"),
             f"the safe alternative to '{item['question']}' is itself risky, or empty")

    for field in ("opening", "closing"):
        risk_text(f"the {field} script", guide[field])

    return {"ready": not block, "blocking": block, "warnings": warn, "questions": checked}


def load_guide(path):
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise Refusal(f"the guide is not valid JSON: {exc}")


# ------------------------------------------------------------------- output

CSS = """
:root{--bg:#fff;--fg:#1d1d1b;--mute:#62615c;--line:#d9d6cc;--soft:#f5f3ee;--bad:#b3392e;--warn:#a26b12;--ok:#2f7a4a}
@media (prefers-color-scheme:dark){:root{--bg:#171715;--fg:#efede6;--mute:#a3a198;--line:#3a3934;--soft:#22211e;--bad:#ef7d70;--warn:#e0a84a;--ok:#6cc08b}}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 40px}
h1{font-size:21px;margin:0 0 2px} h2{font-size:15px;margin:22px 0 8px} .sub{color:var(--mute);margin:0 0 14px}
.script{background:var(--soft);border-radius:8px;padding:10px 12px;margin:6px 0 12px}
.q{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:10px 0;break-inside:avoid}
.q h3{font-size:15px;margin:0 0 4px} .q .meta{color:var(--mute);font-size:12px;margin-bottom:8px}
table{border-collapse:collapse;width:100%} td,th{border-top:1px solid var(--line);padding:6px 8px;vertical-align:top;text-align:left}
th{width:46px;color:var(--mute);font-weight:600} .box{float:right;border:1.5px solid var(--fg);border-radius:4px;width:34px;height:26px;margin-left:10px}
ul{margin:4px 0 0;padding-left:20px} .cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:1px 7px;border-radius:9px;margin-right:6px;color:#fff}
.blocking{background:var(--bad)} .caution{background:var(--warn)} .weak{background:var(--mute)} .ok{background:var(--ok)} .unchecked{background:var(--bad)}
.item{border-top:1px solid var(--line);padding:10px 0} .item p{margin:4px 0} small{color:var(--mute)}
@media (max-width:640px){.cols{grid-template-columns:1fr}}
@media print{body{font-size:12px} main{padding:0} .q{padding:8px 10px;margin:6px 0}}
"""


def render_guide(guide, path):
    e = html.escape
    scored = [q for q in guide["questions"] if q.get("purpose") != "their_questions"]
    cards = []
    for n, q in enumerate(guide["questions"], start=1):
        rows = ""
        if q.get("anchors"):
            rows = "<table>" + "".join(f"<tr><th>{k}</th><td>{e(q['anchors'][k])}</td></tr>"
                                       for k in ("3", "2", "1") if k in q["anchors"]) + "</table>"
        probes = ("<div class='meta'>If the answer is short: " + " / ".join(e(p) for p in q.get("probes", []))
                  + "</div>") if q.get("probes") else ""
        box = "<span class='box'></span>" if q.get("purpose") != "their_questions" else ""
        cards.append(f"<div class='q'>{box}<h3>{n}. {e(q['text'])}</h3>"
                     f"<div class='meta'>{e(q.get('purpose', '').replace('_', ' '))}, about {q.get('minutes')} min</div>"
                     f"{probes}{rows}</div>")
    d = guide["decision"]
    flags = lambda k: "".join(f"<li>{e(f)}</li>" for f in guide.get(k, []))
    dna = "".join(f"<tr><td>{e(x['question'])}</td><td>{e(x['instead'])}</td></tr>" for x in guide.get("do_not_ask", []))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(guide['role'])} interview</title>
<style>{CSS}</style></head><body><main>
<h1>{e(guide['role'])}: {e(str(guide['minutes']))}-minute interview</h1>
<p class="sub">{e(guide.get('interviewer', ''))}{', ' + e(guide['format']) if guide.get('format') else ''}.
Ask every question, in this order, the same way for everyone. Score each one as you go: 1, 2 or 3.</p>
<h2>Open</h2><div class="script">{e(guide['opening'])}</div>
{''.join(cards)}
<h2>Close</h2><div class="script">{e(guide['closing'])}</div>
<h2>Decide</h2>
<p>Total out of {3 * len(scored)}. <strong>{e(str(d['advance_at']))} or more: advance.</strong>
Below {e(str(d['reject_below']))}: do not advance. In between: {e(d['middle'])}</p>
<div class="cols"><div><h2>Red flags</h2><ul>{flags('red_flags')}</ul></div>
<div><h2>Green flags</h2><ul>{flags('green_flags')}</ul></div></div>
{'<h2>Do not ask, and what to ask instead</h2><table>' + dna + '</table>' if dna else ''}
<p class="sub" style="margin-top:20px"><small>Checked by scripts/check_guide.py. Not legal advice: confirm local rules.</small></p>
</main></body></html>"""
    open(path, "w", encoding="utf-8").write(page)


def render_check(result, path, title="Interview questions check"):
    e = html.escape
    items = []
    for q in result["questions"]:
        parts = [f"<p><span class='badge {q['level']}'>{LABEL[q['level']]}</span><strong>{e(q['text'])}</strong></p>"]
        if q["level"] == "unchecked":
            parts.append(f"<p>{e(UNCHECKED)}</p>")
        for r in q["risks"]:
            src = f" <small>Source: {e(r['source'])}</small>" if r["source"] else ""
            parts.append(f"<p>{e(r['topic'])}. {e(r['why'])}{src}</p><p><em>Instead:</em> {e(r['instead'])}</p>")
        for w in (q["weak"] if q["level"] == "weak" else []):
            parts.append(f"<p>{e(w['advice'])}</p>")
        items.append("<div class='item'>" + "".join(parts) + "</div>")
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{e(title)}</title>
<style>{CSS}</style></head><body><main><h1>{e(title)}</h1>
<p class="sub">{e(summary(result))}</p>
<p class="sub"><small>{e(LIMITS)}</small></p>{''.join(items)}
<p class="sub"><small>Checked by scripts/check_guide.py against references/question_rules.json. Not legal advice.</small></p>
</main></body></html>"""
    open(path, "w", encoding="utf-8").write(page)


LABEL = {"blocking": "legal risk", "caution": "needs care", "weak": "weak", "unchecked": "not checked",
         "ok": "no rule matched"}
UNCHECKED = ("Not in English. The rules are written for English, so this was not checked. "
             "Have someone check it by hand.")
LIMITS = ("The check matches the phrasings in references/question_rules.json, in English. A risky question "
          "worded in a way it has not seen can pass, so 'no rule matched' is not a clearance.")


def summary(result):
    s = (f"{result['total']} questions: {result['blocking']} legal risk, {result['caution']} need care, "
         f"{result['weak']} weak, {result['ok']} no rule matched")
    if result.get("unchecked"):
        s += f", {result['unchecked']} not checked (not in English)"
    return s + "."


def text_check(result):
    out = [summary(result), LIMITS]
    for q in result["questions"]:
        out.append(f"\n[{LABEL[q['level']].upper()}] {q['text']}")
        if q["level"] == "unchecked":
            out.append("  " + UNCHECKED)
        for r in q["risks"]:
            out.append(f"  {r['topic']}: {r['why']}")
            out.append(f"  Instead: {r['instead']}")
        for w in (q["weak"] if q["level"] == "weak" else []):
            out.append(f"  {w['advice']}")
    return "\n".join(out)


def text_guide(result):
    out = ["READY TO PRINT" if result["ready"] else "NOT READY"]
    for b in result["blocking"]:
        out.append("  BLOCKING  " + b)
    for w in result["warnings"]:
        out.append("  worth a look  " + w)
    out.append(LIMITS)
    return "\n".join(out)


# -------------------------------------------------------------------- tests

def run_tests():
    passed = failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL  {name}")

    rules = load_rules()

    # every question fixture declares what it must and must not trigger
    cases = json.load(open(os.path.join(FIXTURES, "questions.json"), encoding="utf-8"))["cases"]
    for c in cases:
        r = check_question(c["q"], rules)
        ids = {x["id"] for x in r["risks"]} | {w["id"] for w in r["weak"]}
        check(f"q '{c['q']}' is {c['level']}", r["level"] == c["level"])
        for must in c.get("must", []):
            check(f"q '{c['q']}' flags {must}", must in ids)
        for nope in c.get("must_not", []):
            check(f"q '{c['q']}' does not flag {nope}", nope not in ids)

    # every safe alternative the rules offer must itself be safe
    for r in rules["rules"]:
        c = check_question(r["instead"], rules)
        check(f"rule {r['id']}: its own safe alternative passes", c["level"] not in ("blocking", "caution"))
        check(f"rule {r['id']}: names a source or says it has none",
              r["source"] is None or r["source"].startswith("https://"))

    # the sample guide is ready; each broken fixture fails for its named reason only
    good = load_guide(os.path.join(SAMPLE, "overnight_stocker_guide.json"))
    g = check_guide(good, rules)
    check("sample guide: ready to print", g["ready"] and not g["blocking"])
    check("sample guide: no warnings either", not g["warnings"])
    fixtures = json.load(open(os.path.join(FIXTURES, "broken_guides.json"), encoding="utf-8"))

    def mutate(changes):
        guide = json.loads(json.dumps(good))
        for path, value in changes:
            target = guide
            keys = path.split(".")
            idx = lambda t, k: int(k) if isinstance(t, list) else k
            for k in keys[:-1]:
                target = target[idx(target, k)]
            last = idx(target, keys[-1])
            if value == "__delete__":
                del target[last]
            else:
                target[last] = value
        return guide

    for b in fixtures["cases"]:
        res = check_guide(mutate(b["set"]), rules)
        text = " | ".join(res["blocking"] + res["warnings"])
        check(f"broken '{b['name']}': {'not ready' if b['blocking'] else 'ready with a warning'}",
              res["ready"] != b["blocking"])
        check(f"broken '{b['name']}': says '{b['expect']}'", b["expect"] in text)
        n = len(res["blocking"]) if b["blocking"] else len(res["warnings"])
        check(f"broken '{b['name']}': one finding, not a pile", n == 1)

    # a guide in the wrong shape is refused with the field named, never a traceback
    for b in fixtures["refused"]:
        try:
            check_guide(mutate(b["set"]), rules)
            check(f"refused '{b['name']}'", False)
        except Refusal as exc:
            check(f"refused '{b['name']}': says '{b['expect']}'", b["expect"] in str(exc))
    for name, value in (("null", None), ("a list", []), ("a string", "guide")):
        try:
            check_guide(value, rules)
            check(f"refuses a guide that is {name}", False)
        except Refusal as exc:
            check(f"refuses a guide that is {name}", "must be a JSON object" in str(exc))

    # text the English rules cannot read is reported, not passed
    check("non-English question is not checked, not passed",
          check_question("¿Cuántos hijos tiene usted y quién los cuida?", rules)["level"] == "unchecked")
    check("one accented word is still English", check_question("Have you worked in a café?", rules)["level"] != "unchecked")

    # the sample manager questions: what is planted, and nothing else
    s = check_questions(os.path.join(SAMPLE, "manager_questions.txt"), rules)
    exp = json.load(open(os.path.join(SAMPLE, "manager_questions_expected.json"), encoding="utf-8"))
    check("sample questions: levels as planted", [q["level"] for q in s["questions"]] == exp["levels"])
    check("sample questions: blocking count", s["blocking"] == exp["levels"].count("blocking"))

    check("grade: plain question is low", reading_grade("How would you get here for a 6am start?") <= 6)
    check("grade: jargon is high", reading_grade(
        "Characterise your methodology for prioritising concurrent operational responsibilities.") > 12)

    import tempfile
    tmp = tempfile.mkdtemp(prefix="sig-")
    try:
        render_guide(good, os.path.join(tmp, "g.html"))
        body = open(os.path.join(tmp, "g.html"), encoding="utf-8").read()
        check("html guide: renders every question", all(html.escape(q["text"]) in body for q in good["questions"]))
        check("html guide: self-contained", "<script" not in body and "http://" not in body)
        render_check(s, os.path.join(tmp, "c.html"))
        check("html check: renders", "legal risk" in open(os.path.join(tmp, "c.html"), encoding="utf-8").read())
        try:
            check_questions(os.path.join(tmp, "nope.txt"))
            check("refuses a missing file", False)
        except Refusal:
            check("refuses a missing file", True)
        u16 = os.path.join(tmp, "u16.txt")
        open(u16, "wb").write("Do you have kids?\nHow tall are you?\n".encode("utf-16"))
        r16 = check_questions(u16, rules)
        check("reads a UTF-16 questions file", r16["total"] == 2 and r16["blocking"] == 1)
        open(u16, "wb").write(b"\xff\xfe\x00\xd8")
        try:
            check_questions(u16, rules)
            check("refuses unreadable text", False)
        except Refusal:
            check("refuses unreadable text", True)
        check("text output says no match is not a clearance", "not a clearance" in text_check(s))
        bad = os.path.join(tmp, "bad.json")
        open(bad, "w").write("{not json")
        try:
            load_guide(bad)
            check("refuses broken JSON", False)
        except Refusal:
            check("refuses broken JSON", True)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"{passed}/{passed + failed} passed")
    return 0 if failed == 0 else 1


# --------------------------------------------------------------------- main

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
        if opt("--questions"):
            r = check_questions(opt("--questions"))
            print(text_check(r))
            if opt("--html"):
                render_check(r, opt("--html"))
            return 1 if r["blocking"] or r["unchecked"] else 0
        if opt("--guide"):
            guide = load_guide(opt("--guide"))
            r = check_guide(guide)
            print(text_guide(r))
            if opt("--html") and r["ready"]:
                render_guide(guide, opt("--html"))
            elif opt("--html"):
                print("No sheet written: fix the blocking items first.")
            return 0 if r["ready"] else 1
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:                          # a bug, not a verdict on the guide
        print(f"ERROR: the checker failed ({type(exc).__name__}: {exc}). This is a bug in the checker, "
              "not a finding about your guide.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
