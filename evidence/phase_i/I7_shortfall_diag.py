# Diagnosis only: run the shortfall pass exactly as the test does (S04, seed 9000,
# 2 workers, D=10), many times, and record every stage's status and the shortfalls.
import io, json, os, sys, time, importlib.util
from pathlib import Path
pkg = Path(sys.argv[1]); n = int(sys.argv[2]); out = Path(sys.argv[3])
os.sched_setaffinity(0, {2, 3})
sys.path.insert(0, str(pkg / "tests_staged"))
spec = importlib.util.spec_from_file_location("t32", pkg / "tests_staged/test_rc9_2_32_phase_c_shortfall.py")
T = importlib.util.module_from_spec(spec); spec.loader.exec_module(T)
E = T.E
rows = []
for i in range(n):
    path, parsed = T.build(T.S04)
    dst = path.parent / "case_L6_3_2_3_HARD_RULE_SHORTFALL_SCHEDULE.xlsx"
    t0 = time.time()
    rec = E.run_shortfall_pass(parsed, path, dst, {}, E.capacity_diagnostics(parsed), time_limit=600, workers=2,
                               log=io.StringIO(), random_seed=9000, deterministic_time=10.0)
    extra = [f"{s['day']} {s['time']}" for s in rec["shortfalls"] if not (s["day"] == "Sun" and s["time"].startswith("03:"))]
    keep = {k: v for k, v in rec.items() if k not in ("shortfalls", "families", "workbook", "person_rule_failures") and not isinstance(v, (list, dict))}
    rows.append({"run": i, "ok": not extra, "extra": extra, "wall": round(time.time() - t0, 1), **keep})
    print(json.dumps(rows[-1]), flush=True)
out.write_text(json.dumps(rows, indent=1))
