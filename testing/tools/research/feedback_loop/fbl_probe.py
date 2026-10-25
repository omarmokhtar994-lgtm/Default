"""Stage-2 -> Stage-1 feedback loop, measured on saved candidate pools.

The engine's coordinated repair already feeds break damage back into Stage 1
(donor/receiver shift plan, break-damage focus cells), but in the 3,600 s
DNBS A/B it committed 0 of 22 attempts: every attempt was the 2-change step
(the budget never reached 4 or 6), and the repaired skeleton got a plain
Stage-2 solve while the anchor it had to beat was already DNBS-polished.

This probe runs the same feedback with (a) growing change limits, (b) DNBS on
every repaired candidate, (c) acceptance by the engine's own dominance rule
(dnbs_metrics_no_worse: after_target up, nothing guarded worse) and the
release validator (candidate_pool_class == compliant), (d) iteration from an
accepted candidate. Scores are calculate_metrics on the engine's own objects.

usage: fbl_probe.py ENGINE RUN_DIR SECONDS WORKERS [LIMITS]
"""
import glob
import io
import json
import sys
import time
import importlib.util
from pathlib import Path

eng, run_dir, budget, workers = sys.argv[1], Path(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4])
limits = [int(x) for x in (sys.argv[5] if len(sys.argv) > 5 else "4,8,12,16").split(",")]
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
width = 115
hard = E.HardConfig(hard_floor=(P.floor_mode == "hard"))
log = io.StringIO()
start_best = cands[0][1].metrics
print(f"pool {len(cands)} compliant; best after_target {start_best['after_target']} floor {start_best['after_floor']} "
      f"(profile {cands[0][0].profile}/{cands[0][1].profile})", flush=True)

deadline = time.time() + budget
anchor = cands[0]
rows = []
improved = 0
seed = 9000
while time.time() < deadline - 30:
    progress = False
    for limit in limits:
        if time.time() > deadline - 30:
            break
        a_sk, a_br = anchor
        plan = E.donor_receiver_shift_plan(P, a_sk, a_br)
        focus = set(plan.get("focus_cells", set()))
        preferred = dict(plan.get("preferred_shift_targets", {}))
        focus |= set(E.break_damage_focus_cells(P, a_sk, a_br))
        focus |= set(E.coverage_rebalance_focus_cells(P, a_sk, a_br))
        for a, d in list(focus):
            if d > 0:
                focus.add((a, d - 1))
            if d < 6:
                focus.add((a, d + 1))
        remaining = deadline - time.time()
        t1 = min(180.0, max(20.0, remaining * 0.25))
        repaired = E.build_skeleton(P, E.repair_profile(f"fbl_{limit}"), hard, t1, workers, log,
                                    anchor=a_sk, max_changes=limit, focus_cells=focus, random_seed=seed,
                                    hint_skeleton=a_sk, preferred_shift_targets=preferred)
        seed += 1
        row = {"limit": limit, "focus": len(focus), "stage1": repaired.cp_status, "t1": round(repaired.elapsed_sec, 1)}
        if repaired.cp_status not in {"OPTIMAL", "FEASIBLE"}:
            rows.append(row); print(row, flush=True); continue
        bm = E.calculate_metrics(P, repaired, {(a, d): None for a, d, _ in E.scheduled_cells(repaired)}, [])
        repaired.diagnostics["no_break_metrics"] = bm
        row["before_target"] = bm.get("before_target", bm.get("after_target"))
        if not E.skeleton_hard_clean(P, bm):
            row["result"] = "STAGE1_HARD_GATE"; rows.append(row); print(row, flush=True); continue
        remaining = deadline - time.time()
        t2 = min(240.0, max(20.0, remaining * 0.3))
        cand = E.solve_breaks(P, repaired, width, False, t2, workers, log, objective_mode="target_priority",
                              random_seed=seed, hint_solution=a_br)
        row["stage2"] = cand.cp_status
        if cand.cp_status not in {"OPTIMAL", "FEASIBLE"}:
            rows.append(row); print(row, flush=True); continue
        cand.metrics = E.calculate_metrics(P, repaired, cand.selected_pattern, cand.patterns)
        row["after_stage2"] = cand.metrics["after_target"]
        pair = (repaired, cand)
        remaining = deadline - time.time()
        if remaining > 60:
            added, _, summary = E.run_day_neighbourhood_break_search(
                P, [pair], time.time() + min(240.0, remaining * 0.4), workers, io.StringIO(), seed)
            if added:
                pair = added[0]
                pair[1].metrics = E.calculate_metrics(P, pair[0], pair[1].selected_pattern, pair[1].patterns)
        m = pair[1].metrics
        row["after_dnbs"] = m["after_target"]
        cls = E.candidate_pool_class(P, pair[0], pair[1])
        ok, worse = E.dnbs_metrics_no_worse(m, anchor[1].metrics)
        row.update(cls=cls, accepted=bool(ok and cls == "compliant"), worse=worse[:4])
        rows.append(row)
        print(row, flush=True)
        if ok and cls == "compliant":
            anchor = pair
            improved += 1
            progress = True
            break
    if not progress:
        break

end = anchor[1].metrics
print(json.dumps({"case": run_dir.name, "start_after_target": start_best["after_target"],
                  "end_after_target": end["after_target"], "start_floor": start_best["after_floor"],
                  "end_floor": end["after_floor"], "accepted": improved, "attempts": len(rows)}), flush=True)
