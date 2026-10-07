"""Phase E, F-E3: how Stage 1 stands in for breaks, made measurable.

Stage 1 counts every head on a shift at a flat (paid - break) / paid presence
in every quarter (`productive_coeff` in build_skeleton). Breaks can only fall
inside each shift's break windows, so a window-aware stand-in is 1.0 outside
them. tools/break_proxy_diagnostic.py compares how well each predicts the
engine's after-break metric on saved weeks (evidence/phase_e/E_PLAN.md).

Pinned: the flat profile equals Stage 1's coefficient; the window profile is
1.0 at a 9-hour shift's first and last quarter and has the same total
presence as the flat one (same break minutes, only placed differently).
"""
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CANDIDATE_ENGINE", REPO)).resolve()
sys.path.insert(0, str(REPO / "tools"))
import break_proxy_diagnostic as D  # noqa: E402
import build_synthetic_suite as B  # noqa: E402

E = B.load_engine(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
# Repo layout or package layout (inputs/ at the package root). Phase G: the
# repo-only path made this suite fail to import inside the built package; the
# lookup changed, not the contract.
CHAT = next(p for p in (REPO / "inputs", REPO / "packages" / "rc9_2_2_production" / "inputs")
            if p.is_dir()) / "ready_to_edit" / "Cricut_Chat_WEEKLY_INPUT.xlsx"
P = E.parse_input(CHAT)
NINE_H = next(s for s in P.shifts if s.duration_min == 540)


class TheFlatProfileIsStageOnesStandIn(unittest.TestCase):
    def test_flat_profile_is_constant_and_matches_productive_coeff(self):
        prof = D.presence_profile(E, P, NINE_H, "flat")
        expected = (NINE_H.duration_q - E.break_quarters_for(P, NINE_H.duration_min)) / NINE_H.duration_q
        self.assertEqual(len(prof), NINE_H.duration_q)
        for v in prof:
            self.assertAlmostEqual(v, expected, places=12)


class TheWindowProfilePlacesTheSameBreakTime(unittest.TestCase):
    def test_window_profile_is_1_outside_every_break_window_and_sums_to_the_same_paid_presence(self):
        flat = D.presence_profile(E, P, NINE_H, "flat")
        win = D.presence_profile(E, P, NINE_H, "window")
        self.assertEqual(len(win), NINE_H.duration_q)
        self.assertAlmostEqual(sum(win), sum(flat), places=9)
        self.assertEqual(win[0], 1.0)
        self.assertEqual(win[-1], 1.0)
        self.assertTrue(all(0.0 <= v <= 1.0 for v in win))


if __name__ == "__main__":
    unittest.main()
