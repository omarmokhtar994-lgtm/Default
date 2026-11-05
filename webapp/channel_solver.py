# © 2026 Omar Mokhtar. All rights reserved.
"""Keep a native CP-SAT crash outside the web server, with the same model and limits.

Only the solver runs in a fresh child. Its private temporary files are removed
after every result, crash or timeout. No pickle or public worker endpoint is used.
"""
from __future__ import annotations

import json
import logging
import math
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ortools.sat.python import cp_model

log = logging.getLogger(__name__)
STARTUP_GRACE = 15.0
STOPPED = "Channel planning stopped unexpectedly. Please try again."


class SolverStopped(RuntimeError):
    """The child failed without returning a complete solver result."""


@dataclass(frozen=True)
class Solution:
    status: int
    status_name: str
    values: list[int]
    parameters: str

    def value(self, variable) -> int:
        index = variable.Index()
        return self.values[index] if index >= 0 else 1 - self.values[-index - 1]


def _command(request: Path, response: Path) -> list[str]:
    return [sys.executable, "-X", "faulthandler", "-m", "webapp.channel_solver", "--worker",
            str(request), str(response)]


def solve(model: cp_model.CpModel, settings: dict) -> Solution:
    """Solve in a bounded child; exceptions never become a fabricated solution."""
    limit = float(settings.get("max_time_in_seconds", 10.0))
    if not math.isfinite(limit) or limit <= 0:
        raise ValueError("Channel solver needs a finite, positive time limit.")
    parameters = cp_model.CpSolver().parameters
    for key, value in settings.items():
        setattr(parameters, key, value)
    with tempfile.TemporaryDirectory(prefix="scheduler-channel-") as folder:
        root = Path(folder)
        request, response = root / "request.json", root / "response.json"
        request.write_text(json.dumps({"model": str(model.Proto()), "parameters": str(parameters)}))
        try:
            with (root / "worker.log").open("w+") as output:
                child = subprocess.run(_command(request, response), cwd=Path(__file__).resolve().parent.parent,
                                       stdout=output, stderr=subprocess.STDOUT, timeout=limit + STARTUP_GRACE)
                if child.returncode:
                    output.seek(0)
                    log.error("Channel solver child exited %s: %s", child.returncode, output.read()[-4000:])
                    raise SolverStopped(STOPPED)
        except subprocess.TimeoutExpired as exc:
            # subprocess.run kills and waits for its child before raising.
            log.error("Channel solver child exceeded %.1f seconds and was reaped", limit + STARTUP_GRACE)
            raise SolverStopped("Channel planning did not finish in the time allowed. Please try again.") from exc
        except OSError as exc:
            log.error("Channel solver child could not start: %s", exc)
            raise SolverStopped(STOPPED) from exc
        try:
            data = json.loads(response.read_text())
            status, values = data["status"], data["values"]
            if type(status) is not int or status not in (0, 1, 2, 3, 4):
                raise ValueError("unknown solver status")
            if data["status_name"] != cp_model.CpSolverStatus(status).name:
                raise ValueError("inconsistent solver status")
            if data["parameters"] != str(parameters):
                raise ValueError("solver parameters changed")
            if not isinstance(values, list) or any(type(value) is not int for value in values):
                raise ValueError("invalid solver values")
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                if len(values) != len(model.Proto().variables):
                    raise ValueError("incomplete solver values")
            elif values:
                raise ValueError("values without a feasible solution")
            return Solution(status, data["status_name"], values, data["parameters"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            log.error("Channel solver child returned an invalid answer: %s", exc)
            raise SolverStopped(STOPPED) from exc


def _worker(request: Path, response: Path) -> None:
    data = json.loads(request.read_text())
    model = cp_model.CpModel()
    if not model.Proto().parse_text_format(data["model"]):
        raise ValueError("Cannot parse the channel model.")
    solver = cp_model.CpSolver()
    if not solver.parameters.parse_text_format(data["parameters"]):
        raise ValueError("Cannot parse the channel solver parameters.")
    status = solver.Solve(model)
    values = list(solver.ResponseProto().solution) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else []
    response.write_text(json.dumps({"status": int(status), "status_name": solver.StatusName(status),
                                    "values": values, "parameters": str(solver.parameters)}))


if __name__ == "__main__":
    if len(sys.argv) != 4 or sys.argv[1] != "--worker":
        raise SystemExit("This is the channel planner's internal worker.")
    _worker(Path(sys.argv[2]), Path(sys.argv[3]))
