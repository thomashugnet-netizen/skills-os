# Structured Interview Guide

> Builds the fifteen-minute interview a store or site manager can run the same way every time, without training, and checks the questions managers ask today for the ones that are a legal risk.

Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**Build:** describe the role and what makes people stay, and get a one-page guide: opening and closing script, four to six questions chosen for what predicts staying in shift work, a 1-to-3 score with a written description under each question, follow-ups for one-word answers, a decision rule, red and green flags, and the questions not to ask with what to ask instead.

**Check:** paste the questions your managers ask today, and each one comes back marked as a legal risk, needing care, weak, or no rule matched, with the reason, an official source where there is one, and a safe question that gets the same information.

Both run through `scripts/check_guide.py`, a dependency-free checker, so the guide is graded against a written rubric rather than taken on trust.

## Why it exists

In frontline hiring the interviewer is a manager between deliveries, not a recruiter. Without a script, each one asks different questions, decides on rapport, and sooner or later asks something like "do you have kids?" On the sample, half of the twelve questions a fictional store manager asks today are a legal risk somewhere, and three more are weak.

## Install

**1. Download** [structured-interview-guide.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/structured-interview-guide.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the interview guide demo."* Then: *"Build a 15-minute interview for overnight stockers"*, or *"Check these interview questions: ..."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/interviewing/structured-interview-guide ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## What the check looks for

Fourteen kinds of risky question: age (including graduation year and "are you retired"), marriage, children and caring, disability and health (including medication, treatment and past sick days), height and weight, religion, national origin and citizenship, sex and orientation, arrests and criminal history before an offer, pay history, personal finances, union membership and views, military discharge, photos and social media, and car ownership as a stand-in for getting to work. Two more catch the indirect versions: "what do you do on Sundays?" and "what's your background?". Plus six kinds of weak question: yes/no, brainteasers, "tell me about yourself", "biggest weakness", "five years", and two questions in one.

Words that are only a risk when they are about the candidate (kids, husband, church, accent, anxiety, arrest) are skipped when the question is about a customer, a teammate or a place, so "a customer's kids were running around the store" and "our store is near First Baptist Church" pass, and "do you have kids?" does not. The common ways people type are read too: "r u", "d0 you", "Do you have chldren".

The guide rubric: four to six questions, timing inside an interview of 5 to 30 minutes, anchors exactly 1 to 3, written out and different from each other, one question at a time and under sixty words, a reading level of grade 8 or below, the three questions that predict staying present, a decision rule in whole numbers that fits the scores and can actually reject someone, concrete flags, and every piece of text on the sheet (questions, probes, scripts, anchors, flags, the decision rule and the role title) run through the rules above. A guide in the wrong shape is refused with the field named.

**The rules are written for English.** A question in another language is reported as not checked, never passed. And the check matches phrasings: a risky question worded in a way it has not seen can still pass, so "no rule matched" is not a clearance.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Store managers interviewing at volume across many sites. |
| Quick-service restaurants | Strong | Shift managers interviewing walk-ins between rushes. |
| Logistics and delivery (W2) | Strong | Site leads hiring for nights, lifting and safety. |
| Gig and courier marketplaces | Does not fit | There is no interview. |

US rules. Not legal advice.

## Verifying this yourself

```bash
python3 scripts/check_guide.py --test
```

276 questions, each declaring what the checker must find and what it must not. 157 are risky phrasings that must be caught, most of them from an adversarial pass ("What year were you born?", "Are you a single mom?", "How much are you on at the moment?", "H0w old are you?"). 119 are job questions that must not be flagged, and are the cases a naive checker gets wrong: "Tell me about a time a customer's kids were running around the store", "What would you do if a customer asked where the pregnancy tests are?", "Can you take Visa payments?". Every safe alternative the rules suggest is itself checked. The sample guide must pass clean, 37 broken copies of it must each fail, or warn, for exactly one named reason, and 14 malformed copies must be refused with the field named rather than crash. The twelve sample manager questions must come back exactly as planted.

Exit codes: 0 ready (or no legal risk in the list), 1 not ready (or a legal risk, or a question that could not be checked), 3 input refused, 4 the checker itself failed.

## Who it's for

- **Store, restaurant and site managers** who interview without training.
- **HR and talent leads** who want every site to interview the same way, and to stop the questions that end up in a complaint.
- **District managers** rolling one interview out across many locations.
