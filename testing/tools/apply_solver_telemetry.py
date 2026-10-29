#!/usr/bin/env python3
"""Capture the telemetry CP-SAT already produces, which the engine throws away.

WHY THIS EXISTS

Every performance question asked of this engine has been unanswerable, because
all three solver call sites set `log_search_progress = False` and the diagnostic
dicts keep only four numbers. Two specific losses:

1. `best_objective_bound` is recorded ONLY when the status is OPTIMAL or
   FEASIBLE. On UNKNOWN it is written as None -- discarding it in exactly the
   case where it says the most (how close the search got before its slice ran
   out), and where a stop-at-the-bound rule would need it. Verified against
   ortools 9.15.6755: the bound IS populated and meaningful on UNKNOWN.

2. `deterministic_time` is never read. It measures search effort in a way that
   does NOT move with machine load, unlike wall_time. On a wall-clock-budgeted
   solver running on a contended box, it is the only honest way to say whether
   two runs did the same amount of work -- the exact confound that has dogged
   every comparison in this review.

WHAT THIS CHANGE IS NOT

Observation only. Every value captured is a field the solver filled in as a
side effect of solving; reading it back costs no solver time. This applier sets
no solver parameter, and in particular does NOT enable `log_search_progress`:
logging costs wall clock, and on a wall-clock-budgeted solve that would change
results. Full log capture is left to a separate opt-in change.

The existing `best_objective_bound` key keeps its current semantics untouched,
because solve_breaks consumes it to derive `exception_lower_bound`. The new
data lands under a new `solver_telemetry` key. Purely additive.

Usage:  apply_solver_telemetry.py <engine_tree>   [--check]
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

HELPER = '''

def capture_solver_telemetry(
    cp_model: Any, solver: Any, status: int,
    granted_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    """Read back what the solve already computed. Costs no solver time.

    OBSERVATION ONLY -- nothing here may set a solver parameter or alter search.

    Two fields matter most and neither was previously recorded:

    * `best_objective_bound` is captured UNCONDITIONALLY. The engine's older
      diagnostics kept it only on OPTIMAL/FEASIBLE, which discards it on
      UNKNOWN -- precisely when it carries the most information, and precisely
      the number a stop-at-the-bound rule needs.
    * `deterministic_time` measures search effort independently of machine
      load. Two runs that disagree on wall_time but agree on deterministic_time
      performed the same search; that distinction is not recoverable from
      wall_time alone on a contended box.

    `branches_per_conflict` is a learning-health signal: a large ratio means the
    search is enumerating rather than learning from conflicts, which is what a
    badly conditioned objective or weak propagation produces.
    """
    def _get(name: str, default: Any = None) -> Any:
        try:
            value = getattr(solver, name)
            return value() if callable(value) else value
        except Exception:
            return default

    response = None
    try:
        response = solver.ResponseProto()
    except Exception:
        response = None

    def _resp(name: str, default: Any = None) -> Any:
        if response is None:
            return default
        try:
            return getattr(response, name)
        except Exception:
            return default

    has_solution = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    bound = None
    try:
        raw_bound = solver.BestObjectiveBound()
        bound = float(raw_bound) if raw_bound is not None else None
    except Exception:
        bound = None

    objective = None
    if has_solution:
        try:
            objective = float(solver.ObjectiveValue())
        except Exception:
            objective = None

    conflicts = _get("NumConflicts", 0) or 0
    branches = _get("NumBranches", 0) or 0
    wall = _get("WallTime", None)

    telemetry: Dict[str, Any] = {
        "status": status_name(cp_model, solver, status),
        "has_solution": bool(has_solution),
        "best_objective_bound": bound,
        "objective_value": objective,
        "wall_time_sec": wall,
        "user_time_sec": _get("UserTime", None),
        "deterministic_time": _resp("deterministic_time", None),
        "num_conflicts": conflicts,
        "num_branches": branches,
        "num_booleans": _get("NumBooleans", None),
        "num_integers": _resp("num_integers", None),
        "num_restarts": _resp("num_restarts", None),
        "num_lp_iterations": _resp("num_lp_iterations", None),
        "num_fixed_booleans": _resp("num_fixed_booleans", None),
        "gap_integral": _resp("gap_integral", None),
        "solution_info": _get("SolutionInfo", None),
        "granted_seconds": granted_seconds,
    }

    if objective is not None and bound is not None:
        telemetry["absolute_gap"] = abs(objective - bound)

    if conflicts:
        telemetry["branches_per_conflict"] = round(float(branches) / float(conflicts), 1)
    else:
        telemetry["branches_per_conflict"] = None

    if granted_seconds and wall:
        try:
            telemetry["slice_utilisation"] = round(float(wall) / float(granted_seconds), 3)
        except Exception:
            pass

    return telemetry

'''

# (site marker, solver variable, granted-seconds expression)
SITES = [
    ('"conflicts": solver.NumConflicts(), "branches": solver.NumBranches(), "wall_time": solver.WallTime(),',
     "solver", "time_limit"),
    ('"wall_time": solver.WallTime(),', "solver", "time_limit"),
]


def apply(tree: Path, check_only: bool = False) -> int:
    target = tree / "engine" / "_tools" / "l632_universal_scheduler.py"
    src = target.read_text()

    if "def capture_solver_telemetry(" in src:
        print("ALREADY APPLIED")
        return 0

    anchor = '        }.get(status, str(status))\n'
    if src.count(anchor) != 1:
        print(f"FAIL: helper anchor found {src.count(anchor)} times, expected 1")
        return 1
    src = src.replace(anchor, anchor + HELPER, 1)

    # Attach telemetry to every diagnostic dict that records wall_time.
    patched = 0
    out_lines = []
    for line in src.split("\n"):
        stripped = line.strip()
        if stripped.endswith('"wall_time": solver.WallTime(),') or stripped == '"wall_time": solver.WallTime(),':
            indent = line[: len(line) - len(line.lstrip())]
            out_lines.append(line)
            out_lines.append(
                f'{indent}"solver_telemetry": capture_solver_telemetry('
                f'cp_model, solver, status, float(time_limit)),'
            )
            patched += 1
        else:
            out_lines.append(line)
    src = "\n".join(out_lines)

    if patched != 3:
        print(f"FAIL: patched {patched} diagnostic sites, expected 3")
        return 1

    if check_only:
        print(f"WOULD PATCH: helper + {patched} sites")
        return 0

    target.write_text(src)
    print(f"APPLIED: helper + {patched} diagnostic sites -> {target}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(apply(Path(args[0]), check_only="--check" in sys.argv))
