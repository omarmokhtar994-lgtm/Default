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

# Engine statuses that mean the run stopped after stage 1 and never placed a
# break. Anything else reached the break stage and must be gated on it.
SKELETON_ONLY_STATUSES = {"SKELETON_ONLY_COMPLETE"}

# Consolidated RC9.1 comparator for gates 2 and 9. Absent by default: without it
# both gates report REQUIRES_RC9_1_BASELINE rather than guessing.
RC9_1_BASELINE_PATH = Path(__file__).resolve().parent.parent / "evidence" / "RC9_1_BASELINE.json"

# Gate 2/9 tolerance. "Not materially worse than RC9.1" needs a number; a single
# interval of noise is not a regression, a systematic loss is.
COMPARATOR_TARGET_TOLERANCE = 2
COMPARATOR_FLOOR_TOLERANCE = 2


def load_rc9_1_baseline() -> dict:
    if not RC9_1_BASELINE_PATH.exists():
        return {}
    return read_json(RC9_1_BASELINE_PATH)


def compare_to_rc9_1(summary: dict, identity: dict, baseline: dict) -> tuple:
    """Decide gates 2 and 9 for one case, or explain why they cannot be decided.

    The critical rule is the input-identity check. RC9.2.1 was run on a REPAIRED
    NMG EN fixture (two associates added to cover early Sunday), while the RC9.1
    baseline came from the unrepaired historical workbook. Comparing 227 against
    214 across those two rosters would read as a large RC9.2.1 win and would be
    meaningless - more headcount trivially buys coverage. A comparator that will
    happily compare different inputs is worse than no comparator, so this
    refuses unless the input hash matches the one the baseline names.
    """
    if not baseline:
        return "REQUIRES_RC9_1_BASELINE", "no RC9.1 comparator present"

    run_sha = str(identity.get("input_sha256") or "")
    scenarios = baseline.get("scenarios") or {}
    match = None
    for name, row in scenarios.items():
        prefix = row.get("input_sha256_prefix")
        if prefix and run_sha.startswith(prefix):
            match = (name, row)
            break
    if match is None:
        return ("NOT_COMPARABLE_INPUT_NOT_IN_BASELINE",
                f"run input {run_sha[:16] or 'unknown'} matches no RC9.1 baseline scenario; "
                "refusing to compare across different inputs")

    name, row = match
    if not row.get("comparable"):
        return "NOT_COMPARABLE_INPUT_NOT_IN_BASELINE", str(row.get("not_comparable_reason") or name)

    base_active = num(row.get("active_intervals"))
    run_active = num(summary.get("active_intervals")) or base_active
    if base_active and run_active and abs(base_active - run_active) > 1e-9:
        return ("NOT_COMPARABLE_DIFFERENT_CONTRACT",
                f"{name}: RC9.1 had {base_active:.0f} active intervals, this run has "
                f"{run_active:.0f}")

    base_t, base_f = num(row.get("before_target")), num(row.get("before_floor"))
    run_t, run_f = num(summary.get("before_target")), num(summary.get("before_floor"))
    if not run_t:
        return "NO_EVIDENCE", f"{name}: run reported no before_target"

    dt, df = run_t - base_t, run_f - base_f
    problems = []
    if dt < -COMPARATOR_TARGET_TOLERANCE:
        problems.append(f"before_target {run_t:.0f} vs RC9.1 {base_t:.0f} ({dt:+.0f})")
    if base_f and df < -COMPARATOR_FLOOR_TOLERANCE:
        problems.append(f"before_floor {run_f:.0f} vs RC9.1 {base_f:.0f} ({df:+.0f})")
    detail = (f"{name} [{baseline.get('evidence_class', 'UNKNOWN')}]: "
              f"target {run_t:.0f} vs {base_t:.0f} ({dt:+.0f}), "
              f"floor {run_f:.0f} vs {base_f:.0f} ({df:+.0f})")
    if problems:
        return "FAIL", detail + "; worse: " + "; ".join(problems)
    # Never a bare PASS: the comparator is consolidated metrics, not raw RC9.1
    # artifacts, and this is a before-break comparison only.
    return "PASS_AGAINST_CONSOLIDATED_BASELINE", detail


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


def evaluate(case: Path, baseline: dict | None = None) -> dict:
    summary = read_summary(case)
    identity = read_json(case / "UNIVERSAL_RUN_IDENTITY.json")
    validation = read_json(case / "INDEPENDENT_VALIDATION.json")
    if baseline is None:
        baseline = load_rc9_1_baseline()

    before_target = num(summary.get("before_target"))
    after_target = num(summary.get("after_target"))
    before_floor = num(summary.get("before_floor"))
    after_floor = num(summary.get("after_floor"))
    active = num(summary.get("active_intervals")) or num(
        (validation.get("metrics") or {}).get("active_intervals"))

    target_loss = num(summary.get("target_losses_from_breaks"))
    floor_loss = num(summary.get("floor_losses_from_breaks"))
    # Match the engine's skeleton-only statuses exactly. A substring test for
    # "SKELETON" also matches statuses such as
    # SKELETONS_AND_BREAK_DIAGNOSTICS_READY and
    # SKELETON_EXCEPTION_LOWER_BOUND_EXCEEDS_CAP, which are NOT skeleton-only
    # runs - excusing gates 4 and 5 as NOT_APPLICABLE on a run that did reach
    # the break stage.
    skeleton_only = str(summary.get("status", "")).strip().upper() in SKELETON_ONLY_STATUSES

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

    # Skeleton retention: the best before-break skeleton found versus the one
    # actually carried into the winning after-break pair. A large gap means the
    # strongest skeleton had no production break solution.
    best_before = num(summary.get("global_best_before_target") or summary.get("best_before_target"))
    final_before = num(summary.get("before_target"))
    retention_loss = max(0.0, best_before - final_before) if best_before else 0.0

    # Gate 4 - the engine's own quality/retention benchmark, NOT an RC9.1
    # comparison and NOT a supplied benchmark workbook (which is typically
    # NOT_PROVIDED). It warns when skeleton retention exceeds the configured
    # max_final_before_target_loss.
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
        # An unevaluated protected benchmark is NOT a passed one. The engine used
        # to publish protected_benchmark_status="PASS" unconditionally, including
        # on runs where neither protected minimum was configured, so this gate
        # read a pass out of a benchmark that never ran. It now reports
        # NOT_CONFIGURED, and older artifacts leave the field blank; both are
        # surfaced as PASS_PROTECTED_NOT_EVALUATED rather than folded into PASS.
        protected_evaluated = protected == "PASS"
        protected_unknown = protected in ("", "NOT_CONFIGURED")
        if bench != "PASS":
            gate4 = "FAIL"
        elif not protected_evaluated and not protected_unknown:
            gate4 = "FAIL"
        elif protected_unknown:
            gate4 = "PASS_PROTECTED_NOT_EVALUATED"
        else:
            gate4 = "PASS"
        gate4_why = (f"quality_benchmark={bench or 'n/a'}, "
                     f"protected_benchmark={protected or 'not reported'}"
                     + ("; no protected minimum was configured, so the protected "
                        "tier was never checked" if protected_unknown else "")
                     + (f", skeleton retention -{retention_loss:.0f} ({best_before:.0f} -> {final_before:.0f})"
                        if retention_loss else ""))

    # Gates 2 and 9 both mean "not materially worse than RC9.1" and are decided
    # from the same comparison; 9 is the whole-set view of what 2 says per case.
    gate2, gate2_why = compare_to_rc9_1(summary, identity, baseline)

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
        "best_before_target": f"{best_before:.0f}" if best_before else "",
        "skeleton_retention_loss": f"{retention_loss:.0f}" if best_before else "",
        "max_concurrent_breaks_observed": summary.get("max_concurrent_breaks_observed", ""),
        "break_concurrency_violations": summary.get("break_concurrency_violations", ""),
        "break_objective_mode": summary.get("break_objective_mode", ""),
        "gate4_quality_retention": gate4, "gate4_detail": gate4_why,
        "gate5_break_regression": gate5, "gate5_detail": gate5_why,
        "gate8_independent_validation": gate8, "gate8_detail": gate8_why,
        "gate2_vs_rc9_1": gate2, "gate2_detail": gate2_why,
        "gate9_vs_rc9_1": gate2, "gate9_detail": gate2_why,
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
              f"{r['gate4_quality_retention'][:6]:6} {r['gate5_break_regression'][:15]:15} "
              f"{r['gate8_independent_validation'][:12]:12}")
    print()
    for r in rows:
        print(f"{r['case']}:")
        print(f"    gate 4 {r['gate4_quality_retention']:22} {r['gate4_detail']}")
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
