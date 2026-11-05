import io, sys, tempfile
src = open("/tmp/prefexp/pref_experiment.py").read().split("asked = sum")[0]
src = src.replace('PREFS = {n: [None] + [SHIFTS[(i + 2 * k) % 6] for k in range(1, 6)] + [None] for i, n in enumerate(NAMES)}',
                  'PREFS = {n: [None] + [SHIFTS[i % 6]] * 5 + [None] for i, n in enumerate(NAMES)}')
src = src.replace('"demand": lambda d, m: 2 if 9 * 60 <= m < 18 * 60 else None', '"demand": lambda d, m: 2 if (1 <= d <= 5 and 9 * 60 <= m < 18 * 60) else None')
exec(src)
asked = sum(1 for a in parsed.associates for p in a.preferences if E.preference_kind(p) == "shift")
# 1. are they jointly possible?
spec2 = dict(spec); spec2["preferences"] = {}; spec2["fixed"] = PREFS
spec2["instructions"] = {"Separate OFF Days": "Yes", "Use Preferences": "No", "Fixed Request Use": "Yes"}
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "case.xlsx"; W.build(spec2, path); parsed2 = E.parse_input(path)
prof0 = next(p for p in E.skeleton_profiles() if p["name"] == "quality_convergence")
sk = E.build_skeleton(parsed2, prof0, E.HardConfig(), 20.0, 2, io.StringIO(), random_seed=9000)
print("all", asked, "as HARD requests:", sk.cp_status, flush=True)
m0 = E.calculate_metrics(parsed2, sk, {}, []) if sk.assignment else {}
print("   coverage with them forced: before_target", m0.get("before_target"), "overage", m0.get("before_solver_controllable_avoidable_overage_fte_sum"), flush=True)
# 2. what the engine does as soft preferences, by weight
for w in (0, 4, 20, 90, 1000, 1_000_000):
    prof = dict(prof0, preference=w)
    sk = E.build_skeleton(parsed, prof, E.HardConfig(), 15.0, 2, io.StringIO(), random_seed=9000)
    hit = sum(1 for a, assoc in enumerate(parsed.associates) for d in range(7)
              if E.preference_kind(assoc.preferences[d]) == "shift" and E.norm(sk.assignment[a][d]) == E.norm(assoc.preferences[d]))
    worked = sum(1 for a, assoc in enumerate(parsed.associates) for d in range(7)
              if E.preference_kind(assoc.preferences[d]) == "shift" and E.preference_kind(sk.assignment[a][d]) == "shift")
    m = E.calculate_metrics(parsed, sk, {}, [])
    print(f"soft weight {w:7}: on a day with a request they work {worked}, with the asked shift {hit} ({100*hit//max(1,worked)}% of those); asked {asked}: before_target {m['before_target']} overage {m['before_solver_controllable_avoidable_overage_fte_sum']}", flush=True)
