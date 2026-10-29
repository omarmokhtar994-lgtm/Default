"""Phase F, task 1: every run states plainly whether its schedule is releasable.

External audit (evidence/external_reviews/CHATGPT_FINAL_AUDIT_2026_10_07_EVALUATION.md):
tools/release_gate_report.py printed gates 4, 5 and 8 but never combined them
into a verdict and always exited 0, so run F-37 (gate 5 FAIL) ended exit 0.

Policy (owner deferred the mandatory-gate list; safe default, never hides or
blocks a schedule):
  * NOT_RELEASABLE when independent validation (gate 8) failed or never ran;
  * REVIEW_REQUIRED when gate 4 or gate 5 FAILed;
  * checks that were not evaluated are listed, never read as a pass, and do
    not change the verdict on their own;
  * RELEASABLE otherwise. The run verdict is the worst case verdict; the
    report exits 3 only for NOT_RELEASABLE, so REVIEW_REQUIRED runs keep
    their artifacts and finish normally.
"""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load():
    spec = importlib.util.spec_from_file_location("release_gate_report_f1", REPO / "tools" / "release_gate_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = load()


def row(g4="PASS", g5="PASS", g8="PASS", g5_detail="target -2, floor -1 of 168 active"):
    return {"case": "CASE", "gate4_quality_retention": g4, "gate4_detail": "",
            "gate5_break_regression": g5, "gate5_detail": g5_detail,
            "gate8_independent_validation": g8, "gate8_detail": ""}


class TheVerdictPolicy(unittest.TestCase):
    def test_all_gates_pass_is_releasable(self):
        v = GATE.release_verdict(row())
        self.assertEqual(v["verdict"], "RELEASABLE")
        self.assertEqual(v["failed"], [])

    def test_gate5_fail_is_review_required_and_named(self):
        v = GATE.release_verdict(row(g5="FAIL"))
        self.assertEqual(v["verdict"], "REVIEW_REQUIRED")
        self.assertTrue(any("gate 5" in f for f in v["failed"]), v)

    def test_gate4_fail_is_review_required(self):
        self.assertEqual(GATE.release_verdict(row(g4="FAIL"))["verdict"], "REVIEW_REQUIRED")

    def test_unconfigured_protected_tier_alone_stays_releasable_but_is_listed_not_evaluated(self):
        v = GATE.release_verdict(row(g4="PASS_PROTECTED_NOT_EVALUATED"))
        self.assertEqual(v["verdict"], "RELEASABLE")
        self.assertTrue(any("gate 4" in n for n in v["not_evaluated"]), v)

    def test_delta_only_break_gate_is_listed_not_evaluated(self):
        v = GATE.release_verdict(row(g5="PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD"))
        self.assertEqual(v["verdict"], "RELEASABLE")
        self.assertTrue(any("gate 5" in n for n in v["not_evaluated"]), v)

    def test_validator_fail_is_not_releasable(self):
        self.assertEqual(GATE.release_verdict(row(g8="FAIL"))["verdict"], "NOT_RELEASABLE")

    def test_validator_never_run_is_not_releasable(self):
        v = GATE.release_verdict(row(g8="NO_EVIDENCE"))
        self.assertEqual(v["verdict"], "NOT_RELEASABLE")

    def test_a_validator_failure_outranks_a_quality_failure(self):
        self.assertEqual(GATE.release_verdict(row(g5="FAIL", g8="FAIL"))["verdict"], "NOT_RELEASABLE")


def make_case(root: Path, name: str, validation_status, **fields):
    case = root / name
    case.mkdir(parents=True)
    r = {"status": "PASS", "active_intervals": 168, "target_ratio": 1.0, "before_target": 166,
         "after_target": 164, "before_floor": 168, "after_floor": 167,
         "target_losses_from_breaks": 2, "floor_losses_from_breaks": 1,
         "quality_benchmark_status": "PASS", "protected_benchmark_status": "PASS"}
    r.update(fields)
    with (case / "case.l6_3_2_3_summary.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(r))
        w.writeheader()
        w.writerow(r)
    if validation_status is not None:
        (case / "INDEPENDENT_VALIDATION.json").write_text(
            json.dumps({"status": validation_status, "hard_fail_count": 0 if validation_status == "PASS" else 2,
                        "artifact_role": "FINAL_AFTER_BREAKS"}), encoding="utf-8")
    return case


class TheReportWritesTheVerdictAndExitCode(unittest.TestCase):
    def _run(self, *cases):
        tmp = Path(tempfile.mkdtemp())
        results, out = tmp / "results", tmp / "out"
        for name, status in cases:
            make_case(results, name, status)
        import sys
        argv = sys.argv
        sys.argv = ["release_gate_report.py", str(results), "--out-dir", str(out)]
        try:
            rc = GATE.main()
        finally:
            sys.argv = argv
        return rc, json.loads((out / "RELEASE_VERDICT.json").read_text())

    def test_main_writes_the_verdict_file_and_exits_0_when_releasable(self):
        rc, verdict = self._run(("A", "PASS"))
        self.assertEqual(rc, 0)
        self.assertEqual(verdict["verdict"], "RELEASABLE")
        self.assertEqual(verdict["cases"]["A"]["verdict"], "RELEASABLE")

    def test_main_exits_3_only_for_not_releasable_and_reports_the_worst_case(self):
        rc, verdict = self._run(("A", "PASS"), ("B", "FAIL"))
        self.assertEqual(rc, 3)
        self.assertEqual(verdict["verdict"], "NOT_RELEASABLE")
        self.assertEqual(verdict["cases"]["A"]["verdict"], "RELEASABLE")
        self.assertEqual(verdict["cases"]["B"]["verdict"], "NOT_RELEASABLE")


if __name__ == "__main__":
    unittest.main()
