# Consolidated state: what was fixed, what was wrong about my own reports, what is left

One page for the whole engagement. Every claim here is backed by a file in
`evidence/` and a commit on `claude/handoff-document-m6egz2`.

---

## A. Fixed, measured, shipped

| | defect | proof |
|---|---|---|
| **B-1** | The release parity gate demanded a full after-break metric surface from a skeleton-only artifact. 41 mismatches, every one `engine: null`. **Every `BEFORE_BREAKS_ONLY` run failed with `rc=4`.** | skeleton run `rc 4 → 0`, parity `FAIL(41) → PASS(0)`, all 41 fields compared |
| **B-1c** | The quality report published `active_intervals: 0` and `safety: NOT_RUN` for a run that covered 112 of 112. A null is a visible absence; `0` is a number, and it was wrong. | Phase C coverage `0/0 → 112/112`, safety `NOT_RUN → PASS` |
| **B-1d** | The preliminary quality report runs *before* validation, was honestly blocked, and latched a code the later clean report could not clear. | `quality_allows_validation` made stage-aware |
| **B-2** | The run reported *"No final schedule workbook was produced, so independent validation could not run"* — on a run whose validation had run and passed. | outcome now `BEFORE_BREAK_SKELETON_GENERATED` |
| **B-3** | `STAGE1_MIN_MEANINGFUL_SLICE_SEC = 240` was measured **cold** (`build_skeleton` with no hint) and applied to the portfolio loop, which is **always warm-started**. A 900s run refused a 171-second window for a solve needing 30 and attempted **0 of 15** profiles. | warm curve: cliff moves 150–210s → **15–30s**; default 240 → 45 |
| **B-7** | 43 behavioural parameters had no workbook route, and the runner passed its own value for 24 of them — so adding rows alone would have changed nothing. | engine command byte-identical when the workbook is silent; contract hash unchanged on all 14 workbooks |
| **B-8** | The independent validator compared next-Sunday adjacency between **intervals** using each interval's maximum, while the solver constrains adjacent **quarter slots**. It was checking a weaker rule under the same name. | engine 1 / validator 0 → **1 / 1**; six artifacts agree |

**B-3 outcome**, shipped default vs shipped default, 900s, seed 9000:

| | AE_FR_Choice | AE_AR_B2B *(the workbook 240 was calibrated on)* |
|---|---|---|
| Stage-1 profiles attempted | 0/15 → **3/15** | 0/15 → **3/15** |
| before_target | 105 → **112** | 166 → **168** (max) |
| after_target | 101 → **109** | 161 → **164** |
| floor gaps | 2 → **0** | 1 → **0** |

Gate: **17 suites, 607 tests, PASS.**

---

## B. Investigated, no change warranted

**B-5 — the objective.** Measured off the built model, not the declared
weights: 2,109 terms, 14 distinct coefficients, **400,000,000 : 1**, and 13 of
14 tiers can be outvoted in aggregate by the tier below. So the ladder does not
implement the priority order it resembles.

It does not need to. Candidate order is a real lexicographic tuple; guarantees
are hard constraints (`min_target_hits` — which is what the B-4 proof uses).
Worst case across eight rosters is 7.0e12–1.5e13, **~600,000× int64 headroom**.
No symptom. Restructuring a solver objective on a measurement with no symptom
is the speculative change this work has avoided.

**B-6 — symmetry.** Real and large (Cricut_Chat: 24 of 27 associates in one
orbit, 6.204e23 permutations). But `symmetry_level` defaults to **2** — the
enabled level — and presolve already installs an **orbitope**:

```
Cricut_Chat   1047 generators, 613 orbits sized 24, orbitope 137 x 24
NMG_EN_PROD    409 generators, 316 orbits sized 10, orbitope  94 x 10
```

That is the canonical strongest break for interchangeable columns. Hand-written
symmetry breaking would duplicate or conflict with it.

---

## C. Open, fix specified — in the order I would do them

### 1. B-11 — name-matched sheets fail open *(highest severity)*

A misspelled name on the **Preference** sheet silently discards that person's
**approved leave and guaranteed OFF days**, and they get scheduled. No warning;
every gate passes. Fixed Request warns only if *every* row misses. The carry-in
sheet drops the Sunday rest gap with an advisory, while treating a *duplicate*
name as a hard failure — an asymmetry that ranks duplicates above a lost rest
constraint.

**The parity architecture cannot catch this**: the validator parses the same
contract, sees the same absent leave, and agrees. Both sides consistently
wrong. Unlike B-8, there is no disagreement to detect.

*Fix:* report unmatched rows on every name-matched sheet; `HARD_` for
Preference and Fixed Request, joining the 27 existing fail-closed codes.
**Settle the departed-staff workflow first** so failing closed does not block
legitimate runs.

### 2. B-10 — the adaptive break search never runs *(highest coverage upside)*

112 planned attempts, **0 completed**, on essentially every run including the
authors' own 3600s runs. `BREAK_MIN_MEANINGFUL_SLICE_SEC = 180` gates whether
to attempt at all, but its own comment justifies it as a **ceiling** — *"180 is
the point past which more time per attempt buys nothing"*. The same curve puts
feasibility at **90s** and shows 150s returning a feasible result. Stage 1 has
both a floor and a cap; the break search has one constant doing a floor's job.

On `B3_FRC_DEFAULT45` it stopped at 549s inside a 471–700s window, leaving
**151 seconds of its own phase** — precisely the slice it refused.

*Also B-3's defect again:* the probe that set 180 calls `solve_breaks` cold; the
loop calls it warm. Unlike B-3, **no new measurement is needed** — the recorded
cold curve already shows feasibility at 90s.

*Fix:* split the constant as Stage 1 does — floor 90–120, cap 180 — then A/B
**with repeats**.

*My B-3 fix made this worse:* more surviving skeletons → bigger portfolio →
smaller slices (28 planned/1 done → 112 planned/0 done). B-3 still produced the
better schedule, so not an outcome regression, but B-10's value went **up** when
B-3 landed.

### 3. B-9 — sixteen decision-driving metrics have no independent check

The gate compares 41 of 138 engine metrics. Of the 120 scalar claims, 31 drive
a decision and **16 are unchecked** — including two that decide **hard
validity** (`skeleton_hard_clean`) and nine that decide **which candidate
ships** (`_candidate_quality_tuple`).

Two real issues found in the analysis:
* `week_boundary_hard_failure_count` **double-counts** overlapping categories
  (a quarter can be zero-staffed *and* a language gap *and* an opening gap).
  Tested `== 0`, so it can only cause a false *failure*.
* `hard_floor_gap_count` compares raw ratios while the solver enforces ceiled
  units — **the metric is weaker than the constraint it reports on**. Not
  reachable today; becomes reachable the moment a candidate path is built with
  `hard_floor=False`.

*Build order:* `target_losses_from_breaks` (trivial, gates release, is the B-4
quantity), `before_severe_floor_gap_count` (trivial), then the two near-free
week-boundary ones. **`transferable_overstaffing_pair_count` should probably be
excluded and documented** — an independent version means reimplementing the
pairing heuristic, and a copied one can never disagree, which is worse than
uncovered because it looks covered.

### 4. B-4 — fund `target_lock_recovery` at QUICK?

Proven headroom of **1–2 intervals**: `min_target_hits=112` is INFEASIBLE in
1.6s (a proof), `111` is FEASIBLE and hard-clean. The phase needs 65s at its
entry guard, was allocated 19s, attempted **0 of 14**, and its ceiling at 900s
is 53s — so QUICK cannot fund it at any setting.

Funding it costs ~65s from Stage-1 or break search, both of which convert to
real coverage. **Run-to-run variance is ±1 interval — the same size as the
effect** — so one run per arm cannot decide it. Use repeats, or measure the
phase in isolation as `tools/b4_probe.py` does.

### 5. The fork

Coverage Split exists only on this repo's engine (57 references,
`L6.3.2.6-…-RC1`); the RC5 lineage has 0 and carries all the hardening. **Port
Coverage Split into RC5**, not the reverse. 7 self-contained definitions, ~50
call sites across 8 functions, **all 8 present in RC5** — mechanical except
`calculate_metrics`, which feeds the parity gate and so forces a deliberate
choice about `PARITY_FIELDS` (the B-8 trap).

### 6. Repackaging and handoff

Manifests not re-hashed and zips stale across nine commits. The RC5 authors
should receive B-1/B-2, B-3, B-8 (their defects), B-10 and B-11 (found in their
lineage), plus the correction that B-5 and B-6 are **not** defects.

---

## D. Corrections I made to my own earlier claims

Recorded because the trustworthiness of the rest depends on these being visible.

| I said | The measurement said |
|---|---|
| B-3 is caused by B-5's 800M:1 objective | **No.** A cold-measured slice floor. The objective is not implicated. |
| B-4 leaves "two intervals" on the table | **1–2.** A byte-identical repeat returned 110 where the first returned 109. |
| B-6: "`symmetry_level` unset", implying off | **Defaults to 2** — the enabled level. And presolve already installs an orbitope. |
| B-9: 9 release-gating metrics unchecked | **16.** I had checked only two decision functions and missed hard-validity and candidate selection. |
| A budget fix that drops phases below their entry guard | **Reverted.** Deadlines are cumulative; `post_break_repair` ran on a nominal 19s against a 35s guard. Dropping on nominal allocation would have deleted real work. |
| (earlier) same-input non-determinism in the engine | **Machine load**, not the engine — two clean sequential runs agreed on 137 of 139 metrics. |

One bug I introduced was caught by the undefined-name sweep before any run hit
it (`audit` referenced before assignment).

---

## E. What the sweep decides

Six AE schedules at **3600s**, the authors' own budget, against their recorded
baselines. Started 01:01 UTC, ~62 min per case, sequential by design.

**If any of the four unmeasured schedules regresses, revert the Stage-1 default
to 240 and keep the floor reachable only through the B-7 workbook control.**
That makes it a configuration change rather than a code change, which is why
B-7 landing before B-3 was worth the ordering.

Nothing in section C should be implemented until the sweep completes — B-9 and
B-10 both touch code the sweep exercises per case, and changing it mid-sweep
would validate early and late cases with different code.
