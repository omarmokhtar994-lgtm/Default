# RC9.2.1 — 7 scenarios at 2700 s + release gates

Self-contained package for running the RC9.2.1 regression set on Colab and
scoring the release gates. Nothing here needs network access after the pip
install, and nothing depends on the machine it was built on.

## Why this run exists

Every published RC9.2.1 quality number so far came from a **900 s** run. DEEP
mode's design budget is **14,400 s**. At 900 s the engine explores **one** of its
fifteen skeleton profiles:

| budget | Stage-1 profiles explored |
|---|---|
| 900 s | 1 of 15 |
| **2,700 s** | **3 of 15** |
| 5,400 s | 6 of 15 |
| 14,400 s | 15 of 15 |

That is not a tuning detail. Cricut Chat's skeleton retention loss — the one
measured quality gap, and the reason Gate 4 sat at WARN — went from **15 to 0**
between 900 s and 2,700 s. So no current quality figure is a property of the
engine; they are all properties of a six-percent budget.

2,700 s is the cheapest budget that demonstrably changes the answer. It is not
the design budget. Treat this as the breadth pass that says *where* a full
14,400 s run is needed.

## Contents

```
SCENARIOS.json                  the 7 scenarios, budgets, input sha256s
inputs/                         the 7 workbooks
engine/                         RC9.2.1 engine, wrapper, validator, Phase C
tools/release_gate_report.py    scores gates 2,4,5,8,9
tools/replay_candidate_ranking.py
tests/                          237 offline guards, 9 suites
run_tests.sh                    the guard gate
evidence/RC9_1_BASELINE.json    RC9.1 comparator for gates 2 and 9
runners/rc921_runner.py         the runner (all variants call this)
runners/RC921_Colab_A_NO_DRIVE.ipynb
runners/RC921_Colab_B_WITH_DRIVE.ipynb
```

## Quick start

Open one of the two notebooks in Colab and run the cells top to bottom.

- **Variant A (no Drive)** — everything in the VM, download a ZIP at the end.
  Simplest. A disconnect loses the results.
- **Variant B (with Drive)** — results written straight to Drive, so a
  disconnect cannot lose a finished scenario, and several shards can write into
  one folder. **Use this for the parallel run.**

Or run it directly:

```bash
pip install "ortools==9.15.6755" openpyxl
python runners/rc921_runner.py --package-root . --results-root results
```

## Running in parallel

Scenarios are independent. Open N Colab instances and give each a shard:

```
instance 1:  SHARD = 0, SHARDS = 4
instance 2:  SHARD = 1, SHARDS = 4
instance 3:  SHARD = 2, SHARDS = 4
instance 4:  SHARD = 3, SHARDS = 4
```

or name them directly: `ONLY = "CRICUT_VOICE,NMG_SP"`.

Seven scenarios at 2,700 s ≈ **5.25 h sequential**, ≈ **1.5 h across 4 shards**.
Use a CPU runtime — this is CP-SAT, a GPU does nothing.

## What the runner does, in order

1. **Runs the 237 offline guards.** If the engine does not match its own tests,
   it stops. Nothing produced afterwards would be worth comparing.
2. **Verifies every input against its sha256** in `SCENARIOS.json`. A run against
   a silently different workbook produces evidence that cannot be compared with
   anything.
3. Runs each selected scenario, recording wall clock against budget.
4. Scores the release gates and writes `_gate_report/`.

Skip step 1 with `--skip-guards` only if you are re-running and already saw it
pass.

## What to send back

The **whole** results directory. In particular:

- `RUN_LEDGER.json` — which scenarios ran, on what hardware, wall clock vs
  budget, and whether anything overran
- `_gate_report/RC9_2_1_RELEASE_GATE_REPORT.csv`
- each `<SCENARIO>/` directory
- each `<SCENARIO>.log`

Wall clock and CPU count matter: a scenario that ran on 2 cores got a different
search than one on 8, and the gate numbers cannot be read without knowing that.

## What to expect in the results

Some of these are already known and are **not** new failures:

- **Gate 4 `PASS_PROTECTED_NOT_EVALUATED`** — no workbook configures a
  protected-tier minimum, so that benchmark has never actually run. It used to
  report a hardcoded `PASS`; it now says so honestly.
- **Gates 2/9 `NOT_COMPARABLE_*`** for most scenarios — only NMG SP, Cricut
  Voice and AE AR B2B have an RC9.1 baseline row with a matching input hash. The
  comparator refuses to compare across different inputs, contracts or target
  tiers rather than producing a flattering wrong number.
- **NMG EN historical** will fail preflight with `FIXED_CYCLIC_REST_CONFLICT`.
  That is correct: two associates carry 6.0 h and 9.0 h rest across the
  previous-Saturday boundary against a 12 h minimum.
- **Gate 5 may FAIL where it passed at 900 s.** A better skeleton is harder to
  place breaks into. That trade-off is the main thing this run is meant to
  measure.

## Engine identity

```
release      L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1
ortools      9.15.6755  (pinned - a different build can change selection)
```

`SCENARIOS.json` carries the engine sha256. Quote it with any result.
