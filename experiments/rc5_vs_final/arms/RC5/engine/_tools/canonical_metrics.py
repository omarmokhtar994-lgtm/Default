"""Canonical metric names and parity checks shared by release paths.

The optimizer and the independent validator deliberately calculate coverage
independently. They must nevertheless publish the same metric vocabulary so a
release decision cannot compare ``after_100`` with ``after100`` by accident.
This module normalizes names only; it never calculates coverage.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping


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
}

PARITY_FIELDS = tuple(ALIASES)
INTEGER_FIELDS = {
    name for name in PARITY_FIELDS
    if not name.endswith("_ratio_observed") and name not in {
        "after_avoidable_overage_fte_sum",
        "after_avoidable_overage_peak_fte",
        "after_avoidable_overage_variance_fte",
        "after_avoidable_overage_stddev_fte",
        "after_avoidable_overage_top10_concentration",
    }
}


def canonicalize_metrics(metrics: Mapping[str, Any] | None, source: str) -> Dict[str, Any]:
    """Return one stable metric surface without changing source values."""
    raw = metrics or {}
    result: Dict[str, Any] = {
        "schema_version": 1,
        "evaluator": "canonical_metric_surface_v1",
        "source": str(source),
    }
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
) -> Dict[str, Any]:
    """Compare normalized metrics and make omissions explicit."""
    left = canonicalize_metrics(engine_metrics, "engine")
    right = canonicalize_metrics(validator_metrics, "independent_validator")
    mismatches = []
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
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "evaluator": "canonical_metric_surface_v1",
        "compared_fields": list(PARITY_FIELDS),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "engine": left,
        "validator": right,
    }
