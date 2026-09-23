#!/usr/bin/env python3
"""Generate a compact Phase C operational-quality report from one scheduler audit."""
from __future__ import annotations
import argparse, csv, json, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_tools"))
from canonical_metrics import canonicalize_metrics

ENGINE_PATH = Path(__file__).resolve().parent.parent / "_tools" / "l632_universal_scheduler.py"


def _engine_release(default: str = "UNKNOWN_ENGINE_RELEASE") -> str:
    """Fallback release name, read from the engine rather than a literal.

    This module used to hardcode the RC9.0 universal-production-platform
    release name, two releases behind the engine it reports on. It is a
    fallback only, used for an
    audit with no `version`, but a stale one still labels a report with the
    wrong release. Unlike the wrapper this is a reporting path, so an
    unreadable engine yields an explicit UNKNOWN rather than aborting the
    report.
    """
    try:
        text = ENGINE_PATH.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return default
    match = re.search(r'^VERSION\s*=\s*["\'](.+?)["\']', text, re.MULTILINE)
    return match.group(1) if match else default


RELEASE = _engine_release()


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _status(value: Any, default: str = "UNKNOWN") -> str:
    text = str(value or "").strip()
    return text or default


def _external_validation(case_root: Path | None) -> Dict[str, Any]:
    """Read the final independent-validation result when one exists.

    The engine audit may contain its own validation, but the release contract
    also requires the separately invoked checker to validate the exact polished
    workbook.  Once that file exists it is the authoritative safety result for
    this report.
    """
    if case_root is None:
        return {}
    path = case_root / "INDEPENDENT_VALIDATION.json"
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "ERROR", "hard_fail_count": 1}
    return value if isinstance(value, dict) else {"status": "ERROR", "hard_fail_count": 1}


def _stopped_at_the_skeleton_stage(audit: Dict[str, Any]) -> bool:
    """True only when the run deliberately ended after Stage 1."""
    return (str(audit.get("artifact_state") or "").upper() == "BEST_BEFORE_BREAKS_ONLY"
            or str(audit.get("status") or "").upper() == "SKELETON_ONLY_COMPLETE")


def _stage_and_metrics(audit: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
    """Read the metric surface the engine published, with the stage that made it.

    This report used to read ``selected_candidate.metrics`` and nothing else. A
    BEFORE_BREAKS_ONLY run has no selected candidate, so every coverage figure
    was published as 0 for a run that had in fact covered every active
    interval - a fabricated number, not a missing one. Both stages publish a
    surface now, so both are read here.
    """
    stage_surface = audit.get("stage_metric_surface") or {}
    stage = str(stage_surface.get("stage") or "")
    metrics = stage_surface.get("metrics") or {}
    if not metrics:
        candidate = (audit.get("selected_candidate") or {}).get("metrics") or {}
        if candidate:
            metrics, stage = candidate, stage or "FULL_SCHEDULE"
        elif _stopped_at_the_skeleton_stage(audit):
            # Only a run that actually STOPPED at Stage 1 may report the
            # skeleton surface as its own. A full run that reached Stage 2 and
            # failed also carries a before-break skeleton, and publishing that
            # as its result would present before-break coverage as an
            # after-break outcome - the same fabrication this report exists to
            # prevent. Such a run has no metric surface, and says so.
            metrics = (audit.get("selected_before_break_skeleton") or {}).get("metrics") or {}
            if metrics:
                stage = stage or "BEFORE_BREAKS_ONLY"
    if not stage:
        state = str(audit.get("artifact_state") or "").upper()
        stage = ("BEFORE_BREAKS_ONLY" if state == "BEST_BEFORE_BREAKS_ONLY"
                 else "FULL_SCHEDULE" if state.startswith("FINAL_")
                 else "UNKNOWN_STAGE")
    return stage, metrics


def build_report(audit: Dict[str, Any], case_root: Path | None = None) -> Dict[str, Any]:
    selected = audit.get("selected_candidate") or {}
    stage, metrics = _stage_and_metrics(audit)
    before_breaks_only = stage == "BEFORE_BREAKS_ONLY"
    preflight = audit.get("pre_solver_contract_validation") or {}
    feasibility = audit.get("capacity_diagnostics") or {}
    probe = audit.get("hard_feasibility_probe") or {}
    active = int(_num(metrics.get("active_intervals"), 0))
    after_target = int(_num(metrics.get("after_target"), 0))
    after_floor = int(_num(metrics.get("after_floor"), 0))
    avoidable = _num(metrics.get("after_avoidable_overage_fte_sum"), 0)
    target_overage = _num(metrics.get("after_target_overage_fte_sum"), 0)
    severe = int(_num(metrics.get("after_severe_overage_count"), 0))
    extreme = int(_num(metrics.get("after_extreme_overage_count"), 0))
    max_pct = _num(metrics.get("after_overage_max_pct"), 0)
    concentration = _num(metrics.get("after_overage_top10_concentration"), 0)
    # Track whether a hard-failure count was actually reported, not just whether
    # it happened to be zero. An absent count is not a clean validation.
    external = _external_validation(case_root)
    reported = (selected.get("output_validation") or {}).get("validation") or {}
    raw_hard = reported.get("hard_fail_count")
    validation_reported = raw_hard is not None
    validation_source = "engine_audit" if validation_reported else None
    if not validation_reported:
        raw_hard = audit.get("hard_fail_count")
        validation_reported = raw_hard is not None
        if validation_reported:
            validation_source = "audit"
    # The independent validator owns the final polished workbook check.  Do
    # not let an earlier engine-side PASS hide a later independent FAIL.
    external_validation_status = None
    if external:
        external_validation_status = _status(external.get("status"), "ERROR")
        raw_hard = external.get("hard_fail_count")
        validation_reported = raw_hard is not None
        validation_source = "independent_validator" if validation_reported else "independent_validator_incomplete"
    hard_failures = int(_num(raw_hard, 0))
    contract_status = _status(preflight.get("status"))
    feasibility_status = _status(feasibility.get("status"), _status(probe.get("cp_status")))
    # A before-break export is a schedule at its own stage. Reading "no
    # selected candidate" as "no schedule" is what produced safety NOT_RUN and
    # DIAGNOSTICS_ONLY on a validated skeleton run.
    schedule_present = bool(metrics) and (bool(selected) or before_breaks_only)
    # A schedule that was never validated is NOT a safe schedule. Previously an
    # audit carrying no hard_fail_count anywhere produced hard_failures == 0 and
    # therefore safety PASS, so a run whose output validation never executed was
    # published as having passed it.
    if not schedule_present:
        safety_status = "NOT_RUN"
    elif not validation_reported:
        safety_status = "NOT_VALIDATED"
    elif hard_failures == 0 and (not external or external_validation_status == "PASS"):
        safety_status = "PASS"
    elif external and external_validation_status != "PASS":
        safety_status = "ERROR" if external_validation_status.startswith("ERROR") else "FAIL"
    else:
        safety_status = "FAIL"
    production_gate = audit.get("production_quality_gate") or {}
    business_outcome = audit.get("business_outcome") or {}
    production_gate_status = _status(production_gate.get("status"), "NOT_EVALUATED")
    if production_gate_status == "FAIL":
        quality_status = "FAIL_PRODUCTION_QUALITY_GATE"
    elif not schedule_present:
        quality_status = "DIAGNOSTICS_ONLY"
    elif safety_status == "NOT_VALIDATED":
        quality_status = "REVIEW_NOT_VALIDATED"
    elif hard_failures:
        quality_status = "FAIL_SAFETY"
    elif production_gate_status == "WARN":
        quality_status = "WARN_PRODUCTION_QUALITY_LIMITED"
    elif extreme > 0:
        quality_status = "REVIEW_EXTREME_OVERAGE"
    elif severe > 0 or avoidable > 1e-9:
        quality_status = "REVIEW_CORRECTABLE_OVERAGE"
    elif active and after_floor < active:
        quality_status = "REVIEW_FLOOR_GAPS"
    elif active and after_target < active:
        quality_status = "PASS_WITH_TARGET_GAPS"
    else:
        quality_status = "PASS_CLEAN"
    parity = (external.get("metric_parity") or {}) if external else {}
    # Stage gate: did the stage that was asked for complete and check out?
    # This is deliberately not the release decision. A before-break artifact is
    # never releasable, so asking it to be FINAL_VERIFIED is a category error;
    # asking whether it completed, validated and agreed on its metrics is not.
    stage_gate_reasons = []
    if contract_status not in {"PASS", "WARN"} or len(preflight.get("failures") or []) > 0:
        stage_gate_reasons.append("input_contract_not_pass")
    if safety_status != "PASS":
        stage_gate_reasons.append("independent_validation_not_pass")
    if parity and str(parity.get("status") or "").upper() not in {"", "PASS"}:
        stage_gate_reasons.append("metric_parity_not_pass")
    if before_breaks_only:
        if _status(audit.get("artifact_state")) != "BEST_BEFORE_BREAKS_ONLY":
            stage_gate_reasons.append("before_break_artifact_not_exported")
    else:
        if _status(audit.get("artifact_state")) != "FINAL_VERIFIED":
            stage_gate_reasons.append("artifact_state_not_final_verified")
        if production_gate_status == "FAIL":
            stage_gate_reasons.append("production_quality_gate_failed")
    return {
        "schema_version": 1,
        "release": _status(audit.get("version"), RELEASE),
        "run_stage": stage,
        # A before-break artifact can never be released, whatever its numbers
        # say. Stating that here keeps a good skeleton report from reading as
        # an approval.
        "production_release_eligible": (
            False if before_breaks_only
            else _status(audit.get("artifact_state")) == "FINAL_VERIFIED"
        ),
        "stage_gate": {
            "stage": stage,
            "status": "PASS" if not stage_gate_reasons else "BLOCKED",
            "blocking_reasons": sorted(set(stage_gate_reasons)),
        },
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "audit_status": _status(audit.get("status")),
        "run_id": (audit.get("run_identity") or {}).get("run_id"),
        "input": audit.get("input"),
        "contract": {
            "status": contract_status,
            "failure_count": len(preflight.get("failures") or []),
            "warning_count": len(preflight.get("warnings") or []),
        },
        "feasibility": {
            "status": feasibility_status,
            "hard_failure_count": len(feasibility.get("hard_failures") or []),
            "probe_status": _status(probe.get("cp_status")),
        },
        "safety": {
            "status": safety_status,
            "hard_fail_count": hard_failures,
            "hard_fail_count_reported": validation_reported,
            "validation_source": validation_source,
            "external_validation_status": external_validation_status,
            "no_break_exception_count": int(_num(selected.get("no_break_exception_count"), 0)),
        },
        "coverage": {
            "active_intervals": active,
            "after_target": after_target,
            "after_floor": after_floor,
            "after100": int(_num(metrics.get("after_100"), 0)),
            "after90": int(_num(metrics.get("after_90"), 0)),
            "after80": int(_num(metrics.get("after_80"), 0)),
            "target_losses_from_breaks": int(_num(metrics.get("target_losses_from_breaks"), 0)),
            "floor_losses_from_breaks": int(_num(metrics.get("floor_losses_from_breaks"), 0)),
            # No breaks were placed at this stage, so after_* is the same
            # schedule measured again rather than a break outcome.
            "after_metrics_basis": (
                "NO_BREAKS_PLACED_AFTER_EQUALS_BEFORE" if before_breaks_only
                else "BREAKS_PLACED_BY_STAGE_2"),
            "canonical_metrics": canonicalize_metrics(metrics, "engine", stage=stage),
        },
        "evaluation": {
            "framework": "canonical_metric_surface_v1",
            "engine_source": (
                "stage_metric_surface.metrics" if audit.get("stage_metric_surface")
                else "selected_candidate.metrics"),
            "validator_source": "independent_validator.metrics",
            "engine_metrics": canonicalize_metrics(metrics, "engine", stage=stage),
            "validator_metrics": canonicalize_metrics(
                external.get("metrics") or {}, "independent_validator"
            ) if external else {},
            "metric_parity": external.get("metric_parity") if external else None,
            "validator_quality_gate_status": external.get("quality_gate_status") if external else None,
            "validator_coverage_quality_gate_status": external.get("coverage_quality_gate_status") if external else None,
            "release_decision": "hard_validation_then_quality_gate_then_human_approval",
        },
        "production_quality_gate": {
            "status": production_gate_status,
            "mode": _status(production_gate.get("mode"), "NOT_EVALUATED"),
            "failure_count": len(production_gate.get("failures") or []),
            "failures": production_gate.get("failures") or [],
        },
        "next_sunday": {
            "active_intervals": int(_num(metrics.get("week_boundary_active_intervals"), 0)),
            "after_target": int(_num(metrics.get("week_boundary_after_target"), 0)),
            "after_floor": int(_num(metrics.get("week_boundary_after_floor"), 0)),
            "floor_gap_count": int(_num(metrics.get("week_boundary_floor_gap_count"), 0)),
            "avoidable_overage_fte_sum": round(_num(metrics.get("week_boundary_avoidable_overage_fte_sum"), 0), 8),
            "maximum_coverage_ratio": round(_num(metrics.get("week_boundary_max_coverage_ratio"), 0), 8),
            "overage_cap_violations": int(_num(metrics.get("week_boundary_overage_cap_violation_count"), 0)),
            "maximum_adjacent_raw_change": int(_num(metrics.get("week_boundary_max_adjacent_raw_change"), 0)),
            "imbalance_violations": int(_num(metrics.get("week_boundary_imbalance_violation_count"), 0)),
        },
        "break_concurrency": {
            "maximum_observed": int(_num(metrics.get("max_concurrent_breaks_observed"), 0)),
            "maximum_ratio_observed": round(_num(metrics.get("max_concurrent_break_ratio_observed"), 0), 8),
            "violation_count": int(_num(metrics.get("break_concurrency_violation_count"), 0)),
        },
        "overage": {
            "target_overage_fte_sum": round(target_overage, 8),
            "avoidable_overage_fte_sum": round(avoidable, 8),
            "avoidable_overage_interval_count": int(_num(metrics.get("after_avoidable_overage_interval_count"), 0)),
            "severe_overage_interval_count": severe,
            "extreme_overage_interval_count": extreme,
            "indivisible_staffing_only_interval_count": int(_num(metrics.get("after_indivisible_staffing_only_count"), 0)),
            "maximum_coverage_ratio": round(max_pct, 8),
            "top10_concentration": round(concentration, 8),
            "classification": (
                "EXTREME" if extreme else "SEVERE_OR_CORRECTABLE" if severe or avoidable > 1e-9
                else "INTEGER_ROUNDING_ONLY" if target_overage > 1e-9 else "CONTROLLED"
            ),
        },
        "whole_week_balance": {
            "overage_cap_violation_count": int(_num(metrics.get("whole_week_overage_cap_violation_count"), 0)),
            "adjacent_imbalance_violation_count": int(_num(metrics.get("whole_week_imbalance_violation_count"), 0)),
            "maximum_adjacent_raw_change": int(_num(metrics.get("whole_week_max_adjacent_raw_change"), 0)),
            "transferable_overstaffing_pair_count": int(_num(metrics.get("transferable_overstaffing_pair_count"), 0)),
        },
        "language_resilience": {
            "required_quarters": int(_num(metrics.get("language_rule_quarters"), 0)),
            "minimum_only_quarters": int(_num(metrics.get("language_minimum_only_quarters"), 0)),
            "minimum_only_ratio": round(_num(metrics.get("language_minimum_only_ratio"), 0), 8),
            "reserve_shortfall_quarters": int(_num(metrics.get("language_reserve_shortfall_quarters"), 0)),
            "break_caused_reserve_loss_quarters": int(_num(metrics.get("language_break_caused_reserve_loss_quarters"), 0)),
        },
        "skill_allocation": {
            "protected_quarters": int(_num(metrics.get("skill_allocation_protected_quarters"), 0)),
            "gap_quarters": int(_num(metrics.get("skill_allocation_gap_quarters"), 0)),
            "maximum_slot_gap": int(_num(metrics.get("skill_allocation_maximum_gap"), 0)),
            "status": _status((metrics.get("skill_allocation_audit") or {}).get("status"), "NOT_EVALUATED"),
        },
        "break_feasibility_feedback": {
            "status": _status(((audit.get("logic_based_break_cut_feedback") or {}).get("execution") or {}).get("status"), "NOT_RUN"),
            "attempted": int(_num(((audit.get("logic_based_break_cut_feedback") or {}).get("execution") or {}).get("attempted"), 0)),
            "improved": int(_num(((audit.get("logic_based_break_cut_feedback") or {}).get("execution") or {}).get("improved"), 0)),
            "within_cap": int(_num(((audit.get("logic_based_break_cut_feedback") or {}).get("execution") or {}).get("within_cap"), 0)),
            "workbook_exception_cap": ((audit.get("logic_based_break_cut_feedback") or {}).get("execution") or {}).get("workbook_exception_cap"),
        },
        "employee_quality": metrics.get("employee_quality") or {},
        "feasibility_certificate": {
            "target_attainability_status": feasibility.get("target_attainability_status"),
            "floor_attainability_status": feasibility.get("floor_attainability_status"),
            "maximum_achievable_target_intervals_upper_bound": feasibility.get("maximum_achievable_target_intervals_upper_bound"),
            "maximum_achievable_floor_intervals_upper_bound": feasibility.get("maximum_achievable_floor_intervals_upper_bound"),
            "provably_unreachable_target_interval_count": feasibility.get("provably_unreachable_target_interval_count"),
            "estimated_additional_hc_for_aggregate_target": feasibility.get("estimated_additional_hc_for_aggregate_target"),
            "language_capacity_shortages": feasibility.get("language_capacity_shortages") or [],
        },
        "artifact_state": _status(audit.get("artifact_state"), "UNKNOWN"),
        "functional_status": _status(audit.get("functional_status"), "UNKNOWN"),
        "phase_c_promotion_status": _status(audit.get("phase_c_promotion_status"), "NOT_EVALUATED"),
        "phase_c_quality_status": quality_status,
        "business_outcome": {
            "outcome_code": business_outcome.get("outcome_code"),
            "outcome_category": business_outcome.get("outcome_category"),
            "headline": business_outcome.get("headline"),
            "plain_language_summary": business_outcome.get("plain_language_summary"),
            "requested": business_outcome.get("requested") or {},
            "best_proven": business_outcome.get("best_proven") or {},
            "gap": business_outcome.get("gap") or {},
            "recommended_actions": business_outcome.get("recommended_actions") or [],
            "technical_return_code": business_outcome.get("technical_return_code"),
        },
        "interpretation": (
            "The production quality gate is release-authoritative in the current Phase C engine: a failed gate cannot be exported as PASS. "
            "The separate overage classification remains diagnostic and excludes minimum whole-associate staffing "
            "required for fractional demand. Hard rules, workbook target/floor priorities, global champion retention, "
            "Next-Sunday protection, whole-week balance, language resilience, distinct skill allocation, logic-based break-feasibility feedback, employee quality, and break-concurrency limits remain authoritative."
        ),
    }


def flatten(report: Dict[str, Any]) -> list[tuple[str, Any]]:
    rows=[]
    for section in ("contract","feasibility","safety","production_quality_gate","coverage","evaluation","next_sunday","break_concurrency","overage","whole_week_balance","language_resilience","skill_allocation","break_feasibility_feedback","feasibility_certificate","business_outcome"):
        for key,value in (report.get(section) or {}).items():
            rows.append((f"{section}.{key}",value))
    rows.extend([
        ("audit_status",report.get("audit_status")),
        ("phase_c_quality_status",report.get("phase_c_quality_status")),
        ("run_id",report.get("run_id")),
        ("artifact_state",report.get("artifact_state")),
        ("functional_status",report.get("functional_status")),
        ("phase_c_promotion_status",report.get("phase_c_promotion_status")),
    ])
    return rows


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--audit-json",type=Path,required=True)
    ap.add_argument("--case-root",type=Path,required=True)
    ap.add_argument("--strict",action="store_true",help="Return non-zero when a production release gate is not clean.")
    args=ap.parse_args()
    audit=json.loads(args.audit_json.read_text(encoding="utf-8"))
    report=build_report(audit, args.case_root)
    args.case_root.mkdir(parents=True,exist_ok=True)
    out_json=args.case_root/"PHASE_C_QUALITY_SUMMARY.json"
    out_csv=args.case_root/"PHASE_C_QUALITY_SUMMARY.csv"
    out_json.write_text(json.dumps(report,indent=2),encoding="utf-8")
    with out_csv.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.writer(handle); writer.writerow(["Metric","Value"]); writer.writerows(flatten(report))
    print(json.dumps(report,indent=2))
    # A BEFORE_BREAKS_ONLY run is a diagnostic, not a release. The release
    # contract below asks whether this artifact can be published, which a
    # before-break skeleton never can - so applying it returned 2 on every
    # skeleton run and made the stage unusable. The stage gate answers the
    # question that stage actually has: did it complete and check out?
    # The release contract itself is unchanged for full runs.
    if str(report.get("run_stage") or "") == "BEFORE_BREAKS_ONLY":
        stage_gate = report.get("stage_gate") or {}
        stage_blocking = list(stage_gate.get("blocking_reasons") or [])
        if stage_gate.get("status") != "PASS" or stage_blocking:
            print(json.dumps({
                "status": "BLOCKED", "run_stage": "BEFORE_BREAKS_ONLY",
                "blocking_reasons": sorted(set(stage_blocking)) or ["stage_gate_not_pass"],
            }, indent=2))
            return 2
        # Never silently imply release approval for a review artifact.
        print(json.dumps({
            "status": "STAGE_COMPLETE",
            "run_stage": "BEFORE_BREAKS_ONLY",
            "production_release_eligible": False,
            "note": "Before-break review artifact. Breaks are not assigned; not releasable.",
            "quality_observation": report.get("phase_c_quality_status"),
        }, indent=2))
        return 0
    blocking = []
    if report.get("artifact_state") != "FINAL_VERIFIED":
        blocking.append("artifact_state_not_final_verified")
    contract = report.get("contract") or {}
    contract_status = str(contract.get("status") or "UNKNOWN").upper()
    if contract_status not in {"PASS", "WARN"} or int(contract.get("failure_count") or 0) > 0:
        blocking.append("input_contract_not_pass")
    if (report.get("safety") or {}).get("status") != "PASS":
        blocking.append("internal_output_validation_not_pass")
    gate = report.get("production_quality_gate") or {}
    if gate.get("status") == "FAIL":
        blocking.append("production_quality_gate_failed")
    if args.strict and str(gate.get("mode", "")).lower() == "fail" and gate.get("status") != "PASS":
        blocking.append("mandatory_production_quality_gate_not_pass")
    if args.strict and report.get("phase_c_quality_status") in {
        "FAIL_PRODUCTION_QUALITY_GATE", "FAIL_SAFETY", "REVIEW_NOT_VALIDATED",
        "REVIEW_EXTREME_OVERAGE", "DIAGNOSTICS_ONLY",
    }:
        blocking.append(str(report.get("phase_c_quality_status")))
    if blocking:
        print(json.dumps({"status":"BLOCKED","blocking_reasons":sorted(set(blocking))},indent=2))
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
