#!/usr/bin/env python3
"""
Rehire campaign engine: turns your own past applicants and former workers into
a contactable, segmented pool, sized against your reply capacity, and checks
the messages before they go.

    python3 rehire.py --pool export.csv --policy policy.json
                      [--suppress optouts.csv] [--list-out contactable.csv]
                      [--html plan.html] [--json plan.json]
    python3 rehire.py --messages messages.json [--policy policy.json]
    python3 rehire.py --demo
    python3 rehire.py --test

export.csv   one row per application (the library's pipeline samples work as
             they are): application_id, applied_at, stage_reached, exit_reason,
             location_id, role; region, separation_at, separation_reason,
             rehire_eligible, person_id, opted_out and stage dates when you
             have them. Opaque ids only.
policy.json  what you may send and what you are hiring for: as_of,
             retention_months, contact (past_applicants, former_workers,
             other_roles: true, false or null for "not decided"), hiring_now
             (location_id, role, shift, openings), match (location or
             region), news, reply_capacity_hours_per_day. See
             references/sample/northline_policy.json.

Every row lands in exactly one place: a segment, or a named reason it is out.
Permanently out: background, drug-screen, medical-certificate, document and
right-to-work outcomes, conduct, involuntary and attendance exits, opt-outs.
Out for now: past your retention period (a deletion job, not a segment), no
opening near them, a contact purpose nobody has decided on, a reason code
nobody can read. Reply rates are stated assumptions in references/taxonomy.json.

Exit codes: 0 plan written or messages ready, 1 messages not ready,
2 no mode, 3 input refused, 4 the engine failed. Standard library only.
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
SKILL_DIR = os.path.dirname(HERE)
REF = os.path.join(SKILL_DIR, "references")
SAMPLE = os.path.join(REF, "sample")
FIXTURES = os.path.join(REF, "fixtures")

DATE_COLS = ("applied_at", "screened_at", "docs_submitted_at", "interview_scheduled_at", "interview_completed_at",
             "background_clear_at", "offer_at", "onboarding_started_at", "scheduled_first_shift_at",
             "scheduled_first_job_at", "first_shift_at", "first_job_at", "separation_at", "last_activity_at")
NOMINATIVE = re.compile(r"(^|_)(first|last|full)?_?name($|_)|e-?mail|phone|mobile|address|street|zip|postcode|"
                        r"postal|ssn|social_security|dob|birth|notes?$|comment", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
GROUPS = ("former_worker", "late_deep", "late_screened", "other_role")
GROUP_LABEL = {"former_worker": "Former workers who left in good standing",
               "late_deep": "Reached interview or beyond, never started",
               "late_screened": "Screened, then dropped or dropped by us",
               "other_role": "Rejected against a requirement of a different job"}
MERGE_OK = {"first_name": 10, "site": 18, "role": 18, "rate": 6, "booking_link": 23, "applied_month": 9,
            "shift": 10, "start_date": 10}
OPT_OUT = re.compile(r"\b(reply stop|text stop|stop to (opt out|unsubscribe|end)|unsubscribe|opt out)\b", re.I)
REAPPLY = re.compile(r"\b(re-?apply|apply again|submit (a |an |another )?(new )?application|fill (out|in) "
                     r"(the|an|a new|another) (application|form)|start a new application)\b", re.I)
LAST = re.compile(r"\b(last (message|text|note|one)|final (message|text|note)|won't (text|message|contact) "
                  r"(you )?again|this is the last)\b", re.I)
WHY = re.compile(r"\b(you applied|applied (with|to|for)|your application|you worked|worked (with|at) us|"
                 r"when you (were|left)|interviewed|we spoke|we met|you started)\b", re.I)


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ reading

def read_csv(path, what):
    if not path or not os.path.exists(path):
        raise Refusal(f"{what}: file not found ({path}).")
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16")
    else:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = csv.reader(io.StringIO(text), dialect)
    try:
        header = [h.strip().lower().replace(" ", "_") for h in next(rows)]
    except StopIteration:
        raise Refusal(f"{what}: the file is empty.")
    for h in header:
        if NOMINATIVE.search(h):
            raise Refusal(f"{what}: column '{h}' looks like personal information. Re-export with opaque ids only: "
                          "nothing in this plan needs to know who anybody is.")
    out = [{h: (r[i].strip() if i < len(r) else "") for i, h in enumerate(header)}
           for r in rows if any(c.strip() for c in r)]
    if EMAIL.search("".join(",".join(r.values()) for r in out[:3000])):
        raise Refusal(f"{what}: the file contains email addresses. Re-export with opaque ids only.")
    return header, out


def day(s):
    s = (s or "").strip()[:10]
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        for fmt in ("%m/%d/%Y", "%d/%m/%Y"):
            try:
                return dt.datetime.strptime(s, fmt).date()
            except ValueError:
                pass
    return None


def load_policy(path):
    try:
        p = json.load(open(path, encoding="utf-8-sig"))
    except OSError:
        raise Refusal(f"policy: file not found ({path}).")
    except ValueError as exc:
        raise Refusal(f"policy: not valid JSON ({exc}).")
    return validate_policy(p, os.path.dirname(os.path.abspath(path)))


def validate_policy(p, base="."):
    if not isinstance(p, dict):
        raise Refusal("policy: expected an object.")
    out = dict(p)
    try:
        out["as_of"] = dt.date.fromisoformat(str(p.get("as_of", "")))
    except ValueError:
        raise Refusal("policy: as_of must be a date like 2026-09-01.")
    rm = p.get("retention_months")
    if not isinstance(rm, int) or rm < 1:
        raise Refusal("policy: retention_months must be a whole number of months, from your privacy notice. If "
                      "you do not know it, that is the first question for whoever owns data protection.")
    c = p.get("contact")
    if not isinstance(c, dict):
        raise Refusal("policy: contact needs past_applicants, former_workers and other_roles, each true, false "
                      "or null (not decided).")
    for k in ("past_applicants", "former_workers", "other_roles"):
        if k not in c or c[k] not in (True, False, None):
            raise Refusal(f"policy: contact.{k} must be true, false or null.")
    hn = p.get("hiring_now")
    if not isinstance(hn, list) or not hn:
        raise Refusal("policy: hiring_now lists what you are hiring for now: location_id, role, shift, openings.")
    for i, o in enumerate(hn, 1):
        if not isinstance(o, dict) or not o.get("location_id") or not o.get("role"):
            raise Refusal(f"policy: hiring_now item {i} needs location_id and role.")
        if o.get("shift", "days") not in ("days", "evenings", "nights"):
            raise Refusal(f"policy: hiring_now item {i}: shift is days, evenings or nights.")
    if p.get("match", "location") not in ("location", "region"):
        raise Refusal("policy: match is location or region.")
    cap = p.get("reply_capacity_hours_per_day", 0)
    if not isinstance(cap, (int, float)) or cap <= 0:
        raise Refusal("policy: reply_capacity_hours_per_day: how many hours a day someone answers replies. Plan "
                      "the replies before the first send.")
    out["match"] = p.get("match", "location")
    out["news"] = [n for n in p.get("news", []) if isinstance(n, str) and n.strip()]
    out["changed_patterns"] = [r for r in p.get("changed_patterns", []) if isinstance(r, str)]
    out["_base"] = base
    return out


def load_tax():
    return json.load(open(os.path.join(REF, "taxonomy.json"), encoding="utf-8"))


# ------------------------------------------------------------------ the plan

def band_of(months, tax):
    for lo, hi, name in tax["recency_bands"]:
        if lo <= months <= hi:
            return name
    return tax["recency_bands"][-1][2]


def plan(pool, policy, suppress=None):
    tax = load_tax()
    if isinstance(policy, str):
        policy = load_policy(policy)
    header, rows = read_csv(pool, "export")
    idc = "application_id" if "application_id" in header else ("id" if "id" in header else None)
    for c in ("stage_reached", "exit_reason"):
        if c not in header:
            raise Refusal(f"export: missing column '{c}'. Needed: application_id, stage_reached, exit_reason, and "
                          "location_id and role to match people to openings.")
    if not idc:
        raise Refusal("export: missing column 'application_id' (or 'id').")
    if "location_id" not in header:
        raise Refusal("export: missing location_id. Without it nobody can be matched to an opening near them.")
    if not any(c in header for c in DATE_COLS):
        raise Refusal("export: no date column. applied_at at least, so recency and retention can be read.")
    suppressed = set()
    if suppress:
        sh, srows = read_csv(suppress, "suppression")
        col = next((c for c in ("application_id", "id", "person_id") if c in sh), None)
        if not col:
            raise Refusal("suppression: needs an application_id, id or person_id column.")
        suppressed = {r[col] for r in srows if r[col]}

    as_of = policy["as_of"]
    cutoff_days = policy["retention_months"] * 30.44
    openings = policy["hiring_now"]
    by_loc, by_region = {}, {}
    region_of = {}
    for r in rows:
        if r.get("region"):
            region_of[r["location_id"]] = r["region"]
    for o in openings:
        by_loc.setdefault(o["location_id"], []).append(o)
        reg = region_of.get(o["location_id"])
        if reg:
            by_region.setdefault(reg, []).append(o)

    ex = tax["exit_reasons"]
    exit_class = {r: k for k, v in ex.items() for r in v}
    sep = tax["separation_reasons"]
    sep_class = {r: k for k, v in sep.items() for r in v}
    depth = tax["stage_depth"]
    contact = policy["contact"]

    people, buckets, seen_ids = [], {}, set()

    def out_(reason, r):
        buckets[reason] = buckets.get(reason, 0) + 1

    for r in rows:
        rid = r[idc]
        if not rid:
            raise Refusal("export: a row has no application_id.")
        if rid in seen_ids:
            raise Refusal(f"export: application_id {rid} appears twice.")
        seen_ids.add(rid)
        stage = r["stage_reached"].lower()
        if stage not in depth:
            out_("unreadable stage", r)
            continue
        d = depth[stage]
        dates = [x for x in (day(r.get(c, "")) for c in DATE_COLS) if x and x <= as_of]
        if not dates:
            out_("no usable date", r)
            continue
        last = max(dates)
        if (r.get("opted_out", "").lower() in ("yes", "y", "true", "1")) or rid in suppressed \
                or (r.get("person_id") and r["person_id"] in suppressed):
            out_("opted out", r)
            continue
        if d >= 6:
            if not day(r.get("separation_at", "")):
                out_("still working for you", r)
                continue
            cls = sep_class.get(r.get("separation_reason", "").lower())
            flag = r.get("rehire_eligible", "").lower()
            if cls == "never" or flag in ("no", "n", "false", "0"):
                out_("left on conduct, attendance or not eligible for rehire", r)
                continue
            if cls != "good_standing":
                out_("unreadable reason", r)
                continue
            group = "former_worker"
        else:
            reason = r["exit_reason"].lower()
            cls = exit_class.get(reason)
            if cls == "never":
                out_("background, screening or right-to-work outcome", r)
                continue
            if cls is None:
                out_("unreadable reason", r)
                continue
            if cls == "abandoned_form" or (d == 0 and cls in ("screened_dropoff", "late_stage")):
                out_("never got past the form", r)
                continue
            if cls == "late_stage":
                group = "late_deep" if d >= tax["deep_from"] else "late_screened"
            elif cls == "screened_dropoff":
                group = "late_deep" if d >= tax["deep_from"] else "late_screened"
            else:
                group = "other_role"
        if (as_of - last).days > cutoff_days:
            out_("past your retention period (a deletion job)", r)
            continue
        key = {"former_worker": "former_workers", "other_role": "other_roles"}.get(group, "past_applicants")
        if contact[key] is None:
            out_(f"blocked: no decision yet on contacting {key.replace('_', ' ')}", r)
            continue
        if contact[key] is False:
            out_(f"not allowed: {key.replace('_', ' ')}", r)
            continue
        if group == "other_role" and contact["past_applicants"] is not True:
            out_("blocked: no decision yet on contacting past applicants" if contact["past_applicants"] is None
                 else "not allowed: past applicants", r)
            continue
        near = by_loc.get(r["location_id"], [])
        if policy["match"] == "region":
            near = by_region.get(region_of.get(r["location_id"]), near)
        role = r.get("role", "")
        if group == "other_role":
            same_ok = role in policy["changed_patterns"] and r["exit_reason"].lower() == "availability_mismatch"
            near = [o for o in near if o["role"] != role or same_ok]
        if not near:
            out_("no opening near them" if group != "other_role" else "no different opening near them", r)
            continue
        months = int((as_of - last).days // 30.44)
        shifts = sorted({o.get("shift", "days") for o in near})
        people.append({"id": rid, "person": r.get("person_id") or rid, "group": group,
                       "band": band_of(months, tax), "last": last, "site": r["location_id"], "role": role,
                       "offer": sorted({o["role"] for o in near}), "shift": shifts[0] if len(shifts) == 1 else
                       max(shifts, key=lambda s: sum(o.get("openings", 1) for o in near if o.get("shift") == s)),
                       "our_fault": r["exit_reason"].lower() in tax["our_fault"],
                       "channel": r.get(policy.get("channel_column") or "", "") or policy.get("channel", "sms")})

    # one message per person
    order = {g: i for i, g in enumerate(GROUPS)}
    best = {}
    for p in people:
        q = best.get(p["person"])
        if q is None or (order[p["group"]], -p["last"].toordinal()) < (order[q["group"]], -q["last"].toordinal()):
            if q is not None:
                buckets["same person, another application"] = buckets.get("same person, another application", 0) + 1
            best[p["person"]] = p
        else:
            buckets["same person, another application"] = buckets.get("same person, another application", 0) + 1
    people = sorted(best.values(), key=lambda p: (order[p["group"]], p["band"], p["id"]))

    # segments
    rates = tax["reply_rate"]
    segs = {}
    for p in people:
        sid = f"{p['group']}|{p['band']}"
        s = segs.setdefault(sid, {"id": sid, "group": p["group"], "band": p["band"], "size": 0, "sites": set(),
                                  "shifts": {}, "our_fault": 0, "rate": rates[p["group"]][p["band"]]})
        s["size"] += 1
        s["sites"].add(p["site"])
        s["shifts"][p["shift"]] = s["shifts"].get(p["shift"], 0) + 1
        s["our_fault"] += 1 if p["our_fault"] else 0
    seg_list = sorted(segs.values(), key=lambda s: -s["rate"])
    for s in seg_list:
        s["expected_replies"] = round(s["size"] * s["rate"])
        s["small"] = s["size"] < tax["min_segment"]
        s["sites"] = sorted(s["sites"])
        s["windows"] = {sh: tax["send_windows"][sh] for sh in s["shifts"]}
        s["code"] = s["group"].upper().replace("_", "-") + "-" + s["band"].upper()

    # waves: never more replies in an arc than someone can answer
    per_hour = 60 / tax["minutes_per_reply"]
    capacity = policy["reply_capacity_hours_per_day"] * per_hour * 4
    for p in people:
        p["rate"] = rates[p["group"]][p["band"]]
    ranked = sorted(people, key=lambda p: (-p["rate"], p["id"]))
    wave, load, waves = 1, 0.0, []
    count = 0
    for p in ranked:
        if (load + p["rate"] > capacity or (wave == 1 and count >= tax["first_wave_cap"])) and count:
            waves.append({"wave": wave, "people": count, "expected_replies": round(load)})
            wave, load, count = wave + 1, 0.0, 0
        p["wave"] = wave
        load += p["rate"]
        count += 1
    if count:
        waves.append({"wave": wave, "people": count, "expected_replies": round(load)})

    # cost, from the numbers just counted
    total = len(people)
    replies = sum(p["rate"] for p in people)
    sites = sorted({p["site"] for p in people})
    full_segs = [s for s in seg_list if not s["small"]]
    refresh = sum(1 for p in people if (as_of - p["last"]).days <= 30)
    cost = {"contactable": total, "segments": len(full_segs), "small_segments": len(seg_list) - len(full_segs),
            "messages_to_write": 3 * len(full_segs), "canned_replies": 8, "sites_to_confirm": len(sites),
            "site_minutes": len(sites) * 3, "replies": round(replies),
            "reply_hours": round(replies * tax["minutes_per_reply"] / 60, 1),
            "opt_outs": [round(total * tax["opt_out_rate"][0]), round(total * tax["opt_out_rate"][1])],
            "waves": len(waves), "capacity_replies_per_arc": round(capacity),
            "newly_eligible_last_30_days": refresh}

    warnings = []
    if not policy["news"]:
        warnings.append("No news in the policy. A campaign with nothing new in it asks people to change their minds "
                        "for no reason: what has changed since they applied (pay, pattern, a closer site, a removed "
                        "step)?")
    if not suppress and "opted_out" not in header:
        warnings.append("No suppression list given and no opted_out column. Check suppression at send time, not "
                        "now: people opt out in between.")
    if not policy.get("channel_column"):
        warnings.append(f"Channel consent is not in the export: every message assumes "
                        f"'{policy.get('channel', 'sms')}'. A number given to arrange an interview is not "
                        "automatically consent to campaign texts; confirm it with whoever owns data protection.")
    if "rehire_eligible" not in header and any(p["group"] == "former_worker" for p in people):
        warnings.append("No rehire_eligible flag: former workers are judged on separation reason only. An "
                        "unmaintained flag is worse than none, so this may be right; say which.")
    blocked = {k: v for k, v in buckets.items() if k.startswith("blocked")}
    return {"as_of": as_of.isoformat(), "rows": len(rows), "people": people, "segments": seg_list,
            "out": dict(sorted(buckets.items(), key=lambda kv: -kv[1])), "blocked": blocked, "waves": waves,
            "cost": cost, "warnings": warnings, "news": policy["news"],
            "groups": {g: sum(1 for p in people if p["group"] == g) for g in GROUPS},
            "our_fault": sum(1 for p in people if p["our_fault"])}


# ------------------------------------------------------------------ messages

def check_messages(m, policy=None):
    if not isinstance(m, dict) or not isinstance(m.get("segments"), dict) or not m["segments"]:
        raise Refusal("messages: expected {\"sender\": ..., \"channel\": ..., \"segments\": {code: [3 messages]}}.")
    sender = m.get("sender")
    sender = sender.strip() if isinstance(sender, str) else ""
    if not sender:
        raise Refusal("messages: say who is sending (\"sender\").")
    channel = m.get("channel", "sms")
    limit = {"sms": 320, "email": 1200}.get(channel)
    if limit is None:
        raise Refusal("messages: channel is sms or email.")
    block, warn = [], []
    news = [n.lower() for n in (policy or {}).get("news", [])]
    for code, msgs in m["segments"].items():
        if not isinstance(msgs, list):
            raise Refusal(f"messages: {code} must be a list of messages.")
        days = sorted(x.get("day") for x in msgs if isinstance(x, dict))
        if days != [0, 1, 3]:
            block.append(f"{code}: messages on days {days}. Three, on day 0, day 1 and day 3, then stop.")
        byday = {x.get("day"): str(x.get("text", "")) for x in msgs if isinstance(x, dict)}
        for dnum, text in sorted(byday.items(), key=lambda kv: (kv[0] is None, kv[0])):
            tag = f"{code} day {dnum}"
            fields = re.findall(r"\{\{\s*(\w+)\s*\}\}|\[([A-Z_]+)\]", text)
            for a, b in fields:
                f = a or b
                if b or f not in MERGE_OK:
                    block.append(f"{tag}: merge field '{f}' is not one the send tool fills ({', '.join(MERGE_OK)}). "
                                 "Sent as is, two thousand people read it.")
            filled = re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda mm: "x" * MERGE_OK.get(mm.group(1), 12), text)
            if len(filled) > limit:
                block.append(f"{tag}: about {len(filled)} characters with the fields filled. Keep a text under "
                             f"{limit} (two segments).")
            if not OPT_OUT.search(text):
                block.append(f"{tag}: no way to opt out. Every message carries one ('Reply STOP to opt out').")
            if sender.lower() not in text.lower():
                block.append(f"{tag}: does not say who is writing. Name {sender} in every message.")
            if REAPPLY.search(text) and not code.upper().startswith("OTHER"):
                block.append(f"{tag}: asks them to apply again. Someone who reached your offer stage should never "
                             "fill the form twice: one tap to a slot.")
        if 0 in byday and not WHY.search(byday[0]):
            block.append(f"{code} day 0: does not say why you are writing ('you applied in {{{{applied_month}}}}', "
                         "'you worked with us').")
        if 1 in byday:
            t1 = byday[1].lower()
            has_number = bool(re.search(r"\$\d|\d+(\.\d+)?\s*(/hr|an hour|per hour)|\b\d+\b|\{\{\s*rate\s*\}\}",
                                        t1))
            words1 = set(re.findall(r"[a-z]{4,}", t1))
            echoes = any(len(words1 & set(re.findall(r"[a-z]{4,}", n))) >= 3 for n in news)
            if not (has_number or echoes):
                block.append(f"{code} day 1: no news in it. Day 1 is the reason to reconsider: the rate, the "
                             "pattern, the closer site, the step you removed.")
            if 0 in byday and byday[1].strip() == byday[0].strip():
                block.append(f"{code} day 1: the same text as day 0.")
        if 3 in byday and not LAST.search(byday[3]):
            block.append(f"{code} day 3: not marked as the last message. Ending cleanly earns the right to run "
                         "this again next quarter.")
    return {"ready": not block, "blocking": block, "warnings": warn, "segments": len(m["segments"])}


# ------------------------------------------------------------------ output

def text_plan(r):
    c = r["cost"]
    L = [f"Rehire pool, as of {r['as_of']}: {r['rows']:,} records read, {c['contactable']:,} contactable."]
    if r["warnings"]:
        L.append("")
        L.append("Settle these before the first send")
        L += [f"  - {w}" for w in r["warnings"]]
    L.append("")
    L.append("Who is in")
    for g in GROUPS:
        if r["groups"][g]:
            L.append(f"  {r['groups'][g]:>6,}  {GROUP_LABEL[g]}")
    if r["our_fault"]:
        L.append(f"          of whom {r['our_fault']:,} dropped because of you: no slot offered, nobody followed up, "
                 "a check that took too long. Lead with that.")
    L.append("")
    L.append("Who is out, and why")
    for k, v in r["out"].items():
        L.append(f"  {v:>6,}  {k}")
    L.append("")
    L.append("Segments (reply rates are assumptions: replace them with yours after wave 1)")
    for s in r["segments"]:
        mix = ", ".join(f"{n:,} {sh}" for sh, n in sorted(s["shifts"].items()))
        L.append(f"  {s['code']:<22}{s['size']:>6,}  ~{round(s['rate'] * 100)}% reply, ~{s['expected_replies']:,} "
                 f"replies  ({mix})" + ("  too small for its own messages: fold it into the next band"
                                        if s["small"] else ""))
    wins = load_tax()["send_windows"]
    L.append("  Send windows, local time at the site, by the pattern they would work:")
    for sh in ("days", "evenings", "nights"):
        if any(sh in s["shifts"] for s in r["segments"]):
            w = wins[sh]
            L.append(f"    {sh:<9} day 0 {w['day0']}, day 1 {w['day1']}, day 3 {w['day3']}")
    L.append("")
    L.append(f"Waves: someone answering {c['capacity_replies_per_arc']:,} replies across a four-day arc sets the size.")
    for w in r["waves"]:
        L.append(f"  Wave {w['wave']}: {w['people']:,} people, ~{w['expected_replies']:,} replies")
    L.append("")
    L.append("What it costs you to run (from these numbers)")
    L.append(f"  Once: {c['segments']} segments, {c['messages_to_write']} messages to write and approve, "
             f"{c['canned_replies']} canned replies, the open roles, pattern and rate confirmed at "
             f"{c['sites_to_confirm']} sites (~{c['site_minutes']} minutes).")
    L.append(f"  Every run: ~{c['replies']:,} replies at 3 minutes each, ~{c['reply_hours']} hours, most of it in the "
             f"48 hours after each send; {c['opt_outs'][0]}-{c['opt_outs'][1]} opt-outs to record before the next "
             f"wave.")
    L.append(f"  Every month: about {c['newly_eligible_last_30_days']:,} people became contactable in the last 30 days. "
             "Run it monthly and each wave is smaller and better aimed; run it once and you harvest the backlog and "
             "leave the supply on the floor.")
    if r["news"]:
        L.append("")
        L.append("The news for day 1")
        L += [f"  - {n}" for n in r["news"]]
    L.append("")
    L.append("This counts and sorts what you exported. It cannot check a consent record, send a message, or tell you "
             "whether your retention policy allows a segment: that is for whoever owns data protection.")
    return "\n".join(L)


def write_list(r, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["application_id", "segment", "wave", "site", "offer_roles", "send_pattern", "channel"])
        for p in sorted(r["people"], key=lambda p: (p["wave"], p["id"])):
            code = p["group"].upper().replace("_", "-") + "-" + p["band"].upper()
            w.writerow([p["id"], code, p["wave"], p["site"], "; ".join(p["offer"]), p["shift"], p["channel"]])


def render(r, path):
    e = html.escape
    body = e(text_plan(r))
    rows = "".join(f"<tr><td>{e(s['code'])}</td><td>{s['size']:,}</td><td>{round(s['rate'] * 100)}%</td>"
                   f"<td>{s['expected_replies']:,}</td></tr>" for s in r["segments"])
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Rehire campaign plan</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 10px;text-align:right}}
td:first-child,th:first-child{{text-align:left}}pre{{white-space:pre-wrap;font-size:13px}}</style>
<h1>Rehire campaign plan</h1><table><tr><th>Segment</th><th>People</th><th>Reply (assumed)</th><th>Replies</th></tr>
{rows}</table><pre>{body}</pre></html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ tests

def _data(name):
    for d in (os.path.join(SKILL_DIR, "data"), os.path.join(HERE, "..", "..", "..", "..", "data")):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


def run_tests():
    import contextlib
    import copy
    import random
    import shutil
    import tempfile
    tax = load_tax()
    passed = failed = 0

    def check(name, ok, detail=""):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL {name}" + (f"  [{detail}]" if detail != "" else ""))

    base = json.load(open(os.path.join(SAMPLE, "northline_policy.json"), encoding="utf-8"))

    def pol(**kw):
        p = copy.deepcopy(base)
        for k, v in kw.items():
            if k.startswith("contact_"):
                p["contact"][k[8:]] = v
            else:
                p[k] = v
        return validate_policy(p)

    datasets = [(n, _data(f"{n}_pipeline_sample.csv")) for n in ("frontline", "qsr", "logistics", "gig")]
    datasets = [(n, p) for n, p in datasets if p]
    if not datasets:
        print("sample dataset not found")
        return 1
    never_exit = set(tax["exit_reasons"]["never"])
    never_sep = set(tax["separation_reasons"]["never"])
    for name, path in datasets:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        byid = {r["application_id"]: r for r in rows}
        locs = sorted({r["location_id"] for r in rows})
        roles = sorted({r["role"] for r in rows})
        hiring = [{"location_id": l, "role": roles[i % len(roles)], "shift": ("nights", "days", "evenings")[i % 3],
                   "openings": 2} for i, l in enumerate(locs[::3])]
        p = pol(hiring_now=hiring, contact_other_roles=True)
        r = plan(path, p)
        t = f"{name}: "
        ids = [x["id"] for x in r["people"]]
        check(t + "every row lands in exactly one place", len(ids) + sum(r["out"].values()) == len(rows),
              (len(ids), sum(r["out"].values()), len(rows)))
        check(t + "nobody contacted twice", len(ids) == len(set(ids)))
        check(t + "no background, drug, medical or document outcome is contacted",
              not [i for i in ids if byid[i]["exit_reason"] in never_exit])
        check(t + "no involuntary or attendance leaver is contacted",
              not [i for i in ids if byid[i]["separation_reason"] in never_sep])
        check(t + "nobody still working is contacted",
              not [i for i in ids if byid[i]["stage_reached"] in ("started", "activated")
                   and not byid[i]["separation_at"]])
        dropout = set(tax["exit_reasons"]["late_stage"]) | set(tax["exit_reasons"]["screened_dropoff"])
        check(t + "nobody who only abandoned the form is contacted",
              not [i for i in ids if byid[i]["exit_reason"] == "incomplete_application"
                   or (byid[i]["stage_reached"] in ("applied", "signed_up") and byid[i]["exit_reason"] in dropout)])
        check(t + "everyone contacted at the application stage was rejected against a requirement",
              all(x["group"] == "other_role" for x in r["people"]
                  if byid[x["id"]]["stage_reached"] in ("applied", "signed_up")))
        cut = p["as_of"] - dt.timedelta(days=p["retention_months"] * 30.44)
        late = [i for i in ids if max(d for d in (day(byid[i].get(c, "")) for c in DATE_COLS) if d) < cut]
        check(t + "nobody past retention is contacted", not late, late[:3])
        check(t + "everyone contacted has an opening near them",
              all(any(o["location_id"] == x["site"] for o in hiring) for x in r["people"]))
        check(t + "a person rejected against a requirement is only offered a different role",
              all(x["role"] not in x["offer"] for x in r["people"] if x["group"] == "other_role"
                  and x["role"] not in p["changed_patterns"]))
        check(t + "waves never carry more replies than the capacity",
              all(w["expected_replies"] <= r["cost"]["capacity_replies_per_arc"] + 1 for w in r["waves"]))
        check(t + "the first wave is a few hundred at most", r["waves"][0]["people"] <= tax["first_wave_cap"])
        check(t + "the highest-yield people go first",
              min(x["rate"] for x in r["people"] if x["wave"] == 1)
              >= max(x["rate"] for x in r["people"] if x["wave"] == r["waves"][-1]["wave"]) - 1e-9
              if len(r["waves"]) > 1 else True)
        check(t + "the cost section is the plan's own numbers", r["cost"]["contactable"] == len(ids)
              and r["cost"]["messages_to_write"] == 3 * r["cost"]["segments"])
        # consent decisions change the plan, never the other way round
        r0 = plan(path, pol(hiring_now=hiring, contact_other_roles=None))
        check(t + "other roles undecided: that group is blocked, not contacted",
              r0["groups"]["other_role"] == 0 and any(k.startswith("blocked") for k in r0["out"]))
        r1 = plan(path, pol(hiring_now=hiring, contact_former_workers=False, contact_other_roles=True))
        check(t + "former workers not allowed: none contacted", r1["groups"]["former_worker"] == 0)
        r2 = plan(path, pol(hiring_now=hiring, contact_past_applicants=None, contact_other_roles=True))
        check(t + "past applicants undecided: only former workers remain",
              set(g for g, n in r2["groups"].items() if n) <= {"former_worker"})
        r3 = plan(path, pol(hiring_now=hiring, contact_other_roles=True, retention_months=3))
        check(t + "a shorter retention period only ever shrinks the pool",
              set(x["id"] for x in r3["people"]) <= set(ids) and len(r3["people"]) < len(ids))

    # the sample plan, as planted
    exp = json.load(open(os.path.join(SAMPLE, "northline_expected.json"), encoding="utf-8"))
    front = _data("frontline_pipeline_sample.csv")
    r = plan(front, os.path.join(SAMPLE, "northline_policy.json"))
    check("sample: other roles undecided, so blocked", r["groups"]["other_role"] == 0
          and "blocked: no decision yet on contacting other roles" in r["out"])
    check("sample: counts as recorded", {k: r["groups"][k] for k in GROUPS} == exp["groups"],
          {k: r["groups"][k] for k in GROUPS})
    check("sample: deletion job as recorded", r["out"].get("past your retention period (a deletion job)")
          == exp["deletion_job"], r["out"].get("past your retention period (a deletion job)"))
    check("sample: stocker sites get the night windows",
          all(x["shift"] == "nights" for x in r["people"] if x["site"] in exp["night_sites"]))
    check("sample: people dropped by us are counted", r["our_fault"] == exp["our_fault"], r["our_fault"])

    # suppression and opt-outs
    tmp = tempfile.mkdtemp(prefix="rcp-")
    try:
        some = [x["id"] for x in r["people"][:25]]
        sp = os.path.join(tmp, "s.csv")
        open(sp, "w").write("application_id\n" + "\n".join(some) + "\n")
        rs = plan(front, os.path.join(SAMPLE, "northline_policy.json"), suppress=sp)
        check("suppression list: every listed person is out",
              not set(some) & {x["id"] for x in rs["people"]} and rs["out"].get("opted out") == 25)
        rows = list(csv.reader(open(front, encoding="utf-8")))

        def write(name, rr):
            path = os.path.join(tmp, name)
            with open(path, "w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerows(rr)
            return path
        oo = write("oo.csv", [rows[0] + ["opted_out"]] + [row + (["yes"] if i % 2 else ["no"])
                                                          for i, row in enumerate(rows[1:])])
        ro = plan(oo, os.path.join(SAMPLE, "northline_policy.json"))
        check("opted_out column honoured", ro["out"].get("opted out", 0) > 0 and len(ro["people"]) < len(r["people"]))
        # rehire flag
        hdr = rows[0]
        si = hdr.index("separation_reason")
        rf = write("rf.csv", [hdr + ["rehire_eligible"]] + [row + (["no"] if row[si] == "voluntary_quit" else [""])
                                                            for row in rows[1:]])
        rr = plan(rf, os.path.join(SAMPLE, "northline_policy.json"))
        check("rehire_eligible = no keeps a voluntary leaver out",
              rr["groups"]["former_worker"] < r["groups"]["former_worker"])
        # person_id: one message per person
        pi = write("pi.csv", [hdr + ["person_id"]] + [row + [f"P{i // 2}"] for i, row in enumerate(rows[1:])])
        rp = plan(pi, os.path.join(SAMPLE, "northline_policy.json"))
        persons = [x["person"] for x in rp["people"]]
        check("one message per person, even with two applications", len(persons) == len(set(persons))
              and rp["out"].get("same person, another application", 0) > 0)
        # unknown reason codes are never guessed
        ei = hdr.index("exit_reason")
        uk = write("uk.csv", [hdr] + [row[:ei] + ["manager said no"] + row[ei + 1:] if row[ei] else row
                                      for row in rows[1:]])
        ru = plan(uk, os.path.join(SAMPLE, "northline_policy.json"))
        check("free-text reasons are left out, never guessed",
              ru["groups"]["late_deep"] == 0 and ru["out"].get("unreadable reason", 0) > 0)

        def refused(fn):
            try:
                fn()
                return False
            except Refusal:
                return True
        check("refuses a name column", refused(lambda: plan(write("n.csv", [hdr + ["first_name"]] +
                                                                    [row + ["x"] for row in rows[1:50]]),
                                                              os.path.join(SAMPLE, "northline_policy.json"))))
        check("refuses emails in a cell", refused(lambda: plan(write("e.csv", [hdr + ["ref"]] +
                                                                     [row + ["a@b.co"] for row in rows[1:50]]),
                                                               os.path.join(SAMPLE, "northline_policy.json"))))
        check("refuses duplicate ids", refused(lambda: plan(write("d.csv", rows[:20] + rows[1:3]),
                                                            os.path.join(SAMPLE, "northline_policy.json"))))
        check("refuses an export without location", refused(lambda: plan(
            write("l.csv", [[c for j, c in enumerate(row) if j != hdr.index("location_id")] for row in rows[:50]]),
            os.path.join(SAMPLE, "northline_policy.json"))))
        for bad, why in (({**base, "retention_months": None}, "no retention period"),
                         ({**base, "contact": {"past_applicants": "maybe"}}, "contact not decided properly"),
                         ({**base, "hiring_now": []}, "nothing being hired"),
                         ({**base, "reply_capacity_hours_per_day": 0}, "nobody answering replies"),
                         ({**base, "as_of": "soon"}, "no date")):
            check(f"policy refused: {why}", refused(lambda: validate_policy(bad)))

        # messages
        good = json.load(open(os.path.join(SAMPLE, "northline_messages.json"), encoding="utf-8"))
        res = check_messages(good, validate_policy(base))
        check(f"sample messages are ready ({res['blocking']})", res["ready"])
        broken = json.load(open(os.path.join(FIXTURES, "broken_messages.json"), encoding="utf-8"))
        for case in broken["cases"]:
            mm = copy.deepcopy(good)
            seg = next(iter(mm["segments"]))
            for op in case["ops"]:
                msg = next(x for x in mm["segments"][seg] if x["day"] == op["day"]) if "day" in op else None
                if op["op"] == "set":
                    msg["text"] = op["text"]
                elif op["op"] == "drop":
                    mm["segments"][seg] = [x for x in mm["segments"][seg] if x["day"] != op["day"]]
                elif op["op"] == "sender":
                    mm["sender"] = op["text"]
            rr = check_messages(mm, validate_policy(base))
            ok = not rr["ready"] and any(case["expect"].lower() in b.lower() for b in rr["blocking"])
            check(f"broken message caught: {case['name']}", ok, rr["blocking"])

        # outputs
        lp = os.path.join(tmp, "list.csv")
        write_list(r, lp)
        out = list(csv.DictReader(open(lp, encoding="utf-8")))
        check("the list has one row per contactable person and no personal columns",
              len(out) == len(r["people"]) and set(out[0]) == {"application_id", "segment", "wave", "site",
                                                               "offer_roles", "send_pattern", "channel"})
        hp = os.path.join(tmp, "p.html")
        render(r, hp)
        check("html self-contained", "<script" not in open(hp, encoding="utf-8").read())
        t = text_plan(r)
        check("text states reply rates are assumptions", "assumptions" in t)
        check("text names the deletion job", "deletion job" in t)
        with contextlib.redirect_stdout(io.StringIO()):
            check("main: no mode exits 2", main([]) == 2)
            check("main: demo exits 0", main(["--demo"]) == 0)
            check("main: missing policy exits 3", main(["--pool", front, "--policy", os.path.join(tmp, "x")]) == 3)
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
            front = _data("frontline_pipeline_sample.csv")
            if not front:
                raise Refusal("the sample dataset is not in this copy of the skill.")
            argv = argv + ["--pool", front, "--policy", os.path.join(SAMPLE, "northline_policy.json")]
        if opt("--messages"):
            try:
                m = json.load(open(opt("--messages"), encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise Refusal(f"messages: cannot read it ({exc}).")
            res = check_messages(m, load_policy(opt("--policy")) if opt("--policy") else None)
            print(f"Messages: {res['segments']} segment(s).")
            print("  Ready." if res["ready"] else f"  NOT READY: {len(res['blocking'])} thing(s) to fix.")
            for b in res["blocking"]:
                print("  - " + b)
            return 0 if res["ready"] else 1
        if opt("--pool"):
            if not opt("--policy"):
                raise Refusal("--policy is needed: what you may send and what you are hiring for come first.")
            r = plan(opt("--pool"), load_policy(opt("--policy")), opt("--suppress"))
            print(text_plan(r))
            if opt("--list-out"):
                write_list(r, opt("--list-out"))
                print(f"\nContact list: {opt('--list-out')} (ids, segments and waves only)")
            if opt("--html"):
                render(r, opt("--html"))
            if opt("--json"):
                json.dump({k: v for k, v in r.items() if k != "people"}, open(opt("--json"), "w",
                                                                             encoding="utf-8"), indent=1, default=str)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, not a finding "
              "about your data.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
