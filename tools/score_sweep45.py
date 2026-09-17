#!/usr/bin/env python3
"""Score the 45s-slice sweep against the authors' recorded RC5 quick baseline.

Reads only; writes nothing. Baseline dir is the authors' recorded result set and
is never regenerated -- if a case is missing there it is reported as missing.
"""
import json, os, sys

SP = os.path.dirname(os.path.abspath(__file__))
NEW  = os.path.join(SP, "sweep45")
BASE = os.path.join(SP, "res", "AE_REAL_RC5_QUICK_RESULTS")
CASES = ["AE_AR_B2B","AE_AR_Choice","AE_FR_B2B","AE_FR_Choice","AE_IT_B2B","AE_IT_Choice"]

def load(root, case):
    p = os.path.join(root, case, "BUSINESS_OUTCOME.json")
    if not os.path.exists(p):
        return None
    with open(p) as fh:
        return json.load(fh)

def surf(d):
    """Return the comparable metric surface, or a blocked-run marker.

    A run that produced no final schedule has no after_* numbers at all --
    independent validation never ran. It is reported as blocked, never
    silently coerced to zeros or to its Stage-1 before_* figures.
    """
    if not d:
        return None
    iv = d.get("independent_validation") or {}
    mp = iv.get("metric_parity") or {}
    if iv.get("status") == "NOT_RUN" or not mp:
        return {"blocked": True,
                "tech": d.get("technical_status"),
                "code": d.get("outcome_code"),
                "val":  iv.get("status")}
    e  = mp.get("engine") or {}
    return {
        "blocked": False,
        "before_target": e.get("before_target"), "after_target": e.get("after_target"),
        "before_floor":  e.get("before_floor"),  "after_floor":  e.get("after_floor"),
        "val":    iv.get("status"),
        "gate":   iv.get("quality_gate_status"),
        "parity": mp.get("status"),
        "nfields": len(mp.get("compared_fields") or []),
        "mismatch": mp.get("mismatch_count"),
        "tech":   d.get("technical_status"),
    }

rows, missing, blocked_rows = [], [], []
for c in CASES:
    n, b = surf(load(NEW, c)), surf(load(BASE, c))
    if n is None:
        missing.append((c, "new run not present")); continue
    if b is None:
        missing.append((c, "no recorded baseline"))
    rows.append((c, n, b))

print("case            target b->a        floor b->a         t_loss f_loss  val  gate parity")
print("-" * 92)
net_t = net_f = 0
for c, n, b in rows:
    if n.get("blocked") or (b and b.get("blocked")):
        nd = "BLOCKED(%s)" % n.get("code", n.get("tech")) if n.get("blocked") else \
             "target %s->%s" % (n["before_target"], n["after_target"])
        bd = "BLOCKED(%s)" % b.get("code", b.get("tech")) if (b and b.get("blocked")) else \
             ("no baseline" if not b else "target %s->%s" % (b["before_target"], b["after_target"]))
        print("%-15s new=%-46s base=%s" % (c, nd, bd))
        blocked_rows.append((c, n, b))
        continue
    tl = (n["before_target"] or 0) - (n["after_target"] or 0)
    fl = (n["before_floor"]  or 0) - (n["after_floor"]  or 0)
    if b:
        bt = "(%s->%s)" % (b["before_target"], b["after_target"])
        bf = "(%s->%s)" % (b["before_floor"],  b["after_floor"])
        dt = (n["after_target"] or 0) - (b["after_target"] or 0)
        df = (n["after_floor"]  or 0) - (b["after_floor"]  or 0)
        net_t += dt; net_f += df
        dmark = " %+d/%+d" % (dt, df)
    else:
        bt = bf = "(no baseline)"; dmark = "   n/a"
    print("%-15s %3s->%-3s %-12s %3s->%-3s %-12s %4d %5d   %-4s %-4s %s %d/%d%s" % (
        c, n["before_target"], n["after_target"], bt,
        n["before_floor"], n["after_floor"], bf,
        tl, fl, n["val"], n["gate"], n["parity"], n["nfields"] - (n["mismatch"] or 0), n["nfields"],
        dmark))
print("-" * 92)
print("cases scored: %d/%d (%d blocked, excluded from the net)   net vs baseline: after_target %+d, after_floor %+d"
      % (len(rows) - len(blocked_rows), len(CASES), len(blocked_rows), net_t, net_f))
for c, why in missing:
    print("MISSING: %s -- %s" % (c, why))
