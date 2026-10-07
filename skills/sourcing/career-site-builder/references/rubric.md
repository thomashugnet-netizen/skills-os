# The checks

Every check `scripts/check_site.py` runs, grouped the way its report groups them.
**Blocking** means the site is not finished while it fails. **Advisory** means worth
fixing, and the report says why. *Page* checks run on every page; *site* checks need
the whole folder and are reported as not checked when you audit a single saved page.

The report gives a count per area, not a score. A missing JobPosting date is not worth
a number of points, and passing every advisory check does not make up for one blocking
failure.

## Search

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `seo.title` | blocking | page | every page has a <title> |
| `seo.title_length` | advisory | page | titles fit in a search result (70 characters or fewer) |
| `seo.meta_description` | blocking | page | every page has a meta description |
| `seo.h1` | blocking | page | exactly one <h1> per page |
| `seo.heading_order` | advisory | page | headings do not skip a level |
| `seo.canonical` | advisory | page | a canonical URL on every page |
| `seo.jobposting_required` | blocking | page | JobPosting markup has every field Google requires |
| `seo.jobposting_recommended` | advisory | page | JobPosting markup has pay, employment type, closing date and id |
| `seo.job_pages` | advisory | site | each job has its own page with JobPosting markup |
| `seo.location_pages` | advisory | site | a page per location people search for |
| `seo.sitemap` | blocking | site | sitemap.xml lists every page |
| `seo.robots` | blocking | site | robots.txt does not block the site |
| `seo.broken_links` | blocking | site | every internal link and asset resolves |

## AI visibility

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `ai.content_in_html` | blocking | page | the content is in the HTML, not only painted in by JavaScript |
| `ai.jobs_in_html` | blocking | site | every job page is linked from a plain HTML page |
| `ai.llms_txt` | advisory | site | an llms.txt summary at the root |
| `ai.organization` | advisory | site | Organization markup on the home page |
| `ai.faq_schema` | advisory | site | FAQ pages carry FAQPage markup |

## Conversion

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `conv.mobile_viewport` | blocking | page | a mobile viewport on every page |
| `conv.search_jobs_nav` | blocking | page | a jobs link in the header of every page |
| `conv.home_search` | advisory | site | a job search form on the home page |
| `conv.apply_link` | blocking | page | every job page has an Apply link |
| `conv.pay_shown` | advisory | page | every job page shows pay as a number |
| `conv.schedule_shown` | advisory | page | every job page says what the hours are |
| `conv.ats_handoff` | advisory | page | the jump to an external application site is explained |

## Accessibility

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `a11y.lang` | blocking | page | the page declares its language |
| `a11y.img_alt` | blocking | page | every image has alt text (empty for decoration) |
| `a11y.form_labels` | blocking | page | every form field has a label |
| `a11y.focus_visible` | blocking | site | focus is never hidden without a visible replacement |
| `a11y.contrast` | blocking | site | text colour pairs meet 4.5:1 |
| `a11y.reduced_motion` | advisory | site | motion switches off for people who ask for less |

## Honesty

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `content.placeholder` | blocking | page | no lorem ipsum, TODO or unfilled placeholders |
| `content.cliche` | advisory | page | none of the phrases candidates have learned to ignore |
| `content.unverified_claim` | advisory | page | awards and rankings are marked for confirmation |

## Speed

| Check | Severity | Scope | Passes when |
|---|---|---|---|
| `perf.page_weight` | advisory | page | HTML, CSS and JS under 500 KB per page |
| `perf.image_weight` | advisory | site | no image over 400 KB |
| `perf.third_party_scripts` | advisory | page | four or fewer third-party scripts per page |

## Not a check, but always reported

Everything inside `<mark class="confirm">` is listed at the end of the report. That
list is what the employer has to confirm before launch.

## What the checks cannot see

Whether the copy is persuasive, whether the photos are good, whether the pay is
competitive for the area, and whether a confirmed fact is true. Contrast is checked
for colour pairs declared together in the same CSS rule; text over images and colours
set inline are not measured.
