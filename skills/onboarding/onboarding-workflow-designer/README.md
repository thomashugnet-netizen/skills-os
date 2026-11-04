# Onboarding Workflow Designer

> Designs the offer-to-first-shift onboarding workflow for hourly roles: one owner, a deadline and a definition of done on every step, a fallback wherever it can stall, and the federal US filing deadlines checked in code.

Created with Hernan Chiosso. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The workflow:** a short document a site manager can follow and a builder can implement. One line per step: the action, what proves it is done, one owner (never "HR", never two names), the deadline in days before or after the first shift, what it waits for and why, and whether a person confirmed it. Start from a past workflow or let it propose steps: everything stays unconfirmed until you say yes, and the workflow is not ready until then.

**The schedule:** the critical path and the shortest offer-to-first-shift gap the design allows, the steps that can all start the moment the offer is accepted, and three views of the same plan: a timeline, by category and by owner.

**The check:** `scripts/owd.py` blocks the workflow, with the reason, until every rule passes: an owner, a deadline and a testable definition of done on every step; a reason on every wait (waiting "so we don't waste effort" is flagged); a fallback on every step that can stall, and a stop rule; no more than three days without contact with the hire; the Form I-9, E-Verify, Form W-4 and new hire reporting deadlines, each with its official source; every state you hire in confirmed by you.

**The fallback log:** once it runs, log each fallback when it fires. It tells you which steps fall back so often that the fallback has become the process, and which sites fail a step that works everywhere else, without calling a handful of hires a trend.

## Why it exists

Most onboarding workflows run in the order somebody first wrote them down, so every queue adds to the next while the hire waits in silence and a second offer arrives. And a workflow nobody can test is a list of good intentions: "HR ensures the uniform is ordered" has no owner, no date and no way to tell that it did not happen.

On the demo, a fictional retailer's store associate workflow for California and Texas has 18 steps, ten of which start the moment the offer is accepted. It is ready to run, and its shortest offer-to-first-shift gap is 8 days against the 10 planned: the background check sets the pace (authorization, check, then till access). Cloned for a warehouse role in Nevada, the same design is not ready: 18 steps nobody has confirmed for the new role, and Nevada's own rules not yet checked. Its log of 600 hires shows what a design cannot fix by itself: the background check falls back for 23% of hires, so the fallback has become the process; uniform ordering works overall but fails for half the hires at one store and 40% at another; a welcome call falls back 6 times though the design gives it no fallback; and a drug test appears 9 times in the log though the workflow has no such step.

## Install

**1. Download** [onboarding-workflow-designer.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/onboarding-workflow-designer.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the onboarding workflow demo."* Then: *"Design the onboarding workflow for our cashiers in Ohio. Offer to first shift is 7 days, and our background check vendor takes 3 to 5 days."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/onboarding/onboarding-workflow-designer ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | What | |
|---|---|---|
| workflow | JSON in the shape of `references/sample/northline_store_associate.json`, described in `references/workflow_format.md` | written with you |
| fallback log | `hire_id, step_id, outcome` + `site, date` | optional, once it runs |

`outcome` is `primary`, `fallback` or `stop`. Opaque ids only: a log with a name, email, phone or SSN column is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Many sites, a background check and a uniform before the first shift, owners split between a coordinator and the store. |
| Quick-service restaurants | Strong | Short offer-to-start gaps make every wait and every silent day count. |
| Logistics and warehousing (W2) | Strong | Certifications, equipment and site access gate the first shift, and the critical path is where starts are lost. |
| Healthcare support (CNA, home care) | Partial | Licence checks fit as steps that block the first shift; state credentialing rules are yours to confirm. |
| Gig and 1099 delivery | Partial | The design and log checks hold. The checker assumes employees, so it expects Form I-9, W-4 and new hire reporting, which do not apply to contractors. |
| Outside the US | Partial | Every structural check holds; it holds no filing rules for any other country, and says so. |

## Verifying this yourself

```bash
python3 scripts/owd.py --test
```

136 checks. The sample workflow must pass with no findings at all, and 59 damaged copies of it must each be flagged for the right reason or refused as malformed: a team as owner, two owners joined by "or", a vague definition of done, a wait with no reason, a wait to save effort, a step that can stall with no fallback, no stop rule, four silent days, an I-9 Section 2 deadline too late, E-Verify before the I-9, a state nobody confirmed, a step that waits for itself. The sample log was generated with known answers by `references/sample/make_log.py`; the suite checks they come back on 40 redrawn logs, and that a file which is not UTF-8 is refused rather than misread.

Exit codes: 0 workflow ready or log read, 1 workflow not ready, 2 input refused.

Not legal advice. It checks five federal US deadlines against the sources named in `references/compliance_rules.json` and asks you to confirm every state's rules.

## Who it's for

- **Onboarding coordinators** who chase the paperwork between offer and first shift.
- **HR and people operations leads** standardizing onboarding across sites and states.
- **Whoever builds it**: the document is the basis of a spec for your HRIS or onboarding tool.
