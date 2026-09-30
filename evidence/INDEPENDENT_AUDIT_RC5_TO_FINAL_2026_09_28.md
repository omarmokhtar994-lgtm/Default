# Audit of RC5 → FINAL (2026-09-28)

**Conflict of interest.** The auditor is the same engineer (Claude) who built
FINAL and wrote the brief, so this is **not** an independent audit. To reduce
that bias, every claim below was re-derived from a primary source (re-running
the code, rescoring raw run outputs, re-reading code) rather than from memory.
Where the audit contradicts the brief, the audit wins.

**Missing input.** The handoff note (`CLAUDE_HANDOFF_INDEPENDENT_AUDIT_RC5_TO_FINAL.txt`)
was not uploaded. Section 10 (checking the handoff's findings) is therefore
pending.

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
- **Is it production-safe? Not yet**, for three reasons:
  1. The gate silently stopped running the 8 Stage-A regression suites
     (209 tests) plus 17 RC5 test methods. They all pass on FINAL today (RUN),
     but nothing protects those fixes going forward.
  2. The new fail-closed preference vocabulary rejects ordinary real-world
     values as **hard contract failures**: 29 of 39 common spellings probed
     (RUN).
  3. The confirmation experiment has not been run.
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
| F-04 | Med | `RUN_PORTFOLIO.py:113`, `:132` | The before-breaks winner is picked from any finished seed, with no validation gate and possibly from a different seed than the after-breaks winner. The seed's exit code is ignored (only artifacts are read). | A user receives a before-breaks sheet that does not correspond to the after-breaks schedule, or one from a run whose contract or validation failed. | Require the seed to be finished with its contract accepted. Label both sheets with their seed. Offer "paired" mode (the before sheet of the after-winner). Record the exit code and treat nonzero with artifacts as suspect. | READ |
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

- **The handoff note** was not supplied, so its findings could not be checked
  (section 10).
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

**Pending.** The note was not uploaded. Every item is UNVERIFIED until it is
supplied. Upload `CLAUDE_HANDOFF_INDEPENDENT_AUDIT_RC5_TO_FINAL.txt` and each
finding will be classified VALID / PARTIALLY VALID / INVALID / UNVERIFIED
against the evidence above.

---

## 11. Next-step decision

**Do immediately, before any more schedule runs:**
1. F-01: restore the gate.
2. Correct the brief (§3 mismatches).
3. F-11: add raw per-run evidence to the audit package.

**Fix before production:**
- F-02 (preference vocabulary);
- F-05 (Colab orphan processes);
- F-04 (portfolio before-sheet);
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
production engine running until FINAL passes §7. FINAL's main gains are real
and reproducible, and no hard-rule defect was found. What is missing is
protection (the gate), operability (the vocabulary) and a direct comparison.
None of these needs a redesign.

**Minimum evidence to promote FINAL:**
- the gate includes every suite and passes;
- 0 false refusals on the live workbooks;
- §7 rules 1–4, 6 and 7 pass;
- rule 5 passes, if you want to claim "better" rather than "not worse".

**First three actions:**
1. Restore the 209 orphaned tests to the gate and fix the brief's counts
   (½ day).
2. Widen the preference vocabulary with a mapping table, then run the
   contract check on every workbook you schedule with (1 day).
3. Commit the §7 rule and scorer, then launch the minimum RC5-vs-FINAL
   experiment (Chat, Voice, NMG_SP, AE_IT_B2B, H1, M2 × 10 paired seeds).
