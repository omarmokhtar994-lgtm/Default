# Independent re-scorer written for the audit: reads each run's own summary CSV
# and INDEPENDENT_VALIDATION.json; score = after_target only if validator PASS,
# 0 hard failures and parity PASS.
import csv, glob, json, os, sys, statistics
def run(d):
    s = sorted(glob.glob(d + "/*_summary.csv"))
    if not s: return None, None, "NO_SUMMARY"
    r = list(csv.DictReader(open(s[0])))[-1]
    vp = d + "/INDEPENDENT_VALIDATION.json"
    v = json.load(open(vp)) if os.path.exists(vp) else {}
    ok = v.get("status") == "PASS" and int(v.get("hard_fail_count") or 0) == 0 and (v.get("metric_parity") or {}).get("status") == "PASS"
    at = int(float(r["after_target"])) if ok and r.get("after_target") not in (None, "") else None
    bt = float(r["best_before_target"]) if r.get("best_before_target") else None
    return at, bt, "OK" if ok else f"NOT_CLEAN({v.get('status')},{v.get('hard_fail_count')},{(v.get('metric_parity') or {}).get('status')})"
root = sys.argv[1]; arms = sys.argv[2].split(","); seeds = sys.argv[3].split(",")
cases = sorted({os.path.basename(p).split("_")[0] for p in glob.glob(root + "/*_*_*") if os.path.isdir(p)})
tot = {a: 0.0 for a in arms}
for c in cases:
    line = [c]
    for a in arms:
        vals = [run(f"{root}/{c}_{a}_{s}") for s in seeds]
        ats = [v[0] if v[0] is not None else 0 for v in vals]
        m = statistics.mean(ats); tot[a] += m
        line.append(f"{a} {ats} mean {m} {[v[2] for v in vals if v[2]!='OK']}")
    print("  ".join(line))
print("SUM", tot)
