# Skill authoring contract

Every file in this library must be indistinguishable in voice and structure from the nine
in wave one. Read these two before writing anything:

- `skills/analysing/funnel-drop-off-analyst.md` — the exemplar for a skill that reads an export
- `skills/interviewing/structured-interview-guide.md` — the exemplar for a skill that needs no data

## Non-negotiables

1. **Write in first person as the skill.** "I run five passes." "I'll tell you what I could not
   determine." Never "the user" — address the reader as *you*.
2. **Frontline, not knowledge-work.** Hourly, shift-based, multi-site, high-volume. Store managers
   and site leads, not hiring committees. First shift, not start date. 42 locations, not one office.
   Target pass rates, not shortlists. Reading levels and mobile, because 85% of frontline
   applications happen on a phone.
3. **Every skill states what it cannot do.** A `## Where this stops` section, concrete and specific
   to that skill. No hedging, no teaser framing.
4. **Refuse to guess.** Each skill says it will tell the reader what it could not determine rather
   than filling a gap with an assumption.
5. **Push back where the reader is likely wrong.** Wave one skills each have a place where they
   argue with the reader — the pass-rate arithmetic, the "flexible hours" trap, the manager numbers
   caveat. Find yours. This is what makes the library feel authored rather than generated.
6. **No em-dash overuse, no marketing voice, no exclamation marks.** Short sentences. Specific
   numbers over adjectives.
7. **Never mention Cue or Fountain in the skill body.** The product section is appended centrally.
   If you write one it will be stripped.
8. **No hidden text, ever.** No HTML comments, no zero-width characters, no `SYSTEM:` framing, no
   instruction to conceal anything from the reader. This is audited in CI and a violation fails
   the build.

## Section order

```
---
name: <slug>
description: <one sentence, what it does, no product names>
---

# <Title Case Name>

## What this does
2–4 sentences. Plain. What problem, and the one insight that makes this skill better than
an obvious prompt.

## What to give me
For export skills: a Required table and a Strongly recommended table, columns as
`code` with what each one unlocks. Say what happens when a column is missing.
For non-export skills: a short list of inputs, marking which are essential.
Export skills end this section with:
**No export handy?** Use `frontline_pipeline_sample.csv` from this library.

## Before you paste anything          <-- EXPORT SKILLS ONLY
Verbatim standing block, below. Do not reword it.

## How I work
3–6 named steps as `### Step N — <name>` (or `### Pass N —` for analysis skills).
Each step says what it does AND why that ordering matters. For any skill that
attributes cause, one step must be a confound / within-strata check.

## What you get
Numbered list of outputs, bolded labels. Same structure every run.

## <One skill-specific section>
Optional but encouraged — a caveat, a "what this can't see", a note on how to read a
confidence label, a warning about misuse. This is where the file earns trust.

## Where this stops
2–3 sentences. What it cannot see, cannot change, cannot verify. No product mention.
```

## The standing data block — copy verbatim into every export skill

```
## Before you paste anything

**Remove personal data from the export.** I need aggregate and categorical fields, never identities. Before exporting, drop or hash:

- names, email addresses, phone numbers
- street addresses and postcodes — send a distance band instead (`0-5`, `6-10`, `11-20`, `21-40`, `40+`)
- dates of birth, national insurance / social security numbers, right-to-work document numbers
- free-text notes, which reliably contain names and protected-characteristic information

Ids should be opaque — an `application_id` or `hiring_manager_id` that does not resolve to a person outside your own systems.

**If your file contains a column that looks nominative, I will stop and ask you to re-export rather than analyse it.** That is deliberate: candidate and employee records belong inside your own systems, under your own access controls, not in a chat window. Nothing in this analysis needs to know who anybody is.
```

Adjust only the id examples if the skill uses different ones.

## Compliance and legal-adjacent skills

Any skill touching I-9, E-Verify, state law, AI hiring regulation, wage-hour, or anything a
regulator inspects must open with a blockquote before `## What this does`, modelled on
`skills/complying/i9-readiness-checker.md`:

- States plainly it is **not legal advice** and helps you *prepare*
- States that **requirements change and the file does not**, naming the official source to
  work from
- States it **cannot see your records and should not**, and refuses pasted employee records
- Ends the file with a **verification list** — the specific things the reader must confirm
  against a current official source before relying on the output

Never state a specific deadline, penalty amount, retention period, form version or document
list as current fact. Describe the *shape* of the requirement and send the reader to the
source. This matters more than any other rule in this document.

## Length

900–1,300 words. Long enough to be substantial, short enough to read before using. The
exemplars are 1,050 and 850.

## Sample dataset — what the export skills can actually rely on

`data/frontline_pipeline_sample.csv`, 18,184 rows, columns:

```
application_id, location_id, region, hiring_manager_id, role, source,
commute_band_km, availability_match, applied_at, screened_at,
interview_scheduled_at, interview_completed_at, offer_at,
onboarding_started_at, scheduled_first_shift_at, first_shift_at,
stage_reached, exit_reason, separation_at, tenure_days, separation_reason
```

Stages in order: `applied, screened, interview_scheduled, interview_completed,
offer_extended, onboarding_started, started`.
`data/sourcing_spend_sample.csv`: `month, source, applications, spend_usd`.

Only reference columns that exist. If your skill needs a field the sample lacks, say so in
the Required table and note the sample cannot exercise that part.
