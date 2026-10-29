# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BE (owner, 2026-10-29: "it doesn't take [preference] really into consideration even there is availability"): after the schedule is chosen,
two associates of one language and shift length may swap a day when both stay at least as close to their Preference shift and one gets closer,
with coverage and every guarded measure unchanged. Rule and acceptance: evidence/phase_be/REQUESTS.md."""
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


if __name__ == "__main__":
    unittest.main()
