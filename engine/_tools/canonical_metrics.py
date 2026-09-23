"""Canonical metric names and parity checks shared by release paths.

The optimizer and the independent validator deliberately calculate coverage
independently. They must nevertheless publish the same metric vocabulary so a
release decision cannot compare ``after_100`` with ``after100`` by accident.
This module normalizes names only; it never calculates coverage.

A run stops at one of two stages. ``FULL_SCHEDULE`` places breaks;
``BEFORE_BREAKS_ONLY`` exports the Stage-1 skeleton and never starts Stage 2.
Both stages publish the same metric vocabulary, so the gate below compares the
same fields either way - the stage is carried as evidence and cross-checked,
never used to excuse a field from comparison.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


STAGE_BEFORE_BREAKS_ONLY = "BEFORE_BREAKS_ONLY"
STAGE_FULL_SCHEDULE = "FULL_SCHEDULE"
STAGES = (STAGE_BEFORE_BREAKS_ONLY, STAGE_FULL_SCHEDULE)

# The validator names the artifact it read; the engine names the stage it ran.
# They are two vocabularies for one fact, so the gate can only cross-check them
# through an explicit mapping.
ARTIFACT_ROLE_STAGE = {
    "BEST_BEFORE_BREAKS": STAGE_BEFORE_BREAKS_ONLY,
    "FINAL_AFTER_BREAKS": STAGE_FULL_SCHEDULE,
}

# When no break stage ran, every after-break coverage figure must be identical
# to its before-break twin: there is nothing that could have moved it. A
# difference means one side invented a break effect that the artifact does not
# contain, which is a defect in that side, not a stage difference.
BEFORE_AFTER_PAIRS = (
    ("before_100", "after_100"),
    ("before_90", "after_90"),
    ("before_80", "after_80"),
    ("before_target", "after_target"),
    ("before_floor", "after_floor"),
)


ALIASES = {
    "active_intervals": ("active_intervals",),
    "before_100": ("before_100", "before100"),
    "before_90": ("before_90", "before90"),
    "before_80": ("before_80", "before80"),
    "after_100": ("after_100", "after100"),
    "after_90": ("after_90", "after90"),
    "after_80": ("after_80", "after80"),
    "before_target": ("before_target",),
    "after_target": ("after_target",),
    "before_floor": ("before_floor",),
    "after_floor": ("after_floor",),
    "floor_gap_count": ("floor_gap_count", "floor_gaps"),
    "severe_floor_gap_count": ("severe_floor_gap_count", "severe_floor_gaps"),
    "max_consecutive_floor_gaps": ("max_consecutive_floor_gaps", "max_floor_run"),
    "zero_staffed_active_quarters": ("zero_staffed_active_quarters",),
    "language_gap_count": ("language_gap_count",),
    "opening_gap_count": ("opening_gap_count",),
    "blank_staffed_quarters": ("blank_staffed_quarters",),
    "break_concurrency_violation_count": ("break_concurrency_violation_count",),
    "whole_week_overage_cap_violation_count": ("whole_week_overage_cap_violation_count",),
    "whole_week_imbalance_violation_count": ("whole_week_imbalance_violation_count",),
    "max_concurrent_breaks_observed": ("max_concurrent_breaks_observed",),
    "max_concurrent_break_ratio_observed": ("max_concurrent_break_ratio_observed",),
    # The validator's post-break-only value maps to the engine's explicit
    # after-break value. This is a documented alias, not a second calculation.
    "after_avoidable_overage_fte_sum": (
        "after_avoidable_overage_fte_sum", "avoidable_overage_fte_sum"
    ),
    "after_avoidable_overage_interval_count": (
        "after_avoidable_overage_interval_count", "avoidable_overage_positive_interval_count"
    ),
    "after_severe_overage_count": (
        "after_severe_overage_count", "severe_overage_interval_count"
    ),
    "after_extreme_overage_count": (
        "after_extreme_overage_count", "extreme_overage_interval_count"
    ),
    "after_avoidable_overage_peak_fte": (
        "after_avoidable_overage_peak_fte", "avoidable_overage_peak_fte"
    ),
    "after_avoidable_overage_variance_fte": (
        "after_avoidable_overage_variance_fte", "avoidable_overage_variance_fte"
    ),
    "after_avoidable_overage_stddev_fte": (
        "after_avoidable_overage_stddev_fte", "avoidable_overage_stddev_fte"
    ),
    "after_avoidable_overage_top10_concentration": (
        "after_avoidable_overage_top10_concentration",
        "after_overage_top10_concentration", "avoidable_overage_top10_concentration"
    ),
    "after_max_consecutive_avoidable_overage_intervals": (
        "after_max_consecutive_avoidable_overage_intervals", "avoidable_overage_max_consecutive_intervals"
    ),
    "week_boundary_after_target": (
        "week_boundary_after_target", "next_sunday_target_hits"
    ),
    "week_boundary_after_floor": (
        "week_boundary_after_floor", "next_sunday_floor_hits"
    ),
    "week_boundary_floor_gap_count": (
        "week_boundary_floor_gap_count", "next_sunday_floor_gap_count"
    ),
    "week_boundary_zero_staffed_active_quarters": (
        "week_boundary_zero_staffed_active_quarters", "next_sunday_zero_staffed_quarters"
    ),
    "week_boundary_language_gap_count": (
        "week_boundary_language_gap_count", "next_sunday_language_gap_count"
    ),
    "week_boundary_opening_gap_count": (
        "week_boundary_opening_gap_count", "next_sunday_opening_gap_count"
    ),
    "week_boundary_blank_staffed_quarters": (
        "week_boundary_blank_staffed_quarters", "next_sunday_blank_staffed_quarters"
    ),
    "week_boundary_overage_cap_violation_count": (
        "week_boundary_overage_cap_violation_count", "next_sunday_overage_cap_violation_count"
    ),
    "week_boundary_imbalance_violation_count": (
        "week_boundary_imbalance_violation_count", "next_sunday_imbalance_violation_count"
    ),
    # B-9: six fields that a release gate or candidate selection reads, added
    # to the parity surface once the independent validator derived them too.
    # Before this, an engine-side error in any of them was invisible: nothing
    # else computed the number, so there was nothing to disagree with.
    "target_losses_from_breaks": ("target_losses_from_breaks",),
    "floor_losses_from_breaks": ("floor_losses_from_breaks",),
    "before_severe_floor_gap_count": ("before_severe_floor_gap_count",),
    "hard_floor_gap_count": ("hard_floor_gap_count",),
    "week_boundary_hard_failure_count": ("week_boundary_hard_failure_count", "next_sunday_hard_failure_count"),
    "week_boundary_max_adjacent_raw_change": ("week_boundary_max_adjacent_raw_change", "next_sunday_max_adjacent_raw_change"),
    "week_boundary_max_coverage_ratio": ("week_boundary_max_coverage_ratio", "next_sunday_max_coverage_ratio"),
}

PARITY_FIELDS = tuple(ALIASES)
INTEGER_FIELDS = {
    name for name in PARITY_FIELDS
    if not name.endswith("_ratio_observed") and name not in {
        "week_boundary_max_coverage_ratio",
        "after_avoidable_overage_fte_sum",
        "after_avoidable_overage_peak_fte",
        "after_avoidable_overage_variance_fte",
        "after_avoidable_overage_stddev_fte",
        "after_avoidable_overage_top10_concentration",
    }
}


def stage_for_artifact_role(role: Any) -> Optional[str]:
    """Translate the validator's artifact role into a run stage, or None."""
    if role is None:
        return None
    return ARTIFACT_ROLE_STAGE.get(str(role).strip().upper())


def canonicalize_metrics(
    metrics: Mapping[str, Any] | None,
    source: str,
    *,
    stage: Optional[str] = None,
) -> Dict[str, Any]:
    """Return one stable metric surface without changing source values.

    ``stage`` is recorded as evidence when the caller knows it. It never
    filters, defaults or rewrites a value: an unknown stage stays unknown
    rather than being guessed from the metrics themselves.
    """
    raw = metrics or {}
    result: Dict[str, Any] = {
        "schema_version": 2,
        "evaluator": "canonical_metric_surface_v1",
        "source": str(source),
    }
    if stage is not None:
        normalized = str(stage).strip().upper()
        result["stage"] = normalized if normalized in STAGES else "UNRECOGNIZED_STAGE"
        result["break_stage_executed"] = (
            False if normalized == STAGE_BEFORE_BREAKS_ONLY
            else True if normalized == STAGE_FULL_SCHEDULE
            else None
        )
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            if alias in raw and raw[alias] is not None:
                result[canonical] = raw[alias]
                break
    return result


def compare_metric_surfaces(
    engine_metrics: Mapping[str, Any] | None,
    validator_metrics: Mapping[str, Any] | None,
    *,
    float_tolerance: float = 1e-6,
    engine_stage: Optional[str] = None,
    validator_stage: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare normalized metrics and make omissions explicit.

    Every canonical field is compared at every stage. The stage arguments add
    two checks rather than removing any: the two sides must agree on which
    stage produced the artifact, and a run that never started Stage 2 must
    report after-break coverage identical to its before-break coverage.
    """
    left = canonicalize_metrics(engine_metrics, "engine", stage=engine_stage)
    right = canonicalize_metrics(
        validator_metrics, "independent_validator", stage=validator_stage)
    mismatches = []
    if engine_stage is not None or validator_stage is not None:
        engine_declared = left.get("stage")
        validator_declared = right.get("stage")
        if engine_declared != validator_declared:
            # All three cases block. They are named apart because "the two
            # sides disagree" and "one side never said" are different
            # defects: the first is a real contradiction about one artifact,
            # the second means the comparison has no stage to stand on.
            if engine_declared is None:
                reason = "ENGINE_DECLARED_NO_STAGE"
            elif validator_declared is None:
                reason = "VALIDATOR_DECLARED_NO_STAGE"
            else:
                reason = "STAGE_DISAGREEMENT"
            mismatches.append({
                "field": "run_stage",
                "engine": engine_declared,
                "validator": validator_declared,
                "reason": reason,
            })
    for field in PARITY_FIELDS:
        if field not in left or field not in right:
            mismatches.append({
                "field": field,
                "engine": left.get(field),
                "validator": right.get(field),
                "reason": "MISSING_CANONICAL_METRIC",
            })
            continue
        a, b = left[field], right[field]
        try:
            if field in INTEGER_FIELDS:
                equal = int(round(float(a))) == int(round(float(b)))
            else:
                equal = abs(float(a) - float(b)) <= float_tolerance
        except (TypeError, ValueError):
            equal = a == b
        if not equal:
            mismatches.append({
                "field": field,
                "engine": a,
                "validator": b,
                "reason": "VALUE_MISMATCH",
            })
    # A skeleton-only artifact contains no breaks, so "after breaks" can only
    # mean "the same schedule, measured again". Checking that both sides say so
    # is what stops an after-break figure from being read as a break result
    # that was never computed.
    stage_checked = None
    for surface in (left, right):
        if surface.get("stage") == STAGE_BEFORE_BREAKS_ONLY:
            stage_checked = STAGE_BEFORE_BREAKS_ONLY
            for before_field, after_field in BEFORE_AFTER_PAIRS:
                if before_field not in surface or after_field not in surface:
                    continue
                try:
                    equal = (int(round(float(surface[before_field])))
                             == int(round(float(surface[after_field]))))
                except (TypeError, ValueError):
                    equal = surface[before_field] == surface[after_field]
                if not equal:
                    mismatches.append({
                        "field": after_field,
                        "source": surface.get("source"),
                        "engine": left.get(after_field),
                        "validator": right.get(after_field),
                        "before_value": surface[before_field],
                        "after_value": surface[after_field],
                        "reason": "AFTER_DIFFERS_FROM_BEFORE_WITHOUT_BREAK_STAGE",
                    })
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "evaluator": "canonical_metric_surface_v1",
        "compared_fields": list(PARITY_FIELDS),
        "engine_stage": left.get("stage"),
        "validator_stage": right.get("stage"),
        "before_after_identity_checked": stage_checked is not None,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "engine": left,
        "validator": right,
    }
