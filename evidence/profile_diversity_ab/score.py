# Scores the profile-diversity A/B against PREREGISTERED_RULE.txt from the
# per-run evidence in evidence/raw_runs. Fails closed (audit F-19): a missing
# run folder aborts with exit 2; a run without a validated schedule scores
# "no schedule" for its arm (it can never win a best-of).
import datetime, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raw_runs"))
import runlib  # noqa: E402

cases = ["CHAT", "VOICE", "AR", "NMGSP", "M2", "H3", "H1"]
real = {"CHAT", "VOICE", "AR", "NMGSP"}
R = runlib.RAW
runs = runlib.load_all({**{(c, "s0"): R / "dnbs_e2e_3600b" / f"{c}_NEW_9000" for c in cases},
                        **{(c, "s1"): R / "dnbs_e2e_3600b" / f"{c}_NEW_9001" for c in cases},
                        **{(c, "r1"): R / "profile_diversity_ab" / f"{c}_ROT_9001" for c in cases}})


def view(r):
    A = r["audit"]
    return {"after": r["after"], "before": r["before"] or 0.0,
            "endgame": (A.get("final_recovery_endgame") or {}).get("status"),
            "rotation": (A.get("run_parameters") or {}).get("stage1_profile_rotation")}


sum0 = sum1 = 0; issues = []
print(f"Scored {datetime.datetime.utcnow().replace(microsecond=0).isoformat()}Z against PREREGISTERED_RULE.txt; new-run engine sha "
      + runlib.engine_sha(R / "profile_diversity_ab")[:16] + "\n")
print("```")
print(f"{'case':6} {'s9000 (shared)':16} {'s9001 default':16} {'s9001 rotated':16} {'B0 after/before':16} {'B1 after/before':16}")
for c in cases:
    s0, s1, r1 = (view(runs[(c, k)]) for k in ("s0", "s1", "r1"))
    b0a = max([x for x in (s0["after"], s1["after"]) if x is not None], default=0)
    b1a = max([x for x in (s0["after"], r1["after"]) if x is not None], default=0)
    b0b = max(s0["before"], s1["before"]); b1b = max(s0["before"], r1["before"])
    sum0 += b0a; sum1 += b1a
    if b1a < b0a - 3: issues.append(f"(2) {c} after {b1a} < {b0a} - 3")
    if c in real and b1b < b0b - 1: issues.append(f"(3) {c} before {b1b} < {b0b} - 1")
    fmt = lambda x: f"{x['after']}/{x['before']:.0f}"
    print(f"{c:6} {fmt(s0):16} {fmt(s1):16} {fmt(r1):16} {str(b0a)+'/'+format(b0b,'.0f'):16} {str(b1a)+'/'+format(b1b,'.0f'):16}  rot={r1['rotation']} endgame B0={s1['endgame']}")
if not sum1 > sum0: issues.insert(0, f"(1) summed after B1 {sum1} not > B0 {sum0}")
print(f"summed after: B0 {sum0}  B1 {sum1}")
print("VERDICT:", "SHIP --diversify-profiles as default" if not issues else "NOT SHIPPED (stays opt-in): " + "; ".join(issues))
print("```")
