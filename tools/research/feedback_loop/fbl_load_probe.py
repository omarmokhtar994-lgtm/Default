"""Stage-2 -> Stage-1 feedback by observed break load, on saved pools.

Loop: take the best compliant candidate; from the engine's own interval rows,
break load(d,i) = before_effective - after_effective (in Stage-1 units);
re-solve Stage 1 with that load added to its hit thresholds (build_skeleton
break_load_units, objective only, before-coverage basis); Stage 2 + DNBS on
the new skeleton; accept only if dnbs_metrics_no_worse against the anchor and
candidate_pool_class is compliant; repeat from the accepted candidate.

Variants per round: FULL (unanchored re-solve, hinted with the anchor) and
LOCAL-k (anchored, at most k changed cells).

usage: fbl_load_probe.py ENGINE RUN_DIR SECONDS WORKERS [VARIANTS] [ALL|DAMAGED]
"""
import glob
import io
import json
import sys
import time
import importlib.util
from pathlib import Path

eng, run_dir, budget, workers = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
variants = (sys.argv[5] if len(sys.argv) > 5 else "FULL,LOCAL-12,LOCAL-24").split(",")
load_scope = sys.argv[6] if len(sys.argv) > 6 else "DAMAGED"   # DAMAGED: only intervals breaks pushed below target
spec = importlib.util.spec_from_file_location("E", eng)
E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(eng).parent))
sys.modules["E"] = E
spec.loader.exec_module(E)

P = E.parse_input(next(iter(glob.glob(str(run_dir / "input_snapshot" / "*.xlsx")))))
pool = json.load(open(run_dir / "debug" / "CANDIDATE_POOL_CHECKPOINT.json"))
cands = [E.deserialize_break_candidate(P, r) for r in pool["compliant"]]
for sk, br in cands:
    br.metrics = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
cands.sort(key=lambda c: (-c[1].metrics["after_target"], -c[1].metrics["after_floor"]))
hard = E.HardConfig(hard_floor=(P.floor_mode == "hard"))
qpi = P.qslots_per_interval
log = io.StringIO()
start = cands[0][1].metrics
print(f"{run_dir.name}: pool {len(cands)}; best after_target {start['after_target']} floor {start['after_floor']} "
      f"before {start.get('before_target')} ({cands[0][0].profile}/{cands[0][1].profile})", flush=True)


def break_load(metrics):
    load = {}
    for row in metrics.get("interval_rows") or []:
        if load_scope == "DAMAGED" and not (row.get("target_hit_before") and not row.get("target_hit_after")):
            continue
        units = int(round((float(row["before_effective"]) - float(row["after_effective"])) * 100 * qpi))
        if units > 0:
            load[(int(row["day_index"]), int(row["interval_index"]))] = units
    return load


def stage1_profile(name):
    known = {p["name"]: p for p in E.skeleton_profiles()}
    base = dict(known.get(name) or known.get("target90_restore_champion") or next(iter(known.values())))
    base["name"] = f"fbl_load_{base['name']}"
    base["coverage_basis"] = "before"
    return base


deadline = time.time() + budget
anchor = cands[0]
seed, rounds, accepted = 9100, 0, 0
while time.time() < deadline - 60:
    rounds += 1
    load = break_load(anchor[1].metrics)
    progress = False
    for variant in variants:
        if time.time() > deadline - 60:
            break
        a_sk, a_br = anchor
        remaining = deadline - time.time()
        t1 = min(300.0, max(30.0, remaining * 0.3))
        kw = dict(random_seed=seed, hint_skeleton=a_sk, break_load_units=load)
        if variant.startswith("LOCAL"):
            kw.update(anchor=a_sk, max_changes=int(variant.split("-")[1]))
        new_sk = E.build_skeleton(P, stage1_profile(a_sk.profile), hard, t1, workers, log, **kw)
        seed += 1
        row = {"round": rounds, "variant": variant, "load_intervals": len(load), "stage1": new_sk.cp_status,
               "t1": round(new_sk.elapsed_sec, 1)}
        if new_sk.cp_status not in {"OPTIMAL", "FEASIBLE"}:
            print(row, flush=True); continue
        bm = E.calculate_metrics(P, new_sk, {(a, d): None for a, d, _ in E.scheduled_cells(new_sk)}, [])
        new_sk.diagnostics["no_break_metrics"] = bm
        row["before_target"] = bm.get("before_target")
        if not E.skeleton_hard_clean(P, bm):
            row["result"] = "STAGE1_HARD_GATE"; print(row, flush=True); continue
        remaining = deadline - time.time()
        t2 = min(300.0, max(30.0, remaining * 0.3))
        cand = E.solve_breaks(P, new_sk, 115, False, t2, workers, log, objective_mode="target_priority",
                              random_seed=seed, hint_solution=a_br)
        row["stage2"] = cand.cp_status
        if cand.cp_status not in {"OPTIMAL", "FEASIBLE"}:
            print(row, flush=True); continue
        cand.metrics = E.calculate_metrics(P, new_sk, cand.selected_pattern, cand.patterns)
        row["after_stage2"] = cand.metrics["after_target"]
        pair = (new_sk, cand)
        remaining = deadline - time.time()
        if remaining > 60:
            added, _, _ = E.run_day_neighbourhood_break_search(
                P, [pair], time.time() + min(300.0, remaining * 0.4), workers, io.StringIO(), seed)
            if added:
                pair = added[0]
                pair[1].metrics = E.calculate_metrics(P, pair[0], pair[1].selected_pattern, pair[1].patterns)
        m = pair[1].metrics
        cls = E.candidate_pool_class(P, pair[0], pair[1])
        ok, worse = E.dnbs_metrics_no_worse(m, anchor[1].metrics)
        row.update(after_dnbs=m["after_target"], floor=m["after_floor"], cls=cls,
                   accepted=bool(ok and cls == "compliant"), worse=worse[:4])
        print(row, flush=True)
        if ok and cls == "compliant":
            anchor, accepted, progress = pair, accepted + 1, True
            break
    if not progress:
        break

end = anchor[1].metrics
print("RESULT " + json.dumps({"case": run_dir.name, "start_after_target": start["after_target"],
                              "end_after_target": end["after_target"], "start_floor": start["after_floor"],
                              "end_floor": end["after_floor"], "accepted": accepted, "rounds": rounds}), flush=True)
