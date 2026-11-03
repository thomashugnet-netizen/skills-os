#!/usr/bin/env python3
"""
Writes northline_calls.csv and northline_calls_expected.json: two months of
phone-screen calls at a fictional retailer, Northline, with known answers
planted in them. Deterministic: the same file every run. Standard library only.

    python3 generate_calls.py

What is planted:
- Speed. A candidate first called within 4 hours is still interested 82% of
  the time when reached; after a day, 42%. Frontline applicants apply to
  several employers in one sitting.
- When people answer. Evening 45%, morning 30%, afternoon 17%. The team makes
  most of its calls in the afternoon anyway.
- A text after a voicemail. 35% of candidates who get one text back. Only 40%
  of voicemails are followed by a text.
- Callers. C3 advances people and lets 40% of them go without a booked slot
  (others 8%). C4 ends 22% of answered calls without a decision (others 4%).
- Shows. 80% show when the interview is within 2 days of the call, 45% when
  it is further out.
- Limbo. About 7% of unreached candidates are dropped after one or two
  attempts, and 14 candidates are called four or five times.
"""

import csv
import datetime as dt
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
START = dt.datetime(2026, 9, 1)
END = dt.datetime(2026, 10, 31, 21, 0)
N = 1300
CALLERS = ["C1", "C2", "C3", "C4", "C5"]
ANSWER = {"morning": 0.30, "afternoon": 0.17, "evening": 0.45}
HABIT = [("afternoon", 0.6), ("morning", 0.27), ("evening", 0.13)]
HOURS = {"morning": (8, 12), "afternoon": (12, 17), "evening": (17, 21)}
BANDS = [((0.1, 1), 0.24), ((1, 4), 0.2), ((4, 24), 0.26), ((24, 72), 0.18), ((72, 120), 0.12)]
INTERESTED = [(1, 0.85), (4, 0.8), (24, 0.6), (72, 0.45), (10 ** 6, 0.35)]


def pick(rng, pairs):
    x, acc = rng.random(), 0.0
    for v, w in pairs:
        acc += w
        if x < acc:
            return v
    return pairs[-1][0]


def daypart(t):
    for name, (a, b) in HOURS.items():
        if a <= t.hour < b:
            return name
    return None


def at_daypart(rng, not_before, part):
    """The first time in `part` on or after not_before, at a random minute inside the part."""
    a, b = HOURS[part]
    day = not_before.replace(hour=0, minute=0, second=0, microsecond=0)
    for _ in range(10):
        t = day + dt.timedelta(hours=a + rng.random() * (b - a))
        if t >= not_before:
            return t.replace(second=0, microsecond=0)
        day += dt.timedelta(days=1)
    raise RuntimeError("no slot")


def fmt(t):
    return t.strftime("%Y-%m-%dT%H:%M") if t else ""


def main():
    rng = random.Random(20261101)
    rows, planted_limbo, planted_over = [], [], []
    for i in range(N):
        cid = f"A{104211 + i * 7}"
        caller = CALLERS[int(rng.random() * len(CALLERS))]
        applied = START + dt.timedelta(days=rng.random() * 57, hours=0)
        applied = applied.replace(hour=6 + int(rng.random() * 17), minute=int(rng.random() * 60), second=0,
                                  microsecond=0)
        lo, hi = pick(rng, BANDS)
        if hi <= 4:
            t = applied + dt.timedelta(hours=lo + rng.random() * (hi - lo))
            if daypart(t) is None:
                t = at_daypart(rng, t, "morning")
        else:
            t = at_daypart(rng, applied + dt.timedelta(hours=lo), pick(rng, HABIT))
        t = t.replace(second=0, microsecond=0)
        delay = (t - applied).total_seconds() / 3600
        interested = next(p for cut, p in INTERESTED if delay < cut)
        over = len(planted_over) < 14 and applied < dt.datetime(2026, 10, 10) and rng.random() < 0.05
        limit = 4 + int(rng.random() * 2) if over else 3
        dropped = not over and rng.random() < 0.07
        if dropped:
            limit = 1 + int(rng.random() * 2)
        att = []
        reached = None
        n = 0
        while n < limit and t <= END:
            n += 1
            if n == 1 and rng.random() < 0.02:
                att.append([t, "wrong_number", "", False])
                break
            part = daypart(t)
            if rng.random() < ANSWER[part]:
                att.append([t, "answered", "", False])
                reached = t
                break
            if rng.random() < 0.6:
                texted = rng.random() < 0.4
                att.append([t, "voicemail", "", texted])
                if texted and rng.random() < 0.35:
                    back = t + dt.timedelta(hours=0.5 + rng.random() * 9)
                    if back <= END:
                        att.append([back, "texted_back", "", False])
                        call = at_daypart(rng, back + dt.timedelta(hours=1), "evening")
                        if call <= END:
                            att.append([call, "answered", "", False])
                            reached = call
                        break
            else:
                att.append([t, "no_answer", "", False])
            t = at_daypart(rng, t + dt.timedelta(hours=18 + rng.random() * 30), pick(rng, HABIT))
        result, booked, iv, showed = "", False, None, ""
        if reached:
            if rng.random() < (0.22 if caller == "C4" else 0.04):
                result = "no_decision"
            elif rng.random() > interested:
                result = "withdrew"
            else:
                x = rng.random()
                result = ("declined_availability" if x < 0.15 else "redirected" if x < 0.25 else
                          "declined_prerequisite" if x < 0.28 else "declined_preview" if x < 0.35 else "advanced")
            if result in ("advanced", "redirected"):
                booked = rng.random() < (0.6 if caller == "C3" else 0.92)
                if booked:
                    near = rng.random() < 0.55
                    iv = reached + dt.timedelta(hours=(16 + rng.random() * 30) if near else (74 + rng.random() * 90))
                    iv = iv.replace(minute=0 if iv.minute < 30 else 30, second=0, microsecond=0)
                    if iv <= END:
                        showed = "yes" if rng.random() < (0.8 if near else 0.45) else "no"
            for a in att:
                if a[0] == reached:
                    a[2] = result
        if dropped and not reached and att and att[-1][1] != "wrong_number":
            planted_limbo.append((cid, att[-1][0], len([a for a in att if a[1] != "texted_back"])))
        tries = 0
        for a in att:
            if a[1] == "texted_back":
                break
            tries += 1
            if a[1] == "answered":
                break
        if over and tries > 3:
            planted_over.append(cid)
        for k, a in enumerate(att):
            last = a[0] == reached
            rows.append([cid, caller, fmt(applied), fmt(a[0]), a[1], a[2], "yes" if (last and booked) else "",
                         fmt(iv) if last else "", showed if last else "", "yes" if a[3] else ""])
    as_of = max(dt.datetime.fromisoformat(r[3]) for r in rows)
    limbo = sum(1 for cid, last, n in planted_limbo if n < 3 and (as_of - last).days >= 7)
    rows.sort(key=lambda r: (r[3], r[0]))
    with open(os.path.join(HERE, "northline_calls.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["candidate_id", "caller_id", "applied_at", "attempt_at", "outcome", "result", "booked",
                    "interview_at", "showed", "texted"])
        w.writerows(rows)
    exp = {"about": "Answers planted by generate_calls.py. The engine must find them; see the docstring there.",
           "max_attempts": 3, "best_daypart": "evening", "heavy_poor_daypart": "afternoon",
           "caller_flags": [["C3", "unbooked"], ["C4", "no_decision"]], "limbo": limbo,
           "over_max": len(planted_over), "candidates": len({r[0] for r in rows})}
    json.dump(exp, open(os.path.join(HERE, "northline_calls_expected.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(rows)} call rows, {exp['candidates']} candidates, limbo {limbo}, over-called {len(planted_over)}")


if __name__ == "__main__":
    main()
