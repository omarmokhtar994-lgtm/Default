# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BO, exploratory (not decision evidence): when, inside its time limit, the channel planner's solves find their last better plan.
The child solver is replaced by an in-process solve with a callback that notes each better plan's time and objective.
    python evidence/phase_bo/channel_improvement_times.py [scenario ...]"""
import sys, time
sys.path.insert(0, ".")
sys.path.insert(0, "tools")
from ortools.sat.python import cp_model
from webapp import channel_plan, channel_solver
import channel_scenarios as S

LOG = []


class Note(cp_model.CpSolverSolutionCallback):
    def __init__(self):
        super().__init__()
        self.began, self.seen = time.time(), []

    def on_solution_callback(self):
        self.seen.append((round(time.time() - self.began, 1), self.ObjectiveValue()))


def solve(model, settings):
    solver = cp_model.CpSolver()
    for k, v in settings.items():
        setattr(solver.parameters, k, v)
    note = Note()
    began = time.time()
    status = solver.Solve(model, note)
    took = round(time.time() - began, 1)
    last = note.seen[-1][0] if note.seen else None
    near = next((t for t, o in note.seen if note.seen and abs(o - note.seen[-1][1]) <= 0.01 * max(1.0, abs(note.seen[-1][1]))), None)
    LOG.append({"limit": settings.get("max_time_in_seconds"), "took": took, "status": solver.StatusName(status), "solutions": len(note.seen),
                "last_better_at": last, "within_1pct_at": near})
    values = list(solver.ResponseProto().solution) if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else []
    return channel_solver.Solution(int(status), solver.StatusName(status), values, str(solver.parameters))


channel_plan.solve_channels = solve
for name in (sys.argv[1:] or ["base_16", "large_30"]):
    people, config = S.SCENARIOS[name]()
    config["rules"] = dict(config["rules"], fair=True, consistent=True, balanced=False)
    carry = {}
    for d in (1, 2):
        LOG.clear()
        plan = channel_plan.plan_day(people, config, S.RULES, d, carry=carry, move_breaks=True)
        for row in LOG:
            print(name, "day", d, row, flush=True)
