# Phase D: coverage quality (plan and pre-registered rules)

Written 2026-10-06 ~07:00 Egypt time, before any Phase D engine change.
Owner's instruction: keep improving the engine toward the best schedules and
coverage. Project rules (CLAUDE.md) apply unchanged: no speculative behaviour
change, failing test first, pre-registered A/B, protected baselines untouched.

## Evidence that motivates it

* Public benchmark (Bonutti et al. 2017), production settings: R10 306/504 and
  320/504, R1 552/602 and 444/602, where a 100% week is proven to exist under
  the engine's own rules (`evidence/public_benchmarks/`).
* D2a (done): the engine's own `calculate_metrics` scores the proven-perfect
  R1 skill 2 and R10 skill 1 weeks 602/602 and 504/504 with 0 break-cap
  violations (`D2A_PERFECT_PLAN_ENGINE_SCORES.json`). The metric agrees; the
  shortfall is search.
* The independent aggregated tour-pattern model (count of each legal weekly
  tour instead of per-associate variables) proves these perfect weeks in
  0.4-17 s, where the engine's per-associate search reaches 61-92% in 3,600 s.
* Real programs use 1-24 shift options (R10: 141, R1: 90), so their headroom
  is unknown, not assumed.

## Steps

| step | what | changes engine? |
|---|---|---|
| D1 | upper bound on intervals-at-target for the 7 real programs (`tools/real_program_bounds.py`), compared with the engine's latest results | no |
| D2a | engine metric on proven-perfect public weeks | no (done) |
| D2b | engine run seeded with the perfect week (`--use-input-schedule-as-seed`): does it keep it? | no |
| D2c | hint survival: fix variables to the seed hint in Stage-1 and check feasibility | no |
| D3 | aggregated tour-pattern seed inside the engine, behind a flag (default off), feeding the existing hint path | yes, flagged |
| D4 | A/B of D3 under the rule below; default-on only if it passes | yes, if passed |

## D2b reading (pre-registered)

* Seeded run ends at the perfect score (or within 1%): seeding works, so a
  better seed means a better schedule. D3 goes ahead.
* Seeded run ends well below the seed: a later stage loses coverage. D3 is
  paused and the losing stage is root-caused first (systematic-debugging).

## D4 decision rule (pre-registered, before any D3 code exists)

Arms: control = current engine; treatment = D3 flag on. Same workbook, seed
9000, QUICK 3,600 s, 2 workers, one run per arm at a time, same machine.

Cases: the 7 real ready-to-edit workbooks; public R1 skill 2, R10 skill 1;
synthetic M2, H1.

Default-on only if ALL hold:

1. Every treatment run: validator PASS, engine/validator parity PASS, hard
   failures 0, published (no new refusals).
2. Real workbooks: no workbook loses more than 1 interval at target AND no
   workbook loses more than 1 interval at floor versus control.
3. Real workbooks: the sum of intervals at target is at least the control sum.
4. Public + synthetic: the treatment closes at least 25% of the combined gap
   between control and the proven optimum (sum over the 4 cases).
5. Peak RAM no more than 20% above control on any case; wall time within the
   budget.

If 1-3 and 5 pass but 4 fails: keep the flag, default off, documented.
If 1, 2 or 5 fails: keep default off, root-cause, report.

## D3a (added 2026-10-06 ~07:15 Egypt time, before its code exists)

Finding: the engine already has an aggregate day/shift-count guide
(`aggregate_pattern_mix_guidance`, HiGHS MILP, before breaks) that steers
Stage-1 through day and shift-count targets. It refuses any workbook whose
shifts are not all 540 minutes (`SKIPPED_UNSUPPORTED_MIXED_PATTERN`). Both
scored public cases (R1, R10: 7.5-10 h shifts) ran without it. Its constraints
(per-day counts, OFF pairs or OFF days, coverage via
`shift_covers_week_qslot`) use each shift's real length, so the 540 guard
looks unnecessary while `strict_off` holds and 11H/3OFF is off.

Change: a workbook/engine switch "Aggregate Guide Mixed Durations" (default
No) that lifts only the 540-minute condition. All-9 h workbooks (every real
program, every synthetic case) take the identical code path either way.

Decision rule:
1. A test proves the 7 real workbooks and the synthetic cases get the same
   guide status and targets with the switch on and off.
2. Treatment runs on public R1 skill 2, R10 skill 1 and R5 skill 1 (switch on;
   same seed, budget and workers as the benchmark control runs, two at a time):
   validator PASS, parity PASS, 0 hard failures on every run.
3. Default becomes Yes only if the summed intervals at target over those cases
   beat the control sum and no case loses more than 1% of its active intervals.
   Otherwise the switch stays, default No, with the result documented.

## Incident log

* 2026-10-06 ~07:30 Egypt: the D3a engine commit landed while public-benchmark
  runs R5 skill 1 and 2 were in flight (started ~06:25 on the previous engine).
  The packager's identity check then refused to package R5 skill 1 ("Validated
  engine identity does not match the production manifest"); the engine result
  itself was valid (exit 0, validator PASS, 545/630 at target). The guard did
  its job; the cause was editing the engine mid-run. Both R5 cases are rerun on
  the current engine (queue1 *_RERUN), and they are the D3a control for R5.
  Rule adopted: no engine edits while a measured run is in flight.

## D2b result (2026-10-06 ~10:20 Egypt)

R10 skill 1 at its proven roster (21), production settings, seeded through
`--use-input-schedule-as-seed` with the proven-perfect week (147/147 seed cells
valid): engine exit 0, validator PASS, **504/504 at target before and after
breaks** (control run without a seed: 294 / 292). Reading (pre-registered):
seeding works, so a better seed means a better schedule. D3 goes ahead.

## D3 approach (recorded before any D3 code)

Stage 1 of D3 changes no engine file. `tools/aggregate_seed.py` builds a seed
week from a workbook alone (no published solution, no benchmark data):

1. candidate shifts = the shifts the engine's own aggregate guide gives a
   positive count (guide run with the D3a switch where shifts are mixed), so
   the tour space stays small;
2. an exact aggregated model over legal weekly tours (OFF pattern, 12 h rest,
   at most the workbook's number of different shifts) and break starts from the
   engine's own legal patterns, maximising intervals at target in the engine's
   metric (shrinkage, target, carry-in), cyclic week;
3. tours dealt to associates; the week is written into the Schedule sheet,
   which the engine reads as a seed (a hint, never a constraint).

Stage 1 scope: single-language workbooks without leave or fixed requests (the
public cases). A/B: the treatment is the same workbook plus the generated seed;
the control is the existing benchmark run. The D4 rule applies to the public
part. Real programs (languages, leave, preferences) need class-aware
aggregation (stage 2), pre-registered separately before its code.

## D3 stage-1 A/B (pre-registered 2026-10-06 ~10:50 Egypt, before any seeded run)

Seeds: `tools/aggregate_seed.py --max-shifts 10 --time-limit 160 --workers 1`
on the 11 public workbooks, from the workbook alone. Treatment: the same
workbook with the seed in its Schedule sheet, production runner, QUICK 3,600 s,
2 workers, seed 9000, two runs at a time. Control: the benchmark runs (R5: the
clean reruns on the current engine).

Promote stage 1 to engine integration (stage 2 design) only if ALL hold:
1. every treatment run: exit 0, validator PASS, 0 hard failures;
2. no case loses more than 1% of its active intervals at target vs control;
3. summed intervals at target over the 11 cases close at least 25% of the
   combined gap between control and the proven 100%.
Otherwise: document, keep as a tool, root-cause before any further step.

## D3 stage-1 verdict (2026-10-06 ~19:20 Egypt): PASS

Intervals at target after breaks, production runner, QUICK 3,600 s, 2 workers,
seed 9000; control = benchmark runs (R5: clean reruns). Data:
`D3_STAGE1_AB_RESULTS.json`.

| case | control | seeded | delta | active |
|---|---|---|---|---|
| R1 skill 1 | 554 | 602 | +48 | 602 |
| R1 skill 2 | 466 | 600 | +134 | 602 |
| R5 skill 1 | 536 | 626 | +90 | 630 |
| R5 skill 2 | 536 | 618 | +82 | 630 |
| R6 skill 1 | 526 | 644 | +118 | 644 |
| R6 skill 2 | 533 | 644 | +111 | 644 |
| R7 skill 1 | 448 | 608 | +160 | 630 |
| R7 skill 2 | 518 | 594 | +76 | 630 |
| R7 skill 3 | 522 | 610 | +88 | 630 |
| R10 skill 1 | 292 | 504 | +212 | 504 |
| R10 skill 2 | 308 | 504 | +196 | 504 |
| sum | 5,239 | 6,554 | +1,315 | 6,650 |

1. every seeded run exit 0, validator PASS, 0 hard failures: yes (11/11);
2. no case loses more than 1%: yes (no case loses at all);
3. gap closed: 1,315 of 1,411 = 93.2% (needed 25%).

Caveats, stated with the result:
* The seed costs extra compute outside the engine budget (~160 s, 1 worker,
  per case; about 4% of the 3,600 s run).
* Controls R1, R6, R7 skills 1-2, R10 ran on engine 9f91e56 (before D3a); the
  seeded runs and the other controls on 2262ac7. The difference is the D3a
  switch, default off; the treatment workbooks have it off (checked), and with
  it off the guide refuses these workbooks on both engines.
* Seeds were built before the break-cap fix (conservative cap); the A/B stands
  on those seeds.
* Scope: single-language public workbooks without leave or fixed requests.
  It says nothing yet about real programs (stage 2, below).

Next per this rule: engine integration design, pre-registered before code,
failing test first, and real programs only once a stage-2 seed beats the
engine in the model.

## D3 stage 2: real programs (pre-registered 2026-10-06 ~11:00 Egypt, before its code)

Real workbooks add, per `real profile` (7 ready-to-edit workbooks): leave and
hard-OFF days (e.g. AE_AR_B2B 13 leave, 20 hard OFF), fixed shifts and fixed
OFF (Cricut Voice 75 + 30, NMG EN 150 + 60), language minimums (GDI UK and
Bilingual/French, NMG EN+SP Spanish, single-language English minimum 1
elsewhere), carry-in on up to 21 associates, separate OFF days (Voice), and
2-3 different shifts per week.

Design (tool only, no engine change):
* associates grouped by signature (language, per-day availability from leave
  / hard OFF / fixed cells, fixed shift cells, last Saturday's shift);
* each group gets only the tours it may legally work (its OFF rule, its fixed
  cells, its unavailable days, rest after its own carry-in, at most the
  workbook's number of different shifts, capped at 2 for the seed);
* candidate shifts from the engine's aggregate guide plus every fixed shift;
* integer count per (group, tour); break counts per (language class, day,
  shift, pattern); language minimums enforced on on-floor eligible heads;
  shortfall-first then intervals-at-target, the engine's metric;
* groups dealt to their own associates.

A/B (real programs): control = current engine without a seed; treatment = same
workbook with the stage-2 seed. Production runner, QUICK 3,600 s, 2 workers,
seed 9000, two runs at a time, all 7 real workbooks. Rule = D4 items 1, 2, 3, 5:
1. every treatment run exit 0, validator PASS, parity PASS, 0 hard failures,
   no new refusal;
2. no workbook loses more than 1 interval at target AND none loses more than 1
   interval at floor versus its control;
3. summed intervals at target over the 7 is at least the control sum;
5. peak RAM within 20% of control, wall time within budget.
Before any A/B: if the seed model's own predicted intervals-at-target are not
above the engine's latest result for a workbook, that workbook is reported as
"no headroom found" and the A/B still runs (to test for harm).

* 2026-10-06 ~11:35 Egypt, before any seeded run: reading the engine's Stage-1
  model showed it also enforces rest from Saturday to the same week's Sunday
  (cyclic). The seed builder only checked Sunday-Saturday, so seeds could hold
  tours the engine rejects. Fixed (the check now wraps) and all 11 seeds
  regenerated before queue2 started: 10 OPTIMAL at the model bound, R10 skill 2
  498/504. queue2 holds only the regenerated seeds.

## D3 stage 2 first trials (2026-10-06 ~12:15 Egypt; tool only, low priority, 1 worker)

`tools/aggregate_seed_real.py` (experimental). Seeds load cleanly (0 invalid
cells) but are not yet better than the engine:
* NMG SP: seed model 112/126 vs engine ~121 (no headroom found);
* Cricut Chat, per-associate variant: 112/242; grouped variant (4 groups,
  1,390 legal tours, soft break cap): 113/242, vs engine 174-178 (C4 control).
Not a modelling error proven either way: both solves stopped FEASIBLE at the
time limit with the solver at the lowest priority beside two engine runs, and
the seed restricts variety to 2 and candidates to the guide's 12 shifts.
Paused until the machine is free and the stage-1 A/B has reported. No real
workbook A/B runs until a seed beats the engine's own result in the model.

## D3 stage 2 root cause (2026-10-06 ~16:45 Egypt; tools only, engine untouched)

Investigated with systematic-debugging, read-only/low priority beside queue2.
* The engine's Cricut Chat week (C4 control, seed 9000: 191 before / 176
  after breaks) is outside the seed model's search space: 42 of its 128
  shift-days use shifts outside the 12 guide candidates, and 19 of 27
  associates work 3 different shifts (workbook limit 3; grouped seed cap 2).
* Pinned to that week (new diagnostic `--fix-week-from`, `--all-shifts`), the
  seed model scored it 126 after breaks, while its own coverage formula gives
  191 before breaks (= engine). The model's coverage is right; its breaks
  were wrong.
* Root cause: the seed models' concurrent-break cap was `ratio x staffed`
  only. The engine's `maximum_concurrent_breaks` guarantees one break from 2
  staffed heads: min(staffed - 1, max(1, floor(ratio x staffed)),
  max(1, absolute)). At ratio 0.3 the seed forbade every break with 2-3 heads
  on floor (night hours), and with ratio 1.0 it allowed everyone on break.
  Same formula in all three sites (stage-1 tool, both stage-2 variants).
* Fix: one shared `add_break_cap` in `tools/aggregate_seed.py`, exact to the
  engine's rule. Failing first: `tests_staged/test_rc9_2_44_seed_break_cap.py`
  (28 mismatches before the fix, `scratchpad` red log), green after.
  The diagnostic options were written before a test (disclosed).
* queue2 (stage-1 A/B) is unaffected: its seeds were generated before this
  fix, from the conservative cap, and the A/B stands on those seeds.
* Next, after queue2 (no CPU contention with measured runs): re-score the
  pinned engine week (expect ~176), then the full-CPU Chat seed trial with all
  shifts and the workbook's variety limit.

### Correction and second finding (2026-10-06 ~18:30 Egypt)

The entry above overstated the break cap as "the" root cause. Measured since:
* With the exact cap (reified encoding) the pinned-week solve returned UNKNOWN
  in 120 s (1 worker): the cap was right but the encoding hurt search. Re-encoded
  as a table lookup on the staffed count (`engine_break_cap` + `AddElement`);
  the cap test stays green (same oracle: the engine's function).
* Pinned week, table cap, 1 worker, 120 s per phase: 132 after breaks (was 126).
* The engine's own week and breaks checked against the seed model without a
  solver: 128/128 person-day break sets are legal seed patterns, 0 quarters over
  the cap, and the model's formula scores it 176 = the engine. So the model now
  contains the engine's solution at the same score.
* Therefore: cap = real modelling bug (the old cap made the engine's week
  infeasible in the seed model); the remaining 132 vs 176 is search (1 worker:
  no LNS; ~19k break-count variables). Next: the same pinned solve with 2-4
  workers and the engine solution as a hint, then the free-week trial.

### Full-CPU trials (2026-10-06 ~19:25-20:10 Egypt, machine free)

* Pinned engine Chat week, table cap, 4 workers, 240 s per phase: phase 2 found
  break placements the model scores at 180 after breaks (engine shipped 176 for
  the same week). Lead only: the model's breaks are not exported or checked by
  `calculate_metrics` and the validator yet. Peak RSS 1.1 GB.
* Free week (all 24 shifts, workbook variety limit, exact cap), 4 workers,
  900 s phase 1: UNKNOWN, no seed (peak RSS 1.7 GB). Finding any valid week is
  the hard part: every shift needs a legal break under a per-quarter cap.
  Third search failure on this model, so no more tweaks of the free search.
* Next experiment: the same model warm-started from the engine's week as a
  hint only (`--week-mode hint`), i.e. "improve the engine's week" rather than
  "build a week from nothing". Written before a test (experimental tool option,
  disclosed).

## D3a verdict (2026-10-06 ~13:20 Egypt)

Intervals at target after breaks, production settings, control = same
workbook with the switch off on the current engine behaviour (R5: clean rerun):

| case | control | switch on | delta | active | loss > 1%? |
|---|---|---|---|---|---|
| R10 skill 1 | 292 | 278 | -14 | 504 | yes (2.8%) |
| R1 skill 2 | 466 | 462 | -4 | 602 | no (0.7%) |
| R5 skill 1 | 536 (rerun) | 554 | +18 | 630 | no |
| sum | 1,294 | 1,294 | 0 | | |

All runs exit 0, validator PASS. Rule 3 needs the sum to beat control (it ties)
and no case to lose more than 1% (R10 loses 2.8%). **Verdict: the switch stays,
default No.** Reading: a before-break count target helps one case and hurts
another; it is not a reliable signal. The seeded runs (D3 stage 1) test a
different signal, a complete break-aware week.
