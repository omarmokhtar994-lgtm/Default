# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BE (owner, 2026-10-29: "it doesn't take [preference] really into consideration even there is availability"): after the schedule is chosen,
two associates of one language and shift length may swap a day when both stay at least as close to their Preference shift and one gets closer,
with coverage and every guarded measure unchanged. Rule and acceptance: evidence/phase_be/REQUESTS.md."""
from __future__ import annotations

import importlib.util
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

_spec = importlib.util.spec_from_file_location("runner_be", ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py")
RUNNER = importlib.util.module_from_spec(_spec)
sys.modules["runner_be"] = RUNNER
_spec.loader.exec_module(RUNNER)
ROLE = "PREFERENCE_CANDIDATE"
_vspec = importlib.util.spec_from_file_location("validator_be", ROOT / "engine" / "tools" / "independent_validator.py")
IV = importlib.util.module_from_spec(_vspec)
sys.modules["validator_be"] = IV
_vspec.loader.exec_module(IV)

EARLY, LATE = "06:00 - 15:00", "10:00 - 19:00"
SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
MON = 1


def build(roster, prefs, works, instructions=None, fixed=None):
    """works: {name: shift label worked on Monday}. Everything else is OFF."""
    found = {"roster": roster, "shifts": SHIFTS, "demand": lambda d, m: 1 if 8 * 60 <= m < 20 * 60 else None,
             "instructions": dict(instructions or {}), "preferences": prefs}
    if fixed is not None:
        found["fixed"] = fixed
        found["instructions"]["Fixed Request Use"] = "Yes"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        W.build(found, path)
        parsed = E.parse_input(path)
    index = {s.label: s.index for s in parsed.shifts}
    rows = [[index[works[a.name]] if d == MON and a.name in works else None for d in range(7)] for a in parsed.associates]
    labels = [[parsed.shifts[si].label if si is not None else "OFF" for si in row] for row in rows]
    sk = E.SkeletonSolution(profile="t", cp_status="OPTIMAL", objective=0, elapsed_sec=0.0, assignment=labels,
                            selected_shift_index=rows, diagnostics={})
    cells = {(a, d): None for a in range(len(rows)) for d in range(7) if rows[a][d] is not None}
    metrics = E.calculate_metrics(parsed, sk, cells, [])
    br = E.BreakSolution(profile="t", skeleton_profile="t", cp_status="OPTIMAL", elapsed_sec=0.0, objective=0, pattern_width=0,
                         exception_mode=False, selected_pattern=cells, no_break_cells=set(cells), patterns=[], diagnostics={}, metrics=metrics)
    return parsed, sk, br


def pref(**by_name):
    return {name: [None, value, None, None, None, None, None] for name, value in by_name.items()}


ENGLISH = [("Agent A", "English"), ("Agent B", "English")]


class TheSwap(unittest.TestCase):
    def test_two_associates_who_each_want_the_other_shift_swap(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE})
        new_sk, new_br, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "APPLIED")
        self.assertEqual([new_sk.assignment[0][MON], new_sk.assignment[1][MON]], [LATE, EARLY])
        self.assertGreater(E.employee_operational_quality(parsed, new_sk)["preference_match_count"],
                           E.employee_operational_quality(parsed, sk)["preference_match_count"])

    def test_coverage_numbers_do_not_move(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE})
        _, new_br, _ = E.preference_swap_polish(parsed, sk, br)
        for key in E.SHIFT_CONSISTENCY_GUARD_HIGHER + E.SHIFT_CONSISTENCY_GUARD_LOWER:
            self.assertEqual(new_br.metrics.get(key), br.metrics.get(key), key)

    def test_a_swap_that_hurts_one_side_is_not_made(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": LATE}), {"Agent A": EARLY, "Agent B": LATE})
        new_sk, new_br, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, sk)
        self.assertIs(new_br, br)

    def test_different_languages_never_swap(self):
        roster = [("Agent A", "English"), ("Agent B", "Arabic")]
        parsed, sk, br = build(roster, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE})
        new_sk, _, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, sk)

    def test_a_fixed_request_is_never_moved(self):
        fixed = {"Agent A": [None, EARLY, None, None, None, None, None]}
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE}, fixed=fixed)
        new_sk, _, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, sk)

    def test_use_preferences_no_turns_it_off(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE},
                               instructions={"Use Preferences": "No"})
        new_sk, _, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, sk)

    def test_an_associate_without_a_preference_is_a_free_partner(self):
        roster = ENGLISH
        parsed, sk, br = build(roster, pref(**{"Agent A": LATE}), {"Agent A": EARLY, "Agent B": LATE})
        new_sk, _, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "APPLIED")
        self.assertEqual(new_sk.assignment[0][MON], LATE)


class TheReviewFindings(unittest.TestCase):
    """Review of 2026-11-02: each of these failed before the fix."""

    def test_the_separate_off_exception_follows_the_stage_one_relaxation(self):
        # A relaxed Stage 1 profile does not enforce hard OFF, so it must not lift the consecutive-OFF rule for it either.
        found = {"roster": [("Agent A", "English")], "shifts": SHIFTS, "demand": lambda d, m: 1 if 8 * 60 <= m < 20 * 60 else None,
                 "instructions": {"Separate OFF Days": "No"}, "preferences": {"Agent A": ["OFF", None, None, "OFF", None, None, None]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case.xlsx"
            W.build(found, path)
            parsed = E.parse_input(path)
        assoc = parsed.associates[0]
        self.assertTrue(E.separate_off_in_preference(parsed, assoc))
        self.assertTrue(E.separate_off_in_preference(parsed, assoc, E.HardConfig()))
        self.assertFalse(E.separate_off_in_preference(parsed, assoc, E.HardConfig(hard_off=False)))

    def test_a_swap_that_is_thrown_away_is_not_counted(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE})
        original = E.validate_schedule
        E.validate_schedule = lambda p, skeleton, b: {"hard_fail_count": 0 if skeleton is sk else 99}  # only the swapped pair fails
        try:
            new_sk, _, record = E.preference_swap_polish(parsed, sk, br)
        finally:
            E.validate_schedule = original
        self.assertEqual(record["status"], "KEPT_ORIGINAL")
        self.assertEqual(record["swaps"], 0)
        self.assertEqual(record["swaps_discarded"], 1)

    def test_running_out_of_time_is_said_in_the_record(self):
        parsed, sk, br = build(ENGLISH, pref(**{"Agent A": LATE, "Agent B": EARLY}), {"Agent A": EARLY, "Agent B": LATE})
        _, _, record = E.preference_swap_polish(parsed, sk, br, time_limit_sec=-1.0)
        self.assertTrue(record["stopped_by_time_limit"])


class TheSwapIsASeparateCandidate(unittest.TestCase):
    """Owner, 2026-11-02: publish the swapped week beside the recommended schedule, never in its place (F-35)."""

    def pair(self, name):
        return (type("S", (), {"profile": name})(), type("B", (), {"profile": name})())

    def test_the_engine_runner_and_cleanup_know_the_role(self):
        order = list(E.EXPORT_ROLE_ORDER)
        self.assertIn(ROLE, order)
        self.assertLess(order.index("MORE_CONSISTENT_CANDIDATE"), order.index(ROLE))
        self.assertLess(order.index(ROLE), order.index("BALANCED_CANDIDATE"))
        self.assertIn(ROLE, RUNNER.ALTERNATIVE_EXPORT_ROLES)
        self.assertIn(ROLE, RUNNER.ALTERNATIVE_USE)
        source = (ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_text()
        self.assertIn('output_path.with_name(prefix + "_PREFERENCE_CANDIDATE" + output_path.suffix)', source)

    def test_an_applied_swap_adds_an_export_and_leaves_the_selection(self):
        selected, swapped = self.pair("selected"), self.pair("swapped")
        selection = {"recommended": selected, "exports": [("RECOMMENDED_FINAL", selected)]}
        self.assertTrue(E.add_preference_export(selection, swapped, {"status": "APPLIED"}))
        self.assertIs(selection["recommended"], selected)
        self.assertIs(E.recommended_export_pair(selection), selected)
        self.assertEqual([r for r, _ in selection["exports"]], ["RECOMMENDED_FINAL", ROLE])
        self.assertIs(dict(selection["exports"])[ROLE], swapped)
        self.assertFalse(E.add_preference_export(selection, swapped, {"status": "APPLIED"}))

    def test_nothing_is_added_when_no_swap_was_kept(self):
        for status in ("NO_CHANGE", "KEPT_ORIGINAL"):
            selected = self.pair("selected")
            selection = {"recommended": selected, "exports": [("RECOMMENDED_FINAL", selected)]}
            self.assertFalse(E.add_preference_export(selection, self.pair("p"), {"status": status}), status)
            self.assertEqual(len(selection["exports"]), 1)

    def test_the_outcome_text_offers_it_only_when_the_validator_approved_it(self):
        row = {"role": ROLE, "status": "PASS", "coverage_no_worse": True,
               "workbook": "/x/case_L6_3_2_3_PREFERENCE_CANDIDATE.xlsx",
               "preference": {"swaps": 13, "matched_before": 21, "matched_after": 34}}
        text = RUNNER._outcome_detail_text({"independent_validation": {"alternative_exports": [row]}})
        self.assertIn("case_L6_3_2_3_PREFERENCE_CANDIDATE.xlsx", text)
        self.assertIn("21 -> 34", text)
        refused = {"independent_validation": {"alternative_exports": [dict(row, coverage_no_worse=False)]}}
        self.assertNotIn("PREFERENCE_CANDIDATE.xlsx", RUNNER._outcome_detail_text(refused))

    def test_the_independent_validator_reads_the_workbooks_own_role_as_a_final_schedule(self):
        # Found by running the candidate through the validator: it was refused as UNRECOGNIZED:preference_candidate.
        import openpyxl
        parsed, sk, br = build(ENGLISH, pref(), {"Agent A": EARLY, "Agent B": LATE})
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.xlsx"
            W.build({"roster": ENGLISH, "shifts": SHIFTS, "demand": lambda d, m: 1 if 8 * 60 <= m < 20 * 60 else None}, src)
            out = Path(tmp) / "case_PREFERENCE_CANDIDATE.xlsx"
            E.write_output_workbook(src, out, parsed, sk, br, E.capacity_diagnostics(parsed), [], {}, [], artifact_type=ROLE)
            self.assertEqual(IV.declared_artifact_type(out), "FINAL_AFTER_BREAKS")


if __name__ == "__main__":
    unittest.main()
