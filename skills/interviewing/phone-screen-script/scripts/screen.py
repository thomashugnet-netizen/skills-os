#!/usr/bin/env python3
"""
Phone screen engine: checks a five-minute phone screen before anyone dials,
and reads the call log once they do.

    python3 screen.py --script script.json [--html script.html]
    python3 screen.py --calls calls.csv [--max-attempts 3] [--html report.html] [--json report.json]
    python3 screen.py --demo
    python3 screen.py --test

script.json  the call, in the shape of references/sample/northline_script.json:
             the shifts you are short of, the running order, the three gates,
             the booking, the voicemail, the follow-up text, the attempt rule.
calls.csv    one row per call attempt:
             candidate_id, caller_id, applied_at, attempt_at, outcome
             [, result, booked, interview_at, showed, texted]
             outcome: answered, voicemail, no_answer, wrong_number, texted_back
             result (answered calls): advanced, redirected, declined_availability,
             declined_prerequisite, declined_preview, withdrew, no_decision

The script check is a rubric the code enforces: availability first and asked
shift by shift against the real gaps; the journey asked as "how", never "can
you"; only genuine prerequisites; no assessment questions; a preview under
thirty seconds followed by "do you still want it"; three gates and nothing
else decides the call; a polite no and a redirect written out; two specific
slots offered and a confirmation sent before hanging up; pay stated; under
five minutes read aloud; a voicemail under twenty seconds with a way back; a
text after every voicemail; attempts spread across the day and a stop rule;
five fields captured at most.

The call log shows what decides whether a better script changes anything:
how fast the first call goes out and what that is worth, when people answer,
whether a text after a voicemail brings them back, who ends calls without a
decision or a booking, and whether far-off interview slots cost shows.

Exit codes: 0 script ready or log read, 1 script not ready, 2 no mode,
3 input refused, 4 the engine failed. Standard library only.
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

ORDER = ["opener", "availability", "start_date", "travel", "prerequisites", "preview", "questions", "decision",
         "booking"]
REQUIRED = ["opener", "availability", "start_date", "travel", "preview", "decision", "booking"]
WPS = 2.5                 # words per second, read aloud
ANSWER_S = 8              # seconds per short answer
MAX_SECONDS = 300
MAX_PREVIEW_WORDS = 80    # about thirty seconds
MAX_VOICEMAIL_WORDS = 50  # about twenty seconds
MAX_CAPTURE = 5
DAYPARTS = {"morning": (8, 12), "afternoon": (12, 17), "evening": (17, 21)}
SPEED_BANDS = [(0, 1, "under 1 hour"), (1, 4, "1-4 hours"), (4, 24, "4-24 hours"), (24, 72, "1-3 days"),
               (72, 10 ** 6, "over 3 days")]
MIN_N = 30

TIME = re.compile(r"\b(\d{1,2}(:\d{2})?\s?(am|pm)|\d{1,2}:\d{2}|noon|midnight|mornings?|evenings?|nights?|"
                  r"overnights?|afternoons?|weekends?|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
                  r"mon|tue|wed|thu|fri|sat|sun)\b", re.I)
VAGUE_AVAIL = re.compile(r"\b(still (correct|the same|accurate)|are you flexible|open availability|any availability|"
                         r"what('s| is) your availability|when are you available)\b", re.I)
ASSESS = re.compile(r"\b(tell (me|us) about yourself|tell (me|us) about a time|describe a (time|situation)|"
                    r"a time when|your (greatest )?strengths?|your (biggest |greatest )?weakness|why do you want|"
                    r"where do you see yourself|what motivates you|why should we hire)\b", re.I)
PREREQ_OK = re.compile(r"\b(1[68]|21) or older\b|\bat least (1[68]|21)\b|\blicen[cs]e\b|\bcdl\b|"
                       r"\bauthori[sz]ed to work\b|\bwork authori[sz]ation\b|\bcertif\w+\b|\bfood handler\b", re.I)
RISKY = [("age", r"\b(how old|your age|date of birth|birth ?(day|year)|what year did you graduate)\b"),
         ("citizenship", r"\b(are you a (u\.?s\.? )?citizen|citizenship|green card|where are you from|nationality)\b"),
         ("family", r"\b(children|kids|child ?care|babysitter|daycare|pregnan\w*|married|husband|wife)\b"),
         ("health", r"\b(health (condition|problem)|medical condition|disabilit\w*|medications?|injur\w*)\b"),
         ("religion", r"\b(church|religio\w*|pray\w*|sabbath)\b"),
         ("arrest", r"\b(arrested|criminal (record|history)|convicted|felon\w*)\b"),
         ("pay history", r"\b(current|previous|last) (salary|pay|wage|rate)\b|\bhow much (do|did) you (make|earn)\b")]
VAGUE_END = re.compile(r"\b(we'?ll be in touch|we will be in touch|someone will (call|contact|reach out to) you|"
                       r"get back to you|hear from us|we'?ll let you know)\b", re.I)
WAY_BACK = re.compile(r"\b(text|reply|link|book|call (us|me) back on|\{\{\s*(booking_link|text_number|callback_number)"
                      r"\s*\}\})", re.I)
PAY = re.compile(r"\$\s?\d|\{\{\s*pay\s*\}\}", re.I)
OPT_OUT = re.compile(r"\b(reply stop|text stop|stop to opt out|opt out)\b", re.I)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w-])(\+?\d[\d\s().-]{8,}\d)(?![\w-])")
DATEISH = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{1,2}(:\d{2}){0,2})?$|^\d{1,2}/\d{1,2}/\d{2,4}$")
NOMINATIVE = re.compile(r"(^|_)(first|last|full)?_?name($|_)|e-?mail|phone|mobile|address|street|zip|postcode|"
                        r"ssn|dob|birth|notes?$|comment", re.I)


class Refusal(Exception):
    pass


def words(s):
    return len(re.findall(r"[A-Za-z0-9$'{}_]+", s or ""))


# ------------------------------------------------------------------ the script

def load_script(path):
    try:
        s = json.load(open(path, encoding="utf-8-sig"))
    except OSError:
        raise Refusal(f"script: file not found ({path}).")
    except ValueError as exc:
        raise Refusal(f"script: not valid JSON ({exc}).")
    return s


def section(s, sid):
    return next((x for x in s.get("sections", []) if isinstance(x, dict) and x.get("id") == sid), None)


def questions(sec):
    qs = (sec or {}).get("questions", [])
    if not isinstance(qs, list):
        raise Refusal(f"script: '{sec.get('id')}' questions must be a list.")
    out = []
    for q in qs:
        if not isinstance(q, dict) or not isinstance(q.get("text"), str):
            raise Refusal(f"script: every question in '{sec.get('id')}' needs \"text\".")
        out.append(q)
    return out


def text_of(v):
    return v if isinstance(v, str) else ""


def check_script(s):
    if not isinstance(s, dict) or not isinstance(s.get("sections"), list) or not s["sections"]:
        raise Refusal("script: expected an object with \"sections\" (see references/sample/northline_script.json).")
    for k in ("role", "site", "company"):
        if not isinstance(s.get(k), str) or not s[k].strip():
            raise Refusal(f"script: \"{k}\" is needed.")
    block, warn = [], []
    if not all(isinstance(x, dict) for x in s["sections"]):
        raise Refusal("script: every section is an object with an \"id\".")
    ids = [x.get("id") for x in s["sections"]]
    for sid in ids:
        if sid not in ORDER:
            raise Refusal(f"script: unknown section '{sid}'. Sections are {', '.join(ORDER)}.")
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise Refusal(f"script: section '{dup[0]}' appears twice. Each section once.")
    for sid in REQUIRED:
        if sid not in ids:
            block.append(f"No '{sid}' section." + (" A screen with no booking cannot end properly; it drifts into "
                                                   "an interview." if sid == "booking" else ""))
    order = [ORDER.index(i) for i in ids]
    if order != sorted(order):
        block.append(f"Sections run {' > '.join(ids)}. The order is {' > '.join(i for i in ORDER if i in ids)}: "
                     "availability straight after the opener, because it is the fact most likely to end the call.")

    allq = [(sid, q) for sid in ids for q in questions(section(s, sid))]
    spoken = sum(words(text_of(x.get("say"))) for x in s["sections"] if isinstance(x, dict)) + \
        sum(words(q["text"]) for _, q in allq)
    seconds = round(spoken / WPS + ANSWER_S * len(allq))
    if seconds > MAX_SECONDS:
        block.append(f"About {seconds} seconds read aloud with answers. Five minutes is {MAX_SECONDS}: cut, or the "
                     "booking at the end is what gets dropped.")

    op = text_of((section(s, "opener") or {}).get("say"))
    if op:
        if len(re.findall(r"[.!?]", op)) > 2:
            block.append("The opener is more than two sentences. Who you are, which job, how long: callers who take "
                         "longer get treated as a sales call.")
        if s["company"].lower() not in op.lower() or not re.search(r"\bminutes?\b", op, re.I):
            block.append("The opener must name the company and say how long the call takes.")
        if ASSESS.search(op):
            block.append("The opener asks them to talk about themselves. It burns ninety seconds and scores nothing.")

    gaps = s.get("rota_gaps") or []
    if not isinstance(gaps, list) or not all(isinstance(g, str) and g.strip() for g in gaps):
        raise Refusal("script: \"rota_gaps\" is a list of the shifts you are short of, as text.")
    if not gaps:
        block.append("No rota_gaps: the shifts you are short of. Availability is asked against them, block by block.")
    aq = questions(section(s, "availability"))
    if section(s, "availability") is not None:
        if len(aq) < max(1, len(gaps)):
            block.append(f"{len(aq)} availability question(s) for {len(gaps)} shift gap(s). Ask each gap out loud: "
                         "applicants tick availability generously on a phone.")
        for q in aq:
            if VAGUE_AVAIL.search(q["text"]):
                block.append(f"Availability: '{q['text']}' gets a yes from everybody. Name the shift: 'Can you work "
                             "Sunday to Wednesday nights, 10pm to 6:30am?'")
            elif not TIME.search(q["text"]):
                block.append(f"Availability: '{q['text']}' names no day or time.")

    tq = questions(section(s, "travel"))
    if section(s, "travel") is not None and not any(re.match(r"\s*how\b", q["text"], re.I) and
                                                    re.search(r"\b(get|travel|come|commute)\b", q["text"], re.I)
                                                    for q in tq):
        block.append("Travel: ask how they would get here for the earliest shift, in their words. 'Can you get here?' "
                     "gets a yes; a route with a time in it is an answer.")

    for q in questions(section(s, "prerequisites")):
        if not PREREQ_OK.search(q["text"]):
            block.append(f"Prerequisite: '{q['text']}' is not a minimum age, a licence or certificate the job needs, "
                         "or work authorisation. Anything else is not a reason to end a screen.")

    for sid, q in allq:
        if ASSESS.search(q["text"]):
            block.append(f"{sid}: '{q['text']}' assesses. Five minutes cannot score it; it belongs in the interview, "
                         "with anchors.")
        for topic, pat in RISKY:
            if re.search(pat, q["text"], re.I) and not PREREQ_OK.search(q["text"]):
                block.append(f"{sid}: '{q['text']}' strays into {topic}. Leave it out of the call.")

    pv = section(s, "preview")
    if pv is not None:
        if words(text_of(pv.get("say"))) > MAX_PREVIEW_WORDS:
            block.append(f"The preview is {words(text_of(pv.get('say')))} words, over thirty seconds. Say the hard "
                         "part honestly and stop.")
        if not words(text_of(pv.get("say"))):
            block.append("The preview says nothing about the job. Thirty seconds of the honest hard part.")
        if not any(q.get("gate") for q in questions(pv)):
            block.append("The preview is not followed by a gate: 'Knowing that, do you still want it?'")

    gate_secs = sorted({sid for sid, q in allq if q.get("gate")})
    stray = [sid for sid in gate_secs if sid not in ("availability", "prerequisites", "preview")]
    if stray:
        block.append(f"Gates in {', '.join(stray)}. Only availability, a genuine prerequisite and the preview "
                     "decide the call; everything else advances.")
    if not any(q.get("gate") for q in aq) and aq:
        block.append("No availability question is a gate. No overlap with the shifts you need ends the call.")

    dec = section(s, "decision") or {}
    no = dec.get("no") if isinstance(dec.get("no"), dict) else {}
    needed = ["availability", "preview"] + (["prerequisite"] if questions(section(s, "prerequisites")) else [])
    for g in needed:
        if not text_of(no.get(g)).strip():
            block.append(f"No wording for a polite no on {g}. Write it, so every caller says it the same way.")
    if not text_of(dec.get("redirect")).strip():
        block.append("No redirect for partial availability: it is a routing outcome, not a rejection ('the Kettering "
                     "store needs Tuesday mornings').")
    for g, t in no.items():
        if VAGUE_END.search(text_of(t)):
            block.append(f"The no on {g} promises to be in touch. Say the answer on the call.")

    bk = section(s, "booking") or {}
    bsay = text_of(bk.get("say"))
    if bk:
        two = (re.search(r"\{\{\s*slot_1\s*\}\}", bsay) and re.search(r"\{\{\s*slot_2\s*\}\}", bsay)) or \
            len(TIME.findall(bsay)) >= 2
        if not two:
            block.append("Booking: offer two specific slots. Two options get chosen; 'when suits you?' gets "
                         "postponed.")
        if VAGUE_END.search(bsay):
            block.append("Booking: 'we'll be in touch' hands the candidate to whichever employer books properly.")
        conf = text_of(bk.get("confirmation"))
        if not conf:
            block.append("Booking: no confirmation text sent before hanging up.")
        else:
            if not re.search(r"\{\{\s*(address|site)\s*\}\}|\baddress\b", conf, re.I):
                block.append("The confirmation does not say where.")
            if not re.search(r"\{\{\s*(interviewer|contact)\s*\}\}|\bask for\b", conf, re.I):
                block.append("The confirmation does not name who to ask for.")
            if not re.search(r"\{\{\s*(slot|date|time)\w*\s*\}\}", conf, re.I) and not TIME.search(conf):
                block.append("The confirmation does not say when.")
    every = " ".join(text_of(x.get("say")) for x in s["sections"] if isinstance(x, dict)) + " " + \
        " ".join(text_of(x.get("answer")) for _, x in allq) + " " + text_of(s.get("pay"))
    if not PAY.search(every):
        block.append("Pay is never stated. Candidates ask, and a caller who cannot answer gets fewer shows: give the "
                     "rate or the range.")

    vm = text_of(s.get("voicemail"))
    if not vm:
        block.append("No voicemail. At frontline volume most attempts reach one: it is the main path, not an edge case.")
    else:
        if words(vm) > MAX_VOICEMAIL_WORDS:
            block.append(f"The voicemail is {words(vm)} words, over twenty seconds.")
        for k in ("company", "role"):
            if s[k].lower() not in vm.lower():
                block.append(f"The voicemail does not name the {k}.")
        if not WAY_BACK.search(vm):
            block.append("The voicemail gives no way back. A text-back number or a booking link: people who missed "
                         "you will text, not ring an unknown number.")
    ft = text_of(s.get("follow_up_text"))
    if not ft:
        block.append("No text after the voicemail. The text gets read; the voicemail does not.")
    else:
        if len(ft) > 320:
            block.append(f"The follow-up text is {len(ft)} characters. Two text segments at most.")
        if not WAY_BACK.search(ft):
            block.append("The follow-up text gives no way to reply or book.")
        if not OPT_OUT.search(ft):
            block.append("The follow-up text has no opt-out.")
    at = s.get("attempts") if isinstance(s.get("attempts"), dict) else {}
    mx = at.get("max")
    dps = at.get("dayparts") if isinstance(at.get("dayparts"), list) else []
    dps = [d if isinstance(d, str) else "" for d in dps]
    if isinstance(mx, bool) or not isinstance(mx, int) or not 2 <= mx <= 5:
        block.append("attempts.max: between 2 and 5 calls before the stop rule.")
    elif len(dps) != mx or len(set(dps)) < 2 or any(d not in DAYPARTS for d in dps):
        block.append("attempts.dayparts: one per attempt, from morning, afternoon and evening, at least two different. "
                     "Someone on nights is asleep at 2pm.")
    if not text_of(at.get("stop")).strip():
        block.append("No stop rule. Without one a candidate sits in the queue forever.")
    if not text_of(s.get("callback")).strip():
        block.append("No script for the inbound callback: whoever answers has no idea what the call is about.")
    cap = s.get("capture") if isinstance(s.get("capture"), list) else []
    if any(not isinstance(c, str) or not c.strip() for c in cap):
        block.append("Every capture field is a short line of text.")
    if not cap:
        block.append("No capture fields: what the caller writes down.")
    elif len(cap) > MAX_CAPTURE:
        block.append(f"{len(cap)} capture fields. Five at most, or the call runs over.")
    return {"ready": not block, "blocking": block, "warnings": warn, "seconds": seconds, "questions": len(allq)}


def text_script(res, s):
    out = [f"Phone screen: {s['role']}, {s['site']}. About {res['seconds']} seconds read aloud with answers, "
           f"{res['questions']} questions."]
    if res["ready"]:
        out.append("READY to dial.")
    else:
        out.append(f"NOT READY: {len(res['blocking'])} thing(s) to fix.")
        out += [f"  - {b}" for b in res["blocking"]]
    return "\n".join(out)


def render_script(s, path):
    e = html.escape
    parts = []
    for sec in s["sections"]:
        qs = "".join(f"<li>{e(q['text'])}" + (" <b>[gate]</b>" if q.get("gate") else "") + "</li>"
                     for q in questions(sec))
        extra = ""
        if sec.get("id") == "decision":
            no = sec.get("no", {})
            extra = "".join(f"<p><b>If no on {e(k)}:</b> {e(text_of(v))}</p>" for k, v in no.items()) + \
                f"<p><b>Partial availability:</b> {e(text_of(sec.get('redirect')))}</p>"
        if sec.get("id") == "booking":
            extra = f"<p><b>Confirmation text, sent before you hang up:</b> {e(text_of(sec.get('confirmation')))}</p>"
        parts.append(f"<section><h2>{e(sec['id'].replace('_', ' ').title())}</h2>"
                     f"<p class=say>{e(text_of(sec.get('say')))}</p><ol>{qs}</ol>{extra}</section>")
    at = s["attempts"]
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Phone screen</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#111}}
section{{border-top:1px solid #999;page-break-inside:avoid}}.say{{font-style:italic}}h2{{font-size:16px}}</style>
<h1>Phone screen: {e(s['role'])}, {e(s['site'])}</h1>
<p><b>Shifts we are short of:</b> {e('; '.join(s['rota_gaps']))}</p>{''.join(parts)}
<section><h2>If they don't answer</h2><p><b>Voicemail:</b> {e(s['voicemail'])}</p>
<p><b>Then text:</b> {e(s['follow_up_text'])}</p>
<p><b>Attempts:</b> {at['max']}, {', '.join(at['dayparts'])}. {e(at['stop'])}</p>
<p><b>If they call back:</b> {e(s['callback'])}</p></section>
<section><h2>Write down</h2><ol>{''.join(f'<li>{e(c)}</li>' for c in s['capture'])}</ol></section></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ the call log

def has_phone(text):
    for m in PHONE.finditer(text):
        cand = m.group(1).strip()
        if 10 <= len(re.sub(r"\D", "", cand)) <= 15 and not DATEISH.match(cand):
            return True
    return False


def when(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        # the wall-clock time is what decides morning or evening, so an offset is dropped, not converted
        return dt.datetime.fromisoformat(s.replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        return "bad"


def wilson(k, n, z=1.645):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def daypart(t):
    for name, (a, b) in DAYPARTS.items():
        if a <= t.hour < b:
            return name
    return "outside hours"


def read_calls(path):
    if not os.path.exists(path):
        raise Refusal(f"calls: file not found ({path}).")
    raw = open(path, "rb").read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
    if EMAIL.search(text):
        raise Refusal("calls: the file contains an email address. Use opaque candidate ids.")
    if has_phone(text):
        raise Refusal("calls: the file contains what looks like a phone number. The log needs opaque ids, never the "
                      "number you dialled.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise Refusal("calls: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    for h in header:
        if NOMINATIVE.search(h):
            raise Refusal(f"calls: column '{h}' looks like personal information. Opaque ids only.")
    for c in ("candidate_id", "caller_id", "applied_at", "attempt_at", "outcome"):
        if c not in header:
            raise Refusal(f"calls: missing column '{c}'.")
    out = []
    for n, r in enumerate(rows[1:], 2):
        d = {h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)}
        a, t = when(d["applied_at"]), when(d["attempt_at"])
        if a in (None, "bad") or t in (None, "bad"):
            raise Refusal(f"calls row {n}: applied_at and attempt_at must be date-times like 2026-10-01T09:15.")
        if t < a:
            raise Refusal(f"calls row {n}: called before they applied.")
        oc = d["outcome"].lower()
        if oc not in ("answered", "voicemail", "no_answer", "wrong_number", "texted_back"):
            raise Refusal(f"calls row {n}: outcome '{d['outcome']}' should be answered, voicemail, no_answer, "
                          "wrong_number or texted_back.")
        res = d.get("result", "").lower()
        iv = when(d.get("interview_at", ""))
        if iv == "bad":
            raise Refusal(f"calls row {n}: interview_at is not a date-time.")
        out.append({"cand": d["candidate_id"], "caller": d["caller_id"], "applied": a, "at": t, "outcome": oc,
                    "result": res, "booked": d.get("booked", "").lower() in ("yes", "y", "true", "1"),
                    "interview": iv, "showed": d.get("showed", "").lower(),
                    "texted": d.get("texted", "").lower() in ("yes", "y", "true", "1"), "cols": frozenset(header)})
    if len({x["cand"] for x in out}) < 50:
        raise Refusal("calls: fewer than 50 candidates. Too few to read.")
    return out


def analyse_calls(rows, max_attempts=3, as_of=None):
    by = {}
    for x in sorted(rows, key=lambda x: x["at"]):
        by.setdefault(x["cand"], []).append(x)
    as_of = as_of or max(x["at"] for x in rows)
    cols = rows[0].get("cols", frozenset())
    measure = "booked" if "booked" in cols else "reached"
    cands = []
    for cid, att in by.items():
        first = att[0]
        reached = next((x for x in att if x["outcome"] in ("answered", "texted_back")), None)
        ans = next((x for x in att if x["outcome"] == "answered"), None)
        booked = any(x["booked"] for x in att)
        iv = next((x["interview"] for x in att if x["interview"]), None)
        show = next((x["showed"] for x in att if x["showed"]), "")
        # attempts to reach them: outbound calls up to and including the one that reached them; a text back
        # ends the chase, and calls arranged after it are not attempts
        chase = []
        for x in att:
            if x["outcome"] == "texted_back":
                break
            chase.append(x)
            if x["outcome"] in ("answered", "wrong_number"):
                break
        cands.append({"id": cid, "caller": (ans or first)["caller"],
                      "delay_h": (first["at"] - first["applied"]).total_seconds() / 3600, "attempts": len(chase),
                      "reached": bool(reached), "result": ans["result"] if ans else "", "booked": booked,
                      "lag_d": (iv - ans["at"]).total_seconds() / 86400 if (iv and ans) else None,
                      "showed": show, "last": att[-1]["at"], "att": att, "chase": chase})
    n = len(cands)
    # 1. speed to first call
    speed = []
    for lo, hi, label in SPEED_BANDS:
        g = [c for c in cands if lo <= c["delay_h"] < hi]
        k = sum(1 for c in g if c["booked"])
        r = sum(1 for c in g if c["reached"])
        hit = k if measure == "booked" else r
        speed.append({"band": label, "n": len(g), "reached": r, "booked": k,
                      "rate": round(hit / len(g), 3) if g else None,
                      "ci90": [round(v, 3) for v in wilson(hit, len(g))]})
    fast = [b for b in speed[:2] if b["n"]]
    slow = [b for b in speed[3:] if b["n"]]
    fk, fn = sum(b[measure] for b in fast), sum(b["n"] for b in fast)
    sk, sn = sum(b[measure] for b in slow), sum(b["n"] for b in slow)
    speed_finding = None
    if fn >= MIN_N and sn >= MIN_N:
        flo, fhi = wilson(fk, fn)
        slo, shi = wilson(sk, sn)
        speed_finding = {"fast_rate": round(fk / fn, 3), "slow_rate": round(sk / sn, 3),
                         "separated": flo > shi, "fast_n": fn, "slow_n": sn}
    med_delay = sorted(c["delay_h"] for c in cands)[n // 2]
    within_4 = sum(1 for c in cands if c["delay_h"] < 4) / n

    # 2. when people answer: cold attempts only, not calls arranged after a text back
    attempts = [x for c in cands for x in c["chase"] if x["outcome"] in ("answered", "voicemail", "no_answer")]
    parts = {}
    for x in attempts:
        p = daypart(x["at"])
        d = parts.setdefault(p, [0, 0])
        d[1] += 1
        d[0] += 1 if x["outcome"] == "answered" else 0
    dayparts = {p: {"attempts": v[1], "answered": v[0], "rate": round(v[0] / v[1], 3),
                    "ci90": [round(z, 3) for z in wilson(v[0], v[1])]} for p, v in parts.items() if v[1]}
    best = max(dayparts, key=lambda p: dayparts[p]["rate"]) if dayparts else None
    worst_heavy = None
    if best:
        tot = sum(v["attempts"] for v in dayparts.values())
        for p, v in dayparts.items():
            if p != best and v["attempts"] / tot >= 0.4 and v["ci90"][1] < dayparts[best]["ci90"][0]:
                worst_heavy = p
    # repeat attempts
    by_attempt = {}
    for c in cands:
        for i, x in enumerate(c["chase"][:6], 1):
            if x["outcome"] in ("answered", "voicemail", "no_answer"):
                d = by_attempt.setdefault(i, [0, 0])
                d[1] += 1
                d[0] += 1 if x["outcome"] == "answered" else 0
    attempt_rates = {i: {"n": v[1], "rate": round(v[0] / v[1], 3)} for i, v in sorted(by_attempt.items())}

    # 3. text after voicemail
    vm_text, vm_none = [0, 0], [0, 0]
    for c in cands:
        vms = [i for i, x in enumerate(c["att"]) if x["outcome"] == "voicemail"]
        if not vms:
            continue
        i = vms[0]
        later = c["att"][i + 1:]
        back = any(x["outcome"] in ("answered", "texted_back") for x in later)
        bucket = vm_text if c["att"][i]["texted"] else vm_none
        bucket[1] += 1
        bucket[0] += 1 if back else 0
    text_finding = None
    if vm_text[1] >= MIN_N and vm_none[1] >= MIN_N:
        tlo, _ = wilson(*vm_text)
        _, nhi = wilson(*vm_none)
        text_finding = {"with_text": round(vm_text[0] / vm_text[1], 3), "without": round(vm_none[0] / vm_none[1], 3),
                        "n_text": vm_text[1], "n_none": vm_none[1], "separated": tlo > nhi,
                        "share_texted": round(vm_text[1] / (vm_text[1] + vm_none[1]), 2)}

    # 4. calls that end without a decision or a booking, by caller
    answered = [c for c in cands if c["result"]]
    callers = {}
    for c in answered:
        d = callers.setdefault(c["caller"], {"answered": 0, "no_decision": 0, "advanced": 0, "unbooked": 0})
        d["answered"] += 1
        d["no_decision"] += 1 if c["result"] == "no_decision" else 0
        if c["result"] in ("advanced", "redirected"):
            d["advanced"] += 1
            d["unbooked"] += 0 if c["booked"] else 1
    team_adv = sum(d["advanced"] for d in callers.values())
    team_unb = sum(d["unbooked"] for d in callers.values())
    team_rate = team_unb / team_adv if team_adv else 0
    team_ans = sum(d["answered"] for d in callers.values())
    team_nd = sum(d["no_decision"] for d in callers.values()) / team_ans if team_ans else 0
    caller_flags = []
    for cid, d in sorted(callers.items()):
        if d["advanced"] >= 20:
            lo, _ = wilson(d["unbooked"], d["advanced"])
            others_adv = team_adv - d["advanced"]
            others_rate = (team_unb - d["unbooked"]) / others_adv if others_adv else 0
            if lo > others_rate and d["unbooked"] / d["advanced"] >= 0.1:
                caller_flags.append({"caller": cid, "type": "unbooked", "rate": round(d["unbooked"] / d["advanced"], 2),
                                     "others": round(others_rate, 2), "n": d["advanced"]})
        if d["answered"] >= 20:
            lo, _ = wilson(d["no_decision"], d["answered"])
            others = (sum(x["no_decision"] for x in callers.values()) - d["no_decision"]) / \
                max(1, team_ans - d["answered"])
            if lo > others and d["no_decision"] / d["answered"] >= 0.1:
                caller_flags.append({"caller": cid, "type": "no_decision",
                                     "rate": round(d["no_decision"] / d["answered"], 2), "others": round(others, 2),
                                     "n": d["answered"]})

    # 5. how far off the interview is, and shows
    near = [c for c in cands if c["booked"] and c["lag_d"] is not None and c["showed"] in ("yes", "no") and
            c["lag_d"] <= 2]
    far = [c for c in cands if c["booked"] and c["lag_d"] is not None and c["showed"] in ("yes", "no") and
           c["lag_d"] > 2]
    show_finding = None
    if len(near) >= MIN_N and len(far) >= MIN_N:
        nk, fk2 = sum(1 for c in near if c["showed"] == "yes"), sum(1 for c in far if c["showed"] == "yes")
        nlo, _ = wilson(nk, len(near))
        _, fhi2 = wilson(fk2, len(far))
        show_finding = {"near_rate": round(nk / len(near), 3), "far_rate": round(fk2 / len(far), 3),
                        "near_n": len(near), "far_n": len(far), "separated": nlo > fhi2}

    # 6. limbo: no answer, fewer attempts than the rule, nothing for a week (a wrong number is closed, not limbo)
    limbo = [c for c in cands if not c["reached"] and c["attempts"] < max_attempts and
             (as_of - c["last"]).days >= 7 and not any(x["outcome"] == "wrong_number" for x in c["att"])]
    over = [c for c in cands if c["attempts"] > max_attempts]
    return {"candidates": n, "as_of": as_of.isoformat(timespec="minutes"), "measure": measure,
            "has_result": "result" in cols, "median_hours_to_first_call":
            round(med_delay, 1), "called_within_4h": round(within_4, 2), "speed": speed,
            "speed_finding": speed_finding, "dayparts": dayparts, "best_daypart": best, "heavy_poor_daypart":
            worst_heavy, "attempt_rates": attempt_rates, "text_finding": text_finding,
            "team_unbooked_rate": round(team_rate, 2), "team_no_decision_rate": round(team_nd, 2),
            "caller_flags": caller_flags, "show_finding": show_finding, "limbo": len(limbo),
            "over_max": len(over), "max_attempts": max_attempts}


def text_calls(r):
    L = [f"Call log: {r['candidates']:,} candidates, as of {r['as_of']}."]
    L.append("")
    L.append(f"Speed. Median {r['median_hours_to_first_call']:g} hours from application to first call; "
             f"{round(r['called_within_4h'] * 100)}% called within 4 hours.")
    for b in r["speed"]:
        if b["n"]:
            L.append(f"  {b['band']:<14} {b['n']:>5} candidates, {round(b['rate'] * 100):>3}% {r['measure']} "
                     f"(90% range {round(b['ci90'][0] * 100)}-{round(b['ci90'][1] * 100)}%)")
    sf = r["speed_finding"]
    verb = "book" if r["measure"] == "booked" else "are reached"
    if r["measure"] == "reached":
        L.append("  No 'booked' column: speed is read against being reached, not booked.")
    if sf and sf["separated"]:
        L.append(f"  Called within 4 hours, {round(sf['fast_rate'] * 100)}% {verb}; after a day, "
                 f"{round(sf['slow_rate'] * 100)}%. Calling first is worth more than any wording: frontline "
                 "applicants apply to several employers in one sitting.")
    elif sf:
        L.append(f"  How fast the first call goes out and how many {verb} do not separate clearly in this log.")
    else:
        L.append("  Too few candidates called within 4 hours or after a day to compare.")
    L.append("")
    L.append("When people answer")
    for p, v in sorted(r["dayparts"].items(), key=lambda kv: -kv[1]["rate"]):
        L.append(f"  {p:<14} {v['answered']:>5}/{v['attempts']:<5} answered ({round(v['rate'] * 100)}%)")
    if r["heavy_poor_daypart"]:
        L.append(f"  Most attempts go out in the {r['heavy_poor_daypart']}, when people answer least. Move them to the "
                 f"{r['best_daypart']}.")
    ar = r["attempt_rates"]
    ar = {i: v for i, v in ar.items() if v["n"] >= MIN_N}
    if ar:
        L.append("  Answer rate by attempt: " + ", ".join(f"#{i} {round(v['rate'] * 100)}%" for i, v in ar.items()))
    tf = r["text_finding"]
    L.append("")
    if tf:
        if tf["separated"]:
            L.append(f"After a voicemail: {round(tf['with_text'] * 100)}% come back when a text follows, "
                     f"{round(tf['without'] * 100)}% when it does not. {round(tf['share_texted'] * 100)}% of "
                     "voicemails are followed by a text today: make it every one.")
        else:
            L.append(f"After a voicemail: {round(tf['with_text'] * 100)}% come back with a text, "
                     f"{round(tf['without'] * 100)}% without; not clearly different in this log.")
    else:
        L.append("After a voicemail: too few voicemails with and without a text to compare (or no 'texted' column).")
    L.append("")
    if not r["has_result"]:
        L.append("No 'result' column: how answered calls end, and by whom, cannot be read.")
    else:
        L.append(f"Calls that end open: {round(r['team_no_decision_rate'] * 100)}% of answered calls end with no "
                 f"decision; {round(r['team_unbooked_rate'] * 100)}% of people advanced leave without a booked slot.")
    for f in r["caller_flags"]:
        what = (f"of the {f['n']} people they advanced left without a booked slot" if f["type"] == "unbooked" else
                f"of their {f['n']} answered calls ended with no decision")
        L.append(f"  {f['caller']}: {round(f['rate'] * 100)}% {what}, against {round(f['others'] * 100)}% for everyone "
                 "else. Listen to their calls before rewriting the script.")
    sh = r["show_finding"]
    L.append("")
    if sh:
        L.append(f"Shows: {round(sh['near_rate'] * 100)}% when the interview is within 2 days of the call, "
                 f"{round(sh['far_rate'] * 100)}% when it is further out"
                 + (": offer slots in the next two days." if sh["separated"] else " (not clearly different)."))
    else:
        L.append("Shows: needs interview_at and showed, with at least 30 interviews within 2 days and 30 further out.")
    if r["limbo"]:
        L.append(f"In limbo: {r['limbo']} candidates never reached, called fewer than {r['max_attempts']} times, "
                 "nothing for a week. The stop rule is not being run.")
    if r["over_max"]:
        L.append(f"Called more than {r['max_attempts']} times: {r['over_max']} candidates.")
    L.append("")
    L.append("This reads the calls that were logged. It cannot hear them, or tell a script problem from a caller who "
             "does not use it.")
    return "\n".join(L)


def render_calls(r, path):
    e = html.escape
    rows = "".join(f"<tr><td>{e(b['band'])}</td><td>{b['n']}</td><td>{round(b['rate'] * 100)}%</td></tr>"
                   for b in r["speed"] if b["n"])
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Phone screen calls</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px}}pre{{white-space:pre-wrap;font-size:13px}}</style>
<h1>Phone screen calls</h1><table><tr><th>First call</th><th>Candidates</th><th>{e(r['measure'].title())}</th></tr>{rows}</table>
<pre>{e(text_calls(r))}</pre></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

def run_tests():
    import contextlib
    import copy
    import random
    import shutil
    import tempfile
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {name}" + (f"  [{detail}]" if detail != "" else ""))

    s = load_script(os.path.join(SAMPLE, "northline_script.json"))
    res = check_script(copy.deepcopy(s))
    check(f"sample script is ready ({res['blocking']})", res["ready"])
    check("sample script is under five minutes", res["seconds"] <= MAX_SECONDS, res["seconds"])
    broken = json.load(open(os.path.join(FIXTURES, "broken_scripts.json"), encoding="utf-8"))
    for case in broken["cases"]:
        p = copy.deepcopy(s)
        for op in case["ops"]:
            tgt = p
            path = op["path"]
            for k in path[:-1]:
                tgt = next(x for x in tgt if isinstance(x, dict) and x.get("id") == k) \
                    if isinstance(tgt, list) and isinstance(k, str) else tgt[k]
            last = path[-1]
            if isinstance(tgt, list) and isinstance(last, str):
                idx = next(i for i, x in enumerate(tgt) if isinstance(x, dict) and x.get("id") == last)
                if op["op"] == "del":
                    del tgt[idx]
                else:
                    tgt[idx] = op["value"]
            elif op["op"] == "set":
                tgt[last] = op["value"]
            elif op["op"] == "del":
                del tgt[last]
            elif op["op"] == "append":
                tgt[last].append(op["value"])
            elif op["op"] == "move":
                item = tgt.pop(last)
                tgt.insert(op["to"], item)
        try:
            r = check_script(p)
            ok = not r["ready"] and any(case["expect"].lower() in b.lower() for b in r["blocking"])
            check(f"broken script caught: {case['name']}", ok, r["blocking"] if not ok else "")
        except Refusal as exc:
            check(f"broken script refused: {case['name']}", case.get("refuse", False) and
                  case["expect"].lower() in str(exc).lower(), str(exc))

    # the call log, as planted
    exp = json.load(open(os.path.join(SAMPLE, "northline_calls_expected.json"), encoding="utf-8"))
    r = analyse_calls(read_calls(os.path.join(SAMPLE, "northline_calls.csv")), exp["max_attempts"])
    check("calls: speed matters, and is separated", r["speed_finding"] and r["speed_finding"]["separated"],
          r["speed_finding"])
    check("calls: best daypart as planted", r["best_daypart"] == exp["best_daypart"], r["best_daypart"])
    check("calls: the heavy, poor daypart as planted", r["heavy_poor_daypart"] == exp["heavy_poor_daypart"],
          r["heavy_poor_daypart"])
    check("calls: a text after voicemail brings more back", r["text_finding"] and r["text_finding"]["separated"],
          r["text_finding"])
    check("calls: the caller flags as planted", sorted((f["caller"], f["type"]) for f in r["caller_flags"])
          == sorted(tuple(x) for x in exp["caller_flags"]), r["caller_flags"])
    check("calls: near slots show better", r["show_finding"] and r["show_finding"]["separated"], r["show_finding"])
    check("calls: limbo counted as planted", r["limbo"] == exp["limbo"], r["limbo"])
    check("calls: over-calling counted as planted", r["over_max"] == exp["over_max"], r["over_max"])
    check("calls: text says it cannot hear the calls", "cannot hear" in text_calls(r))

    tmp = tempfile.mkdtemp(prefix="pss-")
    try:
        rows = list(csv.reader(open(os.path.join(SAMPLE, "northline_calls.csv"), encoding="utf-8")))
        hdr = rows[0]

        def write(name, rr):
            p = os.path.join(tmp, name)
            with open(p, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rr)
            return p
        # null world: shuffle outcomes across attempts, booked across candidates -> no separated findings
        rng = random.Random(5)
        oi, bi, si, ti = hdr.index("outcome"), hdr.index("booked"), hdr.index("showed"), hdr.index("texted")
        body = [list(x) for x in rows[1:]]
        outs = [x[oi] for x in body]
        rng.shuffle(outs)
        txt = [x[ti] for x in body]
        rng.shuffle(txt)
        for x, o, t in zip(body, outs, txt):
            x[oi], x[ti] = o, t
        cid = hdr.index("candidate_id")
        bk = {}
        for x in body:
            bk.setdefault(x[cid], x[bi])
        vals = list(bk.values())
        rng.shuffle(vals)
        newbk = dict(zip(bk, vals))
        for x in body:
            x[bi] = newbk[x[cid]]
        nr = analyse_calls(read_calls(write("null.csv", [hdr] + body)), exp["max_attempts"])
        check("null world: speed not called decisive", not (nr["speed_finding"] and nr["speed_finding"]["separated"]),
              nr["speed_finding"])
        check("null world: texting not called decisive", not (nr["text_finding"] and nr["text_finding"]["separated"]),
              nr["text_finding"])

        def refused(fn):
            try:
                fn()
                return False
            except Refusal:
                return True
        check("refuses a phone number in the log", refused(lambda: read_calls(write(
            "ph.csv", rows[:60] + [rows[60][:1] + ["(937) 555-0142"] + rows[60][2:]]))))
        check("refuses a name column", refused(lambda: read_calls(write("n.csv", [hdr + ["candidate_name"]] +
                                                                          [x + ["x"] for x in rows[1:]]))))
        check("refuses a call before the application", refused(lambda: read_calls(write(
            "b.csv", [hdr] + [[*x[:hdr.index("attempt_at")], "2020-01-01T09:00", *x[hdr.index("attempt_at") + 1:]]
                              for x in rows[1:3]] + rows[3:]))))
        check("refuses an unknown outcome", refused(lambda: read_calls(write(
            "u.csv", [hdr] + [[*x[:oi], "maybe", *x[oi + 1:]] for x in rows[1:2]] + rows[2:]))))
        check("refuses a thin log", refused(lambda: read_calls(write("t.csv", rows[:40]))))
        check("refuses a missing column", refused(lambda: read_calls(write(
            "m.csv", [[c for j, c in enumerate(x) if j != oi] for x in rows]))))
        thin = analyse_calls(read_calls(write("o.csv", [x[:5] for x in rows])), 3)
        check("no booked column: speed read against reached, and said", thin["measure"] == "reached" and
              "No 'booked' column" in text_calls(thin))
        check("no result column: caller section says it cannot be read", "cannot be read" in text_calls(thin) and
              not thin["caller_flags"])
        ai = hdr.index("attempt_at")
        off = analyse_calls(read_calls(write("z.csv", [hdr] + [[*x[:ai], x[ai] + "+02:00", *x[ai + 1:]]
                                                               for x in rows[1:]])), 3)
        check("offsets on times keep the wall-clock daypart", off["best_daypart"] == r["best_daypart"] and
              off["dayparts"] == r["dayparts"])
        check("reads dates that look like phone numbers as dates",
              read_calls(os.path.join(SAMPLE, "northline_calls.csv")) is not None)
        hp = os.path.join(tmp, "c.html")
        render_calls(r, hp)
        check("calls html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        sp = os.path.join(tmp, "s.html")
        render_script(s, sp)
        body_html = open(sp, encoding="utf-8").read()
        check("script html shows every question", all(html.escape(q["text"]) in body_html
                                                      for sec in s["sections"] for q in questions(sec)))
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: demo exits 0", main(["--demo"]) == 0)
            check("main: missing script exits 3", main(["--script", os.path.join(tmp, "x.json")]) == 3)
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
            s = load_script(os.path.join(SAMPLE, "northline_script.json"))
            print(text_script(check_script(s), s))
            print()
            print(text_calls(analyse_calls(read_calls(os.path.join(SAMPLE, "northline_calls.csv")), 3)))
            return 0
        if opt("--script"):
            s = load_script(opt("--script"))
            res = check_script(s)
            print(text_script(res, s))
            if opt("--html"):
                if res["ready"]:
                    render_script(s, opt("--html"))
                else:
                    print("No sheet written: fix the blocking items first.")
            return 0 if res["ready"] else 1
        if opt("--calls"):
            mx = opt("--max-attempts")
            try:
                mx = int(mx) if mx else 3
            except ValueError:
                raise Refusal("--max-attempts is a whole number.")
            if not 1 <= mx <= 10:
                raise Refusal("--max-attempts is between 1 and 10.")
            r = analyse_calls(read_calls(opt("--calls")), mx)
            print(text_calls(r))
            if opt("--html"):
                render_calls(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1, default=str)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except OSError as exc:
        print(f"REFUSED: could not read or write a file ({exc}).")
        return 3
    except Exception as exc:
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, not a finding "
              "about your calls.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
