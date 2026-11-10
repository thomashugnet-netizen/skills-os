# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Joey V. Price, on the five values from his book
*The Power of HR*.

- Runs a short diagnostic conversation on one real situation and examines the
  approach through all five values, each read as a strength, a development
  opportunity or not enough evidence yet.
- Writes a strategic leadership profile, an evidence and assumptions review, one
  priority leadership move, an executive discussion brief and a focused action plan.
- Checks the diagnostic in code against the person's own words before they see it:
  evidence found word for word, all five values under their exact names, no gap read
  from silence, facts, results, interpretations and intentions kept apart, no verdict
  on the person, missing perspectives named with who to ask, the things the skill
  pushes back on answered, one priority move on a real gap, a complete brief with an
  ask under 80 words, and actions with one owner, an observable measure and a review
  date.
- Return visits: every earlier measure gets a result backed by something observed,
  and approval is never counted as success.
- An adversarial pass before release found four things, all kept as tests. A
  reported remark ("the COO said 'I think we need more applicants'") was refused as
  an opinion filed as a fact; quoted speech is now set aside. A stakeholder asked for
  by a shorter name ("the store managers" for "store managers at the six stores")
  was reported as never heard. "You never received the schedule" was read as a
  verdict on the person. And diagnostics with empty lists in place of evidence
  crashed the checker; found by fuzzing.
