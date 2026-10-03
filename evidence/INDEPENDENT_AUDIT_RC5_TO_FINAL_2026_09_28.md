# Audit of RC5 → FINAL (2026-09-28)

**Conflict of interest.** The auditor is the same engineer (Claude) who built
FINAL and wrote the brief, so this is **not** an independent audit. To reduce
that bias, every claim below was re-derived from a primary source (re-running
the code, rescoring raw run outputs, re-reading code) rather than from memory.
Where the audit contradicts the brief, the audit wins.

**Handoff note (added 2026-09-30).** The ChatGPT handoff note
(`CLAUDE_HANDOFF_INDEPENDENT_AUDIT_RC5_TO_FINAL.txt`) arrived after the first
version of this report. Section 10 now classifies every finding in it.

Checking it exposed two regressions that both audits had missed:
- **F-17**: the Colab runner lost RC5's hardening.
- **F-18**: the shipped workbooks no longer enforce their dropdowns.

It also corrected one of my own results: F-01's RC5 production-hardening
suite fails 13 of 49 tests inside the final *package* (see F-17). Both
regressions are added to §2, and the verdict and §11 are updated.

**Artifacts audited:**

| artifact | sha256 | how verified |
|---|---|---|
| `AUDIT_RC5_TO_FINAL.zip` | `3f579d68…` | its `04_FINAL_ENGINE/` and `05_TESTS/` are byte-identical to the repo at `4ad7a35` (`diff -r`) |
| RC5 engine | `0e6f6435…` | from RC5's own validation package |
| FINAL engine | `2071ae89…` | |

**Tools of this audit:** `evidence/independent_audit_2026_09_28/`

- the independent re-scorer (`indep_score.py`);
- the vocabulary probe and the budget-plan probe, with their outputs;
- the gate re-run logs.

**Legend for the "basis" column:**
- **RUN**: confirmed by running;
- **READ**: confirmed by reading the code;
- **PLAUS**: plausible, not reproduced;
- **N/V**: not verifiable from what was supplied.

---

## 1. Verdict

- **Is FINAL better than RC5?** Very probably yes on after-breaks target
  coverage for the cases measured. The largest single change, S2-PAR, gained
  +86 summed intervals across 6 cases. That is about ten times the
  run-to-run noise, and it **reproduces exactly from the raw runs (RUN)**.
  FINAL also turns DEEP from "OOM-killed on 2 of 4 cases" into finishing runs.
- **But "better than RC5" has not been measured directly.**
  - No RC5-vs-FINAL head-to-head run exists.
  - The behavioural Stage-A changes between RC5 and engine `f5f99789` (B-3
    slice floor 240→45 s, portfolio sizing, A34/A35/A37 budget fixes) were
    never isolated in a clean A/B against RC5.
  - The AE workbooks were not in any Stage-C A/B.
- **Update (2026-09-30).** The Colab package also regressed against RC5's
  package in two places (F-17, F-18). Those regressions are in the delivery
  layer, not the engine, but they are on the path every Colab run takes.
- **Is it production-safe? Not yet**, for three reasons:
  1. The gate silently stopped running the 8 Stage-A regression suites
     (209 tests) plus 17 RC5 test methods. They all pass on FINAL today (RUN),
     but nothing protects those fixes going forward.
  2. The new fail-closed preference vocabulary rejects ordinary real-world
     values as **hard contract failures**: 29 of 39 common spellings probed
     (RUN).
  3. The confirmation experiment has not been run.
- **Update (2026-10-03): the three reasons are resolved.**
  1. The gate runs all 48 suites again, with a count floor and a skip ceiling
     (F-01, F-15). It is now at 1,273 tests.
  2. The preference vocabulary accepts ordinary spellings and site mapping
     tables (F-02).
  3. The confirmation experiment ran: 72 paired runs (F-03).
     - Verdict: INCONCLUSIVE on rule 3. FINAL validated 36 of 36 runs; RC5
       failed its own validator on 7. After-break target is up 24, CI
       [+15.8, +33.2].
     - AE_IT_B2B after-break floor is 4 lower; section 12 F-03 gives its cause.
  Since then the Colab lock defect, the validator's language-hours gaps and an
  orphan-process race have also been found and fixed. They are listed in
  section 12.
- **Correctness of the schedules FINAL does publish:**
  - no hard-rule defect was found;
  - every published schedule in the evidence passed the independent
    validator with parity.
- **Confidence:**
  - medium-high that FINAL is not worse on the 7 measured cases;
  - medium that it is better in general;
  - low on exact magnitudes.

---

## 2. Findings (most severe first)

| ID | sev | file:line | what is wrong | failure scenario | fix | basis |
|---|---|---|---|---|---|---|
| **F-01** | **High** | `run_tests.sh:72,94`; `candidates/RC9_2_2_HARDENED_RC5/tests/` | After the merge, the gate runs only `tests/test_rc9_2_1_*.py` and `tests_staged/`. 8 Stage-A suites (209 tests) are never run against the shipping engine: `production_hardening` 49, `stage_aware_parity` 67, `workbook_search_controls` 34, `input_contract_fidelity` 16, `budget_objective_symmetry` 16, `max_coverage_hardening` 11, `coverage_benchmark_gate` 10, `demand_fit_memo` 6. Neither are 17 RC5 test methods in same-named suites (7 language-window semantics, 3 phase-C, 2 orchestration, 3 selector, 2 tooling). Run against FINAL, all pass except one deliberately re-pinned test (`test_rc9_2_8` old copy), and the RC5 selector/rule-semantics variants fail only on the documented re-pins (slice 240→45, B-7 signature, 3-tuple, `floor_loss` gate). | A later edit re-breaks C-1 (e.g. a zero-break contract gets 15/30/15 again), B-7 workbook routing or B-1 stage-aware parity, and the gate still says PASS. | Move the 8 suites into `tests_staged/` (drop the superseded `test_rc9_2_8` copy). Restore the 17 methods, or record for each why it was superseded. The count reported by the gate must include them. | RUN (`ORPHANED_STAGE_A_SUITES_ON_FINAL_ENGINE.log`, `RC5_BASE_SUITES_ON_FINAL_ENGINE.log`) |
| **F-02** | **High** (operability) | `l632_universal_scheduler.py:4524-4547` (`LEAVE_WORDS`, `OFF_WORDS`, `preference_kind`), `:3704` (`UNRECOGNISED_PREFERENCE_VALUE` added to `failures`) | Any Preference cell that is not in two small word lists is a **hard** contract failure. 29 of 39 ordinary values probed are rejected, including: "Public Holiday", "Bank Holiday", "Casual Leave", "Medical Leave", "Maternity Leave" (plain "maternity" is accepted), "Vacation Leave", "Comp Off", "OFF (approved)", "Leave (approved)", "Requested Off", "annual-leave", "N/A", "-", "TBD", "9-6". | A live workbook that has always run under RC5 (where these values were silently ignored, which was the real defect C-3 fixed) now produces **no schedule at all**. Safe, but the run is blocked. The brief's "0 false positives on 15 workbooks" is true of the corpus only. | Keep fail-closed. Normalise punctuation, brackets and hyphens. Treat `-`, `n/a`, `tbd` as blank. Recognise any value containing a leave or off token (leave, holiday, sick, maternity, paternity, off, rest). Add an optional workbook "Preference Mapping" table. Report each unknown with a suggested mapping. | RUN (`probe_preference_vocabulary.txt`) |
| **F-03** | **High** (evidence) | `evidence/AUDIT_BRIEF_RC5_TO_FINAL.md` §6.7; `DETERMINISTIC_MEASUREMENT.md`; `IT_STAGE1_REGRESSION_ROOT_CAUSE.md` | The brief's "Stage-A hardening: 0 schedule change" covers only the later nine-fix stack (`f5f99789` → `172d7710`). The behavioural block RC5 `0e6f6435` → `f5f99789` (B-3 slice floor, portfolio sizing, A34/A35/A37) was never cleanly measured. The only comparison was confounded by about 25 different CLI flags (the AE_IT_B2B before_target drop of 83→78 cannot be attributed to either). The Stage-C A/Bs used 4 real and 3 synthetic cases. None of the 6 AE workbooks were in them. | FINAL could be worse than RC5 on an AE-type workbook and nothing on record would show it. | Run the §7 experiment, including the AE cases. Correct the brief. | READ + RUN (hashes) |
| **F-17** | **High** (regression vs RC5) | `packages/rc9_2_2_production/runners/rc921_runner.py:253-270` (guards), `:389-393` (exit), `:211-212` (timeout); compare RC5 `runners/rc921_runner.py:69-75`, `:95-130`, `:209`, `:221-235`, `:373-377` | The final Colab package ships an **older runner lineage** than RC5's. The merge covered `engine/` only. Compared with RC5's runner, it has lost: (a) `verify_engine` (engine sha256 checked against the manifest at run time); (b) `run_runtime_check` and `tools/runtime_environment_check.py` (pinned OR-Tools checked before any budget is spent); (c) `_terminate_process_tree` with `start_new_session` + `killpg`; (d) exit-code propagation: RC5 returned `2 if run_failed else gate_rc`, FINAL returns 0; (e) the guard glob `test_rc9_2_*` (FINAL runs `test_rc9_2_1_*` only); (f) the `rc922` entry point and notebooks, and the helper runners. Run inside the final package, RC5's production-hardening suite fails 13 of 49: 5 FAIL, including `test_runner_terminates_the_full_engine_process_group`, plus 8 ERROR, 6 of which come from RC5-only input files. | A modified or mismatched engine runs unnoticed. A wrong OR-Tools version wastes the whole budget. A timeout leaves engines running. A failed scenario or failed gates report success to automation. | Port RC5's runner functions into the final runner, keeping `depth_plan`, `run_portfolio` and `seed_plan`. Ship `runtime_environment_check.py`. Put the RC5 production-hardening suite into the gate, run against the **package** layout. | RUN (`prodhard_in_final_pkg.log`) + READ |
| **F-18** | **High** (regression vs RC5) | `packages/rc9_2_2_production/inputs/*.xlsx` (and the notebooks that copy them) | RC5's 8 shipped workbooks enforce every data validation (`showErrorMessage=1`, 10–67 per workbook). FINAL's 7 workbooks still have the dropdowns, but `showErrorMessage=0` on all of them, so Excel accepts any typed value. My defect register rated C-2 (a yes/no instruction with an unrecognised value silently means "No") as "not reachable in Excel" **because** of those enforced dropdowns. It is reachable again: `yes("Yes.")`, `yes("Enable")`, `yes("Si")` and `yes("✓")` are all False (RUN). | A planner types "Enable" in "Leave Enabled" or "Hard OFF Preferences". Leave or hard OFF is silently ignored for the **whole roster**; the run passes and the schedule is published. | Re-apply RC5's validation hardening (`harden_input_validations.mjs`) to the shipped workbooks and add the RC5 test that checks it to the gate. Independently, make `yes()` fail closed on unrecognised non-empty values (C-2). | RUN |
| **F-19** | Med (evidence integrity) | `evidence/seed_portfolio_ab/score_deep.py:3-36`; same pattern in `profile_diversity_ab/score.py`, `break_load_feedback_ab/score.py` and this audit's own `indep_score.py` | Scorers treat a missing run as 0. Run on **no evidence at all**, `score_deep.py` prints "DEEP VERDICT: adopt E" and exits 0 (RUN). The published verdict is **not** affected: all 16 E runs and all 4 F run folders exist and rescore to 692 vs 370 (RUN). | Future evidence with missing runs yields a confident verdict. | Check the expected case × seed × arm set is complete. Distinguish "killed" (counts as a failure under the rule) from "missing" (abort). Exit nonzero on incomplete evidence. | RUN |
| F-04 | Med | `RUN_PORTFOLIO.py:113`, `:132` | The before-breaks winner is picked from any finished seed, with no validation gate and possibly from a different seed than the after-breaks winner. The seed's exit code is ignored (only artifacts are read). | A user receives a before-breaks sheet that does not correspond to the after-breaks schedule, or one from a run whose contract or validation failed. | Require the seed to be finished with its contract accepted **and** `production_eligible` true. Label both sheets with their seed. Offer "paired" mode (the before sheet of the after-winner). Record the exit code and treat nonzero with artifacts as suspect. Deduplicate `--seed-list` (`9000,9000` runs the same seed twice into one folder). | RUN (a fake seed that failed validation, scoring 999, won the before-breaks slot over a valid 100; duplicate seeds accepted) |
| F-05 | Med | `packages/.../rc921_runner.py:211-212` | Portfolio timeout: `subprocess.run(timeout=…)` kills only `RUN_PORTFOLIO.py`. Its seed runs (and their engines) are grandchildren and keep running. The ledger records `seeds=int(args.seeds or 1)`, which says 1 when the automatic count was 4. | On Colab, a timed-out DEEP scenario leaves engines running into the next scenario, contaminating it or causing an OOM kill. | Start with `start_new_session=True` and on timeout `os.killpg`. Record the planned seed count. | READ / PLAUS |
| F-06 | Med | `l632_universal_scheduler.py:4311` | `isolated_cp_solve`: the parent's wait loop has no deadline. | A child that hangs (a post-fork lock deadlock, or a solver ignoring its limit) blocks the run forever. Only reachable with joint refinement enabled, which is off by default. | Deadline = solver time limit + 60 s; then SIGKILL → UNKNOWN, recorded. | READ |
| F-07 | Med | `l632_universal_scheduler.py:4353-4366` | A child killed by a non-memory signal (SIGSEGV, SIGABRT) is converted into an UNKNOWN solve (`memory_stop=False`) and the run continues. | A CP-SAT crash is recorded in the audit but does not fail or warn visibly, which is contrary to the "do not hide errors" rule. | Treat signals other than 9 as errors: raise, or at least produce a top-level warning in the release gate. | READ |
| F-08 | Med | `l632_universal_scheduler.py:8703` | S2-PAR's INFEASIBLE core re-solve adds up to 60 s on top of the solve's granted `time_limit`. That time is not charged and not in the reported `elapsed`. | Break search with many INFEASIBLE diagnostic solves overruns its phase and shortens later phases, including finalization. | Cap by the remaining phase deadline. Add its time to `elapsed` / diagnostics. | READ / PLAUS |
| F-09 | Med | `l632_universal_scheduler.py:17701-17714`, `:17755` | The DNBS acceptance guard covers hits, gaps, concurrency, zero-staffed quarters, overage sum/severe/extreme and whole-week imbalance. It does **not** cover: language-reserve tiers, overage peak/variance/top-10 concentration, week-boundary imbalance, break-spacing classification, or skill coverage. Groups are keyed by (shift, language) and ignore skills. | DNBS can trade a reserve tier or overage concentration for +1 target. On a skill-configured workbook (none in the corpus) it can permute breaks across differently skilled associates. | Add those metrics to `DNBS_NO_WORSE_*`. Key groups by (shift, language, skill set). | READ |
| F-10 | Med | process | DNBS shipped on its **third** attempt, on +0.5 summed (inside noise), with M2 and H3 −3 each. The S2-PAR end-to-end rule was written after a component A/B had failed its rule, and was committed together with the result (the rule text is stamped 10 s before the first run). | "Shipped on a pre-registered rule" overstates the protection against choosing rules after seeing results. S2-PAR's effect is large enough to survive this; DNBS's is not. | Make DNBS conditional or opt-in until a 10-seed A/B (see §6). Always commit rules before runs. | RUN (git and file timestamps) |
| F-11 | Med | zip layout | The evidence is not self-contained. No raw run outputs (summary CSV and validation JSON per run) are in the zip. `05_TESTS/` cannot run as shipped (no engine/tools at the paths `run_tests.sh` expects). | A third party (e.g. ChatGPT) cannot recompute any score or run the gate from the zip. | Ship `runs/<ab>/<case>_<arm>_<seed>/{summary.csv, INDEPENDENT_VALIDATION.json, run_identity}` (a few MB) and a runnable tree. | RUN |
| F-12 | Low | `l632_universal_scheduler.py:4056` | `joint_memory_headroom` reads host `/proc/meminfo` and ignores a cgroup limit, unlike the new `machine_free_memory_mb`. | In a container with a small limit on a large host, the pre-build check passes falsely. Joint refinement is off by default. | Use `machine_free_memory_mb`. | READ |
| F-13 | Low | `tools/independent_validator.py:47,302` | The "independent" validator loads the engine's `parse_input` and about 25 engine helpers (rest, concurrency caps, language rules, reserve tiers, next-Sunday caps). 4 of these were added since RC5. | A defect in the parser or a shared helper is invisible to parity; independence is only at the level of metric arithmetic. | Document the shared surface. Longer term, give the validator its own contract parser. | READ |
| F-14 | Low | `l632_universal_scheduler.py:119`, `RELEASE_IDENTITY_RC9_2_2.json:3` | `VERSION` and `release` still say `…HARDENED-RC2`. | Artifacts are mislabelled. | Bump the version. | READ |
| F-15 | Low | tests (`skipTest` when assets are missing) | Several suites skip when packaged workbooks or artifacts are absent. The gate passes with fewer checks in a stripped tree. | A package built without inputs reports PASS. | Make the gate fail if the skip count exceeds the expected count. | READ |
| F-16 | Low | runner | The `--single-run` DEEP/OVERNIGHT path changed (the joint reserve was re-allocated) and was never run end to end. | An untested path is shipped behind a flag. | One end-to-end run per case before advertising the flag. | READ (disclosed in the brief) |

**Checked and found sound:**
- **Budget plan.** 5,100 random configurations (every flag, reserve and total
  from 60 s to 86,400 s): phases always non-negative and summing exactly to
  the total. Below 60 s the engine deliberately treats the run as 60 s (RUN).
- **S2-PAR model equivalence.** Fixing the assumption literals true on a clone
  is logically the same model. Values are read by variable index, which the
  clone preserves (READ).
- **Isolation round-trip.** Bit-identical on deterministic solves; 16 gate
  tests pass (RUN).
- **DNBS cannot lower after_target.** It cannot accept a guarded metric
  getting worse, and it cannot accept an engine-hard-invalid candidate (READ).
- **B-11 name matching.** Normalises case and whitespace; flags only rows
  that carry data (READ/RUN).
- **No rule file was edited after its result** (RUN, git history).

---

## 3. Brief accuracy

| claim in the brief | expected | observed | match | evidence |
|---|---|---|---|---|
| RC5 engine sha | `0e6f6435…` | `0e6f6435…` | ✔ | RC5 validation package |
| RC5 gate | 11 suites / 453 tests | 11 / 453 PASS (4 skipped) | ✔ | `GATE_RC5_RERUN.log` |
| FINAL engine sha | `2071ae89…` | same; zip = repo = package | ✔ | sha256 |
| Package | `77e810c6…`, 316 files | same | ✔ | |
| Gate suites | 30 | 30 PASS | ✔ | `GATE_FINAL_RERUN.log` |
| **Total tests** | **677** | **657** | ✘ | per-suite "Ran" lines, both logs |
| `tests/` | 431 | 431 | ✔ | |
| **`tests_staged/`** | **246** | **226** | ✘ | |
| Suite counts in §5 | logic 41; 2_15 13 | 42; 14 | ✘ (minor) | |
| **Commits since RC5** | **168, "all" in the log** | **172**; the log omits 5 (`4561ba2`, `e68617d` P-1, `a8993d6`, `c0f7d3c` C-1, `e2f7a45`) | ✘ | `git rev-list` |
| Engine files changed | 8 changed, 1 added, 26 unchanged | same | ✔ | checksum TSV |
| S2-PAR | 827 → 913 | 827 → 913 per case exactly | ✔ | raw `s2e2e/out`, independent scorer |
| DNBS v2 | 1057.5 → 1058.0; M2/H3 −3; H1 +4; Chat +2.5 | identical | ✔ | raw `dnbs3600b/out` |
| DEEP | E 692 vs F 370 | identical | ✔ | re-ran `score_deep.py` on raw runs |
| Joint refinement | "474 audits, 0 improvements" | 437 audits carry the joint key today; 0 with `improved` true (the only true values are in other phases) | ~ count differs, conclusion holds | scan of every `*solver_audit.json` |
| "Stage-A stack changed no schedule" | all of Stage A | only the nine-fix stack `f5f99789`→`172d7710` | ✘ overstated | F-03 |
| "No test deleted or weakened" | | 209 tests and 17 methods left out of the gate (none weakened; all pass) | ✘ partly | F-01 |
| C-3 "0 false positives" | corpus | true on the corpus; 29 of 39 common values rejected | ~ | F-02 |

---

## 4. Pre-registration and test integrity

| A/B | rule committed | first run started | ruling |
|---|---|---|---|
| S2-PAR end-to-end | 21:23, **in the same commit as the result** (text stamp 19:55:01) | 19:55:11 | plausible, **not provable**; rule written after a failed component A/B |
| DNBS v1 | 05:21:49 (text 05:02:38) | 05:20:00 | runs began 2 min before the commit; rule failed; not shipped |
| DNBS v1 3600 | 07:53 | 08:51 | void (container restart) |
| DNBS v2 | 14:48:01 | 14:48:13 | ✔ (third attempt, see F-10) |
| Seeds vs time | 09-24 22:05 | 09-25 05:39 | ✔ |
| Profile diversity | 15:09 | after | ✔ failed, not shipped |
| Break-load feedback | 19:50:28 | 19:50:38 | ✔ failed, not shipped |
| Isolation | 09-25 19:56 | real-model checks after | ✔ (toy checks before, as disclosed) |

- No rule file was changed after its first commit.
- Two changes failed their rules and were honestly left off (profile
  diversity, break-load feedback).
- The rules were applied as written, including against the author's
  preference (DNBS v1).

**Test integrity:**
- No assertion was weakened.
- The re-pins listed in the brief match documented contract changes; each was
  verified by running the old test against FINAL.
- The real problem is **omission** (F-01), not weakening.

---

## 5. Stage-C technical review (summary)

- **Joint-solve isolation**
  - Sound for its purpose, on Linux with fork. It is off the default path now
    that joint refinement is off, so its production relevance is small.
  - Gaps: F-06 (no parent deadline), F-07 (signal deaths hidden), F-12
    (cgroup).
  - Windows has no fork and falls back to in-process, where the old memory
    risk remains.
  - macOS fork after threaded libraries is not tested.
  - The parent-side model build is not isolated (disclosed).
- **S2-PAR**
  - Equivalent model, correct index reuse, and a large reproduced gain.
  - F-08 is its only defect.
  - At more than one worker, Stage 2 is now nondeterministic; runs were
    already nondeterministic through Stage 1.
- **DNBS**
  - Safe on hard rules and core metrics.
  - Soft-metric and skill blind spots (F-09).
  - Value unproven (F-10).
- **Budget plan**: sound (property test).
- **Portfolio runner and Colab runner**: F-04, F-05. Duplicate seeds in
  `--seed-list` would collide in one run folder (Low).

---

## 6. Decision review

| decision | opinion |
|---|---|
| **DNBS as default** | **Should not have been default.** The measured effect is +0.5 with a mixed per-case sign, reached on the third attempt. It costs 288 s of break search at 3600 s. Make it opt-in, or conditional (run only when the anchor's break losses ≥ 2), until a 10-seed paired A/B shows a lower 95% confidence bound above 0. |
| **Joint refinement removed** | **Justified.** 0 improvements in every audit found (437 carry the key), 36 DEEP attempts accepted nothing, and two 13–14 GB kernel kills. Keeping it behind a flag is right. |
| **No-candidate endgame removed** | **Justified but weakly evidenced.** 9 runs, 0 added. It only fires when there is no release candidate, so removing it cannot turn a published schedule into none. Keep the flag. |
| **DEEP = best of 4 × 1 h** | **An operational policy, not statistical proof of superiority.** One realization per arm, and F lost only by being OOM-killed, a failure since fixed by isolation. It is defensible: E ≥ F wherever F finished, it is memory-safe, and the seeds curve shows +7.6 for the 2nd seed. Whether one 4 h run *with isolation* would beat it has not been measured. |
| **Two seeds per arm** | **Not enough.** Observed seed spread: Chat about ±4 (171–179), H1 125–151, real workbooks otherwise ±1. Detecting a +2 per-case effect on Chat at 80% power needs about 40 paired seeds, which is impractical. Use 10 paired seeds per case (20 for Chat and H1), paired deltas, bootstrap and permutation confidence intervals, **non-inferiority** margins per case, and superiority only on the summed real-workbook statistic. |
| **Confidence from the A/B chain** | Good for **direction** where the effect dwarfs noise (S2-PAR, DEEP). Poor for **magnitude**, for interactions between changes, and for everything in the unmeasured block RC5 → `f5f99789`. Different budgets make the steps non-additive. |
| **What was lost or left weaker than the brief says** | F-01 regression coverage; F-02 operability; DNBS M2/H3 −3; Chat after_floor −4 in the S2-PAR run; before and after sheets can come from different seeds (F-04); QUICK notebook default doubled to 2 h (2 seeds); Stage-2 determinism at >1 worker; untested `--single-run` long path. |

---

## 7. Confirmation experiment: RC5 vs FINAL

Pre-register before any run. Commit the rule, the scorer and the case list.

**Arms**
- RC5: engine `0e6f6435`, with its own runner and defaults.
- FINAL: engine `2071ae89`, with its own runner and defaults.
- Both are "as shipped". A secondary arm runs both with identical explicit
  flags, to separate code from defaults.

**Environment**
- One container image: Python 3.11, OR-Tools 9.15.6755, same openpyxl,
  pandas and numpy.
- 4 vCPU, a cgroup memory limit of 12.7 GB (Colab-equivalent).
- 2 workers per run, at most 2 runs at once, each pinned with `taskset` to
  its own 2 cores.
- Verification jobs at `oom_score_adj` 1000. Contamination logged; a
  contaminated run is rerun with the same seed.

**Mode**
- QUICK, FULL_SCHEDULE, one 3600 s run. This compares engines, not portfolio
  policy.
- Portfolio policy is a separate follow-up: DEEP best-of-4 vs one isolated
  4 h run, 5 seeds.

**Cases**
- Real: Cricut Chat, Cricut Voice, NMG_SP, and the 6 AE workbooks (AE_AR_B2B,
  AE_AR_Choice, AE_FR_B2B, AE_FR_Choice, AE_IT_B2B, AE_IT_Choice).
- Synthetic with known optima: M2 (117), H3 (105), H1 (168), E2 (63),
  Union N=247 (168).
- Inputs are hashed. Where FINAL's contract refuses an input that RC5
  accepts, that is recorded as its own outcome and inspected by hand (true or
  false positive). Inputs are never edited to make both arms run.

**Seeds**
- 9000–9009 paired across arms (the same seed in both arms); 9000–9019 for
  Chat and H1.
- Run order is randomized by a fixed shuffle seed.

**Recorded for every run**
- after/before target and floor;
- after 90/80/100;
- floor gaps and severe gaps;
- max consecutive gaps;
- zero-staffed quarters;
- language gaps and reserve tiers;
- break concurrency violations;
- overage sum/peak/severe/extreme;
- week-boundary metrics;
- balance and employee-quality spreads;
- no-break exceptions;
- validator status, hard failures, parity;
- runtime;
- peak RSS (via `/usr/bin/time -v`);
- timeouts, crashes, OOM;
- `run_identity` hashes.

The before-breaks and after-breaks artifacts are kept separately.

**Analysis**
- Per case: the mean paired delta (FINAL − RC5), with a 10,000-resample
  bootstrap 95% CI and an exact sign-flip permutation p-value.
- Summed over real workbooks: a case-stratified bootstrap.

**Pre-registered rules**

1. **Validity.** FINAL has 100% validator PASS, 0 hard failures and parity
   PASS on every run whose contract it accepts. Any violation means **stop**.
2. **Robustness.** FINAL's crash, timeout and OOM count ≤ RC5's.
3. **Non-inferiority per real workbook:**
   - after_target CI lower bound ≥ −1;
   - after_floor CI lower bound ≥ −1;
   - best_before_target CI lower bound ≥ −1;
   - the upper bound of the mean increase in severe gaps, language gaps and
     concurrency violations ≤ 0.5.
4. **Synthetic cases.** after_target CI lower bound ≥ −3.
5. **Superiority** (needed to claim "better"). The lower CI bound of the
   summed real-workbook after_target delta > 0.
6. **Resources.** Runtime ≤ budget + 5%; peak RSS ≤ 8 GB.
7. **Contract.** 0 false-positive refusals on the real workbooks (after the
   F-02 fix).

**Outcomes**
- **Release:** rules 1–7 all pass.
- **Rollback or more engineering:** any failure of rule 1 or 2, or any real
  case with CI upper bound < −1 (a clear regression). Bisect along the stage
  diffs.
- **Inconclusive** (the CI straddles the margin): keep current production,
  add 10 seeds for that case.

**Cost**
- Full design: about 190 runs per arm, about 380 h of run time, about 8 days
  on one 4-core box, or 1–2 days sharded.
- Minimum version: Chat, Voice, NMG_SP, AE_IT_B2B, H1, M2 × 10 seeds, about
  60 h at 2 concurrent.

---

## 8. Improvement roadmap (in order)

| # | problem | change | quality gain (expected) | runtime / memory | cost | risk | A/B that proves it |
|---|---|---|---|---|---|---|---|
| 1 | F-01: gate coverage lost | Restore the 8 suites and 17 methods | none (protection only) | +~10 s gate | ½ day | none | the gate itself |
| 2 | F-02: false refusals | Normalised vocabulary + mapping table + suggestions | none on coverage; prevents blocked runs | 0 | 1 day | low (still fail-closed) | contract smoke on every live workbook: 0 false refusals, and the 15-workbook corpus unchanged |
| 3 | Unproven RC5→FINAL | §7 experiment | decides the release | compute | 2–8 days | none | §7 |
| 4 | DNBS value unproven | Conditional DNBS, then a 10-seed paired A/B | 0 to +1 | ±288 s of break search | ½ day + compute | low | 10 seeds × 7 cases; ship if the lower CI bound of the summed delta > 0 and no case CI < −1 |
| 5 | Unlucky single runs | QUICK = best of 2 seeds run **in parallel** (2 × 2 workers on 4 cores) instead of in sequence | +7.6 expected on the 4 cases (seeds curve) at the same wall time | 2× CPU, 2× RAM (~2–3 GB) | ½ day | low | 10 paired days: portfolio-2-parallel vs single, same wall clock |
| 6 | Chat about 179 vs a relaxed 218: loss comes from the weekly rules plus break fit | Joint LNS: free shifts **and** breaks for 1–2 days or a subset of associates around the worst intervals, anchored to the incumbent (DNBS generalised to shifts) | +1 to +4 on Chat (a guess; the bound is not tight) | +10–20% time | 1–2 weeks | medium (new model) | 10 seeds × Chat/Voice/NMG/H1 vs FINAL; non-inferiority elsewhere |
| 7 | M2/H3/H1 skeletons cover 100% before breaks but lose 6–25 intervals to breaks | Break-aware Stage 1: per-interval reserve cuts from pattern arithmetic (heads on shift ≥ requirement + expected concurrent breaks) as soft constraints | H1 +5–10, M2 +2–6 (the feedback probe got H1 +8 in 40 min) | Stage 1 slightly slower | 1 week | medium | 10 seeds × synthetic + real; must not lower before_target by more than 1 on real workbooks |
| 8 | F-05, F-06, F-07, F-08 | Process-group kill, parent deadline, surface signal deaths, cap the core re-solve | robustness only | 0 | 1 day | low | fault-injection tests (kill, hang, segfault) |
| 9 | F-04 | Paired before-sheet option, validation gate, seed labels | clarity | 0 | ½ day | low | unit tests |
| 10 | F-09, F-13, F-14 | Complete the DNBS guard; validator parser independence; version bump; one metric registry | trust | 0 | 2–5 days | low–medium | parity on corpus + mutation tests |
| 11 | Maintainability | Split the 24k-line scheduler by stage; delete `candidates/` after F-01; retire dead joint code after 1 more release | none | 0 | 1–2 weeks | medium (merge risk) | gate + deterministic 1-worker bit-identity on 3 cases |

---

## 9. What could not be checked, and why

- **ChatGPT's environment** could not install OR-Tools; this audit could, and ran the full gate. ChatGPT's findings are classified in §10.
- **No new solver runs** were made during this audit. Results come from
  re-scoring existing raw runs, which exist only on the author's machine, not
  in the zip.
- **Behaviour on other platforms** (Windows, macOS, real Colab) was not
  tested. OOM behaviour was checked only under emulation.
- **The exact "474 audits" figure** could not be reproduced (437 found now);
  the conclusion holds.
- **Skill allocation** was not checked: no workbook uses it.
- **The user's live production workbooks** beyond the corpus were not
  available.
- **RC9.1 (the current production engine, per earlier records)** was not part
  of this audit. It should be a third arm in §7 if the goal is to replace it.

---

## 10. Checking the handoff's findings

**Summary.**
- ChatGPT's overall verdict matches this audit: a better engineering baseline,
  not proven better on schedules, not production-ready, targeted fixes plus a
  direct RC5-vs-FINAL experiment, no rewrite.
- Its runner and portfolio findings are largely **right**. Checking them led
  to F-17: those runner behaviours are *regressions from RC5*, which neither
  audit had seen.
- It **missed** the three issues this audit ranks highest:
  - the 209 Stage-A tests the gate no longer runs (F-01);
  - the preference vocabulary rejecting ordinary values (F-02);
  - the unenforced workbook dropdowns (F-18).
- It is **wrong** on two record-keeping points: the commit count, and the
  S2-PAR pre-registration.
- Several severities are overstated because they ignore that joint refinement
  is off by default.
- It could not run OR-Tools. The full gate was run here: 30 suites PASS.

| # | ChatGPT finding | classification | evidence | corrected interpretation |
|---|---|---|---|---|
| C-01 | DEEP scorer reports success on missing evidence | **PARTIALLY VALID** | RUN: `score_deep.py` on an empty evidence directory prints "adopt E", exit 0. RUN: all 16 E runs and all 4 F folders exist and rescore to 692 vs 370. | The defect is real (now F-19) and applies to all the scorers, including this audit's own. It did **not** produce a false claim: the published verdict came from complete evidence. Severity: Medium (evidence tooling), not Critical. |
| H-01 | 677 / 246 tests is wrong; true 657 / 226 | **VALID** | RUN: both gate logs | Same as §3. Also valid: the gate should assert its own total. |
| H-02 | Runner ignores gate failure | **VALID, and a regression** | READ: `rc921_runner.py:389-393` returns 0; RC5's runner returned `2 if run_failed else gate_rc` | Part of F-17. |
| H-03 | Colab guards skip the staged suites | **VALID, and a regression** | READ: `rc921_runner.py:259` globs `test_rc9_2_1_*`; RC5's globbed `test_rc9_2_*` | Part of F-17. It is the same gap as F-01, in the runner rather than the gate. |
| H-04 | Portfolio can pick an unvalidated before-breaks winner | **VALID** | RUN: a fake failed seed (999) beat a valid one (100) | F-04. |
| H-05 | "Validated" portfolio candidates need not be production-quality | **PARTIALLY VALID** | RUN: 80 of 80 evidence runs are `PASS_WITH_QUALITY_WARNINGS` with `production_eligible=TRUE`. READ: `RUN_PORTFOLIO.py` does not read `production_eligible`. | Valid that the portfolio uses its own predicate instead of the engine's `production_eligible`. **Invalid** as a demand that quality warnings must not exist: that would make every run ineligible. Employee quality and language are already validator warnings by design (warn mode). Fix: also require `production_eligible`. |
| H-06 | Duplicate seeds; exit code not persisted | **VALID** | RUN: `seed_list(…,"9000,9000")` → `[9000, 9000]`; READ: `RUN_PORTFOLIO.py:132` | Severity Low–Medium. Added to F-04. |
| H-07 | DNBS acceptance ignores language reserve, skills, employee quality, preferences | **PARTIALLY VALID** | READ: `DNBS_NO_WORSE_*` (`:17701-17714`); DNBS changes only break patterns within fixed shifts | Language reserve, skills (and overage concentration) are valid (F-09). **Employee quality and preferences are invalid:** both depend only on shifts and OFF days, which DNBS never changes. A pure guard test with a made-up metrics dict proves nothing about what DNBS can actually move. |
| H-08 | Isolated-solver signal deaths become UNKNOWN | **VALID** | READ: `:4353-4366` | F-07. Severity Medium, not High: the path runs only when joint refinement is enabled, which is off by default. |
| H-09 | Model is built in the parent; fallback is silent on Windows/macOS | **PARTIALLY VALID** | READ: `:4260-4275`; `RESULT.md` discloses the build in the parent | The fact is valid and was disclosed. "Silently downgrade" is **invalid**: every fallback records `IN_PROCESS_<reason>` (`NO_FORK`, `CALLBACK_ATTACHED`, …) in `joint_solve_isolation`. Severity is low while joint refinement is off by default. Moving the build into the child is worth it only if joint refinement is ever re-enabled. |
| H-10 | Validator shares the engine's `parse_input` | **VALID** | READ: `independent_validator.py:47,302`, plus about 25 shared helpers | F-13. Severity Medium at most. It **pre-dates RC5** (RC5's validator already used `parse_input`); FINAL added 4 shared helpers. |
| H-11 | No direct RC5-vs-FINAL A/B | **VALID** | | F-03; §7 experiment. |
| H-12 | Quality still below known optima | **VALID as a fact, PARTIALLY on the remedy** | | The proposed fix ("reopen Stage 1 after breaks / bounded LNS") was already **measured**. Break-load feedback reopens Stage 1 from the break load: 0 of 26 accepted at 540 s; at 40 minutes, H1 +8 and every other case +0. Joint refinement: 0 improvements. Exact joint models did not beat the engine within budget (7f55c60). The gap is real, but the obvious remedy has evidence against it at production budgets. This is a capability gap, not a release defect. |
| M-01 | Budget plan below the declared minimum at tiny budgets | **PARTIALLY VALID** | RUN: `build_global_budget_plan(1)` sums to 60 | Real only below 60 s: the engine deliberately treats such runs as 60 s (the deadline is `max(60, total)`), so "total ≤ budget" is violated for requests under 60 s. Phases below their viable minimum **are** reported (`phases_below_minimum_viable_slice`). Low. |
| M-02 | S2 core re-solve is capped at 60 s and may yield no core | **VALID** | READ: `:8700-8723` | Diagnostic only. A missing core is not labelled. This audit adds that the re-solve time is also unbudgeted (F-08). |
| M-03 | DNBS is local; skips cross-week shifts | **VALID** (design limit) | READ: `:17752-17755` | Low; this is a search limitation, not a defect. |
| M-04 | DNBS shipped on weak evidence | **VALID** | RUN: rescored 1057.5 → 1058.0 | F-10. |
| M-05 | Quality gates default to WARN | **PARTIALLY VALID** | READ: `target_loss_gate_mode="warn"` in **both** RC5 and FINAL | A policy decision unchanged from RC5, not a regression. `production_ready` stays false when quality fails. Strict defaults would block every evidence run (all carry quality warnings), so "fail" needs a per-gate calibration first. |
| M-06 | Defect register has unresolved items | **VALID** | `DEFECT_REGISTER.md` | Known and listed in the register. **C-2 must be re-rated**: it was "not reachable" only because of enforced dropdowns, which FINAL's workbooks lost (F-18). |
| M-07 | Stale names | **VALID** | READ: `engine/README.md` line 1 says "RC9.2.1 Protected Tier + Residual Balance RC1"; `VERSION` says `…HARDENED-RC2` | F-14. |
| M-08 | Portfolio mixes before/after winners and deletes provenance | **PARTIALLY VALID** | READ: `RUN_PORTFOLIO.py:182-191` | Mixing is valid (F-04). "Deletes provenance" is overstated: only the previous `PORTFOLIO_BEST` copy is replaced; every seed folder and `PORTFOLIO_SUMMARY.json` are kept. |
| M-09 | Parallelism is based on CPU, not memory | **VALID**, Low | READ: `seed_plan` | With joint refinement off, QUICK seeds peak around 0.8–2 GB, so the risk is modest on Colab. |
| M-10 | Timeouts and failures do not propagate | **VALID, and a regression** | READ | Part of F-17. |
| M-11 | Runner parse errors fall back to defaults | **INVALID** (as an impact claim) | READ: `RUN_UNIVERSAL_PRODUCTION.py:55-71` | The fallback covers only the convenience read of Run Stage and Run Depth. The engine then re-parses the same workbook with the same `parse_input` and fails closed, so a malformed workbook cannot produce "a valid-looking schedule" through this path. |
| M-12 | Scorers are not self-contained | **VALID** | | F-11 and F-19. |
| L-01 | `__pycache__` in the audit tree | **INVALID** | RUN: the zip ChatGPT received (sha `3f579d68…`, identical to the one built) contains 0 `__pycache__` entries | Most likely created by ChatGPT's own test runs after extracting. |
| L-02 | Residual items unexercised | **VALID** | | Same as M-06. |
| §Numeric 12 | "168 commits since RC5: MATCHES" | **INVALID** | RUN: `git rev-list` gives 172 commits since RC5; the packaged log omits 5, including P-1 (`e68617d`) and C-1 (`c0f7d3c`) | ChatGPT counted the log, not the history. |
| §Numeric 8 | "474 audits": matches the document | **PARTIALLY** | RUN: 437 audits currently carry the joint key, 0 improved | The conclusion holds; the count is not reproducible. |
| §Prereg | "S2 rule … appear[s] in the commit history before [its] reported runs" | **INVALID** for S2-PAR | RUN: the rule and the result were committed together in `37288d0` (21:23); the runs started 19:55:11; the rule text is stamped 19:55:01 | Plausible, not provable. The other rules are correct as stated. |
| §Prereg | "Re-pins … still need confirmation in the pinned environment" | **Now confirmed** | RUN: full gate on OR-Tools 9.15.6755, 30 suites PASS; RC5 suites against FINAL fail only on documented re-pins | |
| §Quality-failure path | Final path is "substantially stronger" | **VALID** (engine) | | It holds for the engine and runner; the Colab wrapper regressed (F-17). |
| Recommendation | Targeted refactoring plus a direct confirmation test; no rewrite | **VALID** | | Matches §11. The P0 list must add F-01, F-02, F-17 and F-18. |

---

## 11. Next-step decision

**Do immediately, before any more schedule runs:**
1. F-17: restore RC5's runner safeguards in the Colab runner (engine sha
   check, runtime check, process-tree kill, exit propagation, full guard
   glob).
2. F-18: re-enforce the workbook dropdowns.
3. F-01: restore the gate.
4. Correct the brief (§3 mismatches).
5. F-11 and F-19: ship raw per-run evidence, and make the scorers fail
   closed.

**Fix before production:**
- F-02 (preference vocabulary);
- C-2 (`yes()` must fail closed);
- F-04 (portfolio eligibility and duplicate seeds);
- F-07 (hidden child crashes);
- F-08 (core re-solve overrun);
- F-14 (version);
- make DNBS conditional or opt-in (F-10).

**Validate with a focused A/B:**
- the §7 RC5-vs-FINAL experiment, with RC9.1 as a third arm;
- the DNBS 10-seed A/B;
- QUICK = 2 parallel seeds.

**Defer:**
- items 6, 7 and 11 of the roadmap;
- validator parser independence;
- any further joint-refinement work.

**Recommendation: proceed with FINAL after targeted fixes.** Keep the current
production engine running until FINAL passes §7. FINAL's engine gains are real
and reproducible, and no hard-rule defect was found in the engine. The package
around it must be brought back to RC5's safety level (F-17, F-18) before any
Colab or production use.

What is missing is:
- protection (the gate and the runner guards);
- operability (the vocabulary);
- input safety (the dropdowns);
- a direct comparison.

None of these needs a redesign.

**Minimum evidence to promote FINAL:**
- the gate includes every suite and passes;
- 0 false refusals on the live workbooks;
- §7 rules 1–4, 6 and 7 pass;
- rule 5 passes, if you want to claim "better" rather than "not worse".

**First three actions:**
1. Package safety (1 day). Port RC5's runner functions into the final
   runner. Re-enforce the workbook validations. Put the 209 orphaned Stage-A
   tests, and RC5's production-hardening suite run against the package
   layout, into the gate. Fix the brief's counts.
2. Input safety (1 day). Widen the preference vocabulary with a mapping
   table, make `yes()` fail closed, then run the contract check on every
   workbook you schedule with.
3. Commit the §7 rule and a fail-closed scorer, then launch the minimum
   RC5-vs-FINAL experiment (Chat, Voice, NMG_SP, AE_IT_B2B, H1, M2 × 10
   paired seeds).

---

## 12. Disposition of every finding (updated 2026-09-30)

Every fix below was made on `claude/handoff-document-m6egz2`. Each has a test
in the gate, and each test was mutation-checked: removing the fix makes a test
fail. Gate after the last fix: **48 suites, 1236 tests, 2 skipped**, in the
repository and in the built package layout.

### Findings of this audit

| ID | status | what was done | commit |
|---|---|---|---|
| F-01 | **Closed** | The 8 orphaned Stage-A suites, RC5's base suites and RC5's production-hardening suite are in the gate again, run against the package layout (45 → 48 suites). `run_tests.sh` sums "Ran N" / "skipped=K" and fails below `tests_staged/GATE_MINIMUMS.json` (min 1236 tests, max 2 skips). | 572ff17 |
| F-02 | **Closed** | The vocabulary now accepts ordinary spellings: Public Holiday, PH, Casual Leave, OFF (approved), R/D, N/A, "-" and others. Ambiguous values (Training, WFH, Half Day, Sick Off) still fail closed. A workbook can map site codes on a "Preference Code Mapping" sheet (Value / Meaning). 42-workbook corpus: 0 contract results and 0 contract hashes changed. | 1d81b32 |
| F-03 | **Run; verdict INCONCLUSIVE** (rule 3) | 72 runs, 2026-10-01 to 10-02, 6 paired seeds (AMENDMENTS.txt A1/A2, recorded before any quality value was read). Rules 1, 2, 4, 5, 6 and 7 pass. FINAL validated 36 of 36 runs. RC5 failed its own validator (FAIL_METRIC_PARITY) on 7 runs: all 6 NMG_SP seeds, so NMG_SP is a comparator failure, and Chat seed 9001. Summed real after_target is +24.0, CI [+15.8, +33.2]. Break concurrency violations fall on every case. Rule 3 fails on two counts. AE_IT_B2B after_floor is -4.0, CI [-5.2, -2.7], a real loss beyond the margin. best_before_target is 1 to 3 lower on Chat, Voice and AE_IT, with CIs straddling -1. Not rollback: no after_target regression. See `experiments/rc5_vs_final/RESULT.md`. | 420258e, fe0d0c3, 6af1d70, this commit |
| F-03 follow-up | **Cause narrowed** (2026-10-03) | AE_IT_B2B floor -4. Three hypotheses were tested and refuted. A selection defect: FINAL's pool has no candidate with target >= 70 and floor >= 91. The break-concurrency limit: with it lifted, floor 89 and 88. The Stage-1 slice change B-3: with RC5's 240 s on two seeds, floor 88 and 85 (rule registered first). B-3 does partly explain the before-break target item. The loss sits in the Stage-1 skeleton search under FINAL's portfolio and budget phases. No engine change without a stage-bisection A/B; FINAL's +4 target / -4 floor with 0-3 concurrency violations against RC5's 8-21 is the current trade. `evidence/aeit_floor_cause/`. | 4e47d9e, this commit |
| F-04 | **Closed** | Both portfolio slots come only from eligible seeds (exit 0, validator PASS, 0 hard, parity PASS, production_eligible TRUE). | 9d41800 |
| F-05 | **Closed** | The Colab runner starts each engine in its own session and kills the process group on timeout or interrupt. A test proves the grandchild dies. | 1d81b32 |
| F-06 | **Closed** | Isolated solves have a hard deadline (time limit + 120 s grace). A hung child is killed and reported as `killed_for_deadline`, not as a memory stop. | 3cb1441 |
| F-07 | **Closed** | A child dying of any signal other than the memory watchdog's SIGKILL raises RuntimeError. It is no longer turned into an UNKNOWN solve. | 3cb1441 |
| F-08 | **Closed** | The S2-PAR core re-solve time is recorded (`break_infeasibility_core_resolve_sec`). Every outcome is labelled `break_infeasibility_core_status`. | 3cb1441 |
| F-09 | **Closed** | The DNBS guard also covers language reserve and minimum-only quarters, skill allocation, avoidable-overage peak and concentration, and the week-boundary metrics. | 3cb1441 |
| F-10 | **Closed** | DNBS is off by default (opt-in `--enable-dnbs`), because the evidence it shipped on was inside noise. | 3cb1441 |
| F-11 | **Closed** | `evidence/raw_runs/`: 144 runs behind seven published A/Bs (summary, validation, status, identity, audit extract, log tail; 11 MB). A gate test recomputes every published verdict from it. | 02f4d1a |
| F-12 | **Closed** | `joint_memory_headroom` uses `machine_free_memory_mb()`, which respects a cgroup limit. | 3cb1441 |
| F-13 | **Closed** (2026-10-03) | `independent_input_crosscheck` re-reads with openpyxl alone every input fact a metric or hard rule depends on: roster, each associate's Language, demand, shrinkage, the shift catalog, the request switches (preferences, fixed, leave, hard OFF, strict OFF), target/floor/rest, preference and fixed cells, Language Setup hours per day, and the Language Working Window, including a run override. Over 70 workbooks there were 0 mismatches. 12 tamper tests plant a parser defect each, and each is caught. What remains shared is the rule definitions, by design (`engine/tools/VALIDATOR_INDEPENDENCE.md`). The same work found and fixed two validator defects. First, REQUIRED_LANGUAGE_ONLY hours were never checked. Second, a run's `--language-working-window` override was ignored, so hours enforced from the notebook went unverified. | 16ce157, 3109fd7, this commit |
| F-14 | **Closed** | Release is L6.3.2.8-RC9.2.2-PRODUCTION-HARDENED-RC6 in VERSION, the polisher, the release identity and the manifest. | 22775ba |
| F-15 | **Closed** | The gate caps skips at 2. That cap exposed 26 tests that silently skipped in every package build (they looked only for repository paths); they now run there. | 572ff17, 20d4aff |
| F-16 | **Closed** | 2026-10-02, here, from the built package (gate PASS, 1244 tests). Both cases were run with `--mode DEEP --single-run`, 14,400 s each, concurrently: CRICUT_CHAT and SYNTH_H1. Both exited 0 within budget, and the validator passed with 0 hard failures, metric parity PASS and production_eligible TRUE. Engine RSS peaked around 3.7 GB for both together, against 13-14 GB kills before. The path works, but it is not better: Chat after_target 166, against 169-184 for 1 h QUICK runs in F-03. The notebooks and guide now say "works, not recommended" instead of "not for production yet". Evidence: `evidence/f16_single_run_deep/`. | df3715d, this commit |
| F-16b (new) | **Closed** (2026-10-03) | The 1-in-24 isolation-suite error left unexplained in df3715d. It was caught on the old engine twice in 100 side-by-side rounds and once in 150 stress runs. Cause: the forked solve armed PR_SET_PDEATHSIG only after other setup, so a parent killed in that window left an orphan solve running. Fix: the death signal is armed first, then the parent is re-checked. A deterministic delayed-arming test fails on the old order and passes on the fix; there were 0 failures in 150 stress runs on the fix. Evidence: `evidence/isolation_orphan_race/`. | this commit |
| F-17 | **Closed** | RC5's runner safeguards are back: engine sha check, pinned runtime check, full gate, process-group kill, and a nonzero exit on any failed scenario. `--overwrite` is explicit, and seed parallelism is capped by memory. | 1d81b32 |
| F-18 | **Closed** | Every dropdown in the 4 non-baseline shipped workbooks rejects typed values. This is a byte-minimal attribute rewrite; cell values and contract hashes are unchanged. The 3 RC9.1 baseline-protected workbooks are untouched; the engine's boolean check covers them. | 1d81b32 |
| F-19 | **Closed** | All four scorers read through `runlib`. They exit 2 when a run folder is missing, and count killed or rejected runs as failures. They reproduce every published table and verdict exactly. | 02f4d1a |
| F-20 (new) | **Closed** | Found while fixing: the measured runs had no scipy, so the aggregate MILP guide was UNAVAILABLE in all of them. With scipy it is OPTIMAL on all 7 cases. scipy is now a checked runtime dependency (runner refuses to start without it). The engine prints `WARNING AGGREGATE_GUIDANCE_UNAVAILABLE` when the guide is missing. | 1d81b32, 3cb1441 |
| F-21 (new) | **Closed** | Found while fixing: the packaged AE_AR_B2B fails its own contract (5 previous-week associates not on the roster). The workbook is baseline-protected, so it is left byte-identical. The manifest names the 5 departed associates, and the runner passes them with `--acknowledge-departed`. Acknowledging only some of them still fails. | 1d81b32 |

### ChatGPT's findings (section 10)

| ID | status |
|---|---|
| C-01 | Closed with F-19. |
| H-01 | Closed: brief corrected; the gate asserts its own total. |
| H-02, H-03, M-10 | Closed with F-17. |
| H-04, H-05, H-06, M-08 | Closed with F-04: eligibility includes `production_eligible`; distinct seeds; exit codes persisted; seed-labelled files with a sha256 provenance manifest. |
| H-07 | Closed with F-09. Employee quality and preferences are not affected by DNBS, which changes only break placement inside fixed shifts. |
| H-08 | Closed with F-07. |
| H-09 | No change, by decision. Joint refinement is off by default, and Colab/Linux has fork. Where fork is missing, the fallback is not silent: every solve is counted in the run's solver audit as `IN_PROCESS_NO_FORK`. A console warning is deferred so the engine under experiment stays frozen. |
| H-10 | Closed with F-13. |
| H-11 | Answered by F-03: INCONCLUSIVE. FINAL is better on after-break target and robustness; AE_IT floor and before-break target are worse (see F-03). |
| H-12 | Open as a fact: quality is still below known optima on H1/M2. The proposed remedies were measured and did not help (break-load feedback, profile rotation). No change. |
| M-01 | Closed: the engine refuses `--time-limit` below 60 s. |
| M-02 | Closed with F-08. |
| M-03 | Design limit; DNBS is now opt-in (F-10). |
| M-04 | Closed with F-10. |
| M-05 | No change, by decision. `target_loss_gate_mode="warn"` is RC5's own default. It is policy, not a regression, and the business outcome reports the declared quality debt on every run. |
| M-06, L-02 | C-2 re-rated and fixed (`yes()` fails closed; `HARD_INVALID_INSTRUCTION_BOOLEAN`). The other register items are unchanged and listed in `DEFECT_REGISTER.md`. |
| M-07 | Closed with F-14. `engine/README.md`'s title is left as is: it names the tier model, not the release. |
| M-09 | Closed: `seed_plan` caps side-by-side seeds by available memory (3 GB per seed). |
| M-11, L-01 | Invalid (section 10); no change. |
| §Numeric 12 | The brief is corrected to 172. `evidence/COMMIT_LOG_SINCE_RC5.txt` has every commit. |

### Not done, and why
- **RC9.1 as a third arm, the other five AE workbooks, and the secondary
  identical-flags arm** of §7 are outside the minimum experiment (60 h on this
  4-core machine). A verdict speaks only for the six cases run.
- **DNBS 10-seed A/B and "QUICK = 2 parallel seeds"** are improvement
  experiments, not defect fixes. DNBS stays opt-in until such an A/B passes.
