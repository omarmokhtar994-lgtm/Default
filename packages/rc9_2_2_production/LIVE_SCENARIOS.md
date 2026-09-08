# Running your own live scenarios

Everything below runs offline. Nothing here needs the repository.

## 1. Prepare the workbook

Start from one of the workbooks in `inputs/` or from your own RC8.6/RC9.1-shaped
workbook, then convert it to the two-tab Setup/Advanced layout:

    python3 tools/build_input_template.py YOUR_WORKBOOK.xlsx MY_SCENARIO.xlsx

It prints the row counts it wrote. The conversion changes **layout only** —
every contract field is carried across unchanged. If you want to prove that on
your own file, parse both and compare the canonical contract hash.

## 2. Set the rows that decide the run

On the **Instructions (Setup)** tab:

| Row | What it does |
|---|---|
| **Run Stage** | `Full Schedule`, or `Before Breaks Only` to check the roster before spending time on breaks |
| **Run Depth** | `Quick` (1h) · `Deep` (4h) · `Overnight` (6h) |
| **Target** / **Minimum Per Interval** | your coverage contract |
| **Minimum After Break Target Ratio** | **set this.** Without it Gate 5 only checks the break-stage delta and reports `PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD` — it decides nothing |
| **Protected Before80 / After80 Minimum Intervals** | without these Gate 4 reports `PASS_PROTECTED_NOT_EVALUATED` |
| **Language Working Window** | `Off` (default), `Rows With A Minimum`, or `All Rows` — see below |

On the **Language Setup** tab, `Coverage Start` / `Coverage End` and
`Minimum Per Interval` define each language group. A `00:00–00:00` window spans
the whole day and restricts nothing.

## 2b. Coverage Split — which group *staffs* which hours

`Minimum Per Interval` on Language Setup is a floor: "at least N of this group
are present". It does not say who carries the requirement. If International owns
the daytime and Domestic owns the evening, a minimum of 1 lets Domestic staff the
daytime as long as one International is on the floor — which is not the split you
described to the roster.

The **Coverage Split** tab makes a group *responsible* for its hours:

| Column | Meaning |
|---|---|
| **Coverage Group** | must match the `Coverage Group` column on Language Setup |
| **Start** / **End** | the window it owns; may cross midnight (`16:00`–`03:00`) |
| **Coverage Ratio** | share of the requirement that group must field. Blank = the workbook's `Minimum Per Interval`. `1.0` = the whole requirement |
| **Exclusive?** | `Yes` = nobody outside the group may work those hours at all |
| **Active?** | `No` or blank = the row is ignored |

The tab ships empty and the feature is opt-in: a workbook with no rows behaves
exactly as it did before. The requirement is grossed up for shrinkage like every
other requirement, and it is enforced in **both** stages — Stage 1 rosters to it
and the break stage may not hollow it out.

**Overlapping windows pool.** If two windows cover the same hour, the groups
cover it **together** against one requirement: their eligible people combine and
the higher of the two Coverage Ratios applies. An hour needing 10 is 10 people
between them, never 10 from each. Make the windows complementary only if you want
one group solely responsible there. The run log records shared spans as
`COVERAGE_SPLIT SHARED`; it is information, not a warning.

**Read the `COVERAGE_SPLIT` lines at the top of the run log before you wait on a
solve.** Each owning span is scored up front against the people who could staff
it, allowing for OFF days *and* for the fact that someone on a break is not
covering:

* `OK` — fits, with the headroom stated.
* `TIGHT` — it solves only if OFF days fall perfectly; expect no-break
  exceptions. Lower that group's Coverage Ratio or add headcount.
* `SHORT` — arithmetically impossible. The line names the peak interval and the
  numbers. No scheduler setting fixes it; change the ratio, the window, or the
  roster.

This exists because the same shape of mistake previously returned a bare
`INFEASIBLE` with nothing to act on. A group of 8 cannot hold 80% of a 13-hour
daytime window through its own breaks, and that is a headcount fact, not a
configuration one.

## 3. Run it

    python3 engine/RUN_UNIVERSAL_PRODUCTION.py \
        --input MY_SCENARIO.xlsx --output-root results/ --overwrite

Stage and depth come from the workbook; `--mode` and `--stage` override them,
and the run log states which source decided each. Add
`--language-working-window MINIMUM_ROWS` to try the language hours without
editing the sheet.

## 4. Read the result

Open the output workbook. **Read Me First** is the first tab:

* the result and whether the release gate passed
* coverage at target and floor, before and after breaks, as a share of active
  intervals — and what breaks cost
* **current headcount, headcount needed including breaks, and the gap**
* intervals below floor, quarters with nobody staffed, associates with no break

`Feasibility Certificate` holds the headcount arithmetic, `Candidate Leaderboard`
shows every candidate including which ones can actually take their breaks, and
the remaining sheets are per-rule audit evidence.

Score a whole results folder with:

    python3 tools/release_gate_report.py results/ --out-dir gate/

## 5. Before you publish a roster

* **Gate 8 must be PASS** — that is independent validation of the exported
  workbook, 0 hard failures.
* **Read the headcount line.** A `BREAK_CAPACITY_SHORT` result means the roster
  cannot cover the contract and take its breaks; no scheduler setting fixes
  that. The figure is a lower bound.
* **Check `shifts_outside_language_window`.** It is reported even when
  enforcement is off, so it tells you what turning it on would change.
* **Check break concurrency.** `break_concurrency_violations` counts intervals
  over the ratio cap. In `warn` mode it does not fail a gate, but on a small
  roster it can mean a large share of the floor is on break at once.

## Two cautions worth carrying into live use

**Turning on `Language Working Window` is a contract change.** It is not
comparable against a result measured without it, and the input-hash check cannot
detect that because the workbook does not change — only the engine's semantics.
Enable it deliberately, per workbook, and re-measure.

**A break-capacity surplus is not a promise.** A deficit proves headcount is
short. A surplus proves only that headcount is not the constraint — the measure
counts room per slot, not whether break windows and spacing let a placement
reach it.


## Running from the Colab notebook

Cell **5. Run the scenarios** now carries the controls directly:

| Field | Use |
|---|---|
| **MODE** | `SMOKE` · `QUICK` · `DEEP` · `OVERNIGHT` — picks the depth **and** the matching budget |
| **STAGE** | `FULL_SCHEDULE` or `BEFORE_BREAKS_ONLY` |
| **MY_WORKBOOK** | path to your own `.xlsx` — upload it in the Files panel first |
| **ONLY** | one or more scenario ids, comma separated |
| **LANGUAGE_WORKING_WINDOW** | `workbook` (use the sheet's own setting) or force `OFF` / `MINIMUM_ROWS` / `ALL_ROWS` |
| **TIME_LIMIT** | leave at `0` unless you want a budget that does not match MODE |

**Leave TIME_LIMIT at 0 and change MODE instead.** Mode sets the phase reserves
as well as the budget, and `DEEP`'s joint-refinement reserve alone is 5400s —
larger than a 3600s budget. A `DEEP` mode squeezed into a `QUICK` budget starves
Stage 1, which is what produced a Gate 5 failure and 87 concurrency violations
on Cricut Voice that vanished at the proper budget.

Run cells **1 → 2 → 3 → 4** before cell 5. Cell 3 defines `PACKAGE_ROOT`;
running cell 4 on its own raises `NameError: PACKAGE_ROOT is not defined`.

Your own workbook is run without the manifest hash check — that check exists so
a *known* scenario is never compared against a silently different input, and a
workbook that was never in the manifest is a different case. The seven packaged
scenarios stay hash-verified. Gates 2 and 9 will report `NOT_COMPARABLE` for
your data, which is correct: there is no RC9.1 baseline for it. Gates 4, 5 and 8
still decide.
