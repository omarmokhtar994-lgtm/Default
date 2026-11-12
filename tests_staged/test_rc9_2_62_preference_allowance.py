# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BP (owner, 2026-11-12: the asked shift is not given though people are available; a preference may cost coverage "maybe 1-2% maximum"):
after the swaps, one associate's day may move to the asked shift, free moves first, then moves whose cumulative coverage cost stays inside
PREFERENCE_COVERAGE_ALLOWANCE of the selected schedule. Rule and acceptance: evidence/phase_bp/PREFERENCE_ALLOWANCE_RULE.txt.

The made-up week: Monday to Friday, five people on 07:00 - 16:00 and five on 10:00 - 19:00. Demand is what they cover: 5 from 07:00, 10 from
10:00 to 16:00, 5 until 19:00, so every hour stands at exactly 100% (60 hourly intervals at 100%; 2% of that is 1 interval)."""
from __future__ import annotations

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

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location("runner_bp", ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py")
RUNNER = importlib.util.module_from_spec(_spec)
sys.modules["runner_bp"] = RUNNER
_spec.loader.exec_module(RUNNER)

SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
EARLY, NEXT, LATE = "07:00 - 16:00", "08:00 - 17:00", "10:00 - 19:00"
NAMES = [f"Agent {c}" for c in "ABCDEFGHIJ"]
WORKS = {name: (EARLY if i < 5 else LATE) for i, name in enumerate(NAMES)}


def need(short_first_hour=0):
    def demand(d, m):
        if not 1 <= d <= 5 or not 7 * 60 <= m < 19 * 60:
            return None
        if m < 8 * 60:
            return 5 - short_first_hour
        return 5 if m < 10 * 60 or m >= 16 * 60 else 10
    return demand


def build(prefs, demand, instructions=None):
    found = {"roster": [(n, "English") for n in NAMES], "shifts": SHIFTS, "demand": demand,
             "instructions": {"Separate OFF Days": "Yes", **(instructions or {})}, "preferences": prefs}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        W.build(found, path)
        parsed = E.parse_input(path)
    index = {s.label: s.index for s in parsed.shifts}
    rows = [[index[WORKS[a.name]] if 1 <= d <= 5 else None for d in range(7)] for a in parsed.associates]
    labels = [[parsed.shifts[si].label if si is not None else "OFF" for si in row] for row in rows]
    sk = E.SkeletonSolution(profile="t", cp_status="OPTIMAL", objective=0, elapsed_sec=0.0, assignment=labels,
                            selected_shift_index=rows, diagnostics={})
    cells = {(a, d): None for a in range(len(rows)) for d in range(7) if rows[a][d] is not None}
    metrics = E.calculate_metrics(parsed, sk, cells, [])
    br = E.BreakSolution(profile="t", skeleton_profile="t", cp_status="OPTIMAL", elapsed_sec=0.0, objective=0, pattern_width=0,
                         exception_mode=False, selected_pattern=cells, no_break_cells=set(cells), patterns=[], diagnostics={}, metrics=metrics)
    return parsed, sk, br


def asks(days, shift=NEXT, who="Agent A"):
    return {who: [shift if d in days else None for d in range(7)]}


def falls(new, old):
    return {k: float(old.get(k) or 0) - float(new.get(k) or 0) for k in E.SHIFT_CONSISTENCY_GUARD_HIGHER
            if float(new.get(k) or 0) < float(old.get(k) or 0)}


class TheFreeMove(unittest.TestCase):
    """The first hour needs one fewer than is there, so Agent A can start an hour later on Monday at no cost: nobody to swap with is needed."""

    def setUp(self):
        self.parsed, self.sk, self.br = build(asks({1}), need(short_first_hour=1))

    def test_the_asked_shift_is_given_when_it_costs_nothing(self):
        new_sk, new_br, record = E.preference_swap_polish(self.parsed, self.sk, self.br)
        self.assertEqual(record["status"], "APPLIED")
        self.assertEqual(new_sk.assignment[0][1], NEXT)
        self.assertEqual((record["moves"], record["swaps"]), (1, 0))
        self.assertEqual(falls(new_br.metrics, self.br.metrics), {})
        self.assertEqual(record["coverage_cost"], {})

    def test_it_is_given_with_no_allowance_too(self):
        new_sk, _, record = E.preference_swap_polish(self.parsed, self.sk, self.br, allowance=0.0)
        self.assertEqual((record["status"], new_sk.assignment[0][1]), ("APPLIED", NEXT))

    def test_use_preferences_no_still_turns_everything_off(self):
        parsed, sk, br = build(asks({1}), need(short_first_hour=1), {"Use Preferences": "No"})
        new_sk, new_br, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, sk)
        self.assertIs(new_br, br)


class TheMoveThatCostsALittle(unittest.TestCase):
    """Every hour is needed, so Monday an hour later leaves one hour under 100%: 1 of 60 intervals, inside 2% (floor(1.2) = 1)."""

    def setUp(self):
        self.parsed, self.sk, self.br = build(asks({1}), need())

    def test_the_day_as_it_stands(self):
        self.assertEqual(self.br.metrics["before_100"], 60)
        self.assertEqual(E.PREFERENCE_COVERAGE_ALLOWANCE, 0.02)

    def test_it_is_made_inside_the_allowance_and_the_cost_is_recorded(self):
        new_sk, new_br, record = E.preference_swap_polish(self.parsed, self.sk, self.br)
        self.assertEqual(record["status"], "APPLIED")
        self.assertEqual(new_sk.assignment[0][1], NEXT)
        lost = falls(new_br.metrics, self.br.metrics)
        self.assertEqual(lost.get("before_100"), 1)
        for key, drop in lost.items():
            self.assertLessEqual(drop, int(0.02 * float(self.br.metrics[key])), key)
        self.assertEqual(record["coverage_cost"], lost)
        self.assertEqual(record["allowance"], 0.02)
        for key in E.SHIFT_CONSISTENCY_GUARD_LOWER:
            if "overage" not in key:
                self.assertLessEqual(float(new_br.metrics.get(key) or 0), float(self.br.metrics.get(key) or 0), key)

    def test_the_selected_schedule_is_not_touched(self):
        before = [list(r) for r in self.sk.assignment]
        new_sk, _, _ = E.preference_swap_polish(self.parsed, self.sk, self.br)
        self.assertIsNot(new_sk, self.sk)
        self.assertEqual(self.sk.assignment, before)

    def test_with_no_allowance_it_is_refused(self):
        new_sk, new_br, record = E.preference_swap_polish(self.parsed, self.sk, self.br, allowance=0.0)
        self.assertEqual(record["status"], "NO_CHANGE")
        self.assertIs(new_sk, self.sk)
        self.assertIs(new_br, self.br)


class TheAllowanceIsForTheWholeWeek(unittest.TestCase):
    def test_a_second_move_past_the_allowance_is_not_made(self):
        # Monday and Tuesday an hour later would be 2 of 60 intervals (3.3%): one day is given, the other is not
        parsed, sk, br = build(asks({1, 2}), need())
        new_sk, new_br, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual(record["moves"], 1)
        self.assertEqual(sorted([new_sk.assignment[0][1], new_sk.assignment[0][2]]), sorted([EARLY, NEXT]))
        self.assertEqual(falls(new_br.metrics, br.metrics).get("before_100"), 1)
        self.assertGreaterEqual(record["moves_refused_by"].get("before_100", 0), 1)  # the audit says what refused the other day

    def test_a_swap_and_a_move_together_stay_inside_it(self):
        # 09:00 is two hours later, but a swap with a 10:00 person first costs nothing and one hour earlier from there costs one interval
        parsed, sk, br = build(asks({1}, shift="09:00 - 18:00"), need())
        new_sk, new_br, record = E.preference_swap_polish(parsed, sk, br)
        self.assertEqual((record["swaps"], record["moves"], new_sk.assignment[0][1]), (1, 1, "09:00 - 18:00"))
        self.assertEqual(falls(new_br.metrics, br.metrics).get("before_100"), 1)


class TheCostOfACandidate(unittest.TestCase):
    SELECTED = {"before_100": 60, "after_target": 60, "language_gap_count": 0, "after_avoidable_overage_fte_sum": 1.0}

    def cost(self, allowance=0.02, **changed):
        return E.preference_allowance_cost({**self.SELECTED, **changed}, self.SELECTED, allowance)

    def test_nothing_worse_costs_nothing(self):
        self.assertEqual(self.cost(), {})

    def test_one_interval_of_sixty_is_inside_two_percent(self):
        self.assertEqual(self.cost(before_100=59), {"before_100": 1.0})

    def test_two_intervals_of_sixty_are_outside_it(self):
        self.assertIsNone(self.cost(before_100=58))

    def test_a_new_gap_is_never_inside_it(self):
        self.assertIsNone(self.cost(language_gap_count=1))

    def test_more_surplus_is_accepted_only_with_an_allowance(self):
        self.assertEqual(self.cost(after_avoidable_overage_fte_sum=2.0), {})
        self.assertIsNone(self.cost(allowance=0.0, after_avoidable_overage_fte_sum=2.0))

    def test_no_allowance_refuses_any_fall(self):
        self.assertIsNone(self.cost(allowance=0.0, before_100=59))


class TheRunnersOwnCheck(unittest.TestCase):
    """The runner compares the independent validator's numbers for the two workbooks; it does not trust the engine's claim."""
    MAIN = {"after_target": 100, "after_floor": 120, "after100": 90, "after90": 100, "after80": 110, "severe_floor_gaps": 0,
            "language_gap_count": 0, "zero_staffed_active_quarters": 0, "coverage_split_gap_count": 0, "break_concurrency_violation_count": 0}

    def test_the_same_coverage_is_offered_at_no_cost(self):
        self.assertEqual(RUNNER.preference_coverage_verdict(self.MAIN, dict(self.MAIN), 0.02), (True, [], {}))

    def test_a_fall_inside_two_percent_is_offered_with_its_cost(self):
        ok, losses, cost = RUNNER.preference_coverage_verdict(self.MAIN, {**self.MAIN, "after_target": 98, "after100": 89}, 0.02)
        self.assertEqual((ok, losses, cost), (True, [], {"after_target": 2.0, "after100": 1.0}))

    def test_a_fall_past_two_percent_is_not_offered(self):
        ok, losses, _ = RUNNER.preference_coverage_verdict(self.MAIN, {**self.MAIN, "after_target": 97}, 0.02)
        self.assertEqual((ok, losses), (False, ["after_target"]))

    def test_a_new_gap_is_not_offered(self):
        ok, losses, _ = RUNNER.preference_coverage_verdict(self.MAIN, {**self.MAIN, "language_gap_count": 1}, 0.02)
        self.assertEqual((ok, losses), (False, ["language_gap_count"]))

    def test_the_engine_cannot_claim_a_bigger_allowance(self):
        ok, _, _ = RUNNER.preference_coverage_verdict(self.MAIN, {**self.MAIN, "after_target": 95}, 0.10)
        self.assertFalse(ok)
        self.assertEqual(RUNNER.PREFERENCE_COVERAGE_ALLOWANCE_MAX, 0.02)

    def test_the_outcome_text_says_what_it_costs(self):
        alt = {"role": "PREFERENCE_CANDIDATE", "status": "PASS", "coverage_no_worse": True, "workbook": "X_PREFERENCE_CANDIDATE.xlsx",
               "coverage_cost": {"after_target": 2.0}, "allowance": 0.02,
               "preference": {"swaps": 1, "moves": 3, "matched_before": 10, "matched_after": 14}}
        text = "\n".join(RUNNER.preference_candidate_lines(alt))
        self.assertIn("Preference shifts matched 10 -> 14 (1 same-day swaps, 3 moves to the asked shift)", text)
        self.assertIn("It costs coverage inside the 2% allowance: after_target 2 lower", text)
        self.assertNotIn("same coverage", text)
        free = "\n".join(RUNNER.preference_candidate_lines({**alt, "coverage_cost": {}}))
        self.assertIn("same coverage", free)


if __name__ == "__main__":
    unittest.main()
