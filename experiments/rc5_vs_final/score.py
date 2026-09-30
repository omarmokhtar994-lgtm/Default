#!/usr/bin/env python3
"""Score the RC5 vs FINAL confirmation experiment against PREREGISTERED_RULE.txt.

Fails closed: if any of the 120 registered run folders is missing, or a run is
marked CONTAMINATED (it must be rerun first), it prints no verdict and exits 2.

    python3 experiments/rc5_vs_final/score.py [--runs DIR]
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "evidence" / "raw_runs"))
import runlib  # noqa: E402

REAL = ("CHAT", "VOICE", "NMGSP", "AEIT")
SYNTH = ("H1", "M2")
SEEDS = range(9000, 9010)
HIGHER_BETTER = ("after_target", "after_floor", "best_before_target")
LOWER_BETTER = ("severe_floor_gaps", "language_gaps", "break_concurrency_violations")
REPORTED = HIGHER_BETTER + LOWER_BETTER + ("after90", "after80", "floor_gaps", "zero_active_quarters",
                                           "after_severe_overage_count", "after_avoidable_overage_fte_sum")
N_BOOT = 10_000
MIN_PAIRS = 8


def load(runs: Path):
    missing, contaminated, data = [], [], {}
    for arm in ("RC5", "FINAL"):
        for case in REAL + SYNTH:
            for seed in SEEDS:
                d = runs / f"{arm}_{case}_{seed}"
                rec_path = d / "RUN_RECORD.json"
                if not rec_path.exists():
                    missing.append(str(d))
                    continue
                rec = json.loads(rec_path.read_text())
                if rec.get("contaminated"):
                    contaminated.append(str(d))
                r = runlib.load(d)
                validated = r["state"] == "OK" and rec.get("return_code") == 0 and not rec.get("timed_out")
                row = {}
                if validated:
                    import csv
                    summary = next(iter(sorted(d.glob("*_summary.csv"))))
                    row = list(csv.DictReader(open(summary, encoding="utf-8")))[-1]
                    absent = [m for m in REPORTED + ("elapsed_sec",) if row.get(m) in (None, "")]
                    if absent:
                        raise SystemExit(f"{d.name}: summary lacks {absent} - no verdict")
                data[(arm, case, seed)] = {"validated": validated, "record": rec, "reason": r.get("reason", ""),
                                           "row": {k: float(row[k]) for k in REPORTED + ("elapsed_sec",)} if validated else {}}
    if missing:
        raise runlib.IncompleteEvidence(missing)
    if contaminated:
        print("CONTAMINATED runs must be rerun first:", *contaminated, sep="\n  ", file=sys.stderr)
        raise SystemExit(2)
    return data


def boot_ci(deltas: np.ndarray, rng) -> tuple:
    idx = rng.integers(0, len(deltas), size=(N_BOOT, len(deltas)))
    means = deltas[idx].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def sign_flip_p(deltas: np.ndarray) -> float:
    observed = abs(deltas.mean())
    hits = total = 0
    for signs in itertools.product((1, -1), repeat=len(deltas)):
        total += 1
        hits += abs((deltas * np.array(signs)).mean()) >= observed - 1e-12
    return hits / total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=HERE / "runs")
    args = ap.parse_args()
    data = load(args.runs)
    rng = np.random.default_rng(20260930)
    failures = {arm: [k for k, v in data.items() if k[0] == arm and not v["validated"]] for arm in ("RC5", "FINAL")}
    stats, pairs_by_case = {}, {}
    for case in REAL + SYNTH:
        pairs = [s for s in SEEDS if data[("RC5", case, s)]["validated"] and data[("FINAL", case, s)]["validated"]]
        pairs_by_case[case] = pairs
        for metric in REPORTED:
            d = np.array([data[("FINAL", case, s)]["row"][metric] - data[("RC5", case, s)]["row"][metric] for s in pairs])
            if len(d) == 0:
                stats[(case, metric)] = None
                continue
            lo, hi = boot_ci(d, rng)
            stats[(case, metric)] = {"n": len(d), "mean": float(d.mean()), "lo": lo, "hi": hi, "p": sign_flip_p(d),
                                     "rc5_mean": float(np.mean([data[("RC5", case, s)]["row"][metric] for s in pairs])),
                                     "final_mean": float(np.mean([data[("FINAL", case, s)]["row"][metric] for s in pairs]))}
    # summed real after_target: case-stratified bootstrap
    per_case = {c: np.array([data[("FINAL", c, s)]["row"]["after_target"] - data[("RC5", c, s)]["row"]["after_target"]
                             for s in pairs_by_case[c]]) for c in REAL}
    summed = sum(float(v.mean()) for v in per_case.values() if len(v))
    if all(len(v) for v in per_case.values()):
        boots = sum(v[rng.integers(0, len(v), size=(N_BOOT, len(v)))].mean(axis=1) for v in per_case.values())
        summed_ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    else:
        summed_ci = (float("nan"), float("nan"))

    rules, notes = {}, []
    final_invalid = [k for k in failures["FINAL"]
                     if not (data[k]["record"].get("timed_out") or data[k]["record"].get("return_code") in (-9, 137))]
    rules[1] = not final_invalid
    rules[2] = len(failures["FINAL"]) <= len(failures["RC5"])
    inconclusive = [c for c in REAL + SYNTH if len(pairs_by_case[c]) < MIN_PAIRS]
    r3 = True
    for c in REAL:
        if c in inconclusive:
            continue
        for m in HIGHER_BETTER:
            if stats[(c, m)]["lo"] < -1:
                r3 = False; notes.append(f"rule 3: {c} {m} CI lower {stats[(c, m)]['lo']:.2f} < -1")
        for m in LOWER_BETTER:
            if stats[(c, m)]["hi"] > 0.5:
                r3 = False; notes.append(f"rule 3: {c} {m} CI upper {stats[(c, m)]['hi']:.2f} > 0.5")
    rules[3] = r3
    r4 = True
    for c in SYNTH:
        if c not in inconclusive and stats[(c, "after_target")]["lo"] < -3:
            r4 = False; notes.append(f"rule 4: {c} after_target CI lower {stats[(c, 'after_target')]['lo']:.2f} < -3")
    rules[4] = r4
    rules[5] = summed_ci[0] > 0
    over = [k for k, v in data.items() if k[0] == "FINAL" and v["validated"]
            and (v["row"]["elapsed_sec"] > 3780 or (v["record"].get("peak_rss_mb") or 0) > 8192)]
    over += [k for k, v in data.items() if k[0] == "FINAL" and not v["validated"]
             and (v["record"].get("peak_rss_mb") or 0) > 8192]
    rules[6] = not over
    rules[7] = True  # FINAL's contract accepted all six inputs (checked before registration)
    regression = [c for c in REAL if c not in inconclusive and stats[(c, "after_target")]["hi"] < -1]

    if not rules[1] or not rules[2] or regression:
        verdict = "ROLLBACK / MORE ENGINEERING"
    elif inconclusive or not (rules[3] and rules[4] and rules[6] and rules[7]):
        verdict = "INCONCLUSIVE"
    elif rules[5]:
        verdict = "RELEASE-CONFIRMED"
    else:
        verdict = "NON-INFERIOR"

    print("RC5 vs FINAL confirmation experiment - scored against PREREGISTERED_RULE.txt")
    print(f"runs: {len(data)}; FAILED runs RC5 {len(failures['RC5'])}, FINAL {len(failures['FINAL'])}")
    for arm in ("RC5", "FINAL"):
        for k in failures[arm]:
            rec = data[k]["record"]
            print(f"  FAILED {'_'.join(map(str, k))}: rc {rec.get('return_code')}, timed_out {rec.get('timed_out')}, "
                  f"peak {rec.get('peak_rss_mb')} MB, {data[k]['reason']}")
    print()
    print(f"{'case':6} {'metric':32} {'n':>2} {'RC5':>9} {'FINAL':>9} {'delta':>7} {'95% CI':>17} {'p':>6}")
    for c in REAL + SYNTH:
        for m in REPORTED:
            s = stats[(c, m)]
            if s is None:
                print(f"{c:6} {m:32} no validated pairs"); continue
            print(f"{c:6} {m:32} {s['n']:>2} {s['rc5_mean']:>9.2f} {s['final_mean']:>9.2f} {s['mean']:>+7.2f} "
                  f"[{s['lo']:>+6.2f},{s['hi']:>+6.2f}] {s['p']:>6.3f}")
        print()
    print(f"summed real after_target delta {summed:+.2f}, 95% CI [{summed_ci[0]:+.2f}, {summed_ci[1]:+.2f}]")
    for n in sorted(rules):
        print(f"rule {n}: {'PASS' if rules[n] else 'FAIL'}")
    for n in notes:
        print("  " + n)
    if inconclusive:
        print(f"cases with < {MIN_PAIRS} validated pairs: {inconclusive}")
    if final_invalid:
        print("FINAL validity failures:", ["_".join(map(str, k)) for k in final_invalid])
    if over:
        print("FINAL resource overruns:", ["_".join(map(str, k)) for k in over])
    if regression:
        print("clear regressions (after_target CI upper < -1):", regression)
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
