"""Score the C4 impact A/B against C4_AB_RULE.txt (written and pushed before the runs).

    python3 c4_ab_score.py EVIDENCE_DIR C3_RUNS_ROOT OUT.json

EVIDENCE_DIR holds C4AB_<CASE>_<ARM>_<SEED>/RUN_RECORD.json (run_root points at
the run). AEIT INTERVAL comes from C3_RUNS_ROOT/C3_DEFAULT_<SEED> (the rule's
reuse). Every measure is computed from the independent validator's output."""
import json, statistics, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "engine" / "_tools"))
import l632_universal_scheduler as E  # noqa: E402

EVID, C3, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
CASES = ("VOICE", "CHAT", "NMGSP", "AEIT", "GDI")
SEEDS = (9000, 9001, 9002)  # 9002 only where C4_AB_AMENDMENTS.txt A2 called for it
METRICS = ("req_covered", "fte_gap", "after_target", "after_floor", "severe_floor_gaps", "language_gap_count",
           "zero_staffed_active_quarters", "break_concurrency_violation_count")


def measure(run_root: Path, return_code):
    row = {"run_root": str(run_root), "return_code": return_code}
    status = json.loads((run_root / "UNIVERSAL_RUN_STATUS.json").read_text()) if (run_root / "UNIVERSAL_RUN_STATUS.json").exists() else {}
    iv = status.get("independent_validation") or {}
    row["validation"] = iv.get("status")
    mism_rows = (iv.get("metric_parity") or {}).get("mismatches") or []
    row["parity_mismatch_fields"] = [m.get("field") for m in mism_rows]
    audit = next(iter(sorted(run_root.glob("*solver_audit.json"))), None)
    if audit is not None and mism_rows:
        # C4_AB_AMENDMENTS.txt A3: an F-35 parity failure is one where the polish
        # moved a shift and the engine's own RECOMMENDED_FINAL export metrics (the
        # published workbook) equal the validator's value on every mismatching
        # field the export records.
        a = json.loads(audit.read_text())
        moves = int(((a.get("shift_consistency_polish") or {}).get("moves")) or 0)
        export = next((e.get("metrics") or {} for e in ((a.get("export_manifest") or {}).get("exports") or [])
                       if e.get("role") == "RECOMMENDED_FINAL"), {})
        checked = [m for m in mism_rows if export.get(m.get("field")) is not None]
        same = bool(checked) and all(abs(float(export[m["field"]]) - float(m.get("validator") or 0)) <= 1e-6
                                     for m in checked)
        row["parity_f35_check"] = {"polish_moves": moves, "fields_checked": [m["field"] for m in checked],
                                   "export_equals_validator": same}
        row["parity_failure_is_f35"] = bool(moves >= 1 and same)
    row["parity"] = (iv.get("metric_parity") or {}).get("status")
    cr = iv.get("clean_room") or {}
    row["clean_room"] = cr.get("status"); row["clean_room_violations"] = cr.get("violation_count")
    vj = run_root / "INDEPENDENT_VALIDATION.json"
    if not vj.exists():
        row["error"] = "no INDEPENDENT_VALIDATION.json"; return row
    v = json.loads(vj.read_text())
    m = v.get("metrics") or {}
    target = float(E.parse_input(Path(v["input"])).target_ratio)
    rows = v.get("interval_rows") or []
    row["hard_fail_count"] = v.get("hard_fail_count")
    row["active_intervals"] = m.get("active_intervals")
    row["req_covered"] = round(sum(float(r["required"]) for r in rows if float(r["after_pct"]) + 1e-9 >= target), 3)
    row["fte_gap"] = round(sum(max(0.0, target * float(r["required"]) - float(r["after_effective"])) for r in rows), 3)
    row["after_target"] = m.get("after_target"); row["after_floor"] = m.get("after_floor")
    row["severe_floor_gaps"] = m.get("severe_floor_gaps")
    row["language_gap_count"] = m.get("language_gap_count")
    row["zero_staffed_active_quarters"] = m.get("zero_staffed_active_quarters")
    row["break_concurrency_violation_count"] = m.get("break_concurrency_violation_count")
    return row


runs = {}
for case in CASES:
    for seed in SEEDS:
        for arm in ("INTERVAL", "VOLUME"):
            if case == "AEIT" and arm == "INTERVAL":
                if seed == 9002 and not (EVID / f"C4AB_AEIT_VOLUME_{seed}" / "RUN_RECORD.json").exists():
                    continue
                c3 = C3 / f"C3_DEFAULT_{seed}"
                rec = json.loads((Path(sys.argv[1]).parent / "c3_runs" / f"C3_DEFAULT_{seed}" / "RUN_RECORD.json").read_text())
                runs[(case, arm, seed)] = measure(c3, rec.get("return_code")) | {"reused_from_c3": True}
                continue
            p = EVID / f"C4AB_{case}_{arm}_{seed}" / "RUN_RECORD.json"
            if not p.exists():
                if seed != 9002:
                    runs[(case, arm, seed)] = {"missing": True}
                continue
            rec = json.loads(p.read_text())
            runs[(case, arm, seed)] = measure(Path(rec["run_root"]), rec.get("return_code"))

rule_a = []
for (case, arm, seed), r in runs.items():
    if arm != "VOLUME":
        continue
    pair = runs.get((case, "INTERVAL", seed), {})
    problems = []
    if r.get("missing") or r.get("error"):
        problems.append(r.get("error") or "missing")
    else:
        if r.get("hard_fail_count") != 0: problems.append(f"hard_fail_count={r.get('hard_fail_count')}")
        if r.get("parity") != "PASS" and not r.get("parity_failure_is_f35"): problems.append(f"parity={r.get('parity')}")
        if r.get("clean_room") != "PASS" or r.get("clean_room_violations"): problems.append(f"clean_room={r.get('clean_room')}/{r.get('clean_room_violations')}")
        if r.get("language_gap_count"): problems.append(f"language_gaps={r.get('language_gap_count')}")
        if r.get("zero_staffed_active_quarters"): problems.append(f"zero_staffed={r.get('zero_staffed_active_quarters')}")
        if pair.get("return_code") == 0 and r.get("return_code") != 0 and not r.get("parity_failure_is_f35"):
            problems.append(f"exit {r.get('return_code')} where INTERVAL exits 0")
    if problems:
        rule_a.append({"case": case, "seed": seed, "problems": problems})

cases = {}
for case in CASES:
    deltas = {k: [] for k in METRICS}
    for seed in SEEDS:
        a, b = runs.get((case, "INTERVAL", seed), {}), runs.get((case, "VOLUME", seed), {})
        for k in METRICS:
            if isinstance(a.get(k), (int, float)) and isinstance(b.get(k), (int, float)):
                deltas[k].append(b[k] - a[k])
    mean = {k: (round(statistics.mean(v), 3) if v else None) for k, v in deltas.items()}
    active = next((runs[(case, arm, s)].get("active_intervals") for arm in ("INTERVAL", "VOLUME") for s in SEEDS
                   if runs.get((case, arm, s), {}).get("active_intervals")), None)
    major = []
    if mean["after_target"] is not None and active and -mean["after_target"] > 0.05 * active: major.append("after_target")
    if mean["after_floor"] is not None and -mean["after_floor"] > 3: major.append("after_floor")
    if mean["severe_floor_gaps"] is not None and mean["severe_floor_gaps"] > 3: major.append("severe_floor_gaps")
    if mean["break_concurrency_violation_count"] is not None and mean["break_concurrency_violation_count"] > 3: major.append("break_concurrency")
    def seed_major(i):
        out = []
        d = {k: (v[i] if i < len(v) else None) for k, v in deltas.items()}
        if d["after_target"] is not None and active and -d["after_target"] > 0.05 * active: out.append("after_target")
        if d["after_floor"] is not None and -d["after_floor"] > 3: out.append("after_floor")
        if d["severe_floor_gaps"] is not None and d["severe_floor_gaps"] > 3: out.append("severe_floor_gaps")
        if d["break_concurrency_violation_count"] is not None and d["break_concurrency_violation_count"] > 3: out.append("break_concurrency")
        return bool(out)
    rc = deltas["req_covered"][:2]
    third = []
    if len(rc) == 2 and rc[0] * rc[1] < 0: third.append("req_covered deltas of opposite signs")
    if len(deltas["req_covered"]) >= 2 and seed_major(0) != seed_major(1): third.append("seeds disagree on MINOR/MAJOR")
    if any(f["case"] == case for f in rule_a): third.append("a VOLUME run failed rule A")
    cases[case] = {"pairs": len(deltas["req_covered"]), "active_intervals": active, "mean_delta": mean,
                   "per_seed_delta": deltas, "price": "MAJOR" if major else "MINOR", "major_on": major,
                   "third_seed_needed": third if len(deltas["req_covered"]) < 3 else []}

b_pos = [c for c, v in cases.items() if v["mean_delta"]["req_covered"] is not None and v["mean_delta"]["req_covered"] >= 0]
b_sum = sum(v["mean_delta"]["req_covered"] or 0 for v in cases.values())
rule_b = len(b_pos) >= 4 and b_sum > 0
complete = all(v["pairs"] >= 2 and not v["third_seed_needed"] for v in cases.values())
verdict = ("INCOMPLETE" if not complete else "DEFECT" if rule_a else "CLOSE" if rule_b else "NOT_EFFECTIVE")
out = {"rule": "C4_AB_RULE.txt", "verdict": verdict, "rule_a_failures": rule_a,
       "rule_b": {"cases_with_req_covered_delta_ge_0": b_pos, "sum_mean_delta": round(b_sum, 3), "pass": rule_b},
       "cases": cases, "runs": {f"{c}_{a}_{s}": r for (c, a, s), r in runs.items()}}
OUT.write_text(json.dumps(out, indent=1, default=str))
print(json.dumps({"verdict": verdict, "rule_a_failures": rule_a, "rule_b": out["rule_b"]}, default=str))
for c, v in cases.items():
    print(c, v["price"], v["major_on"], v["mean_delta"])
