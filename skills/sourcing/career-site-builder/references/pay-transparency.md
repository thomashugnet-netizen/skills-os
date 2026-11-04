# Pay transparency

> **This is not legal advice.** It describes the shape of pay-transparency rules so a
> careers site can be built to meet them. Requirements differ by state, city and
> country, change often, and this file does not change with them. Confirm what applies
> to each location with the official source for that jurisdiction, or with counsel,
> before launch.

## The shape of the requirement

A growing number of US states and cities, and the EU through its pay transparency
directive, require employers above a certain size to publish pay information with job
postings or to provide it to applicants. The rules usually differ along the same lines:

- **Who is covered**: employer size thresholds, and whether remote jobs that could be
  filled from that jurisdiction count
- **What must be shown**: a good-faith pay range, sometimes a description of benefits
  and other compensation
- **Where**: in the posting itself, on request, or at a stage of the process
- **What counts as a posting**: internal postings, third-party job boards, and
  recruiter postings are treated differently from place to place

## How this skill handles it

- Every job page shows pay as a number or a range, taken from the jobs file
- A job without pay is flagged by `check_site.py`, and the page says pay is discussed
  at interview rather than hiding the question
- Pay figures on area pages that do not come from a live job are marked for confirmation

The site is the easy part. Whether the ranges are good-faith, whether benefits must be
described, and which locations are covered are decisions for the employer.

## Verify before you rely on this

1. Which of the employer's locations fall under a pay-transparency rule today, using
   each jurisdiction's official labour department source
2. Whether remote or multi-location postings bring additional jurisdictions into scope
3. Whether a range, a single figure, or a range plus benefits description is required
4. Whether the ranges in the jobs file are the ones the employer would defend as
   good-faith
5. Whether job boards that syndicate from this site carry the pay through
