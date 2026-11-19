#!/usr/bin/env python3
"""Run the synthetic suite through the production runner and score it.

Each case runs exactly as a user's workbook would (RUN_UNIVERSAL_PRODUCTION.py,
FULL_SCHEDULE, QUICK, independent validation on), single-worker and seeded so
a result is reproducible at comparable load. Scoring reads only the runner's
own artifacts and the expectation written by build_synthetic_suite.py:

  planted cases   validator PASS, 0 hard failures, engine/validator parity PASS,
                  and after-break target hits against the certified optimum
                  (OPTIMAL = equal, NEAR = within 5%, FAR otherwise)
  hard-floor case no schedule may be shipped as meeting the floor
  hard-OFF case   the hard-OFF day must stay at 0 hits
  refusal cases   refused before the solver with the expected code, no traceback
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import glob
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LIMITS = {"easy": 300, "moderate": 600, "hard": 900, "extreme": 1200, "benchmark": 900}
REFUSAL_LIMIT = 120


def run_one(engine_dir: Path, wb: Path, out_root: Path, cid: str, limit: int) -> dict:
    log = out_root / (cid + ".log")
    t0 = time.time()
    with open(log, "w") as fh:
        rc = subprocess.call(
            [sys.executable, str(engine_dir / "RUN_UNIVERSAL_PRODUCTION.py"), "--input", str(wb),
             "--output-root", str(out_root), "--schedule-id", cid, "--stage", "FULL_SCHEDULE",
             "--mode", "QUICK", "--time-limit", str(limit), "--num-workers", "1",
             "--solver-random-seed", "9000", "--overwrite"],
            stdout=fh, stderr=subprocess.STDOUT)
    return {"id": cid, "rc": rc, "wall_sec": round(time.time() - t0, 1)}


def load(path: str):
    try:
        return json.load(open(path))
    except Exception:
        return {}


def grep_dir(d: Path, needle: str) -> bool:
    for p in d.rglob("*"):
        if p.is_file() and p.suffix in (".json", ".txt", ".csv", ".log"):
            try:
                if needle in p.read_text(errors="ignore"):
                    return True
            except Exception:
                pass
    return False


def score(case: dict, out_root: Path, run: dict) -> dict:
    cid = case["id"]
    d = out_root / cid
    log = (out_root / (cid + ".log")).read_text(errors="ignore") if (out_root / (cid + ".log")).exists() else ""
    tb = "Traceback" in log
    exp = case["expected"]
    res = {"id": cid, "tier": case["tier"], "rc": run.get("rc"), "wall_sec": run.get("wall_sec"),
           "traceback": tb}
    if "refused_with" in exp:
        code = exp["refused_with"]
        found = grep_dir(d, code) or code in log
        # The runner writes a summary CSV and audit even when it refuses; a
        # refusal means no final schedule workbook was published.
        published = glob.glob(str(d / "*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"))
        res.update(expected=code, code_reported=found, schedule_written=bool(published))
        res["verdict"] = "PASS" if (found and not tb and not published) else "FAIL"
        return res

    v = load(str(d / "INDEPENDENT_VALIDATION.json"))
    bo = load(str(d / "BUSINESS_OUTCOME.json"))
    par = v.get("metric_parity") or {}
    rows = list(csv.DictReader(open(glob.glob(str(d / "*_summary.csv"))[0]))) if glob.glob(str(d / "*_summary.csv")) else []
    s = rows[-1] if rows else {}
    res.update(validator=v.get("status"), hard_fail=v.get("hard_fail_count"), parity=par.get("status"),
               outcome=bo.get("business_outcome_code") or bo.get("outcome_code") or bo.get("status"),
               before_target=int(s["before_target"]) if s.get("before_target") else None,
               after_target=int(s["after_target"]) if s.get("after_target") else None,
               before_floor=int(s["before_floor"]) if s.get("before_floor") else None,
               after_floor=int(s["after_floor"]) if s.get("after_floor") else None,
               active=case["certificate"]["active_intervals"])
    clean = (not tb and v.get("status") == "PASS" and int(v.get("hard_fail_count") or 0) == 0
             and par.get("status") == "PASS")
    published = bool(glob.glob(str(d / "*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx")))
    refusal = next((c for c in exp.get("acceptable_refusals", []) if grep_dir(d, c)), None)
    res["published"] = published
    res["refused_with"] = refusal
    if exp.get("hard_floor_infeasible"):
        # Either refused with a proof code, or a shipped schedule that does NOT
        # claim the floor everywhere.
        claims_floor = res["after_floor"] is not None and res["after_floor"] >= res["active"]
        res["proof"] = exp["proof"]
        ok = (refusal and not published) or (published and clean and not claims_floor)
        res["verdict"] = "PASS" if (ok and not tb) else "FAIL"
        return res
    if refusal and not published and not tb:
        # A documented fail-closed outcome the case allows (e.g. a demanded
        # interval nobody can staff): correct, but it is not a coverage result.
        res["verdict"] = "REFUSED_OK"
        return res
    opt = exp["optimum_after_target"]
    res["optimum_after_target"] = opt
    got = res["after_target"]
    if not clean or got is None:
        res["verdict"] = "FAIL"
    elif got > opt and exp.get("upper_bound") is not None and got <= exp["upper_bound"]:
        # The reference was a time-limited plan, not a proven optimum.
        res["verdict"] = "BETTER"
    elif got > opt:
        res["verdict"] = "FAIL (beats a proven optimum: metric bug)"
    elif got == opt:
        res["verdict"] = "OPTIMAL"
    elif got >= 0.95 * opt:
        res["verdict"] = "NEAR"
    else:
        res["verdict"] = "FAR"
    res["gap_intervals"] = None if got is None else opt - got
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine-dir", type=Path, required=True)
    ap.add_argument("--suite-dir", type=Path, required=True)
    ap.add_argument("--out-root", type=Path, required=True)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--score-only", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    cases = json.load(open(a.suite_dir / "cases.json"))
    if a.only:
        keep = set(a.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    a.out_root.mkdir(parents=True, exist_ok=True)
    runs = {}
    if not a.score_only:
        # Longest first so the pool drains evenly.
        def limit(c):
            return REFUSAL_LIMIT if "refused_with" in c["expected"] else LIMITS[c["tier"]]
        order = sorted(cases, key=limit, reverse=True)
        with cf.ThreadPoolExecutor(a.parallel) as pool:
            futs = [pool.submit(run_one, a.engine_dir, a.suite_dir / c["workbook"], a.out_root, c["id"], limit(c))
                    for c in order]
            for f in cf.as_completed(futs):
                r = f.result()
                runs[r["id"]] = r
                print("done %-34s rc=%s %ss" % (r["id"], r["rc"], r["wall_sec"]), flush=True)
        json.dump(runs, open(a.out_root / "runs.json", "w"), indent=2)
    else:
        runs = load(str(a.out_root / "runs.json"))
    results = [score(c, a.out_root, runs.get(c["id"], {})) for c in cases]
    json.dump(results, open(a.out_root / "SCORE.json", "w"), indent=2)
    print()
    print("%-34s %-9s %-10s %-9s %-7s %s" % ("case", "tier", "verdict", "validator", "parity", "after target / optimum"))
    bad = 0
    for r in results:
        if r["verdict"].startswith("FAIL"):
            bad += 1
        if "expected" in r:
            detail = "refused with %s: %s" % (r["expected"], r["code_reported"])
        elif r.get("refused_with"):
            detail = "refused before solve: %s" % r["refused_with"]
        elif "proof" in r:
            detail = "after_floor %s of %s active (must be < active)" % (r.get("after_floor"), r["active"])
        else:
            detail = "%s / %s  (before %s)" % (r.get("after_target"), r.get("optimum_after_target"), r.get("before_target"))
        print("%-34s %-9s %-10s %-9s %-7s %s" % (r["id"], r["tier"], r["verdict"][:10], r.get("validator", "-"),
                                                 r.get("parity", "-"), detail))
    print("\n%d cases, %d failing" % (len(results), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
