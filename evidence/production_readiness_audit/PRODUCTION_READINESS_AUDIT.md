# Production-readiness audit — RC9.2.2 WFM scheduling engine

Audited code: commit `373a5db`, engine sha256 `85a87258…`, release `L6.3.2.8-RC9.2.2-PRODUCTION-HARDENED-RC6`.
Date: 2026-10-03.
Method:
- Read the engine, runner, validator and portfolio code against the documentation.
- Wrote a clean-room checker with no engine code and ran it on 28 final schedules.
- Ran 21 parser probes and 14 solver scenarios (16 runs) through the production runner.
- Measured model-build scaling.
- Compared against the RC5 paired-seed experiment.

All evidence is in this folder; `WORKING_NOTES.md` is the running log.

> **Status update — Phase A done (2026-10-03, engine sha256 `e5afd99d…`).**
> - **Fixed:** F-01, F-02, F-03 and F-04. F-09 and F-15 are fixed except the instruction-row values that belong to F-11.
> - **Effect on the scenarios** (`phase_a/PHASE_A_RESULT.md`):
>   - S01, S06, S07, S08 and S12 now publish (exit 0).
>   - S14 is refused in 1 s, naming the person.
>   - S02 and S03 are blocked only by their real coverage-gate failure.
> - **Good inputs are unaffected:** all 110 repository workbooks parse to identical contracts and parsed facts.
> - **Gate:** 1,315 tests, PASS.
> - **Still open, Phase B:** F-05, F-06, F-07, F-08, F-10, F-11, F-12 and below.

> **Status update — Phase B done (2026-10-03, engine sha256 `38f494d9…`).**
> - **Fixed:** F-05, F-08, F-10, F-14 and F-16. F-11, F-12 and F-13 are fixed except one sub-item each, named in their headings. F-19 is mitigated: the clean-room checker is now a release gate.
> - **Effect on the scenarios** (`phase_b/PHASE_B_RESULT.md`):
>   - S10 is refused in 1 s, naming Agent A and each day.
>   - S05 names the conflicting rule family (language).
>   - S11 now passes the contract it was wrongly refused under; it stops at break placement on a real lone-Spanish-coverage window (Phase C).
>   - S09, S11 and S13 keep the engine's diagnosis instead of "engine output problem".
>   - S01, S06 and S08 publish, with the clean-room gate PASS and the alternative exports validated PASS.
> - **A defect found on the way:** the validator could never pass an alternative export, because it did not recognise their artifact type. Fixed.
> - **Good inputs are unaffected:** all 111 repository workbooks parse identically under the Phase A and Phase B engines (contract result, facts, and the language rules in force each quarter).
> - **Gate:** 1,349 tests, PASS.
> - **Still open:**
>   - Phase C: F-06, F-07, F-20.
>   - The F-11 range clamps.
>   - The joint model's split constraint (that model is off in production).
>   - P3 items.

> **Status update — Phase C done (2026-10-04, engine sha256 `34964381…`).**
> - **Fixed:** F-06 and F-07. F-20 is fixed as a capability: the business still has to state its long-shift break rule. F-28 is closed as a per-program option, validated by a five-program A/B.
> - **F-06:** a week with no schedule that meets every hard rule now gets a non-releasable **shortfall schedule**. It meets every person rule, and every missed coverage minimum is listed on a Shortfalls sheet and confirmed by the independent validator and the clean-room checker (`phase_c/PHASE_C_RESULT.md`):
>   - S04: Sun 03:00–03:45 only;
>   - S05: 64 Spanish quarters;
>   - S09: 9 quarters;
>   - S11: 1 Spanish quarter;
>   - S13: 4 quarters.
>
>   Input errors (S10, S14) are still refused, and the runner never exits 0 on a shortfall schedule.
> - **New findings:**
>   - **F-33:** OR-Tools corrupts Stage 2's shared balance expressions. It is fixed for the shortfall pass and **open for normal runs**: the pre-registered A/B of the fix did not pass.
>   - **F-34:** the Stage-1 window ignored the configured slice. Fixed; identical at the default.
>   - **F-35:** the shift-consistency polish was never published. The engine measured the polished schedule and wrote the original one, and a one-hour polish move could block a valid schedule at the parity gate (found in the C4 A/B, Voice seed 9000). Fixed by business decision: the selected schedule stays exactly as before, and the engine refuses to measure one schedule and publish another. The polished week ships beside it as `MORE_CONSISTENT_CANDIDATE`, approved only if the independent validator finds its coverage no worse.
> - **F-21 (C3):** the AE_IT Stage-1 shape test (10 valid runs) reads **UNRESOLVED** under its pre-registered rule.
>   - A 240 s Stage-1 slice gives +1.4 floor and +2.0 target on average (88.2 / 73.8 against 86.8 / 71.8), but not the +2 / ≥ 90 the rule required.
>   - It is available as a per-workbook option. No default changes, and F-21 stays open.
>   - Before breaks, S240 reaches RC5's floor (91), so the rest of the gap sits in break placement (F-33).
> - **Good inputs are unaffected:**
>   - all 111 repository workbooks parse identically;
>   - the Stage-1 and Stage-2 models of every packaged and real-run workbook are constraint-for-constraint identical to Phase B;
>   - the real Voice run gives the same 248 / 264.
> - **Per-program coverage measure:** each program can choose Interval Count or Volume Weighted, by a workbook dropdown or a Colab/runner override. Default runs are unchanged; models are identical back to Phase A (45 Stage-1 builds and 51 Stage-2 models).
> - **Volume Weighted runs end to end:** S01 and the real Voice workbook pass validator, parity and clean-room. Its impact on five programs is measured by a pre-registered A/B (`phase_c/C4_AB_RULE.txt`).
> - **Gate:** 1,395 tests, PASS.
> - **Still open:**
>   - F-33 for normal runs;
>   - Volume Weighted as a default (needs the five-case A/B and a business decision);
>   - the F-11 range clamps;
>   - the joint model's split constraint;
>   - P3 items.

## A. Executive summary

**Verdict: not ready for unsupervised production.** It is usable today only for the packaged workbooks and their layouts, with a person reviewing every run. The schedules it does publish are trustworthy against the contract it parsed. The problems are on both sides of that:
- it can parse the wrong contract without saying so;
- it refuses or blocks far more weeks than it should.

**What holds up under skeptical checking:**
1. **Published schedules are correct for the parsed contract.** A checker that shares no code with the engine found 0 rule violations in 28 final schedules (20 real runs, 8 synthetic). It also matched the engine and the validator exactly on all 15 coverage metrics compared, including overnight shifts, previous-Saturday carry-in, 24/7 week-boundary spill and ALL_ROWS language hours.
2. **The release path fails closed.** In 16 adversarial runs, no hard-rule violation reached a publishable state. The identity seal also caught an engine file changed mid-run.
3. **FINAL is better than RC5 where it was measured:** +24 summed after-break target intervals (CI +15.8 to +33.2), 0 vs 7 parity failures, and far fewer break-concurrency violations. AE_IT floor is −4.

**What does not hold up:**

| # | Severity | Finding |
|---|---|---|
| F-01 | **P0** | Duplicate rows on Preference/Fixed sheets silently overwrite each other. Shown end to end: an associate was scheduled on approved leave, and every rule check passed it. |
| F-02 | **P0** | One associate with 6–7 leave days makes the whole week unschedulable, and the message does not name the cause. |
| F-03 | P1 | Engine and validator define two concurrency metrics differently, so the parity gate blocks valid schedules (S01, S02, S03, S14). |
| F-04 | P1 | The strict quality report turns WARN-level findings into a release block unless the workbook sets the coverage gate to `warn`. A 100 %-coverage valid schedule was blocked (S08, S12). |
| F-05 | P1 | Overnight language rules with Coverage Days are enforced on the wrong day: a Mon–Fri 18:00–05:00 minimum also binds Mon 00:00–05:00. Every component shares this function, so nothing detects it. A feasible case was refused (S11). |
| F-06 / F-07 | P1 | No degraded mode. One unreachable quarter, a one-day language shortage, a lone-coverage break, or 24/7 understaffing ends the run with no schedule at all (S04, S05, S09, S13). |
| F-08 | P1 | The run identity omits CLI-enforced settings, so `--resume` can return a schedule made under a different language-window mode. |
| F-09 | P1 | Malformed layouts (date headers, duplicate or missing demand rows, roster gaps) change demand or drop requests silently. 15 of 21 probes showed a silent change. |
| F-10 | P1 | When the hard rules contradict each other, the diagnosis is skipped "for lack of time" with 298 of 300 s unused. |

None of these is caught by the existing 1,286-test gate, which passes on this commit.

**Bottom line for go-live.** Fix Phase A first. It is mostly parser and contract work, and none of it touches the search:
- duplicate and layout refusal;
- the leave/OFF rule;
- one metric definition;
- the quality-report rule.

Then Phase B: overnight attribution, a complete run fingerprint, coverage-split auditing, and the clean-room checker as a release gate. Then the elastic "best achievable" pass (Phase C). Until Phase A lands, every run needs a person to read `BUSINESS_OUTCOME.txt` and the pre-run checker output, and to check that no associate appears twice on any request sheet.

## B. Architecture reconstruction (what the code actually executes)

Reconstructed from `engine/_tools/l632_universal_scheduler.py` (24,793 lines, 337 top-level functions; `run_case` alone is lines 19664–23509), `engine/RUN_UNIVERSAL_PRODUCTION.py` (runner), `engine/tools/independent_validator.py`, `engine/RUN_PORTFOLIO.py` and `engine/production/*`. Line numbers refer to commit `373a5db`.

```
RUN_PORTFOLIO.py (optional: N seeds, picks best fully-validated seed)
  └─ RUN_UNIVERSAL_PRODUCTION.py  (one case)
       1. case lock (RUN_LOCK.json + heartbeat), input snapshot (sha256-pinned copy)
       2. mode/stage from CLI > workbook > default; SMOKE => diagnostics only
       3. subprocess: l632_universal_scheduler.py  (the engine)
       4. phase_c_quality_report.py --strict
       5. production_output_polisher.py --prepare-only  -> production/*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx
       6. subprocess: independent_validator.py on THAT workbook
       7. metric parity gate (engine audit vs validator, 48 canonical fields)
       8. quality report again; seal manifest; package only if everything PASSed
       9. BUSINESS_OUTCOME.txt / UNIVERSAL_RUN_STATUS.json, exit code (0 = publishable)
```

Inside the engine (`run_case`):

| Step | Function(s) | What it does | Notes from the audit |
|---|---|---|---|
| Parse | `parse_input` (2955) | openpyxl, formulas not evaluated. Sheets found by alias; columns mostly by header text. `Instructions` overrides `Engine Defaults`; within a sheet the last row wins. ~150 controls. | Several silent normalisations and positional fallbacks (F-01, F-09, F-11, F-15). |
| Contract | `validate_input_contract` (3813) + `capacity_diagnostics` (10495) | `HARD_*` parser warnings, roster/headcount, shift grid, ratios, fixed-vs-rest, nesting, language capacity, optimistic per-quarter upper bounds. Any failure stops the run before CP-SAT. | Upper-bound proofs are sound but are used to refuse the **whole** run (F-06). |
| Hard probe | `build_skeleton(profile=None)` (6653) | One CP-SAT feasibility solve with every hard family. INFEASIBLE => `run_constraint_isolation` + `run_conflict_refinement` name the families; run ends with no schedule. | No relaxed/degraded schedule is ever produced (F-06, F-07). |
| Stage 1 | `build_skeleton` × ~15 profiles, budget-sliced | Decision vars `x[a,d,s]`, `off`, `leave`, `y[a,s]` (shift variety), `long_mode`. Hard: one of shift/OFF/leave per day; leave pinned; hard OFF; fixed; OFF count (==2/3 strict, >=2 otherwise); adjacent OFF; max different shifts; rest incl. Sat→Sun wrap and previous Saturday; nesting equality; ≥1 person every active quarter; language minimum per quarter; opening minimum; optional hard floor; coverage split; blank-interval ban. Objective: weighted hit indicators for target / floor / severe / 100 % plus deficits, overage, balance, preference distance, quality-shape terms; weights in the 10^5–10^9 range. | Coverage arithmetic uses integer % shrinkage (×100), not the 1e6 scale used elsewhere — search-only, final metrics are recomputed. |
| Stage 2 | `solve_breaks` (8418) on a fixed skeleton | One break pattern per worked cell from `_generic_break_patterns` (enumerated, width-limited 24/44/60/115 per duration, plus edge sentinels), or a no-break exception (only if allowed). Hard: ≥1 person after breaks, opening, language minimum after breaks, coverage split after breaks, concurrency (only if gate = FAIL). Objective mode chosen from 8 weight sets. | Same 15/30/15 break set for every shift length (no 11-hour entitlement, F-20). |
| Repair / recovery | conflict refinement, coordinated repair, zero-exception recovery, logic-based break cuts, post-break repair, target-lock recovery, cap-feasible recovery, safe incumbent, (joint refinement – off in runner), (DNBS – off), shift consistency polish (on) | Each re-solves Stage 1 around an anchor (`max_changes`) or Stage 2 on a new skeleton; accepted only if full validation passes and a no-worse guard holds. | ~12 interacting phases compensating for the decomposition (F-22). |
| Selection | `select_export_candidates` (12264), `_candidate_quality_tuple` (11692) | Lexicographic interval **counts**: after-target, protected tiers, after-floor, quality admissibility, deficit buckets (0.01), boundary, language reserve, overage… Exports RECOMMENDED + MAX_TARGET + MAX_FLOOR + BALANCED. | Every interval weighs the same regardless of volume (design risk F-28). |
| Metrics | `calculate_metrics` (9367) | Per quarter: raw = current-week covering shifts + previous-Saturday carry-in; after = raw − on-break; effective = raw × (1 − shrinkage); interval value = mean of its quarters; hit if pct + 1e-9 ≥ ratio. Saturday spill measured separately as "next Sunday". | Matches the clean-room recomputation exactly on 20 real runs (section I). |
| Self-validation | `validate_schedule` (10974) + `structural_schedule_audit` (10776) | OFF count, max shifts, rest Mon–Sat, fixed cells, zero/language/opening/hard-floor/next-Sunday gaps, blank staffing, shift-start window, demand-fit. | Does **not** re-check hard-OFF or leave *preferences*, Sat→Sun rest wrap, consecutive OFF, nesting, coverage split, break legality (F-13). The independent validator covers all but coverage split. |
| Quality gate | `production_quality_gate` (13213) | FAIL/WARN/OFF per family (coverage defaults FAIL; others WARN). | Coverage Split has a gate-mode row that is parsed but never used (F-12). |
| Export | `write_output_workbook` (13356), `atomic_save_workbook` | Writes to `.publishing.xlsx`, zip-tests, reopens, `os.replace`, re-verifies. | Sound. |

Identity and provenance: `RUN_IDENTITY.json` = sha256 of input file, canonical contract, engine file, seed workbook, run parameters, plus git commit; `run_id` = hash of those. Outputs are sha256-sealed in `PRODUCTION_ARTIFACT_MANIFEST.json`.

Determinism: every CP-SAT solve uses a wall-clock `max_time_in_seconds` with several workers and no `interleave_search`, so the same input, seed and run_id can produce different schedules on different machines or under different load (F-18).

## C. Findings register

Classification key: **Confirmed defect** (reproduced), **Likely defect** (shown by reading and partial reproduction), **Design risk** (works as written, but the design can produce a bad outcome), **Unverified concern**, **Improvement**.
Evidence paths are relative to `evidence/production_readiness_audit/`. `l632` means `engine/_tools/l632_universal_scheduler.py` at `373a5db`.

### P0 — production blockers

#### ✅ FIXED (Phase A) — F-01 · P0 · Confirmed defect — duplicate rows on name-keyed request sheets silently overwrite each other; approved leave can be lost and the schedule still passes validation
- **Where:** `l632 _parse_preferences` (1640–1700), `_parse_fixed_nesting` (1752–1805). The independent validator's raw cross-check and the pre-run checker have the same last-row-wins behaviour.
- **What happens:** when an associate appears twice on the Preference sheet, the later row replaces the earlier one without any message. The Previous-Saturday sheet already refuses duplicates; Preference and Fixed Request do not.
- **Evidence:**
  - Probe P04 (`adversarial/PARSE_PROBES_RESULT.json`): row 1 = Leave Monday, row 2 = blank. The engine read all seven days as blank, and the contract outcome was ACCEPTED.
  - `tools/check_input_workbook.py` on the same workbook: "independent cross-check: PASS … ACCEPTED - ready to run".
  - End-to-end scenario S14 (row 1 = Leave Monday, row 2 = OFF Fri+Sat): see section I.
- **Operational impact:** an associate is rostered on an approved leave day, and the release gate certifies it, because every checker reads the same collapsed row. Splitting one person's requests over two rows (for example leave added later at the bottom of the sheet) is ordinary planner behaviour.
- **Root cause:** `by_name` dict assignment with no duplicate check, copied in three places.
- **Fix:** refuse duplicates (`HARD_PREFERENCE_DUPLICATE`, `HARD_FIXED_REQUEST_DUPLICATE`), exactly as `HARD_PREVIOUS_SATURDAY_DUPLICATE` already does. Do not merge rows.
- **Regression risk:** low. A workbook that relied on duplicates will now be refused, which is the intent.
- **Test:** K-1.

#### ✅ FIXED (Phase A) — F-02 · P0 · Confirmed defect — an associate with 6 or 7 leave days makes the whole roster unschedulable, and the message does not say why
- **Where:** `l632 build_skeleton` 6845–6880: `x+off+leave == 1` per day, leave pinned, and `sum(off) == 2 + long_mode` under Strict OFF.
- **What happens:** a full week of leave leaves no day for the two mandatory OFF days. The hard probe is INFEASIBLE in about 2 s and the run ends with no schedule for anyone.
- **Evidence:**
  - S06 (7 Leave days) → `FAIL_HARD_CONTRACT_INFEASIBLE`, 2.1 s.
  - S07 (6 Leave days) → same status.
  - The business outcome for both reads: "There was not enough time left to find which rules conflict" (see F-10).
  - The contract check and capacity diagnostics both passed this input (P14).
- **Operational impact:** a week in which anyone takes a full week of annual leave produces no schedule. This is routine in every contact centre.
- **Root cause:** the OFF-count rule ("exactly 2 OFF") was written for a working week and never relaxed for days already consumed by leave.
- **Fix:** required OFF = max(0, min(2 + long_mode, 7 − leave_days − fixed_shift_days)). Equivalently, leave days count toward the weekly non-working allowance, with a rule stated by the business. Apply the same formula in `validate_schedule`, the independent validator and the clean-room check.
- **Regression risk:** medium. OFF-count semantics change for associates with ≥ 6 leave days only. Every other associate is unchanged; prove it with the golden-schedule parity test.
- **Test:** K-18, scenarios S06 and S07.

### P1 — critical

#### ✅ FIXED (Phase A) — F-03 · P1 · Confirmed defect — the metric-parity gate blocks valid schedules because two metrics are defined differently in the engine and the validator
- **Where:** `independent_validator.py` 1094–1102 counts break concurrency (and its ratio) over every quarter, including blank-demand intervals. `l632 calculate_metrics` counts only active intervals plus the next-Sunday horizon. Runner `apply_metric_parity_gate` fails the release on any difference.
- **Evidence:**
  - S01 baseline: clean-room 0 violations, all 15 coverage metrics identical, yet `FAIL_METRIC_PARITY` on `max_concurrent_break_ratio_observed`, engine 0.333 vs validator 0.5.
  - S02: 0.25 vs 0.333.
  - S03: `break_concurrency_violation_count` 0 vs 7, and the ratio 0.5 vs 1.0.
  - Every synthetic run that produced a schedule with day-only demand was blocked.
  - The packaged real workbooks did not hit it (F-03 experiment: 36/36 parity PASS), so the trigger depends on the input. It needs shifts running into blank-demand hours with breaks there.
- **Operational impact:** a correct schedule cannot be released. The operator sees "engine and evaluator disagree", which reads as a correctness problem when it is a definitional one.
- **Root cause:** two hand-written implementations of the same metric name, compared field by field.
- **Fix:** pick one definition. Concurrency matters where people are on the floor, so the validator's all-quarter version is arguably right. Implement it once (shared metric spec plus a golden test), and treat diagnostic-only fields as report-only in the parity gate.
- **Regression risk:** low. The metric only changes.
- **Test:** K-14.

#### ✅ FIXED (Phase A) — F-04 · P1 · Confirmed defect — WARN-level quality findings block release on any workbook that leaves the coverage gate at its default
- **Where:** `engine/production/phase_c_quality_report.py` 442: `if args.strict and gate.mode == "fail" and gate.status != "PASS"`.
  - `gate.mode` is the coverage gate's mode; its engine default is `fail` when the workbook has no `Production Quality Gate Mode` row.
  - `gate.status` aggregates every family, including the ones declared WARN (overage cap, employee fairness, next-Sunday balance).
- **Evidence:**
  - S08 (24/7, 14 agents) scored 168/168 after-break target, validator PASS, parity PASS and clean-room exact, yet the runner returned rc 2 with `FAIL_RELEASE_GATE`, blocking on `mandatory_production_quality_gate_not_pass`.
  - The real Voice and Chat runs pass only because their workbooks set the coverage gate to `warn` (gate mode shown in their audits).
- **Operational impact:** a new or rebuilt workbook gets no publishable schedule whenever any WARN-level debt exists. That is nearly always for overstaffed or uneven rosters. The outcome text then lists the warnings as "Main blockers".
- **Root cause:** a strict check written against the aggregate status instead of the families that are actually in FAIL mode.
- **Fix:** block only on `failures` (families in FAIL mode with issues), i.e. `gate_results[g] == "FAIL"`. Keep WARN visible.
- **Regression risk:** low.
- **Test:** S08 must exit 0, plus a unit test on the quality report.

#### ✅ FIXED (Phase B) — F-05 · P1 · Confirmed defect — overnight language rules with Coverage Days are enforced on the wrong day
- **Where:** `l632 language_rules_at.applies` (5122–5158), shared by Stage 1, Stage 2, metrics, capacity diagnostics and the independent validator.
- **What happens:** a rule "Mon-Fri 18:00–05:00" is in force on Mon 00:00–05:00 (Sunday night, not requested) as well as on Tue..Sat 00:00–05:00. Morning quarters on a listed day are accepted without checking that the window opened on that day.
- **Evidence:**
  - Probe P21 shows Mon 00:00–04:00 in force.
  - Scenario S11 (feasible under the business meaning) was refused: `SKILL_WINDOW_PAID_CAPACITY_PROVABLY_INSUFFICIENT day=Mon required_minutes=660`. 660 = 300 (Mon 00–05, spurious) + 360 (Mon 18–24). The same row was printed twice.
  - `tools/clean_room_check.py rule_in_force` encodes the business meaning and disagrees.
- **Operational impact:** this is exactly the per-day Spanish window the business uses. It forces a qualified associate onto Sunday night, or refuses the run, or quietly spends qualified hours where none were required. No component catches it, because every component calls the same function.
- **Root cause:** `day in active_days` is accepted before the overnight-tail logic is consulted.
- **Fix:** for overnight windows, minute ≥ start requires `day ∈ days`; minute < end requires `(day−1) ∈ days`. Same-day windows are unchanged.
- **Regression risk:** low for all-days rules (identical answers). Day-specific overnight rules change on the first listed day's early hours, which is the intended correction.
- **Test:** K-11.

#### ✅ FIXED (Phase C: shortfall schedule, `phase_c/PHASE_C_RESULT.md`) — F-06 · P1 · Confirmed (S04/S05/S09/S10/S11) — no degraded mode: one locally impossible hard minimum withholds the whole week's schedule
- **Where:**
  - `l632 capacity_diagnostics` (hard_failures: `ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE`, `LANGUAGE_WINDOW_MAX_CAPACITY_BELOW_MINIMUM`, opening, hard floor).
  - `build_skeleton` hard families: ≥1 person in every active quarter, language minimum, opening minimum, coverage split, next-Sunday floor (F-07).
  - `run_case` 20570–20580: a probe that is not FEASIBLE ends the run.
  - `solve_breaks`: ≥1 person after breaks.
- **Evidence:**

  | scenario | status | time | outcome |
  |---|---|---|---|
  | S04: one 0.5-FTE quarter that no legal shift reaches | FAIL_PRE_SOLVER_CONTRACT | 1 s | the other 83 intervals get nothing |
  | S05: two Spanish agents for a 7×12 h minimum | FAIL_HARD_CONTRACT_INFEASIBLE | 2 s | — |
  | S09: 6 agents, 24/7 | FAIL_TESTED_SKELETON_EXCEPTION_LOWER_BOUND_EXCEEDS_CAP | — | no schedule |
  | S10: fixed requests contradict blank rule | INFEASIBLE | — | — |
  | S11: F-05 | refused | — | — |

  By contrast, demand above capacity (S02, S03) does produce a schedule, because coverage itself is soft.
- **Operational impact:** this is the scenario the request highlighted, a difficult-but-solvable case turned into a total failure. The planner gets nothing to publish and often no named cause (F-10).
- **Root cause:** minimums are modelled only as hard constraints; there is no elastic second pass.
- **Fix:** keep the hard probe as the first pass. On INFEASIBLE or contract-capacity failure, run an elastic pass: each hard minimum gets a non-negative slack with a penalty above every coverage weight, and coverage split and the next-Sunday floor become soft. Publish the result as `HARD_RULE_SHORTFALL_SCHEDULE`, not releasable by default, with every slack listed by day, time and rule. Business decides whether such a schedule may be used.
- **Regression risk:** medium. A new path, but only on inputs that today produce nothing.
- **Test:** K-17.

#### ✅ FIXED (Phase C: measured as coverage quality; the normal model keeps it as a constraint so feasible weeks search as before, and the shortfall pass makes it elastic) — F-07 · P1 · Confirmed (reading + S13) — the next-Sunday floor is hard while the current-week floor is soft
- **Where:**
  - `l632 build_skeleton` 7243 and 7299: `eff*raw >= floor units` per spill quarter and per interval.
  - `calculate_metrics` 10222: `week_boundary_hard_failure_count` includes floor misses.
  - The independent validator `NEXT_SUNDAY_CARRY_OUT` does the same.
- **What happens:** in a 24/7 operation that is short of staff, Saturday-night shifts plus the repeated Sunday must reach the floor in the spill hours, or the schedule is hard-invalid. The same shortfall on this week's Sunday is only a quality warning.
- **Evidence:** S13 (24/7, 10 agents, ~75 % of needed hours): hard probe OPTIMAL, then `FAIL_NO_BREAK_FEASIBLE_CANDIDATE`, no schedule; the named blockers are WEEK_BOUNDARY / ZERO_STAFF (and a mislabelled HARD_FLOOR, though no hard floor is configured) on Sun 00:00–07:45.
- **Operational impact:** understaffed 24/7 weeks get no schedule, even though a best-effort week exists.
- **Fix:** treat the boundary floor like the current-week floor: soft, reported, gated by the coverage quality gate. Keep zero-staffing and language minimums as they are, or under F-06's elastic rule.
- **Regression risk:** low to medium. The boundary metric becomes a warning on cases that were refused before.
- **Test:** S13.

#### ✅ FIXED (Phase B) — F-08 · P1 · Confirmed defect — run identity omits CLI-enforced settings, so a resumed run can return a schedule made under a different rule
- **Where:**
  - `l632 run_case` 20146–20280. `contract_payload` has no language window mode, windows or coverage split; `run_parameters` omits `language_working_window_override` and the polish flag.
  - The comment at 19833 claims the opposite.
- **Evidence:** the canonical contract hash is identical for Cricut_Voice_LANGUAGE_HOURS with the mode at ALL_ROWS and at OFF (computed, `WORKING_NOTES.md`). With the same input file, the same run_id follows, and `--resume` takes the `SAFE_RESUME_COMPLETE` path at 20268.
- **Impact:** a schedule published as "the ALL_ROWS run" may be the OFF run. The audit cannot prove which rule was enforced.
- **Fix:** hash the effective `ParsedInput` after overrides, every field. Add the override flags to `run_parameters`.
- **Regression risk:** none functionally. run_ids change once.
- **Test:** K-13.

#### ✅ FIXED (Phase A; instruction-row values remain under F-11) — F-09 · P1 · Confirmed defects — structural input errors silently change the contract (header fallbacks and demand rows)
Each probe below was ACCEPTED or WARNED by the contract unless stated.

| Probe | Input | What the engine did | Caught later? |
|---|---|---|---|
| P03 | Schedule day headers are dates | positional fallback `name_col+3..` read Notes columns as Sun/Mon. Refused only because the notes were not shift labels. | no |
| P05 | Fixed Request sheet with date headers | **all fixed requests dropped** | validator raw cross-check after the run (rc 4, an hour lost) |
| P08 | duplicate 10:00 demand row, second blank | 21 FTE-hours of demand erased | validator cross-check after the run |
| P09 | 12:00 demand row missing | interval treated as blank (no demand) | **no** |
| P07 | Interval 30 on a 15-minute sheet | :15/:45 rows ignored | only if totals differ |
| P17 | 25 blank roster rows | 5 of 10 associates read | hard only when Count of Associates is filled |
| P02 | Emp ID not in column 2 | ID read from column 2 by position → false `HARD_DUPLICATE_EMPLOYEE_ID` refusal | refusal with wrong reason |

- **Where:** `_parse_roster` 1514–1576, `_parse_preferences`, `_parse_fixed_nesting`, `_parse_requirement_table` 1944–2030.
- **Fix:** header binding or refusal everywhere, never position. Refuse duplicate, missing and off-grid demand rows. Refuse a roster gap or read through it. Run the raw cross-check before the solve, not after.
- **Regression risk:** low. Refusals only on malformed workbooks. Re-run all 7 packaged workbooks to prove none is refused.
- **Tests:** K-2, K-3, K-4, K-9.

#### ✅ FIXED (Phase B) — F-10 · P1 · Confirmed defect — infeasibility diagnosis is skipped although almost the whole budget is unused
- **Where:** `l632 run_case` 20562–20568: `isolation_budget` uses `conflict_refinement_deadline − now`. That is a cumulative phase deadline (20 s at a 300 s budget), not the remaining run time.
- **Evidence:** S05, S06, S07 and S10 ended in about 2 s, with 298 s unused, `constraint_isolation: []`, and `conflict_refinement: SKIPPED_DISABLED_OR_INSUFFICIENT_BUDGET`. The outcome text: "There was not enough time left to find which rules conflict".
- **Impact:** exactly when the planner needs the cause named, they get none. At QUICK 3600 the reserve is larger, so this is worst on short and SMOKE runs.
- **Fix:** when the probe is INFEASIBLE, give the diagnosis the remaining total budget (minus finalization). Add direct pre-checks for the known contradictions: leave + OFF count per associate, fixed shift vs blank rule, fixed vs language window (that one exists).
- **Test:** S06, S07 and S10 must name the associate and rule.

### P2 — important

#### ✅ FIXED (Phase B; the range clamps on concurrency and cap ratios remain) — F-11 · P2 · Confirmed — silent numeric fallbacks and clamps on instruction rows
- About 100 controls go through `to_float(v, default)`, outside `numeric_instruction_specs`, so an unreadable value becomes the default without a word.
- P10: No-break exceptions enabled with Max = 0 becomes **8** (`parse_input` ~3218).
- P11: max different shifts "three" becomes 3; 0 becomes 1, and `INVALID_MAX_SHIFT_VARIETY` can never fire.
- P06: 11 h durations with Use 11H/3OFF = No silently become the 9 h set.
- P19: a duplicate `Target` row: last wins.
- Silent clamps: concurrency ratio [0.05, 0.75]; next-Sunday and whole-week caps.
- **Fix:** one declarative control table (type, range, default, aliases). Refuse unreadable or contradictory values. Refuse duplicate labels with different values. **Test:** K-6, K-7, K-10.

#### ✅ FIXED (Phase B; the joint-refinement model, off in the production runner, still has no split constraint) — F-12 · P2 · Confirmed — Coverage Split is enforced by the model but nowhere audited
- The gate mode row (`warn`/`fail`) is parsed and never read; only `off` has an effect (3048–3078).
- Post-break split gaps are reported in the summary but not in `validate_schedule`, `production_quality_gate` or the independent validator (it has no split check at all).
- A row with an unreadable time or ratio is silently dropped (P12).
- The joint-refinement model (off in the runner, on when the engine CLI is called directly) has no split constraint.
- **Fix:** validator check, gate wiring, refusal of unreadable rows. **Test:** K-8 plus a split scenario.

#### ✅ FIXED (Phase B; break legality is still checked only by the independent validator and the clean-room gate) — F-13 · P2 · Confirmed — the engine's own `validate_schedule` misses several hard families
- Not re-checked: hard-OFF and leave *preferences*, the Sat→Sun rest wrap, consecutive OFF, nesting equality, break legality, coverage split (10974–11041).
- The independent validator covers all of these except coverage split, so release is protected. Internal repair phases that accept candidates on `validate_schedule` alone (consistency polish, DNBS) rely on the model, not on this check.
- **Fix:** make `validate_schedule` call the same rule set as the validator.

#### ✅ FIXED (Phase B) — F-14 · P2 · Confirmed — misleading run outcome texts
- SMOKE (= diagnostics only, runner 1114): the engine prints "Final schedule generated successfully … passed all current release gates", and the wrapper then says "blocked until the engine output problem is corrected".
- S09, a capacity problem, is also described as "engine output problem".
- When a run is not production-eligible, WARN items are listed as "Main blockers" while the real blocker (parity, S01) is missing.
- S11 prints the same blocker row twice.
- **Fix:** derive the headline from the actual blocking reason list. Give SMOKE its own outcome code.

#### ✅ FIXED (Phase A) — F-15 · P2 · Confirmed — invalid or unusual values that drop a rule silently
- P13: language minimum 0.5 or −1 silently removes the rule. Banker's rounding sends 0.5 to 0.
- P18: an invalid previous-Saturday shift ("25:00 - 06:00") is ignored, so there is no carry-in and no Sunday rest check.
- P15: malformed Shift Library labels are skipped without a message.
- **Fix:** refuse. **Test:** K-5, K-8.

#### ✅ FIXED (Phase B) — F-16 · P2 · Confirmed — alternative candidate workbooks are not independently validated
- MAX_TARGET, MAX_FLOOR and BALANCED are written by `write_output_workbook` with engine self-validation only. The validator, parity gate and seal apply only to `production/*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx`.
- My earlier statement in this conversation, that these are "validated schedules too", was wrong in the sense that matters (independent validation). Corrected here.
- **Fix:** validate them, or label them "engine-checked only, not approved".

#### F-17 · P2 · Measured — Python-side model construction dominates large cases
- One Stage-1 model build plus a 1 s solve:

  | roster × interval | build time |
  |---|---|
  | 30 × 60 min | 6.4 s |
  | 120 × 30 min | 51.6 s |
  | 120 × 15 min | 130.8 s |

  Measured under CPU contention; `adversarial/SCALE_PROBE_RESULT.json`.
- Stage 1 rebuilds the model for every profile and repair (about 15 or more per run). `coverage_vars_at_qslot` loops A×7×S for every quarter and every rule.
- **Impact:** at 120 associates on a 15-minute grid, model building alone can consume most of a QUICK budget, before any search.
- **Fix:** precompute, once per run, the coverage index qslot → [(a, d, s)] (and per language group). Build the base model once and clone it, or add the objective per profile.

#### F-18 · P2 · Confirmed — runs are not reproducible
- Every CP-SAT call uses wall-clock `max_time_in_seconds` with several workers and no `interleave_search`.
- The same input, seed and run_id can therefore give different schedules under different load. S01 run three times (same content, seed 9000): 30–37 of 70 cells differ, after-target 83/84/84, parity failed on two and passed on one.
- OR-Tools itself documents non-determinism in parallel search ([or-tools#3590](https://github.com/google/or-tools/issues/3590)). Reproducible parallel search needs interleaved search with fixed batch sizes ([or-tools PR #5423](https://github.com/google/or-tools/pull/5423)).
- **Fix:** add a `--reproducible` mode for audit replays. Record that a run was not reproducible in its identity.

#### ✅ MITIGATED (Phase B: clean-room checker is a release gate) — F-19 · P2 · Design risk — the "independent" validator is not independent of the rules
- It imports the engine's `parse_input` and calls `language_rules_at`, `rest_compatible`, `maximum_concurrent_breaks`, `whole_week_raw_cap` and others.
- F-05 is the proof that a shared defect is invisible to it. F-01's duplicate-row loss passes its raw cross-check as well.
- **Fix:** add the clean-room checker (`tools/clean_room_check.py`, written in this audit, no engine imports) to the release gate. It agreed with the engine on all 20 real runs.

#### ✅ FIXED (Phase C: optional `Break Set For Shifts Of N Hours Or More` rows; the business must state the rule) — F-20 · P2 · Missing capability (stated as a defect only where the business requires it) — breaks are the same for every shift length
- `_parse_break_segments`: one global set (default 15/30/15) applied to 9 h and 11 h shifts alike. See E-5.

#### F-21 · P2 · Regression (known, measured) — AE_IT after-break floor
- AE_IT: −4.0 floor intervals versus RC5 (CI −5.2 to −2.7), traded for +4 target and about 13 fewer concurrency violations per run (`experiments/rc5_vs_final/RESULT.md`).
- The cause is in Stage-1 search; three single-factor causes were refuted (`evidence/aeit_floor_cause/RESULT.md`). Still open.
- Phase C3 (`phase_c/C3_SCORE.json`): with the Stage-1 window sized for its slice (F-34), `Stage 1 Minimum Slice Seconds = 240` gives +1.4 floor and +2.0 target over 5 paired seeds.
  - The pre-registered read is UNRESOLVED (the CAUSE bar was +2 and ≥ 90).
  - S240's before-break floor equals RC5's (91), so part of the gap is Stage-1 shape and the rest is break placement (F-33).

#### F-22 · P2 · Design risk — complexity
- About 12 interacting repair and recovery phases and about 70 module-level feature flags; `run_case` is 3,845 lines. See section F.

### P3 — improvements

| ID | Class | Item |
|---|---|---|
| F-23 | Improvement | Requirements pin only `ortools`; `openpyxl`, `pandas`, `numpy`, `scipy` are `>=`. Installed versions are not recorded in the run identity. |
| F-24 | Confirmed | Run guide is stale: "1236 tests" (gate is 1,286), "RC5 comparison results expected around 3 Oct" (done, INCONCLUSIVE), and no statement that SMOKE is diagnostics-only. |
| F-25 | Confirmed | Runner `--overwrite` refuses a case whose input snapshot differs ("Use a new schedule-id"), contrary to its help text. Fail-safe but confusing. |
| F-26 | Confirmed | Dead or latent code: `parsed.dates` is never read, and holds the first demand row rather than dates. Bundled-fallback inventory points at directories that do not exist. |
| F-27 | Confirmed | `CoverageSplitRule.overlaps` tests only the slot start for a 15-minute span (the defect fixed in `LanguageRule.overlaps`). Harmless on quarter-aligned windows. |
| F-28 ✅ CLOSED as a per-program option (Phase C: `Coverage Objective Weighting` dropdown or run override; five-program A/B verdict CLOSE: 0 wrong results, more requirement covered on 5/5, price MINOR on 4, MAJOR on AE IT; default stays Interval Count) | Design risk | The selector counts intervals at or above a ratio, all equally weighted; volume is ignored and deficit depth only enters through 0.01 buckets. Pool-relative envelopes (anchor+2, +0.05) make the winner depend on which other candidates exist. |
| F-29 | Confirmed | The engine CLI defaults differ from the runner's (joint refinement on in the engine, off in the runner). Direct engine calls behave differently from production. |
| F-30 | Design risk | `separate_off_days = No` accepts a Sat+Sun pair of the same week as consecutive (cyclic assumption). With a different next week, those days are not consecutive. |
| F-31 | Design risk | A Language Setup per-day working window: on a day with no row, that language's associates may start at any hour (documented in the pre-check, surprising to planners). |
| F-32 | Improvement | Stage 1 uses whole-percent shrinkage (×100), while Stage 2 and the joint model use the 1e6 scale. Search-only; final metrics are exact. |
| F-33 (Phase C, **open for normal runs**) | Confirmed defect | OR-Tools 9.15 reduces `k - (k - S)` to `S` itself, and the following `- allowed` mutates `S` in place. Stage 2 reuses one `headcount - breaks` expression per quarter in the whole-week and next-Sunday adjacent-balance terms, so 4–40 balance constraints per real model are corrupted (all 40 saved models; `phase_c/F33_STAGE2_MODEL_DIFF.json`). Soft terms only: no hard rule is affected, and every one is re-checked from the cells. Fixed in the shortfall pass, where the model is wrong without it. For normal runs the pre-registered A/B failed (H1 after-target −5.0; concurrency worse on Voice, Chat, H1; `phase_c/F33_AB_SCORE.json`), so the corrected objective needs re-tuning before it ships. |
| F-35 (Phase C, ✅ FIXED by withholding the polish) | Confirmed defect | `run_case` replaced `selection["recommended"]` with the polished pair, and every audit metric, gate and outcome number came from it, but the workbook writer published `selection["exports"]`, which still held the original pair. No published workbook carried the polish (six runs checked, `phase_c/F35_POLISH_NOT_PUBLISHED.txt`), and its claimed gains (`evidence/shift_consistency/RESULT.md`) were never delivered. When a polish move changed untracked statistics (overage), the audit and the workbook disagreed and parity blocked a valid schedule (C4 A/B, Voice 9000, exit 4). The fix keeps the selected schedule exactly as before and adds `recommended_export_pair`, which refuses to measure one pair and publish another. The polished week is published as its own workbook, `MORE_CONSISTENT_CANDIDATE`, approved only if the validator finds its coverage no worse. |
| F-36 (Phase C, ✅ FIXED) | Confirmed defect | Best-of-seeds (`RUN_PORTFOLIO.py`, used by Colab QUICK/DEEP/OVERNIGHT) ranked seeds by after-break intervals at target whatever the run optimised, so a Volume Weighted program had its final pick across seeds made by interval count. The C4 A/B showed the seed is the largest source of variation, so that pick decides the most. Now, when every seed ran Volume Weighted, seeds rank first by requirement covered at target from the independent validator's interval rows, then as before; Interval Count ranks exactly as before; eligibility is unchanged; the summary names the ranking used. Tests written first (5 of 6 failed before). |
| F-34 (Phase C, ✅ FIXED) | Confirmed defect | The budget planner sized the Stage-1 window from the 45 s constant and ignored `Stage 1 Minimum Slice Seconds`, so a deeper slice ran fewer profiles instead of deeper ones (and the earlier AE_IT slice test could not test its hypothesis). Now `max(45 s, slice)` per profile, capped at 45 % of the run; identical at the default. |

## D. Production readiness assessment

Ratings: **Demonstrated** (evidence in this audit), **Partly demonstrated**, **Not demonstrated**, **Contradicted** (evidence against).

| Dimension | Rating | What the evidence supports |
|---|---|---|
| Correctness of published schedules | **Partly demonstrated** | On 20 real final schedules and 4 synthetic finals, a checker sharing no code with the engine found 0 rule violations and exact agreement on 15 coverage metrics. But that only holds for the contract the parser produced, and F-01/F-09 show the parser can produce the wrong contract without warning. |
| Constraint enforcement | **Partly demonstrated** | Every hard family the model states is enforced and re-checked by the validator, except coverage split (F-12). One family is enforced on the wrong hours (F-05). |
| Schedule quality | **Partly demonstrated** | FINAL beats RC5 on summed after-break target (+24, CI +15.8 to +33.2) and break concurrency, on 6 paired seeds × 5 cases. AE_IT floor is −4 (F-21). Not shown: closeness to optimal (no bounds are proven at production budgets). |
| Coverage optimisation | **Partly demonstrated** | Above-capacity demand degrades gracefully (S02, S03 publish a best-effort schedule). Locally impossible minimums do not (F-06). |
| Break handling | **Partly demonstrated** | Break legality re-verified on every schedule (validator and clean-room). A lone-coverage period with mandatory breaks ends the run (S09). One break set for all durations (F-20). |
| Fairness / balance | **Not demonstrated** | Measured and reported (warnings), not optimised beyond penalties. The consistency polish improves start-time stability (10 of 11 saved schedules). |
| Overage control | **Partly demonstrated** | Penalised and reported. Unavoidable overage from strict 5-day rostering is reported as violations (S01, S08). |
| Input robustness | **Contradicted** | In 15 of 21 probes the engine silently dropped or changed what the workbook said; 2 more were refused only by coincidence or for the wrong reason (section I). |
| Validation reliability | **Partly demonstrated** | Fail-closed in the runner: nothing is published without validator PASS plus parity. The validator shares rules with the engine (F-19) and false-blocks valid schedules (F-03, F-04). |
| Failure handling | **Partly demonstrated** | Atomic writes, identity seal (refused a mid-run engine change), stale-lock recovery, isolated joint solves. Infeasibility diagnosis is skipped on short budgets (F-10). |
| Runtime | **Demonstrated** for the packaged sizes | All measured runs finished inside budget. |
| Scalability | **Not demonstrated** | Model build grows to about 131 s per Stage-1 build at 120 associates × 15 min (F-17). No case above 44 associates was run end to end in this audit. |
| Reproducibility | **Not demonstrated** | Wall-clock-limited parallel search (F-18); determinism result in section I. |
| Observability | **Demonstrated** with gaps | Run identity (input, contract, engine, parameters, git), per-phase budget events, solver telemetry, business outcome text. Gaps: overrides missing from the contract hash (F-08), library versions unrecorded (F-23), misleading headlines (F-14). |
| Maintainability | **Contradicted** | A single 24.8k-line module, a 3.8k-line function, about 70 constant feature flags, about 12 repair phases (F-22). |
| Testing | **Partly demonstrated** | 1,286 gate tests protect selector, metric, identity and parity plumbing, mutation-checked in places. The gate has no adversarial input tests and no end-to-end scenarios with known answers. Every confirmed defect in this audit passes the current gate. |
| Deployment safety | **Partly demonstrated** | sha256-pinned engine, test gate before run, sealed outputs. The docs over-claim ("bad inputs are refused") and are stale (F-24). |

## E. Missing capabilities

Each item says what goes wrong operationally without it. Nothing is listed just because commercial WFM suites have it.

### Required before production

| # | Capability | What goes wrong today |
|---|---|---|
| E-1 | **Degraded "best achievable" mode.** If a hard minimum is infeasible (an uncoverable quarter, a language minimum nobody can staff on one day, a coverage-split shortfall, a hard floor), the run should still produce the best schedule, with the violated minimums turned into penalised slacks and listed per interval. | The whole run ends with no schedule (S04, S05, S11). A planner then has to edit the input blind and rerun for an hour. |
| E-2 | **Strict structural input lint**, refusing rather than guessing: duplicate rows on name-keyed sheets, duplicate or missing demand time rows, unrecognised shift labels, out-of-range minimums, unreadable coverage-split times, day headers that are not Sun..Sat, blank-row gaps in the roster. | Approved leave, fixed requests, demand rows and coverage rules are dropped silently (P04, P05, P08, P09, P12, P13, P17). The resulting schedule passes validation, because the validator reads the same parsed contract. |
| E-3 | **One authoritative metric definition** (a single shared function, or a frozen spec with a cross-implementation test), used by the engine, validator and parity gate. | A valid schedule is blocked from release over a diagnostic ratio defined two ways (S01). |
| E-4 | **Complete run fingerprint.** Every enforced setting, including CLI overrides, belongs in the contract hash, plus the installed library versions. | `--resume` can return a schedule produced under a different language-window mode, and the contract hash cannot show what was enforced. |

### Strongly recommended

| # | Capability | Operational problem it solves |
|---|---|---|
| E-5 | Break entitlement by shift length (e.g. 9 h: 2×15 + 30; 11 h: extra break or longer lunch) | Today every shift length gets the same break set. Labour-law or contract differences for 10–11 h shifts cannot be expressed. |
| E-6 | Reproducible solve mode (`interleave_search` with a deterministic time limit, or a single worker) for audit replays | The same run_id can give a different schedule, so a disputed schedule cannot be regenerated exactly. |
| E-7 | Weekly hours and contract-type limits per associate (part-time, minimum and maximum weekly hours) | Every associate is assumed full time, 5 days × the same duration. A part-timer cannot be modelled. |
| E-8 | Volume-weighted coverage objective option (sum of under-coverage in FTE, or a service-level proxy) beside interval counts | The selector treats a 1 FTE and a 30 FTE interval the same. It can trade a big interval's depth for a small interval's hit. |
| E-9 | A "what changed versus last week" report (associates, demand, contract rows) | Most of the silent-drop defects above would be visible to a planner in seconds. |
| E-10 | Independent validation of every exported workbook (MAX_FLOOR, BALANCED, MAX_TARGET), or not exporting them | These are offered as alternatives but are engine-validated only. |

### Future enhancements

- Multi-week horizon with real next-week carry-out, instead of the cyclic "next Sunday = this Sunday" assumption.
- Intraday activities (training, meetings) as non-break, non-productive blocks.
- Skill proficiency levels and multi-skill routing weights, beyond binary eligibility.
- Fairness across weeks (rotating weekends, nights) using history.
- An API or service wrapper with job queueing, instead of a notebook plus CLI.

## F. Technical debt assessment

| Area | Evidence | Classification | Recommendation |
|---|---|---|---|
| `run_case` is 3,845 lines; the engine is one 24.8k-line file with ~70 RC/PHASE feature flags set to `True` at module level | l632 lines 114–240 | **Should be redesigned** (incrementally) | Split into parse / contract / stage1 / stage2 / repair / select / export modules behind the same CLI. Delete the flags that are constant `True` and never read. |
| Twelve repair and recovery phases around a two-stage decomposition (coordinated repair, zero-exception recovery, logic cuts, post-break repair, target-lock, cap-feasible, safe incumbent, joint refinement, DNBS, break-load feedback, final endgame, consistency polish) | Several are off by default after measurement (joint: 474 audits improved 0; endgame: 9 runs, 0 candidates; DNBS off since F-10) | **Technically correct but overly complicated**; partly **obsolete** | Remove the code paths measured as never helping (joint refinement, final endgame, DNBS) once two releases pass without them. Keep the rest behind one budget scheduler. |
| Two-stage shift→break decomposition, with break feasibility pushed back through cuts and reserves | NIGHT_06 "Stage 1 optimises against breaks", break-load feedback, logic cuts | **Justified** (a joint model was tried three ways and does not scale) but is the root of much of the patching | Keep. Invest in Stage-1 break-awareness (productive-coverage basis is already a profile) rather than more post-hoc repairs. |
| Validator "independence" is partial: it imports the engine's `parse_input` and rule helpers (`language_rules_at`, `rest_compatible`, caps) | `independent_validator.py` 47, 802 | **Questionable** for a release gate | Keep the validator, and add the clean-room checker (this audit, `tools/clean_room_check.py`) to the gate. It caught the overnight-window attribution that both shared paths agree on. |
| Instruction parsing: ~150 controls through `to_float(...default)` with ad-hoc clamps | parse_input 3000–3640 | **Potentially harmful** (silent defaults) | One declarative table: name, aliases, type, range, default, and failure on unreadable. `WORKBOOK_SEARCH_CONTROLS` already does this for 40 controls; extend it to all. |
| Engine CLI defaults differ from runner defaults (joint refinement on vs off, SMOKE = diagnostics) | runner 1102–1146, engine 24730 | **Questionable** | Make the engine defaults equal the production defaults. The runner should only add case paths. |
| Bundled-fallback / champion-registry machinery whose directories do not exist in the package | `bundled_schedule_candidate_inventory` 6521 | **Obsolete / latent risk** | Remove, or keep disabled with a test that the directories are absent. |
| Metric names duplicated as string keys across engine, validator, canonical_metrics, parity gate (48 fields) | parity mismatch S01 | **Should be redesigned** | One metrics module, imported by both, plus a golden-file test per field. |

## G. Regression assessment (versus RC5 and earlier RC9 builds)

| Area | Direction | Evidence |
|---|---|---|
| After-break target coverage | **Better** | +24 summed across real cases; Chat +15.8, AE_IT +4.0; synthetic H1 +20, M2 +6.2 (`experiments/rc5_vs_final/RESULT.md`). |
| Robustness and parity on packaged workbooks | **Better** | FINAL 0 of 36 parity failures; RC5 7 of 36. |
| Break concurrency | **Better** | Violations per run, Chat 10.2 → 0.4, Voice 20.5 → 3.8. |
| AE_IT after-break floor | **Worse** | −4.0 (CI −5.2 to −2.7); cause in Stage-1 search, unresolved. |
| Best before-break target | **Slightly worse** on 3 real cases | 1–3 intervals (B-3 Stage-1 slice; partly explained). |
| Validation strictness | **Stricter, with false blocks** | New parity fields and the strict quality report block valid schedules (F-03, F-04) that RC5's gate would have published. |
| Input handling | **Better than RC5 in many places** | Fail-closed booleans, unknown names, vocabulary, departed associates. Still silent in the places listed in F-01, F-09, F-11, F-15. |
| Language hours | **Restored**, with one new defect | Per-day windows and working-window enforcement came back from RC5. The overnight day attribution is wrong (F-05). |

## H. Performance assessment

| Component | Cost observed | Growth |
|---|---|---|
| Parse | under 0.5 s | linear in sheet size |
| `capacity_diagnostics` | 0.6 s (30×60) to 9.6 s (120×15) | O(Q·A·eligible shifts) |
| Stage-1 model build + 1 s solve | 6.4 s (30×60) → 51.6 s (120×30) → 130.8 s (120×15) | about linear in x-variables × quarters; repeated for every profile and repair |
| Stage-2 break model | not measured separately | patterns per shift (24–115) × worked cells × quarters |
| Memory | AE_AR_B2B single run peaked at 8.2 GB in earlier evidence (joint refinement + finalization), fixed by isolation and by disabling joint refinement | joint models grow fastest; now off and isolated |

**Bottlenecks:**
- Python loops in `coverage_vars_at_qslot` and in `build_skeleton`'s effective-coverage terms, which scan all associates × days × shifts for every quarter (F-17).
- Rebuilding the same base model for each profile.

**Scalability risks:**
- A 15-minute grid or a large roster (≥ 100) spends much of the budget on model construction.
- A long horizon is not supported (7 days fixed).
- Many language rules multiply the per-quarter loops.

## I. Independent validation results

### I-1. The clean-room checker

`tools/clean_room_check.py`, written for this audit, imports neither the engine nor the shipped validator. It re-reads the raw input workbook and the output workbook with openpyxl and re-implements every rule from its business meaning:
- OFF count and shape; rest, including the Sat→Sun wrap and the previous Saturday;
- leave, hard OFF and fixed requests honoured; maximum different shifts; language working window;
- break count, length, containment, alignment, overlap and gap;
- quarter-level coverage with previous-Saturday carry-in and breaks, using the target, floor, 80, 90 and 100 tiers;
- language minimums with the correct overnight day attribution, and zero-staffed quarters;
- duplicate rows on name-keyed sheets.

### I-2. Real final schedules: engine, validator and clean-room agree

28 final schedules: 20 from real runs and 8 synthetic finals from this audit (`clean_room/SUMMARY.json`).

| Group | Schedules | Rule violations (clean-room) | Coverage metrics compared | Mismatches vs engine | Mismatches vs validator |
|---|---|---|---|---|---|
| AE_IT_B2B real runs | 6 | 0 | 15 each | 0 | 0 |
| Cricut Chat | 2 | 0 | 15 | 0 | 0 |
| Cricut Voice (incl. ALL_ROWS language hours) | 7 | 0 | 15 | 0 | 0 |
| SYNTH H1 24/7 overnight | 1 | 0 | 15 | 0 | 0 |
| AR_B2B / FRC week-boundary fixtures | 5 | 0 | 15 | 0 | n/a (no validator file kept) |
| Audit scenarios S01×3, S02, S03, S08, S12 | 7 | 0 | 15 | 0 | 0 |
| Audit scenario S14 (duplicate Preference row) | 1 | **1 (`duplicate_input_row`)** | 15 | 0 | 0 |

The 15 metrics compared are: active intervals, before/after target, before/after floor, before/after 100/90/80, target and floor losses from breaks, language gaps, and zero-staffed quarters.

**What this proves.** For the contract as parsed, the published coverage numbers are arithmetically right, and none of 28 schedules breaks a re-derived hard rule.

**What it does not prove:**
- That the parsed contract is what the workbook said (section I-3).
- Anything about overnight day-specific language minimums, coverage split, hard floor, nesting or no-break exceptions. None of these 28 schedules exercises them.

### I-3. Parser and contract probes (`adversarial/PARSE_PROBES_RESULT.json`)

| Probe | Input | Engine outcome | Verdict |
|---|---|---|---|
| P01 | Clean small workbook | accepted (break-window default warning) | correct |
| P02 | Schedule columns re-ordered | refused: false duplicate employee ID (ID read by position) | **wrong reason** |
| P03 | Day headers are dates | positional fallback read the wrong columns; refused only because they held text | **refused by coincidence** |
| P04 | Same associate twice on Preference | Leave on Monday lost, accepted | **silent change** (F-01) |
| P05 | Fixed Request with date headers | all fixed requests dropped, accepted | **silent drop** (F-09) |
| P06 | 11 h durations with Use 11H/3OFF = No | switched to 9 h; refused for an unrelated coverage reason | **silent change** (F-11) |
| P07 | Interval 30 on a 15-minute sheet | :15/:45 rows ignored | **silent drop** |
| P08 | Duplicate demand time row | 21 FTE-hours erased | **silent change** |
| P09 | Missing demand time row | read as no demand | **silent change** |
| P10 | No-break enabled, Max = 0 | Max became 8 | **silent change** |
| P11 | Max shifts "three" / 0 | 3 / 1 | **silent change** |
| P12 | Coverage Split start "9am" | rule dropped | **silent drop** |
| P13 | Language minimum 0.5 / −1 | rule dropped | **silent drop** |
| P14 | 7 Leave days | accepted (then infeasible at solve, S06) | contract misses it |
| P15 | Malformed shift labels | skipped without a message | **silent drop** |
| P16 | Demand cell "abc" | refused, cell named | correct |
| P17 | 25 blank rows in roster | 5 of 10 associates read | **silent drop** (hard only if headcount is set) |
| P18 | Previous Saturday "25:00 - 06:00" | ignored | **silent drop** |
| P19 | Target row twice | last wins; refused only because floor > target | **silent change** |
| P20 | Language window "Enforce" | refused, value named | correct |
| P21 | Mon-Fri 18:00–05:00 Spanish minimum | also enforced Mon 00:00–05:00 | **wrong rule** (F-05) |

The shipped pre-run checker (`tools/check_input_workbook.py`) runs the validator's raw cross-check. It catches P05 and P08, but passes P04, P13 and P18.

### I-4. Solver scenarios through the production runner (`adversarial/scenario_results/`)

QUICK mode, 300 s, 2 workers, seed 9000. "Schedule?" means a workbook was written to `production/`; "Exit 0" means approved for publication.

| Scenario | What it tests | Engine status | Validator | Schedule? | Exit 0? | Clean-room |
|---|---|---|---|---|---|---|
| S01 baseline (×3) | sanity, determinism | PASS_WITH_QUALITY_WARNINGS | FAIL_METRIC_PARITY ×2, PASS ×1 | yes | **no** (F-03 / F-04) | 0 violations, exact |
| S02 demand +10 % | slight under-capacity | FAIL_PRODUCTION_QUALITY_GATE | FAIL_METRIC_PARITY | yes (76/84) | no | 0, exact |
| S03 demand ×3 | massive under-capacity | FAIL_PRODUCTION_QUALITY_GATE | FAIL_METRIC_PARITY | yes (0/84 target) | no | 0, exact |
| S04 one unreachable quarter | partial impossibility | FAIL_PRE_SOLVER_CONTRACT (1 s) | – | **no** | no | – |
| S05 Spanish shortage | language staffing short | FAIL_HARD_CONTRACT_INFEASIBLE (2 s) | – | **no** | no | – |
| S06 7 days Leave | routine leave week | FAIL_HARD_CONTRACT_INFEASIBLE (2 s) | – | **no** | no | – |
| S07 6 days Leave | heavy leave | FAIL_HARD_CONTRACT_INFEASIBLE (2 s) | – | **no** | no | – |
| S08 24/7 + week boundary | overnight, carry-in, spill | PASS_WITH_QUALITY_WARNINGS | PASS, parity PASS | yes (168/168) | **no** (F-04) | 0, exact |
| S09 6 agents 24/7 | lone-coverage breaks | FAIL_TESTED_SKELETON_EXCEPTION_LOWER_BOUND_EXCEEDS_CAP | – | **no** | no | – |
| S10 fixed vs blank rule | contradictory requests | FAIL_HARD_CONTRACT_INFEASIBLE (2 s) | – | no (correct) | no | – |
| S11 overnight day window | per-day Spanish 18–05 | FAIL_PRE_SOLVER_CONTRACT (wrong rule) | – | **no** | no | – |
| S12 overlapping skills | bilingual eligibility | PASS_WITH_QUALITY_WARNINGS | PASS, parity PASS | yes (84/84) | **no** (F-04) | 0, exact |
| S13 24/7 understaffed | 24/7 shortage | FAIL_NO_BREAK_FEASIBLE_CANDIDATE | – | **no** | no | – |
| S14 duplicate Preference row | silent leave loss | PASS_WITH_QUALITY_WARNINGS | rule checks PASS; FAIL_METRIC_PARITY | yes; **Agent A works Mon 11:00–20:00 on approved Leave** | no (only because of F-03) | flags `duplicate_input_row` |

**Determinism.** Three S01 runs with identical content and seed produced three different schedules:
- 30–37 of 70 cells differ between any two;
- after-target 83 / 84 / 84;
- parity failed on two of the three and passed on one.

**Reading these results.**
- No scenario produced a hard-rule violation that reached release. The release path fails closed.
- 0 of 16 runs could be published:
  - every completed schedule was blocked by a false parity mismatch (F-03) or the strict quality report (F-04), apart from S02/S03, whose coverage gate legitimately failed;
  - every hard-minimum difficulty ended with no schedule (F-02, F-05, F-06, F-07).
- The packaged real workbooks avoid F-04 only because they set the coverage gate mode to `warn`.

## J. Recommended remediation plan

Rules for every step:
- Each fix lands with its failing-first test (section K).
- Each fix gets a before/after replay on the 20 golden schedules: clean-room, validator and engine must still agree.
- Each fix gets a paired-seed A/B on the 7 packaged workbooks whenever it can change search or selection.
- No step changes demand, roster or baseline workbooks.

### Phase A — production blockers (do first; mostly parser and contract, no search change)

| Step | Fixes | Change | Depends on | Risk |
|---|---|---|---|---|
| A1 | F-01 | Refuse duplicate names on Preference and Fixed Request. Apply the same rule in the validator cross-check and in the clean-room check. | – | Low |
| A2 | F-02 | OFF requirement accounts for leave and fixed days (formula in F-02), in the model, `validate_schedule`, the validator and the clean-room check. Add a pre-check naming any associate whose requests leave too few days. | – | Medium: run golden replay plus a 7-workbook A/B |
| A3 | F-09, F-15 | Header-only binding; refuse non-day headers, duplicate/missing/off-grid demand rows, roster gaps, malformed shift labels, invalid previous-Saturday shifts and invalid language minimums. | A1 (shared helpers) | Low: confirm the 7 packaged workbooks are all still accepted |
| A4 | F-03 | One definition for concurrency metrics, imported by engine and validator. The parity gate compares decision metrics strictly and diagnostic metrics as report-only. | – | Low |
| A5 | F-04 | Quality report blocks only on families in FAIL mode that have issues. | – | Low |

After Phase A, rerun the parse probes and scenarios S01–S14. Expected: every "silently changed" probe becomes "refused", and S01, S06, S07 and S08 are published.

### Phase B — correctness and validation

| Step | Fixes | Change | Depends on |
|---|---|---|---|
| B1 | F-05 | Overnight day-specific rule attribution. One function, used everywhere, with K-11. | – |
| B2 | F-08 | Contract hash = the effective parsed contract after overrides, plus override flags in `run_parameters`. | – |
| B3 | F-12, F-13 | Coverage-split checks in validator, gate and `validate_schedule`. `validate_schedule` reuses the validator's rule list. | A4 |
| B4 | F-19 | `tools/clean_room_check.py` becomes a release gate step (runner, after the validator), extended to coverage split and to next-Sunday metrics. | B1, B3 |
| B5 | F-10, F-14 | Diagnosis gets the unused budget. Direct contradiction pre-checks. Outcome headlines derived from the real blocking reasons; a SMOKE-specific outcome. | A2 |
| B6 | F-16 | Validate the alternative exports, or label them "not approved". | B4 |
| B7 | F-11 | Declarative control table for every instruction row. | A3 |

### Phase C — schedule quality and graceful degradation

| Step | Fixes | Change | Depends on |
|---|---|---|---|
| C1 ✅ | F-06, F-07 | Elastic second pass when the hard probe fails or the contract's capacity proofs fail. Next-Sunday floor becomes soft. Published as a non-releasable shortfall schedule with every slack listed. | A2, B5 |
| C2 ✅ | F-20 | Break entitlement by shift duration. Needs a business statement of the rule first. | – |
| C3 | F-21 | AE_IT floor: the stage-bisection A/B already designed (RC5 vs FINAL, one block at a time, ≥ 5 seeds). | – |
| C4 ✅ (per-program option; A/B CLOSE) | F-28 | Optional volume-weighted objective, behind a workbook switch, measured by pre-registered A/B before it can become the default. | – |

### Phase D — performance

| Step | Fixes | Change |
|---|---|---|
| D1 | F-17 | Precomputed coverage index (qslot → variables) and language/split eligibility index, built once per run. Expect build time to fall from O(Q·A·D·S) per profile to O(A·D·S·dur). Verify the model is identical with a model-proto hash before and after. |
| D2 | F-17 | Reuse one base model per run; profiles only change the objective. |
| D3 | F-18 | `--reproducible` mode (interleaved search, fixed batch size, deterministic limits) for replays and audits. |

### Phase E — architecture and maintainability

| Step | Fixes | Change |
|---|---|---|
| E1 | F-22 | Split `l632` into modules: parse, contract, model_stage1, model_stage2, repair, select, export, metrics. No behaviour change, proved by the golden replay. |
| E2 | F-22, F-26, F-29 | Delete constant-`True` flags, measured-dead phases (joint refinement, final endgame, DNBS) and bundled-fallback code. Align engine defaults with the runner. |
| E3 | F-23, F-24, F-25 | Pin dependencies and record versions in the run identity. Fix the guide (test count, SMOKE, validated exports, language-window semantics). Make `--overwrite` do what it says or rename it. |

### Phase F — future enhancements

Part-time and contract hours (E-7), multi-week horizon, intraday activities, proficiency levels, cross-week fairness, a job service.

### Dependencies at a glance

```
A1 ─┬─ A3 ── B7
    └────────────── B4 ── B6
A2 ───────── B5 ── C1
A4 ── B3 ── B4
B1 ── B4
A5, B2, C2, C3, D*, E* independent
```

## K. Required regression suite (keep permanently, before every release)

The existing gate (49 suites, 1,286 tests) mostly protects selector, metric, identity and parity plumbing. It has almost no adversarial input tests and no end-to-end scenario with a known answer. Add the following. Each must fail on today's code where the finding is open, and pass after the fix.

**Input contract (seconds, run in the gate)** — the `adversarial/parse_probes.py` set turned into assertions:
1. Duplicate associate on Preference, Fixed Request and Previous-Saturday sheets → refused.
2. Day header row that is not Sun..Sat (dates, merged cells) on Schedule, Preference or Fixed Request → refused, never a positional guess.
3. Schedule columns in any order → employee ID, name and language bound by header.
4. Duplicate demand time row, missing demand time row, rows off the interval grid → refused.
5. Shift Library label that does not parse, or a duration outside the allowed set → reported by label.
6. Contradictory switches (11 h durations with Use 11H/3OFF = No; no-break exceptions enabled with Max = 0) → refused with the contradiction named.
7. Unreadable numeric in any instruction row (all ~150, generated from one table) → refused.
8. Coverage Split / Language Setup rows with an unreadable time or a minimum that is not a whole number ≥ 0 → refused.
9. Roster with a blank-row gap → refused, or every row read.
10. Duplicate instruction label with different values → refused.

**Rule semantics (seconds)**
11. Overnight day-specific language rule (Mon-Fri 18:00-05:00): in force Mon 18:00–Tue 05:00 … Fri 18:00–Sat 05:00, not Mon 00:00–05:00. Assert on `language_rules_at`, the Stage-1 model and the validator.
12. Same check for the working window at the shift-start level.
13. Contract hash changes when any enforced setting changes, including CLI overrides (language window mode, polish, exceptions).

**Metric agreement (seconds)**
14. Golden schedules (the 20 real runs in `clean_room/` plus synthetic S01/S08): engine `calculate_metrics`, `independent_validator` and `tools/clean_room_check.py` agree on every compared field. This includes `max_concurrent_break_ratio_observed` when there are breaks in blank intervals (S01).

**End-to-end scenarios (QUICK 300 s, nightly, not per commit)** — `adversarial/solver_scenarios.py`, with the expectation written in each scenario:
15. S01 baseline → exit 0, validator PASS, parity PASS.
16. S02/S03 demand above capacity → a published schedule plus a named deficit.
17. S04 one unreachable interval, S05 language shortage, S11 overnight day window, S13 24/7 understaffed → today: no schedule. After E-1: a best-achievable schedule with the violated minimums listed.
18. S06/S07 heavy leave → Leave honoured, no infeasibility.
19. S08 24/7 with week-boundary carry → clean-room equals validator equals engine.
20. S09 lone-night breaks → schedule with overlap or a named exception need.
21. S10 fixed requests contradicting the blank rule → refused, naming the requests.
22. Determinism: S01 twice with the same seed under the reproducible mode → byte-identical schedule.

**Statistical regression (release candidates only)**
23. The pre-registered paired-seed comparison (F-03 harness) against the previous release on every packaged workbook. Ship only on the registered rule.

## L. Production go-live checklist

Before a release is declared production-ready:

- [ ] Phase A fixes merged, each with its failing-first test (K-1…K-13).
- [ ] The full gate is green: `./run_tests.sh`, with test and skip counts at or above `GATE_MINIMUMS.json`.
- [ ] Parse probes: every probe refuses or behaves as specified (no "silently changed" outcomes).
- [ ] Clean-room agreement on all golden schedules (0 violations, 0 metric mismatches).
- [ ] Adversarial scenarios S01–S13 match their written expectations.
- [ ] Paired-seed comparison against the previous release passes its pre-registered rule on every packaged workbook.
- [ ] Engine sha256, package sha256 and the pinned dependency set (ortools, openpyxl, numpy, pandas, scipy) recorded in `RELEASE_IDENTITY` and in each run identity.
- [ ] The run guide matches the code: test count, SMOKE meaning, which exported workbooks are validated, language-window semantics, what is refused.
- [ ] Every run, before publishing: exit code 0; `INDEPENDENT_VALIDATION.json` status PASS with parity PASS; `BUSINESS_OUTCOME.txt` read by a person; the "what changed versus last week" diff reviewed (E-9, once it exists).
- [ ] Operational fallback agreed: what the planner does when a run returns no schedule (today: S04/S05/S11/S13-type inputs) until E-1 exists.
- [ ] One parallel-run week: the engine's schedule is compared with the manually produced one on the same input before the first live publication.

## The final questions

**What have we actually proven about this engine?**
- On 28 final schedules (20 real, 8 synthetic), a checker that shares no code with the engine found no hard-rule violation.
  - It reproduced the engine's and the validator's coverage numbers exactly, on 15 metrics.
  - That covers overnight shifts, previous-Saturday carry-in, 24/7 week-boundary spill and enforced language hours.
- The release path fails closed: in 16 adversarial runs nothing invalid became publishable, and the identity seal refused a mid-run engine change.
- Against RC5, on 6 paired seeds × 5 cases:
  - after-break target is higher (+24 summed);
  - break-concurrency violations are lower;
  - parity failures are fewer (0 vs 7).
- Demand above capacity degrades gracefully into a best-effort schedule.

**What have we not proven yet?**
- That the contract the engine schedules against is the one the workbook states. 15 of 21 probes show it is not, for malformed but plausible layouts.
- Optimality, or closeness to it, at production budgets.
- Correct behaviour of:
  - overnight day-specific language minimums (shown wrong);
  - coverage split after breaks;
  - the hard floor;
  - nesting groups;
  - no-break exceptions.
  None of the 28 checked schedules exercises them.
- Scalability beyond about 44 associates end to end. Model build alone takes about 131 s per Stage-1 build at 120 × 15 min.
- Reproducibility: the same input and seed gave three different schedules.
- That AE_IT's −4 floor is an acceptable trade rather than a search weakness.

**What could still fail in production?**
- A planner splits one person's requests over two rows, and the schedule ignores approved leave. It passes validation.
- An associate takes a full week of leave, and the whole team gets no schedule.
- A new workbook leaves the coverage gate at its default, and every week is blocked on warnings.
- A schedule with breaks in sparsely staffed blank hours is blocked by a metric-definition mismatch.
- A per-day overnight language window forces staff onto Sunday night, or refuses the run.
- Demand or roster rows are lost to a layout change (dates as headers, duplicate time rows, a blank-row gap).
- Any locally impossible minimum withholds the entire week.
- A resumed run returns a schedule made under a different language mode.
- A larger roster on a 15-minute grid spends its budget building models.

**What should be fixed before production?**
- Phase A: F-01, F-02, F-09/F-15 (refuse instead of guess), F-03, F-04.
- Then F-05, F-08, F-10 and F-12 from Phase B.

**What should be added that does not exist?**
- An elastic best-achievable mode with listed shortfalls (E-1).
- Strict structural input lint (E-2).
- One shared metric specification (E-3).
- A complete run fingerprint (E-4).
- Break entitlement by shift length (E-5).
- A reproducible solve mode (E-6).
- Part-time and contract hours (E-7).
- An optional volume-weighted objective (E-8).
- A week-over-week change report (E-9).
- Independent validation of every exported workbook (E-10).

**Which existing complexity should be removed or simplified?**
- Phases measured as never helping: joint refinement (474 audits, 0 improvements), the final recovery endgame (9 runs, 0 candidates) and DNBS.
- The bundled-fallback/champion registry, whose directories do not exist.
- The roughly 70 constant `True` feature flags.
- The ad-hoc parsing of about 150 instruction rows, replaced by one declarative table.
- Duplicated metric definitions across engine, validator and parity gate.
- Then split the 24.8k-line module and the 3.8k-line `run_case`, with the golden replay proving no behaviour change.

**What exact tests would give confidence that the engine is genuinely production-ready?** Section K, specifically:
- the 21 parser probes as refusals;
- the overnight-attribution and contract-hash unit tests;
- golden-schedule three-way agreement (engine, validator, clean-room);
- the 14 end-to-end scenarios with written expectations, including duplicate rows, full-week leave, partial impossibility, 24/7 understaffing and lone-coverage breaks;
- a reproducible-mode determinism test;
- the pre-registered paired-seed comparison against the previous release on every packaged workbook.

Sources consulted for external practice:
- OR-Tools issue on CP-SAT parallel non-determinism ([google/or-tools#3590](https://github.com/google/or-tools/issues/3590)).
- The interleaved-search reproducibility fix ([google/or-tools PR #5423](https://github.com/google/or-tools/pull/5423)).
- The OR-Tools shift-scheduling example's soft-constraint pattern (hard limits plus penalised soft ranges, `add_soft_sequence_constraint`, [google/or-tools](https://github.com/google/or-tools)). This is the basis for recommending an elastic pass over all-or-nothing hard minimums.

