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
