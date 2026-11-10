# Resume-Free Triage Rubric

> Builds and checks the rubric that decides who gets a call first when most applicants have no resume, bands the open queue to the calls your team can make, and shows which signals actually predict who stays.

Created with Darrell Clack. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The rubric:** six signals that survive having no work history (shift overlap with the shifts you are short of, start latency, the travel plan for the earliest shift, one concrete reliability answer, and, lightly, rota experience and certifications), with points and a knockout list short enough to read aloud.

**The check:** blocks the rubric until it passes. Distance, a radius, gaps, tenure, a resume, education and past rejections are never scored. Availability and every other signal score points and are never a gate. Knockouts are a minimum age, a licence the law requires with its legal basis, or work authorization, three at most, the same gates the phone screen uses. Questions about age, family, health, religion, citizenship, arrests, pay history or gaps are blocked, and so is a reliability self-rating. A first-job applicant must be able to reach the call-today line.

**The queue:** every open applicant in a band sized to your call capacity (call today, call if the top band runs dry, hold with the reason, knockout), a route to another site when their availability fits it, a hold for the next rota when it fits nowhere, and the blanks to confirm on the call instead of a zero.

**The evidence:** with past hires and their 30-day outcome, whether each signal's higher answer stays better within the same shift overlap; travel levels scored apart that retain alike; what a radius would have cut; and, with voluntary self-ID, each group's call-today rate against the four-fifths line and the signal that opens any gap.

## Why it exists

Most hourly applicants have never written a CV, because nobody asked them for one, so "read the resume" turns into whatever the list happens to sort by. The rubrics that replace it go wrong in the same two places: a commute radius, because distance looks objective, and availability as a filter, because filters are easy to configure. Both feel decisive, and both quietly remove people you would have hired, in ways your funnel never shows, because rejected applicants generate no further data.

On the demo, a fictional four-warehouse operator gets 172 applications a week and can make 150 calls. Its draft rubric pays a car more than a stated bus route with a time for the earliest shift. Its own past hires show the two stay the same, and the car premium puts one self-identified group at 0.76 of the other's call-today rate, under the four-fifths line. Rota experience carries 17% of the points and predicts nothing. A 10 km radius would cut 85 of the 300 people the rubric calls this week, 61 of them with a car or a route with a time, and the people outside it stayed no worse. The revised rubric scores the route like the car, moves the points to shift overlap and start date, separates stayers from leavers at least as well, and clears the flag.

## Install

**1. Download** [resume-free-triage-rubric.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/resume-free-triage-rubric.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the resume-free triage demo."* Then: *"Most of our warehouse applicants have no resume. Build us a rubric for who to call first. Here is our application form and the shifts we are short of."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/screening/resume-free-triage-rubric ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | Columns | |
|---|---|---|
| rubric | JSON: `calls_per_week`, `sites` with their shift `gaps`, `signals` with points, `knockouts` | required |
| applicants | `applicant_id, applied_at, site` + `availability, available_from, travel, reliability, rota_experience, certifications`, one column per knockout, and if you have them `distance_km, reapplicant, called, hired, hired_at, started, day30` | to band the queue |
| groups | `applicant_id, group`, voluntary self-ID only | optional |

Availability is day and part of day (`sat_night; sun_early`; "Saturday nights" and "weekends early" are read too). Travel is coded as `route_with_time`, `own_transport`, `route_no_time` or `no_plan`; the skill codes free-text answers before scoring. Common ATS words for outcomes (Hired, Active, Terminated) are read. Opaque ids only: a name, email, phone, address or notes column, or names in the id column, is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Warehousing and logistics (W2) | Strong | High volume, early and night shifts, no resumes, and transport decides who arrives. |
| Grocery, retail and QSR | Strong | Many sites with different gaps, so routing replaces rejection. |
| Hospitality and facilities | Strong | Split and weekend shifts make overlap the deciding signal. |
| Healthcare support (CNA, home care) | Partial | Works for availability and travel; licensure is a real knockout and needs its legal basis named. |
| Staffing agencies | Partial | Works per client site; the client's shift gaps must be known. |
| Salaried or professional hiring | Does not fit | Work history is the signal there, and volume does not need triage. |

## How well it finds things

The demo was redrawn 20 times with the same effects planted and different chance:

| Planted | Found |
|---|---|
| Shift overlap, start latency and the travel plan predict staying | 20 of 20 each |
| A concrete reliability answer predicts staying (a 5 to 6 point effect) | 12 of 20 |
| The car premium puts self-identified group_2 under four-fifths | 15 of 20 |
| The revised rubric puts any group under four-fifths | 0 of 20 |
| A 10 km radius makes no difference to staying | 20 of 20 |
| Rota experience or certifications, which do nothing, named as earning | 3 of 40 |

In 20 worlds with nothing planted, 6 of 120 signal checks came out as earning, about what 90% ranges allow. A signal the read cannot separate is reported as that, not as proof it does nothing.

## Verifying this yourself

```bash
python3 scripts/triage.py --test
```

99 checks, all inside the download. The sample was generated with known answers by `references/sample/generate.py` (listed in `marlow_expected.json`): the four planted signals must earn their points and rota experience must not; the car premium must be named and must be what puts group_2 under four-fifths; the radius must show no difference; the revised rubric must be ready, clear the flag and separate stayers at least as well. 36 broken rubrics must each be blocked for the right reason, and a blocked rubric scores nobody. A blank must be half points and a question for the call, a re-applicant must score exactly as anyone else, distance must never move a score, and an applicant who fits another site must be routed there. Three worlds with nothing planted and two shuffles of the outcomes must name no signal. 100 damaged files must each be refused or read, never crash; before release, 2,600 more ran without a crash.

Exit codes: 0 read; 3 input refused or rubric blocked; 4 the engine itself failed.

## Who it's for

- **Talent acquisition leads** who own the rubric and the rules recruiters follow.
- **Recruiting coordinators** working an application queue they cannot call in full.
- **HR and compliance partners** who need to know what the rubric screens out, and who.
