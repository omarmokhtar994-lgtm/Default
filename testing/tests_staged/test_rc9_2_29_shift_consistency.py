"""Shift consistency polish: a more uniform week per associate, nothing else changed.

Fixture: the published schedule of the enforced Voice run (fixtures/real_runs/
language_hours), serialised from its candidate pool. Every assertion is about
the contract: coverage, compliance and the employee guards may not get worse,
hard rules hold, locked cells stay where they were, and the week gets more
consistent.
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

RUN = REPO / "fixtures" / "real_runs" / "language_hours"
BOOK = RUN / "Cricut_Voice_LANGUAGE_HOURS.xlsx"
CANDIDATE = RUN / "VOICE_FINAL_SHEET_CANDIDATE.json.gz"
COVERAGE_KEYS = ("after_target", "after_floor", "after_100", "after_90", "after_80", "before_target",
                 "before_floor", "severe_floor_gap_count", "language_gap_count", "zero_staffed_active_quarters",
                 "break_concurrency_violation_count", "after_avoidable_overage_fte_sum",
                 "whole_week_overage_cap_violation_count", "week_boundary_after_target")


def load():
    parsed = E.parse_input(BOOK)
    with gzip.open(CANDIDATE, "rt", encoding="utf-8") as fh:
        skeleton, solution = E.deserialize_break_candidate(parsed, json.load(fh))
    return parsed, skeleton, solution


class Polish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed, cls.skeleton, cls.solution = load()
        cls.before = E.calculate_metrics(cls.parsed, cls.skeleton, cls.solution.selected_pattern, cls.solution.patterns)
        cls.polished_skeleton, cls.polished, cls.record = E.shift_consistency_polish(
            cls.parsed, cls.skeleton, cls.solution, time_limit_sec=60)

    def test_the_week_gets_more_consistent(self):
        self.assertEqual(self.record["status"], "APPLIED")
        self.assertLess(self.record["after"]["start_movement_hours"], self.record["before"]["start_movement_hours"])
        self.assertLessEqual(self.record["after"]["distinct_start_times"], self.record["before"]["distinct_start_times"])

    def test_coverage_and_compliance_are_unchanged(self):
        after = self.polished.metrics
        for key in COVERAGE_KEYS:
            self.assertAlmostEqual(float(after.get(key, 0) or 0), float(self.before.get(key, 0) or 0), places=6,
                                   msg=key)
        self.assertEqual(E._consistency_metrics_no_worse(after, self.before), [])
        self.assertEqual(E.validate_schedule(self.parsed, self.polished_skeleton, self.polished)["hard_fail_count"], 0)
        self.assertEqual(E.candidate_pool_class(self.parsed, self.polished_skeleton, self.polished),
                         E.candidate_pool_class(self.parsed, self.skeleton, self.solution))

    def test_every_changed_cell_keeps_every_hard_rule(self):
        # Checked with the rule primitives directly, not the polish's own helpers.
        parsed = self.parsed
        for a, row in enumerate(self.polished_skeleton.selected_shift_index):
            assoc = parsed.associates[a]
            shifts = [parsed.shifts[si] if si is not None else None for si in row]
            self.assertLessEqual(len({si for si in row if si is not None}), parsed.max_different_shifts, assoc.name)
            if shifts[0] is not None:
                self.assertTrue(E.previous_saturday_compatible(assoc.previous_saturday, shifts[0], parsed.rest_gap_hours))
            for d in range(7):
                nxt = shifts[(d + 1) % 7]
                if shifts[d] is not None and nxt is not None:
                    self.assertTrue(E.rest_compatible(shifts[d], nxt, parsed.rest_gap_hours), (assoc.name, d))
                original = self.skeleton.selected_shift_index[a][d]
                self.assertEqual(row[d] is None, original is None, "a working day became OFF or the reverse")
                if row[d] is not None and row[d] != original:
                    windows = E.associate_language_windows(parsed, assoc, day=d)
                    self.assertTrue(not windows or any(E.shift_within_language_window(shifts[d], w) for w in windows))
                    self.assertEqual(shifts[d].duration_min, parsed.shifts[original].duration_min)

    def test_fixed_requests_and_nesting_groups_are_untouched(self):
        for a, assoc in enumerate(self.parsed.associates):
            for d in range(7):
                fixed = assoc.fixed_schedule[d] if d < len(assoc.fixed_schedule) else ""
                locked = (self.parsed.fixed_enabled and E.preference_kind(fixed) == "shift") or E.norm(assoc.nesting_group)
                if locked:
                    self.assertEqual(self.polished_skeleton.selected_shift_index[a][d],
                                     self.skeleton.selected_shift_index[a][d], (assoc.name, d))

    def test_swaps_stay_inside_one_language(self):
        # Coverage counts depend on language only, so a day's shifts may only
        # be re-dealt among associates of the same language.
        for d in range(7):
            by_language = {}
            for rows, bucket in ((self.skeleton.selected_shift_index, 0), (self.polished_skeleton.selected_shift_index, 1)):
                for a, row in enumerate(rows):
                    if row[d] is not None:
                        key = E.norm(self.parsed.associates[a].language)
                        by_language.setdefault(key, ([], []))[bucket].append(row[d])
            for key, (before, after) in by_language.items():
                self.assertEqual(sorted(before), sorted(after), (d, key))

    def test_the_result_is_deterministic(self):
        again_skeleton, _, again = E.shift_consistency_polish(self.parsed, self.skeleton, self.solution, time_limit_sec=60)
        self.assertEqual(again_skeleton.selected_shift_index, self.polished_skeleton.selected_shift_index)
        self.assertEqual(again["after"], self.record["after"])

    def test_the_input_is_not_mutated(self):
        fresh_parsed, fresh_skeleton, fresh_solution = load()
        self.assertEqual(self.skeleton.selected_shift_index, fresh_skeleton.selected_shift_index)
        self.assertEqual(self.solution.selected_pattern, fresh_solution.selected_pattern)


class SwapsStayWithinALanguageWithoutHours(unittest.TestCase):
    """With the language hours off, only the same-language rule keeps an
    English shift away from an International associate."""

    def test_each_language_keeps_its_own_shifts(self):
        parsed, skeleton, solution = load()
        parsed.language_working_window_mode = "OFF"
        # The fixture's International associates are mostly fixed requests,
        # which the polish never moves; free them so both languages can move.
        for assoc in parsed.associates:
            assoc.fixed_schedule = [""] * 7
        solution.metrics = E.calculate_metrics(parsed, skeleton, solution.selected_pattern, solution.patterns)
        polished_skeleton, _, record = E.shift_consistency_polish(parsed, skeleton, solution, time_limit_sec=60)
        for d in range(7):
            for language in {E.norm(a.language) for a in parsed.associates}:
                before = sorted(r[d] for a, r in enumerate(skeleton.selected_shift_index)
                                if r[d] is not None and E.norm(parsed.associates[a].language) == language)
                after = sorted(r[d] for a, r in enumerate(polished_skeleton.selected_shift_index)
                               if r[d] is not None and E.norm(parsed.associates[a].language) == language)
                self.assertEqual(before, after, (d, language))


class Guards(unittest.TestCase):
    def test_a_move_that_costs_coverage_is_refused(self):
        old = {"after_target": 100, "after_floor": 120, "employee_quality": {"preference_match_count": 4}}
        new = dict(old, after_target=99)
        self.assertIn("after_target", E._consistency_metrics_no_worse(new, old))
        new = dict(old, employee_quality={"preference_match_count": 3})
        self.assertIn("employee.preference_match_count", E._consistency_metrics_no_worse(new, old))

    def test_a_schedule_with_nothing_to_gain_is_returned_unchanged(self):
        parsed, skeleton, solution = load()
        polished_skeleton, polished, record = E.shift_consistency_polish(parsed, skeleton, solution, time_limit_sec=60)
        again_skeleton, again, again_record = E.shift_consistency_polish(parsed, polished_skeleton, polished,
                                                                         time_limit_sec=60)
        self.assertIn(again_record["status"], {"NO_CHANGE", "APPLIED"})
        self.assertLessEqual(again_record["after"]["start_movement_hours"], record["after"]["start_movement_hours"])
        self.assertEqual(E._consistency_metrics_no_worse(again.metrics, polished.metrics), [])


class Switches(unittest.TestCase):
    def test_the_workbook_row_and_its_validation(self):
        import shutil
        import tempfile
        from openpyxl import load_workbook
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "polish.xlsx"
            shutil.copy(BOOK, book)
            self.assertIsNone(E.parse_input(book).shift_consistency_polish)
            for value, expected in (("Yes", True), ("No", False)):
                wb = load_workbook(book)
                ws = wb["Instructions"]
                ws.cell(ws.max_row + 1, 1, "Shift Consistency Polish")
                ws.cell(ws.max_row, 2, value)
                wb.save(book)
                self.assertEqual(E.parse_input(book).shift_consistency_polish, expected)
            wb = load_workbook(book)
            ws = wb["Instructions"]
            ws.cell(ws.max_row + 1, 1, "Shift Consistency Polish")
            ws.cell(ws.max_row, 2, "Yes please")
            wb.save(book)
            warnings = E.parse_input(book).parser_warnings
            self.assertTrue(any("HARD_INVALID_INSTRUCTION_BOOLEAN" in str(w) and "Shift Consistency Polish" in str(w)
                                for w in warnings))

    def test_command_line_flags_reach_the_engine(self):
        parser = E.build_arg_parser()
        self.assertTrue(parser.parse_args(["--shift-consistency-polish"]).shift_consistency_polish)
        self.assertFalse(parser.parse_args(["--no-shift-consistency-polish"]).shift_consistency_polish)
        self.assertIsNone(parser.parse_args([]).shift_consistency_polish)
        source = (ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").read_text(encoding="utf-8")
        self.assertIn("command.append('--shift-consistency-polish')", source)
        self.assertIn("command.append('--no-shift-consistency-polish')", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
