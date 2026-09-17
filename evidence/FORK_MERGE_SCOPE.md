# The fork: what merging Coverage Split into the RC5 lineage actually costs

What this file answers: the two engines have been forked since Coverage Split
was built, nobody has stated what reconciling them involves, and "never merged"
is not a plan. This scopes it from the code.

## 1. The two sides

| | version | lines | Coverage Split references |
|---|---|---|---|
| this repo (`engine/_tools/`) | `L6.3.2.6-RC9.2.2-BUDGETED-SEARCH-AND-BREAK-CONCURRENCY-RC1` | 21,204 | **57** |
| RC5 as shipped | `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2` | 21,409 | **0** |
| RC5 + this session's work | `L6.3.2.7-…-RC2` | 22,094 | **0** |

Coverage Split exists only on this side. The release hardening, and everything
fixed this session (P-1, C-1, the capacity gate, stage-aware release gates,
workbook search controls, the warm slice floor, the validator granularity fix)
exists only on the other.

## 2. Direction

**Port Coverage Split into the RC5 lineage, not the reverse.** RC5 is the
release line: it carries the hardened parsers, the canonical metric surface,
the parity gate, the independent validator and the packaging. Moving all of
that onto the older engine would mean re-doing the RC5 authors' work and this
session's on top of it. Coverage Split is one feature; the hardening is a
lineage.

## 3. What the port consists of

**Seven new definitions**, self-contained:

| symbol | kind |
|---|---|
| `CoverageSplitRule` | dataclass |
| `COVERAGE_SPLIT_SHEET_ALIASES` | constant |
| `_parse_coverage_split` | parser |
| `coverage_split_rules_at` | lookup |
| `merge_coverage_split_rules` | pooling (the overlap semantics) |
| `coverage_split_required_headcount` | arithmetic |
| `coverage_split_capacity_report` | preflight report |

**About 50 call-site edits across eight existing functions**, and every one of
those eight **exists in the RC5 lineage** — so there is no structural conflict
to resolve, only integration:

| function | sites | what goes in |
|---|---|---|
| `calculate_metrics` | 11 | the per-quarter gap audit and its four summary fields |
| `run_case` | 9 | preflight report, audit wiring |
| `parse_input` | 9 | sheet parsing into `ParsedInput` |
| `build_skeleton` | 8 | the Stage-1 constraint |
| `atomic_save_workbook` | 4 | the audit sheet |
| `solve_breaks` | 3 | the Stage-2 constraint |
| `run_constraint_isolation` | 2 | constraint family reporting |
| `run_conflict_refinement` | 2 | constraint family reporting |

**Tests to port:** 38 references across `test_rc9_2_1_rule_semantics.py`.
**Fixture:** `Cricut_Voice_ROSTER_RECONCILED_40.xlsx`, plus the synthetic
overlap workbook the pooling semantics were verified on.

## 4. The one part that is not mechanical

`calculate_metrics` is the densest site (11) **and** it is the function whose
output becomes the canonical metric surface that the release parity gate
compares against the independent validator.

Adding `coverage_split_*` fields there means:

* the independent validator must be taught to recompute them, or they must be
  deliberately excluded from `PARITY_FIELDS` — silently adding engine-only
  metrics is exactly the shape of B-8, where the two sides carried the same
  name for different measurements;
* B-8's lesson applies directly: whatever the validator computes must be
  computed **from workbook cells**, at the granularity the solver constrains,
  not copied from the engine.

Everything else in the list is ordinary integration.

## 5. Sequencing

Do this **after** the Stage-1 default sweep resolves. If that sweep says revert
the floor to 240, the base being ported onto changes, and porting first would
mean doing the integration twice.

## 6. What is not claimed

* **No estimate of solver impact.** Coverage Split adds constraints, so a
  merged engine has to be re-measured against the baselines in this repo; the
  port being mechanical says nothing about the schedules it produces.
* **The 57/0 counts are references, not effort.** They bound the surface, which
  is the useful thing here: there is no hidden third place the feature lives.
