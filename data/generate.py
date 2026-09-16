"""
Generates the public synthetic frontline hiring dataset for the
Claude Skills for HR Ops library.

Design goals
------------
1. No personal data of any kind. There are no names, emails, phone numbers,
   addresses or dates of birth in the output, by construction. Every entity is
   an opaque id.
2. Realistic shape for a multi-site hourly employer: 42 locations, 4 regions,
   5 roles, 7 pipeline stages, 12 months, a Q4 seasonal spike.
3. Contains real, discoverable causal structure so the analysis skills have
   genuine findings to rank -- including two deliberate confounds, so a skill
   that only looks at correlation gets the answer wrong.

Embedded patterns, in the order a correct analysis should rank them:
  P1  Midwest region runs a hard availability knockout at screening.
      Screening pass rate ~28% vs ~62% elsewhere. Largest absolute loss.
  P2  Eight locations have scarce interview self-schedule slots.
      screened -> interview_scheduled collapses; the wait lengthens.
  P3  Days from offer to first shift drives no-shows. Long gap ~3.5x the
      no-show rate of a short gap.
  P4  jobboard_c is high-volume, cheap, and converts to started terribly.
  P5  Five hiring managers have ~3x baseline 30-day attrition. CONFOUND:
      those managers sit on Delivery Driver-heavy sites, so a naive cut
      blames the role. Within-role, the manager effect survives.
  P6  Long commute bands raise no-shows, but materially less than P3.
  P7  Q4 spike degrades cycle time and no-show rate (capacity strain).
  P8  RED HERRING: weekend applications convert worse, but only because
      jobboard_c skews to weekends. Controlling for source removes it.

Deterministic: seeded, so the published CSV is reproducible.
"""

import os

import numpy as np
import pandas as pd

# Output next to this script by default, so the dataset reproduces on any
# machine. Override with OUT_DIR to regenerate somewhere else and diff.
OUT_DIR = os.environ.get("OUT_DIR") or os.path.dirname(os.path.abspath(__file__))

RNG = np.random.default_rng(20260909)

START = pd.Timestamp("2025-09-01")
END = pd.Timestamp("2026-08-31")

REGIONS = {
    "Midwest": 11,
    "Northeast": 10,
    "South": 12,
    "West": 9,
}

ROLES = ["Team Member", "Cashier", "Stocker", "Shift Supervisor", "Delivery Driver"]
ROLE_W = [0.40, 0.20, 0.16, 0.09, 0.15]

SOURCES = ["jobboard_a", "jobboard_b", "jobboard_c", "referral", "career_site", "social"]
SOURCE_W = [0.20, 0.14, 0.31, 0.09, 0.14, 0.12]

STAGES = [
    "applied",
    "screened",
    "interview_scheduled",
    "interview_completed",
    "offer_extended",
    "onboarding_started",
    "started",
]

COMMUTE_BANDS = ["0-5", "6-10", "11-20", "21-40", "40+"]
COMMUTE_W = [0.28, 0.27, 0.22, 0.15, 0.08]


# ---------------------------------------------------------------- locations

def build_locations():
    rows, n = [], 0
    for region, count in REGIONS.items():
        for _ in range(count):
            n += 1
            rows.append({"location_id": f"LOC-{n:02d}", "region": region})
    loc = pd.DataFrame(rows)

    # P2: eight locations with scarce interview slots, spread across regions
    loc["slot_scarce"] = loc["location_id"].isin(
        ["LOC-03", "LOC-07", "LOC-14", "LOC-19", "LOC-25", "LOC-31", "LOC-36", "LOC-40"]
    )

    # One hiring manager per location.
    loc["hiring_manager_id"] = [f"MGR-{i:03d}" for i in range(1, len(loc) + 1)]

    # P5: five managers with poor early retention. Their sites are also
    # Delivery Driver-heavy -- that is the deliberate confound.
    loc["weak_manager"] = loc["hiring_manager_id"].isin(
        ["MGR-004", "MGR-012", "MGR-021", "MGR-029", "MGR-038"]
    )
    loc["driver_heavy"] = loc["weak_manager"] | loc["location_id"].isin(
        ["LOC-09", "LOC-17", "LOC-27", "LOC-33"]
    )

    # Baseline site volume weight.
    loc["volume_w"] = RNG.uniform(0.55, 1.75, len(loc))
    return loc


LOC = build_locations()


# ---------------------------------------------------------------- volume

def monthly_volume():
    """Base ~1,100 applications/month, Q4 spike x2.4."""
    months = pd.date_range(START, END, freq="MS")
    out = {}
    for m in months:
        spike = 2.4 if m.month in (10, 11, 12) else 1.0
        out[m] = int(1100 * spike * RNG.uniform(0.92, 1.08))
    return out


VOLUME = monthly_volume()


def in_spike(ts):
    return ts.month in (10, 11, 12)


# ---------------------------------------------------------------- draw rows

def draw_applications():
    recs = []
    seq = 0
    loc_w = LOC["volume_w"].to_numpy() / LOC["volume_w"].sum()

    for month, count in VOLUME.items():
        days_in_month = month.days_in_month
        for _ in range(count):
            seq += 1
            li = RNG.choice(len(LOC), p=loc_w)
            site = LOC.iloc[li]

            applied = month + pd.Timedelta(days=int(RNG.integers(0, days_in_month)))
            if applied > END:
                applied = END

            # P8 setup: jobboard_c skews to weekend applications.
            src = RNG.choice(SOURCES, p=SOURCE_W)
            if src == "jobboard_c" and applied.dayofweek < 5 and RNG.random() < 0.42:
                applied = applied + pd.Timedelta(days=int(5 - applied.dayofweek))
                if applied > END:
                    applied = END

            role_w = ROLE_W.copy()
            if site["driver_heavy"]:
                role_w = [0.24, 0.13, 0.10, 0.06, 0.47]
            role = RNG.choice(ROLES, p=role_w)

            recs.append(
                {
                    "application_id": f"APP-{seq:06d}",
                    "location_id": site["location_id"],
                    "region": site["region"],
                    "hiring_manager_id": site["hiring_manager_id"],
                    "role": role,
                    "source": src,
                    "applied_at": applied,
                    "commute_band_km": RNG.choice(COMMUTE_BANDS, p=COMMUTE_W),
                    "_slot_scarce": bool(site["slot_scarce"]),
                    "_weak_manager": bool(site["weak_manager"]),
                }
            )
    return pd.DataFrame(recs)


df = draw_applications()


# ---------------------------------------------------------------- availability

# P1: Midwest applies a hard availability knockout. Availability itself is
# distributed the same everywhere -- only the screening rule differs.
avail = RNG.choice(["full", "partial", "limited"], size=len(df), p=[0.46, 0.34, 0.20])
df["availability_match"] = avail


# ---------------------------------------------------------------- progression

n = len(df)
u = RNG.random((n, 6))

stage_idx = np.zeros(n, dtype=int)          # 0 = applied
reject_reason = np.array([""] * n, dtype=object)

src = df["source"].to_numpy()
region = df["region"].to_numpy()
av = df["availability_match"].to_numpy()
scarce = df["_slot_scarce"].to_numpy()
spike = df["applied_at"].apply(in_spike).to_numpy()
commute = df["commute_band_km"].to_numpy()

# --- stage 1: applied -> screened
p_screen = np.full(n, 0.62)
# source quality on screening
p_screen += np.where(src == "referral", 0.16, 0.0)
p_screen += np.where(src == "career_site", 0.06, 0.0)
p_screen -= np.where(src == "jobboard_c", 0.14, 0.0)      # P4
# P1: the Midwest knockout
mw = region == "Midwest"
p_screen = np.where(mw & (av == "full"), 0.60, p_screen)
p_screen = np.where(mw & (av == "partial"), 0.16, p_screen)
p_screen = np.where(mw & (av == "limited"), 0.02, p_screen)
p_screen = np.clip(p_screen, 0.01, 0.95)

passed_screen = u[:, 0] < p_screen
stage_idx[passed_screen] = 1
reject_reason[~passed_screen] = np.where(
    mw[~passed_screen] & (av[~passed_screen] != "full"),
    "availability_mismatch",
    RNG.choice(
        ["incomplete_application", "failed_knockout", "withdrew", "availability_mismatch"],
        size=(~passed_screen).sum(),
        p=[0.34, 0.30, 0.20, 0.16],
    ),
)

# --- stage 2: screened -> interview_scheduled  (P2)
p_sched = np.where(scarce, 0.45, 0.80)
p_sched = np.where(spike, p_sched - 0.07, p_sched)          # P7
p_sched = np.clip(p_sched, 0.05, 0.97)
adv = passed_screen & (u[:, 1] < p_sched)
stage_idx[adv] = 2
lost = passed_screen & ~adv
reject_reason[lost] = np.where(
    scarce[lost],
    "no_interview_slot",
    RNG.choice(["unresponsive", "withdrew", "recruiter_no_action"],
               size=lost.sum(), p=[0.55, 0.30, 0.15]),
)

# --- stage 3: interview_scheduled -> interview_completed
p_done = np.full(n, 0.78)
p_done = np.where(spike, p_done - 0.05, p_done)
prev = stage_idx == 2
adv = prev & (u[:, 2] < p_done)
stage_idx[adv] = 3
lost = prev & ~adv
reject_reason[lost] = "interview_no_show"

# --- stage 4: interview_completed -> offer_extended
p_offer = np.full(n, 0.71)
p_offer += np.where(src == "referral", 0.09, 0.0)
p_offer -= np.where(src == "jobboard_c", 0.10, 0.0)         # P4
p_offer = np.clip(p_offer, 0.05, 0.96)
prev = stage_idx == 3
adv = prev & (u[:, 3] < p_offer)
stage_idx[adv] = 4
lost = prev & ~adv
reject_reason[lost] = RNG.choice(
    ["not_qualified", "failed_background_check", "candidate_declined"],
    size=lost.sum(), p=[0.52, 0.19, 0.29],
)

# --- stage 5: offer_extended -> onboarding_started
p_onb = np.full(n, 0.88)
p_onb = np.where(spike, p_onb - 0.06, p_onb)
prev = stage_idx == 4
adv = prev & (u[:, 4] < p_onb)
stage_idx[adv] = 5
lost = prev & ~adv
reject_reason[lost] = RNG.choice(
    ["offer_declined", "unresponsive_after_offer"], size=lost.sum(), p=[0.58, 0.42]
)

df["stage_idx"] = stage_idx


# ---------------------------------------------------------------- dates

def add_days(base, lo, hi, mask):
    out = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    k = int(mask.sum())
    if k:
        out.loc[mask] = base[mask] + pd.to_timedelta(RNG.integers(lo, hi, k), unit="D")
    return out


applied = df["applied_at"]

m1 = df["stage_idx"] >= 1
screened_at = add_days(applied, 0, 4, m1)

m2 = df["stage_idx"] >= 2
# P2: scarce-slot sites make people wait
wait_lo = np.where(scarce, 4, 0)
wait_hi = np.where(scarce, 13, 4)
interview_scheduled_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
k = int(m2.sum())
if k:
    lo = wait_lo[m2.to_numpy()]
    hi = wait_hi[m2.to_numpy()]
    draws = RNG.integers(lo, hi)
    interview_scheduled_at.loc[m2] = screened_at[m2] + pd.to_timedelta(draws, unit="D")

m3 = df["stage_idx"] >= 3
interview_completed_at = add_days(interview_scheduled_at, 1, 7, m3)

m4 = df["stage_idx"] >= 4
offer_at = add_days(interview_completed_at, 0, 4, m4)

m5 = df["stage_idx"] >= 5
onboarding_started_at = add_days(offer_at, 0, 3, m5)

# The offer -> first shift gap. This is the P3 lever. Spike months and
# scarce-slot sites both stretch it.
gap_lo = np.where(spike, 3, 1)
gap_hi = np.where(spike, 16, 11)
gap = np.zeros(len(df), dtype=int)
k = int(m5.sum())
if k:
    gap[m5.to_numpy()] = RNG.integers(gap_lo[m5.to_numpy()], gap_hi[m5.to_numpy()])

planned_first_shift = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
planned_first_shift.loc[m5] = onboarding_started_at[m5] + pd.to_timedelta(gap[m5.to_numpy()], unit="D")

# --- stage 6: onboarding_started -> started, i.e. did they show for shift one
commute_lift = pd.Series(commute).map(
    {"0-5": 0.00, "6-10": 0.01, "11-20": 0.03, "21-40": 0.07, "40+": 0.11}
).to_numpy()                                                    # P6, deliberately modest

gap_lift = np.select(
    [gap <= 3, gap <= 7, gap <= 11],
    [0.00, 0.11, 0.22],
    default=0.30,
)                                                               # P3, dominant

p_no_show = 0.09 + gap_lift + commute_lift
p_no_show += np.where(src == "jobboard_c", 0.06, 0.0)
p_no_show -= np.where(src == "referral", 0.05, 0.0)
p_no_show += np.where(spike, 0.03, 0.0)
p_no_show = np.clip(p_no_show, 0.01, 0.85)

no_show = m5.to_numpy() & (u[:, 5] < p_no_show)
started = m5.to_numpy() & ~no_show
df.loc[started, "stage_idx"] = 6
reject_reason[no_show] = "no_show_first_shift"

first_shift_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
first_shift_at.loc[started] = planned_first_shift[started]


# ---------------------------------------------------------------- attrition

hired = df["stage_idx"] == 6
weak = df["_weak_manager"].to_numpy()
role_arr = df["role"].to_numpy()

# P5: manager effect is the real driver. Delivery Driver carries a small
# genuine penalty of its own, but nothing like the manager gap.
p_quit30 = np.full(len(df), 0.13)
p_quit30 += np.where(role_arr == "Delivery Driver", 0.04, 0.0)
p_quit30 += np.where(weak, 0.25, 0.0)
p_quit30 += np.where(src == "jobboard_c", 0.05, 0.0)
p_quit30 -= np.where(src == "referral", 0.05, 0.0)
p_quit30 = np.clip(p_quit30, 0.02, 0.80)

q = RNG.random(len(df))
quit30 = hired.to_numpy() & (q < p_quit30)
# a further slice leaves between day 31 and 90
quit90 = hired.to_numpy() & ~quit30 & (RNG.random(len(df)) < 0.11)

tenure = np.full(len(df), np.nan)
tenure[quit30] = RNG.integers(1, 31, quit30.sum())
tenure[quit90] = RNG.integers(31, 91, quit90.sum())

separation_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
sep_mask = quit30 | quit90
separation_at.loc[sep_mask] = first_shift_at[sep_mask] + pd.to_timedelta(
    tenure[sep_mask], unit="D"
)
# nobody separates in the future
future = separation_at > END
separation_at.loc[future] = pd.NaT
tenure[future.to_numpy()] = np.nan
sep_mask = sep_mask & ~future.to_numpy()

sep_reason = np.array([""] * len(df), dtype=object)
sep_reason[sep_mask] = RNG.choice(
    ["voluntary_quit", "schedule_conflict", "attendance", "found_other_job", "involuntary"],
    size=int(sep_mask.sum()),
    p=[0.31, 0.22, 0.18, 0.20, 0.09],
)


# ---------------------------------------------------------------- assemble

out = pd.DataFrame(
    {
        "application_id": df["application_id"],
        "location_id": df["location_id"],
        "region": df["region"],
        "hiring_manager_id": df["hiring_manager_id"],
        "role": df["role"],
        "source": df["source"],
        "commute_band_km": df["commute_band_km"],
        "availability_match": df["availability_match"],
        "applied_at": applied.dt.date,
        "screened_at": screened_at.dt.date,
        "interview_scheduled_at": interview_scheduled_at.dt.date,
        "interview_completed_at": interview_completed_at.dt.date,
        "offer_at": offer_at.dt.date,
        "onboarding_started_at": onboarding_started_at.dt.date,
        "scheduled_first_shift_at": planned_first_shift.dt.date,
        "first_shift_at": first_shift_at.dt.date,
        "stage_reached": [STAGES[i] for i in df["stage_idx"]],
        "exit_reason": reject_reason,
        "separation_at": separation_at.dt.date,
        "tenure_days": tenure,
    }
)
out["separation_reason"] = sep_reason
out.loc[out["separation_reason"] == "", "separation_reason"] = pd.NA
out.loc[out["exit_reason"] == "", "exit_reason"] = pd.NA
out["tenure_days"] = out["tenure_days"].astype("Float64").round(0).astype("Int64")

out = out.sort_values("applied_at").reset_index(drop=True)
out.to_csv(os.path.join(OUT_DIR, "frontline_pipeline_sample.csv"), index=False)


# ---------------------------------------------------------------- spend file

months = pd.date_range(START, END, freq="MS")
cpa = {
    "jobboard_a": 4.10,
    "jobboard_b": 5.40,
    "jobboard_c": 1.35,
    "referral": 0.00,
    "career_site": 0.30,
    "social": 3.20,
}
spend_rows = []
apps_by = out.copy()
apps_by["month"] = pd.to_datetime(apps_by["applied_at"]).dt.to_period("M").dt.to_timestamp()
grp = apps_by.groupby(["month", "source"]).size()
for (m, s), cnt in grp.items():
    rate = cpa[s] * (1.28 if m.month in (10, 11, 12) else 1.0)
    spend_rows.append(
        {
            "month": m.strftime("%Y-%m"),
            "source": s,
            "applications": int(cnt),
            "spend_usd": round(cnt * rate * RNG.uniform(0.94, 1.06), 2),
        }
    )
pd.DataFrame(spend_rows).to_csv(
    os.path.join(OUT_DIR, "sourcing_spend_sample.csv"), index=False
)

print(f"rows: {len(out):,}")
print(out["stage_reached"].value_counts().reindex(STAGES))
