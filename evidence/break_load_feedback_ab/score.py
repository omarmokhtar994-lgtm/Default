import json, csv, glob, datetime
SP = "/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad"
def run(d):
    s = glob.glob(d + "/*_summary.csv")
    if not s:
        return {"after": None, "before": None, "valid": False, "has": False}
    r = list(csv.DictReader(open(s[0])))[-1]
    v = json.load(open(d + "/INDEPENDENT_VALIDATION.json"))
    ok = v.get("status") == "PASS" and int(v.get("hard_fail_count") or 0) == 0 and (v.get("metric_parity") or {}).get("status") == "PASS"
    A = json.load(open(glob.glob(d + "/*solver_audit.json")[0]))
    fb = ((A.get("break_load_feedback") or {}).get("execution") or {})
    return {"after": int(float(r["after_target"])), "before": float(r["best_before_target"]), "valid": ok, "has": True,
            "attempts": fb.get("attempts"), "accepted": fb.get("accepted_candidates")}
cases = ["CHAT", "VOICE", "AR", "NMGSP", "M2", "H3", "H1"]
real = {"CHAT", "VOICE", "AR", "NMGSP"}
issues = []; sc = sn = 0.0; attempted = total = 0
print(f"Scored {datetime.datetime.utcnow().replace(microsecond=0).isoformat()}Z against PREREGISTERED_RULE.txt; NEW engine sha "
      + open(SP + "/fblab/ENGINE_SHA.txt").read().split()[0][:16] + "\n```")
print(f"{'case':6} {'CUR 9000/9001':14} {'NEW 9000/9001':14} {'CUR mean':9} {'NEW mean':9} {'before CUR/NEW':15} phase attempts/accepted")
for c in cases:
    cur = [run(f"{SP}/dnbs3600b/out/{c}_NEW_{s}") for s in ("9000", "9001")]
    new = [run(f"{SP}/fblab/out/{c}_FBL_{s}") for s in ("9000", "9001")]
    for s, n in zip(cur, new):
        total += 1
        attempted += 1 if (n.get("attempts") or 0) > 0 else 0
        if not n["valid"]: issues.append(f"(1) {c} NEW run not validator-clean")
        if s["has"] and not n["has"]: issues.append(f"(4) {c} NEW produced no schedule")
    cm = sum(x["after"] for x in cur) / 2; nm = sum(x["after"] for x in new) / 2
    sc += cm; sn += nm
    cb = max(x["before"] for x in cur); nb = max(x["before"] for x in new)
    if c in real and nm < cm - 2: issues.append(f"(3) {c} mean {nm} < {cm} - 2")
    if c in real and nb < cb - 1: issues.append(f"(5) {c} before {nb} < {cb} - 1")
    print(f"{c:6} {str(cur[0]['after'])+'/'+str(cur[1]['after']):14} {str(new[0]['after'])+'/'+str(new[1]['after']):14} {cm:<9} {nm:<9} {format(cb,'.0f')+'/'+format(nb,'.0f'):15} {[ (x['attempts'], x['accepted']) for x in new]}")
if sn < sc: issues.insert(0, f"(2) summed NEW {sn} < CURRENT {sc}")
if attempted < total / 2: issues.append(f"(6) phase attempted in only {attempted}/{total} runs: INCONCLUSIVE")
print(f"summed two-seed mean after_target: CURRENT {sc}  NEW {sn}; phase attempted in {attempted}/{total} NEW runs")
print("VERDICT:", "SHIP (turn on by default)" if not issues else "NOT SHIPPED (stays opt-in): " + "; ".join(issues))
print("```")
