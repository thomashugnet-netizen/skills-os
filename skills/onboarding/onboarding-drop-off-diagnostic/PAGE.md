# Onboarding Drop-off Diagnostic: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/dropoff.py --demo

## Example prompt

> Attached are two exports from our onboarding system for March to October: one row per accepted offer with its outcome, and one row per onboarding step with when it was requested and completed. We run 30 grocery stores and about one in six people who accept never work a shift. Where are we losing them, and what should we change first?

## Example output

From the skill's demo: `references/sample/bramblewood_hires.csv` and `bramblewood_steps.csv`, a planted onboarding log for a fictional 30-store grocery chain (4,926 accepted offers, 28,491 steps, March to October 2026), read as of 31 October 2026. An excerpt.

**The loss, counted honestly.** Of 4,548 hires whose first shift is already due, 726 (16%) never worked it: 573 withdrew before the day and 153 did not turn up on it. Set aside: 238 rescinded offers, 119 still in onboarding, and 21 already marked withdrew whose first shift is not yet due.

| Offer to first shift | Hires | Lost |
|---|---:|---:|
| 4-6 days | 1,754 | 10% |
| 7-9 days | 1,418 | 13% |
| 10-13 days | 972 | 25% |
| 14+ days | 373 | 32% |

**Where the days go.** Background check, vendor_a: median 2.8 days. vendor_b: median 7.0 days, 2.5 times the fastest. Drug test at a lab: 3.2 days; on site: 0.8. 40% of hires got their forms only after the background check came back (LOC-13: 75%).

**What drives it, tested within strata**

| Cause | Raw | After checks | Recoverable |
|---|---:|---:|---:|
| A gap of 10 days or more | +15.8 pts | +14.7 pts | ~198 |
| Drug test at an outside lab | +8.2 pts | +6.9 pts | ~118 |
| Site: LOC-11 | +13.6 pts | +13.6 pts | ~38 |
| 5 days or more with no contact in the first week | +9.5 pts | +6.7 pts | ~22 |

Explained by something else: vendor_b (+9.4 raw, the gap), Deli Clerk (+12.5 raw, the gap), LOC-29 (+13.6 raw, how its hires were processed). LOC-07 rescinds 18% of its offers but loses no more hires than anyone.

**The fixes (first three of five).** Schedule the first shift within 9 days of the offer; the longest wait you control is vendor_b, so put a turnaround in the contract or move those sites. Start the food handler card at the offer, not after the check, unless a rule requires the order. Never leave a hire 3 days without hearing from you: send the forms and order the uniform at the offer.
