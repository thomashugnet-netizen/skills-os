# Onboarding Drop-off Diagnostic

> Finds where and why accepted hires never reach their first shift: which step they were waiting on, whose side each wait was on, and which causes survive once the gap is held equal. Then writes the fixes.

Created with Anita Chandrasekhar. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The count:** of hires whose first shift is already due, how many never worked it, with withdrawals and first-shift no-shows kept apart. Rescinded offers are counted separately, by the step that failed, because pulling an offer is a decision, not a drop-off. Hires still in onboarding are set aside, including the ones already marked withdrew, and early leavers who never got a first shift date are counted once their cohort is decided.

**The gap:** the loss by days from offer to the scheduled first shift.

**Where the days go:** for every onboarding step, your queue (offer to request) and the turnaround (request to done), by vendor and by method, and which sites send the forms only after the background check clears.

**When people leave:** the steps still open at each withdrawal, and the withdrawals per 100 hire-days spent waiting on each step.

**The causes:** a long gap, a silent first week, a lab drug test, and every site, vendor, role, source and recruiter, each tested inside the strata that usually fake it, and named only if it clears the bar across everything tested together. What fails is listed as explained by something else, and no fix is built on it.

**The fixes:** the longest gap to allow, the vendor or step that sets it, forms and uniform at the offer, the lab test, the site whose loss is on the day. And the two numbers to watch.

## Why it exists

Hourly hires accept more than one offer, and they keep looking while they wait. Every day between the offer and the first shift is a day another employer can call first, and most onboarding is built to make those days longer: a background check that takes a week at some vendors, a certificate that starts only after it, forms sent once the check clears so nobody "wastes" them, a drug test at a lab the hire has to get to. Each looks like its own problem, and each gets its own fix. Most of them are one problem.

On the demo, a fictional 30-store grocery chain loses 16% of its accepted hires before the first shift. The loss climbs from 10% at a 4 to 6 day gap to 32% at 14 days or more; a gap of 10 days or more costs 15 points at the same store, role and month. One background check vendor returns checks in a median 7 days against 2.8, and its hires lose more, but no more than anyone else at the same gap: the vendor matters because it sets the gap. The Deli Clerk role looks worse for the same reason: its food handler card starts after the check. A drug test at a lab costs 7 points at the same gap. A silent first week costs 7. One store loses 14 points more, almost all of it as no-shows on the first day. And the store that rescinds 18% of its offers on failed checks does not lose hires at all; it screens late.

## Install

**1. Download** [onboarding-drop-off-diagnostic.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/onboarding-drop-off-diagnostic.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the onboarding drop-off demo."* Then attach your exports: *"We lose people between offer and first shift. Where, and what should we change?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/onboarding/onboarding-drop-off-diagnostic ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | Columns | |
|---|---|---|
| hires | `hire_id, offer_accepted_at, first_shift_scheduled_at, outcome` + `withdrawn_at, rescinded_at, location_id, role, source, recruiter_id, commute_band_km` | required |
| steps | `hire_id, step, requested_at` + `completed_at, result, vendor, method, needs_hire` | best |

`outcome` is `started`, `withdrew`, `no_show`, `rescinded`, or blank while in onboarding; common ATS words (hired, declined, NCNS, revoked) are read too. Steps such as `background_check`, `drug_test`, `i9_section1`, `tax_forms`, `uniform`, `orientation` and `food_handler_card` are recognised under their usual names; any other step is kept under its own. Opaque ids only: a file with a name, email, phone, address or notes column, or people's names in an id column, is refused. A pipeline export (one row per application) is refused with a pointer to `funnel-drop-off-analyst`.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Grocery, retail and QSR | Strong | Checks, uniforms and orientation at many stores, and enough hires per store to test each cause. |
| Logistics and warehousing (W2) | Strong | Background checks, drug tests and safety training before the first shift, at volume. |
| Healthcare support (CNA, home care) | Partial | The read fits; credential and licence checks lengthen the gap for reasons a schedule change will not fix. |
| Staffing agencies | Partial | Works per client site; the client's own onboarding steps are often missing from the log. |
| Gig sign-up funnels | Does not fit | No scheduled first shift: activation is a different question. |
| Salaried hiring | Does not fit | Too few hires per site, and notice periods set the gap. |

## How well it finds things

The demo was redrawn 20 times with the same causes planted and different chance:

| Cause | Found |
|---|---|
| A gap of 10 days or more | 20 of 20 |
| A lab drug test | 20 of 20 |
| A silent first week (about 320 hires exposed) | 16 of 20 |
| One store at +15 points (about 275 hires) | 10 of 20 |
| A store, vendor, role or recruiter named for something it does not cause | 0 of 20 |

A single store needs volume to be named. When it is not, it stays in the counts and timings, and the report says nothing was proven rather than guessing.

## Verifying this yourself

```bash
python3 scripts/dropoff.py --test
```

75 checks, all inside the download. The sample was generated with known answers by `references/sample/generate.py` (listed in `bramblewood_expected.json`): the gap, the silent week, the lab test and one store must come back, and nothing else; the slow vendor and the Deli Clerk role must be explained by the gap; no store with lab tests or long gaps may be named for them; the store with the most failed checks must appear under rescinded and never as a cause. Two worlds with nothing planted and three shuffles of the sample must name no cause. The early leavers with no first shift date must be counted, recent ones must not, and a company whose gaps are all long must still get a gap read. 100 damaged files must each be refused or read, never crash; before release, 2,000 more ran without a crash.

Exit codes: 0 read; 3 input refused; 4 the engine itself failed.

## Who it's for

- **Heads of talent operations** who own the stretch between offer and first shift.
- **Onboarding coordinators** who chase checks, forms and uniforms.
- **Field HR and district managers** whose stores lose hires before day one.
