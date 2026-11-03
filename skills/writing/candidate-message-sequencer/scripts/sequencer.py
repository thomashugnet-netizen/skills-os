#!/usr/bin/env python3
"""
Candidate message sequencer: checks a nudge sequence before anyone sends it,
and reads the send log once they have.

    python3 sequencer.py --check sequence.txt [--html review.html] [--json review.json]
    python3 sequencer.py --log sends.csv [--html report.html] [--json report.json]
    python3 sequencer.py --demo
    python3 sequencer.py --test

sequence.txt  a short header, then one block per message:

                  stage: applied, no screening call booked
                  channel: sms
                  stop_when: the candidate books a screening call
                  employer: Northline        (optional: the name you sign with)

                  [day 0, 10:00]
                  Hi {first_name}, it's {employer} ...

sends.csv     one row per message sent:
                  candidate_id, sequence, step, sent_at
                  [, channel, acted_at, opted_out_at]
              acted_at is when the candidate did what the sequence asks (its
              stop_when event); opted_out_at is when they opted out. Times in
              the candidate's local time, like 2026-10-01T10:00.

The check grades the sequence, not the message. Four polite messages sent in
thirty-six hours are not four polite messages; a sequence that never says what
stops it keeps texting somebody who booked yesterday. A per-message check sees
neither. The rules live in references/rubric.json.

The log shows what a template cannot: which message earns its place, whether
the stop condition is actually wired to the event, whether anybody is messaged
after opting out, and whether sends go out at night.

Exit codes: 0 sequence ready or log read, 1 sequence not ready, 2 no mode,
3 input refused, 4 the engine failed. Standard library only, no network, no
model judgement: the same input always gives the same findings.
"""

import csv
import datetime as dt
import difflib
import html
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
REF = os.path.join(SKILL_DIR, "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")

with open(os.path.join(REF, "rubric.json"), encoding="utf-8") as _f:
    RUBRIC = json.load(_f)

CHANNELS = list(RUBRIC["channel_limits"])
CADENCE = RUBRIC["cadence"]
BLOCKING = set(RUBRIC["blocking"])
LOGR = RUBRIC["log"]

BLOCK_RE = re.compile(r"^\[\s*day\s+(\d+)\s*,\s*(\d{1,2}):(\d{2})\s*\]\s*$", re.I | re.M)
HEADER_RE = re.compile(r"^([a-z_]+)\s*:\s*(.+)$", re.I)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}", re.I)
LINK_RE = re.compile(r"\{link\}", re.I)
URL_RE = re.compile(r"https?://\S+|\{link\}", re.I)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
SHOUT_RE = re.compile(r"\b[A-Z]{%d,}\b" % RUBRIC["shouting_min_run"])
SHOUT_OK = {"SMS", "ASAP", "HR", "PPE", "DOT", "STOP", "CDL", "OSHA", "HIPAA"}

# The GSM-7 alphabet an SMS is sent in when it can be. One character outside it
# switches the whole message to Unicode.
GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡"
           "ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")
GSM7_EXT = set("^{}\\[~]|€\f")
CHAR_NAMES = {"’": "a curly apostrophe", "‘": "a curly apostrophe", "“": "a curly quote", "”": "a curly quote",
              "—": "an em dash", "–": "an en dash", "…": "an ellipsis character", " ": "a non-breaking space",
              "•": "a bullet"}

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w-])(\+?\d[\d\s().-]{8,}\d)(?![\w-])")
DATEISH = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{1,2}(:\d{2}){0,2})?$|^\d{1,2}/\d{1,2}/\d{2,4}$")
NOMINATIVE = re.compile(r"(^|_)(first|last|full)?_?name($|_)|e-?mail|phone|mobile|address|street|zip|postcode|"
                        r"ssn|dob|birth|notes?$|comment", re.I)
BODY_COL = re.compile(r"^(body|text|content|message(_?(text|body|content))?|rendered\w*)$", re.I)
ALIASES = {"sequence": ("sequence", "sequence_id", "campaign"),
           "step": ("step", "message_number", "position")}


class Refusal(Exception):
    """The input cannot be read. Not a finding."""


def Finding(code, message, where=None):
    return {"code": code, "message": message, "message_index": where,
            "blocking": code in BLOCKING}


# ------------------------------------------------------------------ parsing

def parse(text):
    """Header lines, then [day N, HH:MM] blocks. Forgiving about blank lines,
    strict about the two things a sequence cannot be read without: a channel
    and at least one timestamp."""
    if not isinstance(text, str) or not text.strip():
        raise Refusal("The file is empty.")
    text = text.lstrip(chr(0xFEFF)).replace("\r\n", "\n")
    marks = list(BLOCK_RE.finditer(text))
    head = text[:marks[0].start()] if marks else text
    header = {}
    for line in head.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        found = HEADER_RE.match(line)
        if found:
            header[found.group(1).strip().lower()] = found.group(2).strip()
    if "from" in header and "employer" not in header:
        header["employer"] = header["from"]
    if not marks:
        raise Refusal("No messages found. Each message needs a line like `[day 0, 10:00]` saying when it is sent: "
                      "the timing is half of what this checks.")
    if len(marks) > 40:
        raise Refusal(f"{len(marks)} messages. This reads one sequence at a time.")
    messages = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.end():end].strip()
        day, hour, minute = int(mark.group(1)), int(mark.group(2)), int(mark.group(3))
        if hour > 23 or minute > 59:
            raise Refusal(f"Message {i + 1} has an impossible send time {hour:02d}:{minute:02d}.")
        if day > 365:
            raise Refusal(f"Message {i + 1} is sent on day {day}. A nudge sequence runs in days, not years.")
        messages.append({"index": i + 1, "day": day, "time": f"{hour:02d}:{minute:02d}",
                         "minutes": day * 1440 + hour * 60 + minute, "body": body})
    channel = (header.get("channel") or "").strip().lower()
    if channel not in CHANNELS:
        raise Refusal(f"`channel:` must be one of {', '.join(CHANNELS)}: the limits, the opt-out rule and the "
                      f"length cap depend on it. Found {header.get('channel')!r}.")
    return header, channel, messages


# --------------------------------------------------------------- primitives

def syllables(word):
    word = word.lower()
    count, prev = 0, False
    for ch in word:
        v = ch in "aeiouy"
        if v and not prev:
            count += 1
        prev = v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def sentences(text):
    parts = [p.strip() for p in SENTENCE_SPLIT.split(text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def reading_grade(text):
    """Flesch-Kincaid. Placeholders read as one short word, links as one."""
    clean = PLACEHOLDER_RE.sub("Sam", URL_RE.sub("link", text))
    words = WORD_RE.findall(clean)
    sents = sentences(clean)
    if not words or not sents:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return round(0.39 * (len(words) / len(sents)) + 11.8 * (syl / len(words)) - 15.59, 1)


def contains(text, phrases):
    """Whole-word matches, so 'text' is not found in 'context' or 'book' in
    'notebook'. Placeholders such as {text_number} are not words."""
    raw = text.lower().replace("’", "'")
    low = PLACEHOLDER_RE.sub(" ", raw)
    out = set()
    for p in phrases:
        if p.startswith("{"):
            if p in raw:
                out.add(p)
        elif re.search(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])", low):
            out.add(p)
    return sorted(out)


def actions_in(text):
    """The actions a message asks for. A verb right after 'to' is the purpose
    of another action ('Reply YES to confirm', 'Tap here to book'), or our own
    ('we need your documents to confirm it'), not a second thing to do."""
    low = PLACEHOLDER_RE.sub(" ", strip_boilerplate(text).lower().replace("’", "'"))
    return sorted({v for v in RUBRIC["action_verbs"]
                   if re.search(r"(?<![a-z0-9])(?<!\bto )" + re.escape(v) + r"(?![a-z0-9])", low)})


def filled(text):
    """Roughly what the phone receives: a link is a short link, a placeholder
    a typical value. Measuring the braces understates every real send."""
    return PLACEHOLDER_RE.sub("x" * RUBRIC["placeholder_chars"], LINK_RE.sub("x" * RUBRIC["link_chars"], text))


def sms_parts(text):
    t = filled(text)
    enc = RUBRIC["sms_encoding"]
    odd = sorted({c for c in t if c not in GSM7 and c not in GSM7_EXT})
    if odd:
        n = len(t.encode("utf-16-le")) // 2
        return "unicode", n, (1 if n <= enc["unicode_single"] else math.ceil(n / enc["unicode_part"])), odd
    n = sum(2 if c in GSM7_EXT else 1 for c in t)
    return "gsm", n, (1 if n <= enc["gsm_single"] else math.ceil(n / enc["gsm_part"])), []


def name_chars(chars):
    names = []
    for c in chars:
        nm = CHAR_NAMES.get(c) or ("an emoji" if EMOJI_RE.match(c) else f"'{c}'")
        if nm not in names:
            names.append(nm)
    return ", ".join(names[:3])


def strip_boilerplate(text):
    """Drop the opt-out clause before judging what a message says. It is
    required, identical everywhere, and read as content it becomes a second
    call to action and makes identical messages look different."""
    keep = [part for part in re.split(r"(?<=[.!?])\s+|\n+", text)
            if not contains(part, RUBRIC["opt_out_markers"])]
    return " ".join(keep).strip() or text.strip()


def similarity(a, b):
    def norm(s):
        return " ".join(PLACEHOLDER_RE.sub("", strip_boilerplate(s)).lower().split())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def in_quiet_hours(hhmm):
    return hhmm >= CADENCE["quiet_hours_start"] or hhmm < CADENCE["quiet_hours_end"]


# ----------------------------------------------------------------- the check

def check(text):
    header, channel, messages = parse(text)
    limits = RUBRIC["channel_limits"][channel]
    findings = []
    add = findings.append

    if not (header.get("stop_when") or "").strip():
        add(Finding("no_stop_condition",
                    "This sequence never says what stops it. Without a stop condition it keeps messaging people who "
                    "have already done the thing it asks for, the fastest way to make candidates opt out of hearing "
                    "from you at all. Add `stop_when:` naming the event that halts it."))
    if len(messages) > limits["max_messages"]:
        add(Finding("too_many_messages",
                    f"{len(messages)} messages on {channel}. The cap is {limits['max_messages']}. Past that, reply "
                    "rates fall and opt-outs rise: you are spending future contactability on someone who has decided."))
    ordered = sorted(messages, key=lambda m: m["minutes"])
    if [m["index"] for m in ordered] != [m["index"] for m in messages]:
        add(Finding("out_of_order", "The messages are not in send order. Put them in the order they go out, or the "
                    "cadence below measures something you did not mean."))
    for a, b in zip(ordered, ordered[1:]):
        hours = (b["minutes"] - a["minutes"]) / 60.0
        if hours < CADENCE["min_hours_between"]:
            add(Finding("too_fast",
                        f"Messages {a['index']} and {b['index']} are {hours:.0f} hours apart. Leave at least "
                        f"{CADENCE['min_hours_between']}: a second nudge before someone has had a working day to see "
                        "the first reads as pestering, and it is the same message to them.", b["index"]))
    if ordered:
        span = (ordered[-1]["minutes"] - ordered[0]["minutes"]) / 1440.0
        if span > CADENCE["max_window_days"]:
            add(Finding("window_too_long",
                        f"The sequence runs {span:.0f} days. Past {CADENCE['max_window_days']}, an hourly candidate "
                        "has taken another job and the message lands as a company that lost track of them."))
    for m in messages:
        if in_quiet_hours(m["time"]):
            add(Finding("quiet_hours",
                        f"Message {m['index']} sends at {m['time']}. Keep sends between {CADENCE['quiet_hours_end']} "
                        f"and {CADENCE['quiet_hours_start']}. Shift workers sleep when office workers do not: a 6am "
                        "text reaches somebody who worked until two.", m["index"]))
    for i, a in enumerate(messages):
        for b in messages[i + 1:]:
            if a["body"] and b["body"] and similarity(a["body"], b["body"]) >= RUBRIC["duplicate_similarity"]:
                add(Finding("duplicate_message",
                            f"Messages {a['index']} and {b['index']} say the same thing. Every message has to add "
                            "something (new information, a different action, a reason the timing changed) or it is "
                            "just volume.", b["index"]))
    opt_outs = [m["index"] for m in messages if contains(m["body"], RUBRIC["opt_out_markers"])]
    if limits["needs_opt_out"]:
        if not opt_outs:
            add(Finding("no_opt_out",
                        f"No message offers a way to stop. On {channel} that is a compliance problem in most places "
                        "and the reason people block the number instead. Put it on the first message."))
        elif opt_outs[0] != 1:
            add(Finding("opt_out_not_first",
                        f"The opt-out first appears on message {opt_outs[0]}. It belongs on the first one, the message "
                        "that arrives from a number they do not recognise."))
        if len(opt_outs) > 1:
            add(Finding("opt_out_repeated",
                        f"The opt-out appears on {len(opt_outs)} messages. Once is the requirement; on every message "
                        "it reads as a company that expects to annoy you, and spends characters you need for the ask."))

    ids = list(RUBRIC["identification_markers"])
    employer = (header.get("employer") or "").strip()
    for m in messages:
        body, idx = m["body"], m["index"]
        if not body:
            add(Finding("empty_message", f"Message {idx} has no text.", idx))
            continue
        if channel == "sms":
            enc, n, parts, odd = sms_parts(body)
            if enc == "unicode" and n > RUBRIC["sms_encoding"]["unicode_single"]:
                add(Finding("unicode_sms",
                            f"Message {idx} contains {name_chars(odd)}, which switches the whole text to Unicode: "
                            f"the limit drops from 160 to 70 characters, and at about {n} this goes as {parts} parts, "
                            "billed separately and sometimes arriving out of order. Use plain characters.", idx))
            elif enc == "gsm" and n > limits["chars"]:
                add(Finding("too_long",
                            f"Message {idx} is about {n} characters once the placeholders are filled, so it goes as "
                            f"{parts} parts. Over {limits['chars']} it is split, and the call to action is what falls "
                            "off the end.", idx))
        else:
            n = len(filled(body))
            if n > limits["chars"]:
                add(Finding("too_long",
                            f"Message {idx} is about {n} characters once the placeholders are filled; keep {channel} "
                            f"under {limits['chars']}. The ask has to be visible without scrolling.", idx))
        sensitive = contains(body, RUBRIC["sensitive_asks"])
        if sensitive:
            add(Finding("asks_for_sensitive_data",
                        f"Message {idx} asks for {', '.join(sensitive)}. Never collect that over a messaging channel: "
                        "it trains candidates to hand identity documents to whoever texts them, which is how "
                        "recruitment fraud works. Link to your own system and let them sign in.", idx))
        urgency = contains(body, RUBRIC["false_urgency"])
        if urgency:
            add(Finding("false_urgency",
                        f"Message {idx} uses {', '.join(urgency)}. If the deadline is real, give the date. If it is "
                        "not, this is a threat to somebody deciding whether to trust you as an employer.", idx))
        if not contains(body, ids) and not (employer and employer.lower() in body.lower()):
            add(Finding("unidentified",
                        f"Message {idx} never says who is writing. An unsigned text asking someone to tap a link is "
                        "indistinguishable from a scam, and increasingly gets treated as one.", idx))
        actions = actions_in(body)
        if not actions:
            add(Finding("no_call_to_action",
                        f"Message {idx} asks for nothing. Every message in a nudge sequence exists to make one "
                        "specific action easy.", idx))
        elif len(actions) > 2:
            add(Finding("competing_actions",
                        f"Message {idx} offers {len(actions)} different actions ({', '.join(actions[:4])}). Pick one: "
                        "three ways to respond is a decision, and a decision is what this candidate is not making.",
                        idx))
        grade = reading_grade(body)
        if grade > RUBRIC["reading_grade_max"]:
            add(Finding("reading_level",
                        f"Message {idx} reads at grade {grade}; keep it at or under {RUBRIC['reading_grade_max']}. It "
                        "is read on a phone, often in a second language, often between shifts.", idx))
        for s in sentences(body):
            if len(WORD_RE.findall(s)) > RUBRIC["long_sentence_words"]:
                add(Finding("long_sentence",
                            f"Message {idx} has a sentence over {RUBRIC['long_sentence_words']} words. Split it.", idx))
                break
        if body.count("!") > RUBRIC["max_exclamations_per_message"]:
            add(Finding("over_punctuated",
                        f"Message {idx} has {body.count('!')} exclamation marks. Enthusiasm is not what stands "
                        "between this candidate and a shift.", idx))
        emoji = EMOJI_RE.findall(body)
        if len(emoji) > RUBRIC["max_emoji_per_message"]:
            add(Finding("emoji_heavy", f"Message {idx} carries {len(emoji)} emoji.", idx))
        shouted = [w for w in SHOUT_RE.findall(PLACEHOLDER_RE.sub(" ", body)) if w not in SHOUT_OK]
        if shouted:
            add(Finding("shouting", f"Message {idx} shouts: {', '.join(shouted[:3])}.", idx))

    codes = {f["code"] for f in findings}
    return {"channel": channel, "stage": header.get("stage", ""), "stop_when": header.get("stop_when", ""),
            "messages": len(messages),
            "window_days": round((ordered[-1]["minutes"] - ordered[0]["minutes"]) / 1440.0, 1) if ordered else 0,
            "findings": findings, "ready_to_send": not (codes & BLOCKING),
            "blocking": sorted(codes & BLOCKING), "advice": sorted(codes - BLOCKING),
            "sequence": [{k: m[k] for k in ("index", "day", "time", "body")} for m in messages]}


def report_text(r):
    lines = [f"{r['channel']} sequence: {r['messages']} message(s) over {r['window_days']:g} days"]
    if r["stage"]:
        lines.append(f"stage: {r['stage']}")
    lines.append(f"stops when: {r['stop_when'] or 'NOT SET'}")
    lines.append("")
    if not r["findings"]:
        lines.append("No findings.")
    for f in sorted(r["findings"], key=lambda f: not f["blocking"]):
        where = f" (message {f['message_index']})" if f["message_index"] else ""
        lines.append(f"{'BLOCKS' if f['blocking'] else 'advice'} [{f['code']}]{where} {f['message']}")
    lines.append("")
    lines.append("READY TO SEND" if r["ready_to_send"] else "NOT READY: " + ", ".join(r["blocking"]))
    return "\n".join(lines)


def render_check(r, path):
    e = html.escape
    by = {}
    for f in r["findings"]:
        by.setdefault(f["message_index"], []).append(f)
    msgs = "".join(
        f"<section><h2>Message {m['index']}: day {m['day']}, {e(m['time'])}</h2><p class=msg>{e(m['body'])}</p>"
        + "".join(f"<p class={'b' if f['blocking'] else 'a'}>{e(f['message'])}</p>" for f in by.get(m["index"], []))
        + "</section>" for m in r["sequence"])
    top = "".join(f"<p class={'b' if f['blocking'] else 'a'}>{e(f['message'])}</p>" for f in by.get(None, []))
    verdict = "Ready to send" if r["ready_to_send"] else "Not ready: " + ", ".join(r["blocking"])
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Sequence review</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#111}}
.msg{{white-space:pre-wrap;background:#f3f3f3;padding:10px;border-radius:8px}}.b{{color:#a00}}.a{{color:#555}}
section{{border-top:1px solid #ccc}}h2{{font-size:15px}}</style>
<h1>{e(r['channel'].upper())} sequence</h1><p>{e(r['stage'])}<br>Stops when: {e(r['stop_when'] or 'NOT SET')}</p>
<p><b>{e(verdict)}</b></p>{top}{msgs}</html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ the send log

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
        # the candidate's wall-clock time is what decides night or day, so an offset is dropped, not converted
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


def read_log(path):
    if not os.path.exists(path):
        raise Refusal(f"log: file not found ({path}).")
    raw = open(path, "rb").read()
    text = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
    if EMAIL.search(text):
        raise Refusal("log: the file contains an email address. Export with opaque candidate ids only.")
    if has_phone(text):
        raise Refusal("log: the file contains what looks like a phone number. Export with opaque candidate ids, never "
                      "the number messaged.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        raise Refusal("log: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    for h in header:
        if BODY_COL.match(h):
            raise Refusal(f"log: column '{h}' looks like the message text. Sent messages carry first names: export "
                          "without it, the step number is enough.")
        if NOMINATIVE.search(h):
            raise Refusal(f"log: column '{h}' looks like personal information. Opaque ids only.")
    col = {}
    for want in ("candidate_id", "sequence", "step", "sent_at"):
        names = ALIASES.get(want, (want,))
        hit = next((h for h in names if h in header), None)
        if not hit:
            raise Refusal(f"log: missing column '{want}'" + (f" (or {', '.join(names[1:])})" if len(names) > 1 else "")
                          + ".")
        col[want] = header.index(hit)
    for opt in ("channel", "acted_at", "opted_out_at"):
        if opt in header:
            col[opt] = header.index(opt)
    out = []
    for n, r in enumerate(rows[1:], 2):
        def cell(k):
            i = col.get(k)
            return r[i].strip() if i is not None and i < len(r) else ""
        cid, seq = cell("candidate_id"), cell("sequence")
        if not cid or not seq:
            raise Refusal(f"log row {n}: candidate_id and sequence cannot be empty.")
        if not re.fullmatch(r"\d{1,3}(\.0+)?", cell("step")):
            raise Refusal(f"log row {n}: step '{cell('step')}' is not a message number.")
        step = int(float(cell("step")))
        if not 1 <= step <= 20:
            raise Refusal(f"log row {n}: step {step} is outside 1 to 20.")
        at = when(cell("sent_at"))
        if at in (None, "bad"):
            raise Refusal(f"log row {n}: sent_at must be a date-time like 2026-10-01T10:00.")
        acted, opted = when(cell("acted_at")), when(cell("opted_out_at"))
        if "bad" in (acted, opted):
            raise Refusal(f"log row {n}: acted_at and opted_out_at must be date-times or empty.")
        if any(t and not 2000 <= t.year <= 2100 for t in (at, acted, opted)):
            raise Refusal(f"log row {n}: a date outside 2000 to 2100. Check the export's date format.")
        ch = cell("channel").lower()
        if ch and ch not in CHANNELS:
            raise Refusal(f"log row {n}: channel '{ch}' should be {', '.join(CHANNELS)}.")
        out.append({"cand": cid, "seq": seq, "step": step, "at": at, "channel": ch, "acted": acted, "opted": opted})
    if len({x["cand"] for x in out}) < LOGR["min_candidates"]:
        raise Refusal(f"log: fewer than {LOGR['min_candidates']} candidates. Too few to read.")
    return {"rows": out, "has_acted": "acted_at" in col, "has_opted": "opted_out_at" in col,
            "has_channel": "channel" in col}


def analyse_log(log):
    rows = log["rows"]
    window = dt.timedelta(days=LOGR["act_window_days"])
    grace = dt.timedelta(minutes=LOGR["leak_grace_minutes"])
    times = [x["at"] for x in rows] + [x[k] for x in rows for k in ("acted", "opted") if x[k]]
    as_of = max(times)
    seqs = {}
    for x in rows:
        seqs.setdefault(x["seq"], {}).setdefault(x["cand"], []).append(x)
    out = []
    for name in sorted(seqs):
        cands = seqs[name]
        sends = [x for v in cands.values() for x in v]
        chans = [x["channel"] for x in sends if x["channel"]]
        channel = max(set(chans), key=chans.count) if chans else ""
        cap = RUBRIC["channel_limits"][channel or "sms"]["max_messages"]
        steps, leaked, acted_n, after_opt, fast, over, quiet = {}, 0, 0, 0, 0, 0, 0
        acted_total = opted_total = 0
        for cid, ss in cands.items():
            ss.sort(key=lambda x: (x["at"], x["step"]))
            acted = min((x["acted"] for x in ss if x["acted"]), default=None)
            opted = min((x["opted"] for x in ss if x["opted"]), default=None)
            acted_total += 1 if acted else 0
            opted_total += 1 if opted else 0
            if acted:
                acted_n += 1
                leaked += 1 if any(x["at"] > acted + grace for x in ss) else 0
            if opted:
                after_opt += sum(1 for x in ss if x["at"] > opted)
            fast += sum(1 for a, b in zip(ss, ss[1:])
                        if (b["at"] - a["at"]).total_seconds() / 3600 < CADENCE["min_hours_between"])
            over += 1 if len(ss) > cap else 0
            quiet += sum(1 for x in ss if in_quiet_hours(x["at"].strftime("%H:%M")))
            for i, x in enumerate(ss):
                if (acted and acted <= x["at"]) or (opted and opted <= x["at"]):
                    continue                      # not at risk: they had already acted or left
                last = i + 1 >= len(ss)
                end = x["at"] + window if last else ss[i + 1]["at"]
                first = min([t for t in (acted, opted) if t and x["at"] <= t < end], default=None)
                if last and first is None and as_of < x["at"] + window:
                    continue                      # still inside its window: too early to say
                d = steps.setdefault(x["step"], [0, 0, 0])
                d[0] += 1
                if first is not None and first == acted:
                    d[1] += 1
                elif first is not None:
                    d[2] += 1
        table, flagged = [], []
        for k in sorted(steps):
            n, a, o = steps[k]
            alo, ahi = wilson(a, n)
            olo, ohi = wilson(o, n)
            row = {"step": k, "sent_to": n, "acted": a, "opted": o,
                   "act_rate": round(a / n, 3) if n else None, "act_ci90": [round(alo, 3), round(ahi, 3)],
                   "opt_rate": round(o / n, 3) if n else None, "opt_ci90": [round(olo, 3), round(ohi, 3)]}
            if log["has_acted"] and log["has_opted"] and n >= LOGR["min_candidates_per_step"] and olo > ahi:
                row["costs_more_than_it_earns"] = True
                flagged.append(k)
            table.append(row)
        total_acts = sum(r["acted"] for r in table)
        for r in table:
            r["share_of_actions"] = round(r["acted"] / total_acts, 3) if total_acts else None
        llo, _ = wilson(leaked, acted_n)
        s = {"sequence": name, "channel": channel or "unknown", "cap": cap, "candidates": len(cands),
             "sends": len(sends), "enough": len(cands) >= LOGR["min_candidates_per_sequence"],
             "acted_share": round(acted_total / len(cands), 3), "opted_share": round(opted_total / len(cands), 3),
             "steps": table, "flagged_steps": flagged,
             "leaked": leaked if log["has_acted"] else None, "acted": acted_n,
             "leaky": bool(log["has_acted"] and acted_n >= 20 and llo >= LOGR["leak_flag_lower"]),
             "after_opt_out": after_opt if log["has_opted"] else None,
             "too_fast": fast, "over_cap": over, "quiet_sends": quiet,
             "quiet": len(sends) >= 30 and quiet / len(sends) >= LOGR["quiet_flag_share"]}
        out.append(s)
    return {"as_of": as_of.isoformat(timespec="minutes"), "candidates": len({x["cand"] for x in rows}),
            "sends": len(rows), "has_acted": log["has_acted"], "has_opted": log["has_opted"],
            "has_channel": log["has_channel"], "sequences": out,
            "flagged_steps": [[s["sequence"], k] for s in out if s["enough"] for k in s["flagged_steps"]],
            "leaky": [s["sequence"] for s in out if s["leaky"]],
            "after_opt_out": {s["sequence"]: s["after_opt_out"] for s in out if s["after_opt_out"]},
            "quiet": [s["sequence"] for s in out if s["quiet"]],
            "too_fast": {s["sequence"]: s["too_fast"] for s in out if s["too_fast"]},
            "over_cap": {s["sequence"]: s["over_cap"] for s in out if s["over_cap"]}}


def pct(x):
    return f"{round(x * 100)}%"


def log_text(r):
    L = [f"Send log: {r['candidates']:,} candidates, {r['sends']:,} messages, {len(r['sequences'])} sequence(s), "
         f"as of {r['as_of']}."]
    if not r["has_acted"]:
        L.append("No 'acted_at' column: which message earns its place, and whether the stop condition works, cannot "
                 "be read. Add when each candidate did what the sequence asks.")
    if not r["has_opted"]:
        L.append("No 'opted_out_at' column: opt-outs, and messages sent after one, cannot be read.")
    if not r["has_channel"]:
        L.append("No 'channel' column: the message cap is taken as 4 (SMS).")
    for s in r["sequences"]:
        L.append("")
        L.append(f"{s['sequence']} ({s['channel']}, {s['candidates']:,} candidates, {s['sends']:,} messages)"
                 + (f": {pct(s['acted_share'])} did what it asks, {pct(s['opted_share'])} opted out."
                    if r["has_acted"] and r["has_opted"] else "."))
        if not s["enough"]:
            L.append(f"  Fewer than {LOGR['min_candidates_per_sequence']} candidates: counted, not compared.")
        if s["after_opt_out"]:
            L.append(f"  {s['after_opt_out']} message(s) went to people who had already opted out. Fix this before "
                     "anything else: it is the complaint that ends a sending number, and in most places a breach.")
        if r["has_acted"] and s["enough"]:
            L.append(f"  {'Message':<8} {'Sent to':>7}   {'Acted after it':<18} {'Opted out after it':<18}")
            for t in s["steps"]:
                if t["sent_to"] < 5:
                    continue
                act = f"{pct(t['act_rate']):>4} ({pct(t['act_ci90'][0])}-{pct(t['act_ci90'][1])})"
                opt = (f"{pct(t['opt_rate']):>4} ({pct(t['opt_ci90'][0])}-{pct(t['opt_ci90'][1])})"
                       if r["has_opted"] else "n/a")
                few = "   too few to compare" if t["sent_to"] < LOGR["min_candidates_per_step"] else ""
                L.append(f"  {t['step']:<8} {t['sent_to']:>7}   {act:<18} {opt:<18}{few}".rstrip())
            for k in s["flagged_steps"]:
                t = next(x for x in s["steps"] if x["step"] == k)
                L.append(f"  Message {k} loses more people than it moves: {pct(t['opt_rate'])} opt out after it, "
                         f"{pct(t['act_rate'])} act. Cut it, or make it say something the others did not.")
            first = next((t for t in s["steps"] if t["share_of_actions"] is not None), None)
            if first and first["share_of_actions"] is not None:
                L.append(f"  Message {first['step']} brings {pct(first['share_of_actions'])} of all the actions this "
                         "sequence gets: its wording matters most.")
        if s["leaky"]:
            L.append(f"  {pct(s['leaked'] / s['acted'])} of the people who did it kept getting messages "
                     f"({s['leaked']} of {s['acted']}). The stop condition is not wired to the system where they act.")
        if s["quiet"]:
            L.append(f"  {pct(s['quiet_sends'] / s['sends'])} of its messages go out between "
                     f"{CADENCE['quiet_hours_start']} and {CADENCE['quiet_hours_end']}, candidate's time.")
        if s["too_fast"]:
            L.append(f"  {s['too_fast']} time(s) two messages went to the same person less than "
                     f"{CADENCE['min_hours_between']} hours apart.")
        if s["over_cap"]:
            L.append(f"  {s['over_cap']} candidate(s) got more than {s['cap']} messages: something re-enrols them.")
    L.append("")
    L.append("This reads messages that were sent. It cannot see what they said, or why anyone acted: a candidate who "
             "books after message 3 may have been about to book anyway.")
    return "\n".join(L)


def render_log(r, path):
    e = html.escape
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Send log</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px}}
pre{{white-space:pre-wrap;font-size:13px}}</style><h1>Send log</h1><pre>{e(log_text(r))}</pre></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# --------------------------------------------------------------- test suite

# Every fixture either passes or fails for a named reason, and declares what
# must NOT be found in it. A checker that flags everything is as useless as one
# that flags nothing, and only the must_not sets notice the difference.
EXPECTED = [
    ("good_sms.txt", set(), {"no_stop_condition", "too_many_messages", "too_fast", "quiet_hours", "no_opt_out",
                             "opt_out_not_first", "opt_out_repeated", "too_long", "unicode_sms", "duplicate_message",
                             "unidentified", "no_call_to_action", "asks_for_sensitive_data", "false_urgency",
                             "reading_level", "competing_actions", "shouting", "over_punctuated"}, True),
    ("good_email.txt", set(), {"no_stop_condition", "too_many_messages", "too_fast", "quiet_hours", "no_opt_out",
                               "too_long", "duplicate_message", "unidentified", "no_call_to_action", "reading_level",
                               "false_urgency"}, True),
    ("too_many.txt", {"too_many_messages"}, {"quiet_hours", "too_fast", "no_opt_out"}, False),
    ("too_fast.txt", {"too_fast"}, {"too_many_messages", "quiet_hours", "no_opt_out"}, False),
    ("quiet_hours.txt", {"quiet_hours"}, {"too_many_messages", "too_fast", "no_opt_out"}, False),
    ("no_optout.txt", {"no_opt_out"}, {"too_many_messages", "quiet_hours", "opt_out_repeated", "unidentified"}, False),
    ("optout_every_time.txt", {"opt_out_repeated"}, {"no_opt_out", "opt_out_not_first", "too_many_messages",
                                                     "quiet_hours", "unicode_sms"}, True),
    ("sensitive_data.txt", {"asks_for_sensitive_data"}, {"too_many_messages", "quiet_hours"}, False),
    ("false_urgency.txt", {"false_urgency"}, {"too_many_messages", "quiet_hours", "no_opt_out"}, False),
    ("duplicate.txt", {"duplicate_message"}, {"too_many_messages", "quiet_hours", "no_opt_out"}, False),
    ("no_stop_condition.txt", {"no_stop_condition"}, {"too_many_messages", "quiet_hours", "no_opt_out",
                                                      "unidentified"}, False),
    ("unidentified.txt", {"unidentified"}, {"no_opt_out", "too_many_messages", "no_call_to_action"}, False),
    ("sms_too_long.txt", {"too_long"}, {"no_opt_out", "unidentified", "no_call_to_action", "unicode_sms"}, False),
    ("shouting_and_hype.txt", {"shouting", "over_punctuated", "false_urgency"}, {"no_opt_out", "unidentified"}, False),
    ("unicode_sms.txt", {"unicode_sms"}, {"too_long", "no_opt_out", "unidentified", "too_fast"}, False),
    ("words_not_substrings.txt", set(), {"competing_actions", "no_call_to_action", "asks_for_sensitive_data",
                                         "unidentified"}, True),
    ("signed_by_name.txt", set(), {"unidentified", "no_opt_out", "too_long"}, True),
    ("window_too_long.txt", {"window_too_long"}, {"too_fast", "too_many_messages", "no_opt_out"}, False),
    ("out_of_order.txt", {"out_of_order"}, {"too_many_messages", "no_opt_out"}, False),
    ("opt_out_late.txt", {"opt_out_not_first"}, {"no_opt_out", "opt_out_repeated"}, False),
    ("empty_message.txt", {"empty_message"}, {"no_opt_out", "unidentified"}, False),
]


def load_generator():
    import importlib.util
    spec = importlib.util.spec_from_file_location("generate_log", os.path.join(SAMPLE, "generate_log.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_tests():
    import contextlib
    import shutil
    import tempfile
    passed = failed = 0

    def ok(name, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {name}" + (f"  [{detail}]" if detail != "" else ""))

    for name, must, must_not, ready in EXPECTED:
        path = os.path.join(FIXTURES, name)
        try:
            r = check(open(path, encoding="utf-8").read())
        except (OSError, Refusal) as exc:
            ok(f"fixture {name}", False, exc)
            continue
        codes = {f["code"] for f in r["findings"]}
        ok(f"fixture {name}: finds {sorted(must)}", must <= codes, sorted(codes))
        ok(f"fixture {name}: does not invent", not (must_not & codes), sorted(must_not & codes))
        ok(f"fixture {name}: ready_to_send {ready}", r["ready_to_send"] == ready, r["blocking"])
    for label, text in (("no timestamps", "channel: sms\nstop_when: x\n\nHi there, book a call."),
                        ("unknown channel", "channel: pigeon\nstop_when: x\n\n[day 0, 10:00]\nHi."),
                        ("no channel", "stop_when: x\n\n[day 0, 10:00]\nHi."),
                        ("impossible time", "channel: sms\nstop_when: x\n\n[day 0, 99:00]\nHi."),
                        ("day in years", "channel: sms\nstop_when: x\n\n[day 4000, 10:00]\nHi."),
                        ("empty file", "   \n")):
        try:
            check(text)
            ok(f"refuses {label}", False, "it ran")
        except Refusal:
            ok(f"refuses {label}", True)
    sample = os.path.join(SAMPLE, "northline_applied_sms.txt")
    r = check(open(sample, encoding="utf-8").read())
    ok("sample sequence is ready, with no advice either", r["ready_to_send"] and not r["findings"], r["findings"])
    ok("sms parts: 160 plain characters is one part", sms_parts("a" * 160)[2] == 1)
    ok("sms parts: 161 plain characters is two", sms_parts("a" * 161)[2] == 2)
    ok("sms parts: one curly apostrophe makes 71 characters two parts", sms_parts("’" + "a" * 70)[:3] ==
       ("unicode", 71, 2))
    ok("sms parts: the euro sign counts twice and stays plain", sms_parts("€")[:2] == ("gsm", 2))
    ok("contains: 'text' is not found in 'context'", not contains("context", ["text"]))
    ok("contains: placeholders are not words", not contains("call {text_number}", ["text"]))
    ok("actions: 'Reply YES to confirm' is one action", actions_in("Reply YES to confirm.") == ["reply"])
    ok("actions: our own 'to confirm it' is not the candidate's", actions_in(
        "We need your documents to confirm it. Upload them here: {link}") == ["upload"])
    ok("actions: the opt-out is not an action", actions_in("Book here: {link}. Reply STOP to opt out.") == ["book"])

    # the send log, as planted
    exp = json.load(open(os.path.join(SAMPLE, "northline_sends_expected.json"), encoding="utf-8"))
    lr = analyse_log(read_log(os.path.join(SAMPLE, "northline_sends.csv")))
    ok("log: the step that costs more than it earns", lr["flagged_steps"] == exp["flagged_steps"], lr["flagged_steps"])
    ok("log: the leaky sequence", lr["leaky"] == exp["leaky"], lr["leaky"])
    ok("log: messages after an opt-out", lr["after_opt_out"] == exp["after_opt_out"], lr["after_opt_out"])
    ok("log: the sequence that sends at night", lr["quiet"] == exp["quiet"], lr["quiet"])
    ok("log: too-fast sends", lr["too_fast"] == exp["too_fast"], lr["too_fast"])
    ok("log: over the cap", lr["over_cap"] == exp["over_cap"], lr["over_cap"])
    ok("log: candidates counted", lr["candidates"] == exp["candidates"], lr["candidates"])
    ok("log: text says it cannot see why anyone acted", "cannot see what they said" in log_text(lr))

    gen = load_generator()
    tmp = tempfile.mkdtemp(prefix="cms-")
    try:
        def write(name, rows):
            p = os.path.join(tmp, name)
            with open(p, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rows)
            return p
        null_rows, _ = gen.simulate(plants=False)
        nr = analyse_log(read_log(write("null.csv", null_rows)))
        ok("null world: no step called costly", not nr["flagged_steps"], nr["flagged_steps"])
        ok("null world: no leaky sequence (sync lag inside the grace is not a leak)", not nr["leaky"], nr["leaky"])
        ok("null world: nothing after an opt-out, nothing at night, nothing too fast, nobody over the cap",
           not (nr["after_opt_out"] or nr["quiet"] or nr["too_fast"] or nr["over_cap"]), nr)
        rows = list(csv.reader(open(os.path.join(SAMPLE, "northline_sends.csv"), encoding="utf-8")))
        hdr = rows[0]
        thin = analyse_log(read_log(write("o.csv", [[c for j, c in enumerate(x) if hdr[j] in
                                                     ("candidate_id", "sequence", "step", "sent_at")] for x in rows])))
        t = log_text(thin)
        ok("no acted_at or opted_out_at: says what cannot be read, flags nothing it cannot see",
           "No 'acted_at'" in t and "No 'opted_out_at'" in t and not thin["flagged_steps"] and not thin["leaky"])

        def refused(fn):
            try:
                fn()
                return False
            except Refusal:
                return True
        ci, si = hdr.index("candidate_id"), hdr.index("sent_at")
        ok("refuses a phone number", refused(lambda: read_log(write(
            "p.csv", rows[:80] + [[*rows[80][:ci], "+1 937 555 0142", *rows[80][ci + 1:]]] + rows[81:]))))
        ok("refuses an email address", refused(lambda: read_log(write(
            "e.csv", rows[:80] + [[*rows[80][:ci], "sam@example.com", *rows[80][ci + 1:]]] + rows[81:]))))
        ok("refuses a name column", refused(lambda: read_log(write("n.csv", [hdr + ["first_name"]] +
                                                                    [x + ["x"] for x in rows[1:]]))))
        ok("refuses the message text", refused(lambda: read_log(write("b.csv", [hdr + ["message_text"]] +
                                                                       [x + ["hi"] for x in rows[1:]]))))
        ok("refuses a bad step", refused(lambda: read_log(write(
            "s.csv", [hdr] + [[*x[:hdr.index("step")], "two", *x[hdr.index("step") + 1:]] for x in rows[1:3]]
            + rows[3:]))))
        ok("refuses a bad time", refused(lambda: read_log(write(
            "t.csv", [hdr] + [[*x[:si], "yesterday", *x[si + 1:]] for x in rows[1:3]] + rows[3:]))))
        ok("refuses an infinite step", refused(lambda: read_log(write(
            "i.csv", [hdr] + [[*x[:hdr.index("step")], "inf", *x[hdr.index("step") + 1:]] for x in rows[1:3]]
            + rows[3:]))))
        ok("refuses a year 9999", refused(lambda: read_log(write(
            "y.csv", [hdr] + [[*x[:si], "9999-12-31T23:59", *x[si + 1:]] for x in rows[1:3]] + rows[3:]))))
        ok("refuses a missing column", refused(lambda: read_log(write(
            "m.csv", [[c for j, c in enumerate(x) if j != si] for x in rows]))))
        ok("refuses a thin log", refused(lambda: read_log(write("th.csv", rows[:30]))))
        ok("reads aliases: campaign and message_number", not refused(lambda: read_log(write(
            "a.csv", [[{"sequence": "campaign", "step": "message_number"}.get(h, h) for h in hdr]] + rows[1:]))))
        off = analyse_log(read_log(write("z.csv", [hdr] + [[*x[:si], x[si] + "-05:00", *x[si + 1:]]
                                                           for x in rows[1:]])))
        ok("offsets keep the candidate's wall-clock time", off["quiet"] == lr["quiet"], off["quiet"])
        hp = os.path.join(tmp, "r.html")
        render_log(lr, hp)
        ok("log html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        render_check(r, hp)
        body = open(hp, encoding="utf-8").read()
        ok("review html shows every message", all(html.escape(m["body"]) in body for m in r["sequence"]))
        with contextlib.redirect_stdout(io.StringIO()):
            ok("main: no mode exits 2", main([]) == 2)
            ok("main: demo exits 0", main(["--demo"]) == 0)
            ok("main: a ready sequence exits 0", main(["--check", sample]) == 0)
            ok("main: a blocked sequence exits 1", main(["--check", os.path.join(FIXTURES, "too_fast.txt")]) == 1)
            ok("main: the old --input still works", main(["--input", sample]) == 0)
            ok("main: a missing file exits 3", main(["--check", os.path.join(tmp, "x.txt")]) == 3)
            ok("main: an unreadable sequence exits 3", main(["--check", write("u.txt", [["channel: fax"]])]) == 3)
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
            print(report_text(check(open(os.path.join(SAMPLE, "northline_applied_sms.txt"), encoding="utf-8").read())))
            print()
            print(log_text(analyse_log(read_log(os.path.join(SAMPLE, "northline_sends.csv")))))
            return 0
        path = opt("--check") or opt("--input")
        if path:
            try:
                text = open(path, encoding="utf-8-sig").read()
            except UnicodeDecodeError:
                raise Refusal("the sequence is not a UTF-8 text file.")
            r = check(text)
            print(report_text(r))
            if opt("--html"):
                render_check(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            return 0 if r["ready_to_send"] else 1
        if opt("--log"):
            r = analyse_log(read_log(opt("--log")))
            print(log_text(r))
            if opt("--html"):
                render_log(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except OSError as exc:
        print(f"REFUSED: could not read or write a file ({exc}).")
        return 3
    except Exception as exc:
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, not a finding "
              "about your messages.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
