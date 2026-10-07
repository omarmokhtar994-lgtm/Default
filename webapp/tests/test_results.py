# © 2026 Omar Mokhtar. All rights reserved.
"""Phase J tasks 1 and 5: a run's summary, read from the validator's own file.

The fixture is a trimmed copy of the real Phase I end-to-end run (NMG_SP,
QUICK): every number asserted here is in that file; nothing is invented."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.results import summarize

REAL = Path(__file__).with_name("fixtures") / "real_run"
CASE = "NMG_SP_RC9_1_READY_FIXED"


def copy_real():
    root = Path(tempfile.mkdtemp()) / "results"
    shutil.copytree(REAL, root)
    return root


def rewrite_validation(root, change):
    path = root / CASE / "INDEPENDENT_VALIDATION.json"
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


class TheSummary(unittest.TestCase):
    def test_summary_reads_the_real_validation_file(self):
        s = summarize(copy_real())
        self.assertEqual(s["case"], CASE)
        self.assertEqual(s["interval_minutes"], 30)
        self.assertEqual(s["days"], ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(len(s["slots"]), 48)
        self.assertEqual(s["numbers"], {"active": 126, "fully_covered": 107, "at_90": 121, "floor_gaps": 0,
                                        "zero_staffed": 0, "losses_from_breaks": 5})
        texts = [f["text"] for f in s["findings"]]
        self.assertTrue(any(t.startswith("Fri 21:30: 2 people on break at the same time") for t in texts), texts)
        self.assertTrue(any("Sat 01:30" in t and "cap 5" in t for t in texts), texts)
        self.assertEqual(s["hard_fail_count"], 0)
        filled = sum(cell is not None for row in s["cells"] for cell in row)
        self.assertEqual(filled, 126)

    def test_cell_classes_follow_the_validator(self):
        root = copy_real()

        def plant(data):
            rows = data["interval_rows"]
            rows[0].update(after_pct=1.4, severe_overage=True)
            rows[1].update(after_pct=0.95, severe_overage=False)
            rows[2].update(after_pct=0.85, severe_overage=False)
            rows[3].update(after_pct=1.0, severe_overage=False)
        rewrite_validation(root, plant)
        s = summarize(root)
        data = json.loads((root / CASE / "INDEPENDENT_VALIDATION.json").read_text())
        rows = data["interval_rows"]
        slot = {label: i for i, label in enumerate(s["slots"])}
        got = [s["cells"][r["day_index"]][slot[r["interval"]]]["cls"] for r in rows[:4]]
        self.assertEqual(got, ["over", "short", "gap", "covered"])
        first = s["cells"][rows[0]["day_index"]][slot[rows[0]["interval"]]]
        self.assertEqual(first["pct"], 140)
        # Before breaks: same thresholds on before_pct; over-staffing is only flagged after breaks.
        self.assertIn(first["before_cls"], ("covered", "short", "gap"))
        self.assertIn(f"{rows[0]['day']} {rows[0]['interval']}", first["title"])

    def test_wall_columns_follow_the_interval_length(self):
        root = copy_real()

        def quarter_hours(data):
            base = copy.deepcopy(data["interval_rows"][0])
            data["interval_rows"] = [dict(base, interval="00:00", interval_index=0),
                                     dict(base, interval="00:15", interval_index=1)]
        rewrite_validation(root, quarter_hours)
        s = summarize(root)
        self.assertEqual((s["interval_minutes"], len(s["slots"])), (15, 96))

    def test_no_validation_file_gives_no_wall(self):
        root = Path(tempfile.mkdtemp()) / "results"
        (root / "WEEK42").mkdir(parents=True)
        self.assertIsNone(summarize(root))
        self.assertIsNone(summarize(Path(tempfile.mkdtemp()) / "missing"))

    def test_unknown_warning_type_is_still_listed(self):
        root = copy_real()
        rewrite_validation(root, lambda d: d["warnings"].append({"type": "SOMETHING_NEW_HAPPENED", "count": 3}))
        texts = [f["text"] for f in summarize(root)["findings"]]
        self.assertTrue(any(t.startswith("Something new happened") and "3" in t for t in texts), texts)

    def test_hard_failures_come_first(self):
        root = copy_real()
        rewrite_validation(root, lambda d: d["failures"].append({"type": "ZERO_STAFF_ACTIVE", "count": 2}))
        first = summarize(root)["findings"][0]
        self.assertEqual(first["level"], "gap")


class TheStaffingSuggestions(unittest.TestCase):
    def test_staffing_from_the_real_run(self):
        st = summarize(copy_real())["staffing"]
        self.assertEqual(st["roster"], 7)
        self.assertEqual(st["productive_hours"], 280.0)
        self.assertEqual(round(st["target_hours"]), 207)
        self.assertEqual(round(st["slack_hours"], 1), 72.6)
        self.assertEqual(st["headroom_pct"], 35)
        self.assertEqual(st["class"], "CAPACITY_AMPLE")
        self.assertEqual((st["add_for_target"], st["add_for_floor"], st["add_for_breaks"]), (0, 0, 0))
        self.assertEqual(st["per_person_hours"], 40.0)
        self.assertEqual(st["release_estimate"], 1)  # floor(72.6 / 40)
        self.assertIn("estimate", st["headline"].lower())

    def test_understaffed_case_names_people_to_add(self):
        root = copy_real()
        audit = next((root / CASE).glob("*solver_audit.json"))
        data = json.loads(audit.read_text())
        cap = data["capacity_diagnostics"]
        cap["productive_minus_target_lower_bound"] = -50.0
        cap["estimated_additional_hc_for_aggregate_target"] = 2
        cap["coverage_benchmark"]["capacity_class"] = "CAPACITY_SHORT"
        audit.write_text(json.dumps(data))
        st = summarize(root)["staffing"]
        self.assertEqual(st["add_for_target"], 2)
        self.assertEqual(st["release_estimate"], 0)
        self.assertIn("2", st["headline"])
        self.assertIn("add", st["headline"].lower())

    def test_windows_group_consecutive_half_hours(self):
        root = copy_real()

        def two_runs(data):
            for r in data["interval_rows"]:
                r.update(after_pct=1.0, severe_overage=False)
            mon = [r for r in data["interval_rows"] if r["day"] == "Mon"]
            mon.sort(key=lambda r: r["interval_index"])
            for r in mon[:2]:
                r.update(after_pct=0.5, required=4.0, after_effective=2.0, after_raw_min=2)
        rewrite_validation(root, two_runs)
        st = summarize(root)["staffing"]
        self.assertEqual(len(st["short_windows"]), 1, st["short_windows"])
        w = st["short_windows"][0]
        self.assertEqual(w["day"], "Mon")
        self.assertEqual(w["half_hours"], 2)
        self.assertGreaterEqual(w["people_short"], 1)


if __name__ == "__main__":
    unittest.main()
