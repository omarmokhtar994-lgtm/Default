# Section-by-section evaluation — running notes

Sections were derived from the AST, not guessed: 403 top-level objects in
`l632_universal_scheduler.py` (22,094 lines), plus 3 satellite modules.

Status key: **read** = examined line by line; **scanned** = covered only by the
cross-cutting automated scans.

| | section | lines | status |
|---|---|---|---|
| S1 | foundations, time math, IO | 224–610 | **read** |
| S2 | data model, checkpoint serialization | 614–1064 | **read** |
| S3 | workbook parsing → contract | 1067–3003 | partial |
| S4 | contract validation | 3006–3461 | partial |
| S5 | domain rule predicates | 3464–3967 | **read** |
| S6 | Stage-1 skeleton search | 3970–6168 | **read** |
| S7 | Stage-2 break search | 6171–7657 | **read** (high-risk paths) |
| S8 | metrics & diagnostics | 7661–9541 | **read** (high-risk paths) |
| S9 | candidate selection & Pareto | 9550–11429 | **read** (decision paths) |
| S10 | output & release gates | 11432–12493 | **read** (gate paths) |
| S11 | joint / adaptive refinement | 12496–15755 | scanned + hits read |
| S12 | recovery phases | 15759–17265 | scanned + hits read |
| S13 | orchestration (`run_case`) | 17268–20933 | scanned |
| S14 | CLI, selfcheck, business outcome | 20935–22090 | scanned |
| S15–17 | runner, validator, satellites | 2,136 | **read** |

---

## S2 — data model and checkpoint serialization: SOUND

Examined because resume correctness depends entirely on it. It holds up.

* `run_id` is hashed from VERSION, the coverage-evaluator string,
  `input_sha256`, `contract_sha256`, `engine_sha256`, `seed_sha256`,
  `parameters_sha256` and git commit/describe/dirty. Every checkpoint is
  gated on it, so a changed workbook can never resume onto stale skeletons,
  and neither roster shape nor break-window controls can drift under a
  restored `selected_pattern`.
* The comment block at 17790 is worth preserving: they hit a real bug where
  an absolute wall-clock deadline was hashed into `run_id`, which both
  defeated the exact-identity release gate and made `--resume` permanently
  inoperative. The fix — hash the inputs that determine the deadline, not the
  derived timestamp — is correct.
* `write_json` and `write_csv` are atomic (temp file + `replace`), so a
  container death mid-write cannot leave a truncated checkpoint. Relevant:
  a container did die during this work.

One minor item, folded into C-1 rather than listed separately:
`deserialize_skeleton` and `deserialize_break_candidate` default `cp_status`
to `"FEASIBLE"`. A missing status should not resurrect as *solved*.

---

## S6 — Stage-1 skeleton search

### S6-0 (positive result): the Stage-1 objective is genuinely weighted-sum

Tested whether the 17 profiles' weight vectors are secretly lexicographic —
the B-5 question applied to the whole portfolio. For each profile, ordered the
terms by weight and checked whether any weight exceeds the maximum possible
contribution of everything below it, using real bounds from AE_AR_B2B
(39 associates, 168 active intervals).

**343 weighted terms across 17 profiles; 343 can change an optimum (100%).**
No profile collapses to a lexicographic order, and no two profiles share a
weight vector.

This is a clean result and it *bounds* B-5: the non-separating-tier problem is
a Stage-2 property, not a Stage-1 one.

### S6-1 (LATENT, HIGH if reached): a nesting group with mixed leave is silently UNSAT

`leave[a, d]` is pinned to a constant from the contract:

```python
model.Add(leave[a, d] == (1 if is_leave else 0))          # line 5518
```

and nesting groups then force members to agree:

```python
model.Add(leave[member, d] == leave[leader, d])           # line 5578
```

Both sides are already constants. If the leader has approved leave on a day and
a member does not, this adds `1 == 0` and the model is trivially infeasible.

Measured on GDI_REAL28:

```
no nesting group (control)          cp_status=FEASIBLE
same group, different leave         cp_status=INFEASIBLE   (0.04s)
log line: STAGE1 target90_restore_champion status=INFEASIBLE elapsed=0.04s
diagnostics naming a cause:  NONE  ('conflicts' is CP-SAT's conflict counter)
validate_input_contract:     no nesting failure, no nesting warning
```

The whole run dies in 40 milliseconds and nothing tells the planner that two
people in one nesting group have different approved leave.

Note the asymmetry: `off[a, d]` is only pinned when the preference says OFF, so
the OFF half of the same constraint is partly free and far less dangerous. It
is specifically leave — always pinned — that is fatal.

### S6-2 (dead code): the only nesting-group pre-check can never fire

`validate_input_contract` has `CONTRADICTORY_EXACT_SCHEDULES_IN_NESTING_GROUP`,
guarded by:

```python
if associate.nesting_group and any(associate.fixed_schedule):     # line 3341
```

But the parser makes those mutually exclusive — an exact-days row has its group
cleared, and a group row never gets a fixed schedule:

```python
if any(values):
    assoc.fixed_schedule = values
    ...
    assoc.nesting_group = ""      # line 1511
else:
    assoc.nesting_group = group_value
```

Measured across all 15 workbooks: **0 associates carry both**, so the guard is
never true and the failure code is unreachable.

So the engine has one nesting-group contract check that cannot fire, and no
check at all for the condition that actually kills the model (S6-1).

### S6-3 (coverage gap): the fixed/nesting subsystem is unexercised

**0 of 15 workbooks define any nesting group.** Combined with `Fixed Request
Use = No` in the workbooks checked, the entire fixed/nesting path — parser
branch, group-equality constraints, and its contract check — has no coverage
from any real workbook. S6-1 and S6-2 both live in that unexercised code,
which is consistent: it is where unexercised code decays.

---

## Cross-cutting findings (whole file, from the automated scans)

Recorded in detail in `C1_C2_CONTRACT_PARSING_FAILS_OPEN.md`:

* **C-1** (latent, systemic) — 90 shadow `getattr` defaults, permissive every
  time they disagree with the declared default.
* **C-2** (medium) — `yes()` has no unrecognised state; mitigated in practice
  by stop-style dropdowns on every affected flag.
* **C-3** (high) — `preference_kind` accepts two exact words; everything else
  silently means "no constraint", with no dropdown anywhere.

Low severity, no action proposed:

* three dead determinism guards around `randomize_search`;
* 54 RC-marker constants referenced only at their own definition;
* `minute_of_day`'s ambiguous `1` branch;
* `to_float` (58 sites, permissive) alongside `strict_float` (11 sites, strict)
  in the same contract layer;
* quality-gate thresholds compare with `1e-12` while coverage comparisons use
  `1e-9` — deliberate, not a defect.

---

## S7 — Stage-2 break search: no new defects found

Coverage note: S7 is 1,490 lines. I read the high-risk paths — objective
construction, pattern generation, exception accounting and the admission
guards — not every line.

### S7-0 (positive): the break objective is also a genuine weighted sum

Same separation test as S6-0, applied to all 8 break objective modes with real
bounds from AE_AR_B2B (273 cells, 168 active intervals, 115 patterns, max
pattern score 321), including `exception_penalty`, the pattern penalty,
concurrency, whole-week balance, language reserve and the stacking term.

**152 terms across 8 modes; 152 can change an optimum (100%).**

### S7-1 (checked, sound): an unbreakable shift duration is a contract failure

`_generic_break_patterns` returns `[]` when `duration_q <= total_break_q + 2`,
which would silently force every cell on that shift into a no-break exception.
It does not, because `validate_input_contract` probes **per shift duration**
with `limit=1` and raises `BREAK_WINDOW_CONTRACT_INFEASIBLE` before any solve.

### S7-2 (checked, sound): the minimum-exception proof is correctly lexicographic

`exception_lower_bound = floor((BestObjectiveBound + 1e-6) / exception_penalty)`
is only valid if `exception_penalty` exceeds everything else in the objective.
It does, by construction — `max(1e9, diagnostic_pattern_upper + 1)` — and every
other objective term is gated off in diagnostic mode. I checked the one branch
that is not obviously gated: at 7177 concurrency in `"fail"` mode adds a **hard
constraint**, not an objective term, and the `"warn"` branch carries
`and not diagnostic_mode`. So no term leaks in and the proven minimum is sound.

### S7-3 (checked, unreachable): `float("inf")` on a MODEL_INVALID solution

The early return at 7111 builds a `BreakSolution` with `objective=inf`. That
objective is negated into a sort key at 10993 (`-float(pair[1].objective)`),
where `-inf` would rank **best**. It cannot happen: `candidate_pool_class`
gates on `cp_status in {"OPTIMAL", "FEASIBLE"}` (9858) and pool admission does
the same (18309), so a MODEL_INVALID solution never reaches the ranking.

---

## S8 — metrics and diagnostics

Coverage note: S8 is 1,880 lines, `calculate_metrics` alone is 831. I checked
the arithmetic hazards and the before/after contract, not every line.

### S8-0 (checked, sound): division guards and metric symmetry

* Every division in `calculate_metrics` is guarded. The two that looked unsafe
  are not: `top10_concentration` divides by `sum(values)` under an `if values`
  test, but values are only appended when `> 0`, so a non-empty list always
  sums positive; `divisor = len(protected_quarters)` is guarded by an early
  `continue` at 8190.
* **252 emitted keys, 39 symmetric before/after pairs, 0 `after_*` without a
  `before_*`.** The asymmetry the code fixed once at 8136 has not reappeared.

### S8-1 (latent): a before/after name fallback substitutes the wrong stage

Two metrics break the naming convention. Every other pair is explicitly
`before_`/`after_` prefixed; these two emit the **after** value unprefixed:

```python
severe_floor_gap_count        += int(after_pct  + 1e-9 < severe_threshold)   # after
before_severe_floor_gap_count += int(before_pct + 1e-9 < severe_threshold)   # before
```

Seven call sites then fall back from the before-name to the after-name:

```python
metrics.get("before_severe_floor_gap_count", metrics.get("severe_floor_gap_count", 0))
```
at 7444, 9563, 9564, 9692, 9693, 19379, 19380.

If the before-key were ever absent, these would use the **after-break** count
as the **before-break** count. That is semantically wrong, not merely
permissive — and 7444 is the break-loss guard, which exists precisely to
compare before against after.

Latent: `ensure_before_break_metrics` guarantees `no_break_metrics` is a full
`calculate_metrics` output, so the key is always present.

Two things make it worth fixing anyway:

1. **The same key is read two ways in the same file.** Lines 11343, 11364 and
   11371 use `skeleton.diagnostics["no_break_metrics"]` with direct indexing —
   fail loud. The seven sites above fail silent, into the wrong value.
2. **The empty-dict defaults at 7441–7444 contradict each other.** With
   `no_break_metrics` missing, `before_target` and `before_floor` default to
   "every interval hit" (optimistic) while `before_severe_gaps` defaults to
   `active_for_loss_guard`, i.e. "every interval is a severe gap"
   (pessimistic). One missing input produces a picture that cannot be true.

Same family as C-1: a fallback default that is not the declared value.

---

## S9 — candidate selection and Pareto

Coverage note: read the decision-critical functions (`_candidate_quality_tuple`,
`candidate_dominates`, `nondominated_candidates`, `select_export_candidates`
entry/exit, the prefix helpers), not all 1,880 lines.

### S9-0 (positive): the quality tuple handles the S8-1 trap correctly

Where seven other sites fall back from a before-name to an after-name,
`_candidate_quality_tuple` **branches** instead:

```python
severe_gaps = int((metrics.get("before_severe_floor_gap_count", 0) if prefix == "before"
                   else metrics.get("severe_floor_gap_count", 0)) or 0)
```

The most decision-critical function in the engine gets this right.

### S9-1 (fragile, currently correct): seven unprefixed after-terms in a before ranking

Seven terms are read unprefixed and are after-break quantities:
`week_boundary_hard_failure_count`, `language_reserve_shortfall_quarters`,
`language_minimum_only_quarters`, the two `week_boundary_language_*` variants,
`language_break_caused_reserve_loss_quarters`, `skill_allocation_gap_quarters`,
plus the three `whole_week_*` terms — while `week_boundary_{prefix}_target` and
`week_boundary_{prefix}_floor` next to them **are** prefixed.

Correct today: all four `prefix="before"` call sites (11343, 11371, 12498,
18485) pass `no_break_metrics`, where after == before because no breaks are
placed. Nothing states that invariant — no assertion, no docstring line — and
the function's signature accepts any metrics dict with any prefix.

### S9-2 (MEDIUM-LOW): Pareto dominance and the lexicographic order disagree

`candidate_dominates` compares **15 dimensions**; `_candidate_quality_tuple`
has ~31 terms. About 15 of the lexicographic terms are not dominance
dimensions, among them `floor_deficit_max`, every `language_*` term,
`skill_allocation_gap_quarters`, the `whole_week_*` trio, `before_floor`, and
most of the overage-distribution block.

So B can rank **above** A lexicographically while A dominates B:

* A and B tie on every dominance dimension that appears early in the tuple.
* The first tuple term where they differ is a non-dominance term where B wins.
* A is strictly better on some *later* dominance dimension.
* → A dominates B → `nondominated_candidates` discards B, the lexicographic
  winner.

`week_boundary_hard_failure_count` cannot trigger this — it is hard-gated
through `validate_schedule`, so compliant candidates all carry 0. The ~15 soft
terms can.

**Severity is limited by where the frontier is used.** The release
recommendation comes from `target_priority_tradeoff_select(selection_pool, …)`
— the full pool, not the frontier. The frontier only drives the *alternative*
exports: `SAFER_BALANCED_CANDIDATE` (11019), `MAX_FLOOR_CANDIDATE` (11021),
`BALANCED_CANDIDATE` (11043) and the Pareto manifest. So the shipped schedule
is unaffected; the menu of alternatives offered to the planner can omit the
best option on those soft dimensions.

### S9-3 (structural): eleven different candidate orderings

`protected_floor_anchor_key`, `target_anchor_key`, `repair_candidate_key`,
`_candidate_quality_tuple`, `break_solution_key`, `protected_safe_fallback_key`,
`candidate_dominates`, `safety_key`, `coverage_sum_key`,
`skeleton_quality_key`, `skeleton_breakability_priority_key`.

Eleven orderings over the same candidates, at least one pair provably
inconsistent (S9-2). Each is individually reasonable; there is no single place
that states how they relate.

---

## S10 — output and release gates

### S10-0 (positive): a disabled gate does not manufacture evidence

```python
# ... evidence read as a pass. Turning a gate off must not create
# evidence that it held.
gate_results[gate] = "NOT_ENFORCED"
```

Three distinct states — PASS, NOT_ENFORCED, FAIL — with suppressed rows kept.
This is the right design and it is worth saying so.

### S10-1: C-1's shadow defaults sit inside the production release gate

`production_quality_gate` reads its limits through the same permissive
`getattr` pattern:

| line | read | declared |
|---|---|---|
| 11790, 11851 | `quality_max_target_losses_from_breaks`, **999999** | 6 |
| 11795 | `whole_week_max_overage_cap_violations`, **999999** | 0 |
| 11797 | `whole_week_max_imbalance_violations`, **999999** | 0 |
| 11796 | `whole_week_overage_cap_ratio`, **2.0** | 1.35 |

Still latent, but this raises C-1 from internal plumbing to the release gate
itself, and strengthens the case for removing the defaults rather than
documenting them.

Also confirms B-9's relevance: `transferable_overstaffing_pair_count` is used
here as a hard `> 0` gate condition and has no independent check.

---

## S11 — joint / adaptive refinement

Coverage note: 3,260 lines, the largest section after `run_case`. Covered by
targeted defect-class scans plus reads of the hits. Not read end to end.

Scan results: 19 silent `except` handlers, 9 `getattr(parsed, …)` shadow
defaults, 1 permissive `metrics.get` default, 0 before/after name fallbacks,
4 ordering key functions.

### S11-1 (MEDIUM): floor losses borrow the target loss cap, and are never gated

```python
if before_target_hits and target_hits:
    model.Add(sum(target_hits) >= sum(before_target_hits)
              - getattr(parsed, "quality_max_target_losses_from_breaks", 999999))       # 14308
if getattr(parsed, "target_loss_gate_mode", "warn") == "fail" and floor_hits and before_floor_hits:
    model.Add(sum(floor_hits) >= sum(before_floor_hits)
              - getattr(parsed, "quality_max_target_losses_from_breaks", 999999))       # 14310
```

Three separate problems in two lines:

1. **The floor constraint uses the target cap.** There is no
   `quality_max_floor_losses_from_breaks` anywhere in the contract — grep
   confirms it does not exist. The declared 6 was authored as a *target* budget.
2. **The two are asymmetrically gated.** The target constraint applies
   unconditionally; the floor constraint applies only when
   `target_loss_gate_mode == "fail"`. That field's declared default is
   `"warn"`, so **by default floor losses are unconstrained in joint
   refinement while target losses are hard-capped.**
3. **`floor_losses_from_breaks` is never gated at all.**
   `production_quality_gate` checks only `target_losses_from_breaks` (11790).
   The floor metric is computed (8074), exported to the leaderboard (12394) and
   used in a near-feasible test (9986) and a business-outcome branch (11895) —
   but no release gate ever looks at it.

Floor is the safety threshold, below target. Losing floor coverage to break
placement is the more serious of the two losses, and it is the one with no cap
of its own and no gate.

---

## S12 — recovery phases

Scan results: 15 silent `except` handlers, 0 shadow defaults, 0 permissive
metric defaults, 1 before/after fallback, 0 ordering functions.

### S12-1 (low): one more fallback-to-a-different-metric

```python
raw = source.get("before_raw_min", source.get("before_raw", 1))      # 16126
```

Falls back from a *minimum* to a plain value, then to a literal `1`. Same
family as S8-1 and C-1: the fallback is a different quantity, not a default.

No other findings in S12 from the scans.
