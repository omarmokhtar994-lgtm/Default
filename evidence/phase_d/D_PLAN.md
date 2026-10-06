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
