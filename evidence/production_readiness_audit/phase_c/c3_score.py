"""Score the C3 runs against C3_RULE.txt (written and pushed before the runs).

    python3 c3_score.py C3_RUNS_DIR OUT.json

Reads <C3_RUNS_DIR>/C3_<ARM>_<SEED>/RUN_RECORD.json for ARM in DEFAULT, S240 and
seeds 9000-9004. Means over the 5 seeds:
  CAUSE          S240 after_floor >= 90 AND S240 after_floor >= DEFAULT after_floor + 2
                 AND S240 after_target >= 67
  NOT THE CAUSE  S240 after_floor <= DEFAULT after_floor + 1
  otherwise      unresolved by this test
Validity: every run must exit 0 with validator and parity PASS; a failed run is
reported and voids the read for that arm."""
import json, statistics, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
SEEDS = range(9000, 9005)
arms, invalid = {}, {}
for arm in ("DEFAULT", "S240"):
    rows = []
    for seed in SEEDS:
        p = ROOT / f"C3_{arm}_{seed}" / "RUN_RECORD.json"
        r = json.loads(p.read_text()) if p.exists() else {"seed": seed, "missing": True}
        rows.append(r)
        ok = (not r.get("missing") and r.get("return_code") == 0 and r.get("validation") == "PASS"
              and r.get("parity") == "PASS")
        if not ok:
            invalid.setdefault(arm, []).append({"seed": seed, "return_code": r.get("return_code"),
                                                 "validation": r.get("validation"), "parity": r.get("parity"),
                                                 "missing": bool(r.get("missing"))})
    def mean(k):
        vals = [r.get(k) for r in rows if isinstance(r.get(k), (int, float))]
        return round(statistics.mean(vals), 2) if vals else None
    arms[arm] = {"after_target": mean("after_target"), "after_floor": mean("after_floor"),
                 "before_target": mean("before_target"), "before_floor": mean("before_floor"),
                 "severe_floor_gap_count": mean("severe_floor_gap_count"),
                 "break_concurrency_violation_count": mean("break_concurrency_violation_count"),
                 "per_seed": {r.get("seed"): {k: r.get(k) for k in ("after_target", "after_floor", "return_code",
                                                                     "validation", "parity", "stage1_attempts")}
                              for r in rows}}
paired = []
for seed in SEEDS:
    d, s = arms["DEFAULT"]["per_seed"].get(seed, {}), arms["S240"]["per_seed"].get(seed, {})
    if isinstance(d.get("after_floor"), (int, float)) and isinstance(s.get("after_floor"), (int, float)):
        paired.append({"seed": seed, "after_floor_delta": s["after_floor"] - d["after_floor"],
                       "after_target_delta": (s.get("after_target") or 0) - (d.get("after_target") or 0)})
if invalid:
    read = "VOID (a run failed validity; see invalid_runs)"
else:
    sf, st, df = arms["S240"]["after_floor"], arms["S240"]["after_target"], arms["DEFAULT"]["after_floor"]
    if sf >= 90 and sf >= df + 2 and st >= 67:
        read = "CAUSE"
    elif sf <= df + 1:
        read = "NOT_THE_CAUSE"
    else:
        read = "UNRESOLVED"
out = {"rule": "C3_RULE.txt", "arms": arms, "paired": paired, "invalid_runs": invalid, "read": read,
       "decision": "No default changes, whatever the read (C3_RULE.txt)."}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(json.dumps({k: out[k] for k in ("read", "invalid_runs")}))
print({a: {k: v[k] for k in ("after_target", "after_floor", "severe_floor_gap_count", "break_concurrency_violation_count")} for a, v in arms.items()})
print(paired)
