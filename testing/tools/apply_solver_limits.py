#!/usr/bin/env python3
"""Two native CP-SAT limits the engine never sets: memory, and a gap stop.

WHY

1. MEMORY. `max_memory_in_mb` defaults to 10000 in ortools 9.15.6755 and the
   engine never touches it. A 3600s AE_AR_B2B run was OOM-killed by the cgroup
   at 7.76 GB resident while CP-SAT was still happily heading for its own 10 GB
   ceiling. Telling the solver about the real budget lets it bound itself rather
   than be killed, and a bounded solve still returns its incumbent.

   HONEST CAVEAT: OR-Tools issue #1944 reports that max_memory_in_mb is not
   enforced reliably in all cases. This is a mitigation, not a guarantee, and
   it is documented as such rather than sold as a fix.

2. GAP STOP. Measured on AE_FR_Choice, a Stage-1 solve sat at

       objective 26211272, bound 26211120, gap 152  (0.00058% relative)

   and still consumed 100% of its 45-second slice. `relative_gap_limit` is
   CP-SAT's own termination criterion for exactly this. Because phase deadlines
   are cumulative, seconds returned here flow forward to break search rather
   than being lost, so this is a quality lever as much as a speed one.

DEFAULTS ARE DELIBERATELY INERT

`relative_gap_limit` defaults to 0.0, which is CP-SAT's own default and means
"no gap stop" -- identical behaviour to today. It has to be opted into, then
A/B'd, before any default changes. Nothing here silently alters a schedule.

The memory limit defaults to None (unset) for the same reason; the runner may
pass a value derived from the host.

These are termination limits, not search strategy. The CP-SAT primer warns
against changing top-level parameters because it perturbs the subsolver
portfolio (including LNS workers); limits do not select or configure
subsolvers, so that warning does not apply here.

Usage:  apply_solver_limits.py <engine_tree> [--check]
"""
from __future__ import annotations
import sys
from pathlib import Path

HELPER = '''

SOLVER_MAX_MEMORY_MB: Optional[int] = None
SOLVER_RELATIVE_GAP_LIMIT: float = 0.0


def configure_solver_limits(solver: Any) -> Dict[str, Any]:
    """Apply the two native CP-SAT limits the engine otherwise leaves at default.

    Returns what was actually applied, so the audit records it rather than
    leaving the reader to guess which limits were in force.

    Both limits are termination criteria. Neither selects a subsolver nor
    changes search strategy, so neither disturbs the worker portfolio.

    max_memory_in_mb: CP-SAT's own default is 10000 MB, which is larger than
    many container budgets -- the solver aims for a ceiling above the one that
    will actually kill it. Note OR-Tools issue #1944: enforcement is imperfect,
    so this reduces OOM risk without eliminating it.

    relative_gap_limit: 0.0 is CP-SAT's default and means no gap stop. Any
    positive value stops the solve once the incumbent is provably within that
    relative distance of optimal, returning the remaining slice to later phases
    through the cumulative deadline chain.
    """
    applied: Dict[str, Any] = {
        "max_memory_in_mb": None,
        "relative_gap_limit": None,
    }

    if SOLVER_MAX_MEMORY_MB:
        try:
            solver.parameters.max_memory_in_mb = int(SOLVER_MAX_MEMORY_MB)
            applied["max_memory_in_mb"] = int(SOLVER_MAX_MEMORY_MB)
        except Exception:
            applied["max_memory_in_mb"] = "UNSUPPORTED"

    if SOLVER_RELATIVE_GAP_LIMIT and float(SOLVER_RELATIVE_GAP_LIMIT) > 0.0:
        try:
            solver.parameters.relative_gap_limit = float(SOLVER_RELATIVE_GAP_LIMIT)
            applied["relative_gap_limit"] = float(SOLVER_RELATIVE_GAP_LIMIT)
        except Exception:
            applied["relative_gap_limit"] = "UNSUPPORTED"

    return applied

'''

ANCHOR = "    solver.parameters.log_search_progress = False\n"
STAGE_ANCHOR = "        stage_solver.parameters.log_search_progress = False\n"


def apply(tree: Path, check_only: bool = False) -> int:
    target = tree / "engine" / "_tools" / "l632_universal_scheduler.py"
    src = target.read_text()

    if "def configure_solver_limits(" in src:
        print("ALREADY APPLIED")
        return 0

    helper_anchor = "        }.get(status, str(status))\n"
    if src.count(helper_anchor) != 1:
        print(f"FAIL: helper anchor x{src.count(helper_anchor)}, expected 1")
        return 1
    src = src.replace(helper_anchor, helper_anchor + HELPER, 1)

    n_solver = src.count(ANCHOR)
    n_stage = src.count(STAGE_ANCHOR)
    if n_solver + n_stage != 3:
        print(f"FAIL: found {n_solver} solver + {n_stage} stage_solver config sites, expected 3 total")
        return 1

    src = src.replace(
        ANCHOR,
        ANCHOR + '    _solver_limits_applied = configure_solver_limits(solver)\n',
    )
    src = src.replace(
        STAGE_ANCHOR,
        STAGE_ANCHOR + '        _solver_limits_applied = configure_solver_limits(stage_solver)\n',
    )

    if check_only:
        print(f"WOULD PATCH: helper + {n_solver + n_stage} sites")
        return 0

    target.write_text(src)
    print(f"APPLIED: helper + {n_solver} solver + {n_stage} stage_solver sites -> {target}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(apply(Path(args[0]), check_only="--check" in sys.argv))
