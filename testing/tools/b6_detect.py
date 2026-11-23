"""Does CP-SAT's presolve actually FIND the symmetry the roster contains?

symmetry_level defaults to 2, so detection is already enabled. That is not the
same as detection succeeding. This turns the solver log on and reports what
presolve says about symmetry for a real roster.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import l632_universal_scheduler as E

parsed = E.parse_input(Path(sys.argv[2]))
profile = next(p for p in E.skeleton_profiles() if p["name"] == "target90_restore_champion")
hard = E.HardConfig(hard_floor=(parsed.floor_mode == "hard"))
level = int(sys.argv[3]) if len(sys.argv) > 3 else None

lines = []
cp = E.import_cp_sat()
original_solve = cp.CpSolver.solve


def solve(self, model, *a, **k):
    self.parameters.log_search_progress = True
    self.parameters.log_to_stdout = False
    if level is not None:
        self.parameters.symmetry_level = level
    self.log_callback = lines.append
    return original_solve(self, model, *a, **k)


cp.CpSolver.solve = solve
try:
    E.build_skeleton(parsed, profile, hard, 25.0, 1, sys.stderr, random_seed=0)
finally:
    cp.CpSolver.solve = original_solve

print(f"symmetry_level requested: {level if level is not None else 'engine default (2)'}")
print(f"solver log lines captured: {len(lines)}")
hits = [l for l in lines if re.search(r"symmetr|orbit|generator|stabilizer", l, re.I)]
if hits:
    print("\npresolve symmetry findings:")
    for l in hits[:25]:
        print("   ", l.strip()[:150])
else:
    print("\nNO symmetry/orbit line in the presolve log at all.")
stats = [l for l in lines if re.search(r"^#Model|^Starting|^Presolve summary|variables\)|constraints\)", l)]
for l in stats[:8]:
    print("   ", l.strip()[:150])
