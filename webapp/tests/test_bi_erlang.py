# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI task 1 (owner, 2026-11-03: "use Erlang based on inputs we give to calculate the needed associates per interval"): Erlang C, service
level, agents needed, chat with concurrency, email by workload. The Erlang C numbers are checked against an independent direct-sum formula."""
import math
import time
import unittest

from webapp import erlang as E


def direct_erlang_c(n, a):
    """The textbook formula with factorials, for small n, as an independent check."""
    top = a ** n / math.factorial(n) * n / (n - a)
    return top / (sum(a ** k / math.factorial(k) for k in range(n)) + top)


class TheErlangC(unittest.TestCase):
    def test_it_matches_the_direct_formula(self):
        for a in (0.5, 1, 2.5, 5, 8, 10, 14.7, 20, 33.3, 45):
            for extra in (1, 2, 5, 12):
                n = int(math.floor(a)) + extra
                if n <= a:
                    continue
                self.assertAlmostEqual(E.erlang_c(n, a), direct_erlang_c(n, a), places=9, msg=(n, a))

    def test_nobody_is_served_when_agents_do_not_exceed_the_traffic(self):
        self.assertEqual(E.erlang_c(5, 5.0), 1.0)
        self.assertEqual(E.erlang_c(3, 9.0), 1.0)

    def test_no_traffic_never_waits(self):
        self.assertEqual(E.erlang_c(3, 0.0), 0.0)

    def test_a_very_large_centre_does_not_overflow_or_crawl(self):
        started = time.perf_counter()
        value = E.erlang_c(2000, 1900.0)
        self.assertLess(time.perf_counter() - started, 0.05)
        self.assertTrue(0.0 < value <= 1.0)


class TheTraffic(unittest.TestCase):
    def test_erlangs(self):
        self.assertEqual(E.erlangs(100, 180, 1800), 10.0)
        self.assertEqual(E.erlangs(0, 180, 1800), 0.0)


class TheServiceLevel(unittest.TestCase):
    def test_more_agents_never_lower_it(self):
        last = -1.0
        for n in range(11, 30):
            sl = E.service_level(n, 100, 180, 1800, 20)
            self.assertGreaterEqual(sl, last)
            last = sl

    def test_it_is_a_fraction_and_zero_when_unstable(self):
        self.assertEqual(E.service_level(10, 100, 180, 1800, 20), 0.0)
        self.assertTrue(0.0 < E.service_level(14, 100, 180, 1800, 20) <= 1.0)

    def test_no_calls_is_a_full_service_level(self):
        self.assertEqual(E.service_level(0, 0, 180, 1800, 20), 1.0)

    def test_average_wait(self):
        self.assertIsNone(E.average_wait(10, 100, 180, 1800))
        self.assertGreater(E.average_wait(11, 100, 180, 1800), E.average_wait(14, 100, 180, 1800))


class TheAgentsNeeded(unittest.TestCase):
    def test_no_calls_need_nobody(self):
        self.assertEqual(E.agents_needed(0, 180, 1800, 0.8, 20), 0)

    def test_it_is_the_smallest_number_that_meets_the_target(self):
        n = E.agents_needed(100, 180, 1800, 0.8, 20)
        self.assertGreater(n, 10)
        self.assertGreaterEqual(E.service_level(n, 100, 180, 1800, 20), 0.8)
        self.assertLess(E.service_level(n - 1, 100, 180, 1800, 20), 0.8)

    def test_a_stricter_target_needs_at_least_as_many(self):
        a = E.agents_needed(100, 180, 1800, 0.8, 20)
        b = E.agents_needed(100, 180, 1800, 0.95, 10)
        self.assertGreaterEqual(b, a)

    def test_the_occupancy_cap_is_kept(self):
        n = E.agents_needed(100, 180, 1800, 0.5, 120, max_occupancy=0.85)
        self.assertLessEqual(10.0 / n, 0.85 + 1e-12)

    def test_one_call_needs_one_agent(self):
        self.assertEqual(E.agents_needed(1, 180, 1800, 0.8, 20), 1)


class TheOtherChannels(unittest.TestCase):
    def test_chat_with_concurrency_needs_fewer_than_voice(self):
        voice = E.agents_needed(100, 180, 1800, 0.8, 30)
        chat = E.chat_agents_needed(100, 180, 1800, 0.8, 30, concurrency=2.0, max_occupancy=1.0)
        self.assertLess(chat, voice)
        self.assertGreaterEqual(chat, math.ceil(E.erlangs(100, 180, 1800) / 2.0))

    def test_chat_with_no_concurrency_is_voice(self):
        self.assertEqual(E.chat_agents_needed(100, 180, 1800, 0.8, 30, concurrency=1.0, max_occupancy=1.0),
                         E.agents_needed(100, 180, 1800, 0.8, 30))

    def test_email_is_the_workload(self):
        self.assertEqual(E.workload_agents(60, 600, 1800, 0.9), 60 * 600 / (1800 * 0.9))
        self.assertEqual(E.workload_agents(0, 600, 1800, 0.9), 0.0)


class TheShrinkage(unittest.TestCase):
    def test_fte(self):
        self.assertAlmostEqual(E.fte_required(10, 0.3), 10 / 0.7)
        self.assertEqual(E.fte_required(0, 0.3), 0.0)

    def test_bad_inputs_are_refused(self):
        for bad in (-0.1, 1.0, 1.5):
            with self.assertRaises(ValueError):
                E.fte_required(10, bad)
        with self.assertRaises(ValueError):
            E.erlangs(10, 0, 1800)
        with self.assertRaises(ValueError):
            E.erlangs(-1, 180, 1800)
        with self.assertRaises(ValueError):
            E.agents_needed(10, 180, 1800, 1.2, 20)
        with self.assertRaises(ValueError):
            E.agents_needed(10, 180, 1800, 0.8, 20, max_occupancy=0)


if __name__ == "__main__":
    unittest.main()
