#!/usr/bin/env python3
"""Stage-1-only A/B probe (Phase E). Report-only; changes no engine file.

Runs the engine's own Stage 1 (`build_skeleton`, production hard rules, the
aggregate guide as production passes it, no hint) for named profiles, arms
and seeds, and scores each week with `calculate_metrics` before breaks: the
quantity a Stage-1 change acts on, without the hour of Stage 2, repairs and
selection that a production run wraps around it.

Arms: "off" = workbook as is; "on" = the same parse with one instruction
attribute set (e.g. exact_coverage_units=True), equivalent to the workbook row.
Time mode (--seconds-on): no attribute; "on" only gets a longer Stage-1 slice.

    python3 tools/stage1_ab_probe.py --engine ENGINE --out OUT.json --attr exact_coverage_units \
        --profiles target90_restore_champion,target_floor_pareto_master --seeds 9000,9001,9002 \
        --seconds 45 --workers 2 --parallel 2 WORKBOOK.xlsx [...]
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _solve(args):
    engine, wb, attr, arm, profile_name, seed, seconds, workers = args
    import build_synthetic_suite as S
    E = S.load_engine(Path(engine))
    p = E.parse_input(Path(wb))
    if arm == "on" and attr:
        p = copy.copy(p)
        setattr(p, attr, True)
    guide = E.aggregate_pattern_mix_guidance(p, time_limit_sec=30.0)
    profile = next(pr for pr in E.skeleton_profiles([profile_name]) if pr["name"] == profile_name)
    hard = E.HardConfig(hard_floor=(p.floor_mode == "hard"))
    t0 = time.time()
    sk = E.build_skeleton(p, dict(profile), hard, float(seconds), int(workers), None,
                          random_seed=int(seed), aggregate_guidance=guide)
    row = {"workbook": Path(wb).name, "arm": arm, "profile": profile_name, "seed": seed,
           "cp_status": sk.cp_status, "seconds": round(time.time() - t0, 1),
           "guide_status": guide.get("status")}
    if sk.cp_status in ("OPTIMAL", "FEASIBLE"):
        m = E.calculate_metrics(p, sk, {}, E.generate_break_patterns(p))
        row.update(active=m["active_intervals"], before_target=m["before_target"], before_floor=m["before_floor"])
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--attr", default="")
    ap.add_argument("--seconds-on", type=float, default=None,
                    help="time mode: the 'on' arm's Stage-1 seconds (no attribute is set)")
    ap.add_argument("--profiles", required=True)
    ap.add_argument("--seeds", default="9000,9001,9002")
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("workbooks", nargs="+")
    a = ap.parse_args()
    if not a.attr and a.seconds_on is None:
        ap.error("give --attr or --seconds-on")
    secs = {"off": a.seconds, "on": a.seconds_on if a.seconds_on is not None else a.seconds}
    jobs = [(a.engine, wb, a.attr, arm, pr, int(s), secs[arm], a.workers)
            for wb in a.workbooks for pr in a.profiles.split(",") for s in a.seeds.split(",") for arm in ("off", "on")]
    rows = []
    with ProcessPoolExecutor(max_workers=a.parallel) as ex:
        for row in ex.map(_solve, jobs):
            rows.append(row)
            print(json.dumps(row), flush=True)
            a.out.parent.mkdir(parents=True, exist_ok=True)
            a.out.write_text(json.dumps({"attr": a.attr, "rows": rows}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
