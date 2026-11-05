"""Tighter-to-solve upper bound on after_target: aggregated break relaxation.

As after_target_bound.py (same kept rules, same exact coverage/threshold
formulas, cyclic week-boundary credit), but break patterns are replaced by
per-(day, shift) break counts per quarter: r[d,s,o] people of that cell on
break at shift offset o, with
  * r only at offsets some legal pattern of that duration can break at,
  * r[d,s,o] <= w[d,s] (nobody is on break twice at once),
  * sum_o r[d,s,o] >= w[d,s] * (fewest break quarters any legal pattern has).
Every real schedule maps into this model with the same or more coverage, so
its optimum bounds the true best after_target from above. ~50x fewer variables
than the pattern model, which is what lets the solver prove a bound.

usage: after_target_bound_v2.py ENGINE WORKBOOK SECONDS WORKERS [CANDIDATE_POOL_JSON]
"""
import json, sys, time, importlib.util
from pathlib import Path

engine_file, wb, T, W = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
pool_path = sys.argv[5] if len(sys.argv) > 5 else None
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
from ortools.sat.python import cp_model

P = E.parse_input(wb)
qpi, S, A = P.qslots_per_interval, len(P.shifts), len(P.associates)
pats = E.generate_break_patterns(P, limit_per_duration=10 ** 6)
eligible, min_breaks = {}, {}
for p in pats:
    eligible.setdefault(p.duration_q, set()).update(p.broken_offsets)
    min_breaks[p.duration_q] = min(min_breaks.get(p.duration_q, 10 ** 6), len(p.broken_offsets))
leave = [[E.norm(a.preferences[d]) == "leave" for d in range(7)] for a in P.associates]
avail = [sum(1 for a in range(A) if not leave[a][d]) for d in range(7)]
person_days = sum(max(0, 5 - sum(leave[a])) for a in range(A))
carry = {q: len(E.prior_covering_associates(P, q)) for q in range(96)}
active = [(d, i) for d in range(7) for i in range(P.intervals_per_day) if P.active[d][i]]
factor = {(d, i): E.scaled_effective_factor(P.shrinkage[d][i]) for d, i in active}
thresh = {(d, i): E.scaled_coverage_threshold(P.requirements[d][i] or 0.0, P.target_ratio, qpi) for d, i in active}
print(f"{wb.name}: associates {A}, shifts {S}, active intervals {len(active)}, person-days <= {person_days}, "
      f"min break quarters {min_breaks}", flush=True)


def qs_of(d, s):
    start = d * 96 + P.shifts[s].start_min // 15
    return [(o, (start + o) % 672) for o in range(P.shifts[s].duration_q)]


def hits_from(raw, brk):
    n = 0
    for d, i in active:
        cov = sum(raw.get(q, 0) - brk.get(q, 0) + carry.get(q, 0) for q in range(d * 96 + i * qpi, d * 96 + i * qpi + qpi))
        n += factor[d, i] * cov >= thresh[d, i]
    return n


hint_w, hint_r = {}, {}
if pool_path:
    pool = json.load(open(pool_path))
    best = None
    for row in pool["compliant"]:
        sk, br = E.deserialize_break_candidate(P, row)
        m = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
        if best is None or m["after_target"] > best[2]["after_target"]:
            best = (sk, br, m)
    sk, br, m = best
    by_id = E.pattern_map(br.patterns)
    raw, brk = {}, {}
    for a, d, si in E.scheduled_cells(sk):
        hint_w[d, si] = hint_w.get((d, si), 0) + 1
        broken = by_id[br.selected_pattern[(a, d)]].broken_offsets if br.selected_pattern.get((a, d)) in by_id else set()
        for o, q in qs_of(d, si):
            raw[q] = raw.get(q, 0) + 1
            if o in broken:
                brk[q] = brk.get(q, 0) + 1
                hint_r[d, si, o] = hint_r.get((d, si, o), 0) + 1
    print(f"ENGINE after_target {m['after_target']}; ENGINE_IN_MODEL {hits_from(raw, brk)}", flush=True)

model = cp_model.CpModel()
w, r = {}, {}
raw_terms, brk_terms = {}, {}
for d in range(7):
    for s in range(S):
        dur = P.shifts[s].duration_q
        if dur not in eligible:
            continue
        w[d, s] = model.NewIntVar(0, avail[d], f"w_{d}_{s}")
        cell_r = []
        for o, q in qs_of(d, s):
            raw_terms.setdefault(q, []).append(w[d, s])
            if o in eligible[dur]:
                r[d, s, o] = model.NewIntVar(0, avail[d], f"r_{d}_{s}_{o}")
                model.Add(r[d, s, o] <= w[d, s])
                brk_terms.setdefault(q, []).append(r[d, s, o])
                cell_r.append(r[d, s, o])
        model.Add(sum(cell_r) >= min_breaks[dur] * w[d, s])
for d in range(7):
    model.Add(sum(v for (dd, _), v in w.items() if dd == d) <= avail[d])
model.Add(sum(w.values()) <= person_days)
hits = []
for d, i in active:
    qs = range(d * 96 + i * qpi, d * 96 + i * qpi + qpi)
    cov = sum(sum(raw_terms.get(q, [])) - sum(brk_terms.get(q, [])) + carry.get(q, 0) for q in qs)
    h = model.NewBoolVar(f"h_{d}_{i}")
    model.Add(factor[d, i] * cov >= thresh[d, i]).OnlyEnforceIf(h)
    hits.append(h)
model.Maximize(sum(hits))
for k, v in w.items():
    model.AddHint(v, hint_w.get(k, 0))
for k, v in r.items():
    model.AddHint(v, hint_r.get(k, 0))
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = T
solver.parameters.num_search_workers = W
solver.parameters.linearization_level = 2
t = time.time()
st = solver.Solve(model)
print(json.dumps({"workbook": wb.name, "status": solver.StatusName(st), "best_relaxed_solution": solver.ObjectiveValue(),
                  "UPPER_BOUND_after_target": solver.BestObjectiveBound(), "active_intervals": len(active),
                  "vars": len(w) + len(r), "seconds": round(time.time() - t, 1)}), flush=True)
