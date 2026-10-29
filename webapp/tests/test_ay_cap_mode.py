# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "follow the shape as long as we have enough buffer in the intervals and ignore the cap"): the limit on
people on a break at once follows the workbook's Break Concurrency Gate Mode. Fail keeps it first (as before); Warn, the engine's
default, and Off let the intervals' buffer and the usual shape decide. The rule that accepts this is in evidence/phase_ay/REQUESTS.md."""
import collections
import unittest

from webapp.break_plan import QUARTER, fit, suggest
from webapp.tests.test_au_break_shape import floor
from webapp.tests.test_channel_plan import RULES
from webapp.tests.test_day import INPUTS, WED, WEEK
from webapp.versions import shift_span


def plan_for(cap, mode=None):
    rules = {**RULES, "max_concurrent": cap, "max_concurrent_ratio": 0.3}
    if mode:
        rules["concurrency_mode"] = mode
    return rules, suggest(WEEK, INPUTS, rules, WED, {})


def measure(rules, got):
    far, rule_far, peak = [], [], collections.Counter()
    for a in WEEK["associates"]:
        shift = a["days"][WED]
        if shift_span(shift) and a["name"] in got:
            shape, eng = fit(rules, shift, got[a["name"]])
            far.append(shape)
            rule_far.append(eng)
            for s, m in zip(got[a["name"]], (15, 30, 15)):
                if s is not None:
                    for q in range(s // QUARTER, (s + m) // QUARTER):
                        peak[q] += 1
    cells = floor(WEEK, INPUTS, WED, got, rules)
    return {"off": sum(1 for f in far if f), "worst": max(far), "rules": max(rule_far), "peak": max(peak.values()),
            "tightest": min(c["pm"] for c in cells if c["pm"] is not None)}


class TheLimitFollowsTheGateMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arm = {}
        for cap in (4, 2):
            for mode in ("fail", "warn", "off", None):
                rules, got = plan_for(cap, mode)
                cls.arm[cap, mode] = (got, measure(rules, got))

    def test_warn_and_off_and_no_mode_give_the_same_plan(self):
        for cap in (4, 2):
            self.assertEqual(self.arm[cap, "warn"][0], self.arm[cap, "off"][0], cap)
            self.assertEqual(self.arm[cap, "warn"][0], self.arm[cap, None][0], cap)  # a rules set kept before this says nothing: Warn

    def test_the_breaks_are_no_further_from_the_usual_shape_than_with_the_limit_first(self):
        for cap in (4, 2):
            a, b = self.arm[cap, "fail"][1], self.arm[cap, "warn"][1]
            self.assertLessEqual(b["off"], a["off"], (cap, a, b))
            self.assertLessEqual(b["worst"], a["worst"], (cap, a, b))

    def test_a_tight_limit_no_longer_pushes_first_breaks_off_the_shape(self):
        a, b = self.arm[2, "fail"][1], self.arm[2, "warn"][1]
        self.assertLess(b["off"], a["off"], (a, b))  # measured before the change: 7 people off the shape with the limit at 2

    def test_no_interval_is_left_worse_off_by_more_than_a_quarter_of_an_hour(self):
        for cap in (4, 2):
            a, b = self.arm[cap, "fail"][1], self.arm[cap, "warn"][1]
            self.assertGreaterEqual(b["tightest"], a["tightest"] - 0.25, (cap, a, b))

    def test_the_engines_gaps_and_overlaps_are_still_kept(self):
        for key, (_, m) in self.arm.items():
            self.assertEqual(m["rules"], 0, key)

    def test_fail_still_ranks_the_limit_first(self):
        # the measured plan of the limit-first ranking, as it was before the change (limit 4: 2 people off the shape, peak 4)
        self.assertEqual(self.arm[4, "fail"][1]["off"], 2)
        self.assertEqual(self.arm[4, "fail"][1]["peak"], 4)
        self.assertEqual(self.arm[2, "fail"][1]["off"], 7)

    def test_the_limit_no_longer_decides_so_more_people_may_be_on_a_break_together(self):
        self.assertGreater(self.arm[2, "warn"][1]["peak"], self.arm[2, "fail"][1]["peak"] - 1)  # not fewer than with the limit first


class TheKeptRulesAreReadAgain(unittest.TestCase):
    """Rules kept with a run before the gate mode was read have no ``concurrency_mode``; they are read again once, so that a workbook set
    to Fail is not taken for Warn."""

    def test_a_cache_without_the_mode_is_replaced(self):
        import json
        from webapp.tests.test_auto_breaks import _Book

        class Case(_Book):
            def runTest(self):
                pass

        Case.setUpClass()
        self.addCleanup(Case.tearDownClass)
        case = Case()
        case.setUp()
        cache = case.book.root / "rrrrrrrrrrrr" / "break_rules.json"
        stale = {k: v for k, v in json.loads(cache.read_text()).items() if k != "concurrency_mode"}
        cache.write_text(json.dumps(stale))
        again = case.book.break_rules(case.version["id"])
        self.assertIn(again["concurrency_mode"], ("warn", "fail", "off"))
        self.assertIn("concurrency_mode", json.loads(cache.read_text()))


if __name__ == "__main__":
    unittest.main()
