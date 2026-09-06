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
