# RC9.2.2 RC4 — deep audit

Subject: `RC9_2_2_RC4_COMPLETE_BUNDLE`, engine
`117b14d0dcd4883769b2dea0ce437aa910c3b005239011f04358ffde8f3d3937`.
No code was modified. Every finding below was produced by executing the shipped
code; none is inferred from documentation or test names.

## Scope and its limits — read this first

The brief asks for a function-by-function review. The honest position: the engine
is **21,320 lines and 319 functions in one file**, 32,594 lines of Python across
41 modules. I did not read all 319 functions line by line, and no single pass
could. What I did instead:

- **Automated inventory** of every module, sheet, parameter and validation rule
  (complete, machine-generated — section 2).
- **Contract cross-check**: every one of the 98 instruction parameters the engine
  reads, traced against every workbook that must supply it (complete).
- **Executed adversarial mutation** of the input contract, ~30 fixtures, each
  traced through parse → preflight to confirm the mutation actually landed
  before any finding was recorded (complete for the parameters tested).
- **Profiling** of the pre-solver path with call counts (complete).
- **Targeted code reading** of the paths those measurements implicated.

Unreviewed by this pass, and named so you can commission it: the break-placement
pattern generator, the joint refinement optimiser
(`solve_joint_shift_off_language_break_refinement`, 1,031 lines), the output
workbook writer, and the regression-lab harnesses. Section 14 prices that work.

---

## 1. Executive summary

RC4 is the best-engineered build in this project so far. The four defects raised
against RC2 (F3, F4, F5, F8) are genuinely fixed and I re-tested each. The
generic "any `HARD_*` parser warning is a contract failure" rule in
`validate_input_contract` is the single best piece of design in the release
chain: it makes future strict parsers fail closed by default.

It is still **NO-GO for live**, on two independent grounds:

1. **Nothing has been solved on it.** All three shipped run artifacts record
   engine `ea1fa36e` (RC2), not `117b14d0` (RC4), and none produced a releasable
   schedule (rc=4 validation FAIL, rc=2 no schedule, rc=-9 killed).
2. **The input contract is not trustworthy.** Three separate silent-coercion
   defects let a workbook state one thing and the engine do another, with no
   warning anywhere — including a contract that says *no breaks* receiving 60
   minutes of breaks per associate (A-1, A-2, A-3 below).

Ranked above everything else for effort-to-value: a **9–10× speedup of the
pre-solver path**, measured, no behaviour change (P-1). It matters beyond speed —
Stage 1 is wall-clock budgeted and already reports
`TRUNCATED_INSUFFICIENT_STAGE1_BUDGET`, so the 10–16 s currently burned is search
that never happens.

---

## 2. Module-by-module inventory

### Code (32,594 lines, 41 modules, 1,003 functions)

| Module | Lines | Functions | Role | Risk |
|---|---|---|---|---|
| `engine/_tools/l632_universal_scheduler.py` | **21,320** | 319 | parser, preflight, Stage 1, Stage 2, metrics, writer | **Single point of everything** — see A-8 |
| `engine/RUN_UNIVERSAL_PRODUCTION.py` | 796 | 18 | release chain, gates, sealing | Verified fail-closed |
| `engine/tools/independent_validator.py` | 692 | 13 | artifact validation | Not independent — A-9 |
| `engine/production/production_output_polisher.py` | 340 | 25 | output UX layer | Unreviewed this pass |
| `engine/production/phase_c_quality_report.py` | 324 | 7 | quality gate | Verified reachable |
| `engine/_tools/phase_b_maturity.py` | 541 | 23 | adaptive scoring | Unreviewed this pass |
| `tools/release_gate_report.py` | 561 | 10 | gate scorer | Unreviewed this pass |
| 10 test suites | 5,082 | 506 | 429 offline guards | Gate reproduces: PASS |
| 8 thin runner shims | ~160 | — | entry points | `rc922_runner.py` is 19 lines |

**The eight functions over 500 lines:**

| Function | Lines | Line |
|---|---|---|
| `run_case` | **3,465** | 16839 |
| `solve_joint_shift_off_language_break_refinement` | 1,031 | 13119 |
| `build_skeleton` | 850 | 4991 |
| `calculate_metrics` | 814 | 7592 |
| `run_adaptive_decomposed_joint_optimizer` | 643 | 14411 |
| `parse_input` | 643 | 2119 |
| `write_output_workbook` | 635 | 11420 |
| `solve_breaks` | 565 | 6709 |

14 functions exceed 200 lines. 182 distinct multi-digit numeric literals.

### Workbooks (10 audited: 8 packaged + 2 live)

| Workbook | Sheets | Formulas | Validations |
|---|---|---|---|
| AE_AR_B2B | 20 | 45 | 10 |
| Cricut_Chat | 20 | 0 | 28 |
| Cricut_Voice (packaged) | 20 | 32 | 10 |
| GDI_REAL28 | 20 | 0 | 28 |
| NMG_EN_AND_SP | 20 | 16 | 28 |
| NMG_EN_FIXED_NESTING | 20 | 82 | 28 |
| NMG_SP | 20 | 6 | 10 |
| RC9_2_2_NMG_EN_PRODUCTION | 21 | 133 | 67 |
| **Cricut_Voice_New_RC4 (live)** | **15** | **592** | **7** |
| **NMG_RC4_CURRENT_42HC (live)** | 21 | 133 | 67 |

Sheet presence is **not uniform** (A-6). Every sheet appears in 10/10 except:
`RC9 Universal Setup`, `FT Wise 15 Min`, `Shrinkage 15 Min`, `Shift Catalog`
(9/10 — all four missing from the live Voice workbook), `RC9.1 Release Notes`
(7/10), `RC9.2.2 Release Notes` and `RC9.2.2 Validation` (2/10).

---

## 3. Detailed findings

### A-1 — CRITICAL — a contract of "no breaks" silently becomes 60 minutes of breaks

`_parse_break_segments`, engine line ~1758.

```python
if not segments:
    segments = [(1, "Break 1"), (2, "Lunch"), (1, "Break 2")]
```

Measured, driving the parser directly:

| Configured | Produced | Delivered |
|---|---|---|
| Short Break Count 0, Lunch Count 0 | `Break 1 / Lunch / Break 2` | **60 min of breaks** |
| Short Break Count −3, Lunch 1 | `Lunch` only | 30 min, short breaks dropped |
| 2 × 20-min short breaks + 30-min lunch (70 min) | `Break 1 / Lunch / Break 2` | **60 min** |

Three separate silent rewrites. `short_min not in {15,30,45,60}` coerces to 15;
`max(0, short_count)` swallows negatives; an empty result is replaced by a
hard-coded 15/30/15. None emits a warning; preflight returns WARN with no codes.

**Risk if not fixed.** Break minutes drive required headcount directly
(`need_with_breaks = ceil(need × shift_q / (shift_q − break_q))`). A client
contracted for no breaks, or for 20-minute breaks, gets a roster sized for a
different contract, and the audit trail says nothing. It also violates the
project's own standing rule against silently modifying scenario values.

**Fix.** Reject out-of-set durations and negative counts as `HARD_*` parser
warnings — the machinery already exists and already fails closed. Zero breaks is
a legitimate contract and must produce zero segments.
**Complexity** Low · **Priority** Critical · **Impacts** parser, preflight,
break stage, headcount reporting.

### A-2 — HIGH — an invalid `Interval Minutes` silently becomes 60

Engine line 1465:

```python
instructed = int(round(to_float(_instruction_get(im, ["Interval Granularity Minutes", "Interval Minutes", "Interval"], 0), 0)))
if instructed in {15, 30, 60}:
    return instructed
# ... otherwise infer from the demand sheet's time column
```

Measured on AE_AR_B2B, writing `Instructions!B4`:

| Value written | Parsed | Preflight | Warning |
|---|---|---|---|
| 15 | 15 | FAIL (empty 15-min sheet — correct) | — |
| 30 | 30 | FAIL (empty 30-min sheet — correct) | — |
| **7** | **60** | WARN | **none** |
| **45** | **60** | WARN | **none** |
| **0** | **60** | WARN | **none** |
| **"abc"** | **60** | WARN | **none** |

The parameter is live — 15 and 30 take effect. Out-of-set values are discarded in
favour of inference, and inference returns a plausible-looking 60.

**Risk if not fixed.** Interval granularity is the denominator of every coverage
percentage in the release. A scheduler who sets 45 believes the whole report is
45-minute; it is 60-minute. `Run Stage` and `Run Depth` already have an explicit
"a typo falls back rather than guessing" guard and log which source decided;
the far more consequential field has neither.
**Complexity** Low · **Priority** High · **Impacts** parser, every coverage
metric, gate reporting.

### A-3 — MEDIUM — the all-days aliases are unreachable (third recurrence of A51)

`_parse_language_days`. Acceptance is `norm(text) in {"all","alldays","daily","everyday","7days"}`,
but `norm()` does not strip spaces:

```
norm('All Days')  = 'all days'   -> no match -> HARD preflight FAIL
norm('Every Day') = 'every day'  -> no match -> HARD preflight FAIL
norm('7 Days')    = '7 days'     -> no match -> HARD preflight FAIL
norm('All')       = 'all'        -> matches
```

Three of five aliases can never fire. The two most natural spellings are now a
hard failure. The workaround applied was to edit the Voice workbook rather than
fix the normaliser — the same assumption about `norm()` that produced A51 and the
language-window flag being inert.

It fails **closed**, so it is not a safety hole, but a live scheduler typing the
obvious value gets a blocked run with no hint that `All` would work.

**Fix** (one line, retires the class):
`key = re.sub(r"[^a-z0-9]", "", norm(text))`, applied to the token aliases too.
Add the accepted vocabulary as an Excel dropdown so it cannot be typed free-form.
**Complexity** Low · **Priority** Medium · **Impacts** parser, preflight, template.

### A-4 — HIGH — 45 of 98 engine parameters have no workbook route

Machine-generated: every `_instruction_get` alias group cross-checked against
`Instructions`, `Engine Defaults` and `RC9 Universal Setup` in four
representative workbooks. **45 are absent from all four** and silently take
developer defaults. Among them:

- `Protected Before80 / After80 Minimum Intervals`, `Minimum After Break Target
  Ratio` — the three gate thresholds already known to be unset.
- All 8 `Employee ...` fairness gates (start-time swing, isolated workdays,
  isolated OFF days, late/overnight/weekend load deltas, preference satisfaction).
- All 3 `Skill Allocation ...` controls.
- All 4 `Qualified Language Break Certificate ...` limits.
- `Break Infeasibility Core Enabled`, all 3 `Logic-Based Break Feedback` rows.
- `Whole Week Balance Penalty Weight`, `Language Reserve Penalty Weight`,
  `Break Concurrency Penalty Weight`.
- `Allowed Shift Start Window`, `Shift Start Step Minutes`, `Hard Floor Tolerance`.

This is A36 generalised: the business contract cannot express most of what the
engine does. Two of these (`Language Working Window`, `Run Stage`, `Run Depth`)
exist in the newer workbooks only — so the same engine behaves differently on old
and new inputs for reasons invisible in the workbook.

**Risk if not fixed.** Every one is a behaviour a client cannot configure, tune
or audit. Two of them gate the release.
**Complexity** Medium (template rows + validation) · **Priority** High ·
**Impacts** template builder, parser, all workbooks, gate reporting.

### A-5 — MEDIUM — the live Voice workbook cannot switch interval granularity

`Cricut_Voice_New_DAY_SPECIFIC_LANGUAGE_RC4.xlsx` has **15 sheets** and is missing
`FT Wise 15 Min`, `Shrinkage 15 Min`, `Shift Catalog` and `RC9 Universal Setup`.
It also carries **592 formulas** (the next highest is 133) and only **7 data
validations** (NMG has 67).

Combined with A-2: switching that workbook to 15-minute granularity silently
reverts to 60 rather than failing on the missing sheet, because the value never
reaches the guard.

### A-6 — MEDIUM — dropdown enforcement is wildly uneven

Data-validation counts across the ten workbooks: **7, 10, 10, 10, 28, 28, 28, 28,
67, 67**. Every validation that exists does set `showErrorMessage` (the RC4 claim
is true), but a workbook with 7 validations leaves most enum fields free-text —
which is precisely how A-2 and A-3 become reachable.

### A-7 — MEDIUM — `language_rules_at` still fails open on an out-of-range day

The F3 call site is fixed (`rule_day = 0 if day_scope >= 7 else day_scope`), but
the function itself is unchanged:

```
day=0 -> 1 rule   day=6 -> 1 rule
day=7 -> 0 rules  day=99 -> 0 rules  day=-1 -> 0 rules
```

"No language rules apply anywhere" remains the default for a bad day index. Now
latent rather than live; it should raise or clamp.

### A-8 — MEDIUM — structural: one 21,320-line module, one 3,465-line function

`run_case` at 3,465 lines is longer than most complete applications. It is the
function that orchestrates budget, Stage 1, Stage 2, repair, selection and
export — every defect in this project's history has passed through it. There is
no seam at which any of it can be tested in isolation, which is why the 429
guards are mostly *source-text assertions* rather than behavioural tests.

### A-9 — LOW — the independent validator is still not independent

`load_engine` (line 47–50) `exec_module`s the engine and reuses its parser. It
can detect an inconsistency between the engine's plan and the engine's reading of
its own output; it cannot detect a misreading of the workbook. Acknowledged in
their own summary; recorded here for completeness.

### A-10 — LOW — `VERSION` still reads RC2

The RC4 engine sets `VERSION = "L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2"`, so
every RC4 artifact self-reports as RC2 — the same confusion the `rc921_runner.py`
filename already causes, in the field that identity checks read.

### A-11 — LOW — the sealed manifest overstates approval

`finalize_production_manifest` writes `approval_status =
'APPROVED_AUTOMATED_RELEASE_GATES'` and `production_ready = True` while quality
warnings stand. Their own continuity rule says a technically generated schedule
is not automatically production-approved.

---

## 4. Verified correct — do not "fix" these

Challenged independently and found sound:

- **Shrinkage gross-up.** `0 <= shr < 1` is enforced as `INVALID_SHRINKAGE`, and
  the arithmetic additionally clamps with `max(1e-9, 1-shr)`. Belt and braces.
- **Rest gap.** Negative and 500-hour values both produce `INVALID_REST_GAP`.
- **Breaks exceeding shift length.** Produces `BREAKS_EXCEED_SHIFT` and
  `BREAK_WINDOW_CONTRACT_INFEASIBLE`.
- **Selected-grid check.** Choosing 15- or 30-minute granularity against an empty
  demand sheet correctly fails preflight.
- **Missing `Language Setup` / `Preference` sheets.** Degrade to WARN, no crash.
- **Release chain.** Packaging requires `engine_rc==0 ∧ qrc==0 ∧ rc==0 ∧
  validation PASS ∧ not --skip-validation`; the seal triple-checks that the
  validation record hash, the polished file hash and the prepared manifest hash
  all agree.
- **`HARD_*` → contract failure.** The generic rule makes new strict parsers fail
  closed by default. Keep and extend it.
- **Package identity.** `SCENARIOS.json`, `MANIFEST.json`, `BUILD_MANIFEST.json`
  all carry the shipped engine hash.
- **Offline gate.** Reproduced here: 10 suites, 429 tests, 2 selfchecks,
  undefined-name sweep, all PASS.

---

## 5. Performance

### P-1 — HIGH VALUE — the pre-solver path is 9–10× slower than it needs to be

Profiled `capacity_diagnostics` + `validate_input_contract`, no solver:

| Workbook | Time | |
|---|---|---|
| AE_AR_B2B | **16.44 s** | 35 associates, 24 shifts |
| GDI_REAL28 24/7 | **10.33 s** | 29 associates, 24 shifts |

Call counts on GDI:

```
shift_day_demand_fit          632,649 calls   34.1 s cumulative
cyclic_requirement_context 22,775,364 calls   11.8 s
demand_fit_blocked            632,649 calls
```

`shift_day_demand_fit(parsed, day, shift)` is **pure** in `(day, shift.index)` —
it reads only `parsed.active` and the shift's start/duration, both fixed for the
run. There are at most 7 × 24 = **168 distinct results**.

Measured with a memo wrapper, behaviour unchanged:

| Workbook | Before | After | Speedup | Calls → distinct |
|---|---|---|---|---|
| AE_AR_B2B | 16.34 s | **1.82 s** | **9.0×** | 1,005,804 → 168 |
| GDI_REAL28 | 10.20 s | **1.00 s** | **10.2×** | 631,467 → 168 |

**Why it matters beyond speed.** Stage 1 is wall-clock budgeted and already
reports `TRUNCATED_INSUFFICIENT_STAGE1_BUDGET` on every long run I have seen,
including their own Cricut Chat run. 10–16 seconds is search that never happens,
every run. It also compounds the reproducibility problem in section 6: less
search fits, so the outcome depends more on machine load.

**Fix.** `functools.lru_cache` keyed on `(id(parsed), day, shift.index)`, or a
precomputed 7 × N table built once in `parse_input`. Roughly ten lines.
**Complexity** Low · **Priority** High · **Impacts** capacity diagnostics,
Stage 1 eligibility, preflight.

---

## 6. Data integrity and reproducibility

**R-1 — the same input can produce two different verdicts.** Same workbook
(sha256 `08df02dc…`), same seed 9000, same 2400 s budget, same worker count:

| | run 1 | run 2 |
|---|---|---|
| status | FALLBACK_TO_QUICK | FAIL_BREAKS_REQUIRE_EXPLICIT_EXCEPTION |
| production_eligible | **TRUE** | **FALSE** |
| schedule | 257/231 target | none produced |

Both report `stage1_profiles_attempted: 2` of 15. The search is wall-clock
bounded, so machine load changes how much search fits, which changes the
candidate pool, which changes the outcome. The project documents a 6-interval
noise band; this is a shippable schedule versus no schedule.

**Consequence for this audit and for theirs:** no single run proves a scenario
passes or fails. Decisive scenarios must be run twice. P-1 partially mitigates it
by returning 10–16 s of budget.

**R-2 — the artifact contradicts its own validator.** Their Cricut Chat run
records `production_eligible TRUE` and `PASS_WITH_QUALITY_WARNINGS` in the engine
metrics while `INDEPENDENT_VALIDATION.json` says `FAIL` (1 hard failure,
`NEXT_SUNDAY_CARRY_OUT`, 5 floor gaps). The runner correctly returned 4 and
blocked publication — the chain worked. But anyone reading the workbook rather
than the run status draws the opposite conclusion.

---

## 7. Risk register

| ID | Issue | Sev | Prob | Business impact | Effort |
|---|---|---|---|---|---|
| A-1 | "No breaks" silently becomes 60 min of breaks | **Critical** | Med | Roster sized to the wrong contract; headcount wrong; no audit trail | Low |
| — | No exact-build run exists on RC4 | **Critical** | Certain | Release decision rests on zero solver evidence | Hours (runs) |
| A-2 | Invalid `Interval Minutes` silently becomes 60 | High | Med | Every coverage percentage computed at the wrong granularity | Low |
| A-4 | 45 of 98 parameters unreachable from the workbook | High | Certain | Client cannot configure or audit most engine behaviour; 2 gates unset | Med |
| P-1 | Pre-solver path 9–10× slower than needed | High | Certain | 10–16 s of Stage 1 search lost per run; worsens R-1 | Low |
| R-1 | Same input, same seed, different verdict | High | Certain | No single run is evidence | Med |
| A-3 | All-days aliases unreachable; natural spellings hard-fail | Med | Med | Blocked runs with no usable message | Low |
| A-5 | Live Voice workbook missing 4 sheets | Med | Med | Cannot switch granularity; silently reverts (with A-2) | Low |
| A-6 | Dropdown coverage 7–67 across workbooks | Med | Certain | Free-text enums make A-2/A-3 reachable | Med |
| A-7 | `language_rules_at` fails open on bad day index | Med | Low | Latent: a future caller silently loses all language rules | Low |
| A-8 | 21,320-line module, 3,465-line `run_case` | Med | Certain | Defects cannot be isolated; guards are text assertions | High |
| R-2 | Artifact metrics contradict the validator | Med | Med | Wrong conclusion from reading the workbook | Low |
| A-9 | Validator not independent of the engine | Low | Certain | Cannot catch a contract misreading | High |
| A-10 | `VERSION` says RC2 in the RC4 engine | Low | Certain | Artifacts misidentify their own build | Trivial |
| A-11 | Manifest claims `production_ready` with warnings open | Low | Med | Warning review skipped | Trivial |

**Carried forward, frozen by your instruction:** F1 (selector guard collapses —
accepts 1/10, 1/25, **0/50**, **0/100** on random pools; every RC4 result is
selected through this path) and F2 (whole-shift language window — 3 of 24 legal
shift starts on Voice).

---

## 8. Roadmap

**A. Critical — before any further solver time**
1. A-1 break-segment contract: reject invalid counts/durations, honour zero.
2. A-2 `Interval Minutes`: fail on out-of-set values instead of inferring.
3. P-1 memoise `shift_day_demand_fit` — returns 10–16 s of budget per run.

**B. High value**
4. A-4 add the 45 missing parameters to the template, starting with the three
   gate thresholds.
5. A-3 fix `norm()` collapse; add the Coverage Days dropdown.
6. R-1 characterise reproducibility: one scenario, twice, idle machine.
7. A-6 bring every workbook to the same validation set.

**C. Performance**
8. Profile the solver path itself (unmeasured this pass — P-1 covers only
   pre-solver).
9. `cyclic_requirement_context` at 22.8 M calls deserves its own look even after
   memoisation.

**D. Future**
10. A-8 split the engine at its natural seams (parser / Stage 1 / Stage 2 /
    metrics / writer) so guards can be behavioural rather than textual.
11. A-9 reimplement the validator against the workbook, not the engine module.
12. One canonical language evaluator — A-3, A-7 and F5 are all symptoms of its
    absence.

---

## 9. Change implementation plan

Per the brief, for the three critical items:

### A-1 break segments
- **Current** invalid or zero break configuration is silently replaced with 15/30/15.
- **Root cause** `_parse_break_segments` coerces rather than validates; the empty
  case is backfilled with a hard-coded default.
- **Solution** emit `HARD_INVALID_BREAK_CONTRACT` for out-of-set durations and
  negative counts; return an empty tuple when zero breaks are configured.
- **Implementation risk** workbooks relying on the backfill would begin failing.
  Mitigate by running the preflight matrix across all 10 workbooks first — if any
  depends on the default, that is itself a finding.
- **Testing** unit tests per row of the A-1 table; preflight matrix on all
  workbooks; one before-breaks run to confirm zero-break contracts solve.
- **Regression impact** break stage, headcount reporting, Gate 5. Contract hash
  changes only for workbooks that were being silently rewritten.

### A-2 interval minutes
- **Current** out-of-set values fall through to inference and yield 60.
- **Root cause** `if instructed in {15,30,60}` with no else-branch for a value
  that was supplied but invalid; inference cannot distinguish "absent" from "wrong".
- **Solution** distinguish absent (infer, as today) from supplied-and-invalid
  (`HARD_INVALID_INTERVAL_MINUTES`).
- **Implementation risk** none expected; all 10 workbooks supply 15, 30, 60 or nothing.
- **Testing** the A-2 table as unit tests; preflight matrix.
- **Regression impact** none on valid workbooks; contract hashes unchanged.

### P-1 memoisation
- **Current** 632,649 calls returning 168 distinct results.
- **Root cause** a pure function called inside three nested loops.
- **Solution** cache keyed on `(day, shift.index)`, invalidated per `parsed`.
- **Implementation risk** stale cache if `parsed.active` were mutated after
  parse. Verify it is not; key on `id(parsed)` if unsure.
- **Testing** assert identical `capacity_diagnostics` output before and after
  across all 10 workbooks — byte-for-byte, since this must not change behaviour.
- **Regression impact** none intended; it is the one change that must be provably
  inert.

---

## 10. Testing and regression strategy

**Offline, minutes, before any solver time**
1. Unit-pin every row of the A-1 and A-2 tables.
2. Preflight matrix across all 10 workbooks, before and after each fix — any
   status change is a finding.
3. Byte-comparison of `capacity_diagnostics` output before/after P-1.
4. Re-run the 429-test gate.

**Solver, on the RC4 engine, each scenario twice**
5. **Cricut Chat** — its one hard failure is `NEXT_SUNDAY_CARRY_OUT`, which is
   exactly what the F3 fix targets. Directed test, input and prior result already
   exist. Highest value per hour.
6. **NMG** — was killed at rc=−9; re-run with lower workers and memory headroom.
7. **NMG_EN_PRODUCTION** QUICK/FULL for a zero-return-code sealed package,
   exercising the F4 fix.
8. **A genuine 11H/3OFF fixture** plus the 11H-prohibited negative. Still the only
   wholly untested rule family — the old SAKS artifact was 9H/2OFF with 11H
   disabled.

---

## 11. Prioritised action plan

| # | Action | Effort | Unblocks |
|---|---|---|---|
| 1 | A-1, A-2, P-1 | ~half a day | Trustworthy contract + 10–16 s/run back |
| 2 | Re-run gate + preflight matrix | minutes | Confirms 1 is inert where it must be |
| 3 | Cricut Chat ×2 on RC4 | ~4 h wall | First exact-build evidence; directed F3 test |
| 4 | NMG ×2 on RC4 | ~4 h wall | Second scenario; resolves the rc=−9 kill |
| 5 | A-3, A-4, A-6 | ~1 day | Contract expressible and enforceable |
| 6 | R-1 characterisation | ~2 h | Makes every later result interpretable |
| 7 | Unfreeze F1 | ~half a day | Every result above is selected through it |

Keep RC9.1 as the operational baseline until items 1–4 are complete.
