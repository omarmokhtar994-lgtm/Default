#!/usr/bin/env python3
"""Turn the C4 A/B score (c4_ab_score.py output) into the markdown tables used in
PHASE_C_RESULT.md and the run guide. Reads only the score file; computes nothing new.

    python3 c4_ab_report.py C4_AB_SCORE_FINAL.json
"""
import json
import sys

NAMES = {"VOICE": "Cricut Voice", "CHAT": "Cricut Chat", "NMGSP": "NMG Spanish",
         "AEIT": "AE IT B2B", "GDI": "GDI 28 HC 24/7"}


def signed(x, digits=1):
    return f"{x:+.{digits}f}" if isinstance(x, (int, float)) else str(x)


def main(path):
    score = json.loads(open(path).read())
    print(f"Verdict: **{score['verdict']}**. Rule A failures: {len(score['rule_a_failures'])}. "
          f"Rule B: {len(score['rule_b']['cases_with_req_covered_delta_ge_0'])} of 5 cases cover at least as "
          f"much requirement, sum of mean deltas {signed(score['rule_b']['sum_mean_delta'])} FTE "
          f"({'PASS' if score['rule_b']['pass'] else 'FAIL'}).\n")
    print("| Program | Seeds | Requirement covered at target (FTE) | Intervals at target | Intervals at floor "
          "| Severe floor gaps | Break-overlap violations | Price (rule C) |")
    print("|---|---|---|---|---|---|---|---|")
    for case, row in score["cases"].items():
        d = row["mean_delta"]
        per = ", ".join(signed(v, 0) for v in row["per_seed_delta"]["req_covered"])
        major = f" ({', '.join(row['major_on'])})" if row.get("major_on") else ""
        print(f"| {NAMES.get(case, case)} | {row['pairs']} | {signed(d['req_covered'])} (seeds: {per}) "
              f"| {signed(d['after_target'])} of {row['active_intervals']} | {signed(d['after_floor'])} "
              f"| {signed(d['severe_floor_gaps'])} | {signed(d['break_concurrency_violation_count'])} "
              f"| {row['price']}{major} |")


if __name__ == "__main__":
    main(sys.argv[1])
