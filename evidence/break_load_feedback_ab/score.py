# Scores the break-load-feedback A/B against PREREGISTERED_RULE.txt from the
# per-run evidence in evidence/raw_runs. Fails closed (audit F-19): a missing
# run folder aborts with exit 2; a run without a schedule counts against its arm.
import datetime, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raw_runs"))
import runlib  # noqa: E402

cases = ["CHAT", "VOICE", "AR", "NMGSP", "M2", "H3", "H1"]
real = {"CHAT", "VOICE", "AR", "NMGSP"}
seeds = ("9000", "9001")
R = runlib.RAW
runs = runlib.load_all({**{("CUR", c, s): R / "dnbs_e2e_3600b" / f"{c}_NEW_{s}" for c in cases for s in seeds},
                        **{("NEW", c, s): R / "break_load_feedback_ab" / f"{c}_FBL_{s}" for c in cases for s in seeds}})


def view(r):
    fb = ((r["audit"].get("break_load_feedback") or {}).get("execution") or {})
    raw = r.get("raw_after")
    return {"after": int(float(raw)) if raw not in (None, "") else 0, "before": r["before"] or 0.0,
            "valid": r["valid"], "has": raw not in (None, ""),
            "attempts": fb.get("attempts"), "accepted": fb.get("accepted_candidates")}


issues = []; sc = sn = 0.0; attempted = total = 0
print(f"Scored {datetime.datetime.utcnow().replace(microsecond=0).isoformat()}Z against PREREGISTERED_RULE.txt; NEW engine sha "
      + runlib.engine_sha(R / "break_load_feedback_ab")[:16] + "\n```")
print(f"{'case':6} {'CUR 9000/9001':14} {'NEW 9000/9001':14} {'CUR mean':9} {'NEW mean':9} {'before CUR/NEW':15} phase attempts/accepted")
for c in cases:
    cur = [view(runs[("CUR", c, s)]) for s in seeds]
    new = [view(runs[("NEW", c, s)]) for s in seeds]
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
