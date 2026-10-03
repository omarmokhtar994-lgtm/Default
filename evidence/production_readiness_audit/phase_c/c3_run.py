"""C3 driver (C3_RULE.txt): AE_IT_B2B, DEFAULT vs S240, seeds 9000-9004, QUICK 3600 s.

    python3 c3_run.py FROZEN_REPO WORK_DIR EVIDENCE_DIR
FROZEN_REPO holds the engine/ and tools/ the runs use (a copy taken before the
first run, so later edits in the working tree cannot reach a running arm).
Two runs at a time, each pinned to a free core pair, {0,1} or {2,3} (a run takes
whichever pair the previous run released, so two runs never share a pair). Resumable: a run whose
EVIDENCE_DIR/<ID>/RUN_RECORD.json exists is skipped."""
import json, os, queue, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

FROZEN, WORK, EVID = (Path(a).resolve() for a in sys.argv[1:4])
REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "experiments" / "rc5_vs_final" / "inputs" / "AE_IT_B2B.xlsx"
SEEDS = range(9000, 9005)
SLOTS = ({0, 1}, {2, 3})
FREE = queue.Queue()
for _slot in range(len(SLOTS)):
    FREE.put(_slot)


def s240_copy() -> Path:
    from openpyxl import load_workbook
    out = WORK / "inputs" / "AE_IT_B2B_S240.xlsx"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        wb = load_workbook(SOURCE)
        ws = wb["Engine Defaults"]
        header = [ws.cell(4, c).value for c in range(1, 4)]
        assert header == ["Section", "Instruction", "Value"], header
        # Same layout as the sheet's own rows: Section | Instruction | Value.
        ws.append(["C3 arm S240", "Stage 1 Minimum Slice Seconds", 240])
        wb.save(out)
        (WORK / "inputs" / "S240_HEADER.json").write_text(json.dumps(header))
    return out


def run(job):
    arm, seed = job
    rid = f"C3_{arm}_{seed}"
    if (EVID / rid / "RUN_RECORD.json").exists():
        return rid, "skipped"
    slot = FREE.get()
    try:
        return _run(arm, seed, rid, slot)
    finally:
        FREE.put(slot)


def _run(arm, seed, rid, slot):
    rec_dir = EVID / rid
    inp = SOURCE if arm == "DEFAULT" else s240_copy()
    root = WORK / "runs"
    shutil.rmtree(root / rid, ignore_errors=True)
    cmd = [sys.executable, "-u", str(FROZEN / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"), "--input", str(inp),
           "--output-root", str(root), "--schedule-id", rid, "--mode", "QUICK", "--time-limit", "3600",
           "--num-workers", "2", "--solver-random-seed", str(seed)]
    started = time.time()
    with open(WORK / f"{rid}.log", "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT,
                                preexec_fn=lambda: os.sched_setaffinity(0, SLOTS[slot]))
        rc = proc.wait()
    case = root / rid
    rec_dir.mkdir(parents=True, exist_ok=True)
    for name in ("UNIVERSAL_RUN_STATUS.json", "BUSINESS_OUTCOME.txt", "UNIVERSAL_RUN_IDENTITY.json"):
        if (case / name).exists():
            shutil.copy(case / name, rec_dir / name)
    status = json.loads((case / "UNIVERSAL_RUN_STATUS.json").read_text()) if (case / "UNIVERSAL_RUN_STATUS.json").exists() else {}
    audit = next(iter(sorted(case.glob("*solver_audit.json"))), None)
    a = json.loads(audit.read_text()) if audit else {}
    m = (a.get("selected_candidate") or {}).get("metrics") or {}
    record = {
        "arm": arm, "seed": seed, "cores": sorted(SLOTS[slot]), "return_code": rc, "wall_sec": round(time.time() - started, 1),
        "validation": (status.get("independent_validation") or {}).get("status"),
        "parity": ((status.get("independent_validation") or {}).get("metric_parity") or {}).get("status"),
        "after_target": m.get("after_target"), "after_floor": m.get("after_floor"),
        "before_target": m.get("before_target"), "before_floor": m.get("before_floor"),
        "severe_floor_gap_count": m.get("severe_floor_gap_count"),
        "break_concurrency_violation_count": m.get("break_concurrency_violation_count"),
        "stage1_profile_coverage": a.get("stage1_profile_coverage"),
        "stage1_attempts": len(a.get("stage1_attempts") or []),
        "global_budget": a.get("global_budget"),
        "engine_elapsed_sec": a.get("elapsed_sec"),
    }
    (rec_dir / "RUN_RECORD.json").write_text(json.dumps(record, indent=1, default=str))
    for heavy in ("debug",):
        shutil.rmtree(case / heavy, ignore_errors=True)
    return rid, record


def main():
    EVID.mkdir(parents=True, exist_ok=True)
    s240_copy()  # made once, before any run starts
    jobs = [(arm, seed) for seed in SEEDS for arm in ("DEFAULT", "S240")]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, job) for job in jobs]
        for f in futures:
            rid, rec = f.result()
            print(rid, json.dumps(rec, default=str)[:400], flush=True)


if __name__ == "__main__":
    main()
