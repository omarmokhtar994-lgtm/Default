# © 2026 Omar Mokhtar. All rights reserved.
"""Queue position and start estimates for the run queue.

A run's expected length is the median of this server's last five finished
runs of the same mode once there are at least two; until then it follows the
runner's own plan: each mode's seeds (1-hour searches) run side by side, two
cores per search, in rounds, plus about ten minutes to export and validate.
Every estimate says which basis it used. When the installed package has not
passed its safety gate yet, the next run to start spends about 30 minutes on
it first.
"""
from __future__ import annotations

import math
import statistics
from typing import Dict, List

SEEDS = {"SMOKE": 1, "QUICK": 2, "DEEP": 4, "OVERNIGHT": 6}
ROUND_MINUTES = {"SMOKE": 15}
DEFAULT_ROUND_MINUTES = 60
EXPORT_MINUTES = 10
GATE_MINUTES = 30
MIN_REMAINING = 5
ACTIVE = ("GATE", "RUNNING", "SCORING")
FINISHED_OK = ("DONE", "REVIEW")


def plan_minutes(mode: str, cpus: int) -> int:
    seeds = SEEDS.get(mode, 2)
    side_by_side = max(1, min(seeds, max(1, cpus) // 2))
    rounds = math.ceil(seeds / side_by_side)
    return rounds * ROUND_MINUTES.get(mode, DEFAULT_ROUND_MINUTES) + EXPORT_MINUTES


def expected_minutes(mode: str, cpus: int, history: List[float]) -> int:
    recent = list(history)[-5:]
    if len(recent) >= 2:
        return int(round(statistics.median(recent)))
    return plan_minutes(mode, cpus)


def _history(runs: List[dict]) -> Dict[str, List[float]]:
    out: Dict[str, List[float]] = {}
    for r in sorted(runs, key=lambda r: r.get("finished") or 0):
        if r["status"] in FINISHED_OK and r.get("started") and r.get("finished"):
            out.setdefault(r["mode"], []).append((r["finished"] - r["started"]) / 60.0)
    return out


def _basis(mode: str, history: Dict[str, List[float]], cpus: int) -> str:
    recent = history.get(mode, [])[-5:]
    if len(recent) >= 2:
        return f"based on the last {len(recent)} {mode.lower()} runs on this server"
    seeds = SEEDS.get(mode, 2)
    return f"based on the run plan: {seeds} search{'es' if seeds > 1 else ''} of up to 1 h on {cpus} cores"


def queue_plan(runs: List[dict], now: float, cpus: int, gate_pending: bool) -> Dict[str, dict]:
    history = _history(runs)
    length = {mode: expected_minutes(mode, cpus, history.get(mode, [])) for mode in SEEDS}
    plan: Dict[str, dict] = {}
    cursor = 0.0
    ahead = 0
    gate_extra = GATE_MINUTES if gate_pending else 0
    for r in sorted((r for r in runs if r["status"] in ACTIVE), key=lambda r: r.get("started") or 0):
        elapsed = (now - (r.get("started") or now)) / 60.0
        expected = length.get(r["mode"], plan_minutes(r["mode"], cpus))
        if r["status"] == "GATE" and gate_pending:
            expected += GATE_MINUTES
            gate_extra = 0
        remaining = max(MIN_REMAINING, expected - elapsed)
        plan[r["id"]] = {"position": 0, "ahead": 0, "starts_in_min": 0, "starts_at": r.get("started") or now,
                         "finishes_in_min": int(round(remaining)), "basis": _basis(r["mode"], history, cpus)}
        cursor += remaining
        ahead += 1
    for position, r in enumerate(sorted((r for r in runs if r["status"] == "QUEUED"),
                                        key=lambda r: r.get("created") or 0), start=1):
        own = length.get(r["mode"], plan_minutes(r["mode"], cpus)) + gate_extra
        gate_extra = 0
        plan[r["id"]] = {"position": position, "ahead": ahead, "starts_in_min": int(round(cursor)),
                         "starts_at": now + round(cursor) * 60, "finishes_in_min": int(round(cursor + own)),
                         "basis": _basis(r["mode"], history, cpus)}
        cursor += own
        ahead += 1
    return plan
