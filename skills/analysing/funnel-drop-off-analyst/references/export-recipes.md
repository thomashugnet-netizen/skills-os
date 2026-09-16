# Getting the export out of your ATS

This is the step that stops most people, so it comes before anything else.

**How to read this file.** Anything marked **[documented]** comes from the vendor's own
documentation and carries a link. Anything marked **[inferred]** is a reasonable
conclusion that the vendor does not state — useful, but check it before you rely on it.
Menu wording changes between versions and tenants, so this file names *report types and
data objects*, which are stable, rather than click paths, which are not. Where a vendor
publishes exact task names, they are quoted.

---

## 1. The mistake that wastes the most time

Almost every ATS's delivered recruiting report gives you **the current stage and one
date** — when it last changed. A row reading `Interview` / `2026-04-02` cannot tell you
whether that candidate waited nine days to be screened or nine hours.

That distinction is the whole analysis. On the sample dataset, all three findings were
diagnosed by the **wait**, not the rate: a step converting badly with a long wait is a
capacity problem, the same step with a short wait is a rule problem. They need opposite
fixes.

What you need instead is **one date per stage, on the same row**. In every system
researched for this file, that data exists — but as a **status-history log**: one row per
status change, not one row per application. Getting from one to the other is a pivot, and
it is a real step. Plan for it.

**If the report comes back with a single `Status` + `Status Date` pair, it is the wrong
report.** You still get the funnel shape. You lose the distinction between a step that is
broken and a step that is merely slow.

---

## 2. What to ask for, in any system

**Grain: one row per application.** Not per candidate. In high-volume hourly hiring the
same person applies repeatedly, and a per-candidate export silently collapses those,
which inflates your top-of-funnel loss in a way nothing downstream will catch.

**Period: 12 months.** Six is the floor. Twelve is what lets seasonality be separated
from a real change — a peak quarter degrades cycle time, no-shows and conversion at
once, and produces several convincing false findings if you have nothing to compare it to.

**Volume: 500 usable rows minimum.** Below that the analysis refuses to run rather than
reporting noise as signal.

**Two exports, not one.** `separation_at`, `tenure_days` and `separation_reason` are
post-hire HRIS data. In every system researched here, recruiting and employment sit in
different report categories or different products, and a single report will not span
them **[documented for ADP, UKG Pro; inferred elsewhere]**. Pull the funnel first — it
works without them — and join the separation data later if you want the early-attrition
findings.

### Fields

Map your system's column names onto these. Rename them in the file, or just say which is
which.

| You need | Commonly called |
|---|---|
| `application_id` | Application ID, Job Application ID, Workflow ID |
| `applied_at` | Applied Date, Application Date, Created |
| `stage_reached` | Current Stage, Furthest Stage, Status |
| `location_id` | Location, Site, Store, Station, Office |
| `region` | Region, District, Area, Division, Supervisory Org |
| `role` | Job Title, Requisition Title, Position |
| `source` | Source, Channel, Recruiting Source, Origin |
| `hiring_manager_id` | Hiring Manager, **as an ID, never a name** |
| `exit_reason` | Disposition, Rejection Reason, Status Reason — **coded, not free text** |
| stage dates | one per stage, from status history — see section 1 |
| `scheduled_first_shift_at` | Scheduled Start Date, Planned Start |
| `first_shift_at` | Actual Start Date, First Shift |

`commute_band_km` and `availability_match` are **not native fields in any ATS researched
here** [inferred from documented field lists]. If you can derive them — a distance band
computed on your side, an availability question from the application form — they are
worth having. If not, omit them; the report will say what that cost.

### Fields to exclude — before you export, not after

Candidate Name, Preferred Name, Email, Phone, Address, Postcode/ZIP, Date of Birth,
SSN or national ID, right-to-work document numbers, and **every free-text field** —
Notes, Comments, Interview Feedback, Rejection Notes. Free text reliably contains both
names and protected-characteristic information.

Send a **distance band** (`0-5`, `6-10`, `11-20`, `21-40`, `40+`) rather than a postcode.
Hiring manager as an ID, not a name — a manager is a person too.

The analysis stops and asks you to re-export if it sees a nominative column, so doing
this first saves you a round trip.

---

## 3. Mapping your stages onto the canonical seven

The analysis runs on a fixed seven-stage funnel. Your pipeline almost certainly has more
steps, so several collapse into one. This is normal and costs you nothing.

| Canonical | Your likely stages |
|---|---|
| `applied` | Application submitted |
| `screened` | Application review, recruiter screen, knockout questions passed |
| `interview_scheduled` | Interview booked |
| `interview_completed` | Interview attended |
| `offer_extended` | Offer made |
| `onboarding_started` | Background check, drug screen, assessment, paperwork, road test |
| `started` | First shift worked |

**The compliance stages are the ones to think about.** Background checks, drug screens
and licence checks all sit between offer and day one, and in driver, healthcare and
security hiring that is where a large share of the loss lives. Collapsing them into
`onboarding_started` keeps the funnel readable and the loss still surfaces — as the
offer-to-first-shift gap, which was the single largest finding on the sample data. But
*why* people fell out then comes entirely from `exit_reason`, not the stage. So in those
industries the disposition picklist is doing more work than anywhere else, and free-text
reasons cost you that finding entirely.

**Stages repeat and run in parallel.** Workday states this explicitly for its Job
Application business process **[[documented](https://doc.workday.com/workday-education/en-us/course-manuals/recruiting-for-administrators/the-job-application-business-process.html)]**,
and configurable statuses make it true elsewhere. So when you pivot the history log,
decide: first time the stage was reached, or last? **Use first entry**, and say so — the
analysis measures how long people waited to get in, not how many rounds they had.

---

## 4. The request — forward this

> Could you build me a report?
>
> **Grain:** one row per application — not per candidate, not summarised by month
> **Period:** the last 12 months of applications
> **Format:** CSV if available, otherwise Excel
>
> **The important part:** I need the date each application *reached each stage*, not just
> its current stage and the date that last changed. That usually means sourcing from the
> application's status-history or event data rather than the current-status summary
> fields. If it comes out as one row per status change rather than one row per
> application, that is fine — I can pivot it, as long as each row carries the application
> ID, the status and the date.
>
> **Columns:** application ID, applied date, current/furthest stage, the stage-history
> rows or per-stage dates, requisition or job title, location, region or district,
> recruiting source, hiring manager **as an ID not a name**, disposition/rejection reason
> **as a coded value not free text**, scheduled start date, actual start date.
>
> **Please untick before exporting:** candidate name, email, phone, address, postcode,
> date of birth, SSN or national ID, right-to-work document numbers, and every free-text
> field (notes, comments, interview feedback, rejection notes). If distance to site is
> available, send it as a band rather than a postcode.
>
> No candidate personal data is needed for this — it is all counts, categories and dates.

If you do not know who owns this, it is usually whoever administers your ATS: an HRIS
analyst, a recruiting ops person, or in smaller operations the payroll administrator.

---

## 5. Per-system recipes

Grouped by how much the vendor actually publishes. That matters: where documentation is
thin, the honest instruction is "ask your account manager", and saying so saves you an
afternoon.

### ADP Workforce Now — the best-documented case

ADP ships a delivered standard report that does exactly this job. From the *Workforce
Now Standard Reports Guide*: **Application Status History** — *"lists application status
history for an applicant and addresses the requirement to track applicant workflow
history."* **[documented]**

- Found under **Reports & Analytics > Standard Reports**, Recruitment category
  (managers get a reduced set under **My Team Reports**). **[documented]**
- Other Recruitment reports worth pulling alongside it: **Applicant Summary** (source,
  requisition, location attributes) and **Time to Hire** (spans requisition → candidate →
  onboarding completion). **[documented]**
- **Output is PDF or Excel. CSV is not a documented option** — plan on Excel and convert.
  **[documented]**
- The report is almost certainly long format, one row per status change, needing a pivot.
  ADP publishes no column list. **[inferred]**
- Recruitment and **Personal & Employment** are separate report categories, so separation
  data is a second export. **[documented]**
- The available recruitment reports **differ by Workforce Now version** — a 2016 guide
  lists five, a 2021 guide lists seven. Check your own catalogue rather than this list.
  **[documented]**
- Skip the API for bulk history: the Job Applications V2 API exposes current
  `applicationStatusCode` but no status-history collection, caps pages at 100 records and
  times out at 8–10 seconds. **[documented]**

*If you are on **RUN Powered by ADP**, stop — its custom reports cover payroll and
employee data and have no recruitment category.* **[documented]**

### Workday Recruiting

- Build an **Advanced custom report** with the **`Create Custom Report`** task, on the
  **Job Application** business object. **[documented]**
- The stage set is the Job Application business process: Review, Screen, Interview,
  Assessment, Reference Check, Offer, Background Check, Ready for Hire. **[documented]**
- Stage timing is exposed through delivered reports — **Business Process Event History**,
  **Candidate Time Per Stage**, **Candidate Pipeline** — but as averages or as an event
  log, not as one date column per stage on one row. **[documented]**
- **No Workday documentation names a report field like "date reached Interview stage" on
  the Job Application object.** Getting the wide shape means calculated fields extracting
  each subprocess's completion from process history, or a report over event data. Your
  Workday analyst will know; do not assume it is a checkbox. **[inferred — and the most
  important caveat in this section]**
- Limits: browser reports time out at **30 minutes**, background and scheduled reports at
  **6 hours**; an advanced report renders 1,000 instances / 50,000 rows in the browser but
  Excel export goes to 1,048,576 rows. **Run a full-history extract as a scheduled
  background report, not interactively.** **[documented]**
- **"Optimized for Performance"** silently restricts the field picker to indexed fields —
  if a field you expect is missing, check that first. **[documented]**
- Permissions: creating needs the **Analytics Data: Report Fields and Values** security
  domain plus view access to the data source and every field's domain. **[documented]**
- **`Schedule a Report`** delivers Excel, PDF or CSV ("Text") on a recurrence.
  **[documented]**

### iCIMS

- The right grain is the **recruiting workflow** (person × job), at
  `/customers/{customerId}/applicantworkflows`. **[documented]**
- **Stage history is exposed as the `submittalstatuslog` field**, returning each update's
  `status`, `updatedDate` and `updatedBy`. This is the cleanest history object of any
  system here. **[documented]**
- **It is capped at the 100 most recent entries.** For a normal application that is
  plenty; test it on a high-activity requisition before trusting a bulk pull.
  **[documented]**
- The Search API returns **System IDs only**, 1,000 at a time, sorted by ID — so an
  extract is a two-call pattern: search for IDs, then fetch each workflow. iCIMS states
  the Search API is **not for real-time use**; it is for background syncing.
  **[documented]**
- Callers must belong to the **Integration User** group. **[documented]**
- iCIMS publishes a knowledge-base article titled *"Feature Highlight: Recruiting Workflow
  History Reports"*, which suggests the in-product report builder has a workflow-history
  family — but the article is login-gated, so its contents are unverified. **If you have
  an iCIMS login, look there first; it may save you the API route entirely.**

### SmartRecruiters

- Per application: **`GET /candidates/{id}/jobs/{jobId}/status/history`**. Use the
  job-scoped endpoint — the candidate-level one is **deprecated**, and it collapses
  multiple applications from the same person. **[documented]**
- Statuses are a fixed enum — LEAD, NEW, IN_REVIEW, INTERVIEW, OFFERED, HIRED, REJECTED,
  WITHDRAWN, TRANSFERRED — each with a configurable sub-status. **[documented]**
- **A gotcha worth knowing: status updates accept a `startsOn` date, so a status can be
  backdated.** The history timestamp is not necessarily when someone clicked. Reconcile
  before computing durations. **[documented that `startsOn` exists; the consequence is
  inferred]**
- The **Reporting API** exposes reports built in **Report Builder** and downloads them as
  CSV, asynchronously — wait for status `COMPLETED`. Requires the **`reporting_read`**
  scope. **[documented]**
- Whether Report Builder itself offers per-status timestamp columns is **not published**
  (the help centre blocks automated reading). The Reporting API exposes whatever Report
  Builder has, so if it is there, you can get it. **[inferred]**
- Limits: 10 requests/second, 8 concurrent; candidate listing pages at 100 max. A
  per-application history pull is one call per application — for 18,000 applications that
  is a job to run overnight, not in a coffee break. **[documented limits; arithmetic
  inferred]**

### UKG — check which product first

Customers say "UKG" meaning three different systems. **[documented]**

**UKG Pro** (formerly UltiPro). Reporting is **IBM Cognos**. Recruiting reports sit in two
packages depending on which generation you licensed: **RECRUITMENT** (legacy — includes
*Candidate History*, *Applicant Flow Log Detail*, *Applicant Activity by Status*) and
**TALENT ACQUISITION** (newer — *Opportunity Detail*, *Filled Opportunities with Hired
Candidates*). **[documented]** Their column lists are **not published**, so whether any
emits one row per status change with a date is unverified — but those three legacy report
names are the ones to open first. **[inferred]**

- **The trap: *"Service Accounts do not have access to Time Management or Recruitment
  report data. To access these reports, you must use a UKG Pro Web user account."*** An
  automated pull under a service account comes back empty. **[documented]**
- Reports-as-a-Service outputs comma-, pipe- or space-delimited text or XML, and warns of
  a **5-minute download timeout** — chunk by date range. **[documented]**
- Turnover lives in the **Administrator** package, and a Cognos report cannot span
  packages: recruiting and separation are two exports. **[documented that they are
  separate packages; the consequence inferred]**

**UKG Ready** (formerly Workforce Ready). Different stack: the **Report Hub** and
**Custom Report Builder**, where **Recruitment is one of the reporting categories**.
Saved reports live under *"My Info > My Reports > My Saved Reports"*. **[documented]**
Columns are undocumented — open the builder, pick the Recruitment category, and keyword-
search the column list for "status", "stage" and "date". **[inferred]**

**UKG Pro Workforce Management** (formerly Kronos Dimensions/Central) is time and
attendance and holds no recruiting data. **[inferred from its published report list]**

### Hireology

- Reporting is **Insights**, which is embedded Looker. Documented dashboards include
  **Funnel Report**, **Hiring Velocity**, **Hiring Steps**, **Sourcing Performance**.
  **[documented]**
- Everything published is **aggregate**. The metric *"Average Time in Each Hiring Step"*
  proves per-step timestamps exist in the underlying model, but Hireology documents no
  candidate-level export with a date column per stage, and no ad-hoc Looker Explore access
  for customers. **[documented metrics; the gap is the finding]**
- The only documented row-level route is downloading dashboard tiles: **a zipped
  collection of CSV files, one per query tile** — the tiles as built, not an arbitrary
  dataset. Text tiles are excluded. **[documented]**
- Requires the **"Can access insights and reporting"** permission, and **multi-location
  users only see their own locations** — an estate-wide pull needs an all-locations user,
  or your `location_id` coverage is silently truncated. **[documented]**
- **Realistic path: ask Hireology support for a candidate-level extract or a custom tile.**
  Hireology holds no separation data at all — it is an ATS plus onboarding, not an HRIS.
  **[inferred]**

### Workstream

- Self-serve reporting exists: an **Applicants** dataset and a **Hiring** dataset in the
  report builder, deliverable as CSV, Excel, PDF or PNG on a schedule. **[documented]**
- The public API's `GET /position_applications` returns, as dates, only
  **`application_date`, `hired_at` and `latest_interview_date`**. There is **no stage
  history and no status-change log**. `latest_interview_date` cannot separate
  interview-scheduled from interview-completed. **[documented — full response schema
  inspected]**
- API access must be enabled by Workstream support, is Super-Admin only, and **tokens
  expire after 7 days**. **[documented]**
- The separate **export template** feature triggers on *"applicant marked as hired"* or
  *"onboarding complete"* — so it captures people who finished the funnel, not everyone
  who entered it. Not what you want here. **[documented]**
- **Workstream never publishes the column inventory of its Applicants report.** That is
  the decisive unknown: open the report builder's column picker and look for stage-date
  fields yourself. If they are not there, the API will not rescue you. **[gap — worth
  asking support directly]**

### HigherMe

- Strong export UI: an **Exports** page with presets including **Applicants** ("every
  applicant who applied within a specified date range") and **Location and job
  statistics** ("all hiring activity... including applicant status updates regardless of
  original application date"). Fields can be renamed, reordered and added; exports are
  generated asynchronously and emailed. **[documented]**
- Stage vocabulary: New, Contacted, Interviewing/Interviewed, Hired, Future candidate,
  Rejected, Auto-rejected. **[documented]**
- **The field list is never published**, so whether date-of-status columns are selectable
  is unknowable from outside. The dashboard computes *"Avg. Time to Review"* and *"Avg.
  Time to Interview"*, which means the timestamps exist server-side. **[inferred]**
- **Open the field picker on the Applicants export and look.** That one check answers it.
  No public API exists. **[documented]**

### Harri

Harri publishes almost nothing usable here, and pretending otherwise would waste your
time.

- **There is no public help centre** — the support URLs return HTTP 410. The developer
  portal exists but every content page is member-gated. **[documented]**
- Its documented API surface, read from the complete sitemap, is **employees, clocks, pay
  sheets, scheduling and labour exports**. **Not one applicant, application, candidate or
  hiring-stage endpoint appears anywhere.** **[documented — a strong negative, since the
  sitemap is the full index]**
- The only evidence of hiring reporting is a **2018 product blog post** describing an
  enterprise report called **"Time in Workflow"** with columns *Shortlist Time, Recruiter
  Time, Hiring Manager Time*, emailed as CSV. Note what that gives: **durations per step,
  not dated stage transitions.** Eight years old and tier-gated. **[documented that the
  post says so; currency unverified]**
- **Go to your Harri account manager.** Ask for "Time in Workflow" and for an
  applicant-level extract with status history. Do not expect a self-serve path.
  **[inferred from documented absence]**

### Fountain

Applicant exports carry stage timestamps natively, one row per applicant per opening.
Include the funnel and stage columns, the location, the source and the labels. If your
workspace is connected through its MCP, you do not need this step at all — see
**Works with** in `SKILL.md`.

### Systems that do not hold your funnel

**Paradox, Sapia.ai** and similar conversational layers sit on top of an ATS. **Deputy**
and other scheduling tools hold shifts, not applications. Your funnel data lives in the
underlying ATS — go there. **[inferred from their published product scope]**

Phenom, Eightfold, Sense, Humanly, HireVue, Homebase and Landed were not researched for
this file. Use section 2 and section 4 and ask their support what their status-history
export looks like.

---

## 6. Any other ATS

Anything that produces a row-per-application CSV works. The minimum is three columns:

```
application_id, applied_at, stage_reached
```

That alone gives you the funnel and where the volume went. Every further column buys a
specific class of finding, and the report names exactly which ones you did not supply and
what each cost.

If you cannot get stage timestamps at all, you still get the funnel shape — you lose the
distinction between a step that is broken and a step that is merely slow, which is often
the distinction worth having.

## 7. Before you send it

- One row per application, not per candidate
- 500+ rows; 12 months rather than 6
- **More than one date column populated** — the check from section 1
- No column header containing name, email, phone, address, postcode, zip, dob, ssn,
  notes or comments — the engine refuses the file outright if it sees one, by design
- Hiring manager values look like `MGR-0142`, not `Sarah Chen`
- Disposition reasons are coded values, not free text

## 8. If the export is genuinely impossible this week

Run the analysis on `data/frontline_pipeline_sample.csv` instead. It is entirely
synthetic — 18,184 applications across 42 locations, no real people — and it shows you
exactly what the output looks like and which columns are doing the work, so you know what
to ask for.
