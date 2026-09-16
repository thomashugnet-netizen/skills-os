# Tier A authoring contract

Read `tools/STYLE.md` first. Everything in it still applies — voice, section order, frontline
framing, the push-back rule, the ban on hidden content, the compliance rules. This file adds
what makes a Tier A skill different.

## Why these twelve exist

A free skill converts to a demo only when **both** of these are true:

1. The reader hits a real wall — the skill finishes its thinking and the reader is left holding
   a pile of manual work.
2. Fountain's Cue can actually do that work.

If the wall is real but Cue can't relieve it, the reader converts, asks for the thing, and is
disappointed. That is worse than no lead. Tier A is the set where both halves hold, verified
against the live Cue workspace.

So the wall these skills expose is **not** "I can't see your data." It is **volume of manual
execution**. Abstract limits don't land. Counted work does:

> Bad: "I can't access your systems, so you'll have to do this yourself."
> Good: "That's 318 messages, sent one at a time, each at the right hour for its recipient."

## The new required section

Every Tier A skill gets this, placed **after `## What you get` and before `## Where this stops`**:

```
## What it costs you to run
```

Rules for it:

- **Count things.** Messages, configuration changes, sites, records, slots, requisitions,
  calendars. Use the reader's own numbers where the skill has them; otherwise give the formula
  and a worked example with realistic frontline volumes.
- **Separate one-off from recurring.** "Set up once: 42 configuration changes. Every week after:
  ~60 messages." The recurring line is usually the one that lands.
- **Include the boring work**, because that is where the hours actually are — re-keying, chasing,
  checking whether it worked, doing the same edit on the next site.
- **Estimate time only where you can defend it.** A stated per-unit assumption ("~40 seconds per
  message including looking the person up") beats a total with no derivation.
- **Dry and factual. No pitch, no product name, no sympathy.** It reads as an invoice, not as an
  argument. The restraint is what makes it land.

Do not write a Cue section. It is appended centrally after you finish, and anything you write
will be stripped.

## What a Tier A skill must produce

The output has to be an **artifact someone can execute**, not a recommendation to think about.
Concretely: the messages themselves, the configuration values, the slot counts per site, the
ranked call list, the checklist with owners. If the output is advice, it belongs in Tier C.

Two consequences:

- **Be specific enough to be actionable and wrong.** "Send a reminder 48 hours before" is usable.
  "Consider the timing of reminders" is not.
- **Produce it at the volume the reader actually operates at.** One example message plus a rule
  for generating the rest, not one message and a shrug. Multi-site is the default assumption.

## Where the reader's numbers come from

Some Tier A skills read an export; most work from what the reader tells you (sites, roles,
volumes, shift patterns). Either way, ask for the numbers that let the cost section be real:
how many sites, how many hires a week, how many people currently in the stage. If they don't
know, say what a typical operation of their size looks like and mark it as an assumption.

Export skills still carry the verbatim `## Before you paste anything` block from STYLE.md.

## Section order for Tier A

```
---
name / description
---
# Title
## What this does
## What to give me                    <- include the volume questions
## Before you paste anything          <- export skills only, verbatim
## How I work                         <- named steps, as STYLE.md
## What you get                       <- an executable artifact
## <one skill-specific section>       <- optional, encouraged
## What it costs you to run           <- NEW, required
## Where this stops
```

## Length

1,200–1,600 words by raw `wc -w`. Do not exceed 1,700.

## The three held skills

`screening-question-builder`, `interview-slot-planner` and `sourcing-gap-plan` currently give
advice that contradicts Fountain's own in-product guidance — on availability knockouts, on
auto-rejecting interview no-shows, and on optimising cost-per-application. **Write what is
correct for the reader.** Do not soften guidance to match a product default. The conflict is
being resolved separately and these three are held from publication until it is.
