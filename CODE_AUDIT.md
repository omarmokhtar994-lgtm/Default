# CODE_AUDIT.md — RC9.2.1 repository audit

Scope: the whole repository, 23,906 lines of Python across 19 modules plus the
shell gate, fixtures, evidence and documentation.

| | |
|---|---|
| Engine | `engine/_tools/l632_universal_scheduler.py` — 19,696 lines |
| Everything else | ~4,200 lines across 18 modules |
| Test suites | 4 (`tests/test_rc9_2_1_*.py`) |
| Gate | `run_tests.sh` |

Findings from this audit are numbered **A#**. Release-behaviour findings 1–16
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
| **Status** | **DEFERRED, with evidence** |

The engine matches day columns with the same `startswith(short name)` rule that
caused A1. Applied to input workbooks rather than exports.

**Measured, not assumed:** 638 header rows across all 23 delivered workbooks were
checked against a strict matcher — **zero mismatches**. So this is latent, not
live.

**Deferred deliberately.** Changing input parsing that 23 workbooks depend on,
to fix a case that does not occur in any of them, is a speculative change to the
release-critical path. Revisit if a workbook ever ships a "Monthly"/"Saturation"
style column.

---

### A10 — Parallel skeleton ranking duplicates the selector

| | |
|---|---|
| **File** | `engine/_tools/phase_b_maturity.py` (~line 347) |
| **Category** | Duplicated / conflicting logic |
| **Severity** | **Low–Medium** |
| **Status** | **OPEN** |

`phase_b_maturity` builds its own skeleton ranking key (exception count, then
target, floor, 100, floor gaps, severe gaps, max run, overage) rather than using
`_candidate_quality_tuple`. The two orderings differ — notably this one ranks
exception count first and does not apply the protected-tier logic. Two ranking
implementations that can disagree is a maintenance and correctness hazard.

Not yet consolidated: it feeds adaptive break-task ordering rather than release
selection, so the blast radius of changing it needs establishing first.

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
| `assert` for runtime validation | 1 real hit → **A7**; others are test scripts |
| Division without a zero guard | 3 candidates, **all guarded** on inspection |
| Set iteration feeding ordered output | 2 hits, both order-insensitive |
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

## Verification after this batch

| Check | Result |
|---|---|
| `python -m py_compile` — all modules | PASS |
| `tests/test_rc9_2_1_production_identity.py` | **11/11** (new) |
| `tests/test_rc9_2_1_rule_semantics.py` | 30/30 |
| `tests/test_rc9_2_1_selector_integrity.py` | 36/36 |
| `tests/test_rc9_2_1_validator_parity.py` | **42/42** (+13) |
| engine selfcheck | PASS, byte-identical to the pre-change baseline |
| wrapper selfcheck | PASS |
| Real-artifact revalidation (NMG SP / Voice / Chat2) | PASS, metrics unchanged |
| `run_tests.sh` | **GATE PASS — 4 suites + 2 selfchecks** |

**119 guards** across four suites.
