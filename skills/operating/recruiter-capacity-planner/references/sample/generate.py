#!/usr/bin/env python3
"""
Generates the Northline recruiter sample with known answers. Deterministic.

    python3 generate.py            # writes the three CSVs next to this file

Seven recruiters, 30 weeks, one row per application. What is planted:

  KNEE      Screening wait (applied -> screened) is flat up to 70 applications a
            week per available recruiter, then rises 0.06 days for every
            application above it. Every recruiter shares this curve.
  REC-01..03, REC-07   Ordinary recruiters. REC-07 only ever carries light load.
  REC-02    Holds most of the Shift Supervisor reqs, and supervisor applications
            take a day longer to screen for everyone. Raw, REC-02 looks slow;
            within role, REC-02 is like the others. Must not be called individual.
  REC-04    Holds the Seasonal reqs fed by a cheap board: 80% of the applications
            never get past the form. The load is upstream, not the recruiter.
  REC-05    Two days slower than everyone at every load. Individual.
  REC-06    Reschedules 45% of the interviews booked. Rework: process.
  SEASON    Weeks in November and December carry more applications for everyone
            and candidates answer more slowly (+0.4 days). The knee must survive
            inside a single season.
  ABSENCE   The roster marks leave weeks. Load per available day is the honest
            denominator: REC-03 is off three days in week 12 and REC-01 two days in
            week 20, and both weeks sit above the knee only once leave is counted.
"""

import csv
import datetime as dt
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
START = dt.date(2025, 6, 2)          # a Monday
WEEKS = 30
KNEE = 70.0
SLOPE = 0.06
REC = ["REC-01", "REC-02", "REC-03", "REC-04", "REC-05", "REC-06", "REC-07"]
ROLES = ["Sales Associate", "Cashier", "Stocker", "Shift Supervisor", "Seasonal Associate"]
LEAVE = {("REC-03", 12): 2, ("REC-01", 20): 3}     # available days that week


def main():
    rng = random.Random(20261103)
    rows, roster = [], []
    n = 0
    for w in range(WEEKS):
        monday = START + dt.timedelta(weeks=w)
        peak = monday.month in (11, 12)
        for r in REC:
            avail = LEAVE.get((r, w), 5)
            roster.append({"week": monday.isoformat(), "recruiter_id": r, "available_days": avail})
            base = {"REC-07": 35}.get(r, 58)
            load = base * (1.45 if peak else 1.0) * rng.uniform(0.75, 1.3)
            if (r, w) in LEAVE:
                load = 66 * rng.uniform(0.95, 1.05)
            load = int(load)
            per_day_load = load / avail * 5
            for i in range(load):
                n += 1
                if r == "REC-02":
                    role = "Shift Supervisor" if rng.random() < 0.7 else rng.choice(ROLES[:3])
                elif r == "REC-04":
                    role = "Seasonal Associate"
                else:
                    role = rng.choice(ROLES[:3] + (["Shift Supervisor"] if rng.random() < 0.08 else []))
                applied = monday + dt.timedelta(days=rng.randint(0, 4))
                mgr = f"MGR-{rng.randint(1, 4) + 4 * REC.index(r):03d}"
                row = {"application_id": f"APP-{n:06d}", "recruiter_id": r, "hiring_manager_id": mgr,
                       "role": role, "region": "Midwest" if REC.index(r) % 2 else "South",
                       "applied_at": applied.isoformat(), "screened_at": "", "interview_scheduled_at": "",
                       "reschedules": 0, "offer_at": "", "first_shift_at": "", "stage_reached": "applied",
                       "exit_reason": ""}
                if r == "REC-04" and rng.random() < 0.8:
                    row["exit_reason"] = rng.choice(["failed_knockout", "incomplete_application"])
                    rows.append(row)
                    continue
                if rng.random() < 0.12:
                    row["exit_reason"] = "withdrew"
                    rows.append(row)
                    continue
                wait = 1.0 + max(0.0, per_day_load - KNEE) * SLOPE
                wait += 1.0 if role == "Shift Supervisor" else 0.0
                wait += 2.0 if r == "REC-05" else 0.0
                wait += 0.4 if peak else 0.0
                wait = max(0.0, wait + rng.gauss(0, 0.6))
                screened = applied + dt.timedelta(days=round(wait))
                row["screened_at"] = screened.isoformat()
                row["stage_reached"] = "screened"
                if rng.random() < 0.55:
                    row["exit_reason"] = rng.choice(["unresponsive", "not_qualified", "withdrew"])
                    rows.append(row)
                    continue
                sched = screened + dt.timedelta(days=rng.randint(1, 3))
                row["interview_scheduled_at"] = sched.isoformat()
                row["stage_reached"] = "interview_scheduled"
                p_res = 0.45 if r == "REC-06" else 0.12
                row["reschedules"] = (1 if rng.random() < p_res else 0) + (1 if rng.random() < p_res / 4 else 0)
                if rng.random() < 0.45:
                    row["exit_reason"] = rng.choice(["interview_no_show", "not_qualified"])
                    rows.append(row)
                    continue
                offer = sched + dt.timedelta(days=rng.randint(1, 4))
                row["offer_at"] = offer.isoformat()
                row["stage_reached"] = "offer_extended"
                if rng.random() < 0.75:
                    row["first_shift_at"] = (offer + dt.timedelta(days=rng.randint(3, 10))).isoformat()
                    row["stage_reached"] = "started"
                else:
                    row["exit_reason"] = "offer_declined"
                rows.append(row)
    with open(os.path.join(HERE, "northline_recruiting.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(HERE, "northline_roster.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["week", "recruiter_id", "available_days"])
        w.writeheader()
        w.writerows(roster)
    print(len(rows), "applications")


if __name__ == "__main__":
    main()
