# Interview Panel Calibrator

> Gets several interviewers onto the same bar, and says whether each disagreement comes from the anchor wording or from a person.

Created with Taylar Martin. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The exercise:** from your interview questions and anchors, a twenty-minute pack of written answers, three per question at different levels, in the way candidates really talk, with one deliberate borderline, shuffled. A printable scoring sheet that never shows the intended level, and a key to keep back.

**The reading:** your interviewers score alone; you put the scores in a three-column file. For every answer, the report says whether the panel agrees, has one or two people outside, splits between two readings of the anchor, scatters on the middle level, or agrees with each other but not with what you meant. For every interviewer: aligned, lenient, severe, range-restricted (strong and weak answers get the same score) or inconsistent, measured against the others with that person left out, and with how much the number of answers can support.

**The live check:** with counts per interviewer (interviews, advanced, open roles at the site), pass rate against the pool with a 90% range, and whether pass rate follows vacancies.

All of it runs through `scripts/calibrate.py`, standard library only.

## Why it exists

Disagreement is diagnostic. When the panel splits evenly, the anchor has two readings and nobody needs coaching. When one person sits outside on most answers, the anchor is fine and the person needs a conversation. Most teams cannot tell the two apart, so they buy training, which fixes neither.

On the sample, seven interviewers at a fictional retailer score nine answers. The report finds one anchor with two readings, one answer the panel agrees on but reads differently from its author, a middle anchor that says nothing, one lenient interviewer and one who gives every answer a 2. And it shows that the site with the most open roles advances 80% of the people it interviews.

## Install

**1. Download** [interview-panel-calibrator.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/interview-panel-calibrator.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the panel calibration demo."* Then: *"Build a calibration exercise for these interview questions: ..."*, or *"Here are my panel's scores, what do they say?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/interviewing/interview-panel-calibrator ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | Columns | Needed |
|---|---|---|
| scores | `interviewer,item,score` | yes |
| key | `item,intended,borderline` | for the "not what you meant" check; written for you from the pack |
| live | `interviewer,site,interviews,advanced,open_roles` | optional |

Commas, semicolons or tabs; UTF-8 or UTF-16; any column order. Scores on 1 to 3 by default, `--scale 1-5` for a five-point scale. Files with emails, phone numbers or candidate columns are refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Many store managers interviewing for the same roles at different sites. |
| Quick-service restaurants | Strong | Shift and general managers interviewing walk-ins, with high manager turnover. |
| Logistics and delivery (W2) | Strong | Site leads interviewing for the same warehouse and driver roles across a network. |
| Gig and courier marketplaces | Does not fit | There is usually no interview to calibrate. |
| A single interviewer | Does not fit | Calibration needs at least three people scoring the same answers. |

## Verifying this yourself

```bash
python3 scripts/calibrate.py --test
```

The sample's problems were planted before the engine was written, and the suite checks they come back exactly: each interviewer's profile, each answer's pattern, the three guide findings, the live flags and the hiring-pressure verdict. Around it: a panel that agrees must produce no finding; a lenient, a severe and an all-2s scorer must each be told apart; a reversed scorer must never be called aligned; an even split must blame the anchor and a lone dissenter must not; a whole panel scoring above the key must be called a key problem, not five lenient people; 200 random panels of six answers must never produce a "consistent" verdict about anyone; borderline answers must be allowed to split between neighbouring levels and caught when they do not. Broken packs (in level order, no borderline, a one-line answer, a phone number, no ends covered) must each fail for the named reason, and malformed files must be refused, not crash.

Exit codes: 0 report written, 1 pack not ready, 3 input refused, 4 the engine itself failed.

## Who it's for

- **HR and talent leads** who want every site to score the same answer the same way.
- **District and area managers** who run the interviewers at several stores.
- **Recruiting operations** teams who combine scores from several interviewers and want to know whether they can.
