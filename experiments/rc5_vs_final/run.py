#!/usr/bin/env python3
"""Driver for the RC5 vs FINAL confirmation experiment (PREREGISTERED_RULE.txt).

    python3 experiments/rc5_vs_final/run.py --work SCRATCH_DIR [--limit N]

Resumable: a job whose runs/<ID>/RUN_RECORD.json exists (and is not
CONTAMINATED) is skipped, so a restarted container picks up where it stopped.
Two slots run at once, pinned to cores {0,1} and {2,3}. Each finished run is
extracted into runs/<ID>/ (small files only) and the heavy debug checkpoints in
the scratch run folder are deleted to keep the disk allowance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import tarfile
import io
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "evidence" / "raw_runs"))
from extract import extract_run  # noqa: E402

FINAL_COMMIT = "20d4affc3d7c85f0e1fc83daaea577da549669c2"
SHA = {"RC5": "0e6f643552c5e59f", "FINAL": "251cf35a9ae41258"}
CASES = {
    "CHAT": "Cricut_Chat_RC9_1_READY_SKELETON.xlsx",
    "VOICE": "Cricut_Voice_RC9_1_READY_SKELETON.xlsx",
    "NMGSP": "NMG_SP_RC9_1_READY_FIXED.xlsx",
    "AEIT": "AE_IT_B2B.xlsx",
    "H1": "SYNTH_H1_24x7_OVERNIGHT.xlsx",
    "M2": "SYNTH_M2_MULTI_START_WITH_BREAKS.xlsx",
}
SEEDS = list(range(9000, 9006))  # AMENDMENTS.txt A1 (was 9000-9009)
ARMS = ("RC5", "FINAL")
BUDGET = 3600
KILL_AFTER = 7200
FOREIGN_CPU_SHARE = 0.5  # a process outside the experiment using > half a core over a sample
HZ = os.sysconf("SC_CLK_TCK")
SLOTS = ({0, 1}, {2, 3})
HEAVY = ("CANDIDATE_POOL_CHECKPOINT.json", "SKELETON_CHECKPOINTS.json",
         "RECOVERY_CHECKPOINT_BEST_VALIDATED_NOT_FINAL.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jobs():
    all_jobs = [(arm, case, seed) for arm in ARMS for case in CASES for seed in SEEDS]
    random.Random(20260930).shuffle(all_jobs)
    return all_jobs


def job_id(arm, case, seed) -> str:
    return f"{arm}_{case}_{seed}"


def done(jid: str) -> bool:
    rec = HERE / "runs" / jid / "RUN_RECORD.json"
    return rec.exists() and not json.loads(rec.read_text()).get("contaminated")


def prepare_arms(work: Path) -> dict:
    roots = {}
    rc5 = work / "arms" / "RC5"
    if not rc5.exists():
        shutil.copytree(HERE / "arms" / "RC5", rc5)
    final = work / "arms" / "FINAL"
    if not final.exists():
        blob = subprocess.run(["git", "-C", str(REPO), "archive", FINAL_COMMIT, "engine"],
                              check=True, capture_output=True).stdout
        final.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
            tar.extractall(final)
    for arm, root in (("RC5", rc5), ("FINAL", final)):
        digest = sha256(root / "engine" / "_tools" / "l632_universal_scheduler.py")
        if not digest.startswith(SHA[arm]):
            raise SystemExit(f"{arm} scheduler sha256 {digest[:16]} != registered {SHA[arm]}")
        roots[arm] = root
    return roots


class Monitor(threading.Thread):
    """Every 5 s: flag the active runs if a process outside the experiment used
    more than half a core (e.g. a test gate), which would steal solver time."""

    def __init__(self):
        super().__init__(daemon=True)
        self.active = {}  # pgid -> job record (dict), mutated in place
        self.lock = threading.Lock()
        self.prev = {}

    def run(self):
        me = os.getpid()
        while True:
            now = {}
            pgrp = {}
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry}/stat") as fh:
                        fields = fh.read().rsplit(")", 1)[1].split()
                    now[int(entry)] = int(fields[11]) + int(fields[12])
                    pgrp[int(entry)] = int(fields[2])
                except (OSError, IndexError, ValueError):
                    continue
            with self.lock:
                active = dict(self.active)
            foreign = []
            for pid, ticks in now.items():
                if pid == me or pgrp.get(pid) in active or pid not in self.prev:
                    continue
                if (ticks - self.prev[pid]) / HZ > FOREIGN_CPU_SHARE * 5:
                    foreign.append(pid)
            if foreign and active:
                names = []
                for pid in foreign[:5]:
                    try:
                        names.append(open(f"/proc/{pid}/comm").read().strip())
                    except OSError:
                        names.append(str(pid))
                for rec in active.values():
                    rec["contaminated"] = True
                    rec.setdefault("contamination", []).append(
                        {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "processes": names})
            self.prev = now
            time.sleep(5)


MONITOR = Monitor()


def tree_rss_mb(pgid: int) -> float:
    total = 0
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as fh:
                fields = fh.read().rsplit(")", 1)[1].split()
            if int(fields[2]) != pgid:  # field 5 (pgrp) after the command name
                continue
            with open(f"/proc/{entry}/statm") as fh:
                total += int(fh.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
        except (OSError, IndexError, ValueError):
            continue
    return total / 2**20


def run_job(arm: str, case: str, seed: int, cpus: set, roots: dict, work: Path) -> dict:
    jid = job_id(arm, case, seed)
    out_root = work / "out"
    out_root.mkdir(parents=True, exist_ok=True)
    workbook = HERE / "inputs" / CASES[case]
    cmd = [sys.executable, "-u", str(roots[arm] / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"),
           "--input", str(workbook), "--mode", "QUICK", "--time-limit", str(BUDGET),
           "--num-workers", "2", "--solver-random-seed", str(seed),
           "--output-root", str(out_root), "--schedule-id", jid, "--overwrite"]
    started = time.time()
    record = {"id": jid, "arm": arm, "case": case, "seed": seed, "cpus": sorted(cpus),
              "command": cmd, "start_utc": datetime.now(timezone.utc).isoformat(),
              "scheduler_sha256": sha256(roots[arm] / "engine" / "_tools" / "l632_universal_scheduler.py"),
              "input_sha256": sha256(workbook)}
    with open(out_root / f"{jid}.log", "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                                preexec_fn=lambda: os.sched_setaffinity(0, cpus))
        peak = max_load = 0.0
        timed_out = False
        record["contaminated"] = False
        with MONITOR.lock:
            MONITOR.active[proc.pid] = record
        while proc.poll() is None:
            peak = max(peak, tree_rss_mb(proc.pid))
            max_load = max(max_load, os.getloadavg()[0])
            if time.time() - started > KILL_AFTER:
                timed_out = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
                break
            time.sleep(5)
    with MONITOR.lock:
        MONITOR.active.pop(proc.pid, None)
    record.update({"return_code": proc.returncode, "timed_out": timed_out,
                   "wall_sec": round(time.time() - started, 1), "peak_rss_mb": round(peak, 1),
                   "max_load_1min": round(max_load, 2),
                   "end_utc": datetime.now(timezone.utc).isoformat()})
    dst = HERE / "runs" / jid
    if dst.exists():
        shutil.rmtree(dst)
    record["extract"] = extract_run(out_root / jid, dst) if (out_root / jid).is_dir() else "NO_RUN_FOLDER"
    (dst).mkdir(parents=True, exist_ok=True)
    (dst / "RUN_RECORD.json").write_text(json.dumps(record, indent=2) + "\n")
    for heavy in HEAVY:
        for f in (out_root / jid).rglob(heavy):
            f.unlink()
    for f in (out_root / jid).rglob("*_03_FULL_DEBUG.zip"):
        f.unlink()
    return record


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many jobs (0 = all)")
    args = ap.parse_args()
    roots = prepare_arms(args.work)
    MONITOR.start()
    queue = [j for j in jobs() if not done(job_id(*j))]
    if args.limit:
        queue = queue[:args.limit]
    print(f"{len(queue)} jobs to run", flush=True)
    lock = threading.Lock()

    def slot(cpus):
        while True:
            with lock:
                if not queue:
                    return
                arm, case, seed = queue.pop(0)
            rec = run_job(arm, case, seed, cpus, roots, args.work)
            print(f"{rec['end_utc'][:19]} {rec['id']} rc={rec['return_code']} wall={rec['wall_sec']} "
                  f"rss={rec['peak_rss_mb']} load={rec['max_load_1min']}"
                  f"{' CONTAMINATED' if rec['contaminated'] else ''}", flush=True)
            if rec["contaminated"]:
                with lock:
                    queue.append((arm, case, seed))

    threads = [threading.Thread(target=slot, args=(cpus,)) for cpus in SLOTS]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
