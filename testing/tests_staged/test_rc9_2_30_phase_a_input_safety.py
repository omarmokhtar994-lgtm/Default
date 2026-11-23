"""Phase A of the production-readiness audit (evidence/production_readiness_audit).

Each class pins one fix and was written to FAIL on the engine before the fix
(commit 373a5db):

  A1 (F-01) duplicate rows on a name-keyed request sheet are refused, and a
            blank duplicate can no longer erase a populated row;
  A2 (F-02) leave days count against the week: an associate on leave all week
            no longer makes the whole roster infeasible, and requests that
            cannot fit in seven days are named before the solver starts;
  A3 (F-09, F-15) a layout the parser cannot read with certainty is refused
            instead of guessed (day headers, demand rows, roster gaps, shift
            labels, language minimums, previous-Saturday shifts);
  A4 (F-03) one definition per concurrency metric, so the parity gate stops
            blocking valid schedules whose breaks fall in blank-demand hours;
  A5 (F-04) the strict release check blocks on gates in FAIL mode, not on
            warnings.
"""
from __future__ import annotations

import datetime as dt
import gzip
import importlib.util
import json
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

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJ"]
DAY_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
PARITY = REPO / "fixtures" / "real_runs" / "parity_blank_breaks"


def spec(**over):
    base = {"roster": [(n, "English") for n in NAMES], "shifts": DAY_SHIFTS,
            "demand": lambda d, m: 3 if 8 * 60 <= m < 20 * 60 else None}
    base.update(over)
    return base


def parse(s):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        W.build(s, path)
        parsed = E.parse_input(path)
    contract = E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))
    codes = {str(f.get("code")) for f in contract["failures"]}
    return parsed, codes


def dated_header(prefix):
    return prefix + [dt.datetime(2026, 10, 4) + dt.timedelta(days=i) for i in range(7)]


class A1DuplicateRequestRows(unittest.TestCase):
    def test_two_populated_preference_rows_for_one_person_are_refused(self):
        _, codes = parse(spec(preference_rows=[
            ("Agent A", [None, "Leave", None, None, None, None, None]),
            ("Agent A", [None, None, None, None, None, "OFF", "OFF"])]))
        self.assertIn("HARD_PREFERENCE_DUPLICATE_ASSOCIATE", codes)

    def test_a_blank_duplicate_row_cannot_erase_approved_leave(self):
        parsed, codes = parse(spec(preference_rows=[
            ("Agent A", [None, "Leave", None, None, None, None, None]),
            ("Agent A", [None] * 7)]))
        self.assertNotIn("HARD_PREFERENCE_DUPLICATE_ASSOCIATE", codes)
        self.assertEqual(parsed.associates[0].preferences[1], "Leave")
        self.assertTrue(any(w.startswith("PREFERENCE_BLANK_DUPLICATE_IGNORED") for w in parsed.parser_warnings))

    def test_the_validator_cross_check_flags_the_duplicate_too(self):
        rows = [("Agent A", [None, "Leave", None, None, None, None, None]),
                ("Agent A", [None, None, None, None, None, "OFF", "OFF"])]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.xlsx"
            W.build(spec(preference_rows=rows), path)
            parsed = E.parse_input(path)
            cross = _validator().independent_input_crosscheck(path, parsed)
        self.assertIn("preference_duplicate_rows", {m["check"] for m in cross["mismatches"]})

    def test_two_active_fixed_request_rows_for_one_person_are_refused(self):
        row = ["Yes", "Agent A", None] + ["08:00 - 17:00"] * 5 + ["OFF", "OFF"]
        _, codes = parse(spec(instructions={"Fixed Request Use": "Yes"}, fixed_rows=[row, list(row)]))
        self.assertIn("HARD_FIXED_REQUEST_DUPLICATE_ASSOCIATE", codes)


class A2LeaveCountsAgainstTheWeek(unittest.TestCase):
    def test_required_off_days(self):
        parsed, _ = parse(spec(preferences={"Agent A": ["Leave"] * 7, "Agent B": [None] + ["Leave"] * 6,
                                            "Agent C": ["Leave"] * 5 + [None, None],
                                            "Agent D": ["Leave"] + [None] * 6}))
        got = [E.required_off_days(parsed, parsed.associates[i], long_mode=False) for i in range(5)]
        self.assertEqual(got, [0, 1, 2, 2, 2])
        self.assertEqual(E.required_off_days(parsed, parsed.associates[3], long_mode=True), 3)
        self.assertEqual(E.required_off_days(parsed, parsed.associates[2], long_mode=True), 2)

    def _probe(self, leave_row):
        parsed, codes = parse(spec(preferences={"Agent A": leave_row}))
        self.assertFalse(codes, codes)
        probe = E.build_skeleton(parsed, None, E.HardConfig(), 20.0, 2, open(os.devnull, "w"))
        self.assertIn(probe.cp_status, {"OPTIMAL", "FEASIBLE"})
        return parsed, probe

    def test_a_full_week_of_leave_is_schedulable(self):
        parsed, probe = self._probe(["Leave"] * 7)
        self.assertEqual(probe.assignment[0], ["Leave"] * 7)

    def test_six_leave_days_leave_one_off_day(self):
        parsed, probe = self._probe([None] + ["Leave"] * 6)
        self.assertEqual(probe.assignment[0], ["OFF"] + ["Leave"] * 6)

    def test_requests_that_cannot_fit_in_a_week_are_named(self):
        _, codes = parse(spec(preferences={"Agent A": ["OFF", "OFF", "OFF", None, None, None, None]}))
        self.assertIn("ASSOCIATE_REQUESTS_EXCEED_WEEK", codes)

    def test_validator_uses_the_same_off_rule(self):
        source = (ROOT / "engine" / "tools" / "independent_validator.py").read_text(encoding="utf-8")
        self.assertIn("eng.required_off_days(", source)


class A3RefuseWhatCannotBeReadWithCertainty(unittest.TestCase):
    def test_schedule_without_day_headers_is_refused_when_its_cells_are_fixed_requests(self):
        header = ["Slot", "Emp ID", "Email", "SF Name", "TL", "Language"] + [f"Day {i}" for i in range(1, 8)]
        rows = [[i + 1, 900 + i, "e", n, "TL", "English"] + ["08:00 - 17:00"] * 5 + ["OFF", "OFF"]
                for i, n in enumerate(NAMES)]
        _, codes = parse(spec(roster_rows=rows, schedule_header=header, instructions={"Fixed Request Use": "Yes"}))
        self.assertIn("HARD_DAY_COLUMNS_NOT_FOUND", codes)

    def test_schedule_date_headers_bind_by_weekday_not_by_position(self):
        # Two notes columns sit between Language and the first date; the old
        # positional fallback read them as Sunday and Monday.
        header = dated_header(["Slot", "Emp ID", "Email", "SF Name", "TL", "Language", "Notes A", "Notes B"])
        rows = [[i + 1, 900 + i, "e", n, "TL", "English", "x", "y"] + ["OFF"] + ["08:00 - 17:00"] * 5 + ["OFF"]
                for i, n in enumerate(NAMES)]
        parsed, codes = parse(spec(roster_rows=rows, schedule_header=header, instructions={"Fixed Request Use": "Yes"}))
        self.assertNotIn("HARD_DAY_COLUMNS_NOT_FOUND", codes)
        self.assertEqual(parsed.associates[0].fixed_schedule, ["OFF"] + ["08:00 - 17:00"] * 5 + ["OFF"])

    def test_fixed_request_sheet_without_day_headers_is_refused(self):
        rows = [["Yes", "Agent A", None] + ["08:00 - 17:00"] * 5 + ["OFF", "OFF"]]
        _, codes = parse(spec(instructions={"Fixed Request Use": "Yes"}, fixed_rows=rows,
                              fixed_header=["Active?", "Associate Name", "Nesting Group"]
                              + [f"D{i}" for i in range(1, 8)]))
        self.assertIn("HARD_DAY_COLUMNS_NOT_FOUND", codes)

    def test_fixed_request_dates_starting_midweek_bind_by_weekday(self):
        # Dates Wed 7 Oct .. Tue 13 Oct: the first column is Wednesday.
        header = ["Active?", "Associate Name", "Nesting Group"] + [
            dt.datetime(2026, 10, 7) + dt.timedelta(days=i) for i in range(7)]
        row = ["Yes", "Agent A", None, "08:00 - 17:00", "08:00 - 17:00", "OFF", "OFF",
               "08:00 - 17:00", "08:00 - 17:00", "08:00 - 17:00"]
        parsed, codes = parse(spec(instructions={"Fixed Request Use": "Yes"}, fixed_rows=[row], fixed_header=header))
        self.assertNotIn("HARD_DAY_COLUMNS_NOT_FOUND", codes)
        # Columns are Wed Thu Fri Sat Sun Mon Tue; read back as Sun..Sat.
        self.assertEqual(parsed.associates[0].fixed_schedule,
                         ["08:00 - 17:00", "08:00 - 17:00", "08:00 - 17:00", "08:00 - 17:00",
                          "08:00 - 17:00", "OFF", "OFF"])

    def test_preference_sheet_without_day_headers_is_refused(self):
        _, codes = parse(spec(preference_header=["Associate Name", "Language"] + [f"Col{i}" for i in range(7)],
                              preference_rows=[("Agent A", [None, "Leave", None, None, None, None, None])]))
        self.assertIn("HARD_DAY_COLUMNS_NOT_FOUND", codes)

    def _demand_rows(self, skip=None, extra=None):
        rows = []
        for m in range(0, 1440, 60):
            if m == skip:
                continue
            rows.append((W.hhmm(m), [3 if 480 <= m < 1200 else None] * 7))
            if extra and m == extra[0]:
                rows.append(extra[1])
        return rows

    def test_a_repeated_demand_time_row_is_refused(self):
        _, codes = parse(spec(demand_rows=self._demand_rows(extra=(600, ("10:00", [None] * 7)))))
        self.assertIn("HARD_DUPLICATE_REQUIREMENT_TIME", codes)

    def test_a_missing_demand_time_row_is_refused(self):
        _, codes = parse(spec(demand_rows=self._demand_rows(skip=720)))
        self.assertIn("HARD_MISSING_REQUIREMENT_TIME", codes)

    def test_demand_rows_off_the_interval_grid_are_refused(self):
        rows = [(W.hhmm(m), [2 if 480 <= m < 1200 else None] * 7) for m in range(0, 1440, 15)]
        _, codes = parse(spec(step=30, demand_rows=rows))
        self.assertIn("HARD_OFF_GRID_REQUIREMENT_TIME", codes)

    def test_roster_rows_after_a_long_blank_gap_are_refused(self):
        header = ["Slot", "Emp ID", "Email", "SF Name", "TL", "Language"] + W.DAYS
        rows = [[i + 1, 700 + i, "e", n, "TL", "English"] + [None] * 7 for i, n in enumerate(NAMES[:5])]
        rows += [[None] * 13 for _ in range(25)]
        rows += [[i + 6, 800 + i, "e", n, "TL", "English"] + [None] * 7 for i, n in enumerate(NAMES[5:])]
        _, codes = parse(spec(roster_rows=rows, schedule_header=header, instructions={"Count of Associates": None}))
        self.assertIn("HARD_ROSTER_ROWS_AFTER_BLANK_GAP", codes)

    def test_employee_id_is_bound_by_header_not_position(self):
        header = ["Slot", "TL", "Email", "Emp ID", "SF Name", "Language"] + W.DAYS
        rows = [[i + 1, "Same TL", "e", 5000 + i, n, "English"] + [None] * 7 for i, n in enumerate(NAMES)]
        parsed, codes = parse(spec(roster_rows=rows, schedule_header=header))
        self.assertNotIn("HARD_DUPLICATE_EMPLOYEE_ID", codes)
        self.assertEqual([a.emp_id for a in parsed.associates][:2], [5000, 5001])

    def test_an_unreadable_shift_label_is_refused(self):
        _, codes = parse(spec(shifts=["08:00 - 24:00"] + DAY_SHIFTS))
        self.assertIn("HARD_INVALID_SHIFT_LABEL", codes)

    def test_language_minimum_must_be_a_whole_number_of_zero_or_more(self):
        for value in (0.5, -1):
            _, codes = parse(spec(roster=[(n, "Spanish" if i < 3 else "English") for i, n in enumerate(NAMES)],
                                  language_setup=[{"Language": "Spanish", "Coverage Start": "09:00",
                                                   "Coverage End": "17:00", "Active?": "Yes",
                                                   "Coverage Group": "Spanish", "Minimum Per Interval": value}]))
            self.assertIn("HARD_INVALID_LANGUAGE_MINIMUM", codes, value)

    def test_an_unreadable_previous_saturday_shift_is_refused(self):
        _, codes = parse(spec(previous_saturday={"Agent A": "25:00 - 06:00"}))
        self.assertIn("HARD_INVALID_PREVIOUS_SATURDAY_SHIFT", codes)

    def test_a_clean_workbook_is_still_accepted(self):
        _, codes = parse(spec(preferences={"Agent A": [None, "Leave", None, None, None, "OFF", "OFF"]},
                              previous_saturday={"Agent B": "22:00 - 07:00", "Agent C": "OFF"}))
        self.assertFalse(codes, codes)


def _validator():
    spec_ = importlib.util.spec_from_file_location("iv_phase_a", ROOT / "engine" / "tools" / "independent_validator.py")
    mod = importlib.util.module_from_spec(spec_)
    sys.modules["iv_phase_a"] = mod
    spec_.loader.exec_module(mod)
    return mod


class A4OneDefinitionPerConcurrencyMetric(unittest.TestCase):
    """S01: a valid schedule whose breaks fall in blank-demand hours (06:00-08:00).

    Before the fix the engine reported a 0.333 maximum concurrent break ratio
    (active intervals only) and the validator 0.5 (every staffed quarter), so
    the parity gate blocked a correct schedule.
    """

    @classmethod
    def setUpClass(cls):
        cls.parsed = E.parse_input(PARITY / "S01_BASELINE.xlsx")
        with gzip.open(PARITY / "S01_SELECTED_CANDIDATE.json.gz", "rt", encoding="utf-8") as fh:
            cls.skeleton, cls.solution = E.deserialize_break_candidate(cls.parsed, json.load(fh))
        cls.engine = E.calculate_metrics(cls.parsed, cls.skeleton, cls.solution.selected_pattern, cls.solution.patterns)
        cls.validator = _validator().validate(
            PARITY / "S01_BASELINE.xlsx", PARITY / "S01_BASELINE_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
            ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")

    def test_both_sides_publish_both_definitions_and_agree_on_each(self):
        keys = ("max_concurrent_breaks_observed", "max_concurrent_break_ratio_observed",
                "break_concurrency_violation_count", "max_concurrent_breaks_all_staffed_quarters",
                "max_concurrent_break_ratio_all_staffed_quarters",
                "break_concurrency_violation_count_all_staffed_quarters")
        for key in keys:
            self.assertIn(key, self.engine, key)
            self.assertIn(key, self.validator["metrics"], key)
            self.assertAlmostEqual(float(self.engine[key]), float(self.validator["metrics"][key]), places=6, msg=key)

    def test_the_definitions_really_differ_on_this_schedule(self):
        self.assertAlmostEqual(self.engine["max_concurrent_break_ratio_observed"], 1 / 3, places=6)
        self.assertAlmostEqual(self.engine["max_concurrent_break_ratio_all_staffed_quarters"], 0.5, places=6)

    def test_parity_gate_passes_and_compares_the_new_fields(self):
        sys.path.insert(0, str(ROOT / "engine" / "_tools"))
        import canonical_metrics as C
        self.assertIn("max_concurrent_break_ratio_all_staffed_quarters", C.PARITY_FIELDS)
        result = C.compare_metric_surfaces(self.engine, self.validator["metrics"],
                                           engine_stage="FULL_SCHEDULE", validator_stage="FULL_SCHEDULE")
        concurrency = [m for m in result["mismatches"] if "concurren" in m["field"]]
        self.assertEqual(concurrency, [])


def _quality_report():
    spec_ = importlib.util.spec_from_file_location(
        "qr_phase_a", ROOT / "engine" / "production" / "phase_c_quality_report.py")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    return mod


class A5WarningsDoNotBlockRelease(unittest.TestCase):
    def report(self, gate):
        return {"artifact_state": "FINAL_VERIFIED", "contract": {"status": "PASS", "failure_count": 0},
                "safety": {"status": "PASS"}, "production_quality_gate": gate,
                "phase_c_quality_status": "PASS_WITH_DECLARED_WARNINGS"}

    def test_warn_families_with_a_passing_coverage_gate_do_not_block(self):
        gate = {"status": "WARN", "mode": "fail",
                "gate_results": {"coverage": "PASS", "whole_week_balance": "WARN", "employee_quality": "WARN"}}
        self.assertEqual(_quality_report().release_blocking_reasons(self.report(gate), strict=True), [])

    def test_a_failing_family_still_blocks(self):
        gate = {"status": "FAIL", "mode": "fail", "gate_results": {"coverage": "FAIL"}}
        self.assertIn("production_quality_gate_failed",
                      _quality_report().release_blocking_reasons(self.report(gate), strict=True))

    def test_a_coverage_gate_in_fail_mode_that_was_not_evaluated_blocks(self):
        gate = {"status": "WARN", "mode": "fail", "gate_results": {"employee_quality": "WARN"}}
        self.assertIn("mandatory_production_quality_gate_not_pass",
                      _quality_report().release_blocking_reasons(self.report(gate), strict=True))


if __name__ == "__main__":
    unittest.main()
