# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release.

- Builds a fifteen-minute structured interview for a frontline role: opening and closing
  script, four to six questions chosen for what predicts staying (reliability and
  getting there, a tested realistic preview, availability confirmed out loud, one
  role-critical behaviour, their questions), 1-to-3 anchors written under each, probes,
  a decision rule, red and green flags, and questions not to ask with safe alternatives.
- Checks pasted interview questions against fourteen kinds of legal risk, two indirect ones, and six kinds
  of weak question, each with the reason, an official source where there is one, and a
  safe question that gets the same information.
- Grades a guide against a rubric the code enforces, and renders it as a one-page sheet
  with a score box beside each question.
- Absorbs two skills that were announced on the roadmap: `interview-question-bank` (the
  questions not to ask, with alternatives) and `scorecard-designer` (anchored scoring).
  `interview-panel-calibrator` stays as the follow-on for several interviewers.
- An adversarial pass before release found everyday phrasings the first rules missed ("What year were you born?",
  "Are you a single mom?", "How much are you on at the moment?"), job questions they wrongly flagged (a customer's
  kids, a church down the road, a pallet discharge), guide text that was never checked (anchors, flags, the role
  title), and malformed guides that crashed. All are fixed and kept as tests: 276 question cases, 37 broken guides,
  14 refused shapes.
- Words that are only a risk when they are about the candidate are skipped when the question is about a customer,
  a teammate or a place. Text in another language is reported as not checked, never passed.
- Known limits: the rules are English-only and match phrasings, so a new wording can pass; anchor order is not
  checked; lawful questions such as drug tests are not flagged.
- Rules describe the shape of state and city differences (pay history, criminal history
  timing) and flag those questions everywhere, because the safe question is the same in
  every state.
