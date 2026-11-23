"""Aggregated exact joint shift+break model.

Variables: y[c,t] = associates of class c on legal weekly tour t (shift per day),
n[d,s,p] = associates working shift s on day d with break pattern p.
Associates of one class are interchangeable, so the optimum of this model is the
optimum of the joint problem for those rules; the schedule is expanded and scored
by the engine's own calculate_metrics.
"""
import sys, time, math, itertools, importlib.util, json
from pathlib import Path
from ortools.sat.python import cp_model

engine_file, wb = sys.argv[1], sys.argv[2]
T = float(sys.argv[3]) if len(sys.argv) > 3 else 300
W = int(sys.argv[4]) if len(sys.argv) > 4 else 4
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
P = E.parse_input(Path(wb))
t0 = time.time()
A, S, qpi = len(P.associates), len(P.shifts), P.qslots_per_interval
pats = E.generate_break_patterns(P)
by_dur = {}
for p in pats: by_dur.setdefault(p.duration_q, []).append(p)
active = [(d, i) for d in range(7) for i in range(P.intervals_per_day) if P.active[d][i]]
act_set = set(active)
def key_of(q): return None if q >= 672 else (q // 96, (q % 96) // qpi)

# ---- (day, shift) cells that may be staffed: no new staffing in blank intervals
def raw_q(d, s):
    st = d * 96 + P.shifts[s].start_min // 15
    return list(range(st, st + P.shifts[s].duration_q))
cell_ok = {(d, s): all(key_of(q) is None or key_of(q) in act_set for q in raw_q(d, s)) for d in range(7) for s in range(S)}

def rest_ok(s1, s2):
    a, b = P.shifts[s1], P.shifts[s2]
    return 1440 + b.start_min - (a.start_min + a.duration_min) >= P.rest_gap_hours * 60

def shift_of_label(lbl):
    return next((sh.index for sh in P.shifts if E.norm(sh.label) == E.norm(lbl)), None)

# ---- classes
def ckey(a):
    x = P.associates[a]
    return (x.language, tuple(E.norm(v) for v in x.preferences), E.norm(x.previous_saturday),
            tuple(E.norm(v) for v in x.fixed_schedule), x.nesting_group)
classes = {}
for a in range(A): classes.setdefault(ckey(a), []).append(a)
cls = list(classes.values())
maxdiff = max(1, int(P.max_different_shifts))

def tours_for(members):
    x = P.associates[members[0]]
    hard_off = {d for d in range(7) if E.norm(x.preferences[d]) in {"off", "leave"}}
    prev = shift_of_label(x.previous_saturday)
    out = []
    for p0 in range(7):
        off = {p0, (p0 + 1) % 7}
        if not hard_off <= off: continue
        work = [d for d in range(7) if d not in off]
        for combo in itertools.product(range(S), repeat=len(work)):
            if len(set(combo)) > maxdiff: continue
            tour = [None] * 7
            for d, s in zip(work, combo): tour[d] = s
            if any(not cell_ok[(d, s)] for d, s in zip(work, combo)): continue
            if prev is not None and tour[0] is not None and not rest_ok(prev, tour[0]): continue
            if any(tour[d] is not None and tour[d + 1] is not None and not rest_ok(tour[d], tour[d + 1]) for d in range(6)): continue
            out.append(tuple(tour))
    return out

m = cp_model.CpModel()
y = {}
for ci, members in enumerate(cls):
    ts = tours_for(members)
    for t in ts: y[(ci, t)] = m.NewIntVar(0, len(members), "")
    m.Add(sum(y[(ci, t)] for t in ts) == len(members))
print(f"{Path(wb).stem}: {A} associates, {len(cls)} class(es), {S} shifts, {len(pats)} patterns, {len(y)} tour vars", flush=True)

cnt = {}  # (d, s) -> expr of associates working
for (ci, t), v in y.items():
    for d, s in enumerate(t):
        if s is not None: cnt.setdefault((d, s), []).append(v)

n = {}; on_terms = {}; raw_terms = {}; brk_terms = {}
for (d, s), vs in cnt.items():
    total = sum(vs)
    dq = P.shifts[s].duration_q
    plist = by_dur.get(dq, [])
    st = d * 96 + P.shifts[s].start_min // 15
    for q in range(st, st + dq): raw_terms.setdefault(q, []).append(total)
    if not plist:
        for q in range(st, st + dq): on_terms.setdefault(q, []).append(total)
        continue
    nv = [m.NewIntVar(0, A, "") for _ in plist]
    m.Add(sum(nv) == total)
    for p, v in zip(plist, nv):
        n[(d, s, p.index)] = v
        bo = p.broken_offsets
        for o in range(dq):
            (brk_terms if o in bo else on_terms).setdefault(st + o, []).append(v)

carry = {q: len(E.prior_covering_associates(P, q)) for q in range(96)}

def on_expr(q): return sum(on_terms.get(q, [])) + carry.get(q, 0)
def raw_expr(q): return sum(raw_terms.get(q, [])) + carry.get(q, 0)
def brk_expr(q): return sum(brk_terms.get(q, []))

ratio_s = int(round(P.break_max_concurrent_ratio * 1_000_000)); ABS = max(1, int(P.break_max_concurrent_absolute))
ALLHIT = "--allhit" in sys.argv
hits = []
DAYONLY = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--day=")), -1))
for (d, i) in active:
    if DAYONLY >= 0 and d != DAYONLY: continue
    qs = range(d * 96 + i * qpi, d * 96 + i * qpi + qpi)
    tot = sum(on_expr(q) for q in qs)
    e = E.scaled_effective_factor(P.shrinkage[d][i])
    tt = E.scaled_coverage_threshold(P.requirements[d][i] or 0, P.target_ratio, qpi)
    tf = E.scaled_coverage_threshold(P.requirements[d][i] or 0, P.floor_ratio, qpi)
    ht, hf = m.NewBoolVar(""), m.NewBoolVar("")
    m.Add(e * tot >= tt).OnlyEnforceIf(ht); m.Add(e * tot >= tf).OnlyEnforceIf(hf)
    if ALLHIT: m.Add(ht == 1)
    hits.append((ht, hf))
    for q in qs:
        m.Add(on_expr(q) >= 1)
        raw, brk = raw_expr(q), brk_expr(q)
        if brk_terms.get(q):
            c = m.NewIntVar(0, 4 * A, "")
            m.Add(1_000_000 * c <= ratio_s * raw); m.Add(1_000_000 * c + 1_000_000 > ratio_s * raw)
            cap = m.NewIntVar(0, 4 * A, ""); m.AddMaxEquality(cap, [c, m.NewConstant(1)])
            m.Add(brk <= cap); m.Add(brk <= ABS); m.Add(brk <= raw - 1)
# next-Sunday protected quarters: Saturday spill + this Sunday's own staffing (steady-state week)
for q in range(672, 768):
    if not (raw_terms.get(q) and key_of(q - 672) in act_set): continue
    raw = sum(raw_terms[q]) + sum(raw_terms.get(q - 672, []))
    brk = sum(brk_terms.get(q, [])) + sum(brk_terms.get(q - 672, []))
    if brk_terms.get(q) or brk_terms.get(q - 672):
        c = m.NewIntVar(0, 4 * A, "")
        m.Add(1_000_000 * c <= ratio_s * raw); m.Add(1_000_000 * c + 1_000_000 > ratio_s * raw)
        cap = m.NewIntVar(0, 4 * A, ""); m.AddMaxEquality(cap, [c, m.NewConstant(1)])
        m.Add(brk <= cap); m.Add(brk <= ABS); m.Add(brk <= raw - 1)

m.Maximize(sum(1000 * ht + hf for ht, hf in hits))

SEED = {}
def hint_from(skel_idx, selected, fix=False):
    """Hint (or fix) y and n from an explicit schedule: sidx[a][d], selected[(a, d)]."""
    tc, nc = {}, {}
    for ci, members in enumerate(cls):
        for a in members:
            tc[(ci, tuple(skel_idx[a]))] = tc.get((ci, tuple(skel_idx[a])), 0) + 1
            for d in range(7):
                if skel_idx[a][d] is not None and selected.get((a, d)) is not None:
                    k = (d, skel_idx[a][d], selected[(a, d)]); nc[k] = nc.get(k, 0) + 1
    SEED["y"], SEED["n"] = tc, nc
    missing = [k for k in tc if k not in y]
    if missing: print(f"  hint: {len(missing)} tours outside the legal-tour set, e.g. {missing[:2]}", flush=True)
    for k, v in y.items():
        (m.Add(v == tc.get(k, 0)) if fix else m.AddHint(v, tc.get(k, 0)))
    for k, v in n.items():
        (m.Add(v == nc.get(k, 0)) if fix else m.AddHint(v, nc.get(k, 0)))

MODE = sys.argv[6] if len(sys.argv) > 6 else ""
if MODE.startswith("planted"):
    sys.path.insert(0, str(Path(engine_file).resolve().parents[2] / "tools"))
    import build_synthetic_suite as B
    case = next(c for c in B.case_defs() if c["id"] == Path(wb).stem)
    psk, psel, _ = B.plant(case, P, E)
    hint_from(psk.selected_shift_index, psel, fix=(MODE == "planted_fix"))
elif MODE.startswith("json"):
    h = json.load(open(MODE.split(":", 1)[1].replace("+mfix", "").replace("+dfree", "")))
    hint_from(h["selected_shift_index"], {(a, d): p for a, d, p in h["selected_pattern"]}, fix=MODE.startswith("jsonfix"))
    MODE = MODE.split(":", 1)[0] + next((x for x in ("+mfix", "+dfree") if MODE.endswith(x)), "")
obj_expr = sum(1000 * ht + hf for ht, hf in hits)
cell_expr = {k: sum(vs) for k, vs in cnt.items()}

def solve(model, tl, workers=W):
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = tl; sv.parameters.num_workers = workers
    return sv, sv.Solve(model)

LNS = float(sys.argv[7]) if len(sys.argv) > 7 else 0
if MODE.endswith("+mfix") or MODE.endswith("+dfree"):
    for (d, s_), ex in cell_expr.items():
        if MODE.endswith("+dfree") and d == DAYONLY: continue
        m.Add(ex == sum(v for (ci, t), v in SEED["y"].items() if t[d] == s_))
if LNS and SEED:
    seeded = m.clone()
    for k, v in y.items(): seeded.Add(v == SEED["y"].get(k, 0))
    for k, v in n.items(): seeded.Add(v == SEED["n"].get(k, 0))
    sv, st = solve(seeded, 60)
else:
    sv, st = solve(m, T)
th = sum(sv.Value(h) for h, _ in hits); fh = sum(sv.Value(f) for _, f in hits)
print(f"  CP-SAT {sv.StatusName(st)}: target {th}/{len(active)} floor {fh}  bound {int(sv.BestObjectiveBound())//1000} [{time.time()-t0:.0f}s]", flush=True)
if LNS and st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
    inc_y = {k: sv.Value(v) for k, v in y.items()}; inc_n = {k: sv.Value(v) for k, v in n.items()}
    inc_obj = int(sv.ObjectiveValue())
    import random; rng = random.Random(7)
    neigh = [(d1, d2) for d1 in range(7) for d2 in range(d1 + 1, 7)]
    deadline = time.time() + LNS; rounds = 0; stale = 0
    while time.time() < deadline and stale < len(neigh):
        rng.shuffle(neigh); improved_round = False
        for free in neigh:
            if time.time() >= deadline: break
            sub = m.clone()
            for (d, s), ex in cell_expr.items():
                if d in free: continue
                sub.Add(ex == sum(inc_y[k] for k in y if k[1][d] == s))
            sub.Add(obj_expr >= inc_obj + 1)
            sub.ClearHints()
            for k, v in y.items(): sub.AddHint(v, inc_y[k])
            for k, v in n.items(): sub.AddHint(v, inc_n[k])
            s2, st2 = solve(sub, min(30.0, max(1.0, deadline - time.time())))
            rounds += 1
            if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                inc_y = {k: s2.Value(v) for k, v in y.items()}; inc_n = {k: s2.Value(v) for k, v in n.items()}
                inc_obj = int(s2.ObjectiveValue()); stale = 0; improved_round = True
                print(f"    LNS free days {free}: -> target {inc_obj // 1000} floor {inc_obj % 1000} [{time.time()-t0:.0f}s]", flush=True)
            else:
                stale += 1
        if not improved_round and stale >= len(neigh): break
    vals = {id(v): inc_y[k] for k, v in y.items()}; vals.update({id(v): inc_n[k] for k, v in n.items()})
    class _SV:
        def Value(self, v): return vals[id(v)]
    sv = _SV()
    print(f"  LNS: {rounds} sub-solves, final target {inc_obj // 1000} floor {inc_obj % 1000} [{time.time()-t0:.0f}s]", flush=True)

# ---- expand and score with the engine metric
assign = [["OFF"] * 7 for _ in range(A)]; sidx = [[None] * 7 for _ in range(A)]; sel = {}
for ci, members in enumerate(cls):
    pool = list(members)
    for (c2, t), v in y.items():
        if c2 != ci: continue
        for _ in range(sv.Value(v)):
            a = pool.pop()
            for d, s in enumerate(t):
                if s is not None: assign[a][d] = P.shifts[s].label; sidx[a][d] = s
for d in range(7):
    for s in range(S):
        workers = [a for a in range(A) if sidx[a][d] == s]
        queue = []
        for p in by_dur.get(P.shifts[s].duration_q, []):
            if (d, s, p.index) in n: queue += [p.index] * sv.Value(n[(d, s, p.index)])
        for a, pi in itertools.zip_longest(workers, queue):
            assert a is not None and pi is not None or not by_dur.get(P.shifts[s].duration_q), (d, s)
            if a is not None: sel[(a, d)] = pi
sk = E.SkeletonSolution("aggregated_joint", "FEASIBLE", 0, 0, assign, sidx, {})
mm = E.calculate_metrics(P, sk, sel, pats)
print(f"  ENGINE METRIC: before {mm['before_target']} after {mm['after_target']}/{mm['after_floor']} of "
      f"{mm['active_intervals']}  conc_viol={mm['break_concurrency_violation_count']} "
      f"zero={mm['zero_staffed_active_quarters']} blank={mm['blank_staffed_quarters']} [{time.time()-t0:.0f}s]", flush=True)
out = Path(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else None
if out:
    json.dump({"assignment": assign, "selected_shift_index": sidx,
               "selected_pattern": [[a, d, p] for (a, d), p in sel.items()]}, open(out, "w"))
