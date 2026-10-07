"""Phase E, F-E1: Stage 1 and the aggregate guide decide "hit" exactly as the metric does.

calculate_metrics: an interval is hit when (eff x head-quarters / qpi) / req +
1e-9 >= ratio. Stage 1 and the guide compared round(eff x 100) x head-quarters
with ceil(req x ratio x 100) x qpi, which disagrees on up to 8 thresholds per
real program (evidence/phase_e/ENGINE_MODEL_REVIEW.md, F-E1). With the switch
"Exact Coverage Units" the threshold is c x n*, c = round(eff x 100) (the
coefficient every head carries in that interval) and n* the metric's minimum
head-quarters, so "c x heads >= threshold" holds exactly when the metric hits.
Magnitudes stay in the same units, so objective weights are unchanged.

Pinned here: default off and legacy thresholds unchanged; on, every real
interval agrees with the metric; hand-checked literal cases; eff 0 stays
unreachable; qpi 1, 2 and 4.
"""
import copy
import math
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
READY = REPO / "packages" / "rc9_2_2_production" / "inputs" / "ready_to_edit"
SWITCH = "Exact Coverage Units"


def metric_min_head_quarters(req, eff, qpi, ratio):
    """Smallest n with (eff * n / qpi) / req + 1e-9 >= ratio (calculate_metrics' test)."""
    n = 0
    while (eff * n / qpi) / req + 1e-9 < ratio:
        n += 1
    return n


def min_heads_for(threshold, c):
    return 0 if threshold <= 0 else -(-threshold // c)


def stub(req, shrink, qpi, exact):
    return types.SimpleNamespace(requirements=[[req]], shrinkage=[[shrink]], qslots_per_interval=qpi,
                                 exact_coverage_units=exact)


class TheSwitchDefaultsOffAndChangesNothingThen(unittest.TestCase):
    def test_default_off_on_every_ready_workbook(self):
        for wb in sorted(READY.glob("*.xlsx")):
            with self.subTest(workbook=wb.name):
                self.assertFalse(E.parse_input(wb).exact_coverage_units)

    def test_legacy_units_are_unchanged_when_the_switch_is_off(self):
        for req, shrink, qpi, ratio in ((10.0, 0.0923, 2, 1.0), (8.7, 0.13, 2, 0.75), (2.9, 0.13, 4, 0.8), (1.5, 0.25, 1, 0.8)):
            p = stub(req, shrink, qpi, False)
            self.assertEqual(E.coverage_hit_threshold_units(p, 0, 0, ratio), E.ceil_units(req * ratio) * qpi)


class ExactUnitsAgreeWithTheMetric(unittest.TestCase):
    def test_hand_checked_chat_monday_1730(self):
        # 10 FTE, shrinkage 9.23 %: metric needs 23 head-quarters (22 gives 9.985 FTE).
        p = stub(10.0, 0.0923, 2, True)
        self.assertEqual(E.coverage_hit_threshold_units(p, 0, 0, 1.0), 91 * 23)

    def test_hand_checked_exact_tie_counts_as_a_hit(self):
        # 8.7 FTE, shrinkage 13 %, ratio 0.75: 15 head-quarters give exactly 6.525 = 0.75 x 8.7.
        p = stub(8.7, 0.13, 2, True)
        self.assertEqual(E.coverage_hit_threshold_units(p, 0, 0, 0.75), 87 * 15)

    def test_every_real_interval_target_and_floor(self):
        for wb in sorted(READY.glob("*.xlsx")):
            p = copy.copy(E.parse_input(wb))
            p.exact_coverage_units = True
            qpi = p.qslots_per_interval
            for ratio in (p.target_ratio, p.floor_ratio):
                for d in range(7):
                    for i in range(p.intervals_per_day):
                        req = float(p.requirements[d][i] or 0.0)
                        eff = 1.0 - float(p.shrinkage[d][i])
                        if not p.active[d][i] or req <= 0 or eff <= 0:
                            continue
                        c = int(round(eff * 100))
                        got = min_heads_for(E.coverage_hit_threshold_units(p, d, i, ratio), c)
                        with self.subTest(workbook=wb.name, ratio=ratio, day=d, interval=i):
                            self.assertEqual(got, metric_min_head_quarters(req, eff, qpi, ratio))

    def test_qpi_1_and_4(self):
        for qpi in (1, 4):
            p = stub(3.3, 0.17, qpi, True)
            c = int(round(0.83 * 100))
            self.assertEqual(min_heads_for(E.coverage_hit_threshold_units(p, 0, 0, 0.9), c),
                             metric_min_head_quarters(3.3, 0.83, qpi, 0.9))

    def test_zero_effective_capacity_stays_unreachable(self):
        p = stub(5.0, 1.0, 2, True)
        self.assertGreater(E.coverage_hit_threshold_units(p, 0, 0, 0.8), 0)


class TheSwitchIsAnInstruction(unittest.TestCase):
    def _workbook(self, value=None):
        names, langs = B.english(8)
        settings = {"Short Break Count": 0, "Lunch Count": 0}
        if value is not None:
            settings[SWITCH] = value
        case = dict(id="E2_SWITCH", tier="test", associates=8, shift_starts=[8 * 60], shift_minutes=540,
                    shrinkage=0.0, interval_minutes=60, names=names, languages=langs,
                    language_rules=B.ENGLISH_RULE, settings=settings)
        demand = [[(2.0 if 8 <= h < 17 else None) for h in range(24)] for _ in range(7)]
        out = Path(tempfile.mkdtemp()) / "E2_SWITCH.xlsx"
        B.build_workbook(REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx", out, case, E, demand)
        return out

    def test_yes_turns_it_on_and_the_contract_records_it(self):
        p = E.parse_input(self._workbook("Yes"))
        self.assertTrue(p.exact_coverage_units)
        self.assertTrue(E.input_contract_payload(p).get("exact_coverage_units"))

    def test_absent_switch_leaves_the_contract_without_the_key(self):
        p = E.parse_input(self._workbook())
        self.assertNotIn("exact_coverage_units", E.input_contract_payload(p))


if __name__ == "__main__":
    unittest.main()
