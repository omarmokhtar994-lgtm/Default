"""Prototype: joint shift+break tours by column generation, then an exact integer
selection. Standalone; scores with the engine's own metric."""
import sys, time, math, itertools, importlib.util
from pathlib import Path
from ortools.linear_solver import pywraplp
from ortools.sat.python import cp_model

engine_file, wb = sys.argv[1], sys.argv[2]
T_IP = float(sys.argv[3]) if len(sys.argv) > 3 else 120
W = int(sys.argv[4]) if len(sys.argv) > 4 else 4
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
P = E.parse_input(Path(wb))
t0 = time.time()
A, S, qpi = len(P.associates), len(P.shifts), P.qslots_per_interval
pats = E.generate_break_patterns(P)
by_dur = {}
for p in pats: by_dur.setdefault(p.duration_q, []).append(p)
H = 8 * 96  # quarters incl. next-Sunday spill

def key_of(q):
    if q >= 7 * 96: return None
    return (q // 96, (q % 96) // qpi)

active = {(d, i) for d in range(7) for i in range(P.intervals_per_day) if P.active[d][i]}
eff = {k: 1 - float(P.shrinkage[k[0]][k[1]] or 0) for k in active}
need = {k: float(P.requirements[k[0]][k[1]] or 0) * P.target_ratio for k in active}

# ---- day options: (shift, pattern) with their per-interval productive FTE and quarter footprints
day_opts = {}   # (d, s) -> list of (pattern_index, contrib{interval: fte}, onq set, rawq set)
for d in range(7):
    for s, sh in enumerate(P.shifts):
        st = d * 96 + sh.start_min // 15
        rawq = [st + o for o in range(sh.duration_q)]
        # "no new staffing in blank intervals": skip options covering a blank current-week interval
        if any(key_of(q) is not None and key_of(q) not in active for q in rawq):
            continue
        opts = []
        for p in by_dur.get(sh.duration_q, []):
            onq = [st + o for o in range(sh.duration_q) if o not in p.broken_offsets]
            contrib = {}
            for q in onq:
                k = key_of(q)
                if k in active: contrib[k] = contrib.get(k, 0.0) + eff[k] / qpi
            opts.append((p.index, contrib, onq, rawq))
        if opts: day_opts[(d, s)] = opts

def rest_ok(s1, s2):  # s1 on day d, s2 on day d+1
    a, b = P.shifts[s1], P.shifts[s2]
    return 1440 + b.start_min - (a.start_min + a.duration_min) >= P.rest_gap_hours * 60

# ---- associate classes (identical in everything the model uses)
def ckey(a):
    x = P.associates[a]
    return (x.language, tuple(x.preferences), x.previous_saturday, tuple(x.fixed_schedule), x.nesting_group)
classes = {}
for a in range(A): classes.setdefault(ckey(a), []).append(a)
cls = list(classes.items())
print(f"{Path(wb).stem}: {A} associates in {len(cls)} class(es), {S} shifts, {len(pats)} patterns, "
      f"{sum(len(v) for v in day_opts.values())} day options", flush=True)

def hard_off_days(members):
    x = P.associates[members[0]]
    return {d for d in range(7) if E.norm(x.preferences[d]) in {"off", "leave"}}

def price(duals, members):
    """Best tour for this class under interval duals. Returns (value, tour) where
    tour = tuple per day of None or (s, pattern_index)."""
    offs = hard_off_days(members)
    best_day = {}
    for (d, s), opts in day_opts.items():
        bv, bp = -1e18, None
        for pi, contrib, _, _ in opts:
            v = sum(duals.get(k, 0.0) * c for k, c in contrib.items())
            if v > bv: bv, bp = v, pi
        best_day[(d, s)] = (bv, bp)
    best = (-1e18, None)
    for p0 in range(7):
        off = {p0, (p0 + 1) % 7}
        if not offs <= off: continue
        work = [d for d in range(7) if d not in off]
        for pair in itertools.combinations_with_replacement(range(S), 2):
            allowed = sorted(set(pair))
            # DP over days in calendar order with state = shift of previous day
            dp = {None: (0.0, ())}
            for d in range(7):
                ndp = {}
                if d not in work:
                    v = max(dp.values(), key=lambda t: t[0])
                    ndp[None] = (v[0], v[1] + (None,))
                else:
                    for s in allowed:
                        if (d, s) not in best_day: continue
                        dv, pi = best_day[(d, s)]
                        for prev, (val, tour) in dp.items():
                            if prev is not None and not rest_ok(prev, s): continue
                            if d == 0 and prev is None:
                                ps = P.associates[members[0]].previous_saturday
                                prev_shift = next((sh.index for sh in P.shifts if E.norm(sh.label) == E.norm(ps)), None)
                                if prev_shift is not None and not rest_ok(prev_shift, s): continue
                            cand = (val + dv, tour + ((s, pi),))
                            if s not in ndp or cand[0] > ndp[s][0]: ndp[s] = cand
                dp = ndp
                if not dp: break
            if dp:
                v = max(dp.values(), key=lambda t: t[0])
                if v[1] and len(v[1]) == 7 and v[0] > best[0]: best = v
    return best

def tour_contrib(tour):
    c = {}
    for d, x in enumerate(tour):
        if x is None: continue
        s, pi = x
        for p_i, contrib, _, _ in day_opts[(d, s)]:
            if p_i == pi:
                for k, v in contrib.items(): c[k] = c.get(k, 0.0) + v
                break
    return c

# ---- column generation with diving (price-and-branch heuristic)
ratio = float(P.break_max_concurrent_ratio); ABS = max(1, int(P.break_max_concurrent_absolute))
opt_lookup = {(d, s, o[0]): o for (d, s), opts in day_opts.items() for o in opts}

def tour_quarters(tour):
    on, raw = [], []
    for d, t in enumerate(tour):
        if t is None: continue
        _, _, onq, rawq = opt_lookup[(d, t[0], t[1])]
        on += onq; raw += rawq
    return on, raw

qinfo = {}
def col_rows(tour):
    if tour not in qinfo:
        on, raw = tour_quarters(tour); c = tour_contrib(tour)
        qinfo[tour] = (c, set(on), set(raw))
    return qinfo[tour]

def price_with_rows(ydem, yq, members):
    """yq[q] = combined dual weight per break quarter and per on quarter: (w_on, w_brk)."""
    # fold quarter weights into per-option values by patching the dual map per option
    return price2(ydem, yq, members)

def option_value(d, s, ydem, yq):
    bv, bp = -1e18, None
    for pi, contrib, onq, rawq in day_opts[(d, s)]:
        v = sum(ydem.get(k, 0.0) * c for k, c in contrib.items())
        ons = set(onq)
        for q in rawq:
            w = yq.get(q)
            if w: v += w[0] if q in ons else w[1]
        if v > bv: bv, bp = v, pi
    return bv, bp

def price2(ydem, yq, members):
    offs = hard_off_days(members)
    best_day = {k: option_value(k[0], k[1], ydem, yq) for k in day_opts}
    ps = P.associates[members[0]].previous_saturday
    prev_shift = next((sh.index for sh in P.shifts if E.norm(sh.label) == E.norm(ps)), None)
    best = (-1e18, None)
    maxdiff = max(1, int(P.max_different_shifts))
    for p0 in range(7):
        off = {p0, (p0 + 1) % 7}
        if not offs <= off: continue
        for combo in itertools.combinations(range(S), min(maxdiff, S)):
            allowed = combo
            dp = {None: (0.0, ())}
            for d in range(7):
                ndp = {}
                if d in off:
                    v = max(dp.values(), key=lambda t: t[0]); ndp[None] = (v[0], v[1] + (None,))
                else:
                    for s in allowed:
                        if (d, s) not in best_day: continue
                        dv, pi = best_day[(d, s)]
                        for prev, (val, tour) in dp.items():
                            if prev is not None and not rest_ok(prev, s): continue
                            if d == 0 and prev_shift is not None and not rest_ok(prev_shift, s): continue
                            cand = (val + dv, tour + ((s, pi),))
                            if s not in ndp or cand[0] > ndp[s][0]: ndp[s] = cand
                dp = ndp
                if not dp: break
            if dp:
                v = max(dp.values(), key=lambda t: t[0])
                if len(v[1]) == 7 and v[0] > best[0]: best = v
    return best

cols = {ci: [] for ci in range(len(cls))}
fixed = {ci: {} for ci in range(len(cls))}   # tour -> count
lp = pywraplp.Solver.CreateSolver("GLOP")
conv = {ci: lp.Add(lp.Sum([]) == len(cls[ci][1])) for ci in cols} if False else {}
for ci in cols:
    conv[ci] = lp.Constraint(len(cls[ci][1]), len(cls[ci][1]))
obj = lp.Objective()
cov = {}
for k in active:
    cov[k] = lp.Constraint(need[k], lp.infinity()); dv = lp.NumVar(0, lp.infinity(), ""); cov[k].SetCoefficient(dv, 1); obj.SetCoefficient(dv, 1)
rr, ra = {}, {}
for q in range(8 * 96):
    rr[q] = lp.Constraint(-lp.infinity(), 1); s1 = lp.NumVar(0, lp.infinity(), ""); rr[q].SetCoefficient(s1, -1); obj.SetCoefficient(s1, 10)
    ra[q] = lp.Constraint(-lp.infinity(), ABS); s2 = lp.NumVar(0, lp.infinity(), ""); ra[q].SetCoefficient(s2, -1); obj.SetCoefficient(s2, 10)
obj.SetMinimization()
lam = {}
def add_col(ci, tour):
    v = lp.NumVar(0, lp.infinity(), ""); lam[(ci, tour)] = v; cols[ci].append(tour)
    conv[ci].SetCoefficient(v, 1)
    c, on, raw = col_rows(tour)
    for k, x in c.items(): cov[k].SetCoefficient(v, x)
    for q in raw:
        b = 0 if q in on else 1
        rr[q].SetCoefficient(v, b - ratio); ra[q].SetCoefficient(v, b)

def solve_master():
    for it in range(1000):
        assert lp.Solve() == pywraplp.Solver.OPTIMAL
        ydem = {k: cov[k].dual_value() for k in active}
        yq = {}
        for q in rr:
            y1, y2 = rr[q].dual_value(), ra[q].dual_value()
            w_on = y1 * (-ratio); w_brk = y1 * (1 - ratio) + y2
            if abs(w_on) > 1e-12 or abs(w_brk) > 1e-12: yq[q] = (w_on, w_brk)
        added = 0
        for ci, (_, members) in enumerate(cls):
            if sum(fixed[ci].values()) >= len(members): continue
            v, tour = price2(ydem, yq, members)
            if tour and v + conv[ci].dual_value() > 1e-7 and tour not in cols[ci]:
                add_col(ci, tour); added += 1
        if not added:
            return {k: v.solution_value() for k, v in lam.items()}, obj.Value(), it + 1

def remaining(ci): return len(cls[ci][1]) - sum(fixed[ci].values())
for ci, (_, members) in enumerate(cls):
    add_col(ci, price2({k: 1.0 for k in active}, {}, members)[1])
sol, lp_obj, its = solve_master()
print(f"  root LP: objective {lp_obj:.3f} after {its} CG iterations, {sum(map(len, cols.values()))} tours [{time.time()-t0:.0f}s]", flush=True)
dives = 0; dobj = lp_obj
while any(remaining(ci) > 0 for ci in cols):
    # most-fractional-free: pick the largest unfixed mass
    cand = [((ci, t), v - fixed[ci].get(t, 0)) for (ci, t), v in sol.items() if remaining(ci) > 0]
    (ci, t), v = max(cand, key=lambda kv: kv[1])
    n = max(1, min(remaining(ci), int(math.floor(v + 1e-6))))
    fixed[ci][t] = fixed[ci].get(t, 0) + n; lam[(ci, t)].SetLb(fixed[ci][t]); dives += 1
    sol, dobj, its = solve_master()
print(f"  dive: {dives} fixings, final LP objective {dobj:.3f}, {sum(map(len, cols.values()))} tours [{time.time()-t0:.0f}s]", flush=True)
deficit_part = sum(v.solution_value() for v in lp.variables() if obj.GetCoefficient(v) == 1)
print(f"  dive LP split: coverage deficit {deficit_part:.3f}, concurrency slack {(dobj - deficit_part)/10:.3f}", flush=True)
dive_counts = {(ci, j): fixed[ci].get(t, 0) for ci in cols for j, t in enumerate(cols[ci])}

def evaluate(counts, label):
    assign = [["OFF"] * 7 for _ in range(A)]; sidx = [[None] * 7 for _ in range(A)]; sel = {}
    for ci, (_, members) in enumerate(cls):
        pool = list(members)
        for j in range(len(cols[ci])):
            for _ in range(counts[(ci, j)]):
                a = pool.pop()
                for d, t in enumerate(cols[ci][j]):
                    if t is None: continue
                    s_, pi = t
                    assign[a][d] = P.shifts[s_].label; sidx[a][d] = s_; sel[(a, d)] = pi
    sk = E.SkeletonSolution("column_generation", "FEASIBLE", 0, 0, assign, sidx, {})
    mm = E.calculate_metrics(P, sk, sel, pats)
    print(f"  {label} ENGINE METRIC: before {mm['before_target']} after {mm['after_target']}/{mm['after_floor']} of "
          f"{mm['active_intervals']}  conc_viol={mm['break_concurrency_violation_count']} zero={mm['zero_staffed_active_quarters']} "
          f"blank={mm['blank_staffed_quarters']} [{time.time()-t0:.0f}s]", flush=True)
    return sk, sel, mm

evaluate(dive_counts, "DIVE")
# ---- exact integer selection (LP-based MIP over the generated tours)
MIPNAME = sys.argv[5] if len(sys.argv) > 5 else "SCIP"
mip = pywraplp.Solver.CreateSolver(MIPNAME)
mip.SetTimeLimit(int(T_IP * 1000)); mip.SetNumThreads(W)
x = {(ci, j): mip.IntVar(0, len(cls[ci][1]), "") for ci in cols for j in range(len(cols[ci]))}
for ci in cols: mip.Add(sum(x[(ci, j)] for j in range(len(cols[ci]))) == len(cls[ci][1]))
onq_terms, raw_terms = {}, {}; viol = []
for (ci, j), var in x.items():
    c, on, raw = col_rows(cols[ci][j])
    for q in on: onq_terms.setdefault(q, []).append(var)
    for q in raw: raw_terms.setdefault(q, []).append(var)
hits = []
for k in active:
    d, i = k
    tot = sum(v for q in range(d * 96 + i * qpi, d * 96 + i * qpi + qpi) for v in onq_terms.get(q, []))
    e = E.scaled_effective_factor(P.shrinkage[d][i])
    Tt = math.ceil(E.scaled_coverage_threshold(P.requirements[d][i] or 0, P.target_ratio, qpi) / e) if e else 10**6
    Tf = math.ceil(E.scaled_coverage_threshold(P.requirements[d][i] or 0, P.floor_ratio, qpi) / e) if e else 10**6
    ht, hf = mip.BoolVar(""), mip.BoolVar("")
    mip.Add(tot >= Tt * ht); mip.Add(tot >= Tf * hf)
    hits.append((ht, hf))
for q, rv in raw_terms.items():
    raw = sum(rv); on = sum(onq_terms.get(q, [])); brk = raw - on
    if key_of(q) in active:
        zs = mip.NumVar(0, 1, ""); mip.Add(on + zs >= 1); viol.append(zs)
    z = mip.BoolVar(""); M = A; v = mip.NumVar(0, A, ""); viol.append(v)
    mip.Add(brk - v <= 1 + M * z); mip.Add(brk - v <= ratio * raw + M * (1 - z))
    mip.Add(brk - v <= ABS); mip.Add(brk - v <= raw - 1 + M * (1 - z))
mip.Maximize(sum(12 * ht + 3 * hf for ht, hf in hits) - 100 * sum(viol))
mst = mip.Solve()
print(f"  MIP[{MIPNAME}] status {mst} target hits {sum(round(h.solution_value()) for h, _ in hits)}/{len(active)} "
      f"floor {sum(round(f.solution_value()) for _, f in hits)} bound {mip.Objective().BestBound():.1f} [{time.time()-t0:.0f}s]", flush=True)
sk, sel, mm = evaluate({k: int(round(v.solution_value())) for k, v in x.items()}, 'MIP')
