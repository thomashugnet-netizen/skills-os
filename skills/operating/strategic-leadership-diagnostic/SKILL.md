---
name: strategic-leadership-diagnostic
description: Diagnoses how an HR leader is approaching a real workforce challenge through the five values from Joey V. Price's The Power of HR, names the strengths and gaps their own account supports, and leaves them with one priority move, an executive discussion brief and an action plan. Every finding is checked in code against what they actually said. Use before an executive meeting, when an initiative stalls, or to turn workforce findings into a recommendation for the C-suite.
version: 1.0.0
---

# Strategic Leadership Diagnostic

Created with Joey V. Price. Built on the five values from his book *The Power of HR*.

## What this does

Takes one real situation, a workforce challenge, a proposed initiative or an executive conversation coming up, and examines how the person is leading through it, value by value. Then it turns what it finds into the thing they need next: a point of view they can defend in the room, and a plan.

Two parts:

1. **The diagnostic**, which I run as a short conversation and write up.
2. **The check**: `scripts/diagnose.py` reads the write-up against the person's own words and refuses it if a finding cannot be traced back to something they said, a value is skipped, a gap is read from silence, or the plan has no owner, no measure or no date.

The five values are the frame for every diagnostic, under their exact names. This skill applies them to a situation; it does not summarise the book and quotes nothing from it.

## What to give me

- **Your role**: your responsibilities, your decision authority, and how you relate to the people involved. *Essential.*
- **The business challenge**: what is happening, who is affected, and why it matters now. *Essential.*
- **Your current approach**: what you believe, what you have done, and what you are considering next. *Essential.*
- **The decision ahead**: what needs deciding, by whom, and by when.
- **Evidence and constraints**: metrics, examples, stakeholder feedback, resources, known limits. Output from an analysis skill counts: a funnel, turnover or source report is evidence.

Use roles, not names ("the COO", "two store managers"). Supporting material, such as a draft executive update, meeting notes or feedback received, can be pasted in.

**Not enough to go on?** Say so and I will help you work out what to gather and which conversations to have first. **Want to see it first?** Ask for the demo: a fictional grocer whose COO wants more applicants for stores that keep losing new hires.

## How I work

### Establish the business context

I restate the situation, the stakes, your role and the decision ahead, and list who is involved and whether their view is in your account in their own words or reactions. If your opening covers the essentials I do not interrogate you: at most three questions a round, two rounds before the first diagnostic.

I save your account to `situation.md` **word for word**: your first message, each answer under the question I asked, pasted material under its own heading. I never paraphrase it and never add to it, because the check traces every finding back to that file.

### Examine the five values

Each value is a separate lens. Where your account is silent on one that matters here, I ask for an example of what you did, how others responded, and what happened.

| The value | What it examines | What I look for |
|---|---|---|
| **Own Your Expertise** | Whether you have a clear HR point of view grounded in evidence, professional judgment, and an understanding of the business. | A position you state and can support; the business numbers, not only HR's; a view held as a hypothesis until the evidence settles it. |
| **Be Part Coach, Part Cheerleader** | Whether you address difficult truths while giving people the support, encouragement, and accountability to improve. | Candor and support in the same conversation; the people a finding is about hearing it from you first; what HR will do to help, said out loud. |
| **Ignite the Spark** | Whether your approach builds trust, inspires confidence, and helps others see the possibility in a proposed change. | Proof that the change can work (a pilot, a comparable site); the people who will carry it told what is happening and why. |
| **Bring Clarity From the Clouds** | Whether you turn uncertainty into an understandable problem, a clear decision, and actionable direction. | One agreed problem statement; the decision named before resources are asked for; who owns what next. |
| **Forward and Adaptive Beats Static and Slow** | Whether you take timely, thoughtful action and establish a way to learn and adjust as conditions change. | A proportionate next step instead of waiting for certainty; a test with a review date; what worked before, used. |

Each value gets one of three readings: **strength**, **development opportunity**, or **not enough evidence yet**. The third is not a gap. If your account says nothing about how you have handled the people side, I do not conclude you handled it badly; I say what to ask.

### Test the evidence

I separate what you said into **facts**, **observed results** (what happened, how people responded), **interpretations** (your read of it) and **intentions** (what you plan). A strength never rests on intentions alone. I name what is still uncertain, who could answer it, and what answer would change the recommendation. Conclusions that go further than the evidence get challenged, and so does the evidence that could support a different view.

### Identify the priority leadership move

One move: the part of your approach that most needs attention, why this one and not the others, and whether it is within your authority or needs a commitment from someone named. If the evidence is too thin to choose, the move is to settle the open question first.

### Prepare to act and learn

I write the executive discussion brief and the action plan, then check everything:

```bash
python3 scripts/diagnose.py --check diagnostic.json --situation situation.md --md report.md --html report.html
```

`diagnostic.json` follows `references/sample/halden_diagnostic.json`. I fix every blocking item and run it again; you see the report only once it passes. When you come back with results, I save what happened to a new situation file, review each earlier measure against it, and adjust:

```bash
python3 scripts/diagnose.py --check followup.json --situation followup.md --previous diagnostic.json --md report.md
```

## How I say it

Strengths first, and specific. Every finding is about the approach in this situation, never about you as a leader: "your framing could make Operations feel blamed", not "you are not strategic". The check refuses verdicts on the person, either way.

## What you get

1. **A strategic leadership profile**: strengths and development opportunities across the five values, each with the behavior it rests on, the words it rests on, and a next step.
2. **An evidence and assumptions review**: what supports your position, what remains uncertain, and what could change the recommendation.
3. **A priority leadership move.**
4. **An executive discussion brief**: the business issue, your point of view and its evidence, what it means for the business and for people, the trade-offs, the decision needed, who decides by when, and an ask you can say in thirty seconds.
5. **A focused action plan**: each action with one named owner, something you will see or count, and a review date within 120 days.

## The check, in full

Blocking: a value missing or renamed; evidence not found word for word in `situation.md`, or under four words; an opinion filed as a fact, or an intention as a result; a strength or opportunity with no evidence, behavior or next step; a strength resting only on intentions; "not enough evidence" with no question; a verdict on the person; an unheard stakeholder nobody plans to ask; nothing named that could change the recommendation; something you said that this skill pushes back on, left unanswered; a priority move on a value with no opportunity; a brief with no trade-off, no business or people impact, no decider or deadline, a point of view resting only on opinion, certainty wording with nothing factual under it, or an ask over 80 words; an action owned by "HR" or "we", measured by "better alignment", or with no review date. On a return visit: an earlier measure with no result, a result with nothing observed behind it, and approval counted as success.

## What I will push back on

- **"I already know what the problem is."** What supports that, and what could challenge it?
- **"Leadership just doesn't understand HR."** How clearly has the recommendation been connected to the business, and to what they are weighing?
- **"Being supportive means avoiding the difficult conversation."** I look for candor and encouragement together.
- **"We need complete certainty before acting."** A proportionate next step, and a way to learn from it.
- **"We got approval, so the initiative succeeded."** Executive agreement is not implementation, and implementation is not results.

When your account says one of these, the check makes sure the diagnostic answers it.

## Works with

- **Analysis skills from this library**: `funnel-drop-off-analyst`, `turnover-analyst`, `time-to-hire-analyst`, `source-roi-analyst` and `recruiter-capacity-planner` produce findings that make strong evidence. Paste their summary into the situation.
- ***The Power of HR***, by Joey V. Price, where the five values come from. The diagnostic applies the framework to a situation you are responsible for leading.

## Where this stops

This examines the leadership approach described in one situation. Its findings depend on the account and evidence you give; a single account cannot establish anyone's overall effectiveness as a leader, and the report says so. It cannot hear the people you have not asked, so it names them instead. It supports your judgment: organisational decisions and stakeholder conversations stay in your hands. It is not a performance review, a 360 or a coaching relationship, and it is not advice on an employment decision about any individual.

The check proves that each finding is traceable to your words and that the plan is complete. It cannot prove a finding is wise: that is what Joey's frame and your judgment are for. Its phrase checks (verdicts on the person, things to push back on, vague measures) read English and can miss a phrasing they have not seen; treat them as a second pair of eyes.
