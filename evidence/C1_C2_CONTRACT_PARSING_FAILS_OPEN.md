# C-1 / C-2: the contract layer fails open in two systemic ways

Found during the section-by-section evaluation of the engine (S1 foundations,
S4 contract validation). Both are the same shape as B-11 — the schedule is
computed correctly from a contract that is not what the planner wrote — and
both are invisible to the parity architecture for the same reason: the
independent validator parses the same contract.

---

## C-2 (HIGH): an affirmative-looking cell silently disables a hard constraint

### The defect

`yes()` is the only parser for instruction booleans:

```python
def yes(v: Any, default: bool = False) -> bool:
    s = norm(v)
    if not s:
        return default
    return s in {"yes", "y", "true", "1", "enabled", "on", "hard", "required"}
```

It has **no unrecognised state**. Any non-empty text outside those eight words
is silently `False`. There is no warning, so `validate_input_contract` has
nothing to see and the run proceeds.

### Measured, on a copy of GDI_REAL28 (the shipped asset was not modified)

A `Leave` row added to Instructions, as a planner would:

| planner types | `leave_enabled` | approved leave enforced? | warnings |
|---|---|---|---|
| `Yes` | True | yes | 0 |
| `YES` | True | yes | 0 |
| `Y ` | True | yes | 0 |
| `1` | True | yes | 0 |
| `yes - approved only` | **False** | **NO** | **0** |
| `TRUE (see note)` | **False** | **NO** | **0** |
| `Enable` | **False** | **NO** | **0** |
| `yes.` | **False** | **NO** | **0** |

Four of eight affirmative-intent values turn the feature **off**, silently. A
trailing full stop is enough.

`leave_enabled` gates the hard rule directly:

```python
if parsed.leave_enabled and preference_kind_value == "leave":
    return []          # this associate cannot work this day
```

With it False, every person on approved leave becomes schedulable.

### Blast radius

Ten instruction flags are parsed this way. Seven default to an enabling value,
so a typo **flips them off and removes a constraint**:

| flag | default | what a typo silently removes |
|---|---|---|
| `leave_enabled` | Yes | **approved leave stops blocking, whole roster** |
| `hard_off` | Yes | **guaranteed OFF days stop blocking** |
| `strict_off` | Yes | the OFF-count rule relaxes |
| `separate_off_days` | Yes | the OFF-day separation rule relaxes |
| `use_preferences` | Yes | **every preference is ignored** |
| `fixed_enabled` | No | declared fixed shifts are wiped (`fixed_schedule = [""] * 7`) |
| `opening_enabled` | No | opening minimum FTE is not enforced |

The remaining three (`use11`, `allow_no_break`, `demand_fit_mode`) default off,
so a typo fails to *add* a feature rather than removing a guard — still a
silent misread, lower severity.

This is strictly worse in reach than B-11: B-11 loses one person's leave, C-2
loses everyone's from a single cell.

### Root cause

`yes()` conflates "not affirmative" with "negative". `tri_state()` has the same
shape. The engine already solved this once: B-7 introduced `strict_bool` inside
`_parse_search_controls`, which emits `HARD_INVALID_SEARCH_CONTROL` on text it
does not recognise. That parser is used for **2** call sites; these **10** were
never migrated.

### Fix direction

Route the instruction flags through the same validated parser and emit a
`HARD_` code for unrecognised text, joining the 27 codes the engine already
fails closed on. No new machinery: the convention, the parser and the
fail-closed wiring all already exist.

---

## C-1 (LATENT, systemic): 90 shadow defaults, all more permissive than declared

### The defect

Gate limits are read through `getattr(parsed, "field", <default>)` in 90 places
across 36 fields. `ParsedInput` declares all of them, so today the defaults
never fire. But where they disagree, **they disagree in the permissive
direction, every time**:

| field | declared | shadow default | direction |
|---|---|---|---|
| `whole_week_overage_cap_ratio` | 1.35 | 2.0 (6 sites) | looser |
| `whole_week_max_adjacent_raw_change` | 3 | 999999 (5 sites) | unbounded |
| `whole_week_max_imbalance_violations` | 0 | 999999 (3 sites) | unbounded |
| `whole_week_max_overage_cap_violations` | 0 | 999999 (3 sites) | unbounded |
| `quality_max_target_losses_from_breaks` | 6 | 999999 (8 sites), 6 (1 site) | unbounded |
| `employee_max_late/overnight/weekend_load_delta` | 3 | 999999 | unbounded |
| `employee_min_preference_satisfaction_ratio` | 0.5 | 0.0 | never fires |
| `skill_allocation_audit_enabled` | True | False | audit off |
| `quality_gate_mode` | `'fail'` | `'off'` | gate off |
| `whole_week_gate_mode` | `'warn'` | `'off'` (1 of 3 sites) | gate off |
| `employee_quality_gate_mode` | `'warn'` | `'off'` (2 of 4 sites) | gate off |

**11 fields where no shadow default matches the declared one; 4 fields where
the shadow default differs between call sites.**

### Measured

```
declared default whole_week_overage_cap_ratio : 1.35
raw cap, field ABSENT (shadow default fires)  : 20
raw cap, field = declared default 1.35        : 14

declared default whole_week_max_adjacent_raw_change : 3
adjacent limit, field ABSENT                  : 999999
adjacent limit, field = declared default 3    : 3
```

### Why it is latent rather than live

`ParsedInput` is constructed in exactly one place (line 2900) and is never
deserialized, so a field is never actually absent in a production run.

### How it becomes live

1. **Test doubles.** Eight test files build `parsed` as a `SimpleNamespace`. A
   double that omits a field exercises the permissive value, so a test can pass
   on semantics the production path never uses.
2. **Any future change** making a field optional, or any resume/deserialize
   path added later, silently turns every gate permissive at once.
3. `quality_max_target_losses_from_breaks` is already inconsistent *today*: 6 at
   one call site and 999999 at eight. The same limit has two meanings in one
   file.

### Fix direction

Delete the defaults and read the attribute directly. `ParsedInput` is the
single source of truth for what a field defaults to; a second, contradictory
answer at the call site is the defect. Where a caller genuinely may receive a
partial object, that should be explicit, not implied by a permissive fallback.

---

## Also found in this pass (low severity, recorded for completeness)

* **Three dead determinism guards.** `try: solver.parameters.randomize_search =
  False / except Exception: pass` at lines 6080, 7476 and 14400. On the pinned
  OR-Tools 9.15.6755 the attribute exists, assignment cannot raise, and `False`
  is already the default — so all three `try/except` blocks and the assignment
  itself are no-ops. `cp_model_presolve = True` and `linearization_level = 1`
  beside them are also the library defaults. Harmless, but it reads as active
  determinism enforcement when the real levers are `random_seed` and
  `num_search_workers`.

* **Multi-worker nondeterminism is real and already documented** by the engine
  itself at line 17975: "The one-worker baseline is deterministic; multi-worker
  deep searches may still discover different near-optimal schedules." Not a
  defect. It does bound the method: a single-run A/B at `--num-workers 2` cannot
  resolve a one-interval effect, which is why B-4 and B-10 need repeats.

* **54 of 104 module constants** are RC-version marker flags referenced only at
  their own definition. Documentation-as-code, not a defect.

* **`minute_of_day` has an ambiguous branch.** `0 <= x < 1.00001` is read as an
  Excel time serial, `0 <= x < 1440` as raw minutes. The value `1` takes the
  first branch and becomes `00:00`, not `00:01`. Narrow, and no workbook in the
  corpus hits it.

* **`to_float` (58 call sites) silently returns its default on malformed text**,
  including for `target_ratio`, `floor_ratio` and every overage cap ratio, while
  `strict_float` (11 sites) exists precisely to avoid that and says so in its
  docstring. The same contract layer uses both conventions.
