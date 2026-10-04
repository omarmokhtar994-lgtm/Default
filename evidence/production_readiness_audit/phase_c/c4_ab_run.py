"""C4 impact A/B driver (C4_AB_RULE.txt): Interval Count vs Volume Weighted.

    python3 c4_ab_run.py FROZEN_REPO WORK_DIR EVIDENCE_DIR

Waits until FROZEN_REPO/engine exists (the release engine, copied before the
first run). Two runs at a time, each on a free core pair, {0,1} or {2,3}.
Resumable: a run whose EVIDENCE_DIR/<ID>/RUN_RECORD.json exists is skipped.
AEIT INTERVAL is not run here: the rule reuses the C3 DEFAULT runs."""
import json, os, queue, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FROZEN, WORK, EVID = (Path(a).resolve() for a in sys.argv[1:4])
REPO = Path(__file__).resolve().parents[3]
INPUTS = REPO / "experiments" / "rc5_vs_final" / "inputs"
CASES = {
    "VOICE": INPUTS / "Cricut_Voice_RC9_1_READY_SKELETON.xlsx",
    "CHAT": INPUTS / "Cricut_Chat_RC9_1_READY_SKELETON.xlsx",
    "NMGSP": INPUTS / "NMG_SP_RC9_1_READY_FIXED.xlsx",
    "AEIT": INPUTS / "AE_IT_B2B.xlsx",
    "GDI": REPO / "packages" / "rc9_2_2_production" / "inputs" / "GDI_REAL28_RC9_1_24_7_FINAL_READY.xlsx",
}
SEEDS = (9000, 9001, 9002)
ARMS = ("INTERVAL", "VOLUME")
SLOTS = ({0, 1}, {2, 3})
FREE = queue.Queue()
for _slot in range(len(SLOTS)):
    FREE.put(_slot)


def run(job):
    case, arm, seed = job
    rid = f"C4AB_{case}_{arm}_{seed}"
    if (EVID / rid / "RUN_RECORD.json").exists():
        return rid, "skipped"
    slot = FREE.get()
    try:
        return _run(case, arm, seed, rid, slot)
    finally:
        FREE.put(slot)


def _run(case, arm, seed, rid, slot):
    root = WORK / "runs"
    shutil.rmtree(root / rid, ignore_errors=True)
    cmd = [sys.executable, "-u", str(FROZEN / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"), "--input", str(CASES[case]),
           "--output-root", str(root), "--schedule-id", rid, "--mode", "QUICK", "--time-limit", "3600",
           "--num-workers", "2", "--solver-random-seed", str(seed)]
    if arm == "VOLUME":
        cmd += ["--coverage-objective-weighting", "VOLUME_WEIGHTED"]
    started = time.time()
    with open(WORK / f"{rid}.log", "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                preexec_fn=lambda: os.sched_setaffinity(0, SLOTS[slot]))
        try:
            rc = proc.wait(timeout=3600 + 2400)
        except subprocess.TimeoutExpired:
            proc.kill()
            rc = "TIMEOUT"
    rec_dir = EVID / rid
    rec_dir.mkdir(parents=True, exist_ok=True)
    case_root = root / rid
    for name in ("UNIVERSAL_RUN_STATUS.json", "BUSINESS_OUTCOME.txt", "UNIVERSAL_RUN_IDENTITY.json"):
        if (case_root / name).exists():
            shutil.copy(case_root / name, rec_dir / name)
    record = {"case": case, "arm": arm, "seed": seed, "cores": sorted(SLOTS[slot]), "return_code": rc,
              "wall_sec": round(time.time() - started, 1), "run_root": str(case_root),
              "command": cmd}
    (rec_dir / "RUN_RECORD.json").write_text(json.dumps(record, indent=1, default=str))
    shutil.rmtree(case_root / "debug", ignore_errors=True)
    return rid, record


def main():
    while not (FROZEN / "engine" / "RUN_UNIVERSAL_PRODUCTION.py").exists():
        time.sleep(30)
    EVID.mkdir(parents=True, exist_ok=True)
    jobs = [(case, arm, seed) for seed in SEEDS for case in CASES for arm in ARMS
            if not (case == "AEIT" and arm == "INTERVAL")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for rid, rec in pool.map(run, jobs):
            print(rid, json.dumps(rec, default=str)[:300], flush=True)


if __name__ == "__main__":
    main()
