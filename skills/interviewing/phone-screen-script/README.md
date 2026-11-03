# Phone Screen Script

> Writes the five-minute call your team makes: availability first against the shifts you are short of, decided on the call, ended with a booked interview, and the voicemail, text and attempt rule for the calls nobody answers.

Created with Andrea Michelle Eighme. Maintained by [Fountain](https://www.fountain.com). Free to use, MIT licensed. Part of the [Claude Skills for HR Ops](../../../README.md) library.

## What it does

**The script:** word for word, in a fixed running order: a two-sentence opener; availability asked block by block against your real rota gaps; start date; "how would you get here for the earliest shift"; only genuine prerequisites; thirty seconds of honest preview with the pay, then "do you still want it"; their questions; the decision on the call, with the polite no and the redirect written out; two specific slots and a confirmation text before hanging up.

**The path most calls take:** a voicemail under twenty seconds with a way back, a text after every voicemail with an opt-out, attempts spread across the day, a stop rule, a callback script, five fields to write down.

**The check:** `scripts/screen.py` blocks the script, with the reason, until every rule passes: no assessment questions, nothing on age, citizenship, family, health, religion, arrests or pay history, no gate outside availability, prerequisites and the preview, under five minutes read aloud. Then a one-page call sheet.

**The call log:** once you dial, how fast the first call goes out and what that is worth, when people answer, whether a text after voicemail brings them back, which callers end calls open, whether far-off interviews cost shows, and who is stuck in limbo.

## Why it exists

Frontline applicants apply to several employers in one sitting and take the job that books them first. A screen that opens with "tell me about yourself", checks availability with "is that still right?" and ends with "we'll be in touch" loses them to whoever called faster and booked on the call.

On the demo, an overnight stocker screen at a fictional retailer reads in about 140 seconds and passes. Its two months of calls show what the script cannot fix on its own: candidates called within 4 hours book 28% of the time, after a day 16%; most attempts go out in the afternoon, when 16% answer, against 41% in the evening; 59% come back after a voicemail when a text follows, 39% when it does not, and only 41% of voicemails get one; one caller lets 31% of the people they advance leave without a slot; 46 candidates have been left in limbo.

## Install

**1. Download** [phone-screen-script.zip](https://github.com/thomashugnet-netizen/skills-os/releases/latest/download/phone-screen-script.zip). Do not unzip it.

**2. Check** that **Code execution and file creation** is on in the Claude app settings. Skills need it.

**3. Upload**: Settings, Customize, Skills, **+**, then choose the zip. Team and Enterprise owners can provision it to everyone from Organization settings, Skills.

**4. Try it**: *"Run the phone screen demo."* Then: *"Write our phone screen for weekend cashiers at the Columbus store. We're short Saturday and Sunday 7am to 3pm."*

**In Claude Code, Cursor, Codex and other agents:**

```bash
git clone https://github.com/thomashugnet-netizen/skills-os.git
cp -r skills-os/skills/interviewing/phone-screen-script ~/.claude/skills/
```

**Prerequisites:** Python 3. No packages to install.

## The files

| File | What | |
|---|---|---|
| script | JSON in the shape of `references/sample/northline_script.json` | written with you |
| call log | `candidate_id, caller_id, applied_at, attempt_at, outcome` + `result, booked, interview_at, showed, texted` | optional |

`outcome` is `answered`, `voicemail`, `no_answer`, `wrong_number` or `texted_back`. Opaque ids only: a log with an email address, a phone number or a name column is refused.

## Where it fits

| Business | Fit | Why |
|---|---|---|
| Retail and grocery | Strong | Shift-based roles, many sites, coordinators screening by phone at volume. |
| Quick-service restaurants | Strong | Fast decisions matter most; partial availability routes to the next store. |
| Logistics and warehousing (W2) | Strong | Nights and early starts make availability and the journey the deciding facts. |
| Healthcare support (CNA, home care) | Partial | Licence checks fit the prerequisite gate; clinical judgement belongs in the interview. |
| Salaried or professional hiring | Does not fit | The screen there is a conversation about experience, which this deliberately leaves out. |

## Verifying this yourself

```bash
python3 scripts/screen.py --test
```

87 checks. The sample script must pass, and 59 damaged copies of it must each be blocked for the right reason or refused as malformed: availability asked after travel, "is your availability still correct?", "can you get here?", "tell me about a time", a childcare question, one slot instead of two, a confirmation with no address, no pay, a voicemail with no way back, every attempt in the afternoon, and so on. The sample call log was generated with known answers by `references/sample/generate_calls.py`; the suite checks each comes back, and that the same log with outcomes and bookings shuffled is never read as speed or texting mattering. Before release, 2,400 damaged scripts and call logs ran without a crash.

Exit codes: 0 script ready or log read, 1 script not ready, 3 input refused, 4 the engine itself failed.

## Who it's for

- **Recruiting coordinators** who make the calls.
- **Talent acquisition leads** standardizing the screen across sites and callers.
- **Recruiting operations** working out why booked interviews lag applications.
