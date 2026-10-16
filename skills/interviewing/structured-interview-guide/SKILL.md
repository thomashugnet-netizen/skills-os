---
name: structured-interview-guide
description: Builds a fifteen-minute frontline interview a store or site manager can run the same way every time, without training, and checks the questions managers ask today for the ones that are a legal risk or predict nothing.
version: 1.0.0
---

# Structured Interview Guide

> **This is not legal advice.** It flags interview questions that are commonly unlawful or risky, and helps you prepare a consistent interview. What may be asked differs by state and city and changes over time; the rules file in this skill does not. Each rule in `references/question_rules.json` names an official source where there is one. Confirm local rules before relying on the check.

## What this does

Two things. **I build** the interview a busy manager will actually run: short, scripted, scored on the spot, the same every time. And **I check** the questions your managers ask today, one by one, for the ones that are a legal risk or tell you nothing about the job.

The insight is that in frontline hiring the interviewer is a store manager between deliveries, not a recruiter, and has had no interview training. So the guide does the thinking: what to say, what to ask, what a good answer sounds like, and what to do with the score. Every departure from structure is a place where a decision gets made on rapport, and where a question like "do you have kids?" slips in.

## What to give me

To build a guide:

- **The role**, and what separates someone who lasts six months from someone who leaves in three weeks. That second part matters most, and it is usually not skills.
- **How long the interview can really be.** If it is ten minutes, I design for ten.
- **Who runs it**, and whether it is in person, by phone or on a walk-in basis.
- **The shift pattern, the site and the pay**, so the questions can be specific.

To check questions: paste them, one per line, as managers ask them now.

**No role handy?** Ask for the demo: a guide for an overnight stocker in `references/sample/`, and twelve questions a fictional store manager asks today.

## How I work

### Step 1: Four to six questions, chosen for what predicts staying

In fifteen minutes, six questions is two minutes each with the answer. I pick them in this order:

1. **Reliability and getting there**: a real example, and the plan for getting to the first shift and home again.
2. **A realistic preview, tested**: the hardest true part of the job, then how they have handled something like it. It screens, and it lets people screen themselves out.
3. **Availability confirmed out loud**: repeating what the application said and getting a spoken yes catches many week-two schedule conflicts.
4. **One behaviour the role turns on**: safety, customer pressure, working alone, pace.
5. **Their questions.** Someone asking about shift patterns or progression is thinking about staying.

### Step 2: Anchors from 1 to 3, printed under each question

Not 1 to 5: untrained interviewers cluster in the middle of a five-point scale. Each score has a written description of what that answer sounds like. Scoring happens during the interview, because scores written afterwards are memory.

### Step 3: Everything the manager would otherwise improvise

The opening and closing script, a follow-up for the one-word answer, a decision rule (the score that advances, the score that does not, and what happens in between), three red and three green flags you can see or hear, and a list of the questions managers reach for, with what to ask instead.

### Step 4: The check

`scripts/check_guide.py` grades the guide against a rubric the code enforces: question count and timing, anchors present and distinct, one question at a time, a reading level a candidate can follow between shifts, a decision rule that fits the scores, and every piece of text on the sheet run through the question rules, anchors and flags included, because "has kids at home" written under a score decides the hire as surely as asking it. It prints each finding with its reason and exits non-zero when the guide is not ready. A guide in the wrong shape is refused with the field named. The same rules check a pasted list of questions.

When a risky yes/no question comes back, I do not reword it into "tell me about a time you...". A personal question asked open-ended is the same question. I replace it with the job requirement behind it, or drop it.

## What you get

1. **The guide**, as a one-page sheet to print or open on a phone (`--html`), with a score box beside each question.
2. **The check report** for questions you already use: each one marked as a legal risk, needs care, weak, or no rule matched, with the reason, the source, and a safe question that gets the same information. I never call a question "fine": no rule matching is not a clearance.

```bash
python3 scripts/check_guide.py --guide guide.json --html guide.html
python3 scripts/check_guide.py --questions questions.txt --html check.html
```

## What I will push back on

- **"I can tell in two minutes."** You can tell who you like. The anchors are there so that two managers at two sites would score the same answer the same way.
- **"Tell me about yourself."** It is unstructured, hard to score, and the easiest place for a protected topic to come up unasked.
- **Asking about children, health or a car to find out about availability.** Ask about the shifts, the lifting, and how they would get there, the same way for everyone.

## Calibration, when several people interview

Consistency across interviewers is where structure breaks. If several people run the guide, ask me for a calibration pack: three written answers per question at different levels, for your interviewers to score separately and compare. Where they disagree, the anchor needs sharpening. `interview-panel-calibrator` in this library takes that further.

## Verify before you rely on it

- what your state and city allow you to ask about pay history and criminal history, and when
- whether any role has a legal minimum age or a licence you may lawfully ask about
- that any physical requirement you mention is genuinely part of the job
- how your organisation handles requests for accommodation during hiring
- whether any rule in `references/question_rules.json` has changed since its checked date

## Works with

- **`job-ad-writer`.** The ad and the interview should describe the same job, including the hard parts.
- **`candidate-message-sequencer`.** It gets candidates to the interview; this decides what happens there.
- **The Fountain Cue MCP.** When connected, it can bring the guide to the interviewer with the candidate's application. Fountain publishes this skill and sells Cue. The guide, the check and the rules are identical either way, and the skill works completely without it.

## Where this stops

I produce the guide and check questions. I cannot see whether anyone uses it, whether two interviewers score the same answer the same way, or whether the hires it selected lasted. The check catches the questions it has rules for; a risky question phrased in a way it has not seen can pass, so it is a second pair of eyes, not a guarantee. The rules are written for English: text in another language is reported as not checked. The checker does not check that anchor 3 describes a better answer than anchor 1; I read that myself. Questions that are lawful to ask, such as whether someone has failed a drug test or been fired, are not flagged.
