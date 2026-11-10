# Resume-Free Triage Rubric: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/triage.py --demo

## Example prompt

> We hire warehouse associates at four sites and almost nobody sends a resume. We get about 170 applications a week and can make 150 calls. Attached: our current scoring rubric, the shifts each site is short of, and an export of applications since June with who we hired and who was still there at 30 days, plus our voluntary self-ID file. Who should we call first, and is our rubric right?

## Example output

From the skill's demo: `references/sample/marlow_rubric.json` read against `marlow_applicants.csv` and `marlow_groups.csv`, a planted application log for a fictional four-warehouse operator (3,200 applications, 15 June to 30 October 2026, 683 past hires with a 30-day outcome). An excerpt.

**The rubric: READY, WITH ADVICE.** Owning a car scores 100% of the travel points and a route with a time 50%. Both are plans for the earliest shift. Rota experience and certifications carry 17% of the points; keep them under 15%.

**The queue.** 362 open applicants from the last 14 days; about 172 applications a week; your team can make 150 calls a week.

| Band | Applicants | What happens |
|---|---:|---|
| Call today | 150 | score 57.3 or more; call within the day |
| Call if the top band runs dry | 150 | score 38.5 or more; this week |
| Hold, with the reason | 51 | kept, not rejected |
| Knockout | 11 | a minimum age or work authorization answered no |

23 routed to another site whose gaps they fit; 9 held for the next rota change. 31 in call today have a blank to confirm on the call; scored as zero, 16 of them would have dropped out of the band.

**Does each signal earn its points?** 683 past hires, compared within the same shift overlap, 90% ranges.

| Signal | Higher answer vs lower | Range | Verdict |
|---|---:|---|---|
| Shift overlap | +18.2 pts | +10.4 to +25.9 | earns its points |
| Start latency | +18.2 pts | +10.8 to +25.7 | earns its points |
| Travel plan for the earliest shift | +16.2 pts | +6.9 to +25.5 | earns its points |
| Reliability, asked concretely | +13.2 pts | +6.3 to +20.2 | earns its points |
| Has worked to a rota | +2.0 pts | -4.7 to +8.8 | cannot be told apart |

Travel: 'own_transport' scores 50% of the travel points more than 'route_with_time', but people who answered 'route_with_time' stayed as well. Your outcomes do not back the extra points.

**What a 10 km radius would do.** No difference in staying anyone can measure, and it would remove 85 of the 300 applicants this rubric calls this week, 61 of them with a car or a route with a time for the earliest shift.

**Who the call-today line reaches.** group_2 reaches call today at 0.76 of group_1's rate, under the four-fifths line. The gap comes mostly from the travel plan for the earliest shift.
