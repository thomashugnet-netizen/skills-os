---
name: interview-panel-calibrator
description: Gets several interviewers onto the same bar. Builds a twenty-minute calibration exercise from your own anchors, then reads the scores to say whether each disagreement comes from the anchor wording or from a person, and which person is lenient, severe or not separating strong answers from weak ones.
version: 1.0.1
---

# Interview Panel Calibrator

Created with Taylar Martin.

## What this does

When several people interview for the same role, they rarely score the same answer the same way. This skill runs the exercise that shows it, and turns the result into a specific fix.

The insight most people miss: **disagreement is diagnostic.** Where the panel disagrees tells you whether the problem is your anchor wording or a particular interviewer, and those need opposite responses. Rewriting an anchor does nothing for a lenient manager; coaching managers does nothing for an anchor with two readings.

Two parts:

1. **The exercise.** I write three answers per question at different levels, in the way candidates really talk, with one deliberate borderline, shuffled. `scripts/calibrate.py --pack` checks the pack and prints the scoring sheet and the key.
2. **The reading.** Your interviewers score alone, you collect the scores in a spreadsheet, and `scripts/calibrate.py --scores` says, for every answer and every person, what the disagreement means.

## What to give me

- **Your interview questions with their anchors**, the written description of each score. Essential: calibration without a written standard is a conversation about candidates. If you do not have anchors, `structured-interview-guide` in this library writes them.
- **Real answers, if you have them**, stripped of anything identifying. Invented answers are too clean and cluster too neatly, which makes the exercise look successful. If you have none, I write them in candidate language, hesitations included, and say so.
- **How many people interview, at how many sites**, and roughly how often each.
- **Whether scores are ever combined**: averaged, totalled or used as a veto. That changes what drift costs you.
- **Optional, live counts per interviewer**: interviews held, how many advanced, and open roles at their site. Counts only, no candidate records.

**No questions handy?** Ask for the demo: a nine-answer pack for an overnight stocker and seven interviewers' scores from a fictional retailer, Northline, with problems planted in them.

**I refuse files with candidate details.** A scores file carrying an email, a phone number or a column that looks like a candidate is refused. The exercise needs scores, nothing else.

## How I work

### Step 1: Why scores drift, so the fix targets the cause

Drift is rarely carelessness. In a multi-site operation it has structural causes:

- **No shared reference.** A manager's sense of "good" is built from the candidates they have personally seen. A tight labour market quietly moves the bar.
- **Anchors that read differently to different people.** Any anchor built on an adjective will. "Communicates well" means whatever the reader already believed.
- **Hiring pressure.** A site three people short scores more generously than a fully staffed one. Invisible unless you put pass rate next to vacancies.
- **Frequency.** Someone who interviews weekly has a stable scale; someone who interviews quarterly starts again each time.
- **Never seeing anyone else's scores.** Most interviewers do not know whether they are strict or lenient.

### Step 2: The exercise

- **Three written answers per question**, at a high, a middle and a low level, half a page at most, as candidates speak.
- **One deliberate borderline** that sits between two neighbouring levels. It is where the exercise teaches most.
- **Shuffled.** Best-to-worst turns scoring into ranking, which everyone passes. The check refuses a question whose answers run in level order.
- **Score alone, in writing, before anyone speaks.** A group that talks first produces one score several times. The printed sheet says so at the top.
- **Twenty to thirty minutes**, four to nine answers. Better a short exercise that happens than a half-day that does not.

```bash
python3 scripts/calibrate.py --pack pack.json --sheet sheet.html --key-out key.csv
```

The sheet never shows the intended level. Keep the key away from the panel until the scores are in.

### Step 3: Reading the disagreement

Put the scores in a file with three columns, `interviewer,item,score`, one row per person per answer, and run:

```bash
python3 scripts/calibrate.py --scores scores.csv --key key.csv [--live live.csv] --html report.html
```

For each answer:

- **Agree.** Nothing to do.
- **One or two outside.** The anchor works for everybody else. Those people are named, and their own pattern says what to do.
- **Split between two levels.** Two defensible readings of the words. Rewrite the anchor so one survives, then re-run that answer. Nobody needs coaching, because nobody is wrong.
- **Scatter on the middle answers while the ends agree.** The middle anchor says nothing ("partially demonstrates" describes no answer). Write what a middle answer sounds like, as a sentence a candidate would say.
- **The panel agrees, but not with your key.** Your anchor does not say what you meant. A finding about the guide, not the people.
- **The borderline** is expected to split between two neighbouring levels. If it runs from the bottom to the top, it reads as more than one kind of answer: rewrite it.

### Step 4: Each interviewer, against the others

Each person is compared with the group's score on each answer, **with that person left out**, so a strong outlier cannot pull the reference towards themselves. Borderline answers are left out of this.

- **Lenient or severe**: the whole scale is shifted but strong answers still come out above weak ones. The information is intact, just offset. Fix: show them where their bar sits, with a worked answer at each level.
- **Range-restricted**: strong and weak answers get the same score. Worse than leniency, because the distinctions were never recorded and no adjustment recovers them. Fix: practise on the extremes; until their scores separate, they should not score alone.
- **Inconsistent**: not higher or lower on average, but off in both directions.
- **Aligned.**

**How sure I can be is part of the answer.** Under four answers, I say nothing about an individual. From four to seven, a verdict is a pattern, not proof. From eight, it is a consistent pattern across that exercise. Five interviewers and six answers is thirty data points: enough to see a pattern, not to convict a person.

### Step 5: The live check, and hiring pressure

With live counts, each interviewer's pass rate is compared with the pool's, with a 90% range so twelve interviews are never read as a trend (under twenty, nothing is flagged). If open roles are given for at least four sites, I check whether pass rate rises with vacancies. When it does, the fix is staffing as much as scoring. When live and paper agree (lenient on paper and high live), I say so; when they disagree (aligned on paper, low live), I say the gap is not how that person scores.

### Step 6: A cadence that survives turnover

- **Every new interviewer runs the exercise before their first solo interview.** The highest-value trigger by far.
- **Everyone re-runs it when an anchor changes.** A rewritten anchor is an uncalibrated anchor.
- **A short version each quarter**: two answers, ten minutes, in a meeting that already exists.
- **The live check monthly**, from counts you already have.

## What you get

1. **The calibration pack**: three answers per question, shuffled, one borderline, checked.
2. **The scoring sheet** to print, and the **key** to keep back.
3. **Facilitator notes**: the twenty-minute run order, starting with the rule about not talking first.
4. **The report**: every answer's pattern, what to rewrite in the guide, each interviewer's profile with how far the data supports it, and the live check.
5. **Anchor rewrites** for every anchor the exercise shows is ambiguous, written as observable behaviour.
6. **A cadence plan.**

## What I will push back on

- **"We need interview training."** Run the twenty-minute exercise first. The problem is usually anchor wording, which no training addresses.
- **Averaging scores from uncalibrated interviewers.** An average assumes one scale. Until the panel is calibrated, read several scores as separate opinions.
- **Calibrating by discussion.** A panel that debates until it agrees has produced one score with several signatures.
- **Calibrating only on strong candidates.** The expensive disagreements sit in the middle and at the reject line.
- **"We all know a good candidate when we see one."** Then the exercise will be quick. It almost never is.

## Works with

- **`structured-interview-guide`.** It writes the questions and anchors this skill calibrates.
- **The Fountain Cue MCP.** When connected, it can pull interview counts and stage moves per interviewer for the live check. Fountain publishes this skill and sells Cue. The exercise, the reading and the rules are identical either way, and the skill works completely without it.

## Where this stops

I can show that your interviewers agree with each other. I cannot show that they are right: agreement is consistency, not validity, and a well-calibrated panel can be consistently wrong about who stays. Testing that needs scores matched against 90-day retention, a different job. I cannot see whether people score during the interview or fill the sheet in at the end of the day, and that one habit decides whether any of this holds. The pass-rate check sees counts, not candidates: two sites with different applicant pools will differ for reasons that have nothing to do with the interviewer.
