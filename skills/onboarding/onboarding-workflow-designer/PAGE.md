# Onboarding Workflow Designer: page extras

Read by `tools/catalogue.py` for this skill's page on the library site, beside
what the page takes from SKILL.md, README.md and CHANGELOG.md. Not part of the
skill: `tools/package.py` leaves it out of the download, so editing it never
changes what anyone installs and needs no version bump.

The example output is copied from a real run. If the engine's output changes,
re-run this and update the excerpt:

    python3 scripts/owd.py check  references/sample/northline_store_associate.json
    python3 scripts/owd.py render references/sample/northline_store_associate.json --md doc.md

## Example prompt

> Design the onboarding workflow for store associates at Northline Goods. We hire in California and Texas, use E-Verify, and the offer is accepted 10 days before the first shift. Today: the store manager calls each new hire to confirm the date, enters their first two weeks of shifts, assigns the 45-minute safety module, the ladder sign-off for stockroom hires, and orders the uniform, which takes up to 5 days (we can issue one from store stock). Our onboarding coordinator sends the background check authorization, then orders the check from our vendor, which takes up to 5 days and sometimes needs chasing; she also sends the handbook and Form I-9 Section 1. Nobody gets a register login or badge until the check clears, and the IT service desk needs 2 days for that; until then a new hire can shadow a trained cashier. Payroll sends the W-4 and direct deposit form and files the state new hire report. The store manager checks the I-9 documents on the first day. If a check can't be cleared, or a hire misses a rescheduled first shift, the district manager decides and the store manager tells them the same day.

## Example output

From the skill's demo: the finished workflow it ships for this brief (`references/sample/northline_store_associate.json`, a fictional retailer, 18 steps), its checker's verdict and the document it renders. An excerpt.

```
Northline Goods: store associate, US (CA, TX): READY (0 blocking, 0 needs care, 0 unconfirmed)
shortest offer-to-first-shift: 8 days (planned 10); critical path: bg_consent > bg_check > system_access
start together at offer acceptance: bg_consent, direct_deposit, handbook_ack, i9_s1, ladder_cert, safety_training, schedule_shifts, uniform_fit, w4, welcome_call
```

**Steps** (6 of 18)

| Step | Action | Done when | Owner | Category | Waits for | Days | Due | Tags | OK |
|---|---|---|---|---|---|---|---|---|---|
| bg_consent | Send the background check disclosure and authorization form | Signed authorization stored on the hire record | Onboarding coordinator | Work authorization & legal filings | offer_accepted | -10 to -9 | -8 | legally_required, needs_hire_action | yes |
| uniform_fit | Order the uniform in the size the hire gave at offer | Order confirmation number saved on the hire record | Store manager | Equipment & logistics | offer_accepted | -10 to -5 | -1 | external_dependency | yes |
| bg_check | Order the background check from the screening vendor | Vendor portal shows a final result for the hire | Onboarding coordinator | Work authorization & legal filings | bg_consent | -9 to -4 | -2 | external_dependency, blocks_first_shift | yes |
| system_access | Create the hire's register login and staff badge | Login opens the till on the store test terminal | IT service desk | Access & identity | bg_check | -4 to -2 | -1 | blocks_first_shift | yes |
| i9_s2 | Examine the hire's original documents and sign Section 2 | Section 2 signed in the I-9 system with document details | Store manager | Work authorization & legal filings | i9_s1 | +0 to +1 | +3 | legally_required, needs_hire_action, can_follow_first_shift | yes |
| e_verify | Create the E-Verify case from the finished Form I-9 | E-Verify case number saved on the hire record | Onboarding coordinator | Work authorization & legal filings | i9_s2 | +1 to +2 | +3 | legally_required, can_follow_first_shift | yes |

**Fallbacks** (3 of 12, every one logged when it fires)

| Step | Fires after | Shape | Alert | Action | Decides |
|---|---|---|---|---|---|
| uniform_fit | 4 days | substitute | Store manager | Issue a uniform from store stock on day one |  |
| bg_check | 4 days | chase | Onboarding coordinator | Send the vendor a second request quoting the order number |  |
| system_access | 1 days | substitute | Store manager | Pair the hire with a trained cashier, no till access on shift one |  |

Stop rule: Background result cannot be cleared under the hiring policy, or a moved first shift is missed. Decides: District manager. Tells the hire the same day: Store manager.
