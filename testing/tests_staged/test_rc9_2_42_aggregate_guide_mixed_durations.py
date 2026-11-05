"""Phase D3a: the aggregate day/shift guide for workbooks with mixed shift lengths.

`aggregate_pattern_mix_guidance` steers Stage-1 with day and shift-count
targets from a small MILP. It refused every workbook whose shifts were not all
540 minutes (SKIPPED_UNSUPPORTED_MIXED_PATTERN), so the public benchmark cases
(7.5-10 h shifts) ran without it. Its constraints use each shift's real length,
so the switch "Aggregate Guide Mixed Durations" lifts only that condition.

Pinned here (pre-registered in evidence/phase_d/D_PLAN.md, D3a):
  * default No: behaviour unchanged;
  * Yes on a mixed-length workbook: the guide runs and returns targets;
  * all-9 h workbooks: identical guide output with the switch on or off;
  * 11H/3OFF and non-strict OFF contracts stay out of scope either way.
"""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ENGINE)
TEMPLATE = REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx"
SWITCH = "Aggregate Guide Mixed Durations"
STABLE_KEYS = ("status", "day_work_targets", "shift_count_targets", "off_pair_targets", "off_day_targets",
               "optimistic_before_floor_hits", "optimistic_before_target_hits")


def workbook(mixed: bool, switch=None, settings=None) -> Path:
    names, langs = B.english(14)
    case = dict(id="D3A_MIXED" if mixed else "D3A_NINE", tier="test", associates=14,
                shift_starts=[8 * 60, 12 * 60], shift_minutes=540, shrinkage=0.0, interval_minutes=60,
                names=names, languages=langs, language_rules=B.ENGLISH_RULE,
                settings={"Short Break Count": 0, "Lunch Count": 0,
                          "Allowed Shift Durations Hours": "8,9" if mixed else "9"})
    if mixed:
        case["extra_shift_rows"] = [("10:00 - 18:00", "10:00", "18:00", 8.0, "8H", "test")]
    if switch is not None:
        case["settings"][SWITCH] = switch
    case["settings"].update(settings or {})
    demand = [[(3.0 if 8 <= h < 21 else None) for h in range(24)] for _ in range(7)]
    out = Path(tempfile.mkdtemp()) / (case["id"] + ".xlsx")
    B.build_workbook(TEMPLATE, out, copy.deepcopy(case), E, demand)
    return out


def guide(path: Path) -> dict:
    return E.aggregate_pattern_mix_guidance(E.parse_input(path), time_limit_sec=10.0)


class TheSwitchIsReadAndDefaultsOff(unittest.TestCase):
    def test_default_is_off(self):
        self.assertFalse(E.parse_input(workbook(True)).aggregate_guide_mixed_durations)

    def test_yes_turns_it_on(self):
        self.assertTrue(E.parse_input(workbook(True, "Yes")).aggregate_guide_mixed_durations)

    def test_a_value_that_is_neither_yes_nor_no_fails_the_contract(self):
        parsed = E.parse_input(workbook(True, "Maybe"))
        self.assertTrue(any(SWITCH.lower() in w.lower() for w in parsed.parser_warnings), parsed.parser_warnings)


class MixedLengthWorkbooks(unittest.TestCase):
    def test_off_keeps_the_old_refusal(self):
        self.assertEqual(guide(workbook(True))["status"], "SKIPPED_UNSUPPORTED_MIXED_PATTERN")

    def test_on_runs_the_guide_with_both_lengths_available(self):
        g = guide(workbook(True, "Yes"))
        self.assertIn(g["status"], ("OPTIMAL", "LIMIT_REACHED"), g)
        self.assertTrue(g.get("shift_count_targets"), g)
        self.assertEqual(sum(g["day_work_targets"].values()), 5 * 14, "strict 2 OFF: exactly 5 workdays each")

    def test_11h_3off_stays_out_of_scope(self):
        g = guide(workbook(True, "Yes", {"Use 11H/3OFF": "Yes"}))
        self.assertEqual(g["status"], "SKIPPED_UNSUPPORTED_MIXED_PATTERN")


class NineHourWorkbooksAreUnchanged(unittest.TestCase):
    def test_identical_guide_with_the_switch_on_or_off(self):
        off, on = guide(workbook(False)), guide(workbook(False, "Yes"))
        self.assertIn(off["status"], ("OPTIMAL", "LIMIT_REACHED"), off)
        for key in STABLE_KEYS:
            self.assertEqual(off.get(key), on.get(key), key)


if __name__ == "__main__":
    unittest.main()
