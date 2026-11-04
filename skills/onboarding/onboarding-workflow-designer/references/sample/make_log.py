#!/usr/bin/env python3
"""
Generates northline_fallback_log.csv: one row per hire per logged step, for 600
hires across 20 stores. What is planted, and nothing else:

- bg_check: the vendor misses its turnaround for 24% of hires, at every store
  alike. A primary that fails this often is a vendor problem, not a store one.
- uniform_fit: 3% fall back, except stores S07 and S19 at 40%. Overall the rate
  looks fine; the problem lives at two stores.
- ladder_cert: only 12 stockroom hires, 5 fallbacks. A high rate on a handful
  of hires is not a finding.
- welcome_call: 6 fallbacks logged on a step the design gave no fallback.
- drug_test: 9 rows for a step that is not in the workflow.
- every other step: a 2-5% background rate, which must not be flagged.

    python3 make_log.py > northline_fallback_log.csv
    python3 make_log.py 7 > other.csv      # same pattern, another draw

Measured over 200 seeds (owd.py --test re-runs 40 of them): the step verdicts
were right every time. The site screen found both planted stores in 91% of
draws, and 10% of draws also carried one store flagged by chance (seed
20261102 is one: bg_check at S11, 16 of 30). That is what a 5% false discovery
rate looks like with two real findings, and why a site flag is a lead to check,
not a verdict. The shipped file uses seed 1, which carries no chance flag.
"""

import random
import sys

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 1

rng = random.Random(SEED)
STORES = [f"S{i:02d}" for i in range(1, 21)]
BACKGROUND = {"bg_consent": 0.04, "i9_s1": 0.02, "i9_s2": 0.03, "w4": 0.05,
              "direct_deposit": 0.05, "handbook_ack": 0.04, "safety_training": 0.03,
              "schedule_shifts": 0.02, "system_access": 0.03}

out = sys.stdout
out.write("hire_id,step_id,outcome,site,date\n")
hire = 0
ladder_left, ladder_fb = 12, 5
welcome_fb = 6
for store in STORES:
    for _ in range(30):
        hire += 1
        hid = f"H{hire:04d}"
        day = f"2026-{9 + hire % 2:02d}-{1 + hire % 28:02d}"

        def row(step, outcome):
            out.write(f"{hid},{step},{outcome},{store},{day}\n")

        r = rng.random()
        row("bg_check", "stop" if r < 0.02 else ("fallback" if r < 0.24 else "primary"))
        rate = 0.40 if store in ("S07", "S19") else 0.03
        row("uniform_fit", "fallback" if rng.random() < rate else "primary")
        for step, p in BACKGROUND.items():
            row(step, "fallback" if rng.random() < p else "primary")
        if hire % 50 == 7 and ladder_left:
            row("ladder_cert", "fallback" if ladder_fb else "primary")
            ladder_left -= 1
            ladder_fb = max(0, ladder_fb - 1)
        if hire % 97 == 3 and welcome_fb:
            row("welcome_call", "fallback")
            welcome_fb -= 1
        if hire % 67 == 5:
            row("drug_test", "fallback")
