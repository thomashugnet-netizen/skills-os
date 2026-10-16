# Being found: search engines and AI assistants

## The jobs file

`build_site.py` reads one CSV, one row per job. With `--examples` the rows are example roles shown on the landing page and labelled as examples; with `--jobs` they are real openings and each gets its own page. Required columns:

| Column | Used for |
|---|---|
| `job_id` | the job page URL and the JobPosting `identifier` |
| `title` | the page title and h1. The searched-for title, not the internal grade name |
| `category` | filters and career-area links (`store-teams`, `food-service`, `store-leadership`, `distribution`, `maintenance`, `corporate`, or your own) |
| `city`, `region`, `country` | the job location, and one location page per city |
| `pay_min`, `pay_max`, `pay_unit` | pay on the page and `baseSalary` in the markup. `pay_unit` is HOUR, DAY, WEEK, MONTH or YEAR |
| `employment_type` | FULL_TIME, PART_TIME, TEMPORARY, SEASONAL, CONTRACTOR, INTERN, PER_DIEM |
| `schedule` | one plain sentence about hours |
| `date_posted` | `YYYY-MM-DD` |
| `apply_url` | where Apply goes |
| `summary` | one or two sentences about the job |

Optional: `postal_code`, `street_address`, `currency`, `valid_through`, `duties` and
`requirements` (each a list separated by `|`).

Most applicant tracking systems can export open jobs with these fields, or publish
them as an XML feed. A spreadsheet typed by hand works too.

## Search engines

- **One page per job, with JobPosting structured data.** This is what makes a job
  eligible for the job listings shown directly in search results. Required: `title`,
  `description`, `datePosted`, `hiringOrganization`, `jobLocation` with an address.
  Recommended and filled when the data exists: `baseSalary`, `employmentType`,
  `validThrough`, `identifier`.
- **Markup only where one job lives.** JobPosting goes on the job's own page and never
  on a search, location or list page; `check_site.py` enforces it.
- **The title is the job title only.** No pay, place, job code or company name in the
  markup's `title`; the search engine treats anything else as keyword stuffing.
- **Markup matches the page.** Pay in the markup must be visible on the page. A
  mismatch is a policy violation, not a style issue.
- **Take filled jobs down.** Leave a past `validThrough`, return a 404 or 410, or remove
  the markup. A filled job still marked up breaks the guidelines and annoys the
  candidate. Rebuild from a current export, and set `valid_through` when you know the
  closing date. At volume, the search engine's indexing API is recommended over the
  sitemap for job URLs.
- **One page per location.** "Jobs in Macon" and "cashier jobs near me" are how
  frontline candidates search. A location page with real jobs on it answers both.
- **A sitemap listing every page, and a robots.txt that points to it.** Both generated.
- **Titles under 70 characters**, with what the candidate searched for first and the
  brand last, because results cut the end off.
- **One h1 per page, a meta description, a canonical URL.**

## AI assistants

Candidates now ask an assistant "who is hiring near me and what do they pay". Whether
the answer includes this employer depends on whether the assistant can read the site.

- **The content has to be in the HTML.** In a December 2024 study of AI crawlers, none
  of the major ones rendered JavaScript (Google's and Apple's excepted), so a
  careers site rendered entirely in the browser can look like an empty page to them.
  Every job, location and answer is written into the HTML here; JavaScript only adds
  filtering. This is the most common failure on existing careers sites, and the audit
  checks it first.
- **Plain facts in plain sentences.** Pay, schedule and requirements as text, not
  inside images or tabs that only open on click.
- **FAQ pages with FAQPage markup**, generated from the questions on the page.
- **Organization markup on the home page.**
- **`llms.txt`** at the root: a short Markdown summary of the site, its pages, open
  jobs by location and pay by job, generated from the same data. It is a proposed
  convention, not a standard every assistant reads. It costs nothing to publish and it
  is the cleanest summary an assistant can fetch, so it ships; nobody should expect
  rankings from it alone.

## What none of this can do

Nothing here guarantees a ranking or an appearance in an AI answer. It removes the
reasons a site would be excluded. Domain age, links from other sites, and how many
people search for the employer by name still matter, and a careers site cannot fix them.
