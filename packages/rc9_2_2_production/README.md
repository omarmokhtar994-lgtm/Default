# RC9.2.2 — production package

`L6.3.2.6-RC9.2.2-BUDGETED-SEARCH-AND-BREAK-CONCURRENCY-RC1`

Self-contained: engine, inputs, 319 offline guards, gate scorer, evidence and
Colab runners. Nothing here needs the repository or any earlier run.

## What changed since the runs you scored

Seven defects, found by reading artifacts rather than reasoning about code.
Four were the **same bug**: a per-attempt time slice clamped *up* to a floor, so
a search ran many times at a depth that could not converge.

| | Defect | Verified by |
|---|---|---|
| **A34** | Stage 1 got a 150s window for 15 profiles; every attempt ran at the 45s floor | AE AR B2B **131/159 → 168/168**, equal to RC9.1 |
| **A35** | The Stage-2 anchor reported a 77s reservation and spent 599.7s | 188s granted, **188.0s spent**; 3 → **7 of 7** objective modes |
| **A37** | Every break attempt ran at a 20s floor that returns no schedule | **0 UNKNOWN** attempts, was 10 of 25 |
| **A38** | Gate 5 could be satisfied by shipping a *worse* skeleton | absolute after-break coverage now always reported |
| **A39** | Retention measured against a skeleton that provably cannot ship | NMG EN+SP reads **−4**, not −18 |
| **A40** | Break-concurrency penalty inert at 1:140,000 against coverage | binds now; max concurrent 5 → 4 |
| **A36** | Gate 4's protected tier had no route from the workbook | two instruction rows |

Full write-ups: `CODE_AUDIT.md`, entries A34–A40.

## The input workbooks are the new two-tab template

**Every contract hash is unchanged.** The template was verified by parsing old
and new side by side across all 120 contract fields on all seven workbooks:
identical, zero mismatches. Only layout changed.

* **Instructions** — *Setup*: the 40 decisions you make per schedule, grouped by
  topic, with **dropdowns** on every enum field. Anything left blank says so in
  the Notes column instead of failing silently.
* **Engine Defaults** — *Advanced*: 23 engine-tuning rows, defaults intact,
  marked do-not-touch. These are the values every released result was measured
  with.
* **Input Checks** — the old tab held **hardcoded PASS/WARN text**. It reported
  PASS regardless of what the roster, demand or language setup contained. It is
  replaced with a pointer to the engine's real pre-solver validation, which runs
  every time and writes a code, day and time per failure to the audit JSON.

Four rows that *looked* like settings and were read by nothing are gone
(`RC9.1 Deep Default Seconds`, `RC9.1 Full Default Seconds`,
`RC9.1 Stage2 Search Order`, `RC9.1 Joint Budget Policy`). They are replaced by
two rows the engine actually acts on:

| Row | Options |
|---|---|
| **Run Stage** | Before Breaks Only · Full Schedule |
| **Run Depth** | Quick (1h) · Deep (4h) · Overnight (6h) |

A command-line flag still overrides, and the run log states which source decided
each.

## How to run

One scenario per Colab instance, seven instances, ~4 hours.

1. Upload this zip (or place it in Drive for the `B_WITH_DRIVE` notebook).
2. Open `runners/RC921_Colab_A_NO_DRIVE.ipynb`.
3. Set `ONLY` to **one** scenario id and run all cells.

`NMG_SP` · `CRICUT_VOICE` · `CRICUT_CHAT` · `AE_AR_B2B` · `GDI_REAL28` ·
`NMG_EN_SP` · `NMG_EN`

The runner refuses any workbook whose sha256 does not match `SCENARIOS.json`,
and runs the 319 guards first.

## What the evidence says about quality

**AE AR B2B reaches RC9.1 exactly** — 168/168 before breaks, 162/168 after, floor
intact, independent validation PASS.

**NMG EN+SP's break loss is not an engine defect.** Counting how many people can
break in each quarter-slot without dropping below target:

| | NMG EN+SP | Cricut Voice |
|---|---|---|
| slots with **zero** target slack | **396 of 504 (78.6%)** | 108 of 528 (20.5%) |
| break-quarters to place | 340 | 660 |
| lossless capacity | **112** | 902 |
| | **deficit 228 — FORCED** | surplus 242 |

228 break-quarters have nowhere lossless to go. Nearly four fifths of that week
runs at exactly target with no spare body. **No scheduler can fix that** — it
takes headcount, a lower target, or shorter breaks. Cricut Voice on the same
engine absorbs 97%.

## Known open item — not a blocker

The selector maximises `after_target` lexicographically and is indifferent to
floor, overage and tier breadth once that is settled. On NMG EN+SP it traded
**9 after-break floor intervals, 5 extreme-overage intervals and 7.89 FTE of
avoidable overage for 3 target intervals**. The fix is an epsilon-constraint
bounding that trade; it moves candidate selection on every scenario, so it needs
a baseline run first and is deliberately **not** in this build.

## Two numbers still yours to set

Both gates report "not configured" rather than quietly passing.

* **Gate 5** — add `Minimum After Break Target Ratio` (e.g. `0.95`) to a
  workbook's Setup tab. Per schedule.
* **Gate 4** — add `Protected Before80 Minimum Intervals` and
  `Protected After80 Minimum Intervals`.

## Still unverified

`GDI_REAL28` was killed by Colab (rc −9) and `NMG_SP`'s archive never uploaded
intact, so the 24/7 day-tail behaviour has **no** current evidence. Those two
runs are the gap between this package and a full release sign-off.
