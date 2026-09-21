#!/usr/bin/env python3
"""
Candidate message sequence checker.

Grades a nudge sequence written for applicants who have stalled somewhere
between applying and their first shift. Standard library only - no network,
no model judgement. The same sequence always produces the same findings.

    check_sequence.py --input sequence.txt
    check_sequence.py --test

Why a checker and not a promise: anyone can claim their nudge sequence is
respectful. The rules below are the claim, written down and enforced, so the
skill can be checked instead of trusted.

The important rules are the ones that only exist at the level of the whole
sequence. Four individually polite messages sent in thirty-six hours are not
four polite messages, they are harassment; a sequence with no stop condition
keeps texting somebody who already booked. A per-message checker cannot see
any of that.

Input format - a short header, then one block per message:

    stage: applied, no screen booked
    channel: sms
    stop_when: the candidate books a screening call

    [day 0, 10:00]
    Hi {first_name}, it's {employer} ...

    [day 2, 09:30]
    ...
"""

import argparse
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
RUBRIC_PATH = os.path.join(SKILL_DIR, "references", "rubric.json")
FIXTURES = os.path.join(SKILL_DIR, "references", "fixtures")

with open(RUBRIC_PATH, encoding="utf-8") as _f:
    RUBRIC = json.load(_f)

CHANNELS = list(RUBRIC["channel_limits"])
CADENCE = RUBRIC["cadence"]

BLOCK_RE = re.compile(r"^\[\s*day\s+(\d+)\s*,\s*(\d{1,2}):(\d{2})\s*\]\s*$", re.I | re.M)
HEADER_RE = re.compile(r"^([a-z_]+)\s*:\s*(.+)$", re.I)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’-]*")
SENTENCE_SPLIT = re.compile(r"[.!?]+(?:\s|$)")
PLACEHOLDER_RE = re.compile(r"\{[a-z_]+\}", re.I)
URL_RE = re.compile(r"https?://\S+|\{link\}", re.I)
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]")
SHOUT_RE = re.compile(r"\b[A-Z]{%d,}\b" % RUBRIC["shouting_min_run"])


class Finding(dict):
    def __init__(self, code, message, where=None):
        super().__init__(code=code, message=message, message_index=where)


class Unparseable(Exception):
    """The input is not a sequence this checker can read. Not a finding."""


# ------------------------------------------------------------------ parsing

def parse(text):
    """Header lines, then [day N, HH:MM] blocks. Deliberately forgiving about
    blank lines and order, and deliberately strict about the two things a
    sequence cannot be read without: a channel and at least one timestamp."""
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

    if not marks:
        raise Unparseable(
            "No messages found. Each message needs a header line like "
            "`[day 0, 10:00]` saying when it is sent - the timing is half of "
            "what this checker looks at.")

    messages = []
    for i, mark in enumerate(marks):
        body_end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[mark.end():body_end].strip()
        hour, minute = int(mark.group(2)), int(mark.group(3))
        if hour > 23 or minute > 59:
            raise Unparseable(f"Message {i + 1} has an impossible send time "
                              f"{hour:02d}:{minute:02d}.")
        messages.append({
            "index": i + 1,
            "day": int(mark.group(1)),
            "time": f"{hour:02d}:{minute:02d}",
            "minutes": int(mark.group(1)) * 1440 + hour * 60 + minute,
            "body": body,
        })

    channel = (header.get("channel") or "").strip().lower()
    if channel not in CHANNELS:
        raise Unparseable(
            f"`channel:` must be one of {', '.join(CHANNELS)} - the limits, the "
            f"opt-out rule and the length cap all depend on it. Found "
            f"{header.get('channel')!r}.")
    return header, channel, messages


# --------------------------------------------------------------- primitives

def syllables(word):
    word = word.lower()
    vowels, count, prev = "aeiouy", 0, False
    for ch in word:
        is_v = ch in vowels
        if is_v and not prev:
            count += 1
        prev = is_v
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def sentences(text):
    parts = [p.strip() for p in SENTENCE_SPLIT.split(text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


def reading_grade(text):
    """Flesch-Kincaid. Placeholders are stripped first: {first_name} is one
    short word to the reader, not a polysyllabic token."""
    clean = PLACEHOLDER_RE.sub("Sam", URL_RE.sub("link", text))
    words = WORD_RE.findall(clean)
    sents = sentences(clean)
    if not words or not sents:
        return 0.0
    syl = sum(syllables(w) for w in words)
    return round(0.39 * (len(words) / len(sents)) + 11.8 * (syl / len(words)) - 15.59, 1)


def contains(text, phrases):
    low = text.lower()
    return sorted({p for p in phrases if p in low})


def visible_length(text):
    """What the recipient's phone counts. Placeholders stand in for real
    values, so measuring the template understates a real send; a generous
    fixed width per placeholder is closer to the truth than the braces."""
    return len(PLACEHOLDER_RE.sub("x" * 12, text))


def strip_boilerplate(text):
    """Drop the opt-out clause before judging what a message says.

    It is required text, it is identical everywhere, and counting it as
    content gets two things wrong at once: 'Reply STOP to opt out' reads as a
    second call to action competing with the real one, and two otherwise
    identical messages look different because only one of them carries it."""
    keep = []
    for part in re.split(r"(?<=[.!?])\s+|\n+", text):
        low = part.lower()
        if any(marker in low for marker in RUBRIC["opt_out_markers"]):
            continue
        keep.append(part)
    return " ".join(keep).strip() or text.strip()


def similarity(a, b):
    norm = lambda s: " ".join(
        PLACEHOLDER_RE.sub("", strip_boilerplate(s)).lower().split())
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


def in_quiet_hours(hhmm):
    start, end = CADENCE["quiet_hours_start"], CADENCE["quiet_hours_end"]
    return hhmm >= start or hhmm < end


# ----------------------------------------------------------------- the check

def check(text):
    header, channel, messages = parse(text)
    limits = RUBRIC["channel_limits"][channel]
    findings = []
    add = findings.append

    # ---------------------------------------------------- sequence-level
    if not (header.get("stop_when") or "").strip():
        add(Finding("no_stop_condition",
                    "This sequence never says what stops it. Without a stop "
                    "condition it keeps messaging people who have already done "
                    "the thing it is asking for, which is the single fastest way "
                    "to make candidates opt out of hearing from you at all. Add "
                    "`stop_when:` naming the event that halts the sequence."))

    if len(messages) > limits["max_messages"]:
        add(Finding("too_many_messages",
                    f"{len(messages)} messages on {channel}. The cap here is "
                    f"{limits['max_messages']}. Past that, reply rates fall and "
                    "opt-out rates rise - you are spending future contactability "
                    "on a candidate who has already decided."))

    ordered = sorted(messages, key=lambda m: m["minutes"])
    if [m["index"] for m in ordered] != [m["index"] for m in messages]:
        add(Finding("out_of_order",
                    "The messages are not in send order. Renumber them by time, "
                    "or the cadence below is measuring something you did not mean."))

    for earlier, later in zip(ordered, ordered[1:]):
        hours = (later["minutes"] - earlier["minutes"]) / 60.0
        if hours < CADENCE["min_hours_between"]:
            add(Finding("too_fast",
                        f"Messages {earlier['index']} and {later['index']} are "
                        f"{hours:.0f} hours apart. Leave at least "
                        f"{CADENCE['min_hours_between']} - a second nudge before "
                        "someone has had a working day to see the first one reads "
                        "as pestering, and it is the same message to them.",
                        later["index"]))

    if ordered:
        span = (ordered[-1]["minutes"] - ordered[0]["minutes"]) / 1440.0
        if span > CADENCE["max_window_days"]:
            add(Finding("window_too_long",
                        f"The sequence runs {span:.0f} days. Past "
                        f"{CADENCE['max_window_days']}, an hourly candidate has "
                        "taken another job and the message lands as a company that "
                        "lost track of them."))

    for m in messages:
        if in_quiet_hours(m["time"]):
            add(Finding("quiet_hours",
                        f"Message {m['index']} sends at {m['time']}. Keep sends "
                        f"between {CADENCE['quiet_hours_end']} and "
                        f"{CADENCE['quiet_hours_start']}. Shift workers sleep at "
                        "hours office workers do not, and a 6am text reaches "
                        "somebody who worked until two.",
                        m["index"]))

    for i, a in enumerate(messages):
        for b in messages[i + 1:]:
            if similarity(a["body"], b["body"]) >= RUBRIC["duplicate_similarity"]:
                add(Finding("duplicate_message",
                            f"Messages {a['index']} and {b['index']} say the same "
                            "thing. Every message in a sequence has to add "
                            "something - new information, a different action, or a "
                            "reason the timing changed - or it is just volume.",
                            b["index"]))

    opt_outs = [m["index"] for m in messages
                if contains(m["body"], RUBRIC["opt_out_markers"])]
    if limits["needs_opt_out"]:
        if not opt_outs:
            add(Finding("no_opt_out",
                        f"No message offers a way to stop. On {channel} that is "
                        "both a compliance problem in most jurisdictions and the "
                        "reason people block the number instead. Put it on the "
                        "first message."))
        elif opt_outs[0] != 1:
            add(Finding("opt_out_not_first",
                        f"The opt-out first appears on message {opt_outs[0]}. It "
                        "belongs on the first one - that is the message that "
                        "arrives from a number they do not recognise."))
        if len(opt_outs) > 1:
            add(Finding("opt_out_repeated",
                        f"The opt-out appears on {len(opt_outs)} messages. Once is "
                        "the requirement; on every message it reads as a company "
                        "that expects to annoy you, and it spends characters you "
                        "need for the actual ask."))

    # ---------------------------------------------------- message-level
    for m in messages:
        body, idx = m["body"], m["index"]
        if not body:
            add(Finding("empty_message", f"Message {idx} has no text.", idx))
            continue

        length = visible_length(body)
        if limits["chars"] and length > limits["chars"]:
            add(Finding("too_long",
                        f"Message {idx} is about {length} characters once the "
                        f"placeholders are filled; the limit on {channel} is "
                        f"{limits['chars']}. Over that it is split or truncated, "
                        "and the call to action is what falls off the end.",
                        idx))

        sensitive = contains(body, RUBRIC["sensitive_asks"])
        if sensitive:
            add(Finding("asks_for_sensitive_data",
                        f"Message {idx} asks for {', '.join(sensitive)}. Never "
                        "collect that over a messaging channel: it trains "
                        "candidates to hand identity documents to whoever texts "
                        "them, which is exactly how recruitment fraud works. Link "
                        "to your own system and let them authenticate.",
                        idx))

        urgency = contains(body, RUBRIC["false_urgency"])
        if urgency:
            add(Finding("false_urgency",
                        f"Message {idx} uses {', '.join(urgency)}. If the deadline "
                        "is real, state it as a date. If it is not, this is a "
                        "threat to somebody deciding whether to trust you as an "
                        "employer.",
                        idx))

        if not contains(body, RUBRIC["identification_markers"]):
            add(Finding("unidentified",
                        f"Message {idx} never says who is writing. An unidentified "
                        "text asking someone to click a link is indistinguishable "
                        "from a scam, and increasingly gets treated as one.",
                        idx))

        actions = contains(strip_boilerplate(body), RUBRIC["action_verbs"])
        if not actions:
            add(Finding("no_call_to_action",
                        f"Message {idx} asks for nothing. Every message in a nudge "
                        "sequence exists to make one specific action easy.",
                        idx))
        elif len(actions) > 2:
            add(Finding("competing_actions",
                        f"Message {idx} offers {len(actions)} different actions "
                        f"({', '.join(actions[:4])}). Pick one. A choice of three "
                        "ways to respond is a decision, and a decision is what the "
                        "candidate is already not making.",
                        idx))

        grade = reading_grade(body)
        if grade > RUBRIC["reading_grade_max"]:
            add(Finding("reading_level",
                        f"Message {idx} reads at grade {grade}; keep it at or under "
                        f"{RUBRIC['reading_grade_max']}. This is read on a phone, "
                        "often in a second language, often between shifts.",
                        idx))

        for s in sentences(body):
            if len(WORD_RE.findall(s)) > RUBRIC["long_sentence_words"]:
                add(Finding("long_sentence",
                            f"Message {idx} has a sentence over "
                            f"{RUBRIC['long_sentence_words']} words. Split it.",
                            idx))
                break

        if body.count("!") > RUBRIC["max_exclamations_per_message"]:
            add(Finding("over_punctuated",
                        f"Message {idx} has {body.count('!')} exclamation marks. "
                        "Enthusiasm is not the thing standing between this "
                        "candidate and a shift.",
                        idx))

        if len(EMOJI_RE.findall(body)) > RUBRIC["max_emoji_per_message"]:
            add(Finding("emoji_heavy",
                        f"Message {idx} carries "
                        f"{len(EMOJI_RE.findall(body))} emoji. On SMS they also "
                        "cost characters at a worse rate than letters.",
                        idx))

        shouted = [w for w in SHOUT_RE.findall(body)
                   if w not in {"SMS", "ASAP", "HR", "PPE", "DOT", "STOP"}]
        if shouted:
            add(Finding("shouting",
                        f"Message {idx} shouts: {', '.join(shouted[:3])}.",
                        idx))

    blocking = {"no_stop_condition", "too_many_messages", "too_fast", "quiet_hours",
                "no_opt_out", "opt_out_not_first", "asks_for_sensitive_data",
                "false_urgency", "too_long", "duplicate_message", "unidentified",
                "no_call_to_action", "empty_message", "out_of_order"}
    codes = {f["code"] for f in findings}
    return {
        "channel": channel,
        "stage": header.get("stage", ""),
        "stop_when": header.get("stop_when", ""),
        "messages": len(messages),
        "window_days": round((ordered[-1]["minutes"] - ordered[0]["minutes"]) / 1440.0, 1)
                       if ordered else 0,
        "findings": findings,
        "ready_to_send": not (codes & blocking),
        "blocking": sorted(codes & blocking),
    }


def report_text(r):
    lines = [f"{r['channel']} sequence - {r['messages']} messages over "
             f"{r['window_days']} days"]
    if r["stage"]:
        lines.append(f"stage: {r['stage']}")
    lines.append(f"stops when: {r['stop_when'] or 'NOT SET'}")
    lines.append("")
    if not r["findings"]:
        lines.append("No findings. Ready to send.")
    for f in r["findings"]:
        where = f" (message {f['message_index']})" if f["message_index"] else ""
        lines.append(f"[{f['code']}]{where} {f['message']}")
    lines.append("")
    lines.append("READY TO SEND" if r["ready_to_send"]
                 else "NOT READY - " + ", ".join(r["blocking"]))
    return "\n".join(lines)


# --------------------------------------------------------------- test suite

# Every fixture either passes clean or fails for a named reason, and each one
# also declares what must NOT be found in it. The second half is what catches
# a rule that fires on everything: a checker that flags every sequence is as
# useless as one that flags none, and only the must_not sets notice.
EXPECTED = [
    ("good_sms.txt", {"must": set(), "must_not": {
        "no_stop_condition", "too_many_messages", "too_fast", "quiet_hours",
        "no_opt_out", "opt_out_not_first", "opt_out_repeated", "too_long",
        "duplicate_message", "unidentified", "no_call_to_action",
        "asks_for_sensitive_data", "false_urgency", "reading_level",
        "competing_actions", "shouting", "over_punctuated"},
        "ready": True}),

    ("good_email.txt", {"must": set(), "must_not": {
        "no_stop_condition", "too_many_messages", "too_fast", "quiet_hours",
        "no_opt_out", "too_long", "duplicate_message", "unidentified",
        "no_call_to_action", "reading_level", "false_urgency"},
        "ready": True}),

    ("too_many.txt", {"must": {"too_many_messages"},
                      "must_not": {"quiet_hours", "too_fast", "no_opt_out"},
                      "ready": False}),

    ("too_fast.txt", {"must": {"too_fast"},
                      "must_not": {"too_many_messages", "quiet_hours", "no_opt_out"},
                      "ready": False}),

    ("quiet_hours.txt", {"must": {"quiet_hours"},
                         "must_not": {"too_many_messages", "too_fast", "no_opt_out"},
                         "ready": False}),

    ("no_optout.txt", {"must": {"no_opt_out"},
                       "must_not": {"too_many_messages", "quiet_hours",
                                    "opt_out_repeated", "unidentified"},
                       "ready": False}),

    ("optout_every_time.txt", {"must": {"opt_out_repeated"},
                               "must_not": {"no_opt_out", "opt_out_not_first",
                                            "too_many_messages", "quiet_hours"},
                               "ready": True}),

    ("sensitive_data.txt", {"must": {"asks_for_sensitive_data"},
                            "must_not": {"too_many_messages", "quiet_hours"},
                            "ready": False}),

    ("false_urgency.txt", {"must": {"false_urgency"},
                           "must_not": {"too_many_messages", "quiet_hours",
                                        "no_opt_out"},
                           "ready": False}),

    ("duplicate.txt", {"must": {"duplicate_message"},
                       "must_not": {"too_many_messages", "quiet_hours", "no_opt_out"},
                       "ready": False}),

    ("no_stop_condition.txt", {"must": {"no_stop_condition"},
                               "must_not": {"too_many_messages", "quiet_hours",
                                            "no_opt_out", "unidentified"},
                               "ready": False}),

    ("unidentified.txt", {"must": {"unidentified"},
                          "must_not": {"no_opt_out", "too_many_messages",
                                       "no_call_to_action"},
                          "ready": False}),

    ("sms_too_long.txt", {"must": {"too_long"},
                          "must_not": {"no_opt_out", "unidentified",
                                       "no_call_to_action"},
                          "ready": False}),

    ("shouting_and_hype.txt", {"must": {"shouting", "over_punctuated", "false_urgency"},
                               "must_not": {"no_opt_out", "unidentified"},
                               "ready": False}),
]


def run_tests():
    passed = failed = 0
    print(f"candidate-message-sequencer - {len(EXPECTED)} fixtures\n")
    for name, want in EXPECTED:
        path = os.path.join(FIXTURES, name)
        if not os.path.exists(path):
            print(f"  MISSING  {name}")
            failed += 1
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                r = check(fh.read())
            except Unparseable as stop:
                print(f"  FAIL  {name}  unparseable: {stop}")
                failed += 1
                continue
        codes = {f["code"] for f in r["findings"]}
        missed = want["must"] - codes
        invented = want["must_not"] & codes
        ok = not missed and not invented and r["ready_to_send"] == want["ready"]
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if missed:
            print(f"        missed: {', '.join(sorted(missed))}")
        if invented:
            print(f"        false positive: {', '.join(sorted(invented))}")
        if r["ready_to_send"] != want["ready"]:
            print(f"        ready_to_send {r['ready_to_send']}, expected {want['ready']}")
        passed, failed = (passed + 1, failed) if ok else (passed, failed + 1)

    print("\n  parser refusals")
    for label, text in (
        ("no timestamps", "channel: sms\nstop_when: x\n\nHi there, book a call."),
        ("unknown channel", "channel: pigeon\nstop_when: x\n\n[day 0, 10:00]\nHi."),
        ("impossible time", "channel: sms\nstop_when: x\n\n[day 0, 99:00]\nHi."),
    ):
        try:
            check(text)
            print(f"  FAIL  refuses {label}: it ran")
            failed += 1
        except Unparseable:
            print(f"  PASS  refuses {label}")
            passed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


def main():
    ap = argparse.ArgumentParser(description="Check a candidate nudge sequence.")
    ap.add_argument("--input", help="the sequence, as a text file")
    ap.add_argument("--out", help="write the report as JSON here")
    ap.add_argument("--test", action="store_true", help="run the fixture suite")
    args = ap.parse_args()

    if args.test:
        return run_tests()
    if not args.input:
        ap.error("give me --input, or --test")

    with open(args.input, encoding="utf-8") as fh:
        try:
            report = check(fh.read())
        except Unparseable as stop:
            print(json.dumps({"unparseable": True, "reason": str(stop)}, indent=2))
            return 2

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print(f"report written to {args.out}")
    else:
        print(report_text(report))
    return 0 if report["ready_to_send"] else 1


if __name__ == "__main__":
    sys.exit(main())
