# Bias Language Checker

> Checks every text a candidate reads, not just the job ad, for wording that excludes people you would hire or asks what you may not ask, and ranks the fixes by how many candidates each line reaches.

Created with Kristi Kennebrew. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Reads job ads, application and screening questions, text and email templates, offer letters, interview scripts and careers pages, one text or a whole library at once. For every flagged line: the class (a protected characteristic, a proxy requirement, coded wording, or a requirement worth challenging), the severity, why it matters, what to say instead, and the official source where there is one. Gendered titles get a direct replacement.

In library mode, the same line copied into many templates is grouped, and the fixes are ranked by severity, then by how many candidates the line reaches. Fix the master once.

It also flags what is missing: an ad for a physical job that states no physical demand.

## Why it exists

Most wording reviews stop at the job ad. Candidates also read the application form, the interview invite, the decline email, the phone-screen script and the offer letter, and in hourly hiring each of those is a template copied across dozens of sites. On the sample library of thirteen templates from a fictional retailer, the application form alone carries four high-severity questions (graduation year, citizenship, arrests, current pay) and reaches 940 applicants a month; "Must have own car" sits in four ads, and correctly not in the fifth, which is a driving job.

## Install

**1. Download** [bias-language-checker.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/bias-language-checker.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the bias language demo."* Then: *"Check these application questions: ..."*, or attach your templates as a CSV.

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/screening/bias-language-checker ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The library file

| Column | Example | |
|---|---|---|
| `id` | `AD-STOCKER-NIGHT` | required |
| `text` | the template, as published | required |
| `type` | `ad`, `question`, `message`, `offer`, `guide`, `page` | recommended |
| `uses` | `38` | candidates, sends or requisitions it reaches |

Or a folder of `.txt` and `.md` files; a folder or file name starting with a type (`ads/`, `question_app.md`) sets it. A column that looks like candidate data is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Hundreds of requisitions from a handful of templates, across many sites. |
| Quick-service restaurants | Strong | Text-message hiring at volume; the invite and the screen are templates. |
| Logistics and delivery (W2) | Strong | Physical roles where demands must be stated, and driving roles where a licence is a real requirement. |
| Gig and courier marketplaces | Strong | Sign-up flows and in-app messages are the whole candidate experience. |

US rules, English text. Not legal advice.

## Verifying this yourself

```bash
python3 scripts/bias_check.py --test
```

84 phrasings that must be caught, each naming the rule that must catch it ("What year did you graduate high school?", "r u a citizen", "Is ur daycare ok with these hours?", "Must own a vehicle"), and 49 that must not ("A customer's kids were running in the aisle", "Northline is an equal opportunity employer and hires without regard to race, religion...", "Courier role. Must have own car; mileage reimbursement paid weekly", "Under 30 minutes from downtown by bus"). Text in Spanish and French must be reported as not checked, never passed. The sample library must come back exactly as planted, with the application form fixed first. Every "instead" the rules suggest, and every replacement title, must itself pass the check. Before release, 3,000 randomly damaged libraries and texts ran without a crash.

Exit codes: 0 no high-severity finding, 1 a high-severity finding or a text not checked, 3 input refused, 4 the checker itself failed.

## Who it's for

- **Talent acquisition and recruitment marketing** teams who own the templates.
- **HR and compliance partners** who want every candidate-facing text reviewed, not just the ads.
- **Operations leaders** rolling one hiring flow out across many sites.
