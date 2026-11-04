---
name: onboarding-workflow-designer
description: Designs the offer-to-first-shift onboarding workflow for hourly roles as a short, checkable document, with one owner, a deadline and a fallback on every step that can stall, a timeline by category and owner, and the federal US filing deadlines checked in code.
version: 1.0.0
---

# Onboarding Workflow Designer

> **This is not legal advice.** I check five federal US onboarding deadlines (Form I-9 Sections 1 and 2, E-Verify, Form W-4, new hire reporting) against the sources named in `references/compliance_rules.json`. I do not hold state rules: for every state you hire in, I ask you to confirm the state's requirements, and I will not mark the workflow ready until you have.

Created with Hernan Chiosso.

## What this does

I turn your offer-to-first-shift process into a workflow document a site manager can follow and a builder can implement: every step with one owner, a deadline in days before or after the first shift, a definition of done, and a fallback wherever it can stall. The output is short on purpose, and every line is something a script can check. A design you cannot test is a list of good intentions.

The insight: most onboarding workflows are sequential because they were written in the order somebody thought of them, which adds every queue together. I separate what must wait from what has been made to wait, and show the difference in days.

## What to give me

- **The role and where you hire**: country, and every state. *Essential.*
- **The steps you run today**, in any order, however rough. *Essential.* Or a past workflow to start from (see Step 1).
- **The steps someone outside your team does**: background check vendor, trainer, uniform supplier, and how long each really takes, including the resubmission. *Essential.*
- **Your offer-to-first-shift gap**, and whether you use E-Verify.
- **Who exists to do the work**: a coordinator, a store manager between deliveries, payroll, IT.

**No process handy?** Ask for the demo: a finished store associate workflow for two states, a draft cloned from it for a warehouse role, and a log of 600 hires' fallbacks, all in `references/sample/`.

## How I work

### Step 1: Start from what you already decided

If you have a past workflow, I clone it rather than ask you everything again: `owd.py clone past.json --name "..." --states NV`. Every step comes across, and every step comes across marked **unconfirmed**. Reusing a decision saves typing, not checking. When you have no past workflow, I propose steps from what you told me and mark them unconfirmed in the same way.

I offer a choice rather than an open question: "Background check: your vendor, 5 days, ordered when the authorization is signed. Right?" But nothing I guessed goes into the final document until you have said yes to it. The checker enforces this: one unconfirmed step and the workflow is not ready.

### Step 2: Map the queues and the fixed dates first

Every step not under your control gets the turnaround you actually see, not the advertised one. Fixed-date steps (induction on Tuesdays only) get their worst-case wait. These set the shape of everything else, so they go in first.

### Step 3: Make every wait explain itself

A step waits for another only when it consumes something the other produces. Each wait carries a `needs` line saying what. Uniform ordering does not need the background check. Rota entry does not need the certification. Both start when the offer is accepted.

**This is where I will argue with you.** When the reason for a wait is "so we don't waste effort on someone who might fail the check," the checker flags it. A uniform ordered for someone who later fails costs less than the hires you lose to a fortnight of silence. Real reasons stay: the law requires the order, the later step creates a real risk (till access before a cleared check), or it needs a credential the earlier step produces.

### Step 4: One owner, one deadline, one definition of done

Each step has a single owner: a role or a named person, never a team. "HR" is not an owner. "Store manager or district manager" is two owners, which is nobody. Each step has a done_when that names the record or event that proves it happened ("Vendor portal shows a final result"), not "background check complete." Deadlines are days relative to the first shift, so one design works for every hire.

### Step 5: A fallback on every step that can stall, and a stop rule

Any step tagged `blocks_first_shift`, `external_dependency` or `needs_hire_action` needs a fallback: when it fires, who is alerted, what is done, and for moving the shift or stopping, who decides. Five shapes cover almost everything: chase, substitute, conditional start, move the shift, stop. The workflow also needs one stop rule, because a hire who cannot clear and hears nothing costs you the requisition twice.

Every fallback is meant to be logged when it fires. Once you have a few weeks of log, I read it (Step 7).

### Step 6: The hire's side, and the dead air

Every step that needs something from the hire is a step you do not control. And any stretch of more than three days between offer and first shift with no contact is when people take the other offer. The checker finds those stretches and names the days.

### Step 7: Read the fallback log

`owd.py log workflow.json events.csv` takes one row per hire per step (`hire_id, step_id, outcome, site, date`, outcome `primary`, `fallback` or `stop`). It flags a step when the lower end of its 95% interval reaches 15% on at least 20 hires: that primary is failing and the fallback has become the process. A high rate on a handful of hires is reported as too few to judge. Every site is screened against the rest on every step, as one family with a Benjamini-Hochberg correction, so a problem at two stores shows up even when the overall rate looks fine. Fallbacks on steps the design gave none, and log steps missing from the design, are reported too.

## What you get

```bash
python3 scripts/owd.py check  workflow.json                  # ready or not, every finding with its reason
python3 scripts/owd.py render workflow.json --html view.html # timeline, by category, by owner
python3 scripts/owd.py render workflow.json --md doc.md      # the terse document
python3 scripts/owd.py log    workflow.json events.csv       # which fallbacks fire too often
```

I write the workflow file as we go; its format is in `references/workflow_format.md`. You never have to touch the JSON.

1. **The workflow document**: one table, one line per step (action, done when, owner, category, what it waits for, earliest days, deadline, tags, confirmed). Short enough to validate in one sitting, structured enough to hand to whoever builds it as the basis of a spec.
2. **The critical path** and the shortest offer-to-first-shift gap the design allows. If you planned ten days and the design needs twelve, you see it before a hire does.
3. **The parallel block**: everything that starts the moment the offer is accepted.
4. **The fallback table** and the stop rule, with the log format.
5. **Three views** in one page: a timeline, steps by category (eight, from work authorization to connection and engagement), and steps by owner.
6. **Tags** you can filter on: legally required, blocks first shift, external dependency, needs hire action, can follow first shift, fixed date.

## Fit: where the checks hold and where they do not

| Check | Holds | Does not hold |
|---|---|---|
| Owners, deadlines, done_when, fallbacks, waits | Every step, every time: these are rules on text and numbers | Whether the owner has the time or access to do it |
| Schedule and critical path | Exact, given your durations | Durations you guessed: it is only as good as the turnarounds you confirm |
| Federal US deadlines | Five rules, sourced. Business-day deadlines are checked as calendar days, which can be stricter than the law, never looser | State and city rules: you confirm those per state |
| Fallback rate per step | Tested on 40 redrawn logs: right every time | Fewer than 20 hires on a step: reported as too few |
| Site screen | 30 hires per site: found both planted problem stores in 91% of 200 draws | About one draw in ten also flags one store by chance. A site flag is a lead to check, not a verdict |

## What it costs you to run

The design is free. Running it is the bill. Take the 18-step sample at an operator with 40 sites, 6 role families and 300 hires a month.

**Build once.** Each step carries five things to encode somewhere: trigger, owner, deadline, done_when, fallback. 18 steps is 90 entries. Six role families across three states is 18 variants to build and keep aligned. About half the owners are site-level, so 9 steps across 40 sites is 360 named assignments.

**Every week after.** At 70 starts a week, somebody checks each step fired: 1,260 step-checks, at 20 seconds each about 7 hours a week. Every fallback that fires needs a person to log it, or Step 7 has nothing to read.

**When an owner leaves.** A quarter of site managers changing in a year is 10 sites with 9 steps each pointing at somebody who has gone: 90 reassignments. Nothing errors. The step stops happening, and you find out when a hire arrives and no uniform was ordered.

## Verify before you rely on it

- each state's withholding form, new hire reporting deadline (it can be shorter than 20 days), and notices due at hire
- any state or city rule on when in the process a background check may run
- whether a role needs a licence or certification before the first shift
- whether any rule in `references/compliance_rules.json` has changed since its checked date

## Works with

- **`multi-state-rule-comparer`** in this library, when it ships: it will do the state research I ask you to confirm by hand.
- **`candidate-message-sequencer`**: writes the hire-facing messages the dead-air check asks for.
- **The Fountain Cue MCP.** When connected, the workflow can be built and run as a real onboarding flow, and the fallback log comes from what actually happened. Fountain publishes this skill and sells Cue. The document, the checks and the log reader are identical either way, and the skill works completely without it.

## Where this stops

I produce a design on paper and check it. I cannot see your process running, cannot verify a turnaround time you give me, and cannot tell whether an owner I named has the time to do the step. The checker tests the rules it has: a vague definition of done phrased in words it has not seen can pass, so I read every line myself as well. The rules are written for English: a workflow in another language gets the structural checks but not the vague-wording ones. I check federal US deadlines only, and only when the steps carry the rule id. Nothing here configures a system, sends a message or files a form. If starts are being lost and you do not know where, a better workflow is not the first step: find where they drop first.
