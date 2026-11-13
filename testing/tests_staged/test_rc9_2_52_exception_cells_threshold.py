"""Phase G, task 5: hard-floor exception cells use the metric's exact threshold.

Phase E ledger ruling (2026-10-06): with "Exact Coverage Units" = Yes,
build_skeleton measures hits as c x n* (coverage_hit_threshold_units), but
critical_exception_cells still compared against ceil(req x ratio x 100) x qpi,
which can disagree with calculate_metrics by one head-quarter. It now uses the
same helper; with the switch off the helper returns the old expression, so
default output is unchanged.

Case (hourly interval, qpi 4, shrinkage 0.125 so c = 88, requirement 1.92,
hard floor 80%, two heads on one shift): one head-quarter less leaves 7
head-quarters, coverage 0.875 x 7 / 4 / 1.92 = 0.797 < 0.8, a real floor
miss. The legacy units (616 >= 154 x 4) say the cell is safe; the exact units
(616 < 88 x 8) say it is critical.
"""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
TEMPLATE = REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx"
MON, HOUR = 1, 10


def parsed_case(exact: bool):
    names, langs = B.english(4)
    case = dict(id="G5_CELLS", tier="test", associates=4, shift_starts=[8 * 60], shift_minutes=540,
                shrinkage=0.0, interval_minutes=60, names=names, languages=langs,
                language_rules=B.ENGLISH_RULE, settings={"Short Break Count": 0, "Lunch Count": 0})
    demand = [[(1.0 if 8 <= h < 17 else None) for h in range(24)] for _ in range(7)]
    out = Path(tempfile.mkdtemp()) / "G5.xlsx"
    B.build_workbook(TEMPLATE, out, copy.deepcopy(case), E, demand)
    p = E.parse_input(out)
    p.floor_mode = "hard"
    p.hard_floor_ratio = 0.80
    p.opening_guard_enabled = False
    p.exact_coverage_units = exact
    p.requirements = [list(day) for day in p.requirements]
    p.shrinkage = [list(day) for day in p.shrinkage]
    p.requirements[MON][HOUR] = 1.92
    p.shrinkage[MON][HOUR] = 0.125
    return p


def two_heads_monday(p):
    shift = next(s.index for s in p.shifts if s.start_min == 8 * 60)
    picks = [[None] * 7 for _ in p.associates]
    picks[0][MON] = shift
    picks[1][MON] = shift
    return E.SkeletonSolution("test", "FEASIBLE", 0.0, 0.0, [[""] * 7 for _ in p.associates], picks, {})


def floor_reasons_at_ten(p):
    _, reasons = E.critical_exception_cells(p, two_heads_monday(p))
    return [r for r in reasons if "hard floor" in r["rule"] and "Mon 10:" in r["rule"]]


class ExactUnitsMarkTheRealFloorMiss(unittest.TestCase):
    def test_metric_agrees_the_cell_is_tight(self):
        # The premise: 7 head-quarters miss the 80% floor at this interval.
        self.assertLess(0.875 * 7 / 4 / 1.92, 0.80)
        self.assertGreaterEqual(0.875 * 8 / 4 / 1.92, 0.80)

    def test_switch_on_uses_exact_threshold(self):
        self.assertTrue(floor_reasons_at_ten(parsed_case(exact=True)))


class DefaultIsUnchanged(unittest.TestCase):
    def test_switch_off_cells_unchanged(self):
        # Legacy units: 2 x 88 x 4 - 88 = 616 >= ceil(1.92 x 0.8 x 100) x 4 = 616.
        self.assertEqual(floor_reasons_at_ten(parsed_case(exact=False)), [])


if __name__ == "__main__":
    unittest.main()
