# Before a large employer puts this live

> **This is not legal advice.** It lists what legal, IT and brand teams at large
> employers typically check before a careers page goes live, so nothing surprises
> them. Requirements differ by country, state and city and change often; this file
> does not change with them. Work from the official source for each jurisdiction, or
> from counsel. Sources and their dates are in `sources.md`.

The checker covers what can be read from the files. Everything below is the part it
cannot see, and it goes on the launch list I hand over.

## Legal

- **Accessibility.** Website accessibility suits rose again in 2025, and food service is
  among the most-sued sectors. Build to WCAG 2.2 AA (this skill does), then have a
  person test with a screen reader and a keyboard: automated checks catch part of the
  problem, not all of it. Publish an accessibility statement and a way to report a
  barrier.
- **Accommodations.** Every page says how to ask for an adjustment to apply or
  interview, and someone answers that inbox.
- **Pay transparency.** Each location's posting rules: range, benefits description,
  which postings count. See `pay-transparency.md`.
- **Candidate privacy.** A notice at or before collection for applicants where the law
  asks for one (California's CCPA covers job applicants), linked from every page and
  from the application. If analytics or advertising tags are added, a cookie consent
  mechanism that matches where candidates are.
- **Equal opportunity statement.** Good practice everywhere, and still expected of many
  federal contractors under Section 503 and VEVRAA even after the rescission of
  Executive Order 11246.
- **E-Verify**, if the employer participates: the participation and Right to Work
  notices, in English and Spanish, where applicants will see them.
- **Claims.** Every `<mark class="confirm">` resolved by someone who can confirm it.

## IT

- **Hosting** on the employer's domain or a subdomain, with HTTPS.
- **The jobs feed**: where open jobs come from and how often the page is rebuilt or
  refreshed. A filled job left live breaks the search engine's rules and the
  candidate's trust.
- **Apply links**: the applicant tracking system's URL format, and the traffic source
  carried into it so recruiting can see which channel worked.
- **Search engine setup**: the sitemap submitted, and for job pages the search engine's
  indexing API if the volume justifies it.
- **Analytics**, if any, approved by privacy (see above).
- **Security review** of any script or form added after handover.

## Brand

- **Logo, colours and type** approved, including the contrast the checker enforced.
- **Real photography** of real employees, with their written consent.
- **Testimonials** from named employees who agreed to be quoted, in their words.
- **Languages**: which pages exist in which languages, reviewed by a native speaker.

## Verify before you rely on this

1. Pay-transparency rules for each state and city where the employer posts jobs
2. Whether the applicant privacy notice meets each applicable privacy law
3. Accessibility: a manual audit against WCAG 2.2 AA, not only the automated checks
4. Whether the employer is a federal contractor or E-Verify participant, and what that
   requires on the careers page
5. For employers in the EU: the national accessibility and pay-transparency laws
