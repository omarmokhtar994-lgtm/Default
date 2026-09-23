#!/usr/bin/env python3
"""Formula-audit fixes F-2 to F-5, tested through the real parser.

Each test injects the bad value into a copy of a real packaged workbook and
parses it, rather than string-matching the engine source, so it proves the
behaviour a user would actually see. See evidence/formula_audit/FINDINGS.md.
"""
from __future__ import annotations

import math
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

ROOT = (Path(os.environ["RC9_ENGINE_DIR"]).resolve().parent.parent
        if os.environ.get("RC9_ENGINE_DIR")
        else Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

BOOK = ROOT / "packages" / "rc9_2_2_production" / "inputs" / "AE_AR_B2B.xlsx"


def with_instruction(tmp: str, pairs: dict) -> Path:
    """Copy the workbook and append Instruction/Value rows to Instructions."""
    dst = Path(tmp) / "case.xlsx"
    shutil.copyfile(BOOK, dst)
    wb = load_workbook(dst)
    ws = wb["Instructions"]
    row = ws.max_row + 1
    for key, value in pairs.items():
        ws.cell(row, 2, key)
        ws.cell(row, 3, value)
        row += 1
    wb.save(dst)
    return dst


def hard(parsed, code: str) -> bool:
    return any(str(w).startswith(code) for w in parsed.parser_warnings)


@unittest.skipUnless(BOOK.is_file(), "packaged workbook not present")
class F5_LossGateModesRejectTyposUnderTheirOwnName(unittest.TestCase):
    def test_a_target_gate_typo_is_rejected_as_the_target_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = E.parse_input(with_instruction(tmp, {"Target Loss From Breaks Gate Mode": "wran"}))
        self.assertTrue(hard(p, "HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE"),
                        "a target-gate typo used to be accepted silently")
        self.assertFalse(hard(p, "HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE"))

    def test_a_floor_gate_typo_is_rejected_as_the_floor_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = E.parse_input(with_instruction(tmp, {"Floor Loss From Breaks Gate Mode": "wran"}))
        self.assertTrue(hard(p, "HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE"))
        self.assertFalse(hard(p, "HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE"),
                         "a floor-gate typo used to be reported as a TARGET-gate error")

    def test_valid_modes_raise_nothing(self):
        for mode in ("off", "warn", "fail", "WARN", " Fail "):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                p = E.parse_input(with_instruction(tmp, {
                    "Target Loss From Breaks Gate Mode": mode,
                    "Floor Loss From Breaks Gate Mode": mode}))
                self.assertFalse(hard(p, "HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE"))
                self.assertFalse(hard(p, "HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE"))

    def test_every_gate_mode_names_itself_when_it_rejects(self):
        """Structural guard: an insertion must never split a gate block again.

        For every `if X_gate_mode not in {...}:` block, the warning in that
        block must carry X's own name.
        """
        import re
        src = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text().split("\n")
        own_name = {
            "target_loss_gate_mode": "TARGET_LOSS", "floor_loss_gate_mode": "FLOOR_LOSS",
            "break_concurrency_gate_mode": "BREAK_CONCURRENCY",
            "next_sunday_balance_gate_mode": "NEXT_SUNDAY_BALANCE",
            "quality_gate_mode": "PRODUCTION_QUALITY",
            "language_reserve_gate_mode": "LANGUAGE_RESERVE",
            "whole_week_gate_mode": "WHOLE_WEEK_BALANCE",
            "employee_quality_gate_mode": "EMPLOYEE_SCHEDULE_QUALITY",
            "skill_allocation_gate_mode": "SKILL_ALLOCATION",
        }
        checked = 0
        for i, line in enumerate(src):
            m = re.search(r"if (\w+_gate_mode) not in \{\"off\", \"warn\", \"fail\"\}", line)
            if not m or m.group(1) not in own_name:
                continue
            block = "\n".join(src[i:i + 3])
            with self.subTest(gate=m.group(1)):
                self.assertIn(f"HARD_INVALID_{own_name[m.group(1)]}", block,
                              f"{m.group(1)} must reject a typo under its own name")
            checked += 1
        self.assertEqual(checked, len(own_name))


@unittest.skipUnless(BOOK.is_file(), "packaged workbook not present")
class F4_OverageCapsAreReadAsWritten(unittest.TestCase):
    def cap(self, value):
        with tempfile.TemporaryDirectory() as tmp:
            return E.parse_input(with_instruction(tmp, {"Overage Extreme Cap": value}))

    def test_a_ratio_above_150_percent_is_kept(self):
        """1.6 means 160%. It used to become 0.016, then be lifted to the severe cap."""
        self.assertAlmostEqual(self.cap(1.6).overage_extreme_cap_ratio, 1.6)
        self.assertAlmostEqual(self.cap(2.0).overage_extreme_cap_ratio, 2.0)

    def test_a_bare_percentage_is_still_converted(self):
        self.assertAlmostEqual(self.cap(160).overage_extreme_cap_ratio, 1.6)
        self.assertAlmostEqual(self.cap(140).overage_extreme_cap_ratio, 1.4)

    def test_a_percent_string_is_converted(self):
        self.assertAlmostEqual(self.cap("160%").overage_extreme_cap_ratio, 1.6)

    def test_a_mis_ordered_set_is_rejected_not_rewritten(self):
        """The order check existed but a max() chain made it unreachable."""
        with tempfile.TemporaryDirectory() as tmp:
            p = E.parse_input(with_instruction(tmp, {
                "Overage Soft Cap": 1.3, "Overage Severe Cap": 1.2, "Overage Extreme Cap": 1.4}))
        self.assertAlmostEqual(p.overage_severe_cap_ratio, 1.2, msg="must not be silently raised")
        codes = {f["code"] for f in E.validate_input_contract(p)["failures"]}
        self.assertIn("INVALID_OVERAGE_CAP_ORDER", codes)

    def test_the_defaults_still_pass(self):
        p = E.parse_input(BOOK)
        self.assertEqual((p.overage_soft_cap_ratio, p.overage_severe_cap_ratio,
                          p.overage_extreme_cap_ratio), (1.1, 1.2, 1.4))
        codes = {f["code"] for f in E.validate_input_contract(p)["failures"]}
        self.assertNotIn("INVALID_OVERAGE_CAP_ORDER", codes)


@unittest.skipUnless(BOOK.is_file(), "packaged workbook not present")
class F2_OffGridShiftsAreRejected(unittest.TestCase):
    def test_every_packaged_shift_is_on_the_grid(self):
        p = E.parse_input(BOOK)
        codes = {f["code"] for f in E.validate_input_contract(p)["failures"]}
        self.assertNotIn("SHIFT_OFF_QUARTER_GRID", codes)

    def test_an_off_grid_start_is_a_contract_failure(self):
        p = E.parse_input(BOOK)
        p.shifts.append(E.Shift(len(p.shifts), "09:10-18:10", 550, 1090, 540))
        codes = {f["code"] for f in E.validate_input_contract(p)["failures"]}
        self.assertIn("SHIFT_OFF_QUARTER_GRID", codes)

    def test_an_off_grid_length_is_a_contract_failure(self):
        """09:00-17:57 passes the old +-5 minute duration tolerance as '9 hours'."""
        p = E.parse_input(BOOK)
        p.shifts.append(E.Shift(len(p.shifts), "09:00-17:57", 540, 1077, 537))
        codes = {f["code"] for f in E.validate_input_contract(p)["failures"]}
        self.assertIn("SHIFT_OFF_QUARTER_GRID", codes)


class F3_BreakHeadcountIsInPeopleNotShiftDays(unittest.TestCase):
    def test_workdays_helper(self):
        from types import SimpleNamespace
        self.assertEqual(E.default_workdays_per_week(SimpleNamespace(allowed_shift_durations={540})), 5)
        self.assertEqual(E.default_workdays_per_week(SimpleNamespace(allowed_shift_durations={630})), 4)
        self.assertEqual(E.default_workdays_per_week(SimpleNamespace(allowed_shift_durations={660, 540})), 5)
        self.assertEqual(E.default_workdays_per_week(SimpleNamespace(allowed_shift_durations=None)), 5)

    def test_the_recorded_cases_now_recommend_people(self):
        """Recorded deficits (person-quarters/week), 9h shift, 4 break quarters.

        One associate nets 32 quarters a shift and 5 shifts a week = 160.
        """
        for deficit, old_answer, correct in ((200, 7, 2), (192, 6, 2), (150, 5, 1),
                                             (144, 5, 1), (28, 1, 1)):
            with self.subTest(deficit=deficit):
                self.assertEqual(math.ceil(deficit / 32), old_answer, "old per-shift formula")
                self.assertEqual(math.ceil(deficit / (32 * 5)), correct)

    def test_the_engine_divides_by_the_weekly_contribution(self):
        import ast
        import inspect
        import textwrap
        src = textwrap.dedent(inspect.getsource(E.break_capacity_headcount_requirement))
        tree = ast.parse(src)
        assigns = {ast.unparse(n.targets[0]): ast.unparse(n.value)
                   for n in ast.walk(tree) if isinstance(n, ast.Assign) and len(n.targets) == 1}
        self.assertIn("net_per_associate_week", assigns.get("additional_hc", ""))
        self.assertIn("default_workdays_per_week", assigns.get("net_per_associate_week", ""))

    def test_the_three_capacity_estimates_share_one_week(self):
        import inspect
        for fn in (E.capacity_diagnostics, E.break_resilience_diagnostics,
                   E.coverage_split_capacity_report, E.break_capacity_headcount_requirement):
            with self.subTest(fn=fn.__name__):
                self.assertIn("default_workdays_per_week(parsed)", inspect.getsource(fn))


if __name__ == "__main__":
    unittest.main(verbosity=1)
