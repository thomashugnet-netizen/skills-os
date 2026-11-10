#!/usr/bin/env python3
"""
Generates the planted sample for resume-free-triage-rubric.

    python3 references/sample/generate.py            # writes the sample next to this file
    python3 references/sample/generate.py --seed 7 --out /tmp/x

Marlow Freight is fictional: four warehouses hiring Warehouse Associates, no
resume asked for, 3,200 applications from 15 June to 30 October 2026. The
company's past hires have a 30-day outcome, so the rubric's weights can be
checked against who stayed.

What is planted, and what the engine must find (marlow_expected.json):

- Staying 30 days rises with shift overlap, falls with a vague or missing
  travel plan, and rises with a concrete yes to the reliability question.
- Starting at all falls with start latency (days from applying to the date
  they say they can start).
- Rota experience, certifications and straight-line distance do nothing,
  once the travel plan is held equal.
- A stated route with a time ("route_with_time") retains as well as having
  a car ("own_transport"). The company's draft rubric pays the car more.
- Self-identified group_2 has a car less often than group_1. Nothing else
  differs between the groups. So any gap in who gets called comes from how
  travel is scored.

Deterministic: the same seed writes the same files.
"""

import argparse
import csv
import datetime as dt
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
PARTS = ["early", "late", "night"]
BLOCKS = [f"{d}_{p}" for d in DAYS for p in PARTS]
AS_OF = dt.date(2026, 10, 30)
START = dt.date(2026, 6, 15)

SITES = {
    "MRL-01": [("sun_night", 8.5, 6), ("mon_night", 8.5, 6), ("tue_night", 8.5, 6),
               ("wed_night", 8.5, 6), ("sat_early", 8, 4)],
    "MRL-02": [("sat_early", 8, 8), ("sun_early", 8, 8), ("sat_late", 8, 6),
               ("sun_late", 8, 6)],
    "MRL-03": [("mon_early", 8, 3), ("tue_early", 8, 3), ("wed_early", 8, 3),
               ("thu_early", 8, 3), ("fri_early", 8, 3), ("fri_late", 8, 4)],
    "MRL-04": [("thu_night", 10, 5), ("fri_night", 10, 5), ("sat_night", 10, 5),
               ("sun_night", 10, 5)],
}
EARLIEST = {"MRL-01": "21:30", "MRL-02": "05:30", "MRL-03": "05:30", "MRL-04": "19:00"}
SITE_WEIGHT = [0.30, 0.25, 0.25, 0.20]

# Planted effects on staying 30 days, given a start.
BASE_STAY = 0.70
OVERLAP_SLOPE = 0.36            # per unit of overlap, centred on 0.5
TRAVEL_STAY = {"route_with_time": 0.04, "own_transport": 0.04,
               "route_no_time": -0.05, "no_plan": -0.17, "": 0.0}
RELIABILITY_STAY = {"yes": 0.05, "no": -0.06, "": 0.0}
# Planted effect on starting at all, by start latency in days.
START_P = [(7, 0.94), (14, 0.88), (28, 0.77), (10_000, 0.64)]


def overlap(avail, site):
    gaps = SITES[site]
    total = sum(h * n for _, h, n in gaps)
    got = sum(h * n for b, h, n in gaps if b in avail)
    return got / total


def draw_availability(rng, site):
    """Some applicants answer for the site they applied to, some do not."""
    k = rng.choice([2, 3, 4, 5, 6, 8, 10])
    pool = list(BLOCKS)
    gaps = [b for b, _, _ in SITES[site]]
    if rng.random() < 0.55:
        chosen = set(rng.sample(gaps, rng.randint(1, len(gaps))))
        chosen |= set(rng.sample(pool, max(0, k - len(chosen))))
    else:
        chosen = set(rng.sample(pool, k))
    return sorted(chosen, key=BLOCKS.index)


def generate(seed=20261030, plants=True):
    rng = random.Random(seed)
    n = 3200
    span = (AS_OF - START).days
    rows, groups = [], []
    for i in range(n):
        aid = f"A{100000 + i * 7 + rng.randint(0, 6)}"
        applied = START + dt.timedelta(days=int(span * (rng.random() ** 0.92)))
        site = rng.choices(list(SITES), SITE_WEIGHT)[0]
        group = "group_1" if rng.random() < 0.5 else "group_2"
        car = rng.random() < ((0.80 if group == "group_1" else 0.36) if plants else 0.6)
        if car:
            travel = rng.choices(["own_transport", "no_plan", "route_with_time"], [0.84, 0.10, 0.06])[0]
            dist = round(min(45.0, max(0.8, rng.lognormvariate(2.2, 0.55))), 1)
        else:
            travel = rng.choices(["route_with_time", "route_no_time", "no_plan"], [0.46, 0.30, 0.24])[0]
            dist = round(min(25.0, max(0.5, rng.lognormvariate(1.55, 0.6))), 1)
        avail = draw_availability(rng, site)
        lat = rng.choices([rng.randint(0, 7), rng.randint(8, 14), rng.randint(15, 28), rng.randint(29, 45)],
                          [0.50, 0.25, 0.15, 0.10])[0]
        available_from = applied + dt.timedelta(days=lat)
        reliability = rng.choices(["yes", "no", ""], [0.58, 0.30, 0.12])[0]
        experience = rng.choices(["yes", "no", ""], [0.55, 0.37, 0.08])[0]
        certs = "forklift" if rng.random() < 0.20 else ""
        age = rng.choices(["yes", "no", ""], [0.93, 0.02, 0.05])[0]
        auth = rng.choices(["yes", "no", ""], [0.935, 0.015, 0.05])[0]
        reapp = "yes" if rng.random() < 0.06 else "no"

        # Blanks the form lets through.
        avail_out = ";".join(avail) if rng.random() > 0.05 else ""
        travel_out = travel if rng.random() > 0.08 else ""

        # Past hiring: who got called and hired did not follow the rubric.
        called = hired = started = day30 = ""
        hired_at = ""
        if applied <= AS_OF - dt.timedelta(days=14):
            called = "yes" if rng.random() < 0.55 else "no"
            if called == "yes" and age != "no" and auth != "no" and rng.random() < 0.52:
                hired = "yes"
                h_at = applied + dt.timedelta(days=rng.randint(3, 10))
                hired_at = h_at.isoformat()
                p_start = next(p for cap, p in START_P if lat <= cap) if plants else 0.85
                if rng.random() < p_start:
                    started = "yes"
                    ov = overlap(set(avail), site)
                    p = (BASE_STAY + OVERLAP_SLOPE * (ov - 0.5) + TRAVEL_STAY[travel]
                         + RELIABILITY_STAY[reliability])
                    if not plants:
                        p = BASE_STAY
                    p = min(0.97, max(0.05, p))
                    stayed = rng.random() < p
                else:
                    started = "no"
                    stayed = False
                if h_at + dt.timedelta(days=30) <= AS_OF:
                    day30 = "yes" if stayed else "no"
                elif started == "no":
                    day30 = "no"
            elif called == "yes":
                hired = "no"
        rows.append({
            "applicant_id": aid, "applied_at": applied.isoformat(), "site": site,
            "availability": avail_out, "available_from": available_from.isoformat(),
            "travel": travel_out, "distance_km": dist, "reliability": reliability,
            "rota_experience": experience, "certifications": certs,
            "age_18_plus": age, "work_authorized": auth, "reapplicant": reapp,
            "called": called, "hired": hired, "hired_at": hired_at,
            "started": started, "day30": day30,
        })
        groups.append({"applicant_id": aid, "group": group})
    rows.sort(key=lambda r: (r["applied_at"], r["applicant_id"]))
    groups.sort(key=lambda r: r["applicant_id"])
    return rows, groups


def rubric(revised=False):
    gaps = {s: {"earliest_shift": EARLIEST[s],
                "gaps": [{"block": b, "hours": h, "shifts": n} for b, h, n in g]}
            for s, g in SITES.items()}
    r = {
        "role": "Warehouse Associate",
        "employer": "Marlow Freight",
        "calls_per_week": 150,
        "queue_days": 14,
        "sites": gaps,
        "signals": {
            "shift_overlap": {"points": 30},
            "start_latency": {"points": 15},
            "travel": {"points": 20,
                       "question": "How would you get to the site for a 05:30 start?",
                       "levels": {"own_transport": 1.0, "route_with_time": 0.5,
                                  "route_no_time": 0.4, "no_plan": 0.0}},
            "reliability": {"points": 10,
                            "question": "Have you worked shifts that start before 7am?"},
            "rota_experience": {"points": 15,
                                "question": "Have you worked to a shift rota before?"},
        },
        "knockouts": [
            {"field": "age_18_plus", "rule": "18 or older",
             "question": "Are you 18 or older?"},
            {"field": "work_authorized", "rule": "authorized to work in the US",
             "question": "Are you authorized to work in the US?"},
        ],
    }
    if revised:
        r["signals"] = {
            "shift_overlap": {"points": 40},
            "start_latency": {"points": 20},
            "travel": {"points": 20,
                       "question": "How would you get to the site for a 05:30 start?",
                       "levels": {"own_transport": 1.0, "route_with_time": 1.0,
                                  "route_no_time": 0.5, "no_plan": 0.0}},
            "reliability": {"points": 10,
                            "question": "Have you worked shifts that start before 7am?"},
            "rota_experience": {"points": 5,
                                "question": "Have you worked to a shift rota before?"},
            "certifications": {"points": 5, "bonus": ["forklift"]},
        }
    return r


EXPECTED = {
    "about": "What the engine must find on the Marlow sample (seed 20261030).",
    "draft": {
        "status": "advice",
        "advice_codes": ["weak_signal_heavy"],
        "signals_earning": ["shift_overlap", "start_latency", "travel", "reliability"],
        "signals_not_earning": ["rota_experience"],
        "travel_pays_for_nothing": ["own_transport over route_with_time"],
        "adverse_impact_flag_signal": "travel",
        "radius_no_difference": True,
    },
    "revised": {
        "status": "ready",
        "adverse_impact_flag": False,
    },
}


def write(out, seed):
    rows, groups = generate(seed)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "marlow_applicants.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(out, "marlow_groups.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["applicant_id", "group"])
        w.writeheader()
        w.writerows(groups)
    for name, rev in (("marlow_rubric.json", False), ("marlow_rubric_revised.json", True)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(rubric(rev), f, indent=2)
            f.write("\n")
    with open(os.path.join(out, "marlow_expected.json"), "w", encoding="utf-8") as f:
        json.dump(EXPECTED, f, indent=2)
        f.write("\n")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=20261030)
    ap.add_argument("--out", default=HERE)
    a = ap.parse_args()
    rows = write(a.out, a.seed)
    print(f"{len(rows)} applicants written to {a.out}")
