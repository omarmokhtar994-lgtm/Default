"""Phase C4 of the production-readiness audit (F-28): optional volume-weighted coverage.

Every interval used to weigh the same in the search and the selector, so a
1-FTE interval and a 30-FTE interval counted alike. A workbook may now choose

    Coverage Objective Weighting = Volume Weighted

so that an interval's miss weighs in proportion to its requirement, and the
selector ranks first by the requirement covered at target. The default stays
"Interval Count", and with it every model is unchanged. Making volume weighting
the default needs the end-to-end A/B registered in
evidence/production_readiness_audit/phase_c/C4_RULE.txt.

Written to FAIL on the engine before C4 and pass after.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import l632_universal_scheduler as E  # noqa: E402
import phase_a_workbooks as W  # noqa: E402

# One associate, Monday only: a long thin window (06-15, 0.5 FTE: 9 intervals,
# 4.5 FTE in all) and a short thick one (15-21, 0.85 FTE: 6 intervals, 5.1 FTE).
# One shift can cover one. Stage 1 counts PRODUCTIVE coverage (a 9-hour shift
# less its breaks, about 0.89 FTE), so the thick window is set where one person
# still reaches the 90 % target (0.85 x 0.9 = 0.765): both windows are fully
# coverable and only the weighting decides.
TWO_WINDOWS = dict(
    roster=[("Agent A", "English")], shifts=["06:00 - 15:00", "15:00 - 00:00"],
    demand=lambda d, m: (0.5 if 6 * 60 <= m < 15 * 60 else 0.85 if 15 * 60 <= m < 21 * 60 else None) if d == 1 else None,
    instructions={"Count of Associates": 1, "Rest Gap Hours": 8},
)


def build(spec):
    path = Path(tempfile.mkdtemp()) / "case.xlsx"
    W.build(spec, path)
    parsed = E.parse_input(path)
    codes = {f.get("code") for f in E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))["failures"]}
    return parsed, codes


def weighting(value):
    spec = dict(TWO_WINDOWS)
    spec["instructions"] = dict(TWO_WINDOWS["instructions"], **{"Coverage Objective Weighting": value})
    return spec


class C4Switch(unittest.TestCase):
    def test_the_default_is_interval_count_and_weights_are_untouched(self):
        parsed, _ = build(TWO_WINDOWS)
        self.assertEqual(parsed.coverage_objective_weighting, "interval_count")
        self.assertEqual(E.volume_weight(parsed, 1000, 1, 18), 1000)

    def test_volume_weighted_is_read_and_scales_by_requirement(self):
        parsed, codes = build(weighting("Volume Weighted"))
        self.assertEqual(parsed.coverage_objective_weighting, "volume_weighted")
        mean = (9 * 0.5 + 6 * 0.85) / 15
        self.assertEqual(E.volume_weight(parsed, 700, 1, 18), round(700 * 0.85 / mean))
        self.assertEqual(E.volume_weight(parsed, 700, 1, 8), round(700 * 0.5 / mean))

    def test_an_unknown_value_is_refused(self):
        _, codes = build(weighting("Revenue"))
        self.assertIn("HARD_INVALID_COVERAGE_OBJECTIVE_WEIGHTING", codes)

    def test_the_setting_is_in_the_contract_fingerprint(self):
        a, _ = build(TWO_WINDOWS)
        b, _ = build(weighting("Volume Weighted"))
        self.assertNotEqual(E.canonical_hash(E.canonical_contract_snapshot(a)),
                            E.canonical_hash(E.canonical_contract_snapshot(b)))


class C4Effect(unittest.TestCase):
    def monday_shift(self, parsed):
        profile = E.skeleton_profiles(["target_priority_balanced"])[0]
        sk = E.build_skeleton(parsed, profile, E.HardConfig(zero_active=False), 20, 1, io.StringIO())
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        return sk.assignment[0][1]

    def test_interval_count_covers_more_intervals(self):
        parsed, _ = build(TWO_WINDOWS)
        self.assertEqual(self.monday_shift(parsed), "06:00 - 15:00")

    def test_volume_weighting_covers_more_requirement(self):
        parsed, _ = build(weighting("Volume Weighted"))
        self.assertEqual(self.monday_shift(parsed), "15:00 - 00:00")

    def test_the_selector_leads_with_covered_requirement_only_when_chosen(self):
        parsed, _ = build(weighting("Volume Weighted"))
        m = {"after_target": 9, "after_target_volume_fte": 4.5, "active_intervals": 15}
        n = {"after_target": 6, "after_target_volume_fte": 5.1, "active_intervals": 15}
        self.assertGreater(E._candidate_quality_tuple(parsed, n, "after"), E._candidate_quality_tuple(parsed, m, "after"))
        default, _ = build(TWO_WINDOWS)
        self.assertGreater(E._candidate_quality_tuple(default, m, "after"), E._candidate_quality_tuple(default, n, "after"))


if __name__ == "__main__":
    unittest.main()
