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
- Counts the scheduled shifts and hours that fall on or after each expiry, when given
  a schedule.
- Finds people with no record of a document their role needs, when given the
  requirements.
- Flags crunch weeks: five or more of one document expiring at one site in one week.
- Keeps the later date when a renewed document sits beside the old one, and lists
  unreadable dates rather than guessing them.
- Planning-default renewal lead times for eight document types, overridable per role.
  Validity periods described in shape only.
- Refuses names, contact details and document numbers, and refuses work-authorisation
  documents by design.
- A fictional six-station sample planted with exactly what the radar must find, and a
  station that must come back clean.
- An adversarial pass before release found 25 issues, from a shift on the expiry day
  counted as at risk to names slipping through as ids. 24 are fixed and tested. The one
  left: a seven-digit id written like a local phone number ("555-1234") is accepted,
  because it cannot be told apart from an id that happens to look like one.
