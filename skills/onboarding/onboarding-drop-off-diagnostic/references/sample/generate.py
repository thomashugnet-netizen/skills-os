"""
Builds the planted onboarding log for onboarding-drop-off-diagnostic.

    python3 generate.py            # writes bramblewood_hires.csv and bramblewood_steps.csv
    python3 generate.py --plain    # the same world with nothing planted (null world)

Bramblewood Grocers is a fictional grocery chain: 30 stores in three regions,
four store roles, one row per accepted offer from March to October 2026, and
one row per onboarding step per hire. No personal data: every id is opaque.

What is planted, and what a correct read must say about it:

  R1  The offer-to-first-shift gap. Losses climb with every day past six:
      about +2 points a day, capped at +25.
  R2  Dead air. A hire who heard nothing for 5 days or more inside the first
      week, and was still waiting after it, leaves 10 points more often.
      It comes from running paperwork and uniform only after the background
      check clears ("sequential"), which half the hires at some stores get.
  R3  A drug test at an outside lab instead of a rapid test on site: +8
      points, at the same gap. The hire has to travel to it.
  R4  LOC-11: +15 points of first-shift no-shows (its first shift is at the
      distribution centre, not the store). Shows as a site, nothing more.
  H1  vendor_b (West region, LOC-21 to 30) takes a median 7 days to return a
      background check, against 2.5 for vendor_a. Its hires lose more, only
      through the longer gap. No vendor effect at the same gap.
  H2  Deli Clerk needs a food handler card after the check clears, so its gap
      is longer. No role effect at the same gap.
  H3  hiring_event hires are concentrated in the West. No source effect.
  T1  LOC-07 fails 20% of background checks. Those offers are rescinded by the
      employer: not a drop-off, and LOC-07 must not be named for losses.
  T2  Hires whose first shift falls after 31 October are pending, including
      the ones already marked withdrew. Counting them would inflate losses.
  N1  Recruiter and commute carry nothing.

Deterministic: seeded, stdlib only.
"""

import csv
import datetime as dt
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_HIRES = os.path.join(HERE, "bramblewood_hires.csv")
OUT_STEPS = os.path.join(HERE, "bramblewood_steps.csv")

START = dt.datetime(2026, 3, 2, 9, 0)
LAST_OFFER = dt.datetime(2026, 10, 28, 18, 0)
AS_OF = dt.datetime(2026, 10, 31, 23, 59)

SITES = [f"LOC-{i:02d}" for i in range(1, 31)]
REGION = {s: ("East" if i < 10 else "Central" if i < 20 else "West")
          for i, s in enumerate(SITES)}
RECRUITERS = {"East": ["REC-01", "REC-02", "REC-03"],
              "Central": ["REC-04", "REC-05", "REC-06"],
              "West": ["REC-07", "REC-08", "REC-09"]}
ROLES = [("Cashier", .40), ("Stocker", .30), ("Deli Clerk", .15),
         ("Produce Associate", .15)]
COMMUTE = ["0-5", "6-10", "11-20", "21-40", "40+"]
LAB_SITES = {"LOC-02", "LOC-05", "LOC-08", "LOC-13", "LOC-16", "LOC-18",
             "LOC-22", "LOC-24", "LOC-27", "LOC-29"}
FAR_DC = "LOC-11"
HIGH_FAIL = "LOC-07"

PLANTED = {"gap": 0.022, "gap_cap": 0.25, "silence": 0.10, "lab": 0.08,
           "loc11": 0.15}
PLAIN = {"gap": 0.0, "gap_cap": 0.0, "silence": 0.0, "lab": 0.0, "loc11": 0.0}


def lognorm(rng, median, spread):
    return median * math.exp(rng.gauss(0, spread))


def fmt(t):
    return t.strftime("%Y-%m-%d %H:%M") if t else ""


def work_hours(t):
    """Snap a time into 8:00-19:00, which is when systems log things."""
    if t.hour < 8:
        t = t.replace(hour=8, minute=t.minute)
    elif t.hour >= 19:
        t = (t + dt.timedelta(days=1)).replace(hour=8 + t.minute % 3)
    return t


def silence_in_first_week(offer, events):
    """Longest stretch, in days, with no event inside [offer, offer + 7 days]."""
    end = offer + dt.timedelta(days=7)
    ts = sorted([offer, end] + [e for e in events if offer <= e <= end])
    return max((b - a).total_seconds() / 86400 for a, b in zip(ts, ts[1:]))


def make(seed=20261107, effects=PLANTED):
    rng = random.Random(seed)
    site_seq = {s: rng.uniform(.15, .75) for s in SITES}   # share run sequentially
    site_recruiter = {s: rng.choice(RECRUITERS[REGION[s]]) for s in SITES}
    site_weight = {s: rng.uniform(.7, 1.3) for s in SITES}
    site_weight[FAR_DC] = 1.7
    hires, steps = [], []
    t = START
    n = 0
    while t < LAST_OFFER:
        # about 22 accepted offers a day (half the draws fall out of hours), a little busier from September
        t += dt.timedelta(hours=rng.expovariate(1.0) * (24 / (52 if t.month >= 9 else 42)))
        if t.hour < 8 or t.hour >= 19:
            continue
        n += 1
        hid = f"H{n:05d}"
        site = rng.choices(SITES, [site_weight[s] for s in SITES])[0]
        region = REGION[site]
        role = rng.choices([r for r, _ in ROLES], [w for _, w in ROLES])[0]
        src_w = {"job_board": .40, "careers_site": .25, "referral": .15,
                 "hiring_event": .30 if region == "West" else .05}
        source = rng.choices(list(src_w), list(src_w.values()))[0]
        recruiter = site_recruiter[site] if rng.random() < .8 else rng.choice(
            RECRUITERS[region])
        commute = rng.choice(COMMUTE)
        vendor = "vendor_b" if region == "West" else "vendor_a"
        lab = rng.random() < (.85 if site in LAB_SITES else .12)
        sequential = rng.random() < site_seq[site]
        offer = t

        # --- the plan: when each step is requested and when it would finish
        plan = []                                  # (step, vendor, method, req, done, needs_hire)
        bg_req = work_hours(offer + dt.timedelta(hours=rng.uniform(1, 30)))
        bg_done = work_hours(bg_req + dt.timedelta(days=lognorm(
            rng, 7.0 if vendor == "vendor_b" else 2.5, .35)))
        plan.append(["background_check", vendor, "", bg_req, bg_done, "no"])
        dt_req = work_hours(offer + dt.timedelta(hours=rng.uniform(1, 20)))
        dt_done = work_hours(dt_req + dt.timedelta(days=lognorm(rng, 3.2, .3) if lab
                                                   else rng.uniform(.1, .9)))
        plan.append(["drug_test", "", "lab" if lab else "onsite", dt_req, dt_done, "yes"])
        after = bg_done if sequential else offer
        for step, med in (("i9_section1", .8), ("tax_forms", 1.0)):
            r = work_hours(after + dt.timedelta(hours=rng.uniform(.5, 6)))
            plan.append([step, "", "", r, work_hours(r + dt.timedelta(
                days=lognorm(rng, med, .5))), "yes"])
        r = work_hours(after + dt.timedelta(hours=rng.uniform(1, 24)))
        plan.append(["uniform", "", "", r, work_hours(r + dt.timedelta(
            days=rng.uniform(2, 4))), "no"])
        ready = max(bg_done, dt_done)
        if role == "Deli Clerk":
            r = work_hours(bg_done + dt.timedelta(hours=rng.uniform(2, 20)))
            d = work_hours(r + dt.timedelta(days=lognorm(rng, 4.5, .25)))
            plan.append(["food_handler_card", "", "", r, d, "yes"])
            ready = max(ready, d)
        first = (ready + dt.timedelta(days=rng.uniform(1, 3))).replace(
            hour=rng.choice([6, 7, 8, 14]), minute=0)
        gap = (first.date() - offer.date()).days
        orient_req = work_hours(ready + dt.timedelta(hours=rng.uniform(1, 8)))
        plan.append(["orientation", "", "", orient_req, first - dt.timedelta(hours=1), "yes"])

        # --- rescinded: a failed check, decided when the result comes back
        fail_p = .20 if site == HIGH_FAIL else .04
        rescinded_at = None
        if rng.random() < fail_p:
            rescinded_at = bg_done
        elif rng.random() < .015:
            rescinded_at = dt_done

        # --- the loss model
        events_planned = [x for p in plan for x in (p[3], p[4])]
        sil = silence_in_first_week(offer, events_planned)
        comps = [(.06, "base")]
        comps.append((min(effects["gap"] * max(0, gap - 6), effects["gap_cap"]), "gap"))
        if lab:
            comps.append((effects["lab"], "lab"))
        if sil >= 5 and gap > 8:
            comps.append((effects["silence"], "silence"))
        if site == FAR_DC:
            comps.append((effects["loc11"], "loc11"))
        u = rng.random()
        cause = None
        acc = 0.0
        for p, name in comps:
            acc += p
            if u < acc:
                cause = name
                break
        outcome, withdrawn = "started", None
        if cause:
            if cause == "loc11" or (cause == "base" and rng.random() < .35):
                outcome = "no_show"
            else:
                outcome = "withdrew"
                lo = 7.2 if cause == "silence" else (1.0 if cause != "lab" else
                                                     (dt_req - offer).total_seconds() / 86400 + .3)
                hi = max(lo + .2, gap - .4)
                withdrawn = work_hours(offer + dt.timedelta(days=rng.uniform(lo, hi)))
                if withdrawn >= first:
                    outcome, withdrawn = "no_show", None
        if rescinded_at and (withdrawn is None or rescinded_at < withdrawn):
            outcome, withdrawn = "rescinded", None

        stop = withdrawn or rescinded_at
        status_time = min([x for x in (stop, AS_OF) if x])
        pending = first > AS_OF
        if pending and outcome != "withdrew":
            outcome = ""
        if pending and outcome == "withdrew" and withdrawn > AS_OF:
            outcome, withdrawn = "", None
            status_time = AS_OF
        hires.append({
            "hire_id": hid, "offer_accepted_at": fmt(offer),
            "first_shift_scheduled_at": fmt(first), "outcome": outcome,
            "withdrawn_at": fmt(withdrawn), "rescinded_at": fmt(rescinded_at)
            if outcome == "rescinded" else "",
            "location_id": site, "region": region, "role": role, "source": source,
            "recruiter_id": recruiter, "commute_band_km": commute})
        for step, vend, method, req, done, needs in plan:
            if req > status_time:
                continue                       # never requested before it ended
            result = "done"
            comp = done
            if step == "orientation" and outcome == "no_show":
                result, comp = "open", None
            elif done > status_time:
                result, comp = ("open" if outcome == "" else "cancelled"), None
            if step == "background_check" and outcome == "rescinded" and rescinded_at == bg_done:
                result, comp = "failed", bg_done
            if step == "drug_test" and outcome == "rescinded" and rescinded_at == dt_done:
                result, comp = "failed", dt_done
            steps.append({"hire_id": hid, "step": step, "requested_at": fmt(req),
                          "completed_at": fmt(comp), "result": result,
                          "vendor": vend, "method": method, "needs_hire": needs})
    return hires, steps


def write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    plain = "--plain" in sys.argv
    hires, steps = make(effects=PLAIN if plain else PLANTED)
    if plain:
        print(f"{len(hires)} hires, {len(steps)} steps (null world, not written)")
    else:
        write(OUT_HIRES, hires)
        write(OUT_STEPS, steps)
        print(f"{len(hires)} hires, {len(steps)} steps")
