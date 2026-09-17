# C-1 / C-2: the contract layer fails open in two systemic ways

Found during the section-by-section evaluation of the engine (S1 foundations,
S4 contract validation). Both are the same shape as B-11 — the schedule is
computed correctly from a contract that is not what the planner wrote — and
both are invisible to the parity architecture for the same reason: the
independent validator parses the same contract.

---

## C-2 (MEDIUM — downgraded, see "What the dropdown actually covers"): an affirmative-looking cell silently disables a hard constraint

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

In reach this is wider than B-11 — B-11 loses one person's leave, this would
lose everyone's from a single cell — but B-11 is reachable today and this is
not, which is why B-11 ranks above it.

### What the dropdown actually covers — correction to my first assessment

I first rated this HIGH. That was wrong, and the reason matters.

`tools/build_input_template.py` puts a `"Yes,No"` data validation with
`errorStyle="stop"` on every one of these flags, and the shipped workbooks
carry it. Verified on AE_AR_B2B and GDI_REAL28:

| flag | on Instructions | dropdown |
|---|---|---|
| Use 11H/3OFF, Strict OFF Count, Separate OFF Days | yes | **YES** |
| Fixed Request Use, Opening Guard Enabled | yes | **YES** |
| Hard OFF Preferences, Leave Enabled, Use Preferences | yes | **YES** |

`GDI_REAL28` also has a `Legacy Instructions` sheet carrying `Leave Days`,
`Hard OFF Preferences` and `Opening Guard Enabled` as free text with no
dropdown — but that sheet is **never read**. The instruction map is built from
exactly two sheets:

```python
engine_defaults      = _instruction_map(... "Engine Defaults" ...)
visible_instructions = _instruction_map(... "Instructions" ...)
im = dict(engine_defaults); im.update(visible_instructions)
```

so `Legacy Instructions` is inert, and `Instructions` overrides
`Engine Defaults` for every flag that appears on both.

So a planner typing into Excel **cannot** produce the failure. What remains:

* Excel data validation is not enforced **on paste**, which is how a value most
  often arrives in a filled-in sheet.
* It is not enforced at all when a workbook is written **programmatically** —
  which is how every regression asset in this project is produced.
* LibreOffice and Google Sheets do not enforce it identically on import.

That makes C-2 a **defence-in-depth gap rather than a live hole**: the
dropdown is currently the only thing between a mistyped cell and a silently
removed hard constraint, and the parser underneath it has no opinion at all.
It is worth closing on that basis, not on the basis of an imminent failure.

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

---

## C-3 (HIGH): the preference vocabulary is two exact words, and everything else means "no constraint"

Found in S5 (domain rule predicates). Unlike C-2, this one has **no dropdown
and no mitigation at all**.

### The defect

`preference_kind` recognises exactly:

* blank: `""`, `none`, `planned`, `plan`, `blank`
* off: the single word `off`
* leave: the single word `leave`
* shift: any text containing two `HH:MM` tokens
* **other: everything else**

and `associate_day_eligible_shifts` — the hard availability gate — blocks on
`"off"` and `"leave"` only:

```python
if fixed_kind in {"off", "leave"}:                          return []
if parsed.leave_enabled and preference_kind_value == "leave":  return []
if parsed.hard_off and preference_kind_value == "off":         return []
```

`"other"` falls through all three. The person is schedulable.

### Measured

| preference cell | kind | blocks the day? |
|---|---|---|
| `Leave`, `leave`, ` LEAVE ` | leave | yes |
| `OFF`, `off` | off | yes |
| `Annual Leave` | other | **NO** |
| `Leave Day` | other | **NO** |
| `A/L`, `AL` | other | **NO** |
| `Vacation` | other | **NO** |
| `Sick` | other | **NO** |
| `Leave - approved` | other | **NO** |
| `Leve` (typo) | other | **NO** |
| `OFF (approved)` | other | **NO** |
| `Off Day` | other | **NO** |
| `Rest`, `RD`, `X` | other | **NO** |

No warning is emitted for any of them.

### Why there is no mitigation

The Preference sheet carries **zero data validations** in every shipped
workbook — checked across the AE inputs and the ready_inputs. Its own banner
invites free text:

> "Optional: enter Leave/OFF/shift preference by day."

So the cell is a human free-text field, the accepted vocabulary is two exact
words, and anything else is silently discarded.

### Live or latent?

**Latent today.** Scanned all 15 workbooks: **0** unrecognised preference or
fixed-schedule values. These sheets are machine-generated and write exactly
`Leave` / `OFF`.

It becomes live the first time a human types into the sheet the engine asks
them to type into — which is the sheet's entire purpose.

### Why parity cannot catch it

Same blindness as B-11 and C-2: the independent validator calls the engine's
own `preference_kind` on the same cell, agrees it is not leave, and correctly
reports that no rule was broken. Both sides are consistently wrong about the
same thing.

### Fix direction

Two parts, and the second matters more than the first:

1. Widen the vocabulary to the forms a planner actually writes (`annual
   leave`, `a/l`, `al`, `vacation`, `holiday`, `sick`, `off day`, `rest day`,
   `rd`, and the `X` marker), matched on normalized text.
2. **Stop treating `"other"` as silence.** An unrecognised, non-blank
   preference cell is a value the planner meant something by. It should raise
   a `HARD_` contract code the same way an unmatched name does under B-11, so
   the run stops and a human reconciles it. Widening the vocabulary alone just
   moves the cliff; it is step 2 that removes it.

Note the ordering interaction: B-11 makes an unmatched *name* fail closed.
C-3 is the same defect one level down — a matched name whose *value* is not
understood. Fixing B-11 without C-3 leaves the cheaper half of the hole open.
