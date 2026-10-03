"""Score the F-33 A/B against F33_RULE.txt. Fails closed on missing pairs.

    python3 f33_score.py F33_AB_RESULTS.json OUT.json"""
import json, sys
from collections import defaultdict

rows = json.load(open(sys.argv[1]))
CASES = ("VOICE", "CHAT", "AEIT", "H1", "S08")
by = {(r["case"], r["mode"], r["seed"], r["arm"]): r for r in rows}
pairs = defaultdict(list)
missing = []
for case in CASES:
    for mode in ("target_priority", "release_quality_guard"):
        for seed in range(9000, 9005):
            o, n = by.get((case, mode, seed, "OLD")), by.get((case, mode, seed, "NEW"))
            if o is None or n is None:
                missing.append((case, mode, seed))
                continue
            pairs[case].append((o, n))
if missing:
    print("MISSING PAIRS", missing); sys.exit(2)

ok = lambda r: r["status"] in ("OPTIMAL", "FEASIBLE")
result = {"cases": {}, "rules": {}}
f1 = True
failed = {"OLD": 0, "NEW": 0}
for case, ps in pairs.items():
    for o, n in ps:
        failed["OLD"] += not ok(o); failed["NEW"] += not ok(n)
        if ok(n) and (n["zero_staffed_active_quarters"] or n["language_gap_count"]):
            f1 = False
    both = [(o, n) for o, n in ps if ok(o) and ok(n)]
    row = {"pairs_scored": len(both)}
    for key in ("after_target", "after_floor", "whole_week_imbalance_violation_count", "break_concurrency_violation_count"):
        deltas = [n[key] - o[key] for o, n in both]
        row[key] = {"mean_old": round(sum(o[key] for o, _ in both) / len(both), 2),
                    "mean_new": round(sum(n[key] for _, n in both) / len(both), 2),
                    "mean_delta": round(sum(deltas) / len(deltas), 2),
                    "wins_new": sum(d > 0 for d in deltas), "wins_old": sum(d < 0 for d in deltas)}
    result["cases"][case] = row
f1 = f1 and failed["NEW"] <= failed["OLD"]
f2 = all(r["after_target"]["mean_delta"] >= -1.0 and r["after_floor"]["mean_delta"] >= -1.0 for r in result["cases"].values())
result["failed_solves"] = failed
result["rules"] = {"F1_validity": "PASS" if f1 else "FAIL", "F2_non_inferiority": "PASS" if f2 else "FAIL"}
result["verdict"] = "SHIP" if f1 and f2 else "DO_NOT_SHIP_AS_IS"
json.dump(result, open(sys.argv[2], "w"), indent=1)
print(json.dumps(result, indent=1))
