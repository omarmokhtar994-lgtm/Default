"""Day-neighbourhood aggregated break search on a fixed engine skeleton.

Neighbourhood d frees the break patterns of every associate whose shift starts on
day d (as counts n[s, p]: associates on shift s taking pattern p, interchangeable
for every term modelled here); everything else stays at the incumbent. The model
scores every interval those shifts touch, including spill into day d+1. The
baseline is the same model with n fixed to the incumbent, so a move is accepted
only if, over the touched intervals, target hits strictly rise and floor hits,
protected-tier hits, concurrency violations and zero-staffed quarters are no worse.
Everything is re-scored by the engine's calculate_metrics at the end.
"""
import sys, time, math, json, importlib.util
from pathlib import Path
from ortools.sat.python import cp_model

engine_file, wb, pool_path = sys.argv[1:4]
T_DAY = float(sys.argv[4]) if len(sys.argv) > 4 else 60
W = int(sys.argv[5]) if len(sys.argv) > 5 else 4
PASSES = int(sys.argv[6]) if len(sys.argv) > 6 else 1
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
P = E.parse_input(Path(wb))
t0 = time.time()
A, S, qpi = len(P.associates), len(P.shifts), P.qslots_per_interval
pats = E.generate_break_patterns(P)
by_dur = {}
for p in pats: by_dur.setdefault(p.duration_q, []).append(p)
pat_by_id = {p.index: p for p in pats}

pool = json.load(open(pool_path))
best = None
for row in pool["compliant"]:
    sk, br = E.deserialize_break_candidate(P, row)
    mm = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
    key = (mm["after_target"], mm["after_floor"])
    if best is None or key > best[0]: best = (key, sk, br, mm)
_, SK, BR, M0 = best
# the run may have used a different pattern numbering: map by (duration, breaks)
by_shape = {(p.duration_q, p.breaks): p.index for p in pats}
remap = {p.index: by_shape.get((p.duration_q, p.breaks)) for p in BR.patterns}
missing = [i for i, j in remap.items() if j is None and any(v == i for v in BR.selected_pattern.values())]
assert not missing, f"engine used {len(missing)} patterns outside the generated set"
BR.selected_pattern = {k: (remap[v] if v is not None else None) for k, v in BR.selected_pattern.items()}
chk = E.calculate_metrics(P, SK, BR.selected_pattern, pats)
assert (chk["after_target"], chk["after_floor"]) == (M0["after_target"], M0["after_floor"]), "remap changed the schedule"
print(f"{Path(wb).stem}: {A} associates, {S} shifts, {len(pats)} patterns; engine best after {M0['after_target']}/{M0['after_floor']} "
      f"(before {M0['before_target']}), no-break cells {len(BR.no_break_cells)}", flush=True)

cells = E.scheduled_cells(SK)          # (a, d, s)
PROT = [r for r in (0.90, 0.80) if r < float(P.target_ratio) - 0.004 and r > float(P.floor_ratio) + 0.004]
PROT.append(max(0.0, float(P.floor_ratio) - 0.10))    # severe-gap threshold
# Engine-level guard: a move is kept only if the engine's own metrics say it is no worse.
HIGHER = ["after_floor", "after_90", "after_80", "after_100", "week_boundary_after_target", "week_boundary_after_floor"]
LOWER = ["severe_floor_gap_count", "hard_floor_gap_count", "max_consecutive_floor_gaps", "zero_staffed_active_quarters",
         "language_gap_count", "opening_gap_count", "break_concurrency_violation_count", "blank_staffed_quarters",
         "week_boundary_zero_staffed_active_quarters", "week_boundary_hard_failure_count", "coverage_split_gap_count",
         "after_extreme_overage_count", "after_severe_overage_count", "whole_week_overage_cap_violation_count",
         "after_avoidable_overage_fte_sum"]
def engine_no_worse(new, old):
    bad = [k for k in HIGHER if (new.get(k) or 0) < (old.get(k) or 0)]
    bad += [k for k in LOWER if (new.get(k) or 0) > (old.get(k) or 0) + 1e-6]
    return (new["after_target"] > old["after_target"] and not bad), bad
CUR = dict(M0)
carry = {q: len(E.prior_covering_associates(P, q)) for q in range(96)}
raw_const = dict(carry)
for a, d, s in cells:
    st = d * 96 + P.shifts[s].start_min // 15
    for q in range(st, st + P.shifts[s].duration_q):
        if q < 672: raw_const[q] = raw_const.get(q, 0) + 1
inc = dict(BR.selected_pattern)        # incumbent (a, d) -> pattern id or None


def span(s, d):
    return d * 96 + P.shifts[s].start_min // 15, P.shifts[s].duration_q


def neighbourhood(d):
    movable = {}
    for a, dd, s in cells:
        if dd != d or inc.get((a, d)) is None or not by_dur.get(P.shifts[s].duration_q):
            continue
        st, dq = span(s, d)
        if st + dq > 672:
            continue                     # week-boundary spill stays fixed
        movable.setdefault(s, []).append(a)
    return movable


def solve_day(d, tl):
    movable = neighbourhood(d)
    if not movable:
        return None
    mov_set = {(a, d) for ms in movable.values() for a in ms}
    on_c, brk_c = dict(carry), {}
    for a, dd, s in cells:
        if (a, dd) in mov_set:
            continue
        st, dq = span(s, dd); pid = inc.get((a, dd))
        bo = pat_by_id[pid].broken_offsets if pid is not None else set()
        for o in range(dq):
            q = st + o
            if q >= 672:
                continue
            if o in bo: brk_c[q] = brk_c.get(q, 0) + 1
            else: on_c[q] = on_c.get(q, 0) + 1
    m = cp_model.CpModel()
    on_t, brk_t, nv, inc_n, touched = {}, {}, {}, {}, set()
    for s, members in movable.items():
        st, dq = span(s, d)
        for q in range(st, st + dq):
            touched.add((q // 96, (q % 96) // qpi))
        vs = []
        for p in by_dur[dq]:
            v = m.NewIntVar(0, len(members), ""); vs.append(v); nv[(s, p.index)] = v
            bo = p.broken_offsets
            for o in range(dq):
                (brk_t if o in bo else on_t).setdefault(st + o, []).append(v)
        m.Add(sum(vs) == len(members))
        for a in members:
            k = (s, inc[(a, d)]); inc_n[k] = inc_n.get(k, 0) + 1
    tgt, flr, prt, vio, zer = [], [], [], [], []
    for (dd, i) in sorted(touched):
        if not P.active[dd][i]:
            continue
        qs = range(dd * 96 + i * qpi, dd * 96 + i * qpi + qpi)
        tot = sum(sum(on_t.get(q, [])) + on_c.get(q, 0) for q in qs)
        e = E.scaled_effective_factor(P.shrinkage[dd][i]); req = P.requirements[dd][i] or 0
        for ratio, bucket in [(P.target_ratio, tgt), (P.floor_ratio, flr)] + [(r, prt) for r in PROT]:
            thr = E.scaled_coverage_threshold(req, ratio, qpi)
            h = m.NewBoolVar("")
            m.Add(e * tot >= thr).OnlyEnforceIf(h); m.Add(e * tot < thr).OnlyEnforceIf(h.Not())
            bucket.append(h)
        for q in qs:
            onq = sum(on_t.get(q, [])) + on_c.get(q, 0)
            z = m.NewBoolVar(""); m.Add(onq == 0).OnlyEnforceIf(z); m.Add(onq >= 1).OnlyEnforceIf(z.Not()); zer.append(z)
            if not brk_t.get(q):
                continue
            b = sum(brk_t[q]) + brk_c.get(q, 0)
            cap = E.maximum_concurrent_breaks(P, raw_const.get(q, 0))   # raw is fixed by the skeleton
            ok = m.NewBoolVar(""); m.Add(b <= cap).OnlyEnforceIf(ok); m.Add(b > cap).OnlyEnforceIf(ok.Not())
            vio.append(ok.Not())
    T_, F_, R_, V_, Z_ = sum(tgt), sum(flr), sum(prt), sum(vio), sum(zer)
    base = m.clone()
    for k, v in nv.items():
        base.Add(v == inc_n.get(k, 0))
    bs = cp_model.CpSolver(); bs.parameters.num_workers = 1; bs.parameters.max_time_in_seconds = 30
    assert bs.Solve(base) in (cp_model.OPTIMAL, cp_model.FEASIBLE), f"incumbent infeasible in its own model, day {d}"
    bT, bF, bR, bV, bZ = (int(bs.Value(x)) for x in (T_, F_, R_, V_, Z_))
    m.Add(T_ >= bT); m.Add(F_ >= bF); m.Add(R_ >= bR); m.Add(V_ <= bV); m.Add(Z_ <= bZ)
    for k, v in nv.items():
        m.AddHint(v, inc_n.get(k, 0))
    m.Maximize(10000 * T_ + 10 * F_ + 10 * R_ - V_)
    sv = cp_model.CpSolver(); sv.parameters.max_time_in_seconds = tl; sv.parameters.num_workers = W
    st_ = sv.Solve(m)
    if st_ not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return (d, sv.StatusName(st_), bT, bT)
    nT = int(sv.Value(T_))
    if nT <= bT:
        return (d, sv.StatusName(st_), bT, nT)
    global CUR
    trial = dict(inc)
    for s, members in movable.items():
        queue = []
        for p in by_dur[span(s, d)[1]]:
            queue += [p.index] * sv.Value(nv[(s, p.index)])
        for a, pid in zip(members, queue):
            trial[(a, d)] = pid
    mt = E.calculate_metrics(P, SK, trial, pats)
    ok, bad = engine_no_worse(mt, CUR)
    if not ok:
        return (d, sv.StatusName(st_) + f" REJECTED by engine metrics {bad or ['after_target']}", bT, nT)
    inc.clear(); inc.update(trial); CUR = mt
    return (d, sv.StatusName(st_) + f" ACCEPTED (engine after_target {mt['after_target']})", bT, nT)


for pas in range(PASSES):
    for d in range(7):
        r = solve_day(d, T_DAY)
        if r:
            print(f"  pass {pas} day {r[0]}: {r[1]} touched-interval target {r[2]} -> {r[3]} [{time.time()-t0:.0f}s]", flush=True)

mm = E.calculate_metrics(P, SK, inc, pats)
keys = ["after_target", "after_floor", "after_90", "language_gap_count", "opening_gap_count", "zero_staffed_active_quarters",
        "break_concurrency_violation_count", "after_avoidable_overage_fte_sum", "severe_floor_gap_count", "blank_staffed_quarters"]
print("  metric                             engine  day-LNS")
for k in keys:
    a0, a1 = M0.get(k), mm.get(k)
    f = lambda x: round(x, 3) if isinstance(x, float) else x
    print(f"  {k:34s} {f(a0)!s:>8} {f(a1)!s:>8}")
out = sys.argv[7] if len(sys.argv) > 7 else None
if out:
    json.dump({"selected_pattern": [[a, d, p] for (a, d), p in inc.items()], "metrics": {k: mm.get(k) for k in keys}}, open(out, "w"))
print(f"  [{time.time()-t0:.0f}s]")
