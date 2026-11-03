# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Kristi Kennebrew.

- Checks every candidate-facing text: job ads, application and screening questions,
  text and email templates, offer letters, interview scripts and careers pages.
- 28 wording rules in four classes (protected characteristic, proxy requirement, coded
  wording, requirement to challenge), each with why, what to say instead and an official
  source where there is one; gendered titles get a direct replacement.
- Flags ads for physical jobs that state no physical demand.
- Library mode: reads a CSV or a folder of templates, groups the same line across
  templates, and ranks fixes by severity then by how many candidates each line reaches.
- Leaves alone: equal-opportunity statements, legal minimum ages, work-authorisation
  questions, a car or licence on a driving job, questions about customers rather than
  the candidate. Text in another language is reported as not checked.
- Refuses libraries with candidate columns.
- An adversarial pass before release found "driver's license" read as a driving job,
  an equal-opportunity promise ("we will never ask about your age") flagged, "he will
  be your trainer" flagged as describing the hire, and short English lines mistaken
  for another language. All fixed and kept as tests.
