#!/usr/bin/env python3
"""
Writes northline_sends.csv and northline_sends_expected.json: two months of
nudge messages at a fictional retailer, Northline, across four stalled stages,
with known answers planted in them. Deterministic. Standard library only.

    python3 generate_log.py

What is planted:
- applied_no_screen (SMS, 4 messages): after message 4, 2% act and 8% opt out.
  The fourth message loses more people than it moves. 12 candidates are
  re-enrolled and get a fifth message.
- screen_no_interview (SMS, 3 messages): 7 messages go to people who had
  already opted out, and 25 times message 2 goes out two hours after message 1.
- documents_missing (email, 3 messages): the upload happens in another system,
  so 40% of the people who upload keep getting reminders.
- start_no_shift (SMS, 2 messages): every message goes out at 07:15.
- Everywhere: 3% of the people who act do so in the half hour before the next
  message, which still goes out. That is sync lag, inside the one-hour grace,
  and must not be read as a leak.

simulate(plants=False) builds the same world with every message equally
useful, no leaks, no night sends and no bugs, for the suite's null test.
"""

import csv
import datetime as dt
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
START = dt.datetime(2026, 9, 1)
END = dt.datetime(2026, 10, 31, 20, 0)

SEQUENCES = [
    # name, channel, candidates, send days, act rate per message, opt-out rate per message
    ("applied_no_screen", "sms", 900, [0, 2, 5, 9], [0.25, 0.14, 0.07, 0.02], [0.01, 0.02, 0.03, 0.08]),
    ("screen_no_interview", "sms", 500, [0, 2, 5], [0.30, 0.15, 0.08], [0.01, 0.015, 0.02]),
    ("documents_missing", "email", 400, [0, 3, 7], [0.35, 0.20, 0.12], [0.0, 0.005, 0.01]),
    ("start_no_shift", "sms", 300, [0, 3], [0.40, 0.20], [0.01, 0.02]),
]
NULL_ACT, NULL_OPT = 0.10, 0.02


def fmt(t):
    return t.strftime("%Y-%m-%dT%H:%M") if t else ""


def simulate(plants=True, seed=20261103):
    rng = random.Random(seed)
    rows = []
    counts = {"too_fast": 0, "after_opt": 0, "over_cap": 0}
    cid = 500000
    for name, channel, n, days, act, opt in SEQUENCES:
        for _ in range(n):
            cid += 13
            enrolled = START + dt.timedelta(days=int(rng.random() * 55))
            hour, minute = (7, 15) if (plants and name == "start_no_shift") else (9 + int(rng.random() * 8),
                                                                                  int(rng.random() * 60))
            plan = [enrolled.replace(hour=hour, minute=minute) + dt.timedelta(days=d) for d in days]
            if plants and name == "screen_no_interview" and counts["too_fast"] < 25 and rng.random() < 0.15:
                plan[1] = plan[0] + dt.timedelta(hours=2)
            if plants and name == "applied_no_screen" and counts["over_cap"] < 12 and rng.random() < 0.06:
                plan.append(plan[-1] + dt.timedelta(days=4))
            leak = plants and name == "documents_missing" and rng.random() < 0.4
            acted = opted = None
            sent = []
            for i, t in enumerate(plan):
                if t > END:
                    break
                if acted and acted <= t and not leak:
                    break
                if opted and opted <= t and not (plants and name == "screen_no_interview" and
                                                 counts["after_opt"] < 7 and rng.random() < 0.7):
                    break
                sent.append((i + 1, t))
                if acted or opted:
                    continue
                k = min(i, len(act) - 1)
                pa, po = (act[k], opt[k]) if plants else (NULL_ACT, NULL_OPT)
                gap = (plan[i + 1] - t) if i + 1 < len(plan) else dt.timedelta(days=7)
                x = rng.random()
                if x < pa:
                    if i + 1 < len(plan) and rng.random() < 0.03:
                        # sync lag: they act half an hour before the next message, which goes anyway
                        acted = plan[i + 1] - dt.timedelta(minutes=5 + rng.random() * 25)
                        if plan[i + 1] <= END:
                            sent.append((i + 2, plan[i + 1]))
                        break
                    acted = t + gap * (0.05 + rng.random() * 0.85)
                elif x < pa + po:
                    opted = t + min(gap * 0.9, dt.timedelta(minutes=10 + rng.random() * 600))
            # what was actually sent, counted the way anyone reading the log would count it
            counts["too_fast"] += sum(1 for (_, a), (_, b) in zip(sent, sent[1:]) if b - a < dt.timedelta(hours=20))
            counts["over_cap"] += 1 if len(sent) > (5 if channel == "email" else 4) else 0
            counts["after_opt"] += sum(1 for _, t in sent if opted and t > opted)
            for step, t in sent:
                rows.append([f"K{cid}", name, str(step), fmt(t), channel,
                             fmt(acted) if acted and acted <= END else "", fmt(opted) if opted and opted <= END else ""])
    rows.sort(key=lambda r: (r[3], r[0]))
    header = ["candidate_id", "sequence", "step", "sent_at", "channel", "acted_at", "opted_out_at"]
    expected = {
        "about": "Answers planted by generate_log.py. The engine must find them; see the docstring there.",
        "flagged_steps": [["applied_no_screen", 4]] if plants else [],
        "leaky": ["documents_missing"] if plants else [],
        "after_opt_out": {"screen_no_interview": counts["after_opt"]} if counts["after_opt"] else {},
        "quiet": ["start_no_shift"] if plants else [],
        "too_fast": {"screen_no_interview": counts["too_fast"]} if counts["too_fast"] else {},
        "over_cap": {"applied_no_screen": counts["over_cap"]} if counts["over_cap"] else {},
        "candidates": len({r[0] for r in rows}),
    }
    return [header] + rows, expected


def main():
    rows, expected = simulate()
    with open(os.path.join(HERE, "northline_sends.csv"), "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(rows)
    json.dump(expected, open(os.path.join(HERE, "northline_sends_expected.json"), "w", encoding="utf-8"), indent=1)
    print(f"{len(rows) - 1} messages, {expected['candidates']} candidates, planted: "
          f"{json.dumps({k: v for k, v in expected.items() if k not in ('about', 'candidates')})}")


if __name__ == "__main__":
    main()
