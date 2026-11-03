---
name: bias-language-checker
description: Checks every text a candidate reads (job ads, application questions, text and email templates, offer letters, interview scripts, careers pages) for wording that excludes people you would hire or asks what you may not ask, and reads a whole template library at once to rank the fixes by how many candidates each line reaches.
version: 1.0.0
---

# Bias Language Checker

Created with Kristi Kennebrew.

> **This is not legal advice.** It flags wording that commonly excludes people or creates legal risk, explains why, and suggests what to say instead. What you may ask differs by state and city and changes over time; the rules file in this skill does not. Each rule in `references/rules.json` names an official source where there is one. Confirm your own rules before relying on the check.
>
> **I flag, I do not clear.** A rewritten line is a lower-risk line, not a safe one, and no match is not an approval.

## What this does

Reads the words a candidate sees, everywhere they see them, and returns the specific lines that narrow who applies or ask about something you may not ask about: why each one matters, and what to say instead.

Most reviews look at the job ad. In hourly hiring the ad is one text among many: the application form, the screening questions, the text message inviting someone to interview, the decline email, the phone-screen script, the offer letter, the careers page. And one line gets copied into two hundred requisitions across forty sites, so the cost of a bad line multiplies.

So this works on a **whole library at once**. Give it every template with how many candidates each one reaches, and it groups the same line across templates and ranks the fixes: severity first, then reach. "Must have own car", copied into four ads reaching 126 candidates a month, is one fix to the master template, not four.

## What to give me

- **The texts, as published.** One text, or a library: a CSV with `id,type,text,uses`, or a folder of `.txt` and `.md` files. *Essential.*
- **The type of each**: `ad`, `question` (application or screening), `message` (text or email), `offer`, `guide` (interview or phone script), `page` (careers site). Some rules only make sense for some types.
- **How many candidates each reaches** (`uses`): requisitions, sends or applications a month. It decides what to fix first.
- **Which requirements are genuinely non-negotiable, and why**: legal, safety, operational. That decides whether a flag becomes a rewrite or a challenge.
- **No candidate data.** Never paste applications, answers or notes. A library with a column that looks like a candidate is refused.

**Nothing handy?** Ask for the demo: thirteen templates from a fictional retailer, Northline, with problems planted in them.

## How I work

`scripts/bias_check.py` applies the rules in `references/rules.json` sentence by sentence; I read its output back to you and write the rewrites.

### Pass 1: Questions that ask what you may not ask

Age, birth year and graduation year; citizenship and origin ("where are you from originally?"); health, disability, medication and workers' comp; children, childcare, pregnancy and marriage; religion; height and weight; arrests; pay history; criminal history before an offer. These are the high-severity findings. Direct questions usually get caught; the indirect ones do not, because each has an operational reason behind it. A question about someone else ("a customer's kids") is not flagged; one about the candidate is.

### Pass 2: Wording that tells people the job is not for them

Gendered titles (salesman, waitress, foreman) with a direct replacement; "he will" written about the hire; age-coded phrases ("young and energetic team", "recent graduates", "digital natives", experience caps); origin-coded language requirements ("native English speaker", "no accent"); hype and masculine-coded words ("rockstar", "aggressive"); "culture fit" as a reason.

### Pass 3: Requirements standing in for something else

| What the text says | What you probably mean |
|---|---|
| Must have own car | Can get here for a 5am start |
| Valid driver's license (no driving in the job) | A photo ID, or nothing |
| Must be flexible / open availability | A specific rotating pattern |
| Any restrictions on your availability? Explain | Which blocks can you work? |
| Professional appearance / clean-shaven | A written uniform, hygiene or PPE standard |
| No gaps in employment | Recent experience of the work, if you need it at all |
| Immediate start only | Start within two weeks |
| 2+ years of experience | We train in four days |

A car or a licence is not flagged when the job is driving.

### Pass 4: What the ad leaves out

An ad for a physical job (stocker, warehouse, cook, delivery) that states no physical demand is flagged. That is not more inclusive: it removes the applicant's chance to judge for themselves, buys first-week exits, and removes the opening for an accommodation conversation. State demands as tasks and frequencies, not as "physically fit".

### What it will not flag

Equal-opportunity statements, which list protected characteristics on purpose. A legal minimum age ("18 or older"). "Authorized to work in the United States". Competitive pay. A background check after a conditional offer. A photo ID for Form I-9. Text in another language is reported as **not checked**, never passed.

## What you get

1. **Fix first**: every flagged line, grouped across the templates it was copied into, ordered by severity then reach.
2. **Why, and what instead**, for each, with the official source where there is one.
3. **Rewrites** beside the original, keeping the requirement you actually have. Where the requirement itself is the problem, I say so rather than softening the words.
4. **Requirement challenges**: the lines worth asking whether you need at all.
5. **Not checked**: texts in another language, named.
6. **A report** to share:

```bash
python3 scripts/bias_check.py --library templates.csv --html wording.html
python3 scripts/bias_check.py --text ad.txt --type ad
```

## What I will push back on

- **"It passed the check, so we're fine."** It did not pass. No rule matched. Whether your screening excludes people shows up in outcomes by group, which this cannot see.
- **Leaving physical demands out to look more inclusive.** It is the opposite.
- **Rewording a risky question into "tell me about a time...".** A personal question asked open-ended is the same question. Replace it with the job requirement behind it, or drop it.
- **Fixing the copy and not the master.** If a line is in forty requisitions, it came from somewhere. Fix that.

## Verify before you rely on it

- the protected characteristics in every state and city you post in
- whether your state or city bars criminal-history or pay-history questions, and when
- the rules on pre-offer health and disability questions
- pay-disclosure rules for job ads where you post
- any rule on automated or scored screening, where your logic decides without a person
- whether any rule in `references/rules.json` has changed since its checked date

Where a physical demand or appearance standard is genuinely required, confirm the accommodation and exemption process with whoever owns safety.

## Works with

- **`job-ad-writer`** writes ads that avoid most of this to begin with; this checks everything else a candidate reads, and the ads already live.
- **`structured-interview-guide`** checks interview questions in depth, with its own question rules.
- **The Fountain Cue MCP.** When connected, it can pull every live message template and job post from your account, so the library check runs on what candidates actually receive. Fountain publishes this skill and sells Cue. The rules and findings are identical either way, and the skill works completely without it.

## Where this stops

This reads text and nothing else. It cannot see who applied, who passed, who was hired, or how those rates differ across groups, which is where adverse impact actually lives. It matches phrasings in English: a risky line worded in a way it has not seen can pass, and text in another language is not read. It cannot see the version a job board actually rendered, or stop someone copying an old template next month.
