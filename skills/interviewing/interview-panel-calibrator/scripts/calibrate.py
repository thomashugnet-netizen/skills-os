#!/usr/bin/env python3
"""
Reads a calibration exercise: several interviewers score the same written
answers alone, and this says where they disagree and why.

    python3 calibrate.py --scores scores.csv [--key key.csv] [--live live.csv]
                         [--scale 1-3] [--html report.html] [--json report.json]
    python3 calibrate.py --pack pack.json [--sheet sheet.html] [--key-out key.csv]
    python3 calibrate.py --demo [--html report.html]
    python3 calibrate.py --test

scores.csv  interviewer,item,score   one row per interviewer per answer scored.
            A blank score means "not scored" and is left out.
key.csv     item,intended[,borderline]   the level you wrote each answer at.
            Optional, but without it the instrument check cannot run.
live.csv    interviewer,site,interviews,advanced[,open_roles]   counts from
            real interviews, no candidate records. Optional.
pack.json   the calibration pack: questions, each with written answers, the
            level each was written at, and which one is the borderline.

What it reports:
  each answer   agree / one or two outside / split / scattered / borderline
  the anchors   split = two readings of the words; scatter on the middle
                level = the middle anchor says nothing; the group agrees with
                each other but not your key = the anchor is not what you meant
  each person   aligned / lenient / severe / range-restricted / inconsistent,
                measured against the others with that person left out, and
                with how much the number of answers can support
  live data     pass rate per interviewer against the pool, and whether pass
                rate rises with open roles (hiring pressure, not scoring)

Exit codes:
    0  report written
    1  pack not ready (with --pack)
    2  no mode given
    3  input refused
    4  the engine itself failed

It refuses files that carry emails or phone numbers, or a column that looks
like a candidate. Calibration needs scores, never candidate records.
Standard library only.
"""

import csv
import html
import io
import json
import math
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "references")
SAMPLE = os.path.join(REF, "sample")

MIN_RATERS = 3          # with two, a disagreement cannot say who is outside
MIN_ITEMS = 3
MIN_ITEMS_PERSON = 4    # below this, nothing is said about an individual
FIRM_ITEMS_PERSON = 8   # from here, a person's pattern is called consistent
MIN_LIVE_INTERVIEWS = 20

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\w)(\+?\d[\d\s().-]{8,}\d)(?!\w)")
CANDIDATE_COLS = re.compile(r"candidate|applicant|first.?name|last.?name|full.?name|e-?mail|phone|mobile|ssn|dob|birth",
                            re.I)


class Refusal(Exception):
    pass


# ------------------------------------------------------------------ reading

def read_csv(path, required, what):
    if not path or not os.path.exists(path):
        raise Refusal(f"{what}: file not found ({path}).")
    raw = open(path, "rb").read()
    text = None
    for enc in ("utf-8-sig", "utf-16"):
        try:
            text = raw.decode(enc)
            if enc == "utf-16" and not raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
                continue
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError:
            raise Refusal(f"{what}: the file is not readable text.")
    if EMAIL.search(text):
        raise Refusal(f"{what}: the file contains an email address. Calibration needs scores, not contact "
                      "details: remove the column and try again.")
    if PHONE.search(text):
        raise Refusal(f"{what}: the file contains what looks like a phone number. Remove it and try again.")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise Refusal(f"{what}: the file is empty.")
    header = [h.strip().lower().replace(" ", "_") for h in rows[0]]
    for h in header:
        if CANDIDATE_COLS.search(h):
            raise Refusal(f"{what}: column '{h}' looks like candidate information. The exercise uses written "
                          "answers with nothing identifying; remove the column and try again.")
    missing = [c for c in required if c not in header]
    if missing:
        raise Refusal(f"{what}: missing column(s) {', '.join(missing)}. Expected: {', '.join(required)}.")
    out = []
    for n, r in enumerate(rows[1:], start=2):
        r = r + [""] * (len(header) - len(r))
        out.append(({h: r[i].strip() for i, h in enumerate(header)}, n))
    return out


def parse_scale(s):
    m = re.fullmatch(r"\s*(\d)\s*-\s*(\d)\s*", s or "")
    if not m or int(m.group(1)) >= int(m.group(2)):
        raise Refusal("--scale must look like 1-3 or 1-5.")
    return int(m.group(1)), int(m.group(2))


def to_level(value, lo, hi, where):
    v = value.strip()
    if v == "":
        return None
    try:
        f = float(v.replace(",", "."))
    except ValueError:
        raise Refusal(f"{where}: score '{value}' is not a number.")
    if f != int(f):
        raise Refusal(f"{where}: score '{value}' is between two levels. Each answer gets one level.")
    f = int(f)
    if f < lo or f > hi:
        raise Refusal(f"{where}: score {f} is outside the scale {lo}-{hi}. Use --scale if your scale differs.")
    return f


def load_scores(path, lo, hi):
    rows = read_csv(path, ["interviewer", "item", "score"], "scores")
    data, seen, canon = {}, set(), {}
    for r, n in rows:
        who = canon.setdefault(("w", " ".join(r["interviewer"].split()).lower()), " ".join(r["interviewer"].split()))
        item = canon.setdefault(("i", " ".join(r["item"].split()).lower()), " ".join(r["item"].split()))
        if not who or not item:
            raise Refusal(f"scores row {n}: interviewer and item are both needed.")
        key = (who.lower(), item.lower())
        if key in seen:
            raise Refusal(f"scores row {n}: {who} scored {item} twice. Keep one score per person per answer.")
        seen.add(key)
        s = to_level(r["score"], lo, hi, f"scores row {n}")
        if s is not None:
            data.setdefault(item, {})[who] = s
    raters = sorted({w for d in data.values() for w in d})
    if len(raters) < MIN_RATERS:
        raise Refusal(f"scores: {len(raters)} interviewer(s). Calibration needs at least {MIN_RATERS}: with two, "
                      "a disagreement cannot say who is outside.")
    if len(data) < MIN_ITEMS:
        raise Refusal(f"scores: {len(data)} answer(s) scored. Use at least {MIN_ITEMS}, ideally 6 to 9.")
    return data, raters


def load_key(path, lo, hi, items):
    rows = read_csv(path, ["item", "intended"], "key")
    key = {}
    by_lower = {i.lower(): i for i in items}
    for r, n in rows:
        r["item"] = by_lower.get(" ".join(r["item"].split()).lower(), r["item"])
        lvl = to_level(r["intended"], lo, hi, f"key row {n}")
        if lvl is None:
            raise Refusal(f"key row {n}: no intended level for {r['item']}.")
        key[r["item"]] = {"intended": lvl,
                          "borderline": r.get("borderline", "").strip().lower() in ("yes", "y", "true", "1", "x")}
    unknown = sorted(set(key) - set(items))
    missing = sorted(set(items) - set(key))
    if missing:
        raise Refusal(f"key: no intended level for {', '.join(missing)}. Key every answer, or leave the key out.")
    return key, unknown


def load_live(path):
    rows = read_csv(path, ["interviewer", "site", "interviews", "advanced"], "live")
    out = []
    for r, n in rows:
        try:
            i, a = int(r["interviews"]), int(r["advanced"])
            o = int(r["open_roles"]) if r.get("open_roles", "") != "" else None
        except ValueError:
            raise Refusal(f"live row {n}: interviews, advanced and open_roles must be whole numbers.")
        if i < 0 or a < 0 or a > i or (o is not None and o < 0):
            raise Refusal(f"live row {n}: advanced must be between 0 and interviews.")
        out.append({"interviewer": r["interviewer"], "site": r["site"], "interviews": i, "advanced": a,
                    "open_roles": o})
    return out


# ------------------------------------------------------------------ maths

def median(xs):
    s = sorted(xs)
    n = len(s)
    return None if n == 0 else (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2)


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def wilson(k, n, z=1.645):
    if n == 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = mean(ra), mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return None if den == 0 else num / den


# ------------------------------------------------------------------ analysis

def item_pattern(scores):
    vals = list(scores.values())
    n = len(vals)
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    top_level, top = ordered[0]
    top_share = top / n
    second = ordered[1][1] / n if len(ordered) > 1 else 0.0
    # a tie for the top: no level is the group's reading
    tie = len(ordered) > 1 and ordered[1][1] == top
    if n < MIN_RATERS:
        kind = "too_few"
    elif top_share >= 0.8 and not tie:
        kind = "agree"
    elif top_share >= 0.6 and not tie:
        kind = "outliers"
    elif second >= 0.3 and top_share + second >= 0.8:
        kind = "split"
    else:
        kind = "scattered"
    outside = sorted(w for w, v in scores.items() if v != top_level) if kind in ("agree", "outliers") else []
    two = sorted(lv for lv, _ in ordered[:2])
    return {"n": n, "counts": {str(k): counts[k] for k in sorted(counts)}, "top_level": None if tie else top_level,
            "top_share": round(top_share, 2), "kind": kind, "outside": outside,
            "split_levels": two if kind == "split" else None, "median": median(vals)}


def analyse(data, raters, lo, hi, key=None, live=None):
    rng = hi - lo
    items = sorted(data)
    key = key or {}
    border = {i for i in items if key.get(i, {}).get("borderline")}

    per_item = {}
    for i in items:
        p = item_pattern(data[i])
        p["intended"] = key.get(i, {}).get("intended")
        p["borderline"] = i in border
        if p["borderline"]:
            p["reading"] = "borderline"
        per_item[i] = p

    findings = []

    # anchors: an even split between two readings is the words, not a person
    for i in items:
        p = per_item[i]
        if p["borderline"]:
            if p["kind"] in ("split", "scattered") and p["counts"]:
                lv = sorted(int(k) for k in p["counts"])
                if lv[-1] - lv[0] > 1:
                    findings.append({"type": "borderline_too_wide", "item": i,
                                     "say": f"{i} is the borderline, but scores ran from {lv[0]} to {lv[-1]}. A "
                                            "borderline should split between two neighbouring levels; this one "
                                            "reads as more than one kind of answer. Rewrite it."})
            continue
        if p["kind"] == "split":
            a, b = p["split_levels"]
            findings.append({"type": "anchor_split", "item": i, "levels": [a, b],
                             "say": f"{i}: the panel split between {a} and {b}. Two defensible readings of the "
                                    f"anchor: rewrite it so only one survives, then re-run this item. Coaching "
                                    f"individuals fixes nothing here, because nobody is wrong."})
        if key and p["kind"] in ("agree", "outliers") and p["top_level"] is not None \
                and p["intended"] is not None and p["top_level"] != p["intended"]:
            findings.append({"type": "key_mismatch", "item": i, "group": p["top_level"], "intended": p["intended"],
                             "say": f"{i}: the panel agrees on {p['top_level']}, you wrote it as a "
                                    f"{p['intended']}. They agree with each other and not with you: the anchor "
                                    f"does not say what you meant. A finding about the guide, not the panel."})

    # the middle anchor: agreement at the ends, scatter in the middle
    def level_of(i):
        p = per_item[i]
        return p["intended"] if p["intended"] is not None else p["median"]
    core = [i for i in items if i not in border]
    mid = [i for i in core if level_of(i) is not None and lo < level_of(i) < hi]
    ends = [i for i in core if level_of(i) in (lo, hi)]
    if len(mid) >= 2 and len(ends) >= 2:
        dis_mid = mean([1 - per_item[i]["top_share"] for i in mid])
        dis_end = mean([1 - per_item[i]["top_share"] for i in ends])
        if dis_mid - dis_end >= 0.2:
            findings.append({"type": "middle_anchor", "items": mid,
                             "disagreement_middle": round(dis_mid, 2), "disagreement_ends": round(dis_end, 2),
                             "say": f"Agreement at the ends, scatter in the middle: {round(dis_mid * 100)}% of "
                                    f"scores on the middle answers ({', '.join(mid)}) left the group's level, "
                                    f"against {round(dis_end * 100)}% at the ends. The middle anchor is "
                                    f"underspecified. Write what a middle answer sounds like, as a sentence a "
                                    f"candidate would say."})

    # people, each against the others with them left out
    people = {}
    for w in raters:
        pairs = []
        for i in core:
            if w in data[i]:
                others = [v for o, v in data[i].items() if o != w]
                if len(others) >= 2:
                    pairs.append((i, data[i][w], median(others)))
        n = len(pairs)
        info = {"items": n}
        if n < MIN_ITEMS_PERSON:
            info.update(kind="too_few", say=f"{w} scored {n} answer(s) outside the borderline: too few to say "
                                              f"anything about how they score.")
            people[w] = info
            continue
        diffs = [s - c for _, s, c in pairs]
        offset = mean(diffs)
        exact = mean([1.0 if abs(d) < 0.5 else 0.0 for d in diffs])
        top = [(s, c) for _, s, c in pairs if c >= hi - rng / 4]
        bot = [(s, c) for _, s, c in pairs if c <= lo + rng / 4]
        sep = gsep = None
        if top and bot:
            sep = mean([s for s, _ in top]) - mean([s for s, _ in bot])
            gsep = mean([c for _, c in top]) - mean([c for _, c in bot])
        rho = spearman([s for _, s, _ in pairs], [c for _, _, c in pairs])
        used = sorted({s for _, s, _ in pairs})
        info.update(offset=round(offset, 2), exact=round(exact, 2), used=used,
                    separation=None if sep is None else round(sep, 2),
                    group_separation=None if gsep is None else round(gsep, 2),
                    rho=None if rho is None else round(rho, 2))
        restricted = (gsep is not None and gsep >= rng / 2 and sep <= 0.35 * gsep) or \
                     (len(used) == 1 and gsep is not None and gsep >= rng / 2)
        if restricted:
            kind = "range_restricted"
        elif offset >= rng / 4:
            kind = "lenient"
        elif offset <= -rng / 4:
            kind = "severe"
        elif exact < 0.5:
            kind = "inconsistent"
        else:
            kind = "aligned"
        info["kind"] = kind
        info["range_tested"] = sep is not None
        info["confidence"] = "consistent" if n >= FIRM_ITEMS_PERSON else "tentative"
        info["outside_on"] = [i for i in core if w in per_item[i]["outside"]]
        people[w] = info

    # live data: pass rates, and whether they follow open roles
    live_out = None
    if live:
        by_w = {}
        for r in live:
            d = by_w.setdefault(r["interviewer"], {"interviews": 0, "advanced": 0, "sites": set()})
            d["interviews"] += r["interviews"]
            d["advanced"] += r["advanced"]
            d["sites"].add(r["site"])
        tot_i = sum(d["interviews"] for d in by_w.values())
        tot_a = sum(d["advanced"] for d in by_w.values())
        pool = tot_a / tot_i if tot_i else None
        rows = []
        for w, d in sorted(by_w.items()):
            n, k = d["interviews"], d["advanced"]
            lo_ci, hi_ci = wilson(k, n)
            flag = None
            if n >= MIN_LIVE_INTERVIEWS and pool is not None:
                if lo_ci > pool:
                    flag = "high"
                elif hi_ci < pool:
                    flag = "low"
            exercise = people.get(w, {}).get("kind")
            note = None
            if flag == "high" and exercise == "lenient":
                note = "is lenient on paper too, where vacancies play no part: both the bar and the pressure need work"
            elif flag == "low" and exercise == "severe":
                note = "is severe on paper too: the exercise and live interviews agree"
            elif flag and exercise in ("aligned", "inconsistent"):
                note = ("scores with the group on paper, so the live gap is not how they score: look at their "
                        "site's vacancies and who they get to interview before coaching anyone")
            rows.append({"note": note, "interviewer": w, "sites": sorted(d["sites"]), "interviews": n, "advanced": k,
                         "pass_rate": round(k / n, 2) if n else None, "ci90": [round(lo_ci, 2), round(hi_ci, 2)],
                         "flag": flag, "exercise": exercise,
                         "too_few": n < MIN_LIVE_INTERVIEWS})
        sites = {}
        for r in live:
            s = sites.setdefault(r["site"], {"interviews": 0, "advanced": 0, "open": []})
            s["interviews"] += r["interviews"]
            s["advanced"] += r["advanced"]
            if r["open_roles"] is not None:
                s["open"].append(r["open_roles"])
        pts = [(max(s["open"]), s["advanced"] / s["interviews"]) for s in sites.values()
               if s["open"] and s["interviews"] >= MIN_LIVE_INTERVIEWS]
        pressure = None
        if any(s["open"] for s in sites.values()):
            if len(pts) < 4:
                pressure = {"verdict": "too_few_sites", "sites": len(pts),
                            "say": f"Open roles given for {len(pts)} site(s) with enough interviews; at least 4 "
                                   f"are needed to see whether pass rate follows vacancies."}
            else:
                rho = spearman([o for o, _ in pts], [p for _, p in pts])
                v = "follows_vacancies" if rho is not None and rho >= 0.6 else "no_link_seen"
                pressure = {"verdict": v, "rho": None if rho is None else round(rho, 2), "sites": len(pts),
                            "say": (f"Across {len(pts)} sites, pass rate rises with open roles (rank correlation "
                                    f"{rho:.2f}). That is hiring pressure: staffing is part of the fix, and "
                                    f"coaching alone will not hold at the sites with the most open roles."
                                    if v == "follows_vacancies" else
                                    f"Across {len(pts)} sites, pass rate does not track open roles (rank "
                                    f"correlation {'n/a' if rho is None else f'{rho:.2f}'}). Differences "
                                    f"between interviewers are not explained by vacancies here.")}
        live_out = {"pool_pass_rate": None if pool is None else round(pool, 2), "interviewers": rows,
                    "pressure": pressure}

    return {"scale": [lo, hi], "raters": raters, "items": items, "per_item": per_item,
            "findings": findings, "people": people, "live": live_out, "keyed": bool(key),
            "data_points": sum(len(d) for d in data.values())}


PERSON_SAY = {
    "aligned": "scores with the group.",
    "lenient": "scores above the group, but in the same order: the information is intact, just offset. Show "
               "them where their bar sits against the group, with a worked answer at each level.",
    "severe": "scores below the group, but in the same order: the information is intact, just offset. Show "
              "them where their bar sits against the group, with a worked answer at each level.",
    "range_restricted": "gives strong and weak answers the same score. Offsetting recovers nothing, because the "
                        "distinctions were never recorded. Practise on the extremes until a low and a high answer "
                        "feel different; until their scores separate, they should not score alone.",
    "inconsistent": "is neither higher nor lower than the group on average, but disagrees with it in both "
                    "directions. Walk them through the anchors against these answers before reading anything "
                    "more into it.",
}


def person_line(w, p):
    if p["kind"] == "too_few":
        return p["say"]
    s = f"{w} {PERSON_SAY[p['kind']]}"
    detail = f" (offset {p['offset']:+.2f} levels"
    if p["separation"] is not None:
        detail += f", separates strong from weak by {p['separation']:.1f} against the group's {p['group_separation']:.1f}"
    else:
        detail += ", range not tested: no clearly strong and clearly weak answers both scored"
    detail += f", same level as the group on {round(p['exact'] * 100)}% of {p['items']} answers)"
    s += detail
    if p["confidence"] == "tentative":
        s += f". {p['items']} answers is a pattern, not proof: confirm it in the next round or a live double-score."
    return s


# ------------------------------------------------------------------ the pack

def check_pack(pack):
    if not isinstance(pack, dict) or not isinstance(pack.get("questions"), list) or not pack["questions"]:
        raise Refusal("pack: expected {\"questions\": [...]}, each with \"answers\".")
    lo, hi = parse_scale(pack.get("scale", "1-3"))
    problems, warnings, items = [], [], 0
    borderlines = 0
    blob = json.dumps(pack, ensure_ascii=False)
    if EMAIL.search(blob) or PHONE.search(blob):
        problems.append("The pack contains an email address or phone number. Strip anything identifying from "
                        "real answers.")
    for qi, q in enumerate(pack["questions"], 1):
        if not isinstance(q, dict) or not isinstance(q.get("answers"), list):
            raise Refusal(f"pack question {qi}: needs \"answers\".")
        qid = q.get("id") or f"Q{qi}"
        ans = q["answers"]
        items += len(ans)
        if len(ans) < 3:
            problems.append(f"{qid}: {len(ans)} answer(s). Three per question, at different levels.")
        levels = []
        for ai, a in enumerate(ans, 1):
            if not isinstance(a, dict) or "text" not in a or "intended" not in a:
                raise Refusal(f"pack {qid} answer {ai}: needs \"text\" and \"intended\".")
            if not isinstance(a["intended"], int) or not lo <= a["intended"] <= hi:
                raise Refusal(f"pack {qid} answer {ai}: \"intended\" must be a whole level from {lo} to {hi}.")
            levels.append(a["intended"])
            if a.get("borderline"):
                borderlines += 1
            words = len(str(a["text"]).split())
            if words < 15:
                problems.append(f"{qid} answer {ai}: {words} words. Write it as a candidate would say it, "
                                f"hesitations included; a one-liner is too easy to score.")
            if words > 250:
                warnings.append(f"{qid} answer {ai}: {words} words. Half a page is enough.")
        if len(ans) >= 3:
            if lo not in levels or hi not in levels:
                problems.append(f"{qid}: answers do not cover both ends ({lo} and {hi}).")
            core = [lv for lv, a in zip(levels, ans) if not a.get("borderline")]
            if len(core) >= 3 and (core == sorted(core) or core == sorted(core, reverse=True)):
                problems.append(f"{qid}: answers run in level order. Shuffle them, or the exercise becomes "
                                f"ranking, which everyone passes.")
    if borderlines == 0:
        problems.append("No answer is marked as the borderline. Add one that sits between two levels: it is "
                        "where the exercise teaches most.")
    if items > 12:
        warnings.append(f"{items} answers: more than half an hour. Four to nine fit in twenty to thirty minutes.")
    return {"ready": not problems, "problems": problems, "warnings": warnings, "answers": items,
            "borderlines": borderlines, "scale": [lo, hi]}


def pack_items(pack):
    out = []
    for qi, q in enumerate(pack["questions"], 1):
        qid = q.get("id") or f"Q{qi}"
        for ai, a in enumerate(q["answers"]):
            out.append({"item": f"{qid}-{chr(65 + ai)}", "question": q.get("text", ""), "text": a["text"],
                        "intended": a["intended"], "borderline": bool(a.get("borderline"))})
    return out


def write_key(pack, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item", "intended", "borderline"])
        for it in pack_items(pack):
            w.writerow([it["item"], it["intended"], "yes" if it["borderline"] else ""])


def render_sheet(pack, path):
    lo, hi = parse_scale(pack.get("scale", "1-3"))
    boxes = " ".join(f"<span class=box>{v}</span>" for v in range(lo, hi + 1))
    body = []
    for qi, q in enumerate(pack["questions"], 1):
        qid = q.get("id") or f"Q{qi}"
        body.append(f"<h2>{html.escape(qid)}. {html.escape(q.get('text', ''))}</h2>")
        if q.get("anchors"):
            body.append("<ul class=anchors>" + "".join(
                f"<li><b>{html.escape(str(k))}</b> {html.escape(str(v))}</li>" for k, v in q["anchors"].items())
                + "</ul>")
        for ai, a in enumerate(q["answers"]):
            body.append(f"<div class=ans><div class=id>{html.escape(qid)}-{chr(65 + ai)}</div>"
                        f"<p>{html.escape(str(a['text']))}</p><div class=score>Your score: {boxes}</div></div>")
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Calibration sheet</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px;color:#111}}
h1{{font-size:20px}}h2{{font-size:16px;margin-top:28px}}.rule{{border:1px solid #999;padding:10px 12px}}
.ans{{border-top:1px solid #ccc;padding:10px 0;page-break-inside:avoid}}.id{{font-weight:600}}
.box{{display:inline-block;border:1px solid #333;width:28px;text-align:center;margin-right:6px}}
.anchors{{color:#333}}@media print{{body{{margin:0}}}}</style>
<h1>Calibration sheet{(': ' + html.escape(pack['title'])) if pack.get('title') else ''}</h1>
<p class=rule><b>Score alone, in writing, before anyone speaks.</b> One level per answer. Hand the sheet in before
the scores are shown. Name: ____________________</p>
{''.join(body)}</html>"""
    open(path, "w", encoding="utf-8").write(doc)


# ------------------------------------------------------------------ output

KIND_WORD = {"agree": "agree", "outliers": "one or two outside", "split": "split", "scattered": "scattered",
             "too_few": "too few scores", "borderline": "borderline"}


def text_report(r):
    lo, hi = r["scale"]
    out = [f"Calibration: {len(r['raters'])} interviewers, {len(r['items'])} answers, {r['data_points']} scores "
           f"on a {lo}-{hi} scale."]
    if not r["keyed"]:
        out.append("No key given: the check that the panel agrees with what you meant could not run.")
    out.append("")
    out.append("Answers")
    for i in r["items"]:
        p = r["per_item"][i]
        word = "borderline" if p["borderline"] else KIND_WORD[p["kind"]]
        counts = "  ".join(f"{k}:{v}" for k, v in p["counts"].items())
        extra = f" (written as {p['intended']})" if p["intended"] is not None else ""
        outs = f"  outside: {', '.join(p['outside'])}" if p["outside"] and p["kind"] == "outliers" else ""
        out.append(f"  {i:<10} {word:<20} {counts}{extra}{outs}")
    out.append("")
    out.append("What to fix in the guide")
    guide = [f for f in r["findings"]]
    out += [f"  - {f['say']}" for f in guide] or ["  - Nothing: no anchor split, no middle scatter, no answer the "
                                                 "panel reads differently from your key."]
    out.append("")
    out.append("Interviewers")
    for w in r["raters"]:
        out.append(f"  - {person_line(w, r['people'][w])}")
    if r["live"]:
        lv = r["live"]
        out.append("")
        out.append(f"Live interviews (pool pass rate {round(lv['pool_pass_rate'] * 100)}%)")
        for row in lv["interviewers"]:
            note = {"high": "above the pool", "low": "below the pool", None: "within the pool"}[row["flag"]]
            if row["too_few"]:
                note = f"too few interviews to compare (under {MIN_LIVE_INTERVIEWS})"
            ex = f"; exercise: {row['exercise'].replace('_', '-')}" if row["exercise"] else ""
            out.append(f"  {row['interviewer']:<16} {row['advanced']}/{row['interviews']} advanced "
                       f"({round(row['pass_rate'] * 100)}%, 90% range {round(row['ci90'][0] * 100)}-"
                       f"{round(row['ci90'][1] * 100)}%): {note}{ex}")
            if row["note"]:
                out.append(f"  {'':<16} {row['interviewer']} {row['note']}.")
        if lv["pressure"]:
            out.append(f"  {lv['pressure']['say']}")
    out.append("")
    out.append(f"What this cannot tell you: {r['data_points']} scores show whether the panel agrees, not whether it "
               "is right. Agreement is consistency, not validity: testing that needs scores matched against "
               "90-day retention.")
    return "\n".join(out)


def render_report(r, path):
    e = html.escape
    rows = []
    for i in r["items"]:
        p = r["per_item"][i]
        word = "borderline" if p["borderline"] else KIND_WORD[p["kind"]]
        lo, hi = r["scale"]
        bars = "".join(f"<td>{p['counts'].get(str(v), '')}</td>" for v in range(lo, hi + 1))
        rows.append(f"<tr><td>{e(i)}</td><td>{'' if p['intended'] is None else p['intended']}</td>{bars}"
                    f"<td class=k-{p['kind']}>{e(word)}</td></tr>")
    lo, hi = r["scale"]
    heads = "".join(f"<th>{v}</th>" for v in range(lo, hi + 1))
    fixes = "".join(f"<li>{e(f['say'])}</li>" for f in r["findings"]) or "<li>Nothing to fix in the guide.</li>"
    people = "".join(f"<li>{e(person_line(w, r['people'][w]))}</li>" for w in r["raters"])
    live = ""
    if r["live"]:
        lv = r["live"]
        lr = "".join(f"<tr><td>{e(x['interviewer'])}</td><td>{x['advanced']}/{x['interviews']}</td>"
                     f"<td>{round(x['pass_rate'] * 100)}%</td><td>{e(x['flag'] or ('too few' if x['too_few'] else 'within'))}</td></tr>"
                     for x in lv["interviewers"])
        live = (f"<h2>Live interviews</h2><p>Pool pass rate {round(lv['pool_pass_rate'] * 100)}%.</p>"
                f"<table><tr><th>Interviewer</th><th>Advanced</th><th>Rate</th><th>Against the pool</th></tr>{lr}"
                f"</table>" + (f"<p>{e(lv['pressure']['say'])}</p>" if lv["pressure"] else ""))
    doc = f"""<!doctype html><html lang=en><meta charset=utf-8><title>Calibration report</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px;color:#111}}
table{{border-collapse:collapse}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:left}}
.k-split,.k-scattered{{background:#fde2e2}}.k-outliers{{background:#fff3cd}}.k-agree{{background:#e3f4e1}}</style>
<h1>Calibration report</h1>
<p>{len(r['raters'])} interviewers, {len(r['items'])} answers, {r['data_points']} scores.</p>
<h2>Answers</h2><table><tr><th>Answer</th><th>Written as</th>{heads}<th>Pattern</th></tr>{''.join(rows)}</table>
<h2>What to fix in the guide</h2><ul>{fixes}</ul>
<h2>Interviewers</h2><ul>{people}</ul>{live}
<p><i>Agreement is consistency, not validity. This shows whether the panel scores alike, not whether it picks
people who stay.</i></p></html>"""
    open(path, "w", encoding="utf-8").write(doc)


def run(scores, key=None, live=None, scale="1-3"):
    lo, hi = parse_scale(scale)
    data, raters = load_scores(scores, lo, hi)
    k = None
    if key:
        k, _ = load_key(key, lo, hi, list(data))
    lv = load_live(live) if live else None
    return analyse(data, raters, lo, hi, k, lv)


# ------------------------------------------------------------------ tests

def run_tests():
    import shutil
    import tempfile
    passed = failed = 0

    def check(name, ok):
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            print("FAIL " + name)

    tmp = tempfile.mkdtemp(prefix="ipc-")

    def write(name, text):
        p = os.path.join(tmp, name)
        open(p, "w", encoding="utf-8").write(text)
        return p

    def rows_to_csv(name, rows, header="interviewer,item,score"):
        return write(name, header + "\n" + "\n".join(",".join(str(c) for c in r) for r in rows) + "\n")

    try:
        # 1. the sample comes back exactly as planted
        exp = json.load(open(os.path.join(SAMPLE, "northline_expected.json"), encoding="utf-8"))
        r = run(os.path.join(SAMPLE, "northline_scores.csv"), os.path.join(SAMPLE, "northline_key.csv"),
                os.path.join(SAMPLE, "northline_live.csv"))
        kinds = {w: p["kind"] for w, p in r["people"].items()}
        check("sample: every interviewer classified as planted", kinds == exp["people"])
        got = sorted((f["type"], f.get("item", ",".join(f.get("items", [])))) for f in r["findings"])
        want = sorted((t, i) for t, i in exp["findings"])
        check(f"sample: guide findings exactly as planted (got {got})", got == want)
        check("sample: item patterns as planted",
              {i: r["per_item"][i]["kind"] for i in exp["items"]} == exp["items"])
        flags = {x["interviewer"]: x["flag"] for x in r["live"]["interviewers"]}
        check(f"sample: live flags as planted (got {flags})", flags == exp["live_flags"])
        check("sample: hiring pressure found", r["live"]["pressure"]["verdict"] == exp["pressure"])
        notes = {x["interviewer"]: bool(x["note"]) for x in r["live"]["interviewers"]}
        check("sample: live notes only where paper and live meet", notes == exp["live_notes"])
        t = text_report(r)
        check("sample: text says consistency is not validity", "not validity" in t)

        # pack
        pack = json.load(open(os.path.join(SAMPLE, "northline_pack.json"), encoding="utf-8"))
        pr = check_pack(pack)
        check(f"sample pack is ready ({pr['problems']})", pr["ready"])
        kp = os.path.join(tmp, "k.csv")
        write_key(pack, kp)
        check("key written from the pack matches the sample key",
              open(kp, encoding="utf-8").read().replace("\r\n", "\n")
              == open(os.path.join(SAMPLE, "northline_key.csv"), encoding="utf-8").read().replace("\r\n", "\n"))
        sp = os.path.join(tmp, "s.html")
        render_sheet(pack, sp)
        sheet = open(sp, encoding="utf-8").read()
        check("sheet: every answer on it", all(html.escape(a["text"]) in sheet
                                               for q in pack["questions"] for a in q["answers"]))
        check("sheet: never shows the intended level", "intended" not in sheet and "borderline" not in sheet.lower())
        check("sheet: tells people to score alone first", "before anyone speaks" in sheet)

        # broken packs, one fault each
        import copy
        def broken(fn):
            p = copy.deepcopy(pack)
            fn(p)
            return check_pack(p)
        b = broken(lambda p: p["questions"][0]["answers"].sort(key=lambda a: a["intended"]))
        check("pack: answers in level order is caught", not b["ready"] and any("level order" in x for x in b["problems"]))
        b = broken(lambda p: [a.pop("borderline", None) for q in p["questions"] for a in q["answers"]])
        check("pack: no borderline is caught", not b["ready"] and any("borderline" in x for x in b["problems"]))
        b = broken(lambda p: p["questions"][1]["answers"].pop())
        check("pack: two answers is caught", not b["ready"])
        b = broken(lambda p: p["questions"][0]["answers"][0].update(text="Yes I am always on time."))
        check("pack: a one-liner is caught", not b["ready"] and any("words" in x for x in b["problems"]))
        b = broken(lambda p: p["questions"][0]["answers"][0].update(
            text=p["questions"][0]["answers"][0]["text"] + " call me on 555-201-3344"))
        check("pack: a phone number is caught", not b["ready"])
        b = broken(lambda p: [a.update(intended=2) for a in p["questions"][2]["answers"]])
        check("pack: no ends covered is caught", not b["ready"] and any("both ends" in x for x in b["problems"]))
        for bad, name in ((["x"], "a list"), ({"questions": []}, "no questions"),
                          ({"questions": [{"answers": [{"text": "a"}]}]}, "answer without level"),
                          ({"questions": [{"answers": [{"text": "a", "intended": 7}]}]}, "level off scale"),
                          ({"questions": [{"answers": "x"}]}, "answers not a list")):
            try:
                check_pack(bad)
                check(f"pack refused: {name}", False)
            except Refusal:
                check(f"pack refused: {name}", True)

        # 2. a panel that agrees produces no finding at all
        good = [(w, f"I{i}", lv) for w in "ABCDE" for i, lv in enumerate([1, 2, 3, 1, 2, 3, 2, 1])]
        r = run(rows_to_csv("good.csv", good))
        check("agreeing panel: no guide finding", r["findings"] == [])
        check("agreeing panel: everyone aligned", all(p["kind"] == "aligned" for p in r["people"].values()))

        # 3. a lenient person is lenient, not range-restricted; order preserved
        rows = good + [("L", f"I{i}", min(3, lv + 1)) for i, lv in enumerate([1, 2, 3, 1, 2, 3, 2, 1])]
        r = run(rows_to_csv("len.csv", rows))
        check("lenient detected", r["people"]["L"]["kind"] == "lenient")
        rows = good + [("S", f"I{i}", max(1, lv - 1)) for i, lv in enumerate([1, 2, 3, 1, 2, 3, 2, 1])]
        check("severe detected", run(rows_to_csv("sev.csv", rows))["people"]["S"]["kind"] == "severe")
        rows = good + [("R", f"I{i}", 2) for i in range(8)]
        check("all-2s is range-restricted, not aligned", run(rows_to_csv("rr.csv", rows))["people"]["R"]["kind"]
              == "range_restricted")
        rows = good + [("R", f"I{i}", 3) for i in range(8)]
        check("all-3s is range-restricted, not lenient", run(rows_to_csv("rr3.csv", rows))["people"]["R"]["kind"]
              == "range_restricted")
        flip = {1: 3, 2: 2, 3: 1}
        rows = good + [("X", f"I{i}", flip[lv]) for i, lv in enumerate([1, 2, 3, 1, 2, 3, 2, 1])]
        check("reversed scorer is not called aligned", run(rows_to_csv("rev.csv", rows))["people"]["X"]["kind"]
              in ("range_restricted", "inconsistent"))

        # 4. an even split is the anchor; a lone dissenter is a person
        rows = [(w, "I0", 1 if w in "ABC" else 2) for w in "ABCDEF"] + \
               [(w, f"I{i}", lv) for w in "ABCDEF" for i, lv in enumerate([1, 3, 2, 3, 1], start=1)]
        r = run(rows_to_csv("split.csv", rows))
        check("even split is an anchor finding", any(f["type"] == "anchor_split" and f["item"] == "I0"
                                                     for f in r["findings"]))
        rows = [(w, "I0", 3 if w == "F" else 1) for w in "ABCDEF"] + rows[6:]
        r = run(rows_to_csv("lone.csv", rows))
        check("lone dissenter is not an anchor finding", not any(f["type"] == "anchor_split" for f in r["findings"]))
        check("lone dissenter is named outside", r["per_item"]["I0"]["outside"] == ["F"])

        # 5. a key the panel disagrees with together is the instrument
        rows = [(w, f"I{i}", lv) for w in "ABCDE" for i, lv in enumerate([1, 2, 3, 3, 1, 2])]
        key = write("key.csv", "item,intended\nI0,1\nI1,2\nI2,3\nI3,2\nI4,1\nI5,2\n")
        r = run(rows_to_csv("km.csv", rows), key)
        check("group-against-key is a key mismatch on I3 only",
              [(f["type"], f["item"]) for f in r["findings"]] == [("key_mismatch", "I3")])

        # 6. scatter in the middle only
        rows = []
        mids = {"A": 1, "B": 2, "C": 3, "D": 2, "E": 1, "F": 3}
        for w in "ABCDEF":
            for i, lv in enumerate([1, 3, 1, 3]):
                rows.append((w, f"E{i}", lv))
            rows.append((w, "M0", mids[w]))
            rows.append((w, "M1", {"A": 2, "B": 3, "C": 1, "D": 2, "E": 3, "F": 1}[w]))
        key = write("mkey.csv", "item,intended\nE0,1\nE1,3\nE2,1\nE3,3\nM0,2\nM1,2\n")
        r = run(rows_to_csv("mid.csv", rows), key)
        check("middle scatter is a middle-anchor finding", any(f["type"] == "middle_anchor" for f in r["findings"]))
        check("middle scatter is not blamed on anyone", all(p["kind"] in ("aligned", "inconsistent", "too_few")
                                                           for p in r["people"].values()))

        # 7. noise: random scorers must not produce confident individual verdicts
        rng = random.Random(7)
        confident = 0
        for trial in range(200):
            rows = [(w, f"I{i}", rng.randint(1, 3)) for w in "ABCDE" for i in range(6)]
            r = run(rows_to_csv("noise.csv", rows))
            confident += sum(1 for p in r["people"].values() if p.get("confidence") == "consistent")
        check("6 answers never yields a 'consistent' verdict", confident == 0)

        # 8. small panels are honest
        rows = [(w, f"I{i}", lv) for w in "ABCD" for i, lv in enumerate([1, 2, 3])]
        r = run(rows_to_csv("small.csv", rows))
        check("3 answers: nobody is judged", all(p["kind"] == "too_few" for p in r["people"].values()))

        # 9. borderline items: a neighbouring split is expected, a wide one is not
        rows = [(w, f"I{i}", lv) for w in "ABCDEF" for i, lv in enumerate([1, 3, 2, 1, 3])] + \
               [(w, "B0", 2 if w in "ABC" else 3) for w in "ABCDEF"]
        key = write("bkey.csv", "item,intended,borderline\nI0,1,\nI1,3,\nI2,2,\nI3,1,\nI4,3,\nB0,2,yes\n")
        r = run(rows_to_csv("bl.csv", rows), key)
        check("borderline neighbouring split is not a finding", r["findings"] == [])
        rows = rows[:30] + [(w, "B0", {"A": 1, "B": 3, "C": 1, "D": 3, "E": 2, "F": 3}[w]) for w in "ABCDEF"]
        r = run(rows_to_csv("bl2.csv", rows), key)
        check("borderline running 1 to 3 is a finding", any(f["type"] == "borderline_too_wide" for f in r["findings"]))

        # 10. refusals, each with the reason
        def refused(name, text, key=None, live=None, scale="1-3"):
            try:
                run(write(name, text), key, live, scale)
                return False
            except Refusal:
                return True
        base = "interviewer,item,score\n" + "\n".join(f"{w},I{i},{lv}" for w in "ABC"
                                                       for i, lv in enumerate([1, 2, 3, 2]))
        check("refuses an email", refused("e.csv", base + "\nann@acme.com,I9,2\n"))
        check("refuses a phone number", refused("p.csv", base + "\nA,I9 call 555-201-3344,2\n"))
        check("refuses a candidate column", refused("c.csv", "interviewer,item,score,candidate\nA,I0,1,Jo\n"))
        check("refuses a score off the scale", refused("o.csv", base + "\nA,I9,4\n"))
        check("refuses a half score", refused("h.csv", base + "\nA,I9,2.5\n"))
        check("refuses a word score", refused("w.csv", base + "\nA,I9,good\n"))
        check("refuses a duplicate score", refused("d.csv", base + "\nA,I0,2\n"))
        check("refuses two interviewers", refused("two.csv", "interviewer,item,score\nA,I0,1\nB,I0,1\nA,I1,2\n"
                                                                 "B,I1,2\nA,I2,3\nB,I2,3\n"))
        check("refuses a missing column", refused("m.csv", "who,item,score\nA,I0,1\n"))
        check("refuses an empty file", refused("z.csv", ""))
        try:
            run(os.path.join(tmp, "does-not-exist.csv"))
            check("refuses a missing file", False)
        except Refusal:
            check("refuses a missing file", True)
        mixed = base + "\na , i0 ,1\n"
        check("same item and person in another case is a duplicate", refused("mx.csv", mixed))
        r = run(write("cs.csv", base.replace("A,I1", "a,i1")))
        check("case differences merge into one item and one person",
              len(r["items"]) == 4 and len(r["raters"]) == 3)
        check("refuses a key that misses an item",
              refused("k1.csv", base, key=write("kk.csv", "item,intended\nI0,1\n")))
        check("refuses live with advanced above interviews",
              refused("l1.csv", base, live=write("ll.csv", "interviewer,site,interviews,advanced\nA,S1,5,6\n")))
        check("accepts 1-5 with --scale", not refused("f.csv", base.replace(",3\n", ",5\n"), scale="1-5"))
        check("refuses a bad --scale", refused("bs.csv", base, scale="3-1"))

        # 11. formats people actually have
        semi = base.replace(",", ";")
        check("reads semicolons", run(write("semi.csv", semi))["data_points"] == 12)
        p16 = os.path.join(tmp, "u16.csv")
        open(p16, "wb").write(base.encode("utf-16"))
        check("reads UTF-16", run(p16)["data_points"] == 12)
        check("reads '2.0' as 2", run(write("dec.csv", base.replace(",2\n", ",2.0\n")))["data_points"] == 12)
        check("blank score is left out", run(write("bl.csv", base + "\nA,I9,\nB,I9,1\nC,I9,1\n"))
              ["per_item"]["I9"]["n"] == 2)
        check("headers in another case and with spaces",
              run(write("hd.csv", base.replace("interviewer,item,score", "Interviewer, Item ,SCORE")))
              ["data_points"] == 12)

        # 12. live: too few interviews is never flagged; pressure needs 4 sites
        live = write("lv.csv", "interviewer,site,interviews,advanced,open_roles\nA,S1,10,10,5\nB,S2,10,1,0\n"
                               "C,S3,10,5,1\n")
        r = run(write("b.csv", base), live=live)
        check("live: under 20 interviews is never flagged", all(x["flag"] is None for x in r["live"]["interviewers"]))
        check("live: 3 sites is too few for pressure", r["live"]["pressure"]["verdict"] == "too_few_sites")

        # 13. outputs
        hp = os.path.join(tmp, "r.html")
        r = run(os.path.join(SAMPLE, "northline_scores.csv"), os.path.join(SAMPLE, "northline_key.csv"),
                os.path.join(SAMPLE, "northline_live.csv"))
        render_report(r, hp)
        body = open(hp, encoding="utf-8").read()
        check("html: self-contained", "<script" not in body and "http" not in body)
        check("html: names every interviewer", all(html.escape(w) in body for w in r["raters"]))
        check("json: serialisable", bool(json.dumps(r)))
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            code = main(["--scores", os.path.join(tmp, "nope.csv")])
            none = main([])
            demo = main(["--demo", "--json", os.path.join(tmp, "d.json")])
            packc = main(["--pack", os.path.join(SAMPLE, "northline_pack.json"),
                          "--sheet", os.path.join(tmp, "sh.html")])
        check("main: refusal exits 3", code == 3)
        check("main: no mode exits 2", none == 2)
        check("main: demo exits 0 and writes json", demo == 0 and os.path.exists(os.path.join(tmp, "d.json")))
        check("main: ready pack exits 0 and writes the sheet", packc == 0 and os.path.exists(os.path.join(tmp, "sh.html")))

        # 14. a whole panel scoring above the key is the guide, not five lenient people
        rows = [(w, f"I{i}", min(3, lv + 1)) for w in "ABCDE" for i, lv in enumerate([1, 2, 1, 2, 1, 2])]
        key = write("allkey.csv", "item,intended\nI0,1\nI1,2\nI2,1\nI3,2\nI4,1\nI5,2\n")
        r = run(rows_to_csv("all.csv", rows), key)
        check("whole panel above the key: nobody called lenient",
              not any(p["kind"] == "lenient" for p in r["people"].values()))
        check("whole panel above the key: every answer is a key mismatch",
              sorted(f["item"] for f in r["findings"] if f["type"] == "key_mismatch") == [f"I{i}" for i in range(6)])

        # 15. one person outside on most answers is that person, and the anchors are not blamed
        rows = [(w, f"I{i}", lv) for w in "ABCDE" for i, lv in enumerate([1, 3, 1, 3, 2, 2])] + \
               [("Z", f"I{i}", lv) for i, lv in enumerate([3, 1, 2, 1, 3, 1])]
        r = run(rows_to_csv("z.csv", rows))
        check("a lone contrarian is not an anchor finding", r["findings"] == [])
        check("a lone contrarian is not called aligned", r["people"]["Z"]["kind"] != "aligned")
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
            argv = argv + ["--scores", os.path.join(SAMPLE, "northline_scores.csv"),
                           "--key", os.path.join(SAMPLE, "northline_key.csv"),
                           "--live", os.path.join(SAMPLE, "northline_live.csv")]
        if opt("--pack"):
            try:
                pack = json.load(open(opt("--pack"), encoding="utf-8-sig"))
            except (OSError, ValueError) as exc:
                raise Refusal(f"pack: cannot read it ({exc}).")
            res = check_pack(pack)
            print(f"Pack: {res['answers']} answers, {res['borderlines']} borderline.")
            for p in res["problems"]:
                print("  NOT READY  " + p)
            for w in res["warnings"]:
                print("  NOTE       " + w)
            if res["ready"]:
                print("  Ready.")
                if opt("--sheet"):
                    render_sheet(pack, opt("--sheet"))
                    print(f"  Scoring sheet: {opt('--sheet')}")
                if opt("--key-out"):
                    write_key(pack, opt("--key-out"))
                    print(f"  Key (keep it from the panel): {opt('--key-out')}")
            return 0 if res["ready"] else 1
        if opt("--scores"):
            r = run(opt("--scores"), opt("--key"), opt("--live"), opt("--scale") or "1-3")
            print(text_report(r))
            if opt("--html"):
                render_report(r, opt("--html"))
            if opt("--json"):
                json.dump(r, open(opt("--json"), "w", encoding="utf-8"), indent=1)
            return 0
    except Refusal as exc:
        print("REFUSED: " + str(exc))
        return 3
    except Exception as exc:
        print(f"ERROR: the engine failed ({type(exc).__name__}: {exc}). This is a bug in the engine, "
              "not a finding about your panel.")
        return 4
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
