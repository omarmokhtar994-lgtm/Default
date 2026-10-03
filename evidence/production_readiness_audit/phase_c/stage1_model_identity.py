"""C1 rule R1 support: the normal Stage-1 model is unchanged.

Builds build_skeleton models (not solved: the solve is stopped at 0.1 s) with
the Phase B engine (argv[1]) and the current engine for every packaged and
real-run input workbook and three profiles (the hard probe and two search
profiles), and compares them constraint by constraint after canonicalising
each constraint (sorted terms by variable name, domain, enforcement), plus
the objective. Writes argv[2]."""
import glob, importlib.util, io, json, sys
from collections import Counter
from pathlib import Path

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod

sys.path.insert(0, 'engine/_tools')
NEW = load('engine/_tools/l632_universal_scheduler.py', 'eng_new')
OLD = load(sys.argv[1] + '/engine/_tools/l632_universal_scheduler.py', 'eng_old')
import ortools.sat.python.cp_model as cp

def canonical(m):
    names = [v.name for v in m.proto.variables]
    rows = []
    for c in m.proto.constraints:
        if c.has_linear():
            rows.append((tuple(sorted((names[v], int(k)) for v, k in zip(c.linear.vars, c.linear.coeffs))),
                         tuple(c.linear.domain), tuple(sorted(names[e] for e in c.enforcement_literal))))
        else:
            rows.append(('other', str(c)))
    obj = tuple(sorted((names[v], int(k)) for v, k in zip(m.proto.objective.vars, m.proto.objective.coeffs)))
    return Counter(rows), obj, len(names)

def build(E, parsed, profile_name):
    got = []
    old = cp.CpSolver.solve
    def solve(self, model, *a, **k):
        got.append(model.clone()); self.parameters.max_time_in_seconds = 0.1
        return old(self, model, *a, **k)
    cp.CpSolver.solve = solve
    try:
        profile = None if profile_name is None else E.skeleton_profiles([profile_name])[0]
        E.build_skeleton(parsed, profile, E.HardConfig(), 1, 1, io.StringIO())
    finally:
        cp.CpSolver.solve = old
    return canonical(got[0])

paths = sorted(set(glob.glob('packages/rc9_2_2_production/inputs/*.xlsx')) | set(glob.glob('fixtures/real_runs/**/*.xlsx', recursive=True)))
paths = [p for p in paths if 'SCHEDULE' not in p and 'CANDIDATE' not in p]
out = []
for p in paths:
    for prof in (None, "target_priority_balanced", "target90_restore_champion"):
        row = {"workbook": p, "profile": prof or "hard_probe"}
        try:
            a = build(OLD, OLD.parse_input(Path(p)), prof)
            b = build(NEW, NEW.parse_input(Path(p)), prof)
            row.update(constraints=sum(a[0].values()), variables_old=a[2], variables_new=b[2],
                       constraints_only_old=sum((a[0] - b[0]).values()),
                       constraints_only_new=sum((b[0] - a[0]).values()),
                       objective_identical=a[1] == b[1])
        except Exception as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"[:200]
        out.append(row); print(json.dumps(row), flush=True)
json.dump(out, open(sys.argv[2], 'w'), indent=1)
