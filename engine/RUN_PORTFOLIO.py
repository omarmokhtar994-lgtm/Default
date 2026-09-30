#!/usr/bin/env python3
"""Multi-seed portfolio runner: run the production runner with several solver
seeds and keep the best validated result.

Why: on identical input the engine's result varies with the solver seed far
more than with extra time. Measured on the final engine (evidence/
SEED_PORTFOLIO_EVIDENCE.md): Cricut Chat after_target 167-182 across seeds,
while going from 900 s to 3,600 s left the mean unchanged (176.0 vs 176.3).
Keeping the best of several seeds takes that spread as gain.

What it guarantees:
* Every seed is a complete, independent RUN_UNIVERSAL_PRODUCTION.py run in its
  own folder under <output-root>/<schedule-id>/seeds/. Nothing in those folders
  is modified.
* A seed is eligible only if its production run exited 0, its final schedule
  passed independent validation with 0 hard failures and metric parity PASS,
  and its summary says production_eligible TRUE. Quality warnings do not block:
  every measured run carries them (PASS_WITH_QUALITY_WARNINGS).
* The after-breaks winner is the best eligible seed. The before-breaks sheet is
  chosen separately, as the best before-breaks sheet among the same eligible
  seeds, so it is never worse than any eligible seed's own. A seed that failed
  validation or crashed contributes neither sheet (audit F-04 / H-05).
* PORTFOLIO_BEST/ holds copies of the two winning workbooks, renamed
  AFTER_BREAKS_BEST__S<seed>__... and BEFORE_BREAKS_BEST__S<seed>__..., the
  winning run's validation, and PORTFOLIO_BEST_MANIFEST.json naming each
  file's seed, source path and sha256 (audit M-08). PORTFOLIO_SUMMARY.json/.csv
  list every seed with its return code.
* Seeds must be distinct: a repeated seed would silently rerun into, and
  overwrite, the same folder (audit H-06).

Seeds run one after another by default (each keeps all its workers); pass
--parallel to run several at once when there are enough cores.

--preset DEEP / OVERNIGHT: the measured replacement for one long run
(evidence/seed_portfolio_ab/RESULT.txt, rule registered before the runs). The
best of four 1 h QUICK seeds tied one 4 h DEEP run wherever that run finished
and the DEEP run produced no schedule on two of four cases (killed at 13-14 GB
in joint refinement). DEEP = 4 x 3600 s QUICK seeds, OVERNIGHT = 6 x 3600 s.
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "RUN_UNIVERSAL_PRODUCTION.py"
DEFAULT_BASE_SEED = 9000
PRESET_SEEDS = {"DEEP": 4, "OVERNIGHT": 6}
PRESET_SEED_ARGS = ["--mode", "QUICK", "--time-limit", "3600"]

# After-breaks ranking across seeds, most important first. Target coverage is
# the production objective; the rest only break ties.
AFTER_KEY = (
    ("after_target", +1), ("after_floor", +1), ("after90", +1), ("after80", +1),
    ("after_severe_overage_count", -1), ("after_avoidable_overage_fte_sum", -1),
)
BEFORE_KEY = (("best_before_target", +1), ("best_before_floor", +1))


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def read_seed_result(run_dir: Path, return_code: Optional[int] = None) -> Dict[str, Any]:
    """Collect one seed run's outcome from its own artifacts and its exit code."""
    out: Dict[str, Any] = {"run_dir": str(run_dir), "return_code": return_code,
                           "finished": False, "after_eligible": False}
    summaries = sorted(glob.glob(str(run_dir / "*_summary.csv")))
    if not summaries:
        return out
    with open(summaries[0], encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return out
    summary = rows[-1]
    out["finished"] = True
    out["summary"] = {k: summary.get(k) for k in (
        [k for k, _ in AFTER_KEY] + [k for k, _ in BEFORE_KEY]
        + ["before_target", "before_floor", "status", "production_eligible"])}
    validation_path = run_dir / "INDEPENDENT_VALIDATION.json"
    validation: Dict[str, Any] = {}
    if validation_path.exists():
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    parity = (validation.get("metric_parity") or {}).get("status")
    out["validation"] = {
        "status": validation.get("status"),
        "hard_fail_count": validation.get("hard_fail_count"),
        "metric_parity": parity,
    }
    out["final_workbook"] = next(iter(sorted(glob.glob(str(run_dir / "production" / "*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx")))), None)
    out["before_workbook"] = next(iter(sorted(glob.glob(str(run_dir / "production" / "*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx")))), None) \
        or next(iter(sorted(glob.glob(str(run_dir / "*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx")))), None)
    out["after_eligible"] = bool(
        return_code == 0
        and out["final_workbook"]
        and str(summary.get("production_eligible") or "").strip().upper() == "TRUE"
        and validation.get("status") == "PASS"
        and int(validation.get("hard_fail_count") or 0) == 0
        and parity == "PASS"
        and summary.get("after_target") not in (None, "")
    )
    return out


def _key(result: Dict[str, Any], spec) -> tuple:
    s = result.get("summary") or {}
    return tuple(sign * _num(s.get(name)) for name, sign in spec)


def choose_winners(results: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Best eligible after-breaks run, and best before-breaks run of the eligible seeds."""
    after_pool = [r for r in results if r.get("after_eligible")]
    before_pool = [r for r in after_pool if r.get("before_workbook")]
    after = max(after_pool, key=lambda r: _key(r, AFTER_KEY)) if after_pool else None
    before = max(before_pool, key=lambda r: _key(r, BEFORE_KEY)) if before_pool else None
    return {"after": after, "before": before}


def seed_list(count: int, base: int, explicit: Optional[str]) -> List[int]:
    if explicit:
        seeds = [int(x) for x in explicit.split(",") if x.strip()]
        repeated = sorted({s for s in seeds if seeds.count(s) > 1})
        if repeated:
            raise ValueError(f"--seed-list repeats seed(s) {repeated}; each seed must be distinct")
        if not seeds:
            raise ValueError("--seed-list names no seeds")
        return seeds
    return [base + i for i in range(max(1, count))]


def run_seed(seed: int, schedule_id: str, seeds_root: Path, passthrough: List[str],
             log_dir: Path) -> Tuple[Path, int]:
    run_id = f"{schedule_id}_S{seed}"
    cmd = [sys.executable, str(RUNNER), *passthrough,
           "--output-root", str(seeds_root), "--schedule-id", run_id,
           "--solver-random-seed", str(seed), "--overwrite"]
    started = time.time()
    with open(log_dir / f"{run_id}.log", "w", encoding="utf-8") as log:
        rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
    print(f"[portfolio] seed {seed} finished rc={rc} in {time.time() - started:.0f}s", flush=True)
    return seeds_root / run_id, rc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def publish_best(best_dir: Path, winners: Dict[str, Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Copy the winning workbooks under seed-labelled names and record provenance."""
    if best_dir.exists():
        shutil.rmtree(best_dir)
    best_dir.mkdir(parents=True)
    manifest: Dict[str, Any] = {}
    for slot, field, label in (("after", "final_workbook", "AFTER_BREAKS_BEST"),
                               ("before", "before_workbook", "BEFORE_BREAKS_BEST")):
        winner = winners[slot]
        if not winner:
            manifest[slot] = None
            continue
        source = Path(winner[field])
        target = best_dir / f"{label}__S{winner['seed']}__{source.name}"
        shutil.copy2(source, target)
        manifest[slot] = {"seed": winner["seed"], "file": target.name, "source": str(source),
                          "sha256": _sha256(target), "run_dir": winner["run_dir"]}
    if winners["after"]:
        validation = Path(winners["after"]["run_dir"]) / "INDEPENDENT_VALIDATION.json"
        shutil.copy2(validation, best_dir / "INDEPENDENT_VALIDATION_OF_BEST_FINAL.json")
        manifest["after"]["validation_sha256"] = _sha256(validation)
    (best_dir / "PORTFOLIO_BEST_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0], add_help=True)
    p.add_argument("--seeds", type=int, default=0,
                   help="Number of seeds to run (default 1 = a single ordinary run; with --preset, the preset's count).")
    p.add_argument("--diversify-profiles", action="store_true",
                   help="Give each seed a different Stage-1 profile order (first profiles fixed, "
                        "the rest rotated) so the portfolio covers every profile.")
    p.add_argument("--preset", choices=sorted(PRESET_SEEDS),
                   help="DEEP = best of 4 x 1 h QUICK seeds, OVERNIGHT = best of 6 (measured defaults).")
    p.add_argument("--seed-list", help="Explicit comma-separated seeds; overrides --seeds.")
    p.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    p.add_argument("--parallel", type=int, default=1,
                   help="Seeds to run at once. Each keeps --num-workers, so only raise this when "
                        "cores >= parallel x workers.")
    p.add_argument("--output-root", type=Path, default=ROOT / "results")
    p.add_argument("--schedule-id", required=True)
    args, passthrough = p.parse_known_args(argv)
    for forbidden in ("--output-root", "--schedule-id", "--solver-random-seed"):
        if forbidden in passthrough:
            p.error(f"{forbidden} is set by the portfolio runner")
    if args.preset:
        for clash in ("--mode", "--time-limit"):
            if clash in passthrough:
                p.error(f"{clash} is set by --preset {args.preset} (each seed: {' '.join(PRESET_SEED_ARGS)})")
        passthrough = list(passthrough) + PRESET_SEED_ARGS
    count = args.seeds or (PRESET_SEEDS[args.preset] if args.preset else 1)
    try:
        seeds = seed_list(count, args.base_seed, args.seed_list)
    except ValueError as exc:
        p.error(str(exc))
    case_root = args.output_root / args.schedule_id
    seeds_root = case_root / "seeds"
    seeds_root.mkdir(parents=True, exist_ok=True)
    print(f"[portfolio] {args.schedule_id}: seeds {seeds}, parallel {args.parallel}", flush=True)
    def seed_arguments(index: int) -> List[str]:
        if args.diversify_profiles and len(seeds) > 1 and "--skeleton-profiles" not in passthrough:
            return list(passthrough) + ["--stage1-profile-rotation", f"{index}/{len(seeds)}"]
        return list(passthrough)

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        runs = list(pool.map(lambda item: run_seed(item[1], args.schedule_id, seeds_root, seed_arguments(item[0]), case_root),
                             enumerate(seeds)))
    results = []
    for seed, (run_dir, rc) in zip(seeds, runs):
        r = read_seed_result(run_dir, rc)
        r["seed"] = seed
        results.append(r)
    winners = choose_winners(results)
    best_manifest = publish_best(case_root / "PORTFOLIO_BEST", winners)
    summary = {
        "schedule_id": args.schedule_id,
        "seeds": seeds,
        "preset": args.preset,
        "diversify_profiles": bool(args.diversify_profiles),
        "passthrough_arguments": passthrough,
        "after_breaks_winner_seed": winners["after"]["seed"] if winners["after"] else None,
        "before_breaks_winner_seed": winners["before"]["seed"] if winners["before"] else None,
        "after_ranking": [k for k, _ in AFTER_KEY],
        "before_ranking": [k for k, _ in BEFORE_KEY],
        "eligibility": "return code 0, validator PASS, 0 hard failures, parity PASS, production_eligible TRUE",
        "best": best_manifest,
        "runs": results,
        "status": "OK" if winners["after"] else "NO_VALIDATED_FINAL_SCHEDULE",
    }
    (case_root / "PORTFOLIO_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(case_root / "PORTFOLIO_SUMMARY.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "return_code", "finished", "after_eligible", "after_target", "after_floor", "best_before_target",
                    "validator", "hard_fail_count", "parity", "after_winner", "before_winner"])
        for r in results:
            s = r.get("summary") or {}
            v = r.get("validation") or {}
            w.writerow([r["seed"], r.get("return_code"), r["finished"], r["after_eligible"], s.get("after_target"), s.get("after_floor"),
                        s.get("best_before_target"), v.get("status"), v.get("hard_fail_count"), v.get("metric_parity"),
                        r is winners["after"], r is winners["before"]])
    if winners["after"]:
        a, b = winners["after"], winners["before"]
        print(f"[portfolio] best after-breaks: seed {a['seed']} after_target {a['summary']['after_target']}; "
              f"best before-breaks: seed {b['seed'] if b else None} "
              f"{(b or {}).get('summary', {}).get('best_before_target')}", flush=True)
        return 0
    print("[portfolio] no seed produced a validated final schedule", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
