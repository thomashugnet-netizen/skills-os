# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter.

## 1.0.0

First release, created with Cathy Neal.

- Joins a pipeline export to monthly channel spend: cost per application, per stage,
  per start and per hire still there at 30 days, with rank changes flagged.
- Reconciles the files first: label variants, missing months, months too recent to
  have started, application counts that disagree, channels with no spend.
- Prices screening time when given minutes per application and an hourly cost, and
  reports the break-even above which the cheapest channel stops being cheapest.
- 30-day retention on starts with a full window only, with a 90% range.
- Mix check by role, site and application month; channels explained by mix are kept
  out of the budget move.
- Elasticity only where spend varies, with the season caveat when high-spend months
  are everyone's peak months.
- A bounded reallocation (at most 20%) with expected starts, extra screening, a
  six-week check and a stop rule. Partial-cost channels are never ranked or targeted.
- Refuses exports with name, email, phone, address or notes columns.
- Before release, an adversarial pass found that the cheap channel stays cheapest per
  start on media cost alone in all four samples, so the suite asserts what the data
  shows rather than the reorder the skill was first written to expect, and that
  damaged spend values (NaN, zero spend months) crashed the engine. Both fixed and kept
  as tests.
