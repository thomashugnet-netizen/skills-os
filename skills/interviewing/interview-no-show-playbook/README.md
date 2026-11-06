# Interview No-Show Playbook

> Finds why booked interviews get missed, usually the calendar rather than the candidate, then writes the slot rules, the confirm, remind and re-offer texts and the reschedule path that fix it, and checks every message before you send it.

Created with Courtney Barabas-Esperance. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The read:** from a booking log (one row per booked interview) or a pipeline export. The miss counted honestly: cancelled in advance is not a silent no-show, rebooked and attended is not a loss, and the candidates who never got a slot are counted beside the misses. The wait between booking and interview first, with the calendar behind it named site by site. Then every other suspect: a weekend inside the wait, the hour of the slot, one slot instead of a choice, self-scheduling, format, commute, every site, interviewer, source and role. Each is tested inside the strata that usually fake it, and named only if it clears the bar across everything tested together. What fails is listed as explained by something else, and no rule is built on it.

**After a miss:** how fast misses get rebooked and what comes of it, any site that never rebooks a miss, and whether a missing reply to the 24-hour reminder flags the miss a day ahead.

**The playbook:** slot rules with your numbers in them, the text sequence word for word (confirmation at booking with the landmark and door, a reply reminder, a morning-of text, a re-offer within the hour with two slots, a close that keeps them eligible), and the reschedule path.

**The check:** `scripts/noshow.py --check` blocks a sequence, with the reason, until every message names who is writing and carries its elements, fits two text messages, asks nobody to log in and keeps its timing, and until the policy rebooks a first miss instead of rejecting it.

## Why it exists

Frontline candidates are working somewhere else while they wait for your interview, with the least control over their hours of anyone you hire. A slot nine days out, on the one day the manager interviews, crossing a weekend with no word from you, gets missed, and the usual fix is another reminder or a rule that rejects anyone who no-shows. Neither touches the calendar, and the second throws away candidates you already paid for.

On the demo, a fictional apparel retailer with 24 stores misses 34% of booked interviews. Waits of 4 days or more miss 18 points more often than shorter ones at the same store and in the same role, and 55% of interviews wait that long. Five stores interview on one weekday only: median wait 9 days, and once the wait is equal they miss like everyone else, so the fix is a second interview day, not a talk with the manager. A weekend inside the wait costs 9 points, a midday slot 7, one slot instead of a choice 5; one outlet-mall store misses 13 points more in every week at every wait. Four stores never rebooked a single miss. Unanswered 24-hour reminders missed 61% of the time, confirmed ones 9%. Self-scheduling looks better, and is not once the wait is equal.

## Install

**1. Download** [interview-no-show-playbook.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/interview-no-show-playbook.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the interview no-show demo."* Then attach your booking log: *"Why are people missing interviews at our stores, and what should we change?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/interviewing/interview-no-show-playbook ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | What | |
|---|---|---|
| booking log | `application_id, booked_at, interview_at, outcome` + `location_id, role, hiring_manager_id, source, slots_offered, mode, format, confirmed, commute_band_km` | best |
| pipeline export | `application_id, interview_scheduled_at, stage_reached, exit_reason` (+ `interview_at` for the wait) | counts misses and never-booked, not the wait |
| facts | JSON in the shape of `references/sample/fernhill_facts.json` | for the playbook |
| messages | JSON in the shape of `references/sample/fernhill_messages.json` | to check your own sequence |

`outcome` is `attended`, `no_show`, `cancelled`, `rescheduled`, `employer_cancelled`, or blank for upcoming. Opaque ids only: a file with a name, email, phone, address or notes column, or people's names in an id column, is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and specialty apparel | Strong | Store managers interview between shifts, every store keeps its own calendar, and volume is high enough to test each cause. |
| Quick-service restaurants | Strong | Same-day and next-day bookings at many sites; the hour and the wait decide most misses. |
| Logistics and warehousing (W2) | Strong | Candidates on shifts elsewhere, early starts, sites that are hard to reach. |
| Healthcare support (CNA, home care) | Partial | The read and the texts fit; credential checks and panels lengthen waits for reasons a calendar rule will not fix. |
| Hiring events and walk-in days | Partial | Booked event slots read fine; walk-ins have no booking to read. |
| Gig sign-up funnels | Does not fit | No interview stage. The engine refuses the export and says why. |
| Salaried hiring with panels | Does not fit | Too few interviews per site to test a cause, and several rounds per candidate. |

## Verifying this yourself

```bash
python3 scripts/noshow.py --test
```

125 checks, 122 of them inside the download (three read samples that live only in the repository). The sample log was generated with known answers by `references/sample/generate.py` (listed in `fernhill_expected.json`): the wait, the weekend, the midday slot, one slot offered, the stockroom role and one hard-to-find store must come back, and nothing else; self-scheduling, early slots and busy weeks must be explained by the wait or the role, the one-day stores must look like everyone else once the wait is equal, and the hard-to-find store's interviewer must not be reported apart from the store. The same log with outcomes shuffled, three times, and a world with nothing planted must name no cause. A wait that is really a site must not be reported as the wait, and a reversal within sites must be explained by site. On the library's pipeline samples it must refuse the wait, find the 1,000 candidates who never got a slot at the same eight sites, and find the busy-season effect and nothing else. 30 damaged copies of the sample sequence must each be blocked for the right reason. Before release, 6,000 damaged booking logs, pipeline exports and sequences ran without a crash.

Exit codes: 0 read, or sequence ready; 1 sequence not ready; 3 input refused; 4 the engine itself failed.

## Who it's for

- **Field talent acquisition leaders** running hiring across many stores.
- **Recruiting coordinators** who book interviews and chase the misses.
- **Store and district managers** who hold the interview calendar.
