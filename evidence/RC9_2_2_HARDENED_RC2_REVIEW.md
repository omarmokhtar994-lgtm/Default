# RC9.2.2 hardened (RC2) — independent engineering review

**Verdict: NO-GO for live scheduling.** This agrees with your own
`RELEASE_STATUS.json`, but for a stronger reason than it states: the headline
selector fix does not hold under an ordinary three-candidate pool, and the
language working window in this build is still the version that was already
rejected in use.

Reviewed: `RC9_2_2_FIX_VALIDATION_RC2`, engine
`L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`,
sha256 `ea1fa36e57c465c411e4382b8424a9ee1440e7d273bdb913969784141e0c4f0a` —
**hash verified against the shipped file**, and `SCENARIOS.json`,
`MANIFEST.json` and `BUILD_MANIFEST.json` all carry that same hash. The package
describes itself accurately.

---

## 0. The finding that governs everything else: the two builds have forked

`b1acc9a949c3…` is my commit `93ab7f86` ("A51: the language window flag was
inert"). RC2 is that commit plus a focused hardening pass: **60 hunks, +361 /
−84 lines** in the engine, +162 / −38 in the production runner.

Since `93ab7f86` my branch has moved on by six commits. **Neither build is a
superset of the other:**

| | RC2 (`ea1fa36e`) | my branch (`7c8d54e3`) |
|---|---|---|
| Release-chain fail-closed rework | **yes** | no |
| Day-specific language rules (`active_days`) | **yes** | no |
| `REQUIRED_LANGUAGE_ONLY` mode | **yes** | no |
| Validator parity expansion (389 → 678 lines) | **yes** | no |
| Fixed OFF/Leave authoritative | **yes** | no |
| Language window START-only semantics (A50) | no | **yes** |
| Coverage Split tab + engine constraint (A52–A54) | no | **yes** |
| Overlapping windows pool | no | **yes** |
| Coverage-split artifact audit | no | **yes** |

Shipping either one alone discards real work. A merge is required before any
release, and the merge order matters: the selector and window fixes below have
to land before another multi-hour scenario campaign, or that campaign measures
the wrong engine.

---

## 1. Remaining issues

| # | Sev | File / function | Root cause | Business impact |
|---|---|---|---|---|
| **F1** | **Critical** | `l632_universal_scheduler.py` → `target_priority_tradeoff_select` (~9838–9962) | `risk_ok` ANDs five **global dominance** tests (`severity_ok`, `concentration_ok`, `depth_ok`, `boundary_ok`, `hard_floor_ok`). Each asks "does any other candidate beat me on this axis at ≥ my target". With three or more candidates these can eliminate *every* candidate at once. `accepted = risk_eligible or pool` then falls back to a **pure target-first sort**. | The +3 target / −9 floor trade returns. Demonstrated below. |
| **F2** | **High** | `shift_within_language_window` (1804) | Still requires the **whole shift** inside the Coverage Start/End window. The start-only correction (A50) is not in this build. | On the packaged Cricut Voice workbook, an English 16:00–03:00 window leaves **3 of 24** legal shift starts (11 under start-only). Your own Cricut Voice section runs `MINIMUM_ROWS` and predicts possible "solver infeasibility if the language working-window … is too restrictive" — that is this defect, not a configuration choice. |
| **F3** | **Medium** | `language_break_overlap_repair_plan` (~6199) | `day=(0 if qslot >= TOTAL_QSLOTS else day_scope)` reads a **stale `qslot`** left over from an earlier loop; `day_scope` *is* correctly rebound per key. When `day_scope == 7` ("Next Sun") and the stale qslot is in-week, `day=7` is passed, and `language_rules_at` drops every rule because `7 ∉ active_days`. | No donors are ever added to the next-Sunday language repair focus. Silently weakens repair in exactly the area the Cricut Chat run failed (12 next-Sunday floor gaps). |
| **F4** | **Medium** | `RUN_UNIVERSAL_PRODUCTION.py` (507–513) | When no validation workbook is produced but the quality gate passed, `rc` now stays **0**. The pre-hardening code set `rc = 4` unconditionally. | The run reports `return_code: 0` with `independent_validation.status = FAIL_OUTPUT_NOT_FOUND`. Packaging is correctly blocked, but a CI/wrapper reading the return code sees success. This is the defect class the pass set out to close. |
| **F5** | **Medium** | `_parse_language_rules` (~1558) | `windows[row["source"]] = entry` — two active rows for one language keep only the **last**. Day namespacing (`source@@day`) does not address it; two day-specific rows on the same day also collide. | Your own open-items list flags this; it is still open. A split window (e.g. Spanish 06:00–12:00 and 18:00–23:00) silently becomes one window. |
| **F6** | **Medium** | `tools/build_input_template.py` | No Language Working Window row is written at all, in **either** build. | `REQUIRED_LANGUAGE_ONLY` — the mode that implements "no English during International-required intervals" — exists in the CLI, both notebooks and the validator, but a scheduler cannot set it in the workbook. All 8 packaged workbooks parse to `OFF`. Same shape as A36. Not introduced by you; shared gap. |
| **F7** | **Low** | `engine/tools/independent_validator.py` (47–50) | `load_engine` still `exec_module`s the engine and reuses its parser. | The validator is not independent of engine interpretation. Real parity work was done (389 → 678 lines); the independence claim is not yet met, as your summary admits. |

### F1 — reproduction

`target_priority_tradeoff_select` with `target_ratio=0.90`, `floor_ratio=0.80`,
production defaults:

```
SAFE    after_target=150  after_floor=160  severe=2  run=2  depth=0.10  overage 40.0 FTE
GREEDY  after_target=153  after_floor=151  severe=9  run=6  depth=0.40  overage 48.0 FTE
ODD     after_target=150  after_floor=158  severe=0  run=8  depth=0.50  overage 60.0 FTE
```

With only `{SAFE, GREEDY}` the guard **works**: SAFE `risk_ok=True`, GREEDY
blocked by one trade-off blocker, SAFE is selected. Adding `ODD` — a perfectly
ordinary candidate that is best on one safety axis at the same target as SAFE —
gives:

```
SAFE    risk_ok=False  (severity_ok=False: ODD has 0 severe at equal target)
GREEDY  risk_ok=False  (1 trade-off blocker)
ODD     risk_ok=False  (concentration_ok=False, depth_ok=False)
guard accepted anybody? False   ->  accepted = pool  ->  target-first sort
PICKED: GREEDY   vs SAFE: target +3, floor -9, severe +7, avoidable overage +8.0 FTE
```

That is the NMG EN+SP trade, restored, by the code written to prevent it.

It is not rescued downstream. `recommendation_anchor` becomes GREEDY, and
`genuinely_safer_than_strict` only promotes a candidate whose target is within
`primary_target_tolerance` — **1** by default and hard-coded as `'1'` in the
production runner. SAFE at 150 is 3 below and cannot be promoted.

**Recommended fix.** Two changes, both small:
1. Make the fallback protected-safe. `accepted = risk_eligible or pool` should
   not revert to target-first. Either relax one axis at a time until the set is
   non-empty (record which axis was dropped), or sort the fallback by the
   protected-tier key rather than by target.
2. Make severity/concentration/depth **anchor-relative thresholds** again — the
   pre-hardening form (`severe <= max(anchor_severe + 2, 2)`) could not empty
   the set — and keep the new `tradeoff_blockers` test, which is the part that
   genuinely works.

### F3 — reproduction

```
all-day Spanish rule, active_days = [0,1,2,3,4,5,6]
  day=None -> 1 rule    day=0 -> 1 rule    day=3 -> 1 rule    day=6 -> 1 rule
  day=7    -> 0 rules
```

`day_scope == 7` is a real, labelled case in that function
(`"day": "Next Sun" if day_scope == 7 else DAY_NAMES[day_scope]`).
Fix: `day=(0 if day_scope >= 7 else day_scope)`, and make `language_rules_at`
normalise or reject `day ∉ 0..6` rather than returning an empty list.

---

## 2. Fixes verified in the code (not taken on trust)

| Claim | Verified |
|---|---|
| Missing Language Setup sheet no longer crashes | **Yes** — and this was a genuine bug in *my* build: `_parse_language_rules` returned a 2-tuple from a 3-tuple signature, so any workbook without the sheet raised `ValueError` on unpack. Good catch. |
| Release chain reordered; exact polished workbook validated | **Yes** — polisher runs `--prepare-only`, the single polished workbook is validated, Phase C is re-run after validation, then the release is sealed. |
| Packaging cannot precede validation | **Yes** — packaging requires `engine_rc==0 ∧ qrc==0 ∧ rc==0 ∧ status=='PASS' ∧ not --skip-independent-validation`. Fail-closed. |
| `--skip-independent-validation` no longer passes silently | **Yes** — `rc = 5`. |
| Fourth candidate no longer discarded | **Yes** — `exports[:3]` removed; BALANCED survives. |
| Frontier built from the complete hard-valid pool | **Yes** — the target-tolerance pre-filter that erased the knee candidate is gone. |
| Omitted trade-off cap no longer means unlimited loss | **Yes** — defaults to 1. (But see F1: the cap is not what fails.) |
| Fixed OFF / Leave authoritative regardless of preference hardness | **Yes** — gated on `fixed_enabled` independently of `hard_off` / `leave_enabled`, in both Stage 1 and the certificate model. |
| Day-specific language rules with overnight spill | **Yes** — `active_days` threaded through ~20 call sites; overnight rows authored for Friday stay active in the early-Saturday spill. |
| Duplicate previous-Saturday rows rejected, unknown names warned | **Yes** — this is what moved `AE_AR_B2B` from PASS to WARN. Correct and informative, not a regression. |
| Engine/validator overlap alignment for unaligned windows | **Yes** — `interval_language_minimum` moved from `contains_minute` to `overlaps`. |
| New 11H and Can-Cover hard failures | **Yes**, and I checked they reject **none** of the 8 packaged workbooks. |
| Offline gate | **Ran it: GATE PASS — 10 suites, 406 tests, 2 selfchecks, undefined-name sweep.** Ruff `E9,F821,F811,F632` clean. |

Preflight across all 8 packaged workbooks on both builds: identical except
`AE_AR_B2B` PASS→WARN (above). `NMG_EN_FIXED_NESTING_REST_SAFE_REGRESSION_CLEAN`
fails on **both** builds — pre-existing, not a hardening regression.

---

## 3. Claims not yet proven by an exact-build solver run

Your own list stands. I would add:

- **F1's real-world frequency.** I proved the collapse on synthetic candidates.
  How often actual pools contain a mutually-dominating trio is unknown and is
  cheap to measure — replay `tools/replay_candidate_ranking.py` over the stored
  Cricut Chat candidate pool (9 compliant candidates, already in the result ZIP).
- **Whether F3 changes any shipped schedule**, or only the repair heuristic's
  search focus.
- **Whether F4's branch is reachable with `engine_rc == 0`** — the code path is
  unambiguously weaker; reachability needs one run.
- **No exact-build CP-SAT run exists for the hardened engine on any priority
  scenario.** The `current_build_smoke` evidence is a smoke run, not a scenario.

---

## 4. Regressions introduced by the hardening pass

1. **F1** — the selector guard can disable itself and revert to target-first.
2. **F3** — stale `qslot` in the language repair planner.
3. **F4** — return code no longer fails when the validated workbook is missing.

Everything else I checked either held or improved.

---

## 5. Prioritised next tests

| # | Test | Why | Runtime |
|---|---|---|---|
| 1 | Replay the stored Cricut Chat candidate pool through `target_priority_tradeoff_select` and count how often `risk_eligible` is empty | Sizes F1 against real data, using evidence you already hold | minutes |
| 2 | Unit-pin F1: assert a protected-safe pick for the 3-candidate pool above | Stops the regression returning a third time | seconds |
| 3 | Unit-pin F3: `language_rules_at(day=7)` and the repair-plan donor set | seconds | seconds |
| 4 | Cricut Voice `MINIMUM_ROWS`, before-breaks only, on a merged engine | Confirms F2 is the infeasibility, not the roster | ~20 min |
| 5 | One `NMG_EN_PRODUCTION` QUICK/FULL run for a zero-rc sealed package | Your top required-to-close item; also exercises F4 | ~1 h |
| 6 | A genuine 11H/3OFF fixture + the 11H-prohibited negative | Still the only untested rule family | ~1 h |

Items 1–3 are offline and should be done before any solver time is spent.

---

## 6. Design note

The one structural change worth making: **there is still no single canonical
language evaluator.** `language_rules_at`, `associate_language_window`,
`shift_overlaps_required_language_for_noneligible` and the validator's copy each
re-implement part of the semantics, which is why `day=7` can silently mean "no
rules" in one caller and nothing elsewhere. Your own §5 recommendation is right;
F3 and F5 are both symptoms of its absence. Coverage Split (on my branch) has
the same requirement and should be folded into the same evaluator during the
merge rather than after it.

---

## 7. Answer to "is this safe for live schedules?"

**No.** Keep RC9.1 as the production baseline, exactly as you have it.

RC2 is materially safer than what I shipped on the release chain, identity, and
fixed-row semantics — those fixes are real and I verified them. But it is not
safe for unattended live use, because F1 means the candidate that reaches a
roster can still be the one that trades protected coverage for target intervals,
and F2 means the language working window will refuse schedules that are
achievable.

Neither build should ship on its own. The merge, plus F1 and F3, is the shortest
path to a defensible release candidate.
