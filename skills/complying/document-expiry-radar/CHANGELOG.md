# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release.

- Reads one row per person per document, with an expiry date, from any export.
- Sorts by the date the renewal had to start, not the expiry: expired and still
  scheduled, expired, start the renewal now, due within the horizon.
- Counts the scheduled shifts and hours that fall after each expiry, when given a
  schedule. A document is valid through the day it expires.
- Finds people with no record of a document their role needs, when given the
  requirements.
- Flags crunch weeks: five or more of one document expiring at one site in one week.
- Keeps the later date when a renewed document sits beside the old one, and lists
  unreadable dates rather than guessing them.
- Planning-default renewal lead times for eleven document types, overridable per role,
  including vehicle insurance, registration and periodic background re-checks for gig
  and courier work. Validity periods described in shape only.
- Refuses names, contact details and document numbers, and refuses work-authorisation
  documents by design.
- Contractors: a list of who is active on the platform replaces the schedule.
- Site minimums (`per_site_min`), such as one certified food manager per restaurant,
  with the day each site drops below it.
- A document that a role does not need is reported as lapsed and stops nobody working.
- Three fictional samples (delivery, quick-service restaurants, couriers), each planted
  with exactly what the radar must find and each with one site that must come back clean.
- An adversarial pass before release found 25 issues, from a shift on the expiry day
  counted as at risk to names slipping through as ids. 24 are fixed and tested. The one
  left: a seven-digit id written like a local phone number ("555-1234") is accepted,
  because it cannot be told apart from an id that happens to look like one.
