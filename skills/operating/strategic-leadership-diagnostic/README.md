# Strategic Leadership Diagnostic

> See where your leadership is creating impact and where your approach needs to change, through the five values from Joey V. Price's *The Power of HR*, and leave with a clearer point of view and a plan.

Created with Joey V. Price, author of *The Power of HR* and President & CEO of Jumpstart HR. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Examines how you are leading through a specific challenge, using the five values from *The Power of HR*: Own Your Expertise; Be Part Coach, Part Cheerleader; Ignite the Spark; Bring Clarity From the Clouds; and Forward and Adaptive Beats Static and Slow.

It asks focused questions about your business context, evidence, stakeholder relationships, proposed response and intended outcomes. It then identifies where your approach demonstrates strategic leadership, where it needs strengthening, and what information is still missing. Each finding connects a value to an observable leadership behavior and a practical next step.

You leave with five things: a strategic leadership profile, an evidence and assumptions review, one priority leadership move, an executive discussion brief, and a focused action plan with owners, measures and review dates.

**The check:** `scripts/diagnose.py` reads the diagnostic against your own words before you see it. Every piece of evidence must be found in what you said, word for word. All five values must be examined. A gap is never read from silence: where your account says nothing, the reading is "not enough evidence yet", with the questions to ask. Facts, results, interpretations and intentions are kept apart. Nothing judges you as a leader overall.

## Why it exists

HR leaders are often asked to solve a workforce problem before the organisation has agreed on what is causing it, who owns it, or what success would mean.

The way HR responds shapes its relationship with the business. A strong response brings expertise, builds trust across functions, clarifies the decision and helps people move forward. This diagnostic makes those leadership choices visible: it examines the approach behind your recommendation and strengthens the contribution you bring to the room.

In the demo, a director at a fictional grocer is asked for twice the applicants at six stores that lose 41% of new hires in 30 days, against 19% elsewhere, while applications are flat. The diagnostic finds the expertise is there (the numbers that separate volume from turnover), and that the case has reached the COO as a verdict on store managers nobody has asked. The priority move is to agree which problem the meeting is solving before $60,000 of advertising is decided.

## Install

**1. Download** [strategic-leadership-diagnostic.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/strategic-leadership-diagnostic.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Show me the leadership diagnostic demo."* Then bring your own: *"Our COO wants recruiting to increase applicant volume because several locations keep losing new hires. I believe we need to examine the employee experience, but I haven't built a convincing case or aligned with Operations. Use the five values from The Power of HR to diagnose my leadership approach, challenge my assumptions, and help me prepare a recommendation for our next leadership meeting."*

Other situations it is built for:

- **A workforce problem with competing explanations**: Recruiting and Operations disagree about why locations remain understaffed.
- **An HR investment that needs executive support**: you have proposed manager development but have not established the business case or shared ownership.
- **A change initiative that has lost momentum**: leadership approved a new process, but managers and employees are not adopting it.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/operating/strategic-leadership-diagnostic ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## Where it fits

| Leadership moment | How it helps |
|---|---|
| Before an executive meeting | Tests your point of view, your assumptions and your decision request. |
| When a workforce initiative stalls | Examines alignment, trust, clarity and ownership. |
| After receiving operational analysis | Turns findings into a leadership response. |
| During a leadership development conversation | Makes strengths and development needs specific to real work. |
| After an initiative or a difficult decision | Supports reflection on what worked, what changed and what to do differently. |

It works on any industry and any size of HR team: the evidence is whatever you bring. It is not built for a decision about one employee, such as a performance or disciplinary case.

## Verifying this yourself

A useful diagnostic lets you trace every finding back to something you provided. Read the report and check that it:

- explains the evidence behind each strength or development opportunity;
- identifies uncertainty and asks for missing perspectives;
- connects recommendations to both business needs and people's experience;
- suggests actions appropriate to your role and authority;
- defines what you will observe or measure when you revisit the situation.

The checker enforces each of those in code. To run its own tests:

```bash
python3 scripts/diagnose.py --test
```

The demo diagnostic and a four-weeks-later follow-up must pass clean. 66 altered copies must each fail for the one named reason (a value renamed or missing, a paraphrase passed off as a quote, a gap read from silence, a strength resting on a plan, "you are a weak leader", an unheard stakeholder nobody asks, a priority move on a strength, a brief with no trade-off, an action owned by "HR" or measured by "better alignment", approval counted as success on the return visit) or, for five, be refused for their shape; ten legitimate variations must still pass (a quote with an ellipsis or a curly apostrophe, a reported opinion inside quotation marks, a value with no evidence yet, an account too thin for any reading). 69 phrases test the detectors in both directions: "Leadership just doesn't understand HR" must be caught, "One district manager told me HR is blaming the stores" must not. 1,500 randomly broken diagnostics must be refused or checked, never crash.

Exit codes: 0 ready, 1 not ready, 3 input refused, 4 the checker itself failed.

## Who it's for

- **HR leaders and business partners** preparing to influence a consequential business decision.
- **Talent acquisition and people operations leaders** translating operational findings into recommendations.
- **HR teams** reflecting on how they lead change and partner with executives.
- **Emerging HR leaders** developing a stronger strategic point of view.
