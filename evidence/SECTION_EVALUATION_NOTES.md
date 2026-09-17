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
| S7 | Stage-2 break search | 6171–7657 | scanned |
| S8 | metrics & diagnostics | 7661–9541 | scanned |
| S9 | candidate selection & Pareto | 9550–11429 | scanned |
| S10 | output & release gates | 11432–12493 | scanned |
| S11 | joint / adaptive refinement | 12496–15755 | scanned |
| S12 | recovery phases | 15759–17265 | scanned |
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
