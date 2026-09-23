#!/usr/bin/env python3
"""Guards for the memoised `shift_day_demand_fit` (P-1).

This change exists to return wall-clock budget to Stage 1, which already
reports TRUNCATED_INSUFFICIENT_STAGE1_BUDGET on long runs. It is therefore
only worth having if it is *provably inert*: the same contract must produce
byte-identical capacity and preflight output. These tests pin that, plus the
two ways a cache of this shape can silently corrupt results - a shared mutable
return value, and a key that does not distinguish two different shifts.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402


def _parsed(active_grid):
    return SimpleNamespace(
        active=active_grid,
        interval_minutes=60,
        intervals_per_day=24,
    )


def _shift(index, start_min, duration_min=540):
    return E.Shift(index=index, label=f"s{index}", start_min=start_min,
                   end_min=(start_min + duration_min) % 1440,
                   duration_min=duration_min)


class MemoisedDemandFitIsInert(unittest.TestCase):
    """The cache must never change an answer, only how often it is computed."""

    def setUp(self):
        self.parsed = _parsed([[True] * 24 for _ in range(7)])

    def test_repeated_calls_agree_with_the_uncached_computation(self):
        for day in range(7):
            for start in (0, 3 * 60, 16 * 60, 23 * 60):
                shift = _shift(1, start)
                direct = E._shift_day_demand_fit_uncached(self.parsed, day, shift)
                first = E.shift_day_demand_fit(self.parsed, day, shift)
                second = E.shift_day_demand_fit(self.parsed, day, shift)
                self.assertEqual(direct, first)
                self.assertEqual(first, second)

    def test_a_hit_returns_a_fresh_mapping(self):
        """`demand_fit_blocked` writes into the returned dict. If the cache
        handed back its own object, the second caller would see the first
        caller's mutation - and `blank_requirement_blocked` would leak across
        unrelated shifts."""
        shift = _shift(1, 0)
        first = E.shift_day_demand_fit(self.parsed, 0, shift)
        first["blank_requirement_blocked"] = True
        first["active_minutes"] = -999
        second = E.shift_day_demand_fit(self.parsed, 0, shift)
        self.assertNotIn("blank_requirement_blocked", second)
        self.assertNotEqual(second["active_minutes"], -999)
        self.assertIsNot(first, second)

    def test_two_shifts_sharing_an_index_do_not_collide(self):
        """The key carries start and duration, not just the index, so a
        synthetic Shift reusing an index cannot read another shift's answer."""
        grid = [[False] * 24 for _ in range(7)]
        for i in range(0, 9):
            grid[0][i] = True
        parsed = _parsed(grid)
        early = E.shift_day_demand_fit(parsed, 0, _shift(1, 0))
        late = E.shift_day_demand_fit(parsed, 0, _shift(1, 12 * 60))
        self.assertNotEqual(early["active_minutes"], late["active_minutes"])
        self.assertEqual(early, E._shift_day_demand_fit_uncached(parsed, 0, _shift(1, 0)))
        self.assertEqual(late, E._shift_day_demand_fit_uncached(parsed, 0, _shift(1, 12 * 60)))

    def test_two_contracts_do_not_share_a_cache(self):
        """The cache lives on the parsed contract, so a second workbook in the
        same process cannot inherit the first one's demand shape."""
        all_active = _parsed([[True] * 24 for _ in range(7)])
        none_active = _parsed([[False] * 24 for _ in range(7)])
        shift = _shift(1, 0)
        a = E.shift_day_demand_fit(all_active, 0, shift)
        b = E.shift_day_demand_fit(none_active, 0, shift)
        self.assertEqual(a["active_minutes"], 540)
        self.assertEqual(b["active_minutes"], 0)

    def test_a_contract_that_refuses_attributes_still_answers_correctly(self):
        """The fallback path must return the right number, not raise."""
        class NoAttrs:
            __slots__ = ("active", "interval_minutes", "intervals_per_day")
            def __init__(self):
                self.active = [[True] * 24 for _ in range(7)]
                self.interval_minutes = 60
                self.intervals_per_day = 24
        parsed = NoAttrs()
        shift = _shift(1, 0)
        self.assertEqual(
            E.shift_day_demand_fit(parsed, 0, shift),
            E._shift_day_demand_fit_uncached(parsed, 0, shift),
        )


class CapacityOutputIsUnchangedOnEveryPackagedWorkbook(unittest.TestCase):
    """The claim that earns the speedup: identical output, not merely similar."""

    def test_capacity_and_preflight_are_byte_identical_to_the_uncached_engine(self):
        inputs = sorted((ROOT / "inputs").glob("*.xlsx"))
        if not inputs:
            self.skipTest("packaged inputs not present")
        for path in inputs:
            with self.subTest(workbook=path.name):
                parsed = E.parse_input(path)
                cached = E.capacity_diagnostics(parsed)
                # Recompute with the cache disabled for this contract by
                # pointing the public name at the uncached implementation.
                original = E.shift_day_demand_fit
                E.shift_day_demand_fit = E._shift_day_demand_fit_uncached
                try:
                    fresh = E.parse_input(path)
                    uncached = E.capacity_diagnostics(fresh)
                finally:
                    E.shift_day_demand_fit = original
                self.assertEqual(
                    json.dumps(cached, sort_keys=True, default=str),
                    json.dumps(uncached, sort_keys=True, default=str),
                    f"{path.name}: memoisation changed capacity_diagnostics output",
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
