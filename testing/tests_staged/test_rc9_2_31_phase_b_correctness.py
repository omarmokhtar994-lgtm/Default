"""Phase B of the production-readiness audit (evidence/production_readiness_audit).

Written to FAIL on the Phase A engine (commit 5597971) and pass after the fix:

  B1 (F-05) an overnight language rule with Coverage Days opens on each listed
            day: Mon-Fri 18:00-05:00 is in force Mon 18:00 .. Sat 05:00, not on
            Monday 00:00-05:00;
  B2 (F-08) the contract fingerprint covers every enforced setting, including
            a run-time override of the language working window;
  B3 (F-12, F-13) Coverage Split rows are read strictly, its gate mode is
            wired, and the engine's own validate_schedule checks every hard
            family the independent validator checks;
  B4 (F-19) the clean-room checker is a release gate step;
  B5 (F-10, F-14) a no-schedule run spends its unused budget naming the
            cause, contradictions are named before the solver starts, and the
            outcome text says what actually happened;
  B6 (F-16) alternative exported schedules are independently validated;
  B7 (F-11) an instruction row the engine cannot read, or that contradicts
            another, is refused instead of silently replaced by a default.
"""
from __future__ import annotations

import gzip
import importlib.util
import json
import os
import re
import shutil
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

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJKL"]
DAY_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
ALL_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(24)]
PARITY = REPO / "fixtures" / "real_runs" / "parity_blank_breaks"


def spec(**over):
    base = {"roster": [(n, "English") for n in NAMES[:10]], "shifts": DAY_SHIFTS,
            "demand": lambda d, m: 3 if 8 * 60 <= m < 20 * 60 else None}
    base.update(over)
    return base


def parse(s, path_out=None):
    tmp = tempfile.mkdtemp()
    path = Path(tmp) / "case.xlsx"
    W.build(s, path)
    parsed = E.parse_input(path)
    contract = E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))
    codes = {str(f.get("code")) for f in contract["failures"]}
    if path_out is not None:
        path_out.append(path)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    return parsed, codes


def load(path: Path, name: str):
    spec_ = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec_)
    sys.modules[name] = mod
    spec_.loader.exec_module(mod)
    return mod


def validator():
    return load(ROOT / "engine" / "tools" / "independent_validator.py", "iv_phase_b")


def runner():
    return load(ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py", "runner_phase_b")


SPANISH_MON_FRI = [{"Language": "Spanish", "Coverage Start": "18:00", "Coverage End": "05:00",
                    "Active?": "Yes", "Coverage Group": "Spanish", "Minimum Per Interval": 1,
                    "Coverage Days": "Mon-Fri"}]


class B1OvernightRulesOpenOnTheirListedDays(unittest.TestCase):
    def setUp(self):
        self.parsed, self.codes = parse(spec(
            roster=[(n, "Spanish" if i < 3 else "English") for i, n in enumerate(NAMES)],
            shifts=ALL_SHIFTS, demand=lambda d, m: 2,
            preferences={"Agent A": ["OFF", "OFF"] + [None] * 5, "Agent B": ["OFF", "OFF"] + [None] * 5,
                         "Agent C": ["OFF"] + [None] * 5 + ["OFF"]},
            language_setup=SPANISH_MON_FRI))

    def in_force(self, day, minute):
        return bool(E.language_rules_at(self.parsed, minute, 15, day=day))

    def test_monday_early_morning_is_sunday_night_and_not_covered(self):
        self.assertFalse(self.in_force(1, 60))
        self.assertFalse(self.in_force(0, 60))
        self.assertFalse(self.in_force(0, 19 * 60))

    def test_the_window_runs_from_each_listed_evening_into_the_next_morning(self):
        for day in range(1, 6):
            self.assertTrue(self.in_force(day, 19 * 60), day)
            self.assertTrue(self.in_force(day + 1, 60), day + 1)
        self.assertFalse(self.in_force(6, 19 * 60))

    def test_an_all_days_overnight_rule_is_unchanged(self):
        parsed, _ = parse(spec(roster=[(n, "Spanish") for n in NAMES[:10]], shifts=ALL_SHIFTS,
                               demand=lambda d, m: 1,
                               language_setup=[dict(SPANISH_MON_FRI[0], **{"Coverage Days": "All"})]))
        for day in range(7):
            self.assertTrue(E.language_rules_at(parsed, 60, 15, day=day))
            self.assertTrue(E.language_rules_at(parsed, 19 * 60, 15, day=day))

    def test_the_feasible_week_is_no_longer_refused(self):
        self.assertNotIn("SKILL_WINDOW_PAID_CAPACITY_PROVABLY_INSUFFICIENT", self.codes)
        self.assertFalse(self.codes, self.codes)


class B2TheContractFingerprintCoversEnforcedSettings(unittest.TestCase):
    def test_language_window_mode_changes_the_contract_hash(self):
        parsed, _ = parse(spec())
        before = E.canonical_hash(E.canonical_contract_snapshot(parsed))
        parsed.language_working_window_mode = "ALL_ROWS"
        self.assertNotEqual(before, E.canonical_hash(E.canonical_contract_snapshot(parsed)))

    def test_requests_and_switches_are_in_the_contract(self):
        a, _ = parse(spec())
        b, _ = parse(spec(preferences={"Agent A": [None, "Leave", None, None, None, None, None]}))
        self.assertNotEqual(E.canonical_hash(E.canonical_contract_snapshot(a)),
                            E.canonical_hash(E.canonical_contract_snapshot(b)))
        snapshot = E.canonical_contract_snapshot(a)
        for key in ("language_working_window_mode", "language_windows", "coverage_split_rules",
                    "requests", "hard_off", "strict_off", "leave_enabled", "fixed_enabled",
                    "shift_consistency_polish"):
            self.assertIn(key, snapshot, key)

    def test_run_overrides_are_in_the_run_parameters(self):
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text(encoding="utf-8")
        block = source[source.index("        run_parameters = {"):]
        block = block[:block.index("\n        }\n")]
        self.assertIn('"language_working_window_override"', block)
        self.assertIn('"shift_consistency_polish_override"', block)


SPLIT = [{"Coverage Group": "English", "Start": "08:00", "End": "20:00", "Coverage Ratio": 1.0,
          "Exclusive?": "No", "Active?": "Yes"}]
LANG_ENGLISH = [{"Language": "English", "Coverage Start": "00:00", "Coverage End": "00:00", "Active?": "Yes",
                 "Coverage Group": "English", "Minimum Per Interval": 0}]


class B3CoverageSplitAndSelfValidation(unittest.TestCase):
    def test_unreadable_coverage_split_rows_are_refused(self):
        for field, value in (("Start", "9am"), ("Coverage Ratio", "most"), ("Active?", "Enable"),
                             ("Exclusive?", "maybe")):
            row = dict(SPLIT[0], **{field: value})
            _, codes = parse(spec(language_setup=LANG_ENGLISH, coverage_split=[row]))
            self.assertIn("HARD_INVALID_COVERAGE_SPLIT_ROW", codes, field)

    def test_a_clean_coverage_split_row_is_read(self):
        parsed, codes = parse(spec(language_setup=LANG_ENGLISH, coverage_split=SPLIT))
        self.assertNotIn("HARD_INVALID_COVERAGE_SPLIT_ROW", codes)
        self.assertEqual(len(parsed.coverage_split_rules), 1)

    def test_the_template_help_row_is_not_a_rule(self):
        # Found by the 111-workbook snapshot: the shipped template writes an
        # explanation row under the header (Cricut Voice carries it).
        help_row = {"Coverage Group": "Name from Language Setup's Coverage Group column.",
                    "Start": "Window opens (e.g. 03:00).", "End": "Window closes; may cross midnight (e.g. 16:00).",
                    "Coverage Ratio": "Blank = the workbook's Minimum Per Interval. 1.0 = full requirement.",
                    "Exclusive?": "Yes = only this group may work these hours at all.",
                    "Active?": "No or blank = row ignored."}
        parsed, codes = parse(spec(language_setup=LANG_ENGLISH, coverage_split=[help_row]))
        self.assertNotIn("HARD_INVALID_COVERAGE_SPLIT_ROW", codes)
        self.assertEqual(parsed.coverage_split_rules, [])

    def test_a_blank_active_cell_is_refused_not_guessed(self):
        # The template says blank = ignored; the parser read blank as active.
        _, codes = parse(spec(language_setup=LANG_ENGLISH, coverage_split=[dict(SPLIT[0], **{"Active?": None})]))
        self.assertIn("HARD_INVALID_COVERAGE_SPLIT_ROW", codes)

    def test_the_coverage_split_gate_mode_reaches_the_quality_gate(self):
        parsed, _ = parse(spec(language_setup=LANG_ENGLISH, coverage_split=SPLIT,
                               instructions={"Coverage Split Gate Mode": "Warn"}))
        gate = E.production_quality_gate(parsed, {"active_intervals": 84, "coverage_split_gap_count": 3})
        self.assertEqual(gate["gate_results"].get("coverage_split"), "WARN")
        parsed.coverage_split_gate_mode = "fail"
        gate = E.production_quality_gate(parsed, {"active_intervals": 84, "coverage_split_gap_count": 3})
        self.assertEqual(gate["gate_results"].get("coverage_split"), "FAIL")

    def _schedule(self, parsed, rows):
        index = {s.label: s.index for s in parsed.shifts}
        assignment, selected = [], []
        for row in rows:
            assignment.append(list(row))
            selected.append([index.get(v) for v in row])
        sk = E.SkeletonSolution("test", "FEASIBLE", 0.0, 0.0, assignment, selected, {})
        metrics = E.calculate_metrics(parsed, sk, {}, [])
        br = E.BreakSolution("test", "test", "FEASIBLE", 0.0, 0.0, 0, False, {}, set(), [], {}, metrics)
        return E.validate_schedule(parsed, sk, br)

    def test_validate_schedule_checks_requests_rest_wrap_and_consecutive_off(self):
        parsed, _ = parse(spec(shifts=ALL_SHIFTS,
                               instructions={"Separate OFF Days": "No"},
                               preferences={"Agent A": ["OFF", None, None, None, None, None, None],
                                            "Agent B": [None, "Leave", None, None, None, None, None]}))
        w = "08:00 - 17:00"
        rows = [[w] * 7 for _ in parsed.associates]
        rows[0] = [w, w, w, w, w, "OFF", "OFF"]            # works its hard-OFF Sunday
        rows[1] = ["OFF", w, w, w, w, w, "OFF"]            # works its Monday leave; OFF not consecutive?  (Sat,Sun are consecutive)
        rows[2] = ["00:00 - 09:00", w, w, w, "OFF", w, "23:00 - 08:00"]  # Sat 23:00 -> Sun 00:00 rest 0 h; OFF split
        types = {f["type"] for f in self._schedule(parsed, rows)["failures"]}
        self.assertIn("hard_off_preference", types)
        self.assertIn("leave_preference", types)
        self.assertIn("rest_gap_cyclic", types)
        self.assertIn("consecutive_off", types)

    def test_the_validator_measures_coverage_split_after_breaks(self):
        iv = validator()
        parsed, _ = parse(spec(language_setup=LANG_ENGLISH, coverage_split=SPLIT))
        after = [[] for _ in range(7 * 96)]
        gaps = iv.coverage_split_gaps(E, parsed, after)
        self.assertGreater(len(gaps), 0)
        staffed = [[0, 1, 2] for _ in range(7 * 96)]
        self.assertEqual(iv.coverage_split_gaps(E, parsed, staffed), [])


class B4CleanRoomIsAReleaseGate(unittest.TestCase):
    def test_the_runner_runs_the_clean_room_check_and_passes_a_correct_schedule(self):
        r = runner()
        tmp = Path(tempfile.mkdtemp())
        audit = tmp / "S01.solver_audit.json"
        engine = json.loads((PARITY / "S01_ENGINE_METRICS.json").read_text())["engine_stage_metric_surface"]
        audit.write_text(json.dumps({"selected_candidate": {"metrics": engine}}))
        result = r.run_clean_room_gate(PARITY / "S01_BASELINE.xlsx",
                                       PARITY / "S01_BASELINE_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
                                       audit, tmp / "CLEAN_ROOM.json")
        self.assertEqual(result["status"], "PASS", result)

    def test_a_disagreement_with_the_engine_blocks(self):
        r = runner()
        tmp = Path(tempfile.mkdtemp())
        audit = tmp / "S01.solver_audit.json"
        engine = json.loads((PARITY / "S01_ENGINE_METRICS.json").read_text())["engine_stage_metric_surface"]
        engine = dict(engine, after_target=int(engine["after_target"]) + 1)
        audit.write_text(json.dumps({"selected_candidate": {"metrics": engine}}))
        result = r.run_clean_room_gate(PARITY / "S01_BASELINE.xlsx",
                                       PARITY / "S01_BASELINE_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
                                       audit, tmp / "CLEAN_ROOM.json")
        self.assertEqual(result["status"], "FAIL", result)


class B5NoScheduleRunsNameTheCause(unittest.TestCase):
    def test_diagnosis_uses_the_unused_budget(self):
        self.assertGreaterEqual(E.infeasibility_diagnosis_budget(remaining_total=298.0, finalization_reserve=30.0), 60.0)
        self.assertEqual(E.infeasibility_diagnosis_budget(remaining_total=20.0, finalization_reserve=30.0), 0.0)
        self.assertLessEqual(E.infeasibility_diagnosis_budget(remaining_total=5000.0, finalization_reserve=60.0), 900.0)

    def test_a_fixed_shift_in_banned_blank_hours_is_named_before_solving(self):
        _, codes = parse(spec(shifts=DAY_SHIFTS + ["22:00 - 07:00"],
                              instructions={"Fixed Request Use": "Yes",
                                            "Blank Interval Staffing Rule": "No new staffing in blank intervals"},
                              fixed={"Agent A": ["22:00 - 07:00"] * 5 + ["OFF", "OFF"]}))
        self.assertIn("FIXED_REQUEST_IN_BLANK_HOURS", codes)

    def test_a_fixed_shift_outside_enforced_language_hours_is_named_before_solving(self):
        _, codes = parse(spec(roster=[(n, "Spanish" if i < 3 else "English") for i, n in enumerate(NAMES[:10])],
                              shifts=ALL_SHIFTS, demand=lambda d, m: 2,
                              instructions={"Fixed Request Use": "Yes", "Language Working Window": "ALL_ROWS"},
                              language_setup=[dict(SPANISH_MON_FRI[0], **{"Coverage Days": "All"})],
                              fixed={"Agent A": ["08:00 - 17:00"] * 5 + ["OFF", "OFF"]}))
        self.assertIn("FIXED_REQUEST_OUTSIDE_LANGUAGE_HOURS", codes)

    def test_a_diagnostics_run_does_not_claim_a_schedule(self):
        outcome = E.build_business_outcome({"status": "PASS_DIAGNOSTICS_ONLY"}, 0)
        self.assertEqual(outcome["outcome_code"], "DIAGNOSTICS_ONLY_COMPLETE")
        self.assertFalse(outcome["production_eligible"])
        self.assertNotIn("Final schedule generated", outcome["headline"])

    def test_no_cap_gap_is_claimed_without_one(self):
        # S11/S13 printed "exceeds the approved exception limit" next to
        # "the proven gap is 0".
        audit = {"status": "FAIL_NO_BREAK_FEASIBLE_CANDIDATE", "operational_no_break_cap": 0,
                 "best_exception_lower_bound": 0, "best_proven_minimum_no_break_exceptions": 0}
        outcome = E.build_business_outcome(audit, 2)
        self.assertEqual(outcome["outcome_code"], "BREAK_PLAN_NOT_FOUND")
        self.assertNotIn("exceeds", outcome["headline"])
        audit.update(best_exception_lower_bound=3, best_proven_minimum_no_break_exceptions=3)
        self.assertEqual(E.build_business_outcome(audit, 2)["outcome_code"], "BREAK_EXCEPTION_CAP_GAP")

    def test_findings_are_not_printed_twice(self):
        row = {"code": "X", "detail": "same"}
        text = E.format_business_outcome({"headline": "h", "plain_language_summary": "s",
                                          "resource_findings": [row, dict(row)]})
        self.assertEqual(text.count("X: same"), 1)

    def _case(self, status, engine_outcome):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "C.l6_3_2_3_solver_audit.json").write_text(json.dumps({"status": status}))
        (tmp / "BUSINESS_OUTCOME.json").write_text(json.dumps(engine_outcome))
        return tmp

    def test_the_engine_diagnosis_of_a_no_schedule_run_is_kept(self):
        r = runner()
        engine_outcome = {"outcome_code": "BREAK_PLACEMENT_INFEASIBLE", "headline": "Breaks leave a quarter unstaffed",
                          "plain_language_summary": "Agent B Tue 20:00 is alone.", "production_eligible": False}
        case = self._case("FAIL_TESTED_SKELETON_EXCEPTION_LOWER_BOUND_EXCEEDS_CAP", engine_outcome)
        r.reconcile_business_outcome_after_validation(case, {"status": "NOT_RUN"}, 2)
        text = (case / "BUSINESS_OUTCOME.txt").read_text()
        self.assertIn("Breaks leave a quarter unstaffed", text)
        self.assertNotIn("engine output problem", text)

    def test_a_diagnostics_run_is_reported_as_one(self):
        r = runner()
        case = self._case("PASS_DIAGNOSTICS_ONLY", {"outcome_code": "FINAL_SCHEDULE_GENERATED",
                                                    "headline": "Final schedule generated successfully"})
        r.reconcile_business_outcome_after_validation(case, {"status": "NOT_RUN"}, 0)
        text = (case / "BUSINESS_OUTCOME.txt").read_text()
        self.assertIn("Diagnostics", text)
        self.assertNotIn("engine output problem", text)
        self.assertNotIn("Final schedule generated successfully", text)

    def test_a_blocked_schedule_lists_why_it_is_blocked(self):
        r = runner()
        case = self._case("PASS_WITH_QUALITY_WARNINGS", {
            "outcome_code": "FINAL_SCHEDULE_GENERATED_WITH_DECLARED_QUALITY_DEBT", "production_eligible": True,
            "resource_findings": [{"code": "EMPLOYEE_ISOLATED_OFFDAY_EXCEEDED"}]})
        (case / "C_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx").write_bytes(b"x")
        validation = {"status": "FAIL_METRIC_PARITY", "return_code": 2,
                      "metric_parity": {"mismatches": [{"field": "after_target", "engine": 3, "validator": 2}]}}
        r.reconcile_business_outcome_after_validation(case, validation, 4)
        text = (case / "BUSINESS_OUTCOME.txt").read_text()
        self.assertIn("Why it is blocked:", text)
        self.assertIn("after_target", text)
        self.assertIn("Warnings:", text)
        self.assertNotIn("Main blockers:\n- EMPLOYEE_ISOLATED_OFFDAY_EXCEEDED", text)


class B6AlternativeExportsAreValidated(unittest.TestCase):
    def test_each_alternative_export_gets_a_validator_verdict(self):
        r = runner()
        case = Path(tempfile.mkdtemp())
        shutil.copy(PARITY / "S01_BASELINE_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
                    case / "S01_L6_3_2_3_MAX_TARGET_CANDIDATE.xlsx")
        results = r.validate_alternative_exports(case, PARITY / "S01_BASELINE.xlsx", None)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["role"], "MAX_TARGET_CANDIDATE")
        self.assertEqual(results[0]["status"], "PASS", results)


class B7InstructionRowsAreReadStrictly(unittest.TestCase):
    def test_unreadable_numbers_are_refused_on_every_numeric_row(self):
        for label in ("Count of Different Shifts Per week", "Overage Penalty Weight",
                      "Critical Coverage No-Break Max Associate-Days", "Quality Benchmark Tolerance Intervals",
                      "Next Sunday Overage Cap", "Break Preferred Gap Minutes", "Lunch Earliest Minutes From Shift Start",
                      "Demand Fit Minimum Active Minutes"):
            _, codes = parse(spec(instructions={label: "three"}))
            self.assertIn("HARD_INVALID_INSTRUCTION_NUMBER", codes, label)

    def test_zero_different_shifts_is_refused(self):
        _, codes = parse(spec(instructions={"Count of Different Shifts Per week": 0}))
        self.assertIn("INVALID_MAX_SHIFT_VARIETY", codes)

    def test_no_break_exceptions_enabled_with_a_zero_limit_is_refused(self):
        _, codes = parse(spec(instructions={"Critical Coverage No-Break Exception Enabled": "Yes",
                                            "Critical Coverage No-Break Max Associate-Days": 0}))
        self.assertIn("HARD_CONTRADICTORY_NO_BREAK_LIMIT", codes)

    def test_long_durations_without_11h_mode_are_refused(self):
        shifts = [f"{h:02d}:00 - {(h + 11) % 24:02d}:00" for h in range(24)] + DAY_SHIFTS
        _, codes = parse(spec(shifts=shifts, instructions={"Allowed Shift Durations Hours": 11, "Use 11H/3OFF": "No"}))
        self.assertIn("HARD_LONG_DURATION_WITHOUT_11H_MODE", codes)

    def test_a_label_given_twice_with_different_values_is_refused(self):
        paths = []
        parse(spec(), paths)
        from openpyxl import load_workbook
        wb = load_workbook(paths[0])
        wb["Instructions"].append(["Case", "Target", 0.85, None])
        wb.save(paths[0])
        parsed = E.parse_input(paths[0])
        codes = {f.get("code") for f in E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))["failures"]}
        self.assertIn("HARD_DUPLICATE_INSTRUCTION", codes)

    def test_the_same_label_twice_with_the_same_value_is_fine(self):
        paths = []
        parse(spec(), paths)
        from openpyxl import load_workbook
        wb = load_workbook(paths[0])
        wb["Instructions"].append(["Case", "Target", 0.9, None])
        wb.save(paths[0])
        parsed = E.parse_input(paths[0])
        codes = {f.get("code") for f in E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))["failures"]}
        self.assertNotIn("HARD_DUPLICATE_INSTRUCTION", codes)

    def test_a_notes_column_is_not_read_as_a_value(self):
        # Found by the 111-workbook snapshot: the RC8 Engine Defaults sheets are
        # headed Instruction | Value | Purpose and carry section rows
        # [section, label, note]. The note is not a second value of the label.
        paths = []
        parse(spec(), paths)
        from openpyxl import load_workbook
        wb = load_workbook(paths[0])
        ws = wb.create_sheet("Engine Defaults")
        ws.append(["Instruction", "Value", "Purpose"])
        ws.append(["overage control", "Overage Penalty Weight", "Kept from the earlier contract."])
        ws.append(["Overage Penalty Weight", 55, "Kept from the earlier contract."])
        ws.append(["overage", "Overage Penalty Weight", "Kept from the earlier contract."])
        wb.save(paths[0])
        parsed = E.parse_input(paths[0])
        codes = {f.get("code") for f in E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))["failures"]}
        self.assertFalse(codes, codes)
        self.assertEqual(parsed.overage_penalty_weight, 55)

    def test_a_clean_workbook_is_still_accepted(self):
        _, codes = parse(spec())
        self.assertFalse(codes, codes)


if __name__ == "__main__":
    unittest.main()
