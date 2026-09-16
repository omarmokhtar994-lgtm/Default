# B-7: the workbook had no route to the parameters that shape the search

What this file answers: which engine parameters a scheduler working from the
workbook could not reach, why adding workbook rows alone would not have fixed
it, and the proof that nothing already shipping changed.

Engine lineage: RC5 + P-1 + C-1 + capacity gate + stage-aware gates + this
change.

---

## 1. The defect

The engine is designed to be workbook-driven. 71 command-line options exist;
after excluding paths and invocation mechanics (`--input`, `--overwrite`,
`--selfcheck`, the fallback workbooks, the dev smoke flag), **43 behavioural
parameters had no workbook row at all**: search shape, reserve budgets, the
quality minimums, and the solver seed.

There is a second half to the defect that matters more than the first. The
production runner passes a value for **24 of them on every run**:

```
--num-workers --pattern-widths --repair-change-limits --skeleton-profiles
--break-objective-modes --min-after90-gain-per-after80-loss
--max-after80-tradeoff-intervals --adaptive-no-improvement-attempts
--primary-target-tolerance --exception-search-reserve-sec ... --solver-random-seed
```

Those values are the runner's own defaults and its depth arithmetic, not
anything a scheduler chose. On a command line a default is indistinguishable
from a typed argument, so **adding workbook rows would have achieved nothing**:
the runner's opinion would have silently outranked the business contract on
every run.

This is not only a convenience gap. B-3 is an instance of it: the Stage-1
portfolio is 15 profiles because the runner hardcodes 15, and at 900s the
budget funds **0 of them**. A workbook-driven user had no way to say "run four
profiles properly instead of fifteen not at all".

## 2. What was changed

**Precedence** is the rule the protected-tier minimums already followed:

```
explicit command line  >  workbook  >  engine default
```

A parameter neither side sets keeps exactly the value it had before this route
existed. That is the whole behaviour-preservation argument, and it rests on
being able to tell "absent" from "set to the default".

* **`WORKBOOK_SEARCH_CONTROLS`** — 43 parameters with their workbook aliases
  and types. `_parse_search_controls` returns only what the workbook actually
  states. A row that is present but unreadable emits
  `HARD_INVALID_SEARCH_CONTROL` and fails the contract, rather than falling
  back to a default: a scheduler who typed a value into the business contract
  must not have it silently discarded.
* **`explicitly_supplied_options`** — argparse skips a default for any
  attribute already on the namespace it is handed, so pre-seeding every
  destination with `None` leaves unset options as `None`. This is what makes
  "typed at the default value" distinguishable from "not typed". It uses
  `parse_known_args`, never `parse_args`: a probe must not be the thing that
  terminates the process.
* **The runner stands aside.** `engine_flags_for_run` drops a flag when the
  workbook states that parameter — unless the operator typed it on the
  runner's own command line. For the 18 flags the runner computes from its
  depth and exposes no option for, the workbook always wins, because there is
  nothing an operator could have typed.
* **`search_control_decisions`** in the audit records every control that was
  set and which side won. A run that behaves unexpectedly is otherwise
  indistinguishable from one configured unexpectedly.

`strict_bool` was added rather than reusing `yes()`: `yes()` reads anything
unrecognized as False, which is right for a legacy contract row and wrong
here, where a typo would silently disable a search phase.

## 3. Proof that nothing already shipping changed

**The engine command is byte-identical when the workbook is silent.** The old
runner's flag list was lifted from its own source and executed against the
same arguments and depth defaults, then compared with the new one:

```
old pairs: 24   new pairs: 24
VALUE DIFFERENCES: none - byte-identical
```

(The only difference is that `--solver-random-seed` now appears last in the
list. argparse is order-independent.)

**The canonical contract hash is unchanged on every workbook available** — the
8 packaged inputs and the 6 AE workbooks:

```
workbooks: 14 | contract hash changed on: 0 | search_controls: {} on all 14
```

No shipped workbook states any of these rows, so no shipped workbook changes
behaviour.

**Search controls are deliberately not part of the canonical contract.** The
contract answers "what must this schedule satisfy"; how hard to search for it
is not part of that question, so two workbooks differing only in search shape
are the same contract. The run's own choices live in the audit instead. Pinned
by `test_search_controls_are_not_part_of_the_coverage_contract` so it stays a
decision rather than an accident.

## 4. Proof that the route actually works

`AE_FR_Choice` with three rows added to Engine Defaults, run through the whole
runner at 240s:

```
[run] workbook states 3 search control(s):
      joint_patterns_per_shift, skeleton_profile_names, solver_random_seed
```

The runner dropped `--solver-random-seed`, `--skeleton-profiles` and
`--joint-patterns-per-shift` from the engine command and kept the other 21.
From the audit:

| control | value | source |
|---|---|---|
| `solver_random_seed` | **4242** | **workbook** |
| `skeleton_profile_names` | **2 profiles** | **workbook** |
| `joint_patterns_per_shift` | **32** | **workbook** |
| the other 24 | runner values, unchanged | command_line |

`run_parameters.solver_random_seed = 4242` — the runner's own 9000 stood down.
`requested_skeleton_profiles` is the workbook's two, not the runner's fifteen.
Run: `return_code 0`, validation `PASS`, metric parity `PASS`.

Both sheet layouts work: label/value in columns 1-2, and the sheet's real
`Section | Instruction | Value` shape in columns 2-3.

A bad value fails closed:

```
Coordinated Repair Cycles = "three"
  -> HARD_INVALID_SEARCH_CONTROL
  -> input contract status: FAIL
```

## 5. Tests

`tests/test_rc9_2_4_workbook_search_controls.py` — 34 tests.

| Class | Pins |
|---|---|
| `ParsingWhatTheWorkbookStates` | absent means absent; every type parses; an unreadable row is a contract failure, not a default |
| `TheTablesCannotDriftApart` | every control names a real `run_case` parameter and a real argparse destination, both directions; no alias claimed twice |
| `TellingATypedFlagFromADefault` | a flag typed at its default counts as typed; detection does not disturb the real parse |
| `TranslatingTypedFlagsToEngineValues` | `--disable-X` becomes the capability off; list splitting; an empty list flag is not a choice |
| `PrecedenceInsideRunCase` | the command line is applied after the workbook; every control falls back to the value `run_case` was called with; pattern widths are normalized after the workbook is read |
| `TheRunnerStandsAsideForTheWorkbook` | a silent workbook leaves all 24 flags exactly as they were; a stated control drops the runner's value; a typed flag still outranks the workbook; the runner's depth arithmetic always yields |
| `PackagedWorkbooksAreUnaffected` | no packaged workbook states a control or raises a warning; controls are not part of the coverage contract |

Full gate: **16 suites, 580 tests, PASS.**

## 6. What is *not* claimed

* **No scheduling decision changed.** Every default is where it was; this adds
  a way to state a different one.
* **These are advanced controls.** The Engine Defaults sheet says so in its own
  header: "Change these only with a specific reason. They are not per-schedule
  business settings." Nothing here makes a bad value safe — it makes it
  *reachable*, and makes an unreadable one fail loudly.
* **`--num-workers` remains machine-dependent.** It is routed for completeness,
  but a workbook that pins it will behave differently on different hardware.
* **This does not fix B-3.** It removes the reason B-3 could not be worked
  around from the workbook, and gives the B-3 measurement a way to vary the
  portfolio without editing the runner.
