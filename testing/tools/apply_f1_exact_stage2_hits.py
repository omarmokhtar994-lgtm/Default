"""F-1: make Stage-2's coverage HIT decisions exact, keep every magnitude.

Stage-2 (`solve_breaks`) reified its target/floor/severe/full hits against an
effective factor rounded to whole percentage points (`round((1-s)*100)`) and a
threshold ceiled per quarter. On the non-terminating shrinkage in Cricut Chat
and Voice (12/130) that disagreed with the reported metric in 70 of 2,810,982
cases: the optimiser banked intervals as hit that the metric scored as missed
(11 people on a 10-FTE, 9.23%-shrinkage interval: model 1001 >= 1000, truth
99.85%), and chased intervals the metric already counted as hit.

The joint model already uses 6-decimal scaling (`scaled_effective_factor`,
`scaled_coverage_threshold`) and agrees with the metric in all 2,810,982 cases.
This builds a parallel exact expression over the SAME break variables and uses
it only where a coverage decision is made:

  * the four hit reifications (floor, severe, target, full);
  * the hard floor, when `floor_mode == "hard"`.

Every objective magnitude stays in the existing x100 units -- the deficit and
overage terms are weighted (`floor_def` 30,000 x slack) and moving them to
x1e6 would multiply their weight by 10,000 and reorder the whole objective.

`minimum_raw_target` for the overage block now uses the true effective factor,
the same formula as the verified `fractional_safe_overage_metrics`, instead of
dividing by the rounded coefficient (11 people instead of the correct 12).
"""
from __future__ import annotations

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine" / "_tools" / "l632_universal_scheduler.py"

EDITS = [
    ("exact effective factor alongside the x100 one",
     '''            req = parsed.requirements[d][i] or 0.0
            eff_person = int(round((1.0 - parsed.shrinkage[d][i]) * 100))
            interval_break_loss: List[Any] = []
            base_eff = 0''',
     '''            req = parsed.requirements[d][i] or 0.0
            eff_person = int(round((1.0 - parsed.shrinkage[d][i]) * 100))
            # F-1: coverage DECISIONS use the exact 6-decimal factor the metric
            # agrees with; eff_person (x100) is kept for the weighted deficit and
            # overage terms so no objective magnitude changes.
            eff_exact = scaled_effective_factor(parsed.shrinkage[d][i])
            interval_break_loss: List[Any] = []
            interval_break_loss_exact: List[Any] = []
            base_eff = 0
            base_eff_exact = 0'''),
    ("accumulate the exact expression over the same variables",
     '''                base_eff += (len(covering) + len(prior)) * eff_person
                interval_break_loss.extend(eff_person * var for var in break_vars)''',
     '''                base_eff += (len(covering) + len(prior)) * eff_person
                interval_break_loss.extend(eff_person * var for var in break_vars)
                base_eff_exact += (len(covering) + len(prior)) * eff_exact
                interval_break_loss_exact.extend(eff_exact * var for var in break_vars)'''),
    ("exact thresholds and exact hard floor",
     '''            after_eff = base_eff - (sum(interval_break_loss) if interval_break_loss else 0)
            floor_units = ceil_units(req * parsed.floor_ratio) * qpi
            hard_floor_units = ceil_units(req * float(parsed.hard_floor_ratio or parsed.floor_ratio)) * qpi
            target_units = ceil_units(req * parsed.target_ratio) * qpi
            units_90 = ceil_units(req * 0.90) * qpi
            units_80 = ceil_units(req * 0.80) * qpi
            full_units = ceil_units(req) * qpi
            if parsed.floor_mode == "hard":
                add_break_family(model.Add(after_eff >= hard_floor_units), "floor")''',
     '''            after_eff = base_eff - (sum(interval_break_loss) if interval_break_loss else 0)
            after_exact = base_eff_exact - (sum(interval_break_loss_exact) if interval_break_loss_exact else 0)
            floor_units = ceil_units(req * parsed.floor_ratio) * qpi
            hard_floor_units = ceil_units(req * float(parsed.hard_floor_ratio or parsed.floor_ratio)) * qpi
            target_units = ceil_units(req * parsed.target_ratio) * qpi
            units_90 = ceil_units(req * 0.90) * qpi
            units_80 = ceil_units(req * 0.80) * qpi
            full_units = ceil_units(req) * qpi
            floor_exact = scaled_coverage_threshold(req, parsed.floor_ratio, qpi)
            target_exact = scaled_coverage_threshold(req, parsed.target_ratio, qpi)
            full_exact = scaled_coverage_threshold(req, 1.0, qpi)
            severe_exact = scaled_coverage_threshold(req, max(0.0, parsed.floor_ratio - 0.10), qpi)
            if parsed.floor_mode == "hard":
                hard_floor_exact = scaled_coverage_threshold(
                    req, float(parsed.hard_floor_ratio or parsed.floor_ratio), qpi)
                add_break_family(model.Add(after_exact >= hard_floor_exact), "floor")'''),
    ("hit reifications on the exact expression",
     '''                model.Add(after_eff >= floor_units).OnlyEnforceIf(floor_hit)
                model.Add(after_eff <= floor_units - 1).OnlyEnforceIf(floor_hit.Not())
                model.Add(after_eff >= severe_units).OnlyEnforceIf(severe_hit)
                model.Add(after_eff <= severe_units - 1).OnlyEnforceIf(severe_hit.Not())
                model.Add(after_eff >= target_units).OnlyEnforceIf(target_hit)
                model.Add(after_eff <= target_units - 1).OnlyEnforceIf(target_hit.Not())
                model.Add(after_eff >= full_units).OnlyEnforceIf(full_hit)
                model.Add(after_eff <= full_units - 1).OnlyEnforceIf(full_hit.Not())''',
     '''                model.Add(after_exact >= floor_exact).OnlyEnforceIf(floor_hit)
                model.Add(after_exact <= floor_exact - 1).OnlyEnforceIf(floor_hit.Not())
                model.Add(after_exact >= severe_exact).OnlyEnforceIf(severe_hit)
                model.Add(after_exact <= severe_exact - 1).OnlyEnforceIf(severe_hit.Not())
                model.Add(after_exact >= target_exact).OnlyEnforceIf(target_hit)
                model.Add(after_exact <= target_exact - 1).OnlyEnforceIf(target_hit.Not())
                model.Add(after_exact >= full_exact).OnlyEnforceIf(full_hit)
                model.Add(after_exact <= full_exact - 1).OnlyEnforceIf(full_hit.Not())'''),
    ("overage minimum headcount from the true factor",
     '''                    minimum_raw_target = int(math.ceil(req * parsed.target_ratio * 100.0 / max(1, eff_person) - 1e-9))
                    minimum_integer_units = minimum_raw_target * eff_person * qpi
                    soft_units = max(ceil_units(req * parsed.overage_soft_cap_ratio) * qpi, minimum_integer_units)
                    over = model.NewIntVar(0, max_def, f"after_over_{d}_{i}")''',
     '''                    minimum_raw_target = int(math.ceil(
                        req * parsed.target_ratio / max(1e-9, 1.0 - parsed.shrinkage[d][i])
                        - OVERAGE_CEIL_TOLERANCE))
                    minimum_integer_units = minimum_raw_target * eff_person * qpi
                    soft_units = max(ceil_units(req * parsed.overage_soft_cap_ratio) * qpi, minimum_integer_units)
                    over = model.NewIntVar(0, max_def, f"after_over_{d}_{i}")'''),
]


def main() -> int:
    text = ENGINE.read_text(encoding="utf-8")
    for name, old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"ABORT {name}: anchor matched {count} times, expected 1")
            return 1
        text = text.replace(old, new, 1)
        print(f"applied  {name}")
    ENGINE.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
