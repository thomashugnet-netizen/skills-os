# Rehire Campaign Planner

> Turns your own past applicants and former workers into a re-engagement campaign: who you may contact, in which segment, in which wave, with which three messages.

Created with Kristi Kennebrew. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

Reads a pipeline export and a short policy, and sorts every record into a segment or a named reason it is out:

- **in**: reached interview or beyond and never started; screened and then dropped, including the ones dropped by you (no slot, no follow-up); former workers who left in good standing; people rejected against a requirement of a different job, offered the job they now fit
- **out for good**: background, drug-screen, medical, document and right-to-work outcomes; involuntary and attendance exits; opt-outs
- **out for now**: past your retention period (a deletion job, counted as one), still working for you, never past the form, no opening near them, a contact purpose nobody has decided, a reason code nobody can read

Then: segments by recency, send windows by the shift each person would work, waves sized to the replies someone can answer, a contact list of ids only, and a check of the three messages (opt-out, sender, reason, news, "last message", no re-apply, no unfilled merge field).

## Why it exists

Someone who reached your interview stage five months ago is the cheapest hire you will make this quarter, and most employers never write to them. The ones who do message everyone, burn the goodwill of their whole history in an afternoon, and land the replies in an inbox nobody watches.

On the demo, 18,184 records at 42 stores become 1,535 people worth contacting near 12 open sites. 404 of them dropped because nobody offered them an interview slot or followed up. 4,429 records are past the retention period: a deletion job, not a segment. 3,821 are blocked because nobody has decided whether the privacy notice covers writing to people about a different job.

## Install

**1. Download** [rehire-campaign-planner.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/rehire-campaign-planner.zip). Do not unzip it. The frontline sample is inside.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the rehire campaign demo."* Then: *"Here's our applicant export from the last year. We're hiring stockers at three stores. Who can we re-engage?"*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/sourcing/rehire-campaign-planner ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Large applicant histories, seasonal peaks, people who left for school and come back. |
| Quick-service restaurants | Strong | Very high volume and short funnels: many drop-offs were only a slot away from starting. |
| Logistics and delivery (W2) | Strong | Drug-screen and medical outcomes are kept out; availability knockouts often fit another shift. |
| Gig and courier marketplaces | Strong | Sign-ups stuck in a background-check queue or without an onboarding slot are the warmest pool there is. |

Not legal advice: the consent questions go to whoever owns data protection, and the plan follows their answers.

## Verifying this yourself

```bash
python3 scripts/rehire.py --test
```

110 checks. On each of the four synthetic datasets: every row lands in exactly one place; nobody is contacted twice; no background, drug, medical or document outcome, no involuntary or attendance leaver, nobody still working and nobody who only abandoned the form is ever contacted; nobody past retention; everyone has an opening near them; someone rejected against a requirement is only offered a different role; waves never carry more replies than the capacity; consent decisions only ever remove people, never add them. On the demo, the counts, the deletion job, the night sites and the 404 people dropped by the employer come back as recorded. Suppression lists, an `opted_out` column, a `rehire_eligible` flag, one message per person and free-text reasons are each tested. Eleven broken message sets must each fail for the named reason. Before release, 300 damaged exports and policies and 1,500 damaged message sets ran without a crash.

Exit codes: 0 plan written or messages ready, 1 messages not ready, 3 input refused, 4 the engine itself failed.

## Who it's for

- **Recruiting and talent operations leads** who need starts this month without more job-board spend.
- **Site and area managers** short-staffed at a handful of locations.
- **HR and data protection partners** who want the consent questions asked before the send, not after.
