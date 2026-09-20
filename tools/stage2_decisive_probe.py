"""Does Stage-2's objective PREFER the worse schedule, or did the search miss it?

NIGHT_06's correction proved a placement at after_target 159 exists on the
tightly-packed Cricut Chat skeleton that production delivered at 130. That
proves reachability. It does NOT say which of two very different defects is
responsible, and the two need opposite fixes:

  weighting defect -> obj(159) > obj(130).  The model is minimising correctly
                      and 130 really is its optimum. Fix = re-weight.
  search defect    -> obj(159) < obj(130).  159 is the better point under the
                      engine's own objective and the unguided search failed to
                      reach it. Fix = search (hints, phase budget, strategy).

min_target_hits only ADDS a constraint (l632:7800-7801); the objective is
assembled identically and minimised at 7823. So the two objective values are
directly comparable -- same function, different feasible region.
"""
import sys, time, json
SP = "/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad"
sys.path.insert(0, f"{SP}/rc5p/RC9_2_2_FIX_VALIDATION_RC5/engine/_tools")
import l632_universal_scheduler as E

BOOK = f"{SP}/preb13/RC9_2_2_FIX_VALIDATION_RC5/inputs/Cricut_Chat_RC9_1_READY_SKELETON.xlsx"
parsed = E.parse_input(BOOK)
prof = {p["name"]: p for p in E.skeleton_profiles()}["target_floor_pareto_master"]

print("rebuilding the 194-coverage skeleton (180s, 4w, seed 9000) ...", flush=True)
sk = E.build_skeleton(parsed, prof, E.HardConfig(), 180.0, 4, sys.stderr, random_seed=9000)
bm = E.ensure_before_break_metrics(parsed, sk) or {}
print(f"  skeleton status={sk.cp_status} before_target={bm.get('before_target')} "
      f"before_floor={bm.get('before_floor')}\n", flush=True)

def arm(label, **kw):
    t = time.time()
    sol = E.solve_breaks(parsed, sk, 115, False, 120.0, 4, sys.stderr,
                         random_seed=9000, **kw)
    el = time.time() - t
    d, m = sol.diagnostics, (sol.metrics or {})
    shape = d.get("break_quality_shape", {}) or {}
    rec = {
        "arm": label, "status": str(sol.cp_status), "sec": round(el, 1),
        "objective": sol.objective,
        "bound": d.get("best_objective_bound"),
        "after_target": m.get("after_target"), "after_floor": m.get("after_floor"),
        "run_window_count": shape.get("run_window_count"),
        "daily_gap_constraint_count": shape.get("daily_gap_constraint_count"),
        "conflicts": d.get("conflicts"), "branches": d.get("branches"),
    }
    print(json.dumps(rec), flush=True)
    return rec

print("ARM A: unguided -- exactly what production Stage-2 runs", flush=True)
a = arm("A_unguided")
print("\nARM B: same model + hard floor of 159 target hits", flush=True)
b = arm("B_lock159", min_target_hits=159)

print("\n" + "=" * 70)
oa, ob = a["objective"], b["objective"]
print(f"obj(A unguided, after_target={a['after_target']}) = {oa:,.0f}")
print(f"obj(B lock159,  after_target={b['after_target']}) = {ob:,.0f}")
if a["status"] not in ("OPTIMAL", "FEASIBLE") or b["status"] not in ("OPTIMAL", "FEASIBLE"):
    print("VERDICT: no verdict -- an arm produced no solution in its slice")
elif ob < oa:
    print(f"VERDICT: SEARCH DEFECT. B is better by {oa-ob:,.0f} under the engine's")
    print("         own objective, and the unguided search did not find it.")
elif ob > oa:
    print(f"VERDICT: WEIGHTING DEFECT. The objective PREFERS A by {ob-oa:,.0f}.")
    print("         130 is the honest optimum of the model as written.")
else:
    print("VERDICT: tie -- objective is indifferent between them.")
gap_a = (oa - a["bound"]) if a["bound"] is not None else None
if gap_a is not None:
    print(f"\nArm A convergence: obj {oa:,.0f} vs bound {a['bound']:,.0f} -> gap {gap_a:,.0f}")
    if ob < oa and a["bound"] is not None and ob >= a["bound"]:
        print("  B lies ABOVE A's own proven bound: A knew a better point existed.")
json.dump([a, b], open(f"{SP}/night/stage2_decisive.json", "w"), indent=2)
