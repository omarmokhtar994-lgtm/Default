"""Valid upper bound on after-break target intervals (after_target) for a workbook.

Relaxation of the scheduling problem, keeping only rules no feasible schedule
can escape, so its optimum can only be >= the true best after_target:
  * per day, at most as many people work as are not on leave that day;
  * in total, each person works at most 5 - (leave days) days;
  * each working person has one shift and one individually legal break
    pattern (every pattern the engine's generator allows, not just the 115 per
    duration the search uses);
  * coverage and target hits use the engine's own exact formulas
    (scaled_effective_factor / scaled_coverage_threshold per interval,
    previous-Saturday carry-in), and week-boundary spill is credited cyclically
    AND nowhere removed (overcounting only loosens the bound).
Dropped (so the bound is loose, never invalid): rest gaps, OFF pairs and
preferences, shift variety, fixed assignments, languages, opening minimums,
break concurrency caps, blank-interval rules.

Check: the engine's own best schedule, expressed in these variables, must
score >= its reported after_target (printed as ENGINE_IN_MODEL).

usage: after_target_bound.py ENGINE WORKBOOK SECONDS WORKERS [CANDIDATE_POOL_JSON]
"""
import json, sys, time, importlib.util
from pathlib import Path

engine_file, wb, T, W = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
pool_path = sys.argv[5] if len(sys.argv) > 5 else None
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
from ortools.sat.python import cp_model

P = E.parse_input(wb)
qpi = P.qslots_per_interval
S = len(P.shifts)
pats = E.generate_break_patterns(P, limit_per_duration=10 ** 6)
by_dur = {}
for p in pats:
    by_dur.setdefault(p.duration_q, []).append(p)
leave = [[E.norm(a.preferences[d]) == "leave" for d in range(7)] for a in P.associates]
avail = [sum(1 for a in range(len(P.associates)) if not leave[a][d]) for d in range(7)]
person_days = sum(max(0, 5 - sum(leave[a])) for a in range(len(P.associates)))
carry = {q: len(E.prior_covering_associates(P, q)) for q in range(96)}
active = [(d, i) for d in range(7) for i in range(P.intervals_per_day) if P.active[d][i]]
print(f"{wb.name}: associates {len(P.associates)}, shifts {S}, patterns {len(pats)} "
      f"(durations {sorted(by_dur)}), active intervals {len(active)}, person-days <= {person_days}", flush=True)


def cover_terms(d, s, p):
    start = d * 96 + P.shifts[s].start_min // 15
    for off in range(P.shifts[s].duration_q):
        if off in p.broken_offsets:
            continue
        yield (start + off) % 672


def hits_of(on):
    total = 0
    for d, i in active:
        qs = range(d * 96 + i * qpi, d * 96 + i * qpi + qpi)
        cov = sum(on.get(q, 0) for q in qs)
        if E.scaled_effective_factor(P.shrinkage[d][i]) * cov >= E.scaled_coverage_threshold(P.requirements[d][i] or 0.0, P.target_ratio, qpi):
            total += 1
    return total


engine_counts = {}
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
    on = dict(carry)
    for a, d, si in E.scheduled_cells(sk):
        p = by_id.get(br.selected_pattern.get((a, d)))
        # map the engine pattern to the full-generator pattern with the same breaks
        match = next((x for x in by_dur.get(P.shifts[si].duration_q, [])
                      if p is not None and x.broken_offsets == p.broken_offsets), None)
        if match is None:
            print("WARNING engine pattern not in full set", flush=True)
            continue
        engine_counts[(d, si, match.index)] = engine_counts.get((d, si, match.index), 0) + 1
        for q in cover_terms(d, si, match):
            on[q] = on.get(q, 0) + 1
    print(f"ENGINE after_target {m['after_target']}; ENGINE_IN_MODEL {hits_of(on)}", flush=True)

model = cp_model.CpModel()
n = {}
for d in range(7):
    for s in range(S):
        for p in by_dur.get(P.shifts[s].duration_q, []):
            n[d, s, p.index] = model.NewIntVar(0, avail[d], f"n_{d}_{s}_{p.index}")
for d in range(7):
    model.Add(sum(v for (dd, _, _), v in n.items() if dd == d) <= avail[d])
model.Add(sum(n.values()) <= person_days)
on_terms = {}
pat_by_index = {p.index: p for p in pats}
for (d, s, pi), v in n.items():
    for q in cover_terms(d, s, pat_by_index[pi]):
        on_terms.setdefault(q, []).append(v)
hits = []
for d, i in active:
    qs = range(d * 96 + i * qpi, d * 96 + i * qpi + qpi)
    cov = sum(sum(on_terms.get(q, [])) + carry.get(q, 0) for q in qs)
    h = model.NewBoolVar(f"h_{d}_{i}")
    model.Add(E.scaled_effective_factor(P.shrinkage[d][i]) * cov
              >= E.scaled_coverage_threshold(P.requirements[d][i] or 0.0, P.target_ratio, qpi)).OnlyEnforceIf(h)
    hits.append(h)
model.Maximize(sum(hits))
for key, v in n.items():
    model.AddHint(v, engine_counts.get(key, 0))
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = T
solver.parameters.num_search_workers = W
t = time.time()
st = solver.Solve(model)
print(json.dumps({"workbook": wb.name, "status": solver.StatusName(st), "best_relaxed_solution": solver.ObjectiveValue(),
                  "UPPER_BOUND_after_target": solver.BestObjectiveBound(), "active_intervals": len(active),
                  "seconds": round(time.time() - t, 1)}), flush=True)
