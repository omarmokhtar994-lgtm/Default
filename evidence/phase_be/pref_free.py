"""Preferences that cost nothing: demand is a staircase that two agents per shift cover exactly, each agent asks for the shift the staircase needs anyway."""
import io, sys, tempfile
from pathlib import Path
REPO = Path("/home/user/Default")
sys.path.insert(0, str(REPO / "engine" / "_tools")); sys.path.insert(0, str(REPO / "tests_staged"))
import l632_universal_scheduler as E
import phase_a_workbooks as W
NAMES = [f"Agent {c}" for c in "ABCDEFGHIJKL"]
SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in (6, 7, 8, 9, 10, 11)]
def need(d, m):
    if not (1 <= d <= 5): return None
    h = m / 60
    return sum(2 for s in range(6, 12) if s <= h < s + 9) or None
# the same pattern for every associate: agent i asks for shift i % 6 on the five weekdays
PREFS = {n: [None] + [SHIFTS[i % 6]] * 5 + [None] for i, n in enumerate(NAMES)}
spec = {"roster": [(n, "English") for n in NAMES], "shifts": SHIFTS, "demand": need, "preferences": PREFS,
        "instructions": {"Separate OFF Days": "Yes", "Use Preferences": "Yes"}}
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "case.xlsx"; W.build(spec, path); parsed = E.parse_input(path)
asked = sum(1 for a in parsed.associates for p in a.preferences if E.preference_kind(p) == "shift")
def run(label, prof):
    sk = E.build_skeleton(parsed, prof, E.HardConfig(), 15.0, 2, io.StringIO(), random_seed=9000)
    if not sk.assignment: print(label, "no skeleton", sk.cp_status); return
    worked = hit = 0
    for a, assoc in enumerate(parsed.associates):
        for d in range(7):
            if E.preference_kind(assoc.preferences[d]) == "shift" and E.preference_kind(sk.assignment[a][d]) == "shift":
                worked += 1; hit += E.norm(sk.assignment[a][d]) == E.norm(assoc.preferences[d])
    m = E.calculate_metrics(parsed, sk, {}, [])
    print(f"{label:34} weight {prof['preference']:>9}: worked a requested day {worked}/{asked}, asked shift {hit} ({100*hit//max(1,worked)}%), before_target {m['before_target']}, overage {m['before_solver_controllable_avoidable_overage_fte_sum']}", flush=True)
profs = {p["name"]: p for p in E.skeleton_profiles()}
for name in ("quality_convergence", "target90_restore_champion", "preference_neighborhood", "floor_protected"):
    run(name, profs[name])
for w in (0, 1000, 1_000_000):
    run("quality_convergence", dict(profs["quality_convergence"], preference=w))
