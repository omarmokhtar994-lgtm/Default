#!/usr/bin/env python3
"""Scenario-neutral adaptive search infrastructure for Phase B RC4.4.

The scheduling contract remains in ``l632_universal_scheduler.py``.  This module
contains only generic adaptive-search state: a deterministic operator portfolio,
feedback-cut records, and bound-quality certificate helpers.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ADAPTIVE_INFRA_VERSION = "1.0"


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class FeedbackCut:
    """A scenario-neutral master/subproblem feedback record.

    ``kind`` controls how the scheduler translates the record into CP-SAT
    constraints.  The payload is deliberately JSON-compatible so cuts can be
    checkpointed, audited, and replayed.
    """

    kind: str
    payload: Mapping[str, Any]
    source_profile: str = ""
    source_class: str = ""
    severity: float = 1.0

    @property
    def cut_id(self) -> str:
        return canonical_hash({
            "kind": self.kind,
            "payload": dict(self.payload),
            "source_profile": self.source_profile,
            "source_class": self.source_class,
        })[:20]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "cut_id": self.cut_id,
            "kind": self.kind,
            "payload": dict(self.payload),
            "source_profile": self.source_profile,
            "source_class": self.source_class,
            "severity": float(self.severity),
        }


@dataclass
class OperatorStats:
    name: str
    weight: float = 1.0
    attempts: int = 0
    feasible: int = 0
    accepted: int = 0
    improvements: int = 0
    reward_sum: float = 0.0
    last_reward: float = 0.0

    def update(self, reward: float, *, feasible: bool, accepted: bool, improved: bool, reaction: float) -> None:
        self.attempts += 1
        self.feasible += int(bool(feasible))
        self.accepted += int(bool(accepted))
        self.improvements += int(bool(improved))
        self.reward_sum += float(reward)
        self.last_reward = float(reward)
        target = max(0.05, 1.0 + float(reward))
        rho = min(1.0, max(0.01, float(reaction)))
        self.weight = max(0.05, (1.0 - rho) * self.weight + rho * target)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "weight": round(float(self.weight), 6),
            "attempts": int(self.attempts),
            "feasible": int(self.feasible),
            "accepted": int(self.accepted),
            "improvements": int(self.improvements),
            "reward_sum": round(float(self.reward_sum), 6),
            "last_reward": round(float(self.last_reward), 6),
        }


@dataclass
class AdaptiveOperatorPortfolio:
    """Deterministic adaptive large-neighborhood operator selector.

    Operators are selected by seeded roulette.  Weights are updated from actual
    candidate quality and feasibility, so a workbook can favor the operators
    that work for its particular break, skill, coverage, or OFF-pattern damage.
    """

    operator_names: Sequence[str]
    seed: int = 0
    reaction: float = 0.20
    exploration_floor: float = 0.08
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        names = list(dict.fromkeys(str(name) for name in self.operator_names if str(name)))
        if not names:
            raise ValueError("AdaptiveOperatorPortfolio requires at least one operator")
        self._rng = random.Random(int(self.seed))
        self.stats: Dict[str, OperatorStats] = {name: OperatorStats(name=name) for name in names}

    def choose(self, *, forbidden: Iterable[str] = ()) -> str:
        blocked = set(forbidden)
        available = [row for name, row in self.stats.items() if name not in blocked]
        if not available:
            available = list(self.stats.values())
        floor = max(0.0, float(self.exploration_floor))
        masses = [max(floor, float(row.weight)) for row in available]
        total = sum(masses)
        point = self._rng.random() * total
        running = 0.0
        for row, mass in zip(available, masses):
            running += mass
            if point <= running:
                return row.name
        return available[-1].name

    def update(
        self,
        name: str,
        *,
        reward: float,
        feasible: bool,
        accepted: bool,
        improved: bool,
        details: Optional[Mapping[str, Any]] = None,
    ) -> None:
        row = self.stats[name]
        row.update(
            reward,
            feasible=feasible,
            accepted=accepted,
            improved=improved,
            reaction=self.reaction,
        )
        self.history.append({
            "attempt": len(self.history) + 1,
            "operator": name,
            "reward": round(float(reward), 6),
            "feasible": bool(feasible),
            "accepted": bool(accepted),
            "improved": bool(improved),
            "weight_after": round(float(row.weight), 6),
            "details": dict(details or {}),
        })

    def snapshot(self) -> Dict[str, Any]:
        return {
            "adaptive_infrastructure_version": ADAPTIVE_INFRA_VERSION,
            "seed": int(self.seed),
            "reaction": float(self.reaction),
            "exploration_floor": float(self.exploration_floor),
            "operators": [self.stats[name].as_dict() for name in sorted(self.stats)],
            "history": list(self.history),
        }


def objective_gap(*, value: Optional[float], bound: Optional[float], sense: str) -> Optional[float]:
    if value is None or bound is None:
        return None
    value_f, bound_f = float(value), float(bound)
    denominator = max(1.0, abs(value_f), abs(bound_f))
    if str(sense).lower().startswith("max"):
        raw = max(0.0, bound_f - value_f)
    else:
        raw = max(0.0, value_f - bound_f)
    return raw / denominator


def make_bound_certificate(stages: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    normalized: List[Dict[str, Any]] = []
    maximum_gap = 0.0
    proven = True
    for stage in stages:
        row = dict(stage)
        gap = objective_gap(
            value=row.get("objective_value"),
            bound=row.get("best_objective_bound"),
            sense=str(row.get("sense", "maximize")),
        )
        row["relative_gap"] = None if gap is None else round(float(gap), 8)
        if gap is None:
            proven = False
        else:
            maximum_gap = max(maximum_gap, gap)
        if row.get("status") != "OPTIMAL":
            proven = False
        normalized.append(row)
    return {
        "stage_count": len(normalized),
        "all_stages_optimal": bool(proven),
        "maximum_relative_gap": round(float(maximum_gap), 8),
        "stages": normalized,
    }


def reward_from_quality_delta(
    *,
    candidate_class: str,
    target_gain: float,
    floor_gain: float,
    full_gain: float,
    exception_reduction: float,
    hard_failure_reduction: float,
    deficit_reduction: float,
    overage_reduction: float,
) -> float:
    class_bonus = {
        "compliant": 8.0,
        "exception": 2.0,
        "near_feasible": 1.0,
        "rejected": -2.0,
    }.get(str(candidate_class), -1.0)
    reward = (
        class_bonus
        + 2.5 * float(target_gain)
        + 1.4 * float(floor_gain)
        + 0.4 * float(full_gain)
        + 5.0 * float(exception_reduction)
        + 6.0 * float(hard_failure_reduction)
        + 0.02 * float(deficit_reduction)
        + 0.5 * float(overage_reduction)
    )
    # Keep weight adaptation stable even when interval counts are large.
    return max(-8.0, min(20.0, reward / 10.0))
