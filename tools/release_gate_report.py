#!/usr/bin/env python3
"""Evaluate RC9.2.1 release gates from executed run artifacts.

Most of the release gates are **self-contained**: they compare a run against
itself or against its own independent validation, not against RC9.1.  Those can
be decided from the artifacts a run already produces.

  Gate 1  environment / smoke        - self-contained
  Gate 4  GDI REAL28 24/7            - self-contained (engine's own benchmark)
  Gate 5  break-stage regression     - self-contained (before vs after, same run)
  Gate 6  11H/3OFF + separate OFF    - self-contained
  Gate 7  resume / timeout           - self-contained
  Gate 8  independent validation     - self-contained (export vs validator)

Only two gates require a comparator this project does not currently hold:

  Gate 2  NMG EN vs RC9.1 baseline   - REQUIRES RC9.1
  Gate 9  regression quality vs RC9.1- REQUIRES RC9.1

Those are reported as REQUIRES_RC9_1_BASELINE rather than PASS or FAIL, because
neither verdict is honest without the comparator.  The rows are otherwise fully
populated, so the moment RC9.1 numbers arrive the comparison is a diff, not a
re-run.

Usage:
    python tools/release_gate_report.py RESULTS_ROOT [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

# Gate 5 thresholds. Break placement always costs a little coverage; the gate is
# about material, unexplained loss. Expressed as a share of active intervals so
# it scales across scenarios of different width.
BREAK_TARGET_LOSS_WARN_RATIO = 0.05
BREAK_FLOOR_LOSS_WARN_RATIO = 0.03


def read_summary(case: Path) -> dict:
    for pattern in ("*.l6_3_2_3_summary.csv", "*_SKELETON_ONLY_SUMMARY.csv"):
        for path in sorted(case.glob(pattern)):
            with path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            if rows:
                return rows[0]
    return {}


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def num(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def evaluate(case: Path) -> dict:
    summary = read_summary(case)
    identity = read_json(case / "UNIVERSAL_RUN_IDENTITY.json")
    validation = read_json(case / "INDEPENDENT_VALIDATION.json")

    before_target = num(summary.get("before_target"))
    after_target = num(summary.get("after_target"))
    before_floor = num(summary.get("before_floor"))
    after_floor = num(summary.get("after_floor"))
    active = num(summary.get("active_intervals")) or num(
        (validation.get("metrics") or {}).get("active_intervals"))

    target_loss = num(summary.get("target_losses_from_breaks"))
    floor_loss = num(summary.get("floor_losses_from_breaks"))
    skeleton_only = "SKELETON" in str(summary.get("status", "")).upper()

    # Gate 5 - break-stage regression, measured within this run.
    if skeleton_only:
        gate5, gate5_why = "NOT_APPLICABLE", "skeleton-only run; break stage not executed"
    elif not summary:
        gate5, gate5_why = "NO_EVIDENCE", "no summary produced"
    elif not active:
        # No active intervals means the run never got far enough to place a
        # break. Zero loss out of zero is not a pass.
        gate5, gate5_why = "NO_EVIDENCE", "run produced no active intervals; break stage never reached"
    else:
        exceptions = num(summary.get("no_break_exceptions"))
        proven = str(summary.get("minimum_exception_proven", "")).lower() == "true"
        lang_loss = num(summary.get("language_break_caused_reserve_loss_quarters"))
        target_ratio = target_loss / active if active else 0.0
        floor_ratio = floor_loss / active if active else 0.0
        problems = []
        if target_ratio > BREAK_TARGET_LOSS_WARN_RATIO:
            problems.append(f"target loss {target_loss:.0f}/{active:.0f} = {target_ratio:.1%}")
        if floor_ratio > BREAK_FLOOR_LOSS_WARN_RATIO:
            problems.append(f"floor loss {floor_loss:.0f}/{active:.0f} = {floor_ratio:.1%}")
        if lang_loss > 0:
            problems.append(f"{lang_loss:.0f} language reserve quarters lost to breaks")
        if exceptions > 0 and not proven:
            problems.append(f"{exceptions:.0f} break exceptions, minimum not proven")
        gate5 = "FAIL" if problems else "PASS"
        gate5_why = "; ".join(problems) or (
            f"target -{target_loss:.0f}, floor -{floor_loss:.0f} of {active:.0f} active; "
            f"{exceptions:.0f} exceptions"
            + (" (minimum proven)" if proven else ""))

    # Gate 8 - independent validation of the exported workbook.
    status = validation.get("status")
    if not validation:
        gate8, gate8_why = "NO_EVIDENCE", "independent validation not run"
    elif status == "PASS":
        gate8 = "PASS"
        gate8_why = f"0 hard failures on {validation.get('artifact_role')}"
    else:
        gate8 = "FAIL"
        gate8_why = f"{validation.get('hard_fail_count')} hard failures on {validation.get('artifact_role')}"

    # Gate 4 - the engine's own release benchmark, not an RC9.1 comparison.
    bench = summary.get("quality_benchmark_status") or ""
    protected = summary.get("protected_benchmark_status") or ""
    if not summary:
        gate4, gate4_why = "NO_EVIDENCE", "no summary produced"
    elif skeleton_only or not bench:
        # A skeleton-only run never reaches the release benchmark, so it has
        # nothing to report. Calling that FAIL would be the same false verdict
        # this report exists to avoid.
        gate4, gate4_why = "NOT_APPLICABLE", (
            "skeleton-only run; release benchmark not evaluated" if skeleton_only
            else "benchmark not reported by this run")
    else:
        gate4 = "PASS" if bench == "PASS" and protected in ("PASS", "") else "FAIL"
        gate4_why = f"quality_benchmark={bench or 'n/a'}, protected_benchmark={protected or 'n/a'}"

    return {
        "case": case.name,
        "engine_sha256": (identity.get("engine_sha256") or "")[:16],
        "input_sha256": (identity.get("input_sha256") or "")[:16],
        "status": summary.get("status", ""),
        "functional_status": summary.get("functional_status", ""),
        "active_intervals": f"{active:.0f}" if active else "",
        "before_target": f"{before_target:.0f}", "after_target": f"{after_target:.0f}",
        "before_floor": f"{before_floor:.0f}", "after_floor": f"{after_floor:.0f}",
        "target_losses_from_breaks": f"{target_loss:.0f}",
        "floor_losses_from_breaks": f"{floor_loss:.0f}",
        "avoidable_overage_fte_sum": summary.get("avoidable_overage_fte_sum", ""),
        "gate4_target_benchmark": gate4, "gate4_detail": gate4_why,
        "gate5_break_regression": gate5, "gate5_detail": gate5_why,
        "gate8_independent_validation": gate8, "gate8_detail": gate8_why,
        "gate2_vs_rc9_1": "REQUIRES_RC9_1_BASELINE",
        "gate9_vs_rc9_1": "REQUIRES_RC9_1_BASELINE",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results_root", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("evidence"))
    args = ap.parse_args()

    cases = sorted(p for p in args.results_root.iterdir()
                   if p.is_dir() and (read_summary(p) or (p / "UNIVERSAL_RUN_IDENTITY.json").exists()))
    if not cases:
        raise SystemExit(f"No run artifacts under {args.results_root}")

    rows = [evaluate(c) for c in cases]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "RC9_2_1_RELEASE_GATE_REPORT.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    width = max(len(r["case"]) for r in rows)
    print(f"{'case':{width}} {'status':26} {'G4':6} {'G5':15} {'G8':12}")
    print("-" * (width + 64))
    for r in rows:
        print(f"{r['case']:{width}} {r['status'][:26]:26} "
              f"{r['gate4_target_benchmark'][:6]:6} {r['gate5_break_regression'][:15]:15} "
              f"{r['gate8_independent_validation'][:12]:12}")
    print()
    for r in rows:
        print(f"{r['case']}:")
        print(f"    gate 4 {r['gate4_target_benchmark']:22} {r['gate4_detail']}")
        print(f"    gate 5 {r['gate5_break_regression']:22} {r['gate5_detail']}")
        print(f"    gate 8 {r['gate8_independent_validation']:22} {r['gate8_detail']}")
    print()
    print(f"written: {csv_path}")
    print("gates 2 and 9 require RC9.1 per-scenario KPIs or the RC9.1 engine "
          "source (sha da21c3ba…); every other column is populated so the "
          "comparison becomes a diff when they arrive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
