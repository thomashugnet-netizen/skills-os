# Sources

What each rule in this skill rests on, and when it was checked. Rules change; the date
says how old the evidence is. Vendor reports are labelled as such: they are useful for
direction and should not be quoted as fact without the underlying study.

Last reviewed: October 2026.

## Search engines

- **Google Search Central, Job posting structured data.**
  https://developers.google.com/search/docs/appearance/structured-data/job-posting
  Primary source for every `seo.jobposting_*` check: required properties (title,
  description as HTML, datePosted, hiringOrganization, jobLocation with country),
  markup only on a single job's page and never on a list, the title holding the job
  title only, markup that must match what is visible, expired jobs handled by a past
  `validThrough`, a 404/410 or removing the markup, the Indexing API recommended over
  sitemaps for job URLs, and the policy violations that get a site excluded.

## AI assistants

- **Vercel and MERJ, "The rise of the AI crawler", 17 December 2024.**
  https://vercel.com/blog/the-rise-of-the-ai-crawler
  None of the major AI crawlers they measured rendered JavaScript, including the
  crawlers behind ChatGPT and Claude; Google's and Apple's did. Basis for
  `ai.content_in_html` and for writing every job into the HTML.

## Candidates and conversion

- **Indeed Hiring Lab, July 2025.**
  https://www.indeed.com/news/releases/pay-transparency-across-high-earning-sectors
  About 59% of US postings included pay in May 2025; postings with an employer-provided
  salary received 3.8 times more applications (Indeed's data).
- **Appcast, apply-process research.**
  https://insights.appcast.io/7-tips-for-seasonal-hiring-success/shorten-your-apply-process
  Applications under five minutes convert better; most online applications take more
  than fifteen. A compilation citing Appcast's 2023 benchmark gives 12.47% completion
  under five minutes against 3.61% past fifteen (vendor compilation:
  https://www.pin.com/blog/application-length-drop-off-study/).
- **Phenom, State of Candidate Experience 2025** (vendor, Fortune 500 audit, full report
  gated). https://www.phenom.com/state-candidate-experience-report-2025
  Most Fortune 500 career sites did not suggest related jobs; most offered mobile apply
  in three steps or fewer.

## Accessibility and legal exposure

- **Website accessibility lawsuits.** Seyfarth Shaw counted 3,117 federal website
  accessibility suits in 2025, up 27% on 2024's 2,452; trackers that include state
  courts count more, with food service among the most-sued sectors. Reconciled here:
  https://www.adacompliancepros.com/blog/who-gets-sued-web-accessibility-filing-data
- **SHRM on careers sites and the ADA** (2021, still the clearest statement of the
  employment angle): hiring websites are likely covered, application-portal suits tend
  to settle, and WCAG AA is the working benchmark.
  https://shrm.org/topics-tools/employment-law-compliance/employers-advised-to-make-careers-websites-accessible-despite-recent-ada-ruling
- **European Accessibility Act.** Whether it covers an ordinary employer's careers site
  is disputed: it lists specific services, and some member states go further.
  https://lists.w3.org/Archives/Public/w3c-wai-ig/2024AprJun/0140.html

## Pay transparency

- **State posting laws, 2026** (vendor tracker, verify against statutes):
  https://coggno.com/blog/pay-transparency-laws-by-state-2026-employer-compliance/
  Lists California, Colorado, District of Columbia, Hawaii, Illinois, Maryland,
  Massachusetts, Minnesota, New Jersey, New York, Vermont and Washington with posting
  rules (Connecticut, Nevada and Rhode Island on request), plus cities including New York
  City. California, Maryland, New York and Washington also ask for a description of
  benefits, which is why `conv.benefits_on_job` exists.
- **EU Pay Transparency Directive**: pay information to applicants before interview;
  member-state transposition due June 2026. Check the national law.

## Privacy and notices

- **CCPA job applicant notice at collection** (example notice, Littler, 2025): categories
  collected, purposes, sources, disclosures, retention, and rights. Basis for
  `legal.privacy_link`.
  https://www.littler.com/sites/default/files/2025-03/ccpa_job_applicant_notice_at_collection.pdf
- **E-Verify**: participating employers must clearly display the Notice of E-Verify
  Participation and the Right to Work posters, in English and Spanish; online display is
  allowed. https://www.e-verify.gov/e-verify-user-manual-introduction/15-user-rules-and-responsibilities
- **Federal contractors**: Executive Order 11246 was rescinded; OFCCP's rescission rule
  takes effect 26 October 2026. Section 503 and VEVRAA have their own statutory basis
  and remain. https://www.fmglaw.com/employment-law-blog-us/ofccp-formally-ends-eo-11246-affirmative-action-requirements/
