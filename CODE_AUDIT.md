# CODE_AUDIT.md — RC9.2.1 repository audit

Scope: the whole repository, 23,906 lines of Python across 19 modules plus the
shell gate, fixtures, evidence and documentation.

| | |
|---|---|
| Engine | `engine/_tools/l632_universal_scheduler.py` — 19,696 lines |
| Everything else | ~4,200 lines across 18 modules |
| Test suites | 9 (`tests/test_rc9_2_1_*.py`) — 4 at the start of this audit |
| Gate | `run_tests.sh` |

Findings from this audit are numbered **A1–A33**. Release-behaviour findings 1–16
from the earlier remediation cycle are recorded in
`docs/RC9_2_1_CONSOLIDATED_ISSUE_REGISTER.md` and are not repeated here.

Status values: OPEN / IN PROGRESS / FIXED / VERIFIED / DEFERRED.
**VERIFIED** means the regression test *and* the full gate have passed.

---

## Method

1. Structural inventory and LOC.
2. Automated pattern sweeps across every Python file (results in *Sweeps* below).
3. Line-by-line reading of the non-engine modules, release-critical first.
4. Targeted reading of engine functions reachable from the release gates.
5. Fix → regression test → full gate, iterating.

The engine is 19,696 lines and was **not** read line by line; it was swept
automatically and read closely around the release-critical paths. That limit is
stated rather than glossed over.

---

## Findings

### A1 — Day-column matching binds non-day columns to days

| | |
|---|---|
| **File** | `engine/tools/independent_validator.py` · `parse_output_schedule` |
| **Category** | Logic defect / data integrity |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

**What is wrong.** Day-column detection accepted any header *starting with* a
short day name.

**Why it is a problem.** `"Monthly Total"` and `"Month"` bind to Mon;
`"Saturation"` and `"Satisfaction Score"` bind to Sat. The validator would then
read a non-day column as that day's assignments and compute coverage from it —
while reporting a clean parse. This validator gates release, so a wrong-but-clean
result is worse than a crash.

**Expected.** Only a genuine day column matches.
**Current (before fix).** Six of nine plausible non-day headers false-matched.

**Fix.** Exact short name, or a label equal to / beginning with the full day name
plus a space.

**Relationship.** Introduced by the fix for issue 13 in the previous cycle —
a defect in a defect fix, found by auditing my own change.

**Regression test.** `DayColumnMatchingIsNotOverBroad` — 3 tests, including the
nine-header false-match table.

---

### A2 — Break-sheet columns were read by position when a header was missing

| | |
|---|---|
| **File** | `engine/tools/independent_validator.py` · `parse_breaks` |
| **Category** | Data integrity / silent failure |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

**What is wrong.** Column indices fell back to positional defaults
(`associate=0, day=1, shift=2, …`) when a header was absent.

**Why it is a problem.** Those defaults happen to match today's export order, so
the validator is silently *correct by coincidence*. A reordered or renamed
column would be read from the wrong position with no error, and could produce a
PASS built on the wrong data. A validator that gates release must not guess at
its own inputs.

**Fix.** Required columns (`associate`, `day`, `duration minutes`) must be
present; otherwise raise, naming the missing keys and what was found.

**Regression test.** `BreakSheetColumnsComeFromHeaders` — 7 tests including a
fully reordered sheet and a missing required header.

---

### A3 — A single malformed break duration aborted the entire validation

| | |
|---|---|
| **File** | `engine/tools/independent_validator.py` · `parse_breaks` |
| **Category** | Error handling |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

`int(float(cell or 0))` raises on a non-numeric cell, aborting before any other
rule is checked. Now the row is kept with `duration = 0`, which the existing
`INVALID_BREAK_ROW` check rejects downstream — the defect is surfaced rather
than swallowed, and every other rule still runs.

**Regression test.** `test_non_numeric_duration_does_not_abort_validation`,
plus `test_short_row_does_not_raise_index_error` pinning that a truncated row is
reported rather than silently dropped.

---

### A4 — Case-root run identity was missing the contract hash and run id

| | |
|---|---|
| **File** | `engine/RUN_UNIVERSAL_PRODUCTION.py` |
| **Category** | Data integrity / release gate |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

**What is wrong.** `UNIVERSAL_RUN_IDENTITY.json` at case root carried
`input_sha256` and `engine_sha256` but not `contract_sha256`, `run_id` or
`parameters_sha256`. Confirmed on a real artifact: all three were `None`.

**Why it is a problem.** The wrapper can only know input and engine hashes before
the run; the rest are derived by the engine during parsing and were written only
to `work_dir/RUN_IDENTITY.json`. The release gate keys identity on input,
**contract** and engine hash plus run metadata, so the case-root artifact — the
file a reviewer or packager reads — could not satisfy it.

**Fix.** After the engine returns, merge its identity into the case-root file.
Wrapper/engine disagreement on a shared hash is recorded under
`identity_mismatches` rather than silently overwritten, and the provenance is
stated in `engine_identity_source`.

**Verified on a live run.** All four axes present, `identity_mismatches: None`.

**Relationship.** Same root cause as finding 3 (previous cycle) and **A5**:
identity asserted by literal or by partial capture instead of derived. A4's fix
is what makes A5's fix possible.

**Regression test.** `CaseRootIdentityIsComplete` — 4 tests.

---

### A5 — Published artifacts asserted a fabricated engine identity

| | |
|---|---|
| **File** | `engine/production/production_output_polisher.py` |
| **Category** | Data integrity / release gate |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

**What is wrong.** Module literals were written into the published production
workbook's Production Summary sheet, into `PRODUCTION_ARTIFACT_MANIFEST.json`,
and into the production ZIP filename:

```
RELEASE = 'L6.3.2.3-RC9.1-...'                 while publishing an RC9.2.1 run
ENGINE  = '4b5f58e5df5513057f511d9e13ccece4…'  matching NO engine in the project
```

That hash is not RC9.1's `da21c3ba…`, not RC9.2.1's `56ec2eef…`, and not the
current build. **Every published artifact asserted an engine identity that never
existed** — in the path that ships to the client, and directly against the
exact-engine-identity hard gate.

**Fix.** `run_identity(case_root)` derives release, engine hash, contract hash,
run id and input hash from the run's own artifacts. Literals remain only so a
case root without identity still publishes, and that path is marked
`identity_source='FALLBACK_LITERALS'` so the substitution is visible.

**Verified end to end.** Published engine SHA now equals the actual engine SHA
byte for byte; release reads RC9.2.1.

**Regression test.** `PublishedIdentityIsDerivedNotHardcoded` — 9 tests,
including one pinning that the old literal matched no real engine.

---

### A6 — Identity merge stopped at the first source

| | |
|---|---|
| **File** | `engine/production/production_output_polisher.py` · `run_identity` |
| **Category** | Logic defect |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

The first version of A5's fix `break`s after the first identity file found. A
case produced before A4 has a `UNIVERSAL_RUN_IDENTITY.json` without the contract
hash, while `debug/RUN_IDENTITY.json` beside it carries it — so those cases would
still publish with the contract hash missing.

**Fix.** Read both sources and fill gaps; record the combination in
`identity_source`. Confirmed on a real pre-A4 artifact (CHAT2), which now
recovers `contract_sha256` and `run_id`.

**Relationship.** A defect in A5's own fix, found by testing the fix against a
*pre-existing* artifact rather than only a fresh one.

---

### A7 — Polisher selfcheck could pass having verified nothing

| | |
|---|---|
| **File** | `engine/production/production_output_polisher.py` · `main` |
| **Category** | Weak test / silent failure |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

The selfcheck was a bare `assert`. Under `python -O` assertions are stripped, so
it printed `SELFCHECK: PASS` having checked nothing. Replaced with an explicit
branch returning 1, plus a second check that the identity fallback is marked.

**Regression test.** `SelfcheckCannotPassVacuously` — including a subprocess run
under `python -O`.

---

### A8 — Test gate reported OK after a failed check, and passed on an empty glob

| | |
|---|---|
| **File** | `run_tests.sh` |
| **Category** | Misleading test output |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

Three problems: `echo "   engine selfcheck OK"` printed unconditionally after
`|| fail=1`, so a failed selfcheck still displayed OK; suite output was piped to
`tail -3`, truncating failures so the failing assertion was usually invisible;
and an empty `tests/` glob meant the loop body never ran and the gate reported
success having tested nothing.

**Fix.** Capture output and print it in full on failure; print OK only on
success and re-run a failed check visibly; refuse to report success when no
suites are found; print an explicit `GATE PASS/FAIL` line with the suite count.

**Verified three ways:** happy path (`GATE PASS — 4 suite(s)`), an injected
failing suite (exit 1, suite named), and an empty repository (exit 1, refuses).

**Note.** An initial suspicion that `|| fail=1` after a pipe could not detect
failure was **wrong** — `set -o pipefail` propagates it correctly. Recorded so it
is not re-investigated.

---

### A9 — Engine day-column matching carries the same over-broad prefix

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` · `_day_columns` |
| **Category** | Latent robustness |
| **Severity** | **Low** |
| **Status** | **VERIFIED** (was DEFERRED; see the resolution below) |

The engine matches day columns with the same `startswith(short name)` rule that
caused A1. Applied to input workbooks rather than exports.

**Measured, not assumed:** 638 header rows across all 23 delivered workbooks were
checked against a strict matcher — **zero mismatches**. So this is latent, not
live.

**Resolved.** The deferral rested on not being able to prove the change safe. A
broader equivalence run settled it: **57 workbooks, 1,507 header sheets, 7,288
header cells** produce identical day bindings under the strict rule, and no
sheet newly falls back to positional column guessing (which would have been
worse than the defect). All 25 exported schedules still re-parse.

Engine and validator now share one predicate, `_is_day_header`. The suffix
clause admits only a DATE ("Sunday 12 Jul" - the suffix must contain a digit):
accepting any suffix re-admits "Sunday Totals", and the header `"sunday shift"`
that really does appear in `AE_FRENCH_RC8_6_1_INPUT_READY`.

---

### A10 — Parallel skeleton ranking duplicates the selector

| | |
|---|---|
| **File** | `engine/_tools/phase_b_maturity.py` (~line 347) |
| **Category** | Duplicated / conflicting logic |
| **Severity** | **Low–Medium** |
| **Status** | **CLOSED — NOT A DEFECT** |

`phase_b_maturity` builds its own skeleton ranking key (exception count, then
target, floor, 100, floor gaps, severe gaps, max run, overage) rather than using
`_candidate_quality_tuple`. The two orderings differ — notably this one ranks
exception count first and does not apply the protected-tier logic. Two ranking
implementations that can disagree is a maintenance and correctness hazard.

**Resolved as a documented divergence, not a defect.** The blast radius was
established: this key orders Stage-2 *attempts*; the champion is still chosen
solely by `_candidate_quality_tuple` via `select_export_candidates`. A different
attempt order changes which candidates get produced under a time budget, not
which one wins. Consolidating the two would change search behaviour with no
correctness gain, so it is left alone and the relationship is now pinned by
`test_the_production_default_plan_is_unchanged_by_the_fix`.

Auditing it did surface a real defect in the same function — see **A19**.

---

### A11 — Replay tool read the pre-fix ranking from the wrong tuple slots

| | |
|---|---|
| **File** | `tools/replay_candidate_ranking.py` · `prefix_ranking` |
| **Category** | Logic defect / false release evidence |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

The tool reconstructed the pre-fix ordering by overwriting quality-tuple slots
9 and 10. Those hold the quantized deficit terms only when
`_protected_tier_counts` yields exactly one tier.

| Contract | Protected tiers | Deficit terms at | Slot 9 actually holds |
|---|---|---|---|
| target 90%, floor 75% | 1 (80) | 9, 10 | the deficit sum — correct |
| target 100%, floor 75% | 2 (90, 80) | 10, 11 | `-max_consecutive_floor_gaps` |
| target 80%, floor 75% | 0 | 8, 9 | `-max_consecutive_floor_gaps` |

Outside 90/75 the tool destroyed a real safety term and reported a "pre-fix"
verdict that was never the pre-fix verdict. This tool produced release evidence
about whether the deficit-masking defect cost the release.

**Fix.** The index is derived from `_protected_tier_counts` and then verified
against the tuple's actual contents; a shape change raises `SystemExit` instead
of skewing the result.

---

### A12 — `protected_benchmark_status` was a hardcoded `"PASS"`

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` (summary row) + `tools/release_gate_report.py` |
| **Category** | False verdict — absent evidence read as a pass |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

The engine wrote `"protected_benchmark_status": "PASS"` as a literal on every
successful run, including runs where neither protected minimum was configured
and the benchmark was therefore never evaluated. Confirmed on all four executed
RC9.2.1 runs: each carries `PASS` with `protected_before80_min` and
`protected_after80_min` empty. `release_gate_report.py` reads exactly this field
for gate 4 and treated `PASS` (and `""`) as a pass — so **gate 4 has been passing
on a benchmark that never ran**.

**Fix.** The engine reports `NOT_CONFIGURED` when neither minimum is supplied.
The gate report reports `PASS_PROTECTED_NOT_EVALUATED` and says so in the detail
column, rather than folding it into `PASS`.

---

### A13 — Skeleton-only detection was a substring test

| | |
|---|---|
| **File** | `tools/release_gate_report.py` |
| **Category** | Over-broad match → gates silently skipped |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

`"SKELETON" in status.upper()` also matches
`SKELETONS_AND_BREAK_DIAGNOSTICS_READY` and
`SKELETON_EXCEPTION_LOWER_BOUND_EXCEEDS_CAP`. Both reached the break stage, so
excusing gates 4 and 5 as `NOT_APPLICABLE` on them hid real break regressions.

**Fix.** Exact match against `SKELETON_ONLY_COMPLETE`, the one skeleton-only
status the engine actually emits (verified against the engine source by a test).

---

### A14 — Phase C reported safety PASS without any validation

| | |
|---|---|
| **File** | `engine/production/phase_c_quality_report.py` |
| **Category** | False verdict — absent evidence read as a pass |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

`hard_failures` defaulted to `0` when no count existed in either the candidate's
`output_validation` or the audit. A run whose output validation never executed
therefore reported `safety.status = PASS` with `hard_fail_count = 0`.

**Fix.** Absence is tracked separately from zero. No count anywhere yields
`NOT_VALIDATED`, and the report now publishes `hard_fail_count_reported`.

---

### A15 — Phase C report carried a two-release-stale release literal

| | |
|---|---|
| **File** | `engine/production/phase_c_quality_report.py` |
| **Category** | Identity drift |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

The module hardcoded the RC9.0 universal-production-platform name as the release
fallback. Same class as A5 and A7. Now derived from the engine's `VERSION`,
returning an explicit `UNKNOWN_ENGINE_RELEASE` rather than aborting a report if
the engine cannot be read.

---

### A16 — An unevaluated production quality gate could reach `PASS_CLEAN`

| | |
|---|---|
| **File** | `engine/production/phase_c_quality_report.py` |
| **Category** | False verdict |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

The report's own interpretation text states that a failed production quality
gate cannot be exported as PASS. That held for a *failed* gate but not an
*unevaluated* one: with no gate result and no validation the status chain fell
through to `PASS_CLEAN`. Now `REVIEW_NOT_VALIDATED`.

---

### A17 — Phase C packager wrote ZIPs before checking required roles

| | |
|---|---|
| **File** | `engine/production/package_phase_c_outputs.py` |
| **Category** | Ordering defect / incomplete delivery |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

The required-artifact-role check ran *after* all three archives were written, so
an incomplete case still produced a `*_01_PRODUCTION_ONLY.zip` — with no manifest
beside it to warn anything downstream that globs for the production ZIP.

**Fix.** The check runs first; a refused case leaves no archive on disk
(verified).

---

### A18 — Phase A packager shipped an empty production archive as a pass

| | |
|---|---|
| **File** | `engine/production/package_phase_a_outputs.py` |
| **Category** | False verdict — empty result reported as success |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

No role check at all. A case with no schedule produced a valid empty archive
whose record read `file_count: 0, zip_test: PASS`. Now refuses.

---

### A19 — Stage-2 attempt plan ignored the requested objective modes

| | |
|---|---|
| **File** | `engine/_tools/phase_b_maturity.py` · `adaptive_break_attempt_plan` |
| **Category** | Parameter silently overridden |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

`preferred_modes` was concatenated *ahead of* the caller's list, so every plan
ran all seven preferred modes whatever was asked for.

| Requested | Modes actually planned | Tasks scheduled |
|---|---|---|
| `["target_priority"]` | 7 | 112 (vs 16) |
| engine default in `quality_gate_mode="warn"` (5) | 7 | +2 unrequested |

This silently voided `--break-objective-modes` and spread a fixed Stage-2 budget
across modes the caller had excluded — including the two quality-guard modes
that `default_break_objective_modes` deliberately omits outside `fail` mode.

**Fix.** `preferred_modes` is now a *ranking over* the caller's set, not a
source of modes.

**Blast radius, measured.** `RUN_UNIVERSAL_PRODUCTION.py` passes all seven modes
explicitly as its default, so across 300 random skeleton sets at the wrapper's
default pattern widths the production plan is **byte-identical**. No run made
with defaults changes. The fix bites only on a request that restricts the
modes — the case that was broken.

---

### A20 — Budget planner emitted a negative phase, then over-allocated the run

| | |
|---|---|
| **File** | `engine/_tools/phase_b_maturity.py` · `build_global_budget_plan`, `GlobalBudgetManager` |
| **Category** | Arithmetic defect / wall-clock overrun |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

At `total=60` the per-phase floors already sum to 110, and
`plan["break_search"] += total - sum(plan)` turned that into `break_search = -20`.
`GlobalBudgetManager` clamped it to zero and ran the 60-second budget as an
**80-second allocation**, putting cumulative phase deadlines past the run's own
`final_deadline`; `remaining_in_phase` could then exceed `remaining_total`.

**Fix.** Both layers scale to fit. Verified across **6,720** budget
combinations: no negative phase, every plan sums to its effective total, and no
phase deadline lands past the final deadline.

Mutation testing later showed non-negativity and correct sums were *not
sufficient*: dropping the proportional scaling and relying on the clamp alone
still satisfies both while handing `break_search` zero seconds — a run that never
places a break. Two further guards now pin that the two primary optimization
phases are never starved and keep at least 25% of the run.

---

### A21 — Bound certificate reported a tight bound when it measured nothing

| | |
|---|---|
| **File** | `engine/_tools/phase_b_adaptive.py` · `make_bound_certificate` |
| **Category** | Absent evidence presented as a good result |
| **Severity** | **Medium** |
| **Status** | **VERIFIED** |

`maximum_gap` started at `0.0` and was only raised by measurable stages, so a
certificate where no stage reported both an objective and a bound published
`maximum_relative_gap: 0.0` — which reads as a proven-tight bound. This value
reaches the summary CSV as `quality_certificate_max_relative_gap`.

**Fix.** `None` when nothing was measured, plus a `measured_stage_count`.

---

### A22 — Regression-lab harnesses could not find the engine

| | |
|---|---|
| **File** | `engine/regression_assets/regression_lab/run_fast70_migrated.py`, `run_phase_b_micro.py` |
| **Category** | Path defect / dead gate |
| **Severity** | **High** (a regression gate that never runs) |
| **Status** | **VERIFIED** |

Both resolved `ROOT` to `engine/regression_assets` and built `ENGINE_PATH` from
it, giving `engine/regression_assets/_tools/l632_universal_scheduler.py` — a path
that has never existed. Both died on `FileNotFoundError` before running a single
scenario.

**Fix.** The assets root and the engine root are now separate constants. The
fast70 harness executes again.

---

### A23 — Fast70 catalog integrity was guarded by bare `assert`

| | |
|---|---|
| **File** | `engine/regression_assets/regression_lab/run_fast70_migrated.py` |
| **Category** | Gate that cannot fail |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

`python -O` strips `assert`. Demonstrated: with the catalog cut from 70
scenarios to 3, `-O` printed `passed 0 / failed 0` and exited **0**.

**Fix.** Catalog size, duplicate ids and required categories branch and return
2. An unknown `--only-ids` value is an error rather than an empty run, and
selecting no scenarios no longer reports success. All verified under `-O`.

---

### A24 — Phase A closure verifier was eight bare asserts

| | |
|---|---|
| **File** | `engine/regression_assets/regression_lab/verify_phase_a_closure.py` |
| **Category** | Gate that cannot fail |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

Its entire verification was `assert` statements, so under `-O` it printed its
PASS line having checked nothing. An absent field also raised `KeyError` rather
than reporting a failure.

**Fix.** Rewritten to collect every failure and return 2. An absent field is now
a failure, not a crash.

**Not fixed, deliberately.** `qa/PHASE_A_CLOSURE_EVIDENCE.json` and
`RUN_UNIVERSAL_WFM.py` are absent from this repository. They are **not
regenerated** — a reconstructed baseline proves nothing. The verifier returns 3
for absent evidence, distinct from both a pass and a verification failure, and
says the file must be restored rather than rebuilt. `run_phase_a_closure`,
`run_phase_a_focused` and `run_phase_b_micro` remain **BLOCKED** on those
missing assets.

---

### A25 — A guard in this project's own suite tested a copy of the rule

| | |
|---|---|
| **File** | `tests/test_rc9_2_1_validator_parity.py` · `DayColumnMatchingIsNotOverBroad` |
| **Category** | Test that passes while the feature is broken |
| **Severity** | **High** (it was the guard for A1) |
| **Status** | **VERIFIED** |

Found by mutation testing, not by reading. The class reimplemented the
day-matching rule in the test body (`_accepts`) and asserted against its own
copy, so it passed for *any* implementation. The only test touching real code
grepped for one specific pre-fix string, which a differently-broken form evades.

Proof: swapping the validator to `norm(d) in h` substring matching left every
assertion in that class green.

**Fix.** Rewritten to build a worksheet containing a decoy column and parse it
with `parse_output_schedule`, asserting the decoy is never read as a day's
shift. The decoy is placed both left and right of the genuine columns, because
matching scans in column order and a decoy-last fixture passes under a broken
rule. The mutant is now caught by 7 assertions.

---

### A26 — The engine calls a function that does not exist

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` · `derive_adaptive_feedback_cuts` (11556), `adaptive_operator_focus_cells` (11618) |
| **Category** | Undefined name → `NameError` at runtime |
| **Severity** | **Critical** |
| **Status** | **VERIFIED** |

Both functions call `parse_time_to_minute(row.get("time"))`. That name is
defined **nowhere** in the engine — the only similar symbol is
`parse_time_window`, which returns a tuple.

**When it fires.** Both call sites sit inside a loop over the candidate's
`language_gaps`. `calculate_metrics` populates that list whenever a language
minimum is unmet. So any candidate with an unmet language minimum that reaches
adaptive feedback raises `NameError`. Six live call sites reach these two
functions from the joint-refinement and descent paths (13075, 13331, 13334,
13450, 13477, 13605). The exposed scenarios are exactly the bilingual and
directional-skill ones.

**Fix.** `minute_of_day`, which is the exact inverse of the `hhmm(minute)` that
`calculate_metrics` writes into the field (round-trip verified at 0, 1, 555, 720
and 1439 minutes).

**How it was found — and why that matters.** Not by the test suites, and not by
reading. A static undefined-name check found it. Neither the 188 guards nor the
20-mutant campaign could have: mutation testing only measures whether the suite
notices code that *changes*, and this code was broken in the baseline. A
`ruff --select E9,F821` sweep is now **part of `run_tests.sh`**, verified to fail
the gate on an injected undefined name, with an in-process AST cross-check in
`tests/test_rc9_2_1_engine_name_resolution.py` for environments without ruff.

---

### A27 — Switching a quality gate off published a PASS for it

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` · `production_quality_gate.apply` |
| **Category** | Present negative evidence read as a pass |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

`apply()` treated *"no issues found"* and *"gate switched off"* as the same
case. Both fell into one `else` branch that wrote `gate_results[gate] = "PASS"`.

All eight quality gates route through this helper — coverage, next-Sunday
balance, break concurrency, target loss, whole-week balance, employee quality,
language reserve, skill allocation — and all eight accept `off` as a documented
workbook value (`… Gate Mode` instructions, validated against
`{off, warn, fail}`).

**Reproduced, not inferred.** With 17 detected break-concurrency violations and
`Break Concurrency Gate Mode = off`:

| Mode | Reported | failures | warnings |
|---|---|---|---|
| `fail` | FAIL | 1 | 0 |
| `warn` | WARN | 0 | 1 |
| `off` | **PASS** | 0 | 0 |

The violations were dropped from both lists and the gate published a clean
PASS. This is worse than the A12/A14/A16 family: not absent evidence read as a
pass, but *present negative evidence* read as one.

**Fix.** `off` now reports `NOT_ENFORCED`, and what it detected is preserved in
a new `suppressed_by_disabled_gates` list with `suppressed_issue_count`.
Turning a gate off still does not block release — `failures` and `warnings` stay
empty and the overall status is still PASS — it just no longer manufactures
evidence that the gate held. The two `gate_results.get(…, "PASS")` defaults
became `NOT_EVALUATED` for the same reason.

**Blast radius.** `gate_results` is reported, never compared, anywhere in the
codebase. All four executed RC9.2.1 runs used `warn`, so none of them changes.
Engine selfcheck output is unchanged.

---

### A28 — Stage 1 abandoned its skeleton portfolio silently

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` (Stage-1 profile loop) |
| **Category** | Truncated search reported as a completed one |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

Root-causing the Cricut Voice gate-2 FAIL found the run had requested **15**
skeleton profiles and attempted **one**. `stage1_attempts` held a single row,
the summary said nothing, and the run read as a completed search.

The arithmetic is deterministic. The Stage-1 profile window is `stage1_search`
minus `breakability_diagnostic_reserve_sec` (up to 55% of it); the loop breaks
at `remaining < 45` while forcing a 45-second minimum slice, so the number of
profiles that can run is `window / 45`:

| budget | stage1 | reserve | window | profiles of 15 |
|---|---|---|---|---|
| 900 | 114 | 62 | 52 | **1** |
| 1,800 | 228 | 125 | 103 | 2 |
| 2,700 | 341 | 187 | 154 | 3 |
| 5,400 | 682 | 375 | 307 | 6 |
| 10,800 | 2,222 | 600 | 1,622 | 15 |

**DEEP's design budget is 14,400s.** The evidence runs used `--time-limit 900`,
six percent of it. So the Voice shortfall is very likely an artifact of
under-budgeting rather than an engine quality regression — but nothing in the
artifacts said so, and that is the actual defect.

**Fix.** The engine records `stage1_profile_coverage` (requested, attempted,
skipped-for-budget, the names skipped, seconds remaining at stop) and logs
`STAGE1_PORTFOLIO_TRUNCATED`. The summary carries the counts plus `COMPLETE` or
`TRUNCATED_INSUFFICIENT_STAGE1_BUDGET`. `release_gate_report.py` returns
`NOT_COMPARABLE_SEARCH_TRUNCATED` rather than scoring a truncated search against
RC9.1, which would blame the engine for a budget that never let it search.

**Deliberately not done.** No threshold was retuned. Whether 55% of Stage 1 for
a diagnostic reserve and a hard 45-second slice floor are the right values needs
the re-run at the design budget to answer, not a guess.

---

### A29 — Gate 2/9 comparator would have compared incomparable runs

| | |
|---|---|
| **File** | `tools/release_gate_report.py` |
| **Category** | False comparison |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

An RC9.1 comparator arrived, so gates 2 and 9 became decidable. Building the
comparison surfaced three ways it would have produced a confident wrong verdict:

1. **Different input.** The RC9.2.1 NMG EN runs used a *repaired* fixture (sha
   `ed90d630`, two associates added on 23:00–08:00 to cover early Sunday); the
   RC9.1 baseline came from the unrepaired historical workbook (sha `230179d9`).
   Comparing their 227 against RC9.1's 214 reads as a **+13 target win** and
   means nothing — extra headcount trivially buys coverage.
2. **Different target tier.** `before_target` means "intervals at the workbook
   target", so it names a different tier under a different contract. Voice and
   Chat carry a 100% RC9.1 target; NMG EN and NMG SP carry 90%. The ratios
   happened to agree on every real case, which is luck, not a check.
3. **Truncated search** — see A28.

The comparator now matches on input sha256, active-interval count and target
ratio, and reports `NOT_COMPARABLE_*` rather than comparing. A clean result is
`PASS_AGAINST_CONSOLIDATED_BASELINE`, never a bare `PASS`: the evidence is
consolidated historical metrics rather than raw RC9.1 artifacts, and it covers
before-break quality only.

---

### A32 — Run identity was not reproducible, and `--resume` never worked

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` · run identity |
| **Category** | Non-determinism in a release-gate identity |
| **Severity** | **Critical** |
| **Status** | **VERIFIED** |

`run_parameters` is hashed into `parameters_sha256`, which is hashed into
`run_id`. It carried:

```python
"stage1_profile_deadline_epoch": float(stage1_profile_deadline),
```

an **absolute wall-clock timestamp**. So the run identity depended on the second
the run started.

**Two consequences, both serious.**

1. **Run identity was not reproducible.** Two runs of the same workbook with the
   same engine and the same parameters produced different `run_id`s. Measured:
   `parameters_sha256` `dc5d8541…` vs `d833ecb1…`, with `input_sha256`,
   `contract_sha256` and `engine_sha256` all identical. The exact-engine-identity
   release gate cannot mean anything if a rerun cannot reproduce the identity of
   the run it is checking.
2. **`--resume` was inoperative.** Resume compares the recomputed `run_id`
   against the checkpoint's and raises `Resume refused` on a mismatch — which was
   *always*. Checkpoint/resume has therefore never worked in this release.
   Segment 2 of a segmented run exited 3 in 4.5 s with
   `RuntimeError: Resume refused: input/contract/engine/seed/parameters hash
   differs from the existing run identity`.

**Why the earlier resume test did not catch it.** The resume-identity test was a
*negative* test: it proved resume refuses a foreign checkpoint. It does — it
refuses every checkpoint, including its own. Nothing tested the positive case.

**Fix.** `stage1_profile_deadline` is not hashed in any form. Expressing it
relative to `started_epoch` is not enough either: the deadline has a
`time.time() + 30` floor, so a relative value still carries scheduling jitter —
the first attempt at this fix still produced `30.355` vs `30.341`. It is a
*derived runtime artifact*, and what determines it (`global_budget_plan`,
`breakability_diagnostic_reserve_sec`) is already hashed. The absolute value is
still reported, under `run_wall_clock` in the audit.

**Verified.** Two identical runs now agree on `parameters_sha256` and `run_id`.
A three-segment resumable run goes 0/0/0 where it previously went 0/3/3.

---

### A33 — Coverage is not reproducible run to run, and the gate tolerance sat below the noise

| | |
|---|---|
| **File** | `tools/release_gate_report.py` + engine behaviour |
| **Category** | Threshold below the measurement noise floor |
| **Severity** | **High** |
| **Status** | **VERIFIED** |

Found while regression-checking the engine shipped in the Colab packages. Three
runs of **Cricut Voice** — same input, same seed 9000, same 300 s budget, same
host:

| run | engine | `before_target` | `after_target` |
|---|---|---|---|
| A | pre-fix | 248 | 245 |
| B | post-fix `880d6389` | 242 | 240 |
| C | pre-fix (control) | 243 | 243 |

Two things follow.

**1. The A32/A30/A31 fixes did not regress anything.** B (242) against its own
control C (243) differs by one interval. The apparent −6 against run A was A
being the outlier.

**2. Coverage varies by ~6 intervals at a fixed seed.** OR-Tools searching in
parallel under a wall-clock limit is not deterministic: the seed fixes the RNG,
not which worker reaches a bound first. `--solver-random-seed` therefore does not
make a run reproducible, only its random draws.

The gate 2/9 comparator used a tolerance of **2**, which sits *below* that noise
floor. It could have declared a regression on nothing but scheduling jitter — in
a tool built specifically to avoid confident wrong verdicts.

**Fix.** A shortfall smaller than the measured spread now reports
`INCONCLUSIVE_WITHIN_RUN_NOISE` and asks for a repeat run, rather than `FAIL`.
The real Cricut Voice gap of −14 is well outside the band and still fails.

**Consequence for reading any result.** A single run is weak evidence for
anything within a few intervals. This applies directly to the Colab runs: two
scenarios differing by a couple of intervals, on different Colab hardware, means
nothing.

---

### A34 — Stage 1 was funded for width it could not pay for, so every attempt ran too shallow to converge

| | |
|---|---|
| **File** | `engine/_tools/phase_b_maturity.py` (`build_global_budget_plan`), `engine/_tools/l632_universal_scheduler.py` (Stage-1 profile loop) |
| **Category** | Wall-clock allocation starves the phase that decides the answer |
| **Severity** | **Critical** — this is the whole RC9.2.1-vs-RC9.1 quality gap |
| **Status** | **VERIFIED** |

A28 recorded that Stage 1 abandoned its portfolio silently and deliberately did
not retune any threshold, because *"whether 55% of Stage 1 for a diagnostic
reserve and a hard 45-second slice floor are the right values needs the re-run
at the design budget to answer, not a guess."* The Colab runs answered it.

**Every Stage-1 attempt, in every scenario, in every recorded RC9.2.1 run, ran
at exactly 45.0 seconds.** Not approximately — the audit rows read `45.0` for
AE AR B2B (12 of 12), Cricut Voice (15 of 15), NMG EN+SP (17 of 17) and
GDI REAL28. That is the `max(45.0, …)` minimum-slice floor, hit every time.

The arithmetic, for the 2,400-second budget the runs actually used:

| phase | allocated |
|---|---|
| `joint_refinement` | 840 |
| `break_search` | 460 |
| `stage1_search` | **332** |
| `breakability_diagnostic_reserve` off Stage 1 | −182 |
| **Stage-1 profile window** | **150 seconds, for a 15-profile portfolio** |

`primary = total - fixed` left 792 seconds, of which Stage 1 took 42%. Stage 1
chooses the skeleton; `joint_refinement`, `coordinated_repair` and
`post_break_repair` can only polish the skeleton Stage 1 hands them, never
replace it. The allocation had that backwards.

**Measured consequence** (`evidence/STAGE1_SLICE_DEPTH_PROBE.md`, same workbook,
same profile, same seed, only the time limit varies):

| Scenario | Profile | 45s | 150s | 210s | 450s | RC9.1 |
|---|---|---|---|---|---|---|
| AE AR B2B | `target90_restore_champion` | UNKNOWN | 101 | — | **167** | 168 |
| AE AR B2B | `before_target_champion` | UNKNOWN | UNKNOWN | 166 | 166 | 168 |
| AE AR B2B | `release_gate_floor_satisfaction` | — | — | — | **168** | 168 |
| Cricut Voice | `target90_restore_champion` | 248 | 250 | — | 250 | — |
| Cricut Voice | `floor_gate_hunter_before` | 238 | 238 | — | 236 | 256 |

On AE AR B2B, 45 seconds is not a short attempt — it is **no** attempt. CP-SAT
returned no feasible skeleton at all, twelve times. The 131/159 the run
published did not come from Stage 1; a downstream fallback carried it. Given
210 seconds the same engine reaches 166 against RC9.1's 168, and
`release_gate_floor_satisfaction` at 450 seconds returns **168 of 168** — RC9.1
exactly — at objective 408 against the 10^9-scale objectives of the unconverged
attempts. The cliff is narrow and past it more time per profile buys nothing,
so `STAGE1_MIN_MEANINGFUL_SLICE_SEC` is set to **240s** on that measurement.

**Fix.** Two coordinated changes.

1. `build_global_budget_plan` takes `stage1_minimum_seconds`. A stated Stage-1
   need enlarges the protected primary block (capped at 70% of the run) so the
   *downstream* reserves scale down, and wins the stage1/break split up to 75%
   of that block. A caller that states no minimum gets the identical old plan.
   The engine states `portfolio_size × STAGE1_MIN_MEANINGFUL_SLICE_SEC / 0.82`,
   capped at 45% of the run.
2. The Stage-1 slice comes from `stage1_slice_seconds(remaining, attempts_left)`:
   the even split when it clears the meaningful minimum, otherwise the minimum
   itself, never more than the window holds. The portfolio is **not** truncated
   up front — a profile that proves OPTIMAL in 0.2s returns its slice unspent
   (NMG SP does this seventeen times), so easy scenarios still explore
   everything and only genuinely hard ones run out of window.

Effect on the Stage-1 profile window, same flags as the recorded runs:

| budget | window before | window after | break_search before → after |
|---|---|---|---|
| 1,800 | 113 | 540 | 345 → 453 |
| 2,400 | 150 | 720 | 460 → 602 |
| 2,700 | 169 | 810 | 519 → 678 |
| 7,200 | 700 | 2,640 | 1,796 → 1,803 |
| 14,400 | 3,104 | 3,790 | 5,116 → 5,693 |

Break search is not the donor and does not lose time in any case — the
reduction falls on `joint_refinement`.

**Deliberately not done — a portfolio reordering.** The first reading of the
AE AR B2B loss was that RC9.1's champion profile, `before_target_champion`, sat
at catalog position 14 and was listed in `skipped_profiles` in every segment, so
the winning strategy never ran. An evidence-ranked ordering was written and then
**removed**: at equal depth three profiles land at 166, 167 and 168, and the one
that reaches RC9.1's 168 exactly is `release_gate_floor_satisfaction` — *not*
RC9.1's champion here. Profile choice does not explain the loss, and on Cricut
Voice promoting the RC9.1 champion would have made the result *worse*
(`floor_gate_hunter_before` scores 236–238 where `target90_restore_champion`
scores 250). Ordering by RC9.1's champions is evidence about RC9.1's engine, not
this one.

**Still open — Cricut Voice.** Depth funding is worth about +4 target intervals
there, not the +10 that would reach the 256 in the baseline; both profiles
plateau. That row is also the only one in `RC9_1_BASELINE.json` sourced from a
*"preserved workbook leaderboard"* rather than a candidate replay, i.e. possibly
a best-of-pool figure rather than one run's champion. Recorded as an open
question, not resolved.

---

### A35 — The guaranteed Stage-2 anchor ignored its reservation and consumed the break-search phase

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` (guaranteed Stage-2 anchor) |
| **Category** | A phase spends 8x what its own audit record says it reserved |
| **Severity** | **High** — this is release gate 5 |
| **Status** | **VERIFIED** |

Found by refusing to accept gate 5 as a policy trade-off and reading the
Stage-2 attempt list of the A34 verification run.

`bounded_stage2_guard_reserve_seconds` is documented as protecting *"at least
one real break solve"* — a floor. The anchor did not use it:

```python
guard_slice = min(900.0, max(45.0, remaining * 0.80))
```

`remaining` is the whole `break_search` phase, so the anchor took 80% of it,
while `guard_record["reserved_seconds"]` reported `stage2_guard_reserve_sec`.
The audit therefore said **77 seconds** and the code spent **599.7** of a
678-second phase — a 7.8x overrun that was invisible because the only number
recorded was the one being ignored.

What the adaptive break search got with the remaining 78 seconds:

| | requested | actually run |
|---|---|---|
| objective modes | 7 | **3** (`target_priority`, `release_quality_guard`, `coverage_rebalance`) |
| attempts | — | 6, at 20.0s each |

`quality_convergence`, `floor_protected`, `balanced` and `target_100` never ran.
Gate 5 failed at 10/168 = 6.0% target loss with the search that decides break
placement effectively never executed.

**The 600 seconds bought nothing measurable.** The anchor returned objective
`156703574` — the identical value a **20-second** adaptive attempt reached on
the same skeleton, pattern width and objective mode.

**Fix.** `stage2_anchor_slice_seconds(reserved_sec, remaining_sec)`: the
reservation is the allowance, the phase share is a ceiling on top of it, and
the result never exceeds the time left. The audit now records
`granted_seconds` and `phase_remaining_at_start_sec` alongside
`reserved_seconds`, so a future overrun is visible in the artifact rather than
only by reading the code.

**Not yet claimed.** Whether this moves gate 5 off FAIL is a measurement, not a
deduction — the freed ~600 seconds have to be shown to buy break placement. The
end-to-end re-run is pending.

---

### A36 — Release gate 4's protected tier was unreachable from the business contract

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` (`ParsedInput`, `parse_input`, run entry) |
| **Category** | A release gate whose input has no route from the contract |
| **Severity** | **Medium** — a gate that can only ever report NOT_CONFIGURED |
| **Status** | **VERIFIED** |

A12 corrected `protected_benchmark_status` so it stops publishing `PASS` for a
check it never ran, and reports `NOT_CONFIGURED` instead. That was right, and it
exposed the larger problem: **nothing could ever configure it.**

`protected_before80_min` and `protected_after80_min` existed only as CLI flags.
`RUN_UNIVERSAL_PRODUCTION.py` does not pass them. No workbook instruction alias
set them — checked against the shipped `Instructions` and `Engine Defaults`
sheets of AE AR B2B and Cricut Voice, neither of which carries any
protected-tier row. Every other contract value in this engine is
workbook-driven. So the protected half of gate 4 reported
`PROTECTED_NOT_EVALUATED` on every run of the release, and there was no
supported way for a business user to change that.

**Fix.** `Protected Before80 Minimum Intervals` and `Protected After80 Minimum
Intervals` (with aliases) parse from the workbook exactly as the existing
optional benchmark minimums do, and an explicit CLI argument still overrides
the workbook, matching `effective_minimum_final_before_target`. Both fields are
**defaulted to `None`**, so an absent row leaves the tier unconfigured — the
behaviour every current workbook already gets — and direct `ParsedInput`
construction keeps working. The regression lab builds `ParsedInput` positionally
and caught this immediately when the fields were first added as required.

Verified against the real AE AR B2B workbook: unchanged → `None, None`; with the
two rows added → `160, 150`; and `protected_benchmark_pass` then returns a real
verdict (`after80 140 < protected minimum 150`) instead of nothing to check.

**What stays with the user.** What the numbers should be. The engine now has a
supported route for the value; the value itself is a business input and was not
invented here.

---

### A37 — The adaptive break search clamped every attempt to a floor that returns no schedule

| | |
|---|---|
| **File** | `engine/_tools/l632_universal_scheduler.py` (adaptive fully-compliant break search) |
| **Category** | Clamp-up slice floor, third instance |
| **Severity** | **High** — six target intervals in the shipped schedule |
| **Status** | **VERIFIED** |

Found by not accepting A35's outcome. A35 fixed the anchor overrun and the
break search went from 3 of 7 objective modes to 7 of 7, from 7 attempts to 25
— and the shipped `after_target` did not move at all: **156 before, 156 after.**
The freed 522 seconds bought breadth and nothing else, because every attempt
still ran at exactly 20.0 seconds and ten of the twenty-five returned `UNKNOWN`.

```python
slice_sec = budget_manager.slice_seconds(
    "break_search", attempts_left=remaining_tasks,
    minimum=20.0, maximum=900.0, share=0.86,
)
if slice_sec < 10:
    break
```

Same shape as A34's 45-second Stage-1 floor and A35's anchor: the even split
clamped **up** to a minimum, producing a search run many times at a depth that
cannot converge.

**Measured** (`evidence/BREAK_SLICE_DEPTH_PROBE.md`, one 168/168 skeleton, same
width, mode and seed, only the time limit varies):

| slice | 20s | 60s | 90s | 120s | 150s | 180s | 450s |
|---|---|---|---|---|---|---|---|
| `after_target` | UNKNOWN | UNKNOWN | 160 | 160 | 160 | **162** | 162 |

At the engine's own floor, break placement returns **no schedule at all**.
Feasibility appears between 60s and 90s; quality steps once more between 150s
and 180s and then stops — 450s returns exactly what 180s returns.

**25 attempts at 20s ship 156. One attempt at 180s ships 162**, with
`after_floor` at a full 168.

**Fix.** `BREAK_MIN_MEANINGFUL_SLICE_SEC = 180.0`, set on the measured plateau.
The loop now **stops** when the phase cannot fund an attempt of that length
rather than spending the tail on attempts that return nothing — the guaranteed
anchor has already secured a compliant candidate, so stopping is safe. The
`< 10` guard that admitted 20-second attempts is gone. Stopping early is
recorded as `STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH` in the audit and as a
budget event, so a short search is visible rather than silent — A28's lesson.

**Limits.** One scenario, one skeleton, one objective mode. AE AR B2B is the
hardest case in the regression set and the one whose gate 5 verdict was in
question; whether 180s is the right boundary for the other scenarios needs the
full re-run.

**A follow-up was written, measured, and reverted.** The package smoke test
showed NMG SP at a 240-second budget stopping before a single adaptive attempt
(`break_search` gets 60 seconds there), and that looked like a regression
against a remembered figure of 123. A "guarantee the first attempt" change was
committed on the strength of it.

The remembered 123 came from a **different, larger budget**. Measured properly
— pre-A37 engine versus post-A37, same 240-second budget, same seed, same
worker count, same input:

| engine | adaptive attempts | `after_target` |
|---|---|---|
| pre-A37 (20s floor) | 6 × 20.0s, every one returning 114 | **118** |
| A37, stop when depth is unfundable | 0 | **121** |
| A37 + guaranteed first attempt | 1 × 141.0s, returning 113 | **119** |

A37 did not regress NMG SP; it improved it by three intervals. The follow-up
fixed a problem that did not exist and cost two of them, because the one
shallow attempt it forced produced a worse result than the anchor already held
*and* consumed time that joint refinement and post-break repair used better.
"Some search beats none" was intuition; the measurement contradicts it.

The follow-up is reverted. The unconditional stop stands. At 2,700s and
14,400s the two variants are identical anyway — the first attempt clears 180
seconds regardless — so this only ever governed short functional runs.

---

### A38 — Release gate 5 could be satisfied by shipping a worse skeleton

| | |
|---|---|
| **File** | `tools/release_gate_report.py` |
| **Category** | A gate whose verdict moves without the deliverable moving |
| **Severity** | **High** — this gate decides break-stage acceptance |
| **Status** | **VERIFIED** |

Two AE AR B2B runs shipped the **identical** schedule — `after_target` 156 of
168 active — and gate 5 disagreed with itself:

| run | before | after | loss | verdict |
|---|---|---|---|---|
| A34 verification | 166 | 156 | 10/168 = 6.0% | **FAIL** |
| A35 verification | 162 | 156 | 6/168 = 3.6% | **PASS** |

Nothing about the delivered schedule changed. Stage 1 produced a worse skeleton
the second time, the delta shrank, and the gate flipped. Gate 5 computed only
`(before − after) / active` and never looked at the absolute result, so
**degrading Stage 1 made it pass.** Taken at face value this would have shipped
the release on a metric that does not mean what it says.

**Fix.** The delta stays — "did the break stage regress the schedule" is a real
question — but it can no longer be read alone. The absolute after-break
coverage is always in `gate5_detail` and carried as an `after_target_ratio`
column; with no absolute standard configured the gate reports
`PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD` rather than a bare `PASS`, following the
precedent gate 4 already sets with `PASS_PROTECTED_NOT_EVALUATED`; and
`RC9_MINIMUM_AFTER_TARGET_RATIO` holds an absolute standard when one is set, an
unparseable value reporting delta-only rather than reading as satisfied.

**What stays with the user.** The absolute standard itself is a business
commitment and was not invented here.

**Found while writing the guards.** An **absent** `target_losses_from_breaks`
column read as **zero loss**, so an artifact predating the column scored a
flawless break stage while carrying a 46-interval regression in its own
before/after pair — the same "missing field is a satisfied field" shape as A12
and A27. The loss is now derived from before/after when the column is absent,
and a summary whose reported loss contradicts its own before/after is refused
rather than scored. Both real AE runs are self-consistent and stay clean.

---

## Sweeps — patterns checked across all 19 modules

Recorded so the absence of findings is evidence, not silence.

| Pattern | Result |
|---|---|
| Bare `except:` | **none** |
| `except …: pass` (silent swallow) | **none** |
| Mutable default arguments | **none** |
| `open()` without a context manager | **none** |
| `TODO` / `FIXME` / `XXX` / `HACK` | **none** |
| `== None` / `!= None` | **none** |
| Mutable dataclass field defaults | none (2 hits were local variables) |
| `assert` for runtime validation | 1 real hit → **A7**; the regression-lab hits became **A23**, **A24** |
| Division without a zero guard | 3 candidates, **all guarded** on inspection |
| Set iteration feeding ordered output | 2 hits, both order-insensitive |
| Undefined names (`ruff E9,F821`) | **2 hits → A26**; now a gate step |

### Static sweep, every hit adjudicated

`ruff --select F,B` over `engine/` and `tools/` returned 45 hits. Each was read
rather than auto-fixed or dismissed; exactly one was a defect.

| Rule | Hits | Verdict |
|---|---|---|
| `F821` undefined name | 2 | **Real → A26.** Both fixed. |
| `B023` closure over a loop variable | 2 | **False positive.** `dynamic_pattern_key` is consumed by the `sort` on the very next line, inside the same iteration; the binding cannot change first. |
| `B905` `zip()` without `strict=` | 13 | **All safe.** Eleven pair a sequence with itself (`zip(xs, xs[1:])`) or with a 7-element day constant. The two dominance checks (9216, 11472) build both operands from one literal tuple constructor in the same function, so the lengths are equal by construction. |
| `F841` unused local | 6 | **All dead locals, no dropped enforcement.** `severity_ok`/`concentration_ok` are unused judgements, but the raw signals they derive from *are* emitted in the tradeoff row and *are* tie-breakers in the sort, so the adjacent comment holds. `preflight_probe_deadline` is unused because the phase deadline is enforced through `budget_manager.slice_seconds`. Left in place: deleting dead locals in a 19,696-line engine is churn with no gain. |
| `F402` import shadowed by a loop variable | 1 | **False positive.** `field` is a local loop variable in a function; `dataclasses.field` is only used at module level, at import time. |
| `F401` unused import | 14 | Cosmetic. Not touched. |
| `B007` unused loop control variable | 8 | Cosmetic. Not touched. |
| `B008` call in a default argument | 1 | `range(...)` in a regression-lab default; immutable, evaluated once. Harmless. |
| `subprocess` without timeout | present throughout; deliberate for long solves |

## Checked and found correct

Recorded so they are not re-investigated:

- **`Schedule` vs `Final Schedule` sheet choice** in the validator — content is
  identical in a real after-breaks export (0 differing rows across 27 rows).
- **`run_tests.sh` pipefail propagation** — correct (see A8 note).
- **`production_quality_gate` division** — guarded by `max(1, …)`.
- **Day-tail aggregate min/max** — guarded by `if total_after_values`.
- **`hhmm_to_min` AM/PM and 24:00 handling** — correct for all branches.

---

## Mutation testing

Reading a test suite cannot tell you whether it would catch a real defect.
Twenty semantically meaningful defects were injected one at a time into the
engine, the validator, the wrapper, the polisher, the Phase B and Phase C
modules and both tools, and the full gate was run against each.

| | |
|---|---|
| Mutants applied | **20** |
| Caught | **20** |
| Survived | **0** |

Two rounds were needed to get there, and both survivors were real:

- **M11** (budget plan can go negative) survived the first round. Investigation
  showed the surviving code still satisfied non-negativity and correct sums but
  starved `break_search` to zero seconds. Two guards were added; it is now
  caught.
- **M18** (validator day column back to substring matching) survived the first
  round and exposed **A25** — the guard for A1 was testing a copy of the rule.
  The test was rewritten behaviourally; it is now caught by 7 assertions.

---

## Verification after this audit

| Check | Result |
|---|---|
| `python -m py_compile` — all modules | PASS |
| `tests/test_rc9_2_1_orchestration_integrity.py` | **33/33** (new; +5 for A34) |
| `tests/test_rc9_2_1_phase_c_integrity.py` | **15/15** (new) |
| `tests/test_rc9_2_1_production_identity.py` | 11/11 |
| `tests/test_rc9_2_1_regression_lab_integrity.py` | **18/18** (new) |
| `tests/test_rc9_2_1_rule_semantics.py` | **56/56** (+7, +6 for A36) |
| `tests/test_rc9_2_1_selector_integrity.py` | **61/61** (+11 A34, +8 A35, +6 A37) |
| `tests/test_rc9_2_1_tooling_integrity.py` | **42/42** (new; +11 for A38) |
| `tests/test_rc9_2_1_validator_parity.py` | 42/42 |
| engine selfcheck | PASS, byte-identical to the pre-change baseline |
| wrapper selfcheck | PASS |
| Real exported workbooks re-parsed by the validator | **25/25**, zero anomalies |
| Budget-plan invariants | 6,720 combinations, 0 violations |
| Stage-2 plan on the production default | byte-identical over 300 skeleton sets |
| Mutation testing | **20/20 caught** |
| `tests/test_rc9_2_1_engine_name_resolution.py` | **5/5** (new) |
| `ruff check --select E9,F821` across engine, tools and tests | **clean** |
| `run_tests.sh` | **GATE PASS — 9 suites + 2 selfchecks + undefined-name sweep** |

**291 guards** across nine suites, up from 119 across four.

Every new guard was run against the pre-fix code:

| Suite | Fail against pre-fix code |
|---|---|
| `tooling_integrity` | 11 of 13 |
| `orchestration_integrity` | 17 of 21 |
| `phase_c_integrity` | 8 of 15 |
| `regression_lab_integrity` | 14 of 18 |
| `orchestration_integrity` (A34 batch) | 5 of 5 |
| `selector_integrity` (A35 batch) | 8 of 8 |
| `rule_semantics` (A36 batch) | 4 of 6 |
| `selector_integrity` (A37 batch) | 6 of 6 |
| `tooling_integrity` (A38 batch) | 11 of 11 |

---

## Remaining risks

1. **The engine was not read line by line.** 19,696 lines. It was swept
   automatically and read closely around every release-critical path. Defects in
   unreached engine code would not have been found by reading — **A26** is the
   proof that this limit is real, and the static sweep now added to the gate is
   the partial compensation.
2. **Gates 2 and 9 stay blocked.** They compare against RC9.1, which this
   project does not hold. Reported as `REQUIRES_RC9_1_BASELINE`, not as a pass.
3. **Three regression-lab harnesses stay blocked** on `RUN_UNIVERSAL_WFM.py`
   and `qa/PHASE_A_CLOSURE_EVIDENCE.json`, which are absent and must not be
   fabricated.
4. **A19 was not re-run end to end.** Its no-op on the production path is proven
   combinatorially rather than by a full solve; a restricted-mode run will now
   behave differently, which is the intended correction.
5. **A9 stays deferred** with measured evidence: 638 header rows examined across
   the real exported workbooks, zero mismatches.
