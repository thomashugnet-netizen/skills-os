# Changelog

An installed skill does not update itself. Once this folder is uploaded into Claude,
that copy is frozen until someone uploads a newer one, so this file exists to tell you
whether the version you are running is the current one.

The version you have is in `SKILL.md`'s frontmatter, and the engine prints it at the top
of every report.

## 1.0.0

First release, created with Kathleen Rakusin.

- Stage-by-stage cycle time, ranked by share of all waiting days rather than by median:
  a four-day wait everybody sits through holds more of the calendar than a twenty-day
  wait forty people reach.
- Three answers kept apart rather than averaged: the stage holding the most calendar
  time, the stage carrying a delay concentrated in a minority of sites, regions, sources
  or roles, and the stage that only stretches in peak months.
- Every candidate who reached a stage is sorted once: moved on, left (closed with an exit
  reason), skipped or undated, still open and recent, or still open with no movement for
  longer than the stage normally takes. Each stage is timed only over arrivals old enough
  to have finished it (three times its p90, two weeks minimum), so the median is not
  computed over the fast ones only.
- Every concentrated delay is re-tested holding each other dimension constant; an effect
  that shrinks below 40% or reverses is reported under Ruled out with the reason.
- A readable report (`--md`) beside the JSON, `--demo` on the bundled sample, and
  `--as-of` for the day the export was pulled.
- Refuses: name, email, phone or address columns; a status-history log not yet pivoted
  to one row per application; dates it cannot read or could read two ways; timestamps
  that contradict the stage order; a file mostly in flight; mixed stage vocabularies;
  under 500 usable rows; a file that is not UTF-8.
- Before release, an adversarial pass found that the first draft counted every candidate
  who had left as still waiting (8,412 people "queuing" 270 days on the retail sample),
  which would have refused any real export losing most applicants at the first step;
  that peak months added two Septembers together; that an effect reversing within a role
  could pass its confound check; and that day-first dates and spreadsheet serial numbers
  were silently dropped. All fixed and kept as tests. 5,150 randomly damaged files ran
  without a crash.
