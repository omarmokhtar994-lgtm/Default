"""Real-model equivalence: Chat's joint refinement, deterministic solves
(1 worker, deterministic time limit), isolation OFF vs ON. Every returned
candidate and every solve's status/objective/bound must be identical."""
import sys, json, glob, io, time, importlib.util, hashlib
from pathlib import Path
eng, run_dir = sys.argv[1], Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("E", eng); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(eng).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
orig_limits = E.configure_solver_limits
solves = []
def deterministic_limits(solver):
    applied = orig_limits(solver)
    solver.parameters.num_search_workers = 1
    solver.parameters.max_deterministic_time = float(sys.argv[6])
    solver.parameters.max_time_in_seconds = 3600.0
    return applied
E.configure_solver_limits = deterministic_limits
cp_model = E.import_cp_sat()
base_cls = cp_model.CpSolver
P = E.parse_input(next(iter(glob.glob(str(run_dir / "input_snapshot" / "*.xlsx")))))
pool = json.load(open(run_dir / "debug" / "CANDIDATE_POOL_CHECKPOINT.json"))
cands = [E.deserialize_break_candidate(P, r) for r in pool["compliant"]]
for sk, br in cands:
    br.metrics = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
best_before = max((sk for sk, _ in cands), key=lambda s: (E.ensure_before_break_metrics(P, s) or {}).get("before_target", 0))

def arm(enabled):
    E.JOINT_SOLVE_ISOLATION_ENABLED = enabled
    rows = []
    real = E.isolated_cp_solve
    def spy(solver, model, fn, rt, cb=None):
        st = real(solver, model, fn, rt, cb)
        r = solver.response_proto
        rows.append((solver.StatusName(st), r.objective_value, r.best_objective_bound,
                     hashlib.sha256(str(list(r.solution)).encode()).hexdigest()[:16], r.num_branches, r.num_conflicts,
                     solver.isolation_record["mode"]))
        return st
    E.isolated_cp_solve = spy
    try:
        added, recs, ex = E.run_adaptive_decomposed_joint_optimizer(
            P, cands, best_before, 115, time.time() + 20000, 1, io.StringIO(), 9000,
            base_shift_options_per_cell=int(sys.argv[3]), base_patterns_per_shift=int(sys.argv[4]), maximum_attempts=int(sys.argv[5]), no_improvement_limit=int(sys.argv[5]),
            protected_target_tolerance=1, operational_exception_cap=E.operational_no_break_exception_cap(P))
    finally:
        E.isolated_cp_solve = real
    out = [(br.profile, hashlib.sha256(json.dumps(sorted((str(k), v) for k, v in br.selected_pattern.items())).encode()).hexdigest()[:16],
            br.metrics.get("after_target")) for _, br in added]
    return rows, out, {k: ex.get(k) for k in ("attempted", "accepted", "improved")}
off = arm(False); print("OFF", json.dumps(off), flush=True)
on = arm(True); print("ON ", json.dumps(on), flush=True)
same_solves = [a[:6] == b[:6] for a, b in zip(off[0], on[0])]
print("modes OFF", sorted({r[6] for r in off[0]}), "ON", sorted({r[6] for r in on[0]}))
print("IDENTICAL" if (len(off[0]) == len(on[0]) and all(same_solves) and off[1] == on[1] and off[2] == on[2]) else "DIFFERENT",
      f"{len(off[0])} solves", flush=True)
searched = sum(1 for r in off[0] if r[0] in ("OPTIMAL", "FEASIBLE") or r[4] > 0)
print(f"non-trivial solves (found a solution or branched): {searched}/{len(off[0])}", flush=True)
