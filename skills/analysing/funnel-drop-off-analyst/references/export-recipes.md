# Getting the export out of your ATS

This is the step that stops most people, so it comes before anything else.

**Read this first.** Menu wording and report names change between ATS versions and
between tenants, and your admin may have renamed things. What is stable is *which
report type* you want and *which fields* it has to carry — that is what this file
gives you. If a label below does not match what you see, look for the report type
described, not the exact words.

If none of this matches your system, skip to **Any other ATS** at the bottom. It works
everywhere.

---

## What you are looking for, in any system

One row per application, with a timestamp for each stage it passed through. Not a
candidate list, not a summary by month — the row-level pipeline history.

Most ATSs call this a *pipeline*, *application*, *stage history* or *funnel* report.
If the export has one row per candidate rather than per application, that is usually
fine: what matters is that each row carries its own stage and dates.

**Take at least six months** if you can. Twelve is better — it lets seasonality be
separated from a real change. Below 500 rows the analysis refuses to run.

---

## Fields to include

Map your system's column names onto these. Rename them in the file, or just tell me
which is which and I will map them.

| You need | Commonly called |
|---|---|
| `application_id` | Application ID, Candidate ID, Requisition Application ID |
| `applied_at` | Applied Date, Application Date, Created At |
| `stage_reached` | Current Stage, Furthest Stage, Application Status |
| `location_id` | Location, Office, Site, Store Number |
| `region` | Region, District, Area, Division |
| `role` | Job Title, Requisition Title, Position |
| `source` | Source, Channel, Source Name, Origin |
| `hiring_manager_id` | Hiring Manager (as an ID, never a name) |
| `exit_reason` | Rejection Reason, Disposition, Status Reason |
| stage timestamps | Screened / Interview Scheduled / Interview Completed / Offer / Onboarding / Start dates |
| `first_shift_at` | Actual Start Date, First Shift, Day One |
| `scheduled_first_shift_at` | Scheduled Start Date, Planned Start |

## Fields to exclude — do this before you export, not after

Untick, drop or hash every one of these:

- Candidate Name, First Name, Last Name, Preferred Name
- Email, Personal Email, Phone, Mobile
- Address, Street, Postcode / ZIP — send a **distance band** instead (`0-5`, `6-10`,
  `11-20`, `21-40`, `40+`), computed on your side
- Date of Birth, National Insurance / Social Security number, right-to-work document
  numbers
- Any free-text field — Notes, Comments, Interview Feedback, Rejection Notes. These
  reliably contain both names and protected-characteristic information.

Hiring manager should be an ID, not a name. A manager is a person too.

The analysis stops and asks you to re-export if it sees a nominative column, so doing
this first saves you a round trip.

---

## Greenhouse

Look under **Reports** for the pipeline or application-history reports rather than the
summary dashboards — the summary views aggregate, and you need the rows.

- The report you want is the one listing applications with their stage and stage dates,
  often called *Pipeline History*, *Pipeline per Job*, or similar.
- Add Office and Department as columns — those map to `location_id` and `region`.
- Source and Rejection Reason are both available as columns; include them, they carry
  most of the mechanism classification.
- Export as CSV.

## Workday Recruiting

Workday installations differ more than most, so ask whoever owns your reports for:

> A custom report on the **Job Application** business object, one row per application,
> with the application event dates, Job Requisition, Location, Recruiting Source and
> Disposition Reason. No worker names or contact fields.

The standard delivered reports are usually summarised. A custom report is normally
needed, and is a small ask.

## iCIMS

Look for the candidate-workflow or application export rather than the candidate search
export — you need the workflow status and its date history, not the profile.

- Include Bin / Status and its date fields, which map to the stage timestamps.
- Include Source, Location and Job.

## SmartRecruiters

The candidate export per job carries status and timestamps. If you hire across many
requisitions, export per requisition and concatenate, or use the reporting module's
application-level export.

## Fountain

Applicant exports carry stage timestamps natively, one row per applicant per opening.
Include the funnel and stage columns, the location, the source and the labels.

If your Fountain workspace is connected through its MCP, you do not need this step at
all — the fields come across directly. See **Works with** in `SKILL.md`.

---

## Any other ATS

Anything that can produce a row-per-application CSV works. The minimum is three
columns:

```
application_id, applied_at, stage_reached
```

That alone gives you the funnel and where the volume goes. Every further column buys
a specific class of finding, and the report will tell you exactly which ones you did
not supply and what each cost you.

If you cannot get stage timestamps, you still get the funnel shape — you just lose the
distinction between a step that is broken and a step that is merely slow, which is
often the distinction that matters.

---

## If the export is genuinely impossible this week

Run the analysis on `data/frontline_pipeline_sample.csv` instead. It is entirely
synthetic — 18,184 applications across 42 locations, no real people — and it will show
you exactly what the output looks like and which columns are doing the work, so you
know what to ask your ATS admin for.
