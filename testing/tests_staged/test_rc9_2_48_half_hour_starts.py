"""Phase F, task 2: optional half-hour starts as a marked fallback.

Owner decision (2026-10-07): ":30 starts as a marked fallback when :00 starts
cannot cover demand - make it optional in the input sheet".

"Allow Half-Hour Starts" = Yes (default No) gives every on-the-hour library
shift a twin starting 30 minutes later, same length, flagged
half_hour_fallback. Stage 1 charges each use of a twin a small penalty, below
any coverage gain, so a twin is picked only where it improves coverage.

Pinned here:
  * default No: library, contract fingerprint and solves unchanged;
  * Yes: flagged twins exist, originals stay unflagged, no duplicates;
  * Yes, demand the :00 shifts cover exactly: no twin is used;
  * Yes, demand only a :30 start covers: a twin is used and coverage rises;
  * half_hour_fallback_usage counts the twins a week uses (output marking).
"""
import copy
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
TEMPLATE = REPO / "fixtures" / "SYNTHETIC_FIXTURE_FLOOR_NOT_80.xlsx"
SWITCH = "Allow Half-Hour Starts"


def workbook(switch=None, interval=60, starts=(8 * 60, 12 * 60), demand=None, n=14):
    names, langs = B.english(n)
    settings = {"Short Break Count": 0, "Lunch Count": 0}
    if switch is not None:
        settings[SWITCH] = switch
    case = dict(id="F2_HALF", tier="test", associates=n, shift_starts=list(starts), shift_minutes=540,
                shrinkage=0.0, interval_minutes=interval, names=names, languages=langs,
                language_rules=B.ENGLISH_RULE, settings=settings)
    if demand is None:
        demand = [[(3.0 if 8 <= h < 21 else None) for h in range(24)] for _ in range(7)]
    out = Path(tempfile.mkdtemp()) / "F2_HALF.xlsx"
    B.build_workbook(TEMPLATE, out, copy.deepcopy(case), E, demand)
    return out


def labels(p):
    return sorted(s.label for s in p.shifts)


def solve(p, seconds=20.0):
    prof = next(pr for pr in E.skeleton_profiles(["target90_restore_champion"]) if pr["name"] == "target90_restore_champion")
    # Elastic (audit F-06): an uncoverable minimum is a priced shortfall, as in
    # production's shortfall pass, so the switch-off arm still yields a week.
    sk = E.build_skeleton(p, dict(prof), E.HardConfig(hard_floor=False, elastic=True), seconds, 2, None,
                          random_seed=9000)
    assert sk.cp_status in ("OPTIMAL", "FEASIBLE"), sk.cp_status
    return sk


class TheSwitchDefaultsOff(unittest.TestCase):
    def test_default_off_and_library_unchanged(self):
        p = E.parse_input(workbook())
        self.assertFalse(p.allow_half_hour_starts)
        self.assertEqual(labels(p), ["08:00 - 17:00", "12:00 - 21:00"])
        self.assertFalse(any(getattr(s, "half_hour_fallback", False) for s in p.shifts))

    def test_contract_key_only_when_on(self):
        self.assertNotIn("allow_half_hour_starts", E.input_contract_payload(E.parse_input(workbook())))
        self.assertTrue(E.input_contract_payload(E.parse_input(workbook("Yes"))).get("allow_half_hour_starts"))


class TheSwitchAddsFlaggedTwins(unittest.TestCase):
    def test_yes_adds_one_flagged_twin_per_on_the_hour_shift(self):
        p = E.parse_input(workbook("Yes"))
        self.assertEqual(labels(p), ["08:00 - 17:00", "08:30 - 17:30", "12:00 - 21:00", "12:30 - 21:30"])
        flagged = sorted(s.label for s in p.shifts if s.half_hour_fallback)
        self.assertEqual(flagged, ["08:30 - 17:30", "12:30 - 21:30"])
        self.assertEqual([s.index for s in p.shifts], list(range(len(p.shifts))))


class StageOneUsesTwinsOnlyWhereTheyHelp(unittest.TestCase):
    def test_no_twin_when_full_hour_shifts_cover_exactly(self):
        # Demand 08:00-21:00: the 08:00 and 12:00 shifts fit it exactly.
        p = E.parse_input(workbook("Yes"))
        sk = solve(p)
        self.assertEqual(E.half_hour_fallback_usage(p, sk)["shift_days"], 0)

    def test_twin_used_when_only_a_half_hour_start_covers(self):
        # 30-minute demand from 08:00 to 17:30 with a single 08:00 library shift:
        # 17:00-17:30 is reachable only from an 08:30 start, so only a mix of
        # 08:00 and 08:30 starts covers the whole day.
        demand = [[(3.0 if 16 <= i < 35 else None) for i in range(48)] for _ in range(7)]
        off = E.parse_input(workbook(None, interval=30, starts=(8 * 60,), demand=demand))
        on = E.parse_input(workbook("Yes", interval=30, starts=(8 * 60,), demand=demand))
        patterns = E.generate_break_patterns(on)
        m_off = E.calculate_metrics(off, solve(off), {}, E.generate_break_patterns(off))
        sk_on = solve(on)
        m_on = E.calculate_metrics(on, sk_on, {}, patterns)
        self.assertGreater(E.half_hour_fallback_usage(on, sk_on)["shift_days"], 0)
        self.assertGreater(m_on["before_target"], m_off["before_target"])



class TheOutputMarksTheTwins(unittest.TestCase):
    """Production Summary rows exist only when the switch is on, so default
    outputs are unchanged."""

    def test_no_summary_rows_when_off(self):
        p = E.parse_input(workbook())
        self.assertEqual(E.half_hour_summary_rows(p, solve(p, 10.0)), [])

    def test_summary_rows_name_count_and_each_twin_shift_day(self):
        demand = [[(3.0 if 16 <= i < 35 else None) for i in range(48)] for _ in range(7)]
        p = E.parse_input(workbook("Yes", interval=30, starts=(8 * 60,), demand=demand))
        sk = solve(p)
        rows = dict(E.half_hour_summary_rows(p, sk))
        usage = E.half_hour_fallback_usage(p, sk)
        self.assertEqual(rows["Half-Hour Starts Allowed"], "Yes")
        self.assertEqual(rows["Half-Hour Fallback Shift-Days"], usage["shift_days"])
        self.assertIn(usage["rows"][0]["shift"], rows["Half-Hour Fallback Shifts"])

if __name__ == "__main__":
    unittest.main()
