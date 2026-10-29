# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BD (owner, 2026-10-29: "if I added in Preference a separate OFF, to be accepted even if the instructions say no separate OFF; stick to the
instructions except for what is mentioned in Preference"): with Separate OFF Days = No every associate's OFF days must include a consecutive pair,
except an associate whose own Preference row names two hard OFF days that are not next to each other: that person gets those days, the rest of the
roster keeps the rule. Rule and acceptance: evidence/phase_bd/REQUESTS.md."""
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

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJ"]
DAY_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]


def spec(preferences, separate="No", fixed=None):
    found = {"roster": [(n, "English") for n in NAMES], "shifts": DAY_SHIFTS,
             "demand": lambda d, m: 3 if 8 * 60 <= m < 20 * 60 else None,
             "instructions": {"Separate OFF Days": separate, "Strict OFF Count": "Yes"}, "preferences": preferences}
    if fixed is not None:
        found["fixed"] = fixed
        found["instructions"]["Fixed Request Use"] = "Yes"
    return found


def parse(s):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "case.xlsx"
        W.build(s, path)
        return E.parse_input(path)


def off_days(row):
    return {d for d, v in enumerate(row) if str(v).upper() == "OFF"}


def adjacent(days):
    return any((d + 1) % 7 in days for d in days)


def solve(parsed):
    sk = E.build_skeleton(parsed, None, E.HardConfig(), 30.0, 2, io.StringIO())
    return sk


SEPARATE = {"Agent A": ["OFF", None, None, "OFF", None, None, None]}  # Sunday and Wednesday: not next to each other


class TheExceptionIsThePreference(unittest.TestCase):
    def test_the_engine_says_who_asks_for_separate_off_days(self):
        parsed = parse(spec(SEPARATE))
        asking = [a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)]
        self.assertEqual(asking, ["Agent A"])

    def test_two_off_days_that_are_next_to_each_other_are_not_a_separate_request(self):
        parsed = parse(spec({"Agent A": ["OFF", "OFF", None, None, None, None, None], "Agent B": ["OFF", None, None, None, None, None, None]}))
        self.assertEqual([a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)], [])

    def test_the_week_wraps_saturday_to_sunday(self):
        parsed = parse(spec({"Agent A": ["OFF", None, None, None, None, None, "OFF"]}))
        self.assertEqual([a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)], [])

    def test_a_preference_that_is_not_hard_does_not_count(self):
        s = spec(SEPARATE)
        s["instructions"]["Hard OFF Preferences"] = "No"
        parsed = parse(s)
        self.assertEqual([a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)], [])


class TheScheduleFollowsIt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parsed = parse(spec(SEPARATE))
        cls.sk = solve(cls.parsed)

    def test_the_request_is_planned_where_the_rule_alone_would_refuse_it(self):
        self.assertIn(self.sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        a = self.sk.assignment[0]
        self.assertEqual(off_days(a), {0, 3})  # Sunday and Wednesday

    def test_everyone_else_still_has_two_days_off_in_a_row(self):
        for name, row in zip(NAMES[1:], self.sk.assignment[1:]):
            self.assertTrue(adjacent(off_days(row)), (name, row))

    def test_the_checker_accepts_the_request_and_still_refuses_a_stranger_who_splits_theirs(self):
        parsed = self.parsed
        w = DAY_SHIFTS[0]
        rows = [["OFF", "OFF", w, w, w, w, w] for _ in parsed.associates]  # two days in a row for everyone
        rows[0] = ["OFF", w, w, "OFF", w, w, w]       # the request: Sunday and Wednesday
        rows[1] = ["OFF", w, w, "OFF", w, w, w]       # the same split, not asked for
        index = {s.label: s.index for s in parsed.shifts}
        selected = [[index.get(v) for v in row] for row in rows]
        sk = E.SkeletonSolution("test", "FEASIBLE", 0.0, 0.0, [list(r) for r in rows], selected, {})
        metrics = E.calculate_metrics(parsed, sk, {}, [])
        br = E.BreakSolution("test", "test", "FEASIBLE", 0.0, 0.0, 0, False, {}, set(), [], {}, metrics)
        failures = E.validate_schedule(parsed, sk, br)["failures"]
        consecutive = [f for f in failures if f["type"] == "consecutive_off"]
        self.assertEqual([f.get("associate") for f in consecutive], ["Agent B"])


class TheFixedRequestSheetIsTreatedTheSame(unittest.TestCase):
    """Owner, 2026-10-29: "make Fixed like Preference": OFF days named on the Fixed Request sheet (when Fixed Request Use is Yes) count the
    same, alone or together with the Preference row."""

    def asking(self, **kw):
        parsed = parse(spec(kw.get("preferences", {}), fixed=kw.get("fixed")))
        return [a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)]

    def test_fixed_off_days_apart_are_a_request(self):
        self.assertEqual(self.asking(fixed={"Agent A": ["OFF", None, None, "OFF", None, None, None]}), ["Agent A"])

    def test_fixed_off_days_next_to_each_other_are_not(self):
        self.assertEqual(self.asking(fixed={"Agent A": ["OFF", "OFF", None, None, None, None, None]}), [])

    def test_one_day_on_each_sheet_that_are_apart_are_a_request(self):
        self.assertEqual(self.asking(preferences={"Agent A": ["OFF", None, None, None, None, None, None]},
                                     fixed={"Agent A": [None, None, None, "OFF", None, None, None]}), ["Agent A"])

    def test_the_fixed_sheet_does_not_count_when_fixed_requests_are_not_in_use(self):
        s = spec({}, fixed={"Agent A": ["OFF", None, None, "OFF", None, None, None]})
        s["instructions"]["Fixed Request Use"] = "No"
        parsed = parse(s)
        self.assertEqual([a.name for a in parsed.associates if E.separate_off_in_preference(parsed, a)], [])

    def test_the_schedule_follows_a_fixed_request_too(self):
        parsed = parse(spec({}, fixed={"Agent A": ["OFF", None, None, "OFF", None, None, None]}))
        sk = solve(parsed)
        self.assertIn(sk.cp_status, {"OPTIMAL", "FEASIBLE"})
        self.assertEqual(off_days(sk.assignment[0]), {0, 3})
        for name, row in zip(NAMES[1:], sk.assignment[1:]):
            self.assertTrue(adjacent(off_days(row)), (name, row))

    def test_the_search_guidance_counts_it_outside_the_pairs(self):
        got = E.aggregate_pattern_mix_guidance(parse(spec({}, fixed={"Agent A": ["OFF", None, None, "OFF", None, None, None]})), 20.0)
        self.assertEqual(sum(got["off_pair_targets"].values()), len(NAMES) - 1)


class TheSearchGuidanceAgrees(unittest.TestCase):
    """The aggregate guidance model (search guidance only) also counted every associate as owing a pair of OFF days; with the request it
    would otherwise ask the impossible, or place pairs where the named person is off on separate days."""

    def guidance(self, preferences):
        return E.aggregate_pattern_mix_guidance(parse(spec(preferences)), 20.0)

    def test_a_separate_request_keeps_the_guidance_feasible_and_counts_one_fewer_pair(self):
        asked = self.guidance(SEPARATE)
        plain = self.guidance({})
        self.assertNotIn(asked.get("status"), {"INFEASIBLE", "MODEL_INVALID"}, asked.get("status"))
        self.assertEqual(sum(asked["off_pair_targets"].values()), len(NAMES) - 1)
        self.assertEqual(sum(plain["off_pair_targets"].values()), len(NAMES))


if __name__ == "__main__":
    unittest.main()
