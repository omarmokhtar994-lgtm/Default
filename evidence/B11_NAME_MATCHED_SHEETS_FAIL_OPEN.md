# B-11: a misspelled name silently deletes approved leave

What this file answers: what happens when a row in a name-matched input sheet
does not match the roster, and why neither the release gates nor the
independent validator can catch it.

This is the most consequential defect found in this work. It is not a coverage
or quality issue — it schedules people who are on approved leave.

---

## 1. The chain

Three input sheets match rows to the roster by **exact normalized name**. The
engine contains **no fuzzy or near-match helper of any kind** (0 occurrences of
`difflib`, `get_close_matches`, edit distance), so any spelling variation
between one week's workbook and the next is an exact miss.

### Preference sheet — silent, and the worst

```python
assoc = by_name.get(norm(ws.cell(r, name_col).value))
if assoc:
    assoc.preferences = [...]
#  no else. no warning. nothing.
```

Preferences are not advisory. They carry **leave** and **hard OFF**:

```python
if parsed.leave_enabled and preference_kind_value == "leave":
    return []          # this associate cannot work this day
if parsed.hard_off and preference_kind_value == "off":
    return []          # this associate cannot work this day
```

So a name typed differently from the roster means that person's **approved
leave and guaranteed OFF days are silently discarded**, they become available
to the solver, and they get scheduled. The run emits no warning, passes the
input contract, passes the production quality gate, passes independent
validation, and is marked production-eligible.

### Fixed Request — half guarded

```python
if not assoc:
    continue
...
if matched == 0:
    parser_warnings.append("Fixed/nesting sheet was present but no roster names matched.")
```

An all-or-nothing failure is caught. **One misspelled row among many is
silent.**

### Previous week scheduled — advisory only

Raises `PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE` (not `HARD_`) and ignores the row.
`associate.previous_saturday` stays `""`, and:

```python
def previous_saturday_compatible(previous_label, sunday_shift, rest_gap_hours):
    parts = shift_parts(previous_label)
    if parts is None:
        return True        # no carry-in, no constraint
```

So the Sunday rest-gap carry-in is **silently absent** and the associate can be
scheduled straight after a late Saturday they actually worked.

Note the asymmetry on this same sheet: a **duplicate** name is
`HARD_PREVIOUS_SATURDAY_DUPLICATE`, a contract failure. An **unknown** name is
an advisory. Duplicates are treated as more serious than a dropped rest
constraint.

## 2. Why nothing catches it

The release architecture is built on two independent computations agreeing —
the canonical metric surface, the parity gate, the independent validator. That
architecture catches B-8, where the two sides measured the same name
differently.

**It cannot catch this.** The independent validator parses *the same input
contract*. It sees the same absent leave, the same absent OFF, the same empty
carry-in, and it correctly concludes the schedule satisfies every rule it can
see. Both sides are consistently wrong about the same thing.

This is a defect class the parity architecture is blind to **by construction**:
parity verifies that the engine computed the contract correctly, never that the
contract is what the scheduler wrote.

## 3. Severity

| sheet | what is lost | loudness |
|---|---|---|
| **Preference** | approved **leave**, guaranteed **OFF** | **nothing at all** |
| Fixed Request | a fixed shift assignment | only if *every* row misses |
| Previous week | Sunday **rest-gap** carry-in | advisory warning |

Scheduling someone who is on approved leave is an operational and contractual
failure, not a quality metric. It is also exactly the kind of error that is
invisible until someone does not turn up.

## 4. Fix direction

The engine already has a fail-closed convention and applies it to **27**
`HARD_` codes. This should join it:

* Every name-matched sheet reports its unmatched rows.
* For sheets carrying hard constraints — Preference and Fixed Request — an
  unmatched row is a `HARD_` contract failure, consistent with those 27.
* The `Previous week scheduled` asymmetry should be resolved in the same pass:
  an unknown name there drops a rest constraint, which is not less serious than
  a duplicate.

Near-match detection would separate a typo from genuinely departed staff and
produce a better message, but it is **not required** to fix this. Reporting
unmatched rows and failing closed forces the scheduler to reconcile, which is
the safe default and needs no new matching machinery.

**One thing to check before implementing:** departed staff. If schedulers
legitimately leave last week's people on the carry-in sheet, failing closed
would block valid runs, and the fix needs an explicit way to say "this person
has left" rather than relying on silence.

## 5. What is not claimed

* **No packaged workbook is known to trigger this.** All eight parse with no
  unmatched-name warnings. The defect is in what happens when one does, and
  nothing in the pipeline would tell you.
* **Not measured against a run.** This is read from the parser and the two
  consumers of `preferences`; no schedule was produced to demonstrate it,
  because doing so means deliberately corrupting a workbook, and the code path
  is unambiguous without it.
