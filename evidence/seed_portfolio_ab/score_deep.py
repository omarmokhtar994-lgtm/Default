import json, csv, glob, os, datetime
SP = "/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad"
def run(d):
    s = glob.glob(d + "/*_summary.csv")
    if not s:
        return {"after": None, "before": None, "note": "no summary (killed)"}
    r = list(csv.DictReader(open(s[0])))[-1]
    v = json.load(open(d + "/INDEPENDENT_VALIDATION.json")) if os.path.exists(d + "/INDEPENDENT_VALIDATION.json") else {}
    ok = v.get("status") == "PASS" and int(v.get("hard_fail_count") or 0) == 0 and (v.get("metric_parity") or {}).get("status") == "PASS"
    return {"after": int(float(r["after_target"])) if ok else None, "before": float(r["best_before_target"]) if r.get("best_before_target") else None}
cases = ["CHAT", "VOICE", "NMGSP", "H1"]
real = {"CHAT", "VOICE", "NMGSP"}
E, F = {}, {}
for c in cases:
    seeds = [run(f"{SP}/dnbs3600b/out/{c}_CUR_{s}") for s in ("9000", "9001")] + [run(f"{SP}/seedtime/out/{c}_T3600_{s}") for s in ("9002", "9003")]
    E[c] = {"after": max([x["after"] for x in seeds if x["after"] is not None], default=None),
            "before": max([x["before"] for x in seeds if x["before"] is not None], default=None),
            "seeds": [x["after"] for x in seeds]}
    F[c] = run(f"{SP}/seedtime/out/{c}_DEEP_9000")
sumE = sum(E[c]["after"] or 0 for c in cases)
sumF = sum(F[c]["after"] or 0 for c in cases)
issues = []
for c in real:
    if F[c]["before"] is not None and (E[c]["before"] or 0) < F[c]["before"] - 1:
        issues.append(f"before {c}: E {E[c]['before']} < F {F[c]['before']} - 1")
adopt = sumE >= sumF and not issues
print(f"DEEP part scored {datetime.datetime.utcnow().replace(microsecond=0).isoformat()}Z against PREREGISTERED_RULE.txt (commit 5c8f6aa).\n")
print("```")
print(f"{'case':8} {'E best 4x3600 (seeds)':34} {'F one DEEP run':28}")
for c in cases:
    f = F[c]
    ftxt = f"{f['after']} / {f['before']}" if f["after"] is not None else ("no validated schedule (" + f.get("note", "not validated") + ")")
    print(f"{c:8} {str(E[c]['after']) + ' / ' + str(E[c]['before']) + '  ' + str(E[c]['seeds']):34} {ftxt}")
print(f"summed after: E {sumE}  F {sumF} (a case without a validated F schedule contributes 0)")
print(f"before check (real workbooks, E not below F by more than 1): {'OK' if not issues else issues}")
print(f"DEEP VERDICT: {'adopt E: DEEP = best of 4 x 3600 s; OVERNIGHT = best of 6 x 3600 s' if adopt else 'stay: one DEEP run'}")
print("```")
