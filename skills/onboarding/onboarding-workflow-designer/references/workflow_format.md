# The workflow file

One JSON object. `scripts/owd.py check` refuses a file in the wrong shape and names the field. The sample in `sample/northline_store_associate.json` uses every field.

## Top level

| Field | Required | Meaning |
|---|---|---|
| `workflow` | yes | Name: role family, country, states |
| `status` | yes | `draft` or `final` |
| `offer_to_first_shift_days` | yes | Planned gap. The offer is accepted on day minus this; the first shift is day 0 |
| `steps` | yes | The list below |
| `jurisdiction` | for legal checks | `{"country": "US", "states": ["CA"], "e_verify": true}` |
| `states_verified` | per state | `{"CA": "who confirmed, when"}`. Empty or missing means not confirmed |
| `stop_rule` | yes | `{"when": "...", "decider": "role", "who_tells_hire": "role"}` |
| `max_silence_days` | no | Longest stretch with no contact with the hire. Default 3 |
| `fallback_alert` | no | `{"rate": 0.15, "min_hires": 20, "min_site_hires": 10}` for the log reader |

## A step

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Lowercase letters, digits, underscores. Used in the fallback log |
| `action` | yes | What is done, 14 words or fewer, no vague verbs |
| `done_when` | yes | The record or event that proves it happened, 20 words or fewer |
| `category` | yes | One of the eight categories below |
| `owner` | yes | One role or one named person |
| `after` | no | Step ids it waits for, or `["offer_accepted"]` (the default) |
| `needs` | when it waits | What it consumes from the step it waits for |
| `not_before_day` | no | A fixed earliest day, for scheduled messages and fixed-date steps |
| `duration_days` | yes | Realistic, including waiting and resubmission |
| `due_day` | yes | Deadline, days relative to the first shift (negative is before) |
| `tags` | no | From the list below |
| `rule` | for legal steps | A rule id from `compliance_rules.json` |
| `legal_basis` | for other legal steps | What requires it, and who confirmed it |
| `fallback` | when tagged | See below |
| `source` | no | `user`, `template`, `cloned` or `inferred` |
| `validated` | yes, to be ready | `true` only after a person confirmed the step |

**Categories:** Work authorization & legal filings; Payroll & pay setup; Policy acknowledgements; Required training & certification; Scheduling & first shift readiness; Equipment & logistics; Access & identity; Connection & engagement.

**Tags:** `legally_required`, `blocks_first_shift`, `external_dependency`, `needs_hire_action`, `can_follow_first_shift`, `fixed_date`. A step tagged with any of the first-shift blocker, external dependency or hire action tags needs a fallback.

## A fallback

```json
{"shape": "move_shift", "after_days": 2, "alert": "Onboarding coordinator",
 "action": "Call the hire; if Section 1 cannot be signed by day 0, move the shift",
 "decider": "Store manager"}
```

`shape` is `chase`, `substitute`, `conditional_start`, `move_shift` or `stop`. `after_days` counts from the step's start. `decider` is required for `move_shift` and `stop`.

## The fallback log

CSV, one row per hire per step: `hire_id, step_id, outcome, site, date`. `outcome` is `primary`, `fallback` or `stop`. `site` is optional but needed for the site screen. No names, emails or phone numbers: the reader refuses a file that has them.

## Rule ids

`i9_section_1`, `i9_section_2`, `e_verify_case` (when `e_verify` is true), `w4`, `new_hire_report`. Each is required for a US workflow, and each step carrying one must be tagged `legally_required`.
