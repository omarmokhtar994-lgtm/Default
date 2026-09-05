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

## 24/7 is now verified

`GDI_REAL28` was killed by Colab with `rc −9`. That was an environment memory
limit, not the engine: the same workbook runs to completion here with memory
flat at 1 GB.

**It produces a production-eligible schedule** — `production_eligible TRUE`,
0 hard validation failures, 0 floor gaps, 1 approved no-break exception.

| | before breaks | after breaks |
|---|---|---|
| at target | 153 / 156 (98%) | 138 / 156 (88%) |
| at floor | 156 / 156 (100%) | 156 / 156 (100%) |

**This is not a comparison against RC9.1.** The baseline file states GDI_REAL28
and SAKS 11H/3OFF are *deliberately not asserted*, so there is no RC9.1 number
to beat. The claim is only that RC9.2.2 handles a 24/7 contract correctly.

`NMG_SP`'s archive never uploaded intact, so that scenario still has no run of
its own. Its workbook is in `inputs/` and matches the RC9.1 baseline hash, so
it is ready to run.


## New since the package you scored: it tells you the headcount you need

The engine already estimated additional headcount, from total productive hours
in the week. That is a necessary condition and not a sufficient one — coverage
has a shape, and a break has to land somewhere the interval can spare a body.
The gap was large: NMG EN+SP's aggregate estimate was **+2 associates** while
the shipped schedule finished **99 target intervals short**. Cricut Chat said
**+1** against **69 short**.

Every run now measures it directly from the schedule it built: per quarter-slot,
how many people can step off without dropping below target, bounded by the
concurrency cap, against the break-quarters that must be placed.

| | reports |
|---|---|
| **Read Me First** sheet, first tab | current headcount, headcount needed, the gap, and why |
| **Feasibility Certificate** | the same, beside the aggregate hours estimate |
| **Candidate Leaderboard** | per skeleton, so you can see which one is completable |
| run summary CSV | six columns, for scripted scoring |
| **Gate 5** | `STAFFING_LIMITED` when a failure is headcount, not the optimiser |

**Read the number as a lower bound.** A deficit *proves* headcount is short. A
surplus proves only that headcount is not the constraint — it counts room per
slot, not whether break windows and spacing let a placement reach that room.
Measured: NMG13 reported a six-slot surplus and still gave up 9 target
intervals to breaks.

### Why this matters for the two Gate 5 failures

Both were chased as optimiser defects for weeks. GDI_REAL28's regression twin,
run here, reported `BREAK_CAPACITY_SHORT` — 560 break-quarters to place, 416
placeable losslessly, **144 with nowhere to go, 28 → 33 associates** — and the
run independently concluded it needed 4 no-break exceptions against a cap of 3.
Two different mechanisms, same conclusion: that roster cannot take its breaks.

## The output workbook opens on the decision

28 audit sheets and a 110-row Production Summary is the right amount of evidence
and the wrong amount of reading. A **Read Me First** tab now opens first with
the result, coverage as a share of active intervals, what breaks cost, the
headcount numbers, and a pointer to where the detail lives. **Nothing was
removed** — the audit sheets are why a schedule can be defended when someone
disputes it.

The before-breaks artifact says what it is. It runs through the same writer
against a placeholder break solution, so it used to report "after breaks"
coverage, "intervals given up to place breaks: 0" and "associates with no
break: 0" for a workbook where breaks were never assigned. It now states that
breaks are not assigned, reports before-break coverage only, and labels its
quality gate as measured on a schedule with no breaks rather than as a verdict.

## Rebuilding this package

    python3 tools/build_production_package.py

It refuses to produce a zip whose offline gate does not pass inside the staged
package, and writes `MANIFEST.json` with the engine and input hashes.


## Language hours: Coverage Start/End can bound when people work

The Language Setup window answered one question — when must this language be
covered — and it reads naturally as two: also the earliest and latest those
associates may work. Nothing enforced the second. `language_eligible` is purely
a capability test, so on GDI a bilingual associate was scheduled 00:00–09:00
against a 16:00–07:00 window and stood on the floor at 08:00. Across that
schedule, 18 of 145 shifts sat outside their language's window.

Set **Language Working Window** on the Setup tab (or pass
`--language-working-window`):

| Mode | A shift must lie inside the window for |
|---|---|
| `Off` **(default)** | nothing — Coverage Start/End stays a coverage minimum only |
| `Rows With A Minimum` | language rows with Minimum Per Interval ≥ 1 |
| `All Rows` | every active row, including rows with no minimum |

A `00:00–00:00` window spans the whole day and never restricts anything, in any
mode. That is how AE AR B2B and Cricut Chat are written.

**Measured on GDI, both runs at 3600s, 4 workers:**

| | Off | Rows With A Minimum |
|---|---|---|
| bilingual/French hours outside 16:00–07:00 | 12 | **0** |
| before-break target | 153 | 153 |
| after-break target | 138 | 132 |
| after-break floor | 156 | 152 |
| floor gaps | 0 | 4 |
| no-break exceptions | 1 | **0** |
| avoidable overage, before / after | 265.96 / 165.69 | **251.60 / 157.14** |

The −6 after-break target sits exactly on this project's documented 6-interval
run-to-run noise band, so it is not claimed as a cost. The 4 floor gaps
reproduced across two runs at different budgets, so those are real. Skeleton
coverage is untouched, so the constraint bites at break placement, not shift/OFF
quality.

**Why the default is Off.** Turning it on is a contract change. NMG SP's Spanish
row is 17:00–02:00, so an enforced run stops being comparable against an RC9.1
baseline measured without it — and the gate's input-hash check cannot detect
that, because the workbook does not change, only the engine's semantics. Enable
it per workbook, deliberately.

Violations are counted and reported on every run whatever the mode
(`shifts_outside_language_window`), so the question is never invisible.

## What this build is verified to be

**The engine's scheduling behaviour is unchanged from the build whose results
you scored.** Since that scoring the engine gained exactly one line that can
affect the solver — the language-window constraint — and it is provably inert
here: all seven packaged workbooks parse to `Language Working Window = Off`,
which restricts zero associates. Everything else added is measurement, workbook
output, or gate reporting. Verified, not assumed.

| | |
|---|---|
| offline gate | 9 suites, 2 selfchecks, undefined-name sweep — run **inside** the built zip |
| AE AR B2B | 168/168 before breaks, equal to RC9.1 |
| GDI_REAL28 24/7 | production-eligible; 153/156 (98%) before breaks, 138/156 (88%) after |
| package | built by `tools/build_production_package.py`, which refuses to write a zip whose gate fails |

**Not yet verified, and the gap to a full sign-off:**

* **NMG_SP has never been run.** Its archive never uploaded intact. Its workbook
  is here and matches the RC9.1 baseline hash, so gates 2 and 9 will decide.
* **Six of seven scenarios have not been re-run on this build.** Their scored
  results still describe this engine by the argument above, but that is
  inference from the diff, not seven fresh runs.
* **Gate 5 and Gate 4 have no thresholds.** Both report "not configured" rather
  than quietly passing. They decide nothing until you set them.
* Cricut Voice's 244 vs 256 gap is unexplained; the selector's lexicographic
  trade is real and its tolerance experiment was inconclusive.
