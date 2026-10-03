"""Audit F-33: how many Stage-2 constraints the in-place expression corruption changed.

For every saved final schedule under argv[1] (input snapshot + published
workbook), rebuild the shift skeleton, build the Stage-2 break model with the
Phase B engine (argv[2]) and with the current engine, and compare the two
models constraint by constraint after canonicalising each linear constraint
(sorted (variable name, coefficient) terms, domain, enforcement literals).
Writes argv[3]."""
import glob, importlib.util, io, json, sys
from pathlib import Path

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod

sys.path.insert(0, 'engine/_tools')
NEW = load('engine/_tools/l632_universal_scheduler.py', 'eng_new')
OLD = load(sys.argv[2] + '/engine/_tools/l632_universal_scheduler.py', 'eng_old')
IV = load('engine/tools/independent_validator.py', 'iv_f33')
import ortools.sat.python.cp_model as cp

def capture(E, parsed, sk):
    got = []
    old = cp.CpSolver.solve
    def solve(self, model, *a, **k):
        got.append(model.clone()); self.parameters.max_time_in_seconds = 0.5
        return old(self, model, *a, **k)
    cp.CpSolver.solve = solve
    try:
        E.solve_breaks(parsed, sk, 24, False, 1, 1, io.StringIO())
    finally:
        cp.CpSolver.solve = old
    m = got[0]
    names = [v.name for v in m.proto.variables]
    rows = []
    for c in m.proto.constraints:
        if c.has_linear():
            terms = tuple(sorted((names[v], int(k)) for v, k in zip(c.linear.vars, c.linear.coeffs)))
            rows.append((terms, tuple(c.linear.domain), tuple(names[e] for e in c.enforcement_literal)))
        else:
            rows.append(('other', str(c)[:200]))
    return rows

out = []
roots = sorted({Path(p).parent.parent for p in glob.glob(sys.argv[1] + '/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True)})
for root in roots:
    if any(x in str(root) for x in ('PRODUCTION_PACKAGE', '/pkg', '/chk/', '/colab/')):
        continue
    inp = sorted((root / 'input_snapshot').glob('*.xlsx')); outp = sorted((root / 'production').glob('*BEST_FINAL*.xlsx'))
    if not (inp and outp):
        continue
    row = {"case": str(root).split('scratchpad/')[-1]}
    try:
        res = {}
        for tag, E in (("old", OLD), ("new", NEW)):
            parsed = E.parse_input(inp[0])
            names = [a.name for a in parsed.associates]
            sched, _ = IV.parse_output_schedule(outp[0], names)
            idx = {E.norm(s.label): s.index for s in parsed.shifts}
            assignment, selected = [], []
            for a in parsed.associates:
                cells = sched[E.norm(a.name)]
                assignment.append(["OFF" if E.norm(v) == "off" else "Leave" if E.norm(v) in ("leave", "pto", "vacation") else v for v in cells])
                selected.append([idx.get(E.norm(v)) for v in cells])
            sk = E.SkeletonSolution("replay", "FEASIBLE", 0.0, 0.0, assignment, selected, {})
            E.ensure_before_break_metrics(parsed, sk)
            res[tag] = capture(E, parsed, sk)
        a, b = res["old"], res["new"]
        from collections import Counter
        ca, cb = Counter(a), Counter(b)
        row.update(constraints_old=len(a), constraints_new=len(b),
                   differing=sum((ca - cb).values()), only_new=sum((cb - ca).values()),
                   corrupted_examples=[str(x)[:240] for x in list((ca - cb).elements())[:3]])
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
    out.append(row); print(json.dumps(row)[:400], flush=True)
json.dump(out, open(sys.argv[3], 'w'), indent=1)
