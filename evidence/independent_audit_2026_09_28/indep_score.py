# Independent re-scorer written for the audit: reads each run's own summary CSV
# and INDEPENDENT_VALIDATION.json; score = after_target only if validator PASS,
# 0 hard failures and parity PASS. Fails closed (F-19): the expected
# case x arm x seed set must be complete, or it exits 2 without a total.
#   python3 indep_score.py RUN_ROOT ARMS SEEDS [CASES]
import os, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raw_runs"))
import runlib  # noqa: E402

root = Path(sys.argv[1]); arms = sys.argv[2].split(","); seeds = sys.argv[3].split(",")
if len(sys.argv) > 4:
    cases = sys.argv[4].split(",")
else:
    cases = sorted({p.name.split("_")[0] for p in root.glob("*_*_*") if p.is_dir()})
if not cases:
    raise runlib.IncompleteEvidence([f"{root}/<case>_<arm>_<seed>"])
runs = runlib.load_all({(c, a, s): root / f"{c}_{a}_{s}" for c in cases for a in arms for s in seeds})
tot = {a: 0.0 for a in arms}
for c in cases:
    line = [c]
    for a in arms:
        vals = [runs[(c, a, s)] for s in seeds]
        ats = [v["after"] if v["after"] is not None else 0 for v in vals]
        m = statistics.mean(ats); tot[a] += m
        line.append(f"{a} {ats} mean {m} {['FAILED: ' + v['reason'] for v in vals if v['state'] != 'OK']}")
    print("  ".join(line))
print("SUM", tot)
