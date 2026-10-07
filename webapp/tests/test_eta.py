# © 2026 Omar Mokhtar. All rights reserved.
"""Phase J task 4: queue position and start estimates.

Owner, 2026-10-07: "show how many hours pending until we start running that
file, how many schedules are queued now, when is your turn". Estimates come
from this server's own finished runs when there are enough, otherwise from the
runner's plan (seeds per mode, side by side on the machine's cores)."""
import unittest

from webapp.eta import expected_minutes, queue_plan

NOW = 1_800_000_000.0


def run(run_id, status, mode="QUICK", created=0.0, started=None, finished=None):
    return {"id": run_id, "status": status, "mode": mode, "created": created, "started": started,
            "finished": finished}


class ExpectedLength(unittest.TestCase):
    def test_quick_on_four_cores_is_one_round(self):
        self.assertEqual(expected_minutes("QUICK", 4, []), 70)   # 2 searches side by side, 60 min + 10
        self.assertEqual(expected_minutes("DEEP", 4, []), 130)   # 4 searches, 2 rounds
        self.assertEqual(expected_minutes("QUICK", 2, []), 130)  # 2 cores: one search at a time
        self.assertEqual(expected_minutes("SMOKE", 4, []), 25)

    def test_history_overrides_the_plan(self):
        self.assertEqual(expected_minutes("QUICK", 4, [50, 60, 80]), 60)
        self.assertEqual(expected_minutes("QUICK", 4, [55]), 70)  # one run is not enough to trust


class TheQueue(unittest.TestCase):
    def test_second_in_line_waits_for_the_running_one(self):
        runs = [run("r", "RUNNING", created=1, started=NOW - 20 * 60),
                run("a", "QUEUED", created=2), run("b", "QUEUED", created=3)]
        plan = queue_plan(runs, NOW, cpus=4, gate_pending=False)
        self.assertEqual(plan["r"]["position"], 0)
        self.assertEqual(plan["r"]["finishes_in_min"], 50)
        self.assertEqual((plan["a"]["position"], plan["a"]["ahead"], plan["a"]["starts_in_min"]), (1, 1, 50))
        self.assertEqual((plan["b"]["position"], plan["b"]["ahead"], plan["b"]["starts_in_min"]), (2, 2, 120))
        self.assertEqual(plan["b"]["starts_at"], NOW + 120 * 60)
        self.assertIn("plan", plan["b"]["basis"])

    def test_gate_time_is_added_once_when_not_yet_passed(self):
        runs = [run("a", "QUEUED", created=1), run("b", "QUEUED", created=2), run("c", "QUEUED", created=3)]
        plan = queue_plan(runs, NOW, cpus=4, gate_pending=True)
        self.assertEqual(plan["a"]["starts_in_min"], 0)
        self.assertEqual(plan["a"]["finishes_in_min"], 100)
        self.assertEqual(plan["b"]["starts_in_min"], 100)
        self.assertEqual(plan["c"]["starts_in_min"], 170)

    def test_overrunning_run_still_counts_a_few_minutes(self):
        runs = [run("r", "RUNNING", started=NOW - 200 * 60), run("a", "QUEUED", created=2)]
        plan = queue_plan(runs, NOW, cpus=4, gate_pending=False)
        self.assertEqual(plan["a"]["starts_in_min"], 5)

    def test_history_from_finished_runs_is_used_and_named(self):
        done = [run(f"d{i}", "DONE", started=NOW - 10_000 - i, finished=NOW - 10_000 - i + m * 60)
                for i, m in enumerate((40, 50, 60))]
        plan = queue_plan(done + [run("a", "QUEUED", created=5), run("b", "QUEUED", created=6)], NOW, 4, False)
        self.assertEqual(plan["b"]["starts_in_min"], 50)
        self.assertIn("last 3 quick runs", plan["b"]["basis"])


if __name__ == "__main__":
    unittest.main()
