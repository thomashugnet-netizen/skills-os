# Interview No-Show Playbook: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/noshow.py --demo

## Example prompt

> Here's our interview booking log for the last eight months, one row per booked interview across our 24 stores. A third of candidates don't show up. Why, and what should we change? For the texts: we're Fernhill & Co., the role is Sales Associate, interviews take about 20 minutes with Dana, the store manager. At Brookfield Outlets candidates should use Entrance C by the food court, the door with the green awning. They need a photo ID, and the store number is 555-0117.

## Example output

From the skill's demo: `references/sample/fernhill_bookings.csv`, a planted booking log for a fictional 24-store apparel retailer (7,349 bookings, March to October 2026), read as of 31 October 2026. An excerpt.

**The miss, counted honestly.** Of interviews still standing on the day, 34% were missed (2,152 of 6,405). 2,010 candidates missed their first interview; 421 were rebooked and came.

| Wait | Interviews | Missed |
|---|---:|---:|
| same day | 336 | 21% |
| 1 day | 850 | 22% |
| 2-3 days | 1,436 | 26% |
| 4-7 days | 1,995 | 39% |
| 8+ days | 1,225 | 50% |

**The calendar behind it.** LOC-04: median wait 9 days. Interviews on Tuesday only; one slot offered to 40%; one interviewer. Misses +8.3 pts against the other sites, -0.6 pts at the same wait: the wait is the problem, not the site. (Four more stores look the same.)

**What drives it, tested within strata**

| Driver | Raw | After checks | Recoverable |
|---|---:|---:|---:|
| A wait of 4 days or more | +19.0 pts | +18.2 pts | ~585 |
| A weekend inside the wait | +14.4 pts | +9.4 pts | ~205 |
| Role: Stockroom Associate | +15.1 pts | +15.0 pts | ~175 |
| Slots at 11:00-13:59 | +7.9 pts | +7.1 pts | ~91 |
| One slot offered | +8.0 pts | +5.1 pts | ~66 |
| Site: LOC-17 | +12.7 pts | +12.6 pts | ~46 |

Explained by something else: busy weeks (+7.5 raw, the wait), slots before 10:00 (+11.2 raw, role), self-scheduled (-5.8 raw, the wait).

**After a miss.** At LOC-06, LOC-11, LOC-15, LOC-23 no first miss was ever rebooked (275 misses), while the other sites rebooked 39%. That is a rule, not candidate choice. Unanswered 24-hour reminders missed 61% of the time, confirmed ones 9%.

**Slot rules (first four of 14).** Book every interview within 3 days. LOC-04: open a second interview day. Offer at least two slots, always. Stop offering 11:00-13:59 slots, or keep them for candidates who choose them.

**At booking** (272 characters): "Fernhill & Co.: you're booked for your Sales Associate interview, {date} at {time}, about 20 min. Go to Entrance C by the food court, the door with the green awning and ask for Dana, the store manager. Bring a photo ID. Need to move it? Reply 2. Reply STOP to opt out."

**30 minutes after a missed slot:** "Fernhill & Co.: we missed you at {time}. Things happen. Want another Sales Associate interview? Reply A for {slot_1} or B for {slot_2}."

**Check:** READY.
