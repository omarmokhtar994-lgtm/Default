# Audit probe: property test of phase_b_maturity.build_global_budget_plan.
import random, sys; sys.path.insert(0, "engine/_tools")
import phase_b_maturity as P
random.seed(1); bad = []; n = 0
B = ['coordinated_repair','joint_refinement','post_break_repair','target_lock_recovery',
     'day_neighbourhood_break_search','break_load_feedback','allow_exceptions']
R = ['finalization_reserve_sec','safe_incumbent_reserve_sec','conflict_refinement_reserve_sec',
     'coordinated_repair_reserve_sec','joint_refinement_reserve_sec','stage1_minimum_seconds']
for total in list(range(60, 3000, 7)) + [3600, 7200, 14400, 21600, 86400]:
    for _ in range(12):
        kw = {f: random.choice([True, False]) for f in B}
        for r in R:
            if random.random() < 0.5: kw[r] = random.choice([0, 30, 120, 600, 5400])
        plan = P.build_global_budget_plan(total, **kw, diagnostics={}); n += 1
        if any(v < 0 for v in plan.values()) or sum(plan.values()) != total: bad.append((total, kw, plan))
print("configurations", n, "violations", len(bad))
