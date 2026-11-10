"""
Builds the planted interview booking log for interview-no-show-playbook.

    python3 generate.py            # writes fernhill_bookings.csv next to this file
    python3 generate.py --plain    # the same world with nothing planted (null world)

Fernhill & Co. is a fictional specialty apparel retailer: 24 stores, five store
roles, one row per booked interview from March to October 2026, with the
September-October holiday hiring ramp. No personal data: every id is opaque.

What is planted, and what a correct read must say about it:

  R1  Booking-to-interview lag. Miss rate climbs with the wait: +12 points at
      4-7 days, +20 at 8 days or more, against a same-day booking.
  R2  A weekend inside the wait: +8 points at the same lag.
  R3  Slots from 11:00 to 13:59, inside the shift most candidates are working
      elsewhere: +10 points, in every role.
  R4  One slot offered instead of a choice: +7 points.
  R5  LOC-17 (a busy outlet-mall store that is hard to find): +20 points for
      in-person interviews only. One interviewer, so site and interviewer
      cannot be told apart.
  R6  The stockroom role misses more at every site and wait (base rate).
  H1  Self-scheduling looks better, but only because self-schedulers book
      sooner. No effect at the same lag.
  H2  Slots before 10:00 look worse, but only because the stockroom role
      (higher base rate) interviews early. Explained by role.
  H3  Five stores interview on one weekday only (LOC-04, 09, 13, 20, 22).
      Their misses are their lag; no site effect beyond it.
  H4  Busy weeks (from 14 September) look worse, through longer lags only.
  H5  jobboard_b is concentrated at the one-day stores. No source effect.
  N1  commute_band_km and format carry nothing.
  RC  Recovery after a silent miss: four stores never rebook a miss (LOC-06,
      11, 15, 23). Elsewhere, the sooner the rebooking the more attend.
  S1  The reply to the 24-hour reminder: no reply misses far more often.

Deterministic: seeded, stdlib only.
"""

import csv
import datetime as dt
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fernhill_bookings.csv")

START = dt.date(2026, 3, 2)
LAST_BOOKING = dt.date(2026, 10, 23)
AS_OF = dt.date(2026, 10, 31)
PEAK_FROM = dt.date(2026, 9, 14)

STORES = [f"LOC-{i:02d}" for i in range(1, 25)]
ONE_DAY = {"LOC-04": 1, "LOC-09": 3, "LOC-13": 1, "LOC-20": 2, "LOC-22": 3}
AUTO_REJECT = {"LOC-06", "LOC-11", "LOC-15", "LOC-23"}
HARD_TO_FIND = "LOC-17"

ROLES = [("Sales Associate", .45, .13), ("Stylist", .15, .12),
         ("Stockroom Associate", .20, .30), ("Key Holder", .12, .12),
         ("Assistant Store Manager", .08, .10)]
SOURCES = ["jobboard_a", "jobboard_b", "careers_site", "referral", "walk_in_qr"]
COMMUTE = ["0-5", "6-10", "11-20", "21-40", "40+"]

LAG_EFFECT = {0: 0.0, 1: .01, 2: .03, 3: .03}       # 4-7: .12, 8+: .20
SELF_LAG = {0: .22, 1: .34, 2: .22, 3: .12, 4: .05, 5: .03, 6: .02}
RECRUITER_LAG = {1: .05, 2: .10, 3: .15, 4: .18, 5: .16, 6: .13, 7: .10,
                 8: .07, 9: .04, 10: .02}
# Rebooking after a silent miss: delay band, chance it happens, then attendance.
REBOOK = [((0, 2), .30, .62, .80), ((3, 10), .15, .50, .75),
          ((14, 34), .25, .40, .66), ((38, 80), .15, .28, .58),
          ((86, 160), .15, .18, .50)]


def pick(rng, weights):
    keys, w = zip(*weights.items())
    return rng.choices(keys, w)[0]


def lag_effect(lag):
    if lag in LAG_EFFECT:
        return LAG_EFFECT[lag]
    return .12 if lag <= 7 else .20


def spans_weekend(booked, appt):
    d = booked + dt.timedelta(days=1)
    while d < appt:
        if d.weekday() >= 5:
            return True
        d += dt.timedelta(days=1)
    return False


def build(planted=True, seed=1117):
    rng = random.Random(seed)
    interviewers = {}
    for i, s in enumerate(STORES, 1):
        two = (i % 2 == 0 and s not in ONE_DAY and s != HARD_TO_FIND)
        interviewers[s] = [f"MGR-{i:02d}A"] + ([f"MGR-{i:02d}B"] if two else [])

    rows, seq = [], [0]

    def new_id():
        seq[0] += 1
        return f"APP-{seq[0]:06d}"

    def appt_hour(role):
        if role == "Stockroom Associate" and rng.random() < .90:
            return rng.choice([7, 8, 9])
        return rng.choice([9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19])

    def schedule(store, booked_day, lag):
        if store in ONE_DAY:
            target = ONE_DAY[store]
            d = booked_day + dt.timedelta(days=1)
            while d.weekday() != target:
                d += dt.timedelta(days=1)
            if rng.random() < .6:
                d += dt.timedelta(days=7)
            return d
        d = booked_day + dt.timedelta(days=lag)
        if d.weekday() == 6:
            d += dt.timedelta(days=1)
        return d

    def p_miss(base, lag, weekend, hour, slots, store, fmt):
        p = base + lag_effect(lag)
        p += .08 if weekend else 0
        p += .10 if 11 <= hour < 14 else 0
        p += .07 if slots == 1 else 0
        p += .20 if (store == HARD_TO_FIND and fmt == "in_person") else 0
        return min(max(p, .02), .90)

    def emit(app, store, role, source, mgr, commute, mode, fmt, slots,
             booked, appt, outcome, cancelled_at, reminder, confirmed):
        rows.append({
            "application_id": app, "location_id": store, "role": role,
            "source": source, "hiring_manager_id": mgr,
            "commute_band_km": commute, "mode": mode, "format": fmt,
            "slots_offered": slots,
            "booked_at": booked.strftime("%Y-%m-%d %H:%M"),
            "interview_at": appt.strftime("%Y-%m-%d %H:%M"),
            "outcome": outcome,
            "cancelled_at": cancelled_at.strftime("%Y-%m-%d %H:%M") if cancelled_at else "",
            "reminder_24h": reminder, "confirmed": confirmed,
        })

    def one_booking(app, store, role, base, source, mgr, commute, fmt, mode,
                    slots, booked, appt, forced_attend=None):
        """Draws the outcome of one appointment and writes it. Returns
        (outcome, appt, cancelled_at)."""
        lag = (appt.date() - booked.date()).days
        weekend = spans_weekend(booked.date(), appt.date())
        if appt.date() > AS_OF:
            emit(app, store, role, source, mgr, commute, mode, fmt, slots,
                 booked, appt, "", None, "", "")
            return "open", appt, None
        hours_ahead = (appt - booked).total_seconds() / 3600
        reminder = "yes" if hours_ahead >= 24 else "no"
        u = rng.random()
        cancelled_at = None
        if u < .015:
            outcome = "employer_cancelled"
        elif u < .015 + .04:
            outcome = "rescheduled"
        elif u < .015 + .04 + .05 + (.03 if lag >= 4 else 0):
            outcome = "cancelled"
        else:
            if forced_attend is not None:
                miss = rng.random() >= forced_attend
            elif planted:
                miss = rng.random() < p_miss(base, lag, weekend, appt.hour,
                                             slots, store, fmt)
            else:
                miss = rng.random() < .19
            outcome = "no_show" if miss else "attended"
        if outcome in ("cancelled", "rescheduled"):
            span = max((appt - booked).total_seconds(), 3600)
            cancelled_at = booked + dt.timedelta(seconds=rng.uniform(.3, .9) * span)
        confirmed = ""
        if reminder == "yes":
            if outcome == "attended":
                confirmed = "yes" if rng.random() < (.70 if planted else .5) else ""
            elif outcome == "no_show":
                confirmed = "yes" if rng.random() < (.12 if planted else .5) else ""
            elif outcome in ("cancelled", "rescheduled"):
                confirmed = "move" if rng.random() < .6 else ""
        emit(app, store, role, source, mgr, commute, mode, fmt, slots,
             booked, appt, outcome, cancelled_at, reminder, confirmed)
        return outcome, appt, cancelled_at

    day = START
    while day <= LAST_BOOKING:
        peak = day >= PEAK_FROM
        for store in STORES:
            rate = 1.05 * (1.6 if peak else 1.0) * (0.55 if day.weekday() == 6 else 1.0)
            rate *= 1.5 if store == HARD_TO_FIND else 1.0
            n = int(rate) + (1 if rng.random() < rate - int(rate) else 0)
            for _ in range(n):
                role, base = None, None
                r = rng.random()
                acc = 0
                for name, w, b in ROLES:
                    acc += w
                    if r < acc:
                        role, base = name, b
                        break
                if role is None:
                    role, base = ROLES[-1][0], ROLES[-1][2]
                if store in ONE_DAY:
                    source = rng.choices(SOURCES, [.20, .45, .15, .08, .12])[0]
                else:
                    source = rng.choices(SOURCES, [.32, .15, .27, .11, .15])[0]
                commute = rng.choices(COMMUTE, [.30, .28, .22, .14, .06])[0]
                mgr = rng.choice(interviewers[store])
                mode = "self" if rng.random() < .55 else "recruiter"
                video = .70 if role == "Assistant Store Manager" else .08
                fmt = "video" if rng.random() < video else "in_person"
                one_slot = .50 if store in ONE_DAY else .18
                slots = 1 if rng.random() < one_slot else rng.choice([2, 3, 3, 4, 5])
                lag = pick(rng, SELF_LAG if mode == "self" else RECRUITER_LAG)
                if peak and rng.random() < .8:
                    lag += rng.choice([3, 4, 4, 5])
                booked = dt.datetime.combine(day, dt.time(rng.randint(8, 21),
                                                          rng.choice([0, 15, 30, 45])))
                appt_day = schedule(store, day, lag)
                hour = appt_hour(role)
                appt = dt.datetime.combine(appt_day, dt.time(hour, rng.choice([0, 30])))
                if appt <= booked:
                    appt = booked + dt.timedelta(hours=rng.choice([3, 4, 5]))
                    appt = appt.replace(minute=0)
                app = new_id()
                outcome, appt, cancelled_at = one_booking(
                    app, store, role, base, source, mgr, commute, fmt, mode,
                    slots, booked, appt)
                follow_ups(rng, app, store, role, base, source, mgr, commute,
                           fmt, outcome, appt, cancelled_at, one_booking,
                           schedule, appt_hour, planted)
        day += dt.timedelta(days=1)
    return rows


def follow_ups(rng, app, store, role, base, source, mgr, commute, fmt,
               outcome, appt, cancelled_at, one_booking, schedule, appt_hour,
               planted):
    """What happens after the first appointment: a rebooking after a miss, a
    cancellation or a reschedule. At most one more appointment."""
    if outcome == "no_show":
        if planted and store in AUTO_REJECT:
            return
        if planted:
            band = rng.choices(REBOOK, [b[1] for b in REBOOK])[0]
            (lo, hi), _w, p_rebook, p_attend = band
        else:
            lo, hi, p_rebook, p_attend = 0, 160, .35, .65
        if rng.random() >= p_rebook:
            return
        booked = appt + dt.timedelta(hours=rng.uniform(lo, hi))
        if booked.hour < 8 or booked.hour > 21:
            booked = booked.replace(hour=rng.randint(8, 21))
            if booked < appt:
                booked += dt.timedelta(days=1)
        lag = rng.choice([1, 1, 2, 2, 3])
        new_day = schedule(store, booked.date(), lag)
        new_appt = dt.datetime.combine(new_day, dt.time(appt_hour(role), 0))
        one_booking(app, store, role, base, source, mgr, commute, fmt,
                    "recruiter", 2, booked, new_appt, forced_attend=p_attend)
    elif outcome == "cancelled":
        if rng.random() >= .55:
            return
        booked = cancelled_at + dt.timedelta(hours=rng.uniform(2, 40))
        lag = rng.choice([1, 2, 2, 3, 4])
        new_day = schedule(store, booked.date(), lag)
        new_appt = dt.datetime.combine(new_day, dt.time(appt_hour(role), 0))
        one_booking(app, store, role, base, source, mgr, commute, fmt,
                    "recruiter", 2, booked, new_appt)
    elif outcome == "rescheduled":
        if rng.random() >= .9:
            return
        booked = cancelled_at
        lag = rng.choice([1, 2, 2, 3, 4])
        new_day = schedule(store, booked.date(), lag)
        new_appt = dt.datetime.combine(new_day, dt.time(appt_hour(role), 0))
        one_booking(app, store, role, base, source, mgr, commute, fmt,
                    "self", 3, booked, new_appt)


FIELDS = ["application_id", "location_id", "role", "source", "hiring_manager_id",
          "commute_band_km", "mode", "format", "slots_offered", "booked_at",
          "interview_at", "outcome", "cancelled_at", "reminder_24h", "confirmed"]


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    plain = "--plain" in sys.argv
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else OUT
    data = build(planted=not plain)
    write(data, out)
    print(f"{len(data)} bookings -> {out}")
