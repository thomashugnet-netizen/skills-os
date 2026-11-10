---
name: resume-free-triage-rubric
description: Builds and checks the rubric that decides who gets a call first, for hourly roles where most applicants have no resume. Scores shift overlap, start date, the travel plan for the earliest shift and one concrete reliability answer, never distance, gaps or tenure; bands the open queue to the calls your team can make; and, with past hires, shows which signals actually predict who stays.
version: 1.0.0
---

# Resume-Free Triage Rubric

Created with Darrell Clack.

## What this does

Builds the rubric your team uses to decide who gets a call, for roles where most applicants attach nothing and the rest attach a document written for a different job. It replaces "read the CV" with a few scored signals that predict starting and staying, and it is built so the two signals that feel most decisive, where someone lives and when they can work, score rather than reject.

`scripts/triage.py` checks the rubric and blocks it until it passes, then scores your application export against it: a band for every open applicant sized to the calls your team can make, a route instead of a rejection when someone fits another site, and a question for the call instead of a zero for a blank. With past hires and their 30-day outcome, it shows whether each signal earns its points. Same files, same answer, every time.

## How this differs from the phone screen

Triage decides who gets called, from what the form collected. `phone-screen-script` is the call itself: it confirms availability, the journey and the gates out loud and books the interview. The knockouts here are the same three gates the phone screen uses, so nobody passes one and fails the other. Wording on the form is checked by `bias-language-checker`; where people abandon the form is `funnel-drop-off-analyst`.

## What to give me

- **The role, the sites, and the shifts each site is short of.** Essential. Availability is scored against the holes in your rota, as day and part of day ("sat_night", "sun_early"), not against "any hours".
- **Calls your team can make a week.** Essential. This sets every threshold.
- **What your application form asks**, word for word. The rubric can only score what you collect.
- **Requirements that are genuinely hard**: a minimum age, a licence the law requires for every shift, work authorization.
- **The earliest shift at each site**, and what transport runs to it.
- **An application export**, to band the queue. Best with past hires and whether they reached day 30.
- **Voluntary self-ID**, if you collect it, in a separate two-column file.

Where you can't tell me one of these, I name the part of the rubric that is then guesswork rather than filling it in quietly.

## Before you paste anything

Opaque applicant ids only. If a file holds a name, email, phone number, address or notes column, or names in the id column, the engine stops and asks you to re-export. Self-ID stays in its own file with nothing but `applicant_id, group`.

## How I work

### Step 1: Establish what you are triaging for

Triage is not ranking. It answers one question: who gets a call today, given that eight hundred people applied and your team can make forty calls. A rubric returning two hundred "call now" applicants has triaged nothing.

### Step 2: Score the signals that survive having no work history

| Signal | Scored as | Why it predicts |
|---|---|---|
| **Shift overlap** | Hours of your unfilled shifts they can work, as a share | The strongest signal. A mismatch produces the hire who leaves in week three |
| **Start latency** | Days from applying to the date they can start | Monday beats five weeks away; five weeks is long enough for three other employers |
| **Travel plan** | Four levels, for the earliest shift | A plan that works at 5am beats a short distance with no plan |
| **Reliability, asked concretely** | "Have you worked shifts that start before 7am?" | One answer about something they did beats any self-rating |
| **Rota experience** | Has worked to a rota, ever | Weak: it makes training easier, nothing more |
| **Certifications** | A bonus where they save training | A knockout only where the law makes them one |

Rota experience and certifications together stay under 15% of the points.

### Step 3: Code the answers the form collected

The engine scores coded answers, so I code free text first and show you the coding:

- **Travel**: `route_with_time` (a route and a time for the earliest shift: "the 42 bus, gets in at 5:10"), `own_transport` (car, bike, a lift they name), `route_no_time` ("I'll get the bus"), `no_plan` (nothing, or "it's fine").
- **Availability**: day and part of day, `early`, `late` or `night`. "Any time" is read as everything and marked to confirm on the call, because people tick availability generously on a phone.

### Step 4: Weight travel and availability without turning them into knockouts

These two go wrong the same way every time: they get built as filters, because filters are easy to configure.

**Travel.** Straight-line distance is a bad proxy for arriving at a 6am start. Ten kilometres with a car is twelve minutes; four kilometres with one bus that starts at 06:40 is impossible. A radius excludes people without a car, which tracks income, age and disability. So travel scores on the plan, and a route with a time should score like a car: both are plans.

**Availability.** Scored as overlap, never as a gate. Someone who cannot do Saturday nights may be exactly who another site needs for weekend mornings, so the engine routes them there; with no overlap anywhere this week, they are held for the next rota change, not rejected.

A signal becomes a knockout only if the answer means you cannot legally employ this person for any shift at any site. Otherwise it is points.

### Step 5: Handle gaps, first jobs, re-applicants and blanks

- **Gaps** are neither asked nor scored. Asking routes into health, caring and pregnancy and puts the answer in your record.
- **First jobs**: no work history is one absent signal. An applicant must be able to clear the call-today line on overlap, start date, travel and reliability alone; the engine checks it.
- **Re-applicants** score like anyone else. A rejection for a rota that no longer exists is not evidence about the person.
- **Blanks** score half the points and become a question for the call. Scoring them as zero rejects everyone who abandoned a slow form on a phone; the engine says how many that would have been.

### Step 6: Check the rubric

The check blocks the rubric, with the reason, when it scores distance, a radius, gaps, tenure, a resume, education or a past rejection; makes availability or any signal a gate; has a knockout that is not a minimum age, a required licence with its legal basis, or work authorization, or more than three; asks about age, family, health, religion, citizenship, arrests, pay history or gaps; asks reliability as a self-rating; orders travel levels backwards; has no capacity or no shift gaps; or puts the call-today line where a first job cannot reach it. It advises when owning a car scores more than a route with a time, when weak signals carry more than 15%, and when overlap carries less than 25%.

### Step 7: Band the queue

Open applicants from the last two weeks get three bands, sized to your calls: call today, call if the top band runs dry, and hold with a stated reason. Plus knockouts, routes and holds for the next rota. I show how the call-today band moves if the line shifts five points.

### Step 8: Check the weights against who stayed

With past hires and whether they reached day 30, each signal's higher answer is compared with its lower answer within the same shift overlap, with 90% ranges: earns its points, cannot be told apart, or works against you. Travel levels scored apart that retain alike are named. With a distance column, I show what a radius would have cut and whether the people outside it stayed any worse. With self-ID, I show each group's call-today rate against the highest, flag anything under four-fifths, and name the signal that opens the gap.

Only hired people have an outcome. Once the rubric decides who gets called, the signals it never lets through can no longer be checked, so I recommend calling a small random slice of the hold band each month.

## What you get

1. **The rubric**: signals, points, knockouts, on one page, as `rubric.json`. READY, or the exact list to fix.
2. **The banded queue**: every open applicant with a band, a rank, a route and what to confirm on the call (`--out scored.csv`).
3. **Fields to fix on the form**: signals not collected, or blank too often.
4. **The outcome check**, the radius read and the adverse-impact read, when you have the data.

```bash
python3 scripts/triage.py --rubric rubric.json
python3 scripts/triage.py --rubric rubric.json --applicants applicants.csv --groups groups.csv --out scored.csv
```

## What I'll push back on

- **Treating no resume as no experience.** Most people who have held three shift jobs have never written a CV.
- **A commute radius.** It reads as objective and excludes people twenty minutes away on a bus.
- **Availability as a hard filter.** The most common way frontline employers manufacture their own shortage.
- **Scoring stability from tenure.** Warehouse and hospitality churn is structural.

## Verifying this yourself

```bash
python3 scripts/triage.py --test
```

The sample (`references/sample/generate.py`, a fictional warehouse operator) was generated with known answers: overlap, start date, the travel plan and reliability predict staying; rota experience, certifications and distance do not; a route with a time retains like a car, and the draft rubric pays the car more, which puts one self-identified group under four-fifths. The suite checks each comes back, that the revised rubric clears the flag, that 36 broken rubrics are each blocked for the right reason, that worlds with nothing planted and shuffled outcomes name no signal, and that 100 damaged files are refused or read without a crash.

## Works with

- **`phone-screen-script`** makes the call this rubric decides to make.
- **`bias-language-checker`** checks the wording of the form questions.
- **The Fountain Cue MCP.** When connected, it can supply the open applications with their answers and past hires' outcomes, so the queue is banded as it fills rather than from an export. Fountain publishes this skill and sells Cue. The rubric, the check and the numbers are identical either way, and the skill works completely without it.

## Where this stops

This designs and checks the rubric and bands a queue; it cannot see the people your earlier rules rejected, and it cannot verify any answer: the journey and availability are confirmed out loud on the call. The outcome check describes your past hires, not the applicants you never hired. The adverse-impact read is a flag, not a clearance, and nothing here is legal advice: anything automated should be reviewed by someone qualified with your own legal position in front of them.
