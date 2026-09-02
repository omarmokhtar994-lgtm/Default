#!/usr/bin/env python3
"""Fresh Phase B micro/focused promotion gate.

This gate combines fast diagnostic checks, two feasible synthetic CP-SAT cases,
and one short end-to-end production solve. It validates Phase B capabilities
without pretending to replace champion Quick/Deep runs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ENGINE_PATH = ROOT / "_tools" / "l632_universal_scheduler.py"
WRAPPER = ROOT / "RUN_UNIVERSAL_WFM.py"
FAST70 = ROOT / "regression_lab" / "run_fast70_migrated.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("phase_b_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load scheduler engine")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def compact_capacity(payload: dict[str, Any]) -> dict[str, Any]:
    break_resilience = payload.get("break_resilience", {}) or {}
    return {
        "status": payload.get("status"),
        "hard_failure_count": len(payload.get("hard_failures", []) or []),
        "warning_count": len(payload.get("warnings", []) or []),
        "break_resilience_status": break_resilience.get("status"),
        "break_resilience_hard_failure_count": len(break_resilience.get("hard_failures", []) or []),
        "break_resilience_warning_codes": sorted({str(row.get("code")) for row in break_resilience.get("warnings", []) or []}),
        "daily_skill_windows": break_resilience.get("daily_skill_windows", []),
        "weekly_skill_redundancy": break_resilience.get("weekly_skill_redundancy", []),
    }


def run_logged(command: list[str], cwd: Path, log_path: Path, timeout: int) -> tuple[int, float]:
    started = time.time()
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env={**os.environ, "TERM": "dumb", "PYTHONUNBUFFERED": "1"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
        )
        assert process.stdout is not None
        try:
            for line in process.stdout:
                print(line, end="")
                log.write(line)
                if time.time() - started > timeout:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                    return 124, time.time() - started
            return process.wait(), time.time() - started
        finally:
            if process.poll() is None:
                process.kill()


def phase_b_assertions(audit: dict[str, Any], case_root: Path) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, value: Any) -> None:
        checks.append({"name": name, "passed": bool(passed), "value": value})

    add("phase_b_release_identity", "R1.2.0-B" in str(audit.get("version", "")), audit.get("version"))
    budget = audit.get("global_budget", {}) or {}
    add("single_global_budget_present", int(budget.get("total_seconds", 0) or 0) > 0, budget)
    add("early_safe_incumbent_executed", (audit.get("early_safe_incumbent", {}) or {}).get("status") not in {None, "PENDING"}, audit.get("early_safe_incumbent"))
    add("adaptive_search_executed", (audit.get("adaptive_search_v1", {}) or {}).get("status") not in {None, "PENDING"}, audit.get("adaptive_search_v1"))
    joint = audit.get("joint_cp_sat_refinement", {}) or {}
    add("joint_cp_sat_accounted", joint.get("status") not in {None, "PENDING"} or joint.get("enabled") is False, joint)
    if joint.get("enabled") is not False:
        add("joint_cp_sat_model_contract", joint.get("model_contract") == "SHIFT_X_OFF_X_LANGUAGE_X_EXACT_BREAK_PATTERN_IN_ONE_CP_SAT_MODEL", joint.get("model_contract"))
        joint_execution = joint.get("execution", {}) or {}
        add("joint_cp_sat_fresh_attempt", int(joint_execution.get("attempted", 0) or 0) > 0, joint_execution)
    coordinated = audit.get("coordinated_shift_break_loop", {}) or {}
    add("coordinated_repair_accounted", coordinated.get("status") not in {None, "PENDING"} or coordinated.get("enabled") is False, coordinated)
    post_execution = audit.get("post_break_repair_execution", {}) or {}
    post_accounted = int(post_execution.get("attempted", 0) or 0) > 0 or bool(post_execution.get("skip_reason")) or post_execution.get("enabled") is False
    add("post_break_repair_accounted", post_accounted, post_execution)
    late_gate = audit.get("late_phase_execution_gate", {}) or {}
    add("late_phase_gate_nonfatal", str(late_gate.get("status", "")).startswith("PASS"), late_gate)
    add("hard_release_status", audit.get("status") in {"PASS", "PASS_WITH_COVERAGE_TRADEOFF", "FALLBACK_TO_QUICK"}, audit.get("status"))
    final_metrics = audit.get("final_metrics", {}) or {}
    add("zero_staff_guard", int(final_metrics.get("zero_staffed_active_quarters", 0) or 0) == 0, final_metrics.get("zero_staffed_active_quarters"))
    add("language_guard", int(final_metrics.get("language_gap_count", 0) or 0) == 0, final_metrics.get("language_gap_count"))
    add("opening_guard", int(final_metrics.get("opening_gap_count", 0) or 0) == 0, final_metrics.get("opening_gap_count"))
    add("hard_floor_guard", int(final_metrics.get("hard_floor_gap_count", 0) or 0) == 0, final_metrics.get("hard_floor_gap_count"))
    add("no_break_exceptions", int(final_metrics.get("no_break_exception_count", 0) or 0) == 0, final_metrics.get("no_break_exception_count"))
    packages = case_root / "packages"
    package_manifest = packages / "PACKAGE_SPLIT_MANIFEST.json"
    add("phase_b_package_manifest", package_manifest.exists(), str(package_manifest))
    if package_manifest.exists():
        manifest = json.loads(package_manifest.read_text(encoding="utf-8"))
        add("three_package_split", set(manifest.get("packages", {})) == {"01_PRODUCTION_ONLY", "02_REVIEW_EVIDENCE", "03_FULL_DEBUG"}, manifest.get("packages", {}).keys())
        add("package_zip_tests", all(row.get("zip_test") == "PASS" for row in manifest.get("packages", {}).values()), manifest.get("packages"))
    return checks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--production-time-limit", type=int, default=900)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    root = args.output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "release": "L6.3.2.3-R1.2.0-B-ENGINE-MATURITY-RC4.3-QUALITY-LOCKED-JOINT-CP-SAT",
        "evidence_class": "FRESH_PHASE_B_MICRO_AND_FOCUSED_CP_SAT",
        "steps": [],
    }

    engine = load_engine()
    diagnostic_cases = [
        ("DIRECTIONAL_SKILL_CONSTRAINT_DIAGNOSTIC", ROOT / "inputs" / "GDI_REAL_28HC_12JUL_INSTRUCTION_DRIVEN_Input.xlsx"),
        ("ELEVEN_HOUR_SKILL_REDUNDANCY_DIAGNOSTIC", ROOT / "inputs" / "UNIVERSAL_30MIN_11H_SYNTHETIC_REGRESSION.xlsx"),
    ]
    for name, workbook in diagnostic_cases:
        started = time.time()
        parsed = engine.parse_input(workbook)
        capacity = engine.capacity_diagnostics(parsed)
        compact = compact_capacity(capacity)
        has_skill_evidence = bool(compact["daily_skill_windows"] or compact["weekly_skill_redundancy"])
        step = {
            "name": name,
            "status": "PASS" if has_skill_evidence else "FAIL",
            "elapsed_sec": round(time.time() - started, 3),
            "workbook": str(workbook),
            "capacity_diagnostics": compact,
        }
        report["steps"].append(step)
        print(json.dumps(step, indent=2, default=str))
        if step["status"] != "PASS":
            report["status"] = "FAIL"
            break

    if report.get("status") != "FAIL":
        fast70_root = root / "FAST70_T42_T44"
        command = [
            sys.executable, "-u", str(FAST70),
            "--run-solvers", "--only-ids", "T42,T44",
            "--time-limit-per-scenario", "45",
            "--pattern-widths", "60,180,680",
            "--workers", str(args.workers),
            "--release-path-repair",
            "--output-dir", str(fast70_root),
        ]
        rc, elapsed = run_logged(command, ROOT, logs / "02_FAST70_T42_T44.log", timeout=1500)
        fast_report_path = fast70_root / "FAST70_MIGRATED_REPORT.json"
        fast_report = json.loads(fast_report_path.read_text(encoding="utf-8")) if fast_report_path.exists() else {}
        passed = rc == 0 and fast_report.get("selected") == 2 and fast_report.get("failed") == 0
        report["steps"].append({
            "name": "FEASIBLE_11H_AND_DIRECTIONAL_SKILL_CP_SAT",
            "status": "PASS" if passed else "FAIL",
            "return_code": rc,
            "elapsed_sec": round(elapsed, 3),
            "report": fast_report,
        })
        if not passed:
            report["status"] = "FAIL"

    if report.get("status") != "FAIL":
        production_root = root / "PRODUCTION_FOCUSED"
        case_id = "PHASE_B_SAFE_INCUMBENT_GLOBAL_BUDGET"
        command = [
            sys.executable, "-u", str(WRAPPER),
            "--input", str(ROOT / "inputs" / "NMG12_R1_1_2_RC2_BREAK_REGRESSION_100_TARGET.xlsx"),
            "--output-root", str(production_root),
            "--case-id", case_id,
            "--time-limit", str(args.production_time_limit),
            "--num-workers", str(args.workers),
            "--pattern-widths", "180,680",
            "--repair-change-limits", "2,4",
            "--break-objective-modes", "target_priority,coverage_rebalance,balanced,floor_protected,target_100",
            "--adaptive-no-improvement-attempts", "8",
            "--coordinated-repair-cycles", "1",
            "--joint-refinement-reserve-sec", "300",
            "--joint-change-limits", "2,4",
            "--joint-shift-options-per-cell", "3",
            "--joint-patterns-per-shift", "8",
            "--disable-no-break-exceptions",
            "--overwrite",
        ]
        rc, elapsed = run_logged(command, ROOT, logs / "03_PHASE_B_PRODUCTION_FOCUSED.log", timeout=max(1800, args.production_time_limit + 600))
        case_root = production_root / case_id
        audit_path = case_root / f"{case_id}.l6_3_2_3_solver_audit.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
        checks = phase_b_assertions(audit, case_root)
        passed = rc == 0 and checks and all(check["passed"] for check in checks)
        report["steps"].append({
            "name": "PHASE_B_END_TO_END_GLOBAL_BUDGET_AND_SAFE_INCUMBENT",
            "status": "PASS" if passed else "FAIL",
            "return_code": rc,
            "elapsed_sec": round(elapsed, 3),
            "audit_path": str(audit_path),
            "operational_status": audit.get("status"),
            "checks": checks,
        })
        if not passed:
            report["status"] = "FAIL"

    report["status"] = report.get("status", "PASS")
    report["passed_step_count"] = sum(step.get("status") == "PASS" for step in report["steps"])
    report["step_count"] = len(report["steps"])
    report_path = root / "PHASE_B_MICRO_FOCUSED_REPORT.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
