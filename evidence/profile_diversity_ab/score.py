import json, csv, glob, datetime
SP = "/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad"
def run(d):
    s = glob.glob(d + "/*_summary.csv")
    if not s:
        return {"after": None, "before": None}
    r = list(csv.DictReader(open(s[0])))[-1]
    v = json.load(open(d + "/INDEPENDENT_VALIDATION.json"))
    ok = v.get("status") == "PASS" and int(v.get("hard_fail_count") or 0) == 0 and (v.get("metric_parity") or {}).get("status") == "PASS"
    A = json.load(open(glob.glob(d + "/*solver_audit.json")[0]))
    eg = (A.get("final_recovery_endgame") or {}).get("status")
    return {"after": int(float(r["after_target"])) if ok else None, "before": float(r["best_before_target"]), "endgame": eg,
            "rotation": (A.get("run_parameters") or {}).get("stage1_profile_rotation")}
cases = ["CHAT", "VOICE", "AR", "NMGSP", "M2", "H3", "H1"]
real = {"CHAT", "VOICE", "AR", "NMGSP"}
sum0 = sum1 = 0; issues = []
print(f"Scored {datetime.datetime.utcnow().replace(microsecond=0).isoformat()}Z against PREREGISTERED_RULE.txt; new-run engine sha "
      + open(SP + "/div/ENGINE_SHA.txt").read().split()[0][:16] + "\n")
print("```")
print(f"{'case':6} {'s9000 (shared)':16} {'s9001 default':16} {'s9001 rotated':16} {'B0 after/before':16} {'B1 after/before':16}")
for c in cases:
    s0 = run(f"{SP}/dnbs3600b/out/{c}_NEW_9000"); s1 = run(f"{SP}/dnbs3600b/out/{c}_NEW_9001"); r1 = run(f"{SP}/div/out/{c}_ROT_9001")
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
