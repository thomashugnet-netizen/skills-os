"""
Generates the public synthetic datasets for the Claude Skills for HR Ops library.

Four Fountain ICPs, one causal structure
----------------------------------------
There is one generator and one set of planted patterns, rendered into the four
segments Fountain actually sells into: retail, quick service restaurants,
logistics and delivery (W2), and gig delivery. That is deliberate. P1-P8 below
are truths about frontline hiring, not about drive-throughs: a stricter
screening rule in one region, a throttled step, a gap before day one driving
no-shows, a cheap channel that converts badly, a handful of managers with poor
retention. All of them happen in a warehouse, a store and a courier app alike.

What changes between segments is the vocabulary a reader recognises -- what a
location is called, the roles, the channels, the compliance steps before day
one, the season that hurts -- and the shape of the gap before the first shift,
which is the one structural difference that genuinely distinguishes these
verticals. A crew hire starts on Saturday; a driver waits for a DOT medical.

Gig is the exception, and deliberately so. A marketplace sign-up is never
interviewed and never given an offer: it submits documents, clears a background
check, and is either activated by a first completed job or is never heard from
again. So the gig dataset is projected onto a five-stage funnel -- the same
simulation, two stages collapsed, the exit vocabulary remapped. Projecting
rather than re-simulating is what lets the same eight assertions run against
both shapes, which is a much stronger claim than running them four times
against four copies of one funnel.

Keeping the skeleton identical (the same 42 locations, the same manager ids,
the same eight patterns) has a second benefit: the regression suite runs
unchanged against all four, which proves an engine is finding the real
structure rather than overfitting one file's quirks.

Design goals
------------
1. No personal data of any kind. There are no names, emails, phone numbers,
   addresses or dates of birth in any output, by construction. Every entity is
   an opaque id.
2. Realistic shape for a multi-site hourly employer: 42 locations, 4 regions,
   5 roles, 7 pipeline stages (5 for gig), 12 months, a seasonal spike.
3. Real, discoverable causal structure -- including two deliberate confounds, so
   a skill that only looks at correlation gets the answer wrong.

Embedded patterns, in the order a correct analysis should rank them:
  P1  One region runs a hard availability knockout at screening.
      Screening pass rate ~28% vs ~62% elsewhere. Largest absolute loss.
  P2  Eight locations have scarce interview self-schedule slots.
      screened -> interview_scheduled collapses; the wait lengthens.
  P3  Days from offer to first shift drives no-shows. Long gap ~3.5x the
      no-show rate of a short gap.
  P4  One cheap, high-volume channel converts to started terribly.
  P5  Five hiring managers have ~3x baseline 30-day attrition. CONFOUND:
      those managers sit on sites heavy in one role, so a naive cut blames
      the role. Within-role, the manager effect survives.
  P6  Long commute bands raise no-shows, but materially less than P3.
  P7  The seasonal spike degrades cycle time and no-show rate.
  P8  RED HERRING: weekend applications convert worse, but only because the
      cheap channel skews to weekends. Controlling for source removes it.

Deterministic: each industry is seeded, so every published CSV is reproducible.

    python3 generate.py              # all four, next to this file
    OUT_DIR=/tmp python3 generate.py # somewhere else, to diff
"""

import os

import numpy as np
import pandas as pd

OUT_DIR = os.environ.get("OUT_DIR") or os.path.dirname(os.path.abspath(__file__))

START = pd.Timestamp("2025-09-01")
END = pd.Timestamp("2026-08-31")

# Structural skeleton, identical across industries so the regression suite and
# every planted pattern transfer unchanged.
REGIONS = {"Midwest": 11, "Northeast": 10, "South": 12, "West": 9}
SCARCE_SITES = ["LOC-03", "LOC-07", "LOC-14", "LOC-19", "LOC-25", "LOC-31",
                "LOC-36", "LOC-40"]
WEAK_MANAGERS = ["MGR-004", "MGR-012", "MGR-021", "MGR-029", "MGR-038"]
EXTRA_HEAVY_SITES = ["LOC-09", "LOC-17", "LOC-27", "LOC-33"]

STAGES = ["applied", "screened", "interview_scheduled", "interview_completed",
          "offer_extended", "onboarding_started", "started"]

# The gig funnel is not a different simulation, it is the same one seen through
# a marketplace's vocabulary. A sign-up is never interviewed and never given an
# offer, so those two stages collapse: whoever cleared the scheduling gate has
# cleared a background check, and whoever received an offer is waiting on
# onboarding. Projecting rather than re-simulating is the point -- it is what
# lets the same eight planted patterns be asserted against both shapes.
ACTIVATION_STAGES = ["signed_up", "docs_submitted", "background_clear",
                     "onboarding_started", "activated"]
ACTIVATION_IX = [0, 1, 1, 2, 2, 3, 4]
ACTIVATION_REASONS = {
    "availability_mismatch": "docs_rejected",
    "withdrew": "abandoned_signup",
    "no_interview_slot": "background_check_queue",
    "recruiter_no_action": "no_onboarding_slot",
    "interview_no_show": "abandoned_signup",
    "not_qualified": "failed_vehicle_check",
    "candidate_declined": "abandoned_signup",
    "no_show_first_shift": "no_show_first_job",
}

COMMUTE_BANDS = ["0-5", "6-10", "11-20", "21-40", "40+"]
COMMUTE_W = [0.28, 0.27, 0.22, 0.15, 0.08]


# --------------------------------------------------------------- industries

INDUSTRIES = [
    {
        # The original dataset. Its values and code path are unchanged, so it
        # regenerates byte-identically -- the regression suite depends on it.
        "slug": "frontline", "label": "Retail & multi-site",
        "pipeline_file": "frontline_pipeline_sample.csv",
        "spend_file": "sourcing_spend_sample.csv",
        "seed": 20260909,
        "place": "store",
        "roles": ["Sales Associate", "Cashier", "Stocker", "Shift Supervisor",
                  "Seasonal Associate"],
        "role_w": [0.40, 0.20, 0.16, 0.09, 0.15],
        "heavy_role": "Seasonal Associate",
        "heavy_w": [0.24, 0.13, 0.10, 0.06, 0.47],
        "sources": ["jobboard_a", "jobboard_b", "jobboard_c", "referral",
                    "career_site", "social"],
        "source_w": [0.20, 0.14, 0.31, 0.09, 0.14, 0.12],
        "cheap_source": "jobboard_c",
        "spike_months": (10, 11, 12), "spike": 2.4, "base_volume": 1100,
        "gap": (1, 11), "gap_spike": (3, 16),
        "onboarding_exits": ["offer_declined", "unresponsive_after_offer"],
        "onboarding_exit_w": [0.58, 0.42],
        "cpa": {"jobboard_a": 4.10, "jobboard_b": 5.40, "jobboard_c": 1.35,
                "referral": 0.00, "career_site": 0.30, "social": 3.20},
    },
    {
        "slug": "qsr", "label": "Quick service restaurants",
        "seed": 20260910,
        "place": "restaurant",
        "roles": ["Crew Member", "Drive-Thru", "Cook", "Shift Leader",
                  "Delivery Driver"],
        "role_w": [0.46, 0.18, 0.20, 0.07, 0.09],
        "heavy_role": "Delivery Driver",
        "heavy_w": [0.28, 0.12, 0.14, 0.05, 0.41],
        "sources": ["jobboard_a", "text_to_apply", "jobboard_c", "referral",
                    "career_site", "social"],
        "source_w": [0.16, 0.18, 0.33, 0.11, 0.10, 0.12],
        "cheap_source": "jobboard_c",
        # Summer is the crunch, and the funnel is the shortest of the four:
        # a crew hire can start on Saturday.
        "spike_months": (5, 6, 7), "spike": 2.1, "base_volume": 1600,
        "gap": (0, 8), "gap_spike": (1, 12),
        "onboarding_exits": ["offer_declined", "unresponsive_after_offer",
                             "took_other_offer"],
        "onboarding_exit_w": [0.44, 0.38, 0.18],
        "cpa": {"jobboard_a": 3.60, "text_to_apply": 2.10, "jobboard_c": 1.10,
                "referral": 0.00, "career_site": 0.25, "social": 2.80},
    },
    {
        "slug": "logistics", "label": "Logistics & delivery",
        "seed": 20260911,
        "place": "station",
        "roles": ["Warehouse Associate", "Package Handler", "Delivery Driver",
                  "Dispatcher", "Team Lead"],
        "role_w": [0.36, 0.30, 0.13, 0.12, 0.09],
        "heavy_role": "Delivery Driver",
        "heavy_w": [0.17, 0.15, 0.58, 0.06, 0.04],
        "sources": ["jobboard_a", "jobboard_b", "jobboard_c", "referral",
                    "career_site", "staffing_agency"],
        "source_w": [0.18, 0.13, 0.30, 0.12, 0.11, 0.16],
        "cheap_source": "jobboard_c",
        # Peak season, and the longest pre-start gauntlet of the four:
        # background check, drug screen, DOT medical, road test.
        "spike_months": (10, 11, 12), "spike": 2.6, "base_volume": 1250,
        "gap": (3, 18), "gap_spike": (5, 24),
        "onboarding_exits": ["failed_drug_screen", "failed_dot_medical",
                             "failed_background_check", "offer_declined",
                             "unresponsive_after_offer"],
        "onboarding_exit_w": [0.22, 0.14, 0.18, 0.26, 0.20],
        "cpa": {"jobboard_a": 5.80, "jobboard_b": 6.40, "jobboard_c": 1.90,
                "referral": 0.00, "career_site": 0.40, "staffing_agency": 12.50},
    },
    {
        # The one structurally different funnel. A gig marketplace has no
        # interview and no offer: a sign-up submits documents, clears a
        # background check, and is either activated by a first completed job or
        # is never heard from again. Same eight patterns, five stages.
        "slug": "gig", "label": "Delivery & courier (gig)",
        "seed": 20260913,
        "stage_profile": "activation",
        "place": "market",
        "roles": ["Car Courier", "Bike Courier", "Scooter Courier",
                  "Cargo Van Driver", "Shopper"],
        "role_w": [0.41, 0.19, 0.14, 0.11, 0.15],
        # Cargo van sign-ups need more paperwork, so they cluster in the markets
        # with the weakest onboarding owners -- that is the P5 confound here.
        "heavy_role": "Cargo Van Driver",
        "heavy_w": [0.21, 0.12, 0.09, 0.47, 0.11],
        "sources": ["paid_social", "app_store_organic", "search_ads",
                    "worker_referral", "affiliate", "jobboard_a"],
        # Paid social is the volume monster and the worst converter: the whole
        # gig problem in one column.
        "source_w": [0.34, 0.16, 0.14, 0.10, 0.14, 0.12],
        "cheap_source": "paid_social",
        # Holiday delivery peak, and by far the largest sign-up volume of the
        # four -- low activation on a very big top of funnel is the ICP's
        # actual complaint.
        "spike_months": (11, 12, 1), "spike": 1.8, "base_volume": 3200,
        "gap": (2, 14), "gap_spike": (3, 20),
        "onboarding_exits": ["never_completed_docs", "unresponsive_after_clear",
                             "failed_vehicle_check", "failed_insurance_check"],
        "onboarding_exit_w": [0.37, 0.29, 0.20, 0.14],
        "cpa": {"paid_social": 2.60, "app_store_organic": 0.10,
                "search_ads": 4.80, "worker_referral": 0.00,
                "affiliate": 3.90, "jobboard_a": 5.10},
    },
]


# --------------------------------------------------------------- build

def write_spend(out, profile, rng):
    """Monthly spend per channel, priced off the applications that channel
    actually produced. Same for every funnel shape."""
    spend_months = profile["spike_months"]
    spend_rows = []
    apps_by = out.copy()
    apps_by["month"] = pd.to_datetime(apps_by["applied_at"]).dt.to_period("M").dt.to_timestamp()
    grp = apps_by.groupby(["month", "source"]).size()
    for (m, s), cnt in grp.items():
        rate = profile["cpa"][s] * (1.28 if m.month in spend_months else 1.0)
        spend_rows.append({"month": m.strftime("%Y-%m"), "source": s,
                           "applications": int(cnt),
                           "spend_usd": round(cnt * rate * rng.uniform(0.94, 1.06), 2)})
    spend_name = profile.get("spend_file", f"{profile['slug']}_spend_sample.csv")
    pd.DataFrame(spend_rows).to_csv(os.path.join(OUT_DIR, spend_name), index=False)
    return spend_name


def build(profile):
    rng = np.random.default_rng(profile["seed"])
    roles = profile["roles"]
    role_w = profile["role_w"]
    sources = profile["sources"]
    source_w = profile["source_w"]
    cheap = profile["cheap_source"]
    spike_months = profile["spike_months"]

    # ----------------------------------------------------------- locations
    rows, n = [], 0
    for region, count in REGIONS.items():
        for _ in range(count):
            n += 1
            rows.append({"location_id": f"LOC-{n:02d}", "region": region})
    loc = pd.DataFrame(rows)

    # P2: eight locations with scarce interview slots, spread across regions
    loc["slot_scarce"] = loc["location_id"].isin(SCARCE_SITES)

    # One hiring manager per location.
    loc["hiring_manager_id"] = [f"MGR-{i:03d}" for i in range(1, len(loc) + 1)]

    # P5: five managers with poor early retention. Their sites are also heavy
    # in one role -- that is the deliberate confound.
    loc["weak_manager"] = loc["hiring_manager_id"].isin(WEAK_MANAGERS)
    loc["role_heavy"] = loc["weak_manager"] | loc["location_id"].isin(EXTRA_HEAVY_SITES)

    # Baseline site volume weight.
    loc["volume_w"] = rng.uniform(0.55, 1.75, len(loc))
    LOC = loc

    def in_spike(ts):
        return ts.month in spike_months

    # ----------------------------------------------------------- volume
    months = pd.date_range(START, END, freq="MS")
    VOLUME = {}
    for m in months:
        mult = profile["spike"] if m.month in spike_months else 1.0
        VOLUME[m] = int(profile["base_volume"] * mult * rng.uniform(0.92, 1.08))

    # ----------------------------------------------------------- draw rows
    recs = []
    seq = 0
    loc_w = LOC["volume_w"].to_numpy() / LOC["volume_w"].sum()

    for month, count in VOLUME.items():
        days_in_month = month.days_in_month
        for _ in range(count):
            seq += 1
            li = rng.choice(len(LOC), p=loc_w)
            site = LOC.iloc[li]

            applied = month + pd.Timedelta(days=int(rng.integers(0, days_in_month)))
            if applied > END:
                applied = END

            # P8 setup: the cheap channel skews to weekend applications.
            src = rng.choice(sources, p=source_w)
            if src == cheap and applied.dayofweek < 5 and rng.random() < 0.42:
                applied = applied + pd.Timedelta(days=int(5 - applied.dayofweek))
                if applied > END:
                    applied = END

            weights = role_w.copy()
            if site["role_heavy"]:
                weights = profile["heavy_w"]
            role = rng.choice(roles, p=weights)

            recs.append({
                "application_id": f"APP-{seq:06d}",
                "location_id": site["location_id"],
                "region": site["region"],
                "hiring_manager_id": site["hiring_manager_id"],
                "role": role,
                "source": src,
                "applied_at": applied,
                "commute_band_km": rng.choice(COMMUTE_BANDS, p=COMMUTE_W),
                "_slot_scarce": bool(site["slot_scarce"]),
                "_weak_manager": bool(site["weak_manager"]),
            })
    df = pd.DataFrame(recs)

    # ----------------------------------------------------------- availability
    # P1: one region applies a hard availability knockout. Availability itself
    # is distributed the same everywhere -- only the screening rule differs.
    avail = rng.choice(["full", "partial", "limited"], size=len(df), p=[0.46, 0.34, 0.20])
    df["availability_match"] = avail

    # ----------------------------------------------------------- progression
    n = len(df)
    u = rng.random((n, 6))

    stage_idx = np.zeros(n, dtype=int)
    reject_reason = np.array([""] * n, dtype=object)

    src = df["source"].to_numpy()
    region = df["region"].to_numpy()
    av = df["availability_match"].to_numpy()
    scarce = df["_slot_scarce"].to_numpy()
    spike = df["applied_at"].apply(in_spike).to_numpy()
    commute = df["commute_band_km"].to_numpy()

    # --- stage 1: applied -> screened
    p_screen = np.full(n, 0.62)
    p_screen += np.where(src == "referral", 0.16, 0.0)
    p_screen += np.where(src == "career_site", 0.06, 0.0)
    p_screen -= np.where(src == cheap, 0.14, 0.0)                 # P4
    mw = region == "Midwest"
    p_screen = np.where(mw & (av == "full"), 0.60, p_screen)      # P1
    p_screen = np.where(mw & (av == "partial"), 0.16, p_screen)
    p_screen = np.where(mw & (av == "limited"), 0.02, p_screen)
    p_screen = np.clip(p_screen, 0.01, 0.95)

    passed_screen = u[:, 0] < p_screen
    stage_idx[passed_screen] = 1
    reject_reason[~passed_screen] = np.where(
        mw[~passed_screen] & (av[~passed_screen] != "full"),
        "availability_mismatch",
        rng.choice(
            ["incomplete_application", "failed_knockout", "withdrew",
             "availability_mismatch"],
            size=(~passed_screen).sum(), p=[0.34, 0.30, 0.20, 0.16]),
    )

    # --- stage 2: screened -> interview_scheduled  (P2)
    p_sched = np.where(scarce, 0.45, 0.80)
    p_sched = np.where(spike, p_sched - 0.07, p_sched)            # P7
    p_sched = np.clip(p_sched, 0.05, 0.97)
    adv = passed_screen & (u[:, 1] < p_sched)
    stage_idx[adv] = 2
    lost = passed_screen & ~adv
    reject_reason[lost] = np.where(
        scarce[lost], "no_interview_slot",
        rng.choice(["unresponsive", "withdrew", "recruiter_no_action"],
                   size=lost.sum(), p=[0.55, 0.30, 0.15]))

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
    p_offer -= np.where(src == cheap, 0.10, 0.0)                  # P4
    p_offer = np.clip(p_offer, 0.05, 0.96)
    prev = stage_idx == 3
    adv = prev & (u[:, 3] < p_offer)
    stage_idx[adv] = 4
    lost = prev & ~adv
    reject_reason[lost] = rng.choice(
        ["not_qualified", "failed_background_check", "candidate_declined"],
        size=lost.sum(), p=[0.52, 0.19, 0.29])

    # --- stage 5: offer_extended -> onboarding_started
    # Where the compliance gauntlet lives: the exit vocabulary is what makes a
    # logistics funnel legible as a logistics funnel.
    p_onb = np.full(n, 0.88)
    p_onb = np.where(spike, p_onb - 0.06, p_onb)
    prev = stage_idx == 4
    adv = prev & (u[:, 4] < p_onb)
    stage_idx[adv] = 5
    lost = prev & ~adv
    reject_reason[lost] = rng.choice(
        profile["onboarding_exits"], size=lost.sum(),
        p=profile["onboarding_exit_w"])

    df["stage_idx"] = stage_idx

    # ----------------------------------------------------------- dates
    def add_days(base, lo, hi, mask):
        out = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
        k = int(mask.sum())
        if k:
            out.loc[mask] = base[mask] + pd.to_timedelta(rng.integers(lo, hi, k), unit="D")
        return out

    applied = df["applied_at"]

    m1 = df["stage_idx"] >= 1
    screened_at = add_days(applied, 0, 4, m1)

    m2 = df["stage_idx"] >= 2
    wait_lo = np.where(scarce, 4, 0)                              # P2
    wait_hi = np.where(scarce, 13, 4)
    interview_scheduled_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    k = int(m2.sum())
    if k:
        lo = wait_lo[m2.to_numpy()]
        hi = wait_hi[m2.to_numpy()]
        interview_scheduled_at.loc[m2] = screened_at[m2] + pd.to_timedelta(
            rng.integers(lo, hi), unit="D")

    m3 = df["stage_idx"] >= 3
    interview_completed_at = add_days(interview_scheduled_at, 1, 7, m3)

    m4 = df["stage_idx"] >= 4
    offer_at = add_days(interview_completed_at, 0, 4, m4)

    m5 = df["stage_idx"] >= 5
    onboarding_started_at = add_days(offer_at, 0, 3, m5)

    # The offer -> first shift gap. This is the P3 lever, and the one number
    # that genuinely differs by industry: a crew hire starts on Saturday, a
    # nurse waits for credentialing.
    lo_base, hi_base = profile["gap"]
    lo_spike, hi_spike = profile["gap_spike"]
    gap_lo = np.where(spike, lo_spike, lo_base)
    gap_hi = np.where(spike, hi_spike, hi_base)
    gap = np.zeros(len(df), dtype=int)
    k = int(m5.sum())
    if k:
        gap[m5.to_numpy()] = rng.integers(gap_lo[m5.to_numpy()], gap_hi[m5.to_numpy()])

    planned_first_shift = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    planned_first_shift.loc[m5] = onboarding_started_at[m5] + pd.to_timedelta(
        gap[m5.to_numpy()], unit="D")

    # --- stage 6: did they show for shift one
    commute_lift = pd.Series(commute).map(
        {"0-5": 0.00, "6-10": 0.01, "11-20": 0.03, "21-40": 0.07, "40+": 0.11}
    ).to_numpy()                                                  # P6, modest

    gap_lift = np.select([gap <= 3, gap <= 7, gap <= 11],
                         [0.00, 0.11, 0.22], default=0.30)        # P3, dominant

    p_no_show = 0.09 + gap_lift + commute_lift
    p_no_show += np.where(src == cheap, 0.06, 0.0)
    p_no_show -= np.where(src == "referral", 0.05, 0.0)
    p_no_show += np.where(spike, 0.03, 0.0)
    p_no_show = np.clip(p_no_show, 0.01, 0.85)

    no_show = m5.to_numpy() & (u[:, 5] < p_no_show)
    started = m5.to_numpy() & ~no_show
    df.loc[started, "stage_idx"] = 6
    reject_reason[no_show] = "no_show_first_shift"

    first_shift_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    first_shift_at.loc[started] = planned_first_shift[started]

    # ----------------------------------------------------------- attrition
    hired = df["stage_idx"] == 6
    weak = df["_weak_manager"].to_numpy()
    role_arr = df["role"].to_numpy()

    # P5: the manager effect is the real driver. The heavy role carries a small
    # genuine penalty of its own, but nothing like the manager gap.
    p_quit30 = np.full(len(df), 0.13)
    p_quit30 += np.where(role_arr == profile["heavy_role"], 0.04, 0.0)
    p_quit30 += np.where(weak, 0.25, 0.0)
    p_quit30 += np.where(src == cheap, 0.05, 0.0)
    p_quit30 -= np.where(src == "referral", 0.05, 0.0)
    p_quit30 = np.clip(p_quit30, 0.02, 0.80)

    q = rng.random(len(df))
    quit30 = hired.to_numpy() & (q < p_quit30)
    quit90 = hired.to_numpy() & ~quit30 & (rng.random(len(df)) < 0.11)

    tenure = np.full(len(df), np.nan)
    tenure[quit30] = rng.integers(1, 31, quit30.sum())
    tenure[quit90] = rng.integers(31, 91, quit90.sum())

    separation_at = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns]")
    sep_mask = quit30 | quit90
    separation_at.loc[sep_mask] = first_shift_at[sep_mask] + pd.to_timedelta(
        tenure[sep_mask], unit="D")
    future = separation_at > END
    separation_at.loc[future] = pd.NaT
    tenure[future.to_numpy()] = np.nan
    sep_mask = sep_mask & ~future.to_numpy()

    sep_reason = np.array([""] * len(df), dtype=object)
    sep_reason[sep_mask] = rng.choice(
        ["voluntary_quit", "schedule_conflict", "attendance", "found_other_job",
         "involuntary"],
        size=int(sep_mask.sum()), p=[0.31, 0.22, 0.18, 0.20, 0.09])

    # ----------------------------------------------------------- assemble
    if profile.get("stage_profile") == "activation":
        gidx = [ACTIVATION_IX[i] for i in df["stage_idx"]]
        out = pd.DataFrame({
            "application_id": df["application_id"],
            "location_id": df["location_id"],
            "region": df["region"],
            "hiring_manager_id": df["hiring_manager_id"],
            "role": df["role"],
            "source": df["source"],
            "commute_band_km": df["commute_band_km"],
            "availability_match": df["availability_match"],
            "applied_at": applied.dt.date,
            "docs_submitted_at": screened_at.dt.date,
            "background_clear_at": interview_completed_at.dt.date,
            "onboarding_started_at": onboarding_started_at.dt.date,
            "scheduled_first_job_at": planned_first_shift.dt.date,
            "first_job_at": first_shift_at.dt.date,
            "stage_reached": [ACTIVATION_STAGES[i] for i in gidx],
            "exit_reason": [ACTIVATION_REASONS.get(r, r) for r in reject_reason],
            "separation_at": separation_at.dt.date,
            "tenure_days": tenure,
        })
        out["separation_reason"] = sep_reason
        out.loc[out["separation_reason"] == "", "separation_reason"] = pd.NA
        out.loc[out["exit_reason"] == "", "exit_reason"] = pd.NA
        out["tenure_days"] = out["tenure_days"].astype("Float64").round(0).astype("Int64")
        out = out.sort_values("applied_at").reset_index(drop=True)

        pipeline_name = profile.get("pipeline_file", f"{profile['slug']}_pipeline_sample.csv")
        out.to_csv(os.path.join(OUT_DIR, pipeline_name), index=False)
        spend_name = write_spend(out, profile, rng)
        return {"label": profile["label"], "rows": len(out),
                "started": int((out["stage_reached"] == "activated").sum()),
                "pipeline": pipeline_name, "spend": spend_name}

    out = pd.DataFrame({
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
    })
    out["separation_reason"] = sep_reason
    out.loc[out["separation_reason"] == "", "separation_reason"] = pd.NA
    out.loc[out["exit_reason"] == "", "exit_reason"] = pd.NA
    out["tenure_days"] = out["tenure_days"].astype("Float64").round(0).astype("Int64")
    out = out.sort_values("applied_at").reset_index(drop=True)

    pipeline_name = profile.get("pipeline_file", f"{profile['slug']}_pipeline_sample.csv")
    out.to_csv(os.path.join(OUT_DIR, pipeline_name), index=False)

    spend_name = write_spend(out, profile, rng)

    started_n = int((out["stage_reached"] == "started").sum())
    return {"label": profile["label"], "rows": len(out), "started": started_n,
            "pipeline": pipeline_name, "spend": spend_name}


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    for prof in INDUSTRIES:
        r = build(prof)
        print(f"{r['label']:<28} {r['rows']:>7,} applications  "
              f"{r['started']:>6,} started   {r['pipeline']}")
