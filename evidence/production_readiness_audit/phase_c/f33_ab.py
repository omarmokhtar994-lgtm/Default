"""F-33 A/B (F33_RULE.txt): Stage-2 break placement, OLD vs NEW engine, same skeleton/seed/time.

    python3 f33_ab.py SCRATCH OLD_ENGINE_ROOT OUT.json
Resumable: finished (case, mode, seed, arm) rows in OUT.json are kept."""
import importlib.util, io, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

SCRATCH, OLD_ROOT, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3])
CASES = {
    "VOICE": "phaseB_real/VOICE_PHASE_B",
    "CHAT": "f16/results_chat/CRICUT_CHAT",
    "AEIT": "aeit/out/FINAL_AEIT_9002_R",
    "H1": "f16/results_h1/SYNTH_H1_24X7_OVERNIGHT",
    "S08": "advB/runs/S08_24x7_WEEK_BOUNDARY",
}
MODES = ("target_priority", "release_quality_guard")
SEEDS = range(9000, 9005)
KEYS = ("after_target", "after_floor", "whole_week_imbalance_violation_count",
        "break_concurrency_violation_count", "zero_staffed_active_quarters", "language_gap_count")


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod


def job(args):
    case, mode, seed, arm, slot = args
    os.sched_setaffinity(0, {0, 1} if slot == 0 else {2, 3})
    repo = Path.cwd()
    sys.path.insert(0, str(repo / "engine" / "_tools"))
    E = load((OLD_ROOT if arm == "OLD" else str(repo)) + "/engine/_tools/l632_universal_scheduler.py", f"eng_{arm}")
    IV = load(str(repo / "engine/tools/independent_validator.py"), "iv_ab")
    root = Path(SCRATCH) / CASES[case]
    inp = sorted((root / "input_snapshot").glob("*.xlsx"))[0]
    out = sorted((root / "production").glob("*BEST_FINAL*.xlsx"))[0]
    parsed = E.parse_input(inp)
    sched, _ = IV.parse_output_schedule(out, [a.name for a in parsed.associates])
    idx = {E.norm(s.label): s.index for s in parsed.shifts}
    assignment = [["OFF" if E.norm(v) == "off" else "Leave" if E.norm(v) in ("leave", "pto", "vacation") else v
                   for v in sched[E.norm(a.name)]] for a in parsed.associates]
    selected = [[idx.get(E.norm(v)) for v in sched[E.norm(a.name)]] for a in parsed.associates]
    sk = E.SkeletonSolution("replay", "FEASIBLE", 0.0, 0.0, assignment, selected, {})
    E.ensure_before_break_metrics(parsed, sk)
    t = time.time()
    sol = E.solve_breaks(parsed, sk, 60, False, 60, 2, io.StringIO(), objective_mode=mode, random_seed=seed)
    row = {"case": case, "mode": mode, "seed": seed, "arm": arm, "status": sol.cp_status,
           "elapsed": round(time.time() - t, 1)}
    if sol.cp_status in ("OPTIMAL", "FEASIBLE"):
        row.update({k: sol.metrics.get(k) for k in KEYS})
    return row


def main():
    done = json.loads(OUT.read_text()) if OUT.exists() else []
    have = {(r["case"], r["mode"], r["seed"], r["arm"]) for r in done}
    jobs = [(c, m, s, a) for c in CASES for m in MODES for s in SEEDS for a in ("OLD", "NEW")
            if (c, m, s, a) not in have]
    with ProcessPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(job, (*j, i % 2)) for i, j in enumerate(jobs)]
        for f in futures:
            row = f.result(); done.append(row)
            OUT.write_text(json.dumps(done, indent=1))
            print(json.dumps(row), flush=True)


if __name__ == "__main__":
    main()
