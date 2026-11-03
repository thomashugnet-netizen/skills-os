# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Adam Hickman.

- Writes day 1, day 7 and day 30 check-ins for new hourly hires, each answering a
  different question, with owners, fallbacks, probes, an escalation table and the lines
  to say back.
- Checks the plan in code: three touchpoints, four to six questions of twenty words or
  fewer, under three minutes read aloud, a fallback who is not the owner, day 30 not owned
  by the day-7 supervisor, kit, next shift, breaks, pay and safety acted on within 24
  hours, conduct routed to the grievance owner, fixes the site can make, a reply within
  seven days, and no question about health, family, age, religion or origin.
- Reads the check-in log: completion by site and touchpoint with a 90% range, nothing
  judged under ten due, escalations past their deadline, sites slow on urgent items, and
  answers logged that needed a response.
- Refuses logs with names, emails or phone numbers.
- An adversarial pass before release found dates read as phone numbers, a customer's
  kids and the family restroom read as personal questions, and malformed plans that
  crashed the checker. All are fixed and kept as tests.
