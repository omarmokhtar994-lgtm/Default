#!/usr/bin/env python3
"""Phase B engine-maturity infrastructure for the universal WFM scheduler.

This module deliberately contains only scenario-neutral orchestration helpers.
The scheduling contract, skill names, shift windows, targets, roster sizes, and
business rules remain workbook-driven in ``l632_universal_scheduler.py``.

Implemented capabilities
------------------------
* One global wall-clock budget with protected finalization time.
* Early safe-incumbent acquisition budget.
* Carry-forward phase deadlines: unused time remains available to later phases.
* Transaction ledger for bounded shift/OFF/break repairs.
* Adaptive attempt ordering and stagnation tracking.
* Stable cache keys for warm-started/replayed CP-SAT attempts.
"""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Tuple

PHASE_B_INFRA_VERSION = "1.4-rc9.2"


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class PhaseBudget:
    name: str
    seconds: int
    deadline_offset_sec: int


@dataclass
class GlobalBudgetManager:
    """Single-run budget controller with protected phase deadlines.

    The plan is cumulative. Finishing a phase early carries unused wall time to
    all later phases, while an early phase cannot consume the reserved time of
    later phases. This avoids the old Quick + Deep sequential budget pattern.
    """

    total_seconds: int
    phase_seconds: Mapping[str, int]
    started_epoch: float = field(default_factory=time.time)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.total_seconds = max(60, int(self.total_seconds))
        normalized: Dict[str, int] = {str(k): max(0, int(v)) for k, v in self.phase_seconds.items()}
        allocated = sum(normalized.values())
        if allocated != self.total_seconds:
            delta = self.total_seconds - allocated
            target = "break_search" if "break_search" in normalized else next(iter(normalized), "finalization")
            normalized[target] = max(0, normalized.get(target, 0) + delta)
        self.phase_seconds = normalized
        self._ordered = list(normalized)
        cumulative = 0
        self._deadlines: Dict[str, float] = {}
        for name in self._ordered:
            cumulative += normalized[name]
            self._deadlines[name] = self.started_epoch + cumulative

    @property
    def final_deadline(self) -> float:
        return self.started_epoch + self.total_seconds

    def elapsed(self) -> float:
        return max(0.0, time.time() - self.started_epoch)

    def remaining_total(self) -> float:
        return max(0.0, self.final_deadline - time.time())

    def deadline(self, phase: str) -> float:
        return self._deadlines.get(phase, self.final_deadline)

    def remaining_in_phase(self, phase: str) -> float:
        return max(0.0, self.deadline(phase) - time.time())

    def slice_seconds(
        self,
        phase: str,
        attempts_left: int = 1,
        minimum: float = 1.0,
        maximum: Optional[float] = None,
        share: float = 0.70,
    ) -> float:
        """Return a bounded solver slice inside the phase deadline."""
        remaining = self.remaining_in_phase(phase)
        if remaining <= 0:
            return 0.0
        attempts = max(1, int(attempts_left))
        proposed = remaining * max(0.05, min(1.0, float(share))) / attempts
        proposed = max(float(minimum), proposed)
        if maximum is not None:
            proposed = min(float(maximum), proposed)
        return max(0.0, min(proposed, remaining))

    def record(self, phase: str, event: str, **details: Any) -> None:
        self.events.append({
            "phase": phase,
            "event": event,
            "elapsed_sec": round(self.elapsed(), 6),
            "remaining_total_sec": round(self.remaining_total(), 6),
            "remaining_phase_sec": round(self.remaining_in_phase(phase), 6),
            **details,
        })

    def snapshot(self) -> Dict[str, Any]:
        cumulative = 0
        phases: List[Dict[str, Any]] = []
        for name in self._ordered:
            cumulative += self.phase_seconds[name]
            phases.append({
                "phase": name,
                "allocated_seconds": self.phase_seconds[name],
                "deadline_offset_seconds": cumulative,
            })
        return {
            "infrastructure_version": PHASE_B_INFRA_VERSION,
            "total_seconds": self.total_seconds,
            "elapsed_seconds": round(self.elapsed(), 6),
            "remaining_seconds": round(self.remaining_total(), 6),
            "phases": phases,
            "events": list(self.events),
        }


def build_global_budget_plan(
    total_seconds: int,
    *,
    allow_exceptions: bool,
    coordinated_repair: bool,
    joint_refinement: bool = True,
    post_break_repair: bool = True,
    target_lock_recovery: bool,
    finalization_reserve_sec: int = 300,
    safe_incumbent_reserve_sec: int = 600,
    conflict_refinement_reserve_sec: int = 300,
    coordinated_repair_reserve_sec: int = 1200,
    joint_refinement_reserve_sec: int = 1800,
) -> Dict[str, int]:
    """Create a scenario-neutral, single-run budget plan.

    For short functional runs, optional phases are scaled down first. For a
    four-hour Deep run, the plan protects an early incumbent and finalization
    while assigning most time to skeleton and break search.
    """
    total = max(60, int(total_seconds))
    # Protected floors. Optional phases may be zero on very short tests.
    finalization = min(max(30, int(total * 0.035)), max(30, int(finalization_reserve_sec)))
    preflight_probe = min(max(20, int(total * 0.035)), 420)
    conflict = 0 if total < 600 else min(max(45, int(total * 0.025)), max(45, int(conflict_refinement_reserve_sec)))
    safe = 0 if total < 180 else min(max(45, int(total * 0.075)), max(45, int(safe_incumbent_reserve_sec)))
    joint = 0
    if joint_refinement and total >= 600:
        # RC4.4.2 capped the adaptive joint phase at 12% even when the runner
        # explicitly reserved a much larger budget. Real cases therefore
        # received only 1,728 seconds from a requested 4,800-second reserve.
        # Honor the request up to a scenario-neutral 35% wall-time ceiling.
        requested_joint = max(120, int(joint_refinement_reserve_sec))
        joint = min(requested_joint, max(120, int(total * 0.35)))
    coordinated = 0
    if coordinated_repair and total >= 600:
        coordinated = min(max(90, int(total * 0.07)), max(90, int(coordinated_repair_reserve_sec)))
    post = 0
    if post_break_repair and total >= 480:
        post = min(max(60, int(total * 0.04)), 600)
    target = 0
    if target_lock_recovery and total >= 480:
        target = min(max(60, int(total * 0.04)), 600)
    exception = 0
    if allow_exceptions and total >= 900:
        exception = min(max(90, int(total * 0.05)), 900)

    fixed = preflight_probe + conflict + safe + joint + coordinated + post + target + exception + finalization
    # Keep at least 30% of the run for the two primary optimization phases.
    primary_floor = max(60, int(total * 0.30))
    if fixed > total - primary_floor:
        scalable_names = ["conflict_refinement", "safe_incumbent", "joint_refinement", "coordinated_repair", "post_break_repair", "target_lock_recovery", "exception_search"]
        scalable = {
            "conflict_refinement": conflict,
            "safe_incumbent": safe,
            "joint_refinement": joint,
            "coordinated_repair": coordinated,
            "post_break_repair": post,
            "target_lock_recovery": target,
            "exception_search": exception,
        }
        excess = fixed - (total - primary_floor)
        scalable_total = sum(scalable.values())
        if scalable_total > 0:
            keep_ratio = max(0.0, (scalable_total - excess) / scalable_total)
            for key in scalable_names:
                scalable[key] = int(scalable[key] * keep_ratio)
        conflict = scalable["conflict_refinement"]
        safe = scalable["safe_incumbent"]
        joint = scalable["joint_refinement"]
        coordinated = scalable["coordinated_repair"]
        post = scalable["post_break_repair"]
        target = scalable["target_lock_recovery"]
        exception = scalable["exception_search"]
        fixed = preflight_probe + conflict + safe + joint + coordinated + post + target + exception + finalization

    primary = max(60, total - fixed)
    # Split primary optimization toward break search; break quality is the final
    # production objective, while before-break quality remains a protected input.
    stage1 = max(30, int(primary * 0.42))
    break_search = max(30, primary - stage1)

    plan = {
        "preflight_probe": preflight_probe,
        "conflict_refinement": conflict,
        "safe_incumbent": safe,
        "stage1_search": stage1,
        "break_search": break_search,
        "joint_refinement": joint,
        "coordinated_repair": coordinated,
        "exception_search": exception,
        "post_break_repair": post,
        "target_lock_recovery": target,
        "finalization": finalization,
    }
    delta = total - sum(plan.values())
    plan["break_search"] += delta
    return plan


@dataclass
class TransactionLedger:
    """Append-only transaction log for bounded repair attempts."""

    path: Optional[Path] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    _next_id: int = 1

    def begin(self, kind: str, anchor_id: str, proposal: Mapping[str, Any]) -> str:
        transaction_id = f"TX-{self._next_id:05d}"
        self._next_id += 1
        self.rows.append({
            "transaction_id": transaction_id,
            "kind": kind,
            "anchor_id": anchor_id,
            "status": "STARTED",
            "proposal": dict(proposal),
            "started_at_monotonic": time.monotonic(),
        })
        self.flush()
        return transaction_id

    def _find(self, transaction_id: str) -> MutableMapping[str, Any]:
        for row in reversed(self.rows):
            if row.get("transaction_id") == transaction_id:
                return row
        raise KeyError(transaction_id)

    def commit(self, transaction_id: str, *, validation: Mapping[str, Any], quality_delta: Mapping[str, Any], result: Mapping[str, Any]) -> None:
        row = self._find(transaction_id)
        row.update({
            "status": "COMMITTED",
            "completed_at_monotonic": time.monotonic(),
            "validation": dict(validation),
            "quality_delta": dict(quality_delta),
            "result": dict(result),
        })
        self.flush()

    def rollback(self, transaction_id: str, reason: str, *, validation: Optional[Mapping[str, Any]] = None, result: Optional[Mapping[str, Any]] = None) -> None:
        row = self._find(transaction_id)
        row.update({
            "status": "ROLLED_BACK",
            "completed_at_monotonic": time.monotonic(),
            "rollback_reason": str(reason),
            "validation": dict(validation or {}),
            "result": dict(result or {}),
        })
        self.flush()

    def flush(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps({"schema_version": 1, "transactions": self.rows}, indent=2, default=str), encoding="utf-8")
        temporary.replace(self.path)

    def summary(self) -> Dict[str, Any]:
        return {
            "transaction_count": len(self.rows),
            "committed": sum(row.get("status") == "COMMITTED" for row in self.rows),
            "rolled_back": sum(row.get("status") == "ROLLED_BACK" for row in self.rows),
            "started": sum(row.get("status") == "STARTED" for row in self.rows),
            "path": str(self.path) if self.path else None,
        }


@dataclass(frozen=True)
class AdaptiveBreakTask:
    skeleton_index: int
    width: int
    objective_mode: str
    priority: Tuple[Any, ...]


def adaptive_break_attempt_plan(
    skeleton_records: Sequence[Mapping[str, Any]],
    pattern_widths: Sequence[int],
    objective_modes: Sequence[str],
) -> List[AdaptiveBreakTask]:
    """Breadth-first, target-driven Stage-2 attempt ordering.

    RC8.13 restored the best before-break target skeleton, but GDI REAL28 showed
    a universal orchestration weakness: the break phase could spend too long on
    one restored skeleton, repeatedly returning INFEASIBLE/UNKNOWN, while other
    Pareto skeletons were not tested early enough.  RC9.1 changes the attempt
    plan from ``exhaust the best skeleton`` to ``expand one meaningful layer,
    then test the next skeleton``.

    The ordering is still scenario-neutral.  It uses the workbook target counts
    in the skeleton records; it never checks client names.  Full-width patterns
    are tried first, then objective modes, then the next target/floor Pareto
    skeleton.  Deeper widths/modes only run after the breadth layer has been
    covered.
    """
    widths = sorted({max(1, int(width)) for width in pattern_widths})
    if not widths:
        widths = [1]
    width_order = {width: index for index, width in enumerate(sorted(widths, reverse=True))}
    raw_modes = list(dict.fromkeys(str(mode) for mode in objective_modes))
    preferred_modes = [
        "target_priority", "release_quality_guard", "coverage_rebalance",
        "quality_convergence", "floor_protected", "balanced", "target_100",
    ]
    modes: List[str] = []
    for mode in preferred_modes + raw_modes:
        if mode not in modes:
            modes.append(mode)

    skeleton_rank_rows: List[Tuple[Tuple[Any, ...], int]] = []
    for skeleton_index, record in enumerate(skeleton_records):
        min_exc = record.get("minimum_exception_count")
        upper_exc = record.get("minimum_exception_upper_bound")
        exception_rank = int(min_exc) if isinstance(min_exc, int) else (int(upper_exc) if isinstance(upper_exc, int) else 999999)
        before_target = int(record.get("before_target", 0) or 0)
        before_floor = int(record.get("before_floor", 0) or 0)
        before_100 = int(record.get("before_100", 0) or 0)
        floor_gaps = int(record.get("floor_gaps", 999999) or 999999)
        severe_gaps = int(record.get("severe_floor_gaps", 999999) or 999999)
        max_floor_run = int(record.get("max_floor_run", 999999) or 999999)
        overage = float(record.get("before_avoidable_overage_fte_sum", 0.0) or 0.0)
        skeleton_key = (
            exception_rank,
            -before_target,
            -before_floor,
            -before_100,
            floor_gaps,
            severe_gaps,
            max_floor_run,
            round(overage, 6),
            skeleton_index,
        )
        skeleton_rank_rows.append((skeleton_key, skeleton_index))
    rank_by_index = {idx: rank for rank, (_, idx) in enumerate(sorted(skeleton_rank_rows, key=lambda row: row[0]))}

    tasks: List[AdaptiveBreakTask] = []
    for skeleton_index, record in enumerate(skeleton_records):
        min_exc = record.get("minimum_exception_count")
        upper_exc = record.get("minimum_exception_upper_bound")
        exception_rank = int(min_exc) if isinstance(min_exc, int) else (int(upper_exc) if isinstance(upper_exc, int) else 999999)
        before_target = int(record.get("before_target", 0) or 0)
        before_floor = int(record.get("before_floor", 0) or 0)
        before_100 = int(record.get("before_100", 0) or 0)
        floor_gaps = int(record.get("floor_gaps", 999999) or 999999)
        severe_gaps = int(record.get("severe_floor_gaps", 999999) or 999999)
        max_floor_run = int(record.get("max_floor_run", 999999) or 999999)
        overage = float(record.get("before_avoidable_overage_fte_sum", 0.0) or 0.0)
        skeleton_rank = rank_by_index.get(skeleton_index, skeleton_index)
        for width in widths:
            width_rank = width_order.get(width, 999999)
            for mode_index, mode in enumerate(modes):
                mode_rank = preferred_modes.index(mode) if mode in preferred_modes else len(preferred_modes) + mode_index
                # Breadth key first: width -> mode -> skeleton.  Skeleton quality
                # remains inside the skeleton rank, so the best skeleton still
                # leads each layer without monopolizing all layers.
                tasks.append(AdaptiveBreakTask(
                    skeleton_index=skeleton_index,
                    width=width,
                    objective_mode=mode,
                    priority=(
                        exception_rank,
                        width_rank,
                        mode_rank,
                        skeleton_rank,
                        -before_target,
                        -before_floor,
                        -before_100,
                        floor_gaps,
                        severe_gaps,
                        max_floor_run,
                        round(overage, 6),
                        skeleton_index,
                    ),
                ))
    return sorted(tasks, key=lambda task: task.priority)


@dataclass
class AdaptiveConvergence:
    no_improvement_limit: int
    attempts: int = 0
    last_improvement_attempt: int = 0
    best_signature: Optional[Tuple[Tuple[Any, ...], ...]] = None
    improvement_count: int = 0

    def observe(self, signature: Tuple[Tuple[Any, ...], ...]) -> bool:
        self.attempts += 1
        improved = self.best_signature is None or signature != self.best_signature
        if improved:
            self.best_signature = signature
            self.last_improvement_attempt = self.attempts
            self.improvement_count += 1
        return improved

    def stagnant(self) -> bool:
        return (
            self.no_improvement_limit > 0
            and self.attempts - self.last_improvement_attempt >= self.no_improvement_limit
        )

    def snapshot(self) -> Dict[str, Any]:
        return {
            "attempts": self.attempts,
            "last_improvement_attempt": self.last_improvement_attempt,
            "improvement_count": self.improvement_count,
            "no_improvement_limit": self.no_improvement_limit,
            "stagnant": self.stagnant(),
            "best_signature": [list(row) for row in self.best_signature] if self.best_signature else [],
        }


def stable_attempt_key(
    *,
    skeleton_fingerprint: str,
    pattern_width: int,
    objective_mode: str,
    exception_mode: bool,
    exception_cap: Optional[int],
    min_target_hits: Optional[int],
    min_floor_hits: Optional[int],
    phase: str,
) -> str:
    return _canonical_hash({
        "skeleton_fingerprint": skeleton_fingerprint,
        "pattern_width": int(pattern_width),
        "objective_mode": str(objective_mode),
        "exception_mode": bool(exception_mode),
        "exception_cap": exception_cap,
        "min_target_hits": min_target_hits,
        "min_floor_hits": min_floor_hits,
        "phase": str(phase),
    })[:32]
