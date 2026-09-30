# Scores the DEEP part of the seed-portfolio A/B against PREREGISTERED_RULE.txt
# from the per-run evidence in evidence/raw_runs. Fails closed (audit F-19): on
# an empty or incomplete evidence tree it aborts with exit 2 instead of printing
# a verdict. A run folder that exists without a validated schedule (killed at
# the memory ceiling, or rejected by the validator) is a failed run, which the
# rule counts as contributing 0 to its arm.
import datetime, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "raw_runs"))
import runlib  # noqa: E402

cases = ["CHAT", "VOICE", "NMGSP", "H1"]
real = {"CHAT", "VOICE", "NMGSP"}
R = runlib.RAW
paths = {}
for c in cases:
    for s in ("9000", "9001"):
        paths[("E", c, s)] = R / "dnbs_e2e_3600b" / f"{c}_CUR_{s}"
    for s in ("9002", "9003"):
        paths[("E", c, s)] = R / "seed_portfolio_ab" / f"{c}_T3600_{s}"
    paths[("F", c)] = R / "seed_portfolio_ab" / f"{c}_DEEP_9000"
runs = runlib.load_all(paths)

E, F = {}, {}
for c in cases:
    seeds = [runs[("E", c, s)] for s in ("9000", "9001", "9002", "9003")]
    E[c] = {"after": max([x["after"] for x in seeds if x["after"] is not None], default=None),
            "before": max([x["before"] for x in seeds if x["before"] is not None], default=None),
            "seeds": [x["after"] for x in seeds]}
    F[c] = runs[("F", c)]
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
    ftxt = f"{f['after']} / {f['before']}" if f["after"] is not None else f"no validated schedule ({f['reason']})"
    print(f"{c:8} {str(E[c]['after']) + ' / ' + str(E[c]['before']) + '  ' + str(E[c]['seeds']):34} {ftxt}")
print(f"summed after: E {sumE}  F {sumF} (a case without a validated F schedule contributes 0)")
print(f"before check (real workbooks, E not below F by more than 1): {'OK' if not issues else issues}")
print(f"DEEP VERDICT: {'adopt E: DEEP = best of 4 x 3600 s; OVERNIGHT = best of 6 x 3600 s' if adopt else 'stay: one DEEP run'}")
print("```")
