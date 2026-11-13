# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL A/B helper: the Stage 1 model one engine file builds for one workbook, as a hash.

    python ab_model_hash.py ENGINE_TOOLS_DIR WORKBOOK [WORKBOOK ...]

Prints one line per workbook: the workbook name, the number of associates and shifts, and the SHA-256 of the CP-SAT model that
``build_skeleton`` is about to solve (seed 9000, default hard rules). The solve itself is stopped before it starts, so the
result is exact and does not depend on solver timing: the same hash means the same model, so the same schedule."""
import hashlib
import io
import sys
from pathlib import Path

tools, workbooks = Path(sys.argv[1]), sys.argv[2:]
sys.path.insert(0, str(tools))
import l632_universal_scheduler as E  # noqa: E402
from ortools.sat.python import cp_model  # noqa: E402


class Stop(Exception):
    pass


def capture(self, model, *args, **kwargs):
    raise Stop(hashlib.sha256(str(model.Proto()).encode()).hexdigest())


cp_model.CpSolver.Solve = capture
for path in workbooks:
    parsed = E.parse_input(path)
    try:
        E.build_skeleton(parsed, None, E.HardConfig(), 5.0, 1, io.StringIO(), random_seed=9000)
        digest = "NO_SOLVE_REACHED"
    except Stop as stop:
        digest = str(stop)
    print(f"{Path(path).name}\t{len(parsed.associates)}\t{len(parsed.shifts)}\t{digest}")
