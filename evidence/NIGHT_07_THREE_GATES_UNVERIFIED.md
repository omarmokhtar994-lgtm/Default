# #38 resolved precisely: 3 of 9 release gates have no independent check

## The measurement

`production_quality_gate.gate_results` holds the nine gates that decide whether
a schedule is releasable. Counting references to each inside
`engine/tools/independent_validator.py`:

| release gate | engine verdict | validator references |
|---|---|---|
| coverage | PASS | 28 |
| next_sunday_balance | PASS | 3 |
| break_concurrency | WARN | 4 |
| target_loss | PASS | 1 |
| floor_loss | PASS | 1 |
| whole_week_balance | WARN | 3 |
| **employee_quality** | **WARN** | **0** |
| **language_reserve** | PASS | **0** |
| **skill_allocation** | PASS | **0** |

Six gates are independently recomputed. **Three are taken on the engine's
word**, and `employee_quality` is actively returning WARN on a current run --
so the engine is reporting a quality problem that nothing verifies.

## What the earlier framing got wrong

The canonical metric surface is **not** the gap. All 53 engine metrics are on
it and 48 are compared; the 5 excluded are metadata (`schema_version`,
`evaluator`, `source`, `stage`, `break_stage_executed`), not measurements.
B-9's work closed that. Language coverage is also already validated --
`OUTPUT_LANGUAGE_MISMATCH` and `LANGUAGE_WORKING_WINDOW` both exist, and
`language_gap_count` is in parity.

The residual gap is narrower and sharper than "20 unchecked metrics": it is
three **gates**, not metrics, and gates are what authorise release.

## Corpus exposure decides the priority

| subsystem | workbooks affected (of 9) |
|---|---|
| language (multi-language rosters) | **4** -- Voice 2, GDI 4, NMG_EN_AND_SP 2 |
| skills | **0** |

* **`employee_quality` -- build it.** It is the only one of the three currently
  firing, so it is doing real work that nothing checks.
* **`language_reserve` -- build it.** 4 of 9 workbooks are multi-language, so it
  is exercised and testable.
* **`skill_allocation` -- do NOT build it.** Zero workbooks define skills, so
  the gate passes trivially and any validator for it would be untestable code.
  This is the same trap as nesting groups (0 of 15 workbooks) and S6-3.

## Interim change applied now

Building two validator subsystems is substantial work and is not attempted
here. What IS cheap and protects immediately: **make the absence explicit.**
The validator now declares which gates it did not independently verify, so a
reader can see that three verdicts are self-reported rather than assuming all
nine were checked.

That converts a silent gap into a declared one. It does not close the gap.

## Recommended follow-up, scoped

1. `employee_quality` validator -- recompute the per-associate fairness deltas
   (weekend, overnight, late-shift load) from the output workbook and compare.
2. `language_reserve` validator -- recompute reserve satisfaction per interval
   from the roster's language column and the coverage grid.
3. `skill_allocation` -- leave unbuilt until a workbook in the corpus actually
   uses skills.
