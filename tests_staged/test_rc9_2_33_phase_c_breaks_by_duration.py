"""Phase C2 of the production-readiness audit (F-20): break entitlement by shift length.

Every shift used to get the one global break set (default 15/30/15). A workbook
may now state a different set for long shifts:

    Break Set For Shifts Of 10 Hours Or More = 15, 30, 15, 15

(minutes, in operational order; 30 minutes or more is a lunch). The set with the
largest threshold a shift reaches applies; a workbook without such a row is
unchanged. The engine, the independent validator and the clean-room checker
must all read it.

Written to FAIL on the engine before C2 and pass after.
"""
from __future__ import annotations

import importlib.util
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

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJKL"]
NINE = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
ELEVEN = [f"{h:02d}:00 - {(h + 11) % 24:02d}:00" for h in range(6, 10)]
LONG_SET = {"Break Set For Shifts Of 10 Hours Or More": "15, 30, 15, 15"}


def spec(**over):
    base = {"roster": [(n, "English") for n in NAMES[:10]], "shifts": NINE + ELEVEN,
            "demand": lambda d, m: 3 if 8 * 60 <= m < 20 * 60 else None,
            "instructions": {"Allowed Shift Durations Hours": "9, 11", "Use 11H/3OFF": "Yes"}}
    base.update(over)
    return base


def build(s):
    tmp = Path(tempfile.mkdtemp())
    path = tmp / "case.xlsx"
    W.build(s, path)
    parsed = E.parse_input(path)
    codes = {f.get("code") for f in E.validate_input_contract(parsed, E.capacity_diagnostics(parsed))["failures"]}
    return path, parsed, codes


def with_rows(rows):
    s = spec()
    s["instructions"] = dict(s["instructions"], **rows)
    return s


def load(path: Path, name: str):
    spec_ = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec_)
    sys.modules[name] = mod
    spec_.loader.exec_module(mod)
    return mod


class C2Parsing(unittest.TestCase):
    def test_without_a_row_every_shift_keeps_the_global_set(self):
        _, parsed, codes = build(spec())
        self.assertFalse(codes, codes)
        for minutes in (540, 660):
            self.assertEqual(E.break_segments_for(parsed, minutes), parsed.break_segments_q)

    def test_a_long_shift_row_applies_to_long_shifts_only(self):
        _, parsed, codes = build(with_rows(LONG_SET))
        self.assertFalse(codes, codes)
        self.assertEqual(E.break_segments_for(parsed, 540), parsed.break_segments_q)
        self.assertEqual(E.break_segments_for(parsed, 660),
                         ((1, "Break 1"), (2, "Lunch"), (1, "Break 2"), (1, "Break 3")))

    def test_the_largest_reached_threshold_wins(self):
        _, parsed, _ = build(with_rows({"Break Set For Shifts Of 10 Hours Or More": "15, 30, 15",
                                        "Break Set For Shifts Of 11 Hours Or More": "15, 45, 15"}))
        self.assertEqual(E.break_segments_for(parsed, 600), ((1, "Break 1"), (2, "Lunch"), (1, "Break 2")))
        self.assertEqual(E.break_segments_for(parsed, 660), ((1, "Break 1"), (3, "Lunch"), (1, "Break 2")))

    def test_unreadable_sets_are_refused(self):
        for value in ("15, 20", "fifteen", "15, -30", ""):
            if value == "":
                continue
            _, _, codes = build(with_rows({"Break Set For Shifts Of 10 Hours Or More": value}))
            self.assertIn("HARD_INVALID_BREAK_CONTRACT", codes, value)

    def test_a_set_longer_than_the_shift_is_refused(self):
        _, _, codes = build(with_rows({"Break Set For Shifts Of 9 Hours Or More": "60, 60, 60, 60, 60, 60, 60, 60, 60"}))
        self.assertIn("BREAKS_EXCEED_SHIFT", codes)

    def test_the_contract_fingerprint_carries_the_sets(self):
        _, a, _ = build(spec())
        _, b, _ = build(with_rows(LONG_SET))
        self.assertNotEqual(E.canonical_hash(E.canonical_contract_snapshot(a)),
                            E.canonical_hash(E.canonical_contract_snapshot(b)))


class C2Patterns(unittest.TestCase):
    def test_patterns_follow_the_shift_length(self):
        _, parsed, _ = build(with_rows(LONG_SET))
        patterns = E.generate_break_patterns(parsed, 24)
        by_duration = {}
        for p in patterns:
            by_duration.setdefault(p.duration_q * 15, []).append(p)
        self.assertTrue(by_duration[540] and by_duration[660])
        for p in by_duration[540]:
            self.assertEqual(sorted(length for _, length, _ in p.breaks), [1, 1, 2])
        for p in by_duration[660]:
            self.assertEqual(sorted(length for _, length, _ in p.breaks), [1, 1, 1, 2])


class C2EndToEnd(unittest.TestCase):
    def test_an_eleven_hour_schedule_gets_its_four_breaks_and_both_checkers_agree(self):
        path, parsed, codes = build(with_rows(LONG_SET))
        self.assertFalse(codes, codes)
        sk = E.build_skeleton(parsed, None, E.HardConfig(), 30, 2, io.StringIO())
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        E.ensure_before_break_metrics(parsed, sk)
        sol = E.solve_breaks(parsed, sk, 24, False, 30, 2, io.StringIO())
        self.assertIn(sol.cp_status, {"OPTIMAL", "FEASIBLE"})
        by_id = {p.index: p for p in sol.patterns}
        for (a, d), pid in sol.selected_pattern.items():
            shift = parsed.shifts[sk.selected_shift_index[a][d]]
            want = len(E.break_segments_for(parsed, shift.duration_min))
            self.assertEqual(len(by_id[pid].breaks), want, shift.label)
        out = path.parent / "case_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"
        E.write_output_workbook(path, out, parsed, sk, sol, E.capacity_diagnostics(parsed), [], {}, [],
                                artifact_type="BEST_FINAL_AFTER_BREAKS_SCHEDULE")
        iv = load(ROOT / "engine" / "tools" / "independent_validator.py", "iv_c2")
        result = iv.validate(path, out, ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
        break_failures = [f for f in result["failures"] if "BREAK" in str(f.get("type"))]
        self.assertEqual(break_failures, [])
        cr = load(REPO / "tools" / "clean_room_check.py", "clean_room_c2")
        k = cr.read_contract(path)
        sched, brk, exc = cr.read_output(out)
        report = cr.check(k, sched, brk, exc)
        self.assertNotIn("break_set", report["violations_by_rule"], report["violations"][:5])

    def test_the_break_capacity_diagnostic_counts_each_shift_its_own_set(self):
        # run_case measures break capacity on every skeleton. The first C2 build
        # left a stale name in it, and the S09 and S11 scenario runs stopped with
        # FAIL_UNEXPECTED_ENGINE_EXCEPTION (NameError) the moment Stage 1 succeeded.
        for rows in ({}, LONG_SET):
            _, parsed, _ = build(with_rows(rows))
            sk = E.build_skeleton(parsed, None, E.HardConfig(), 30, 2, io.StringIO())
            self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
            got = E.break_capacity_headcount_requirement(parsed, sk)
            want = sum(E.break_quarters_for(parsed, parsed.shifts[si].duration_min)
                       for row in sk.selected_shift_index for si in row if si is not None)
            self.assertEqual(got["break_quarters_required"], want, rows)
            if not rows:
                worked = sum(1 for row in sk.assignment for v in row if v != "OFF")
                self.assertEqual(got["break_quarters_required"], worked * 4)


if __name__ == "__main__":
    unittest.main()
