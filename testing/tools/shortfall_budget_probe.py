#!/usr/bin/env python3
"""Measure the shortfall test's solver-work budget on this machine.

Phase I follow-up (2026-10-07): on the Oracle ARM server (aarch64, Python
3.12) tests_staged/test_rc9_2_32 failed once with the Phase H budget D = 10:
the shortfall pass left Sat 15:30 uncovered besides the planted Sunday 03:xx
hour. This applies the SAME pre-registered rule
(evidence/phase_h/H4_DETERMINISTIC_BUDGET_RULE.txt) on the machine that
failed, without changing anything installed:

1. Candidates D in {10, 20, 40}, smallest first. Unloaded, 2 cores pinned:
   run the test 5 times; the first D with 5/5 PASS and median wall <= 90 s
   is chosen.
2. Confirm with that D: 10 runs on the same 2 cores with two busy-loop
   processes pinned to them. Accept only 10/10 PASS.
3. Run on x86 and on the ARM server; the larger per-platform choice ships.
   If no candidate meets 1 and 2, nothing ships and the result is reported.

Each run executes the unchanged test method in its own process, with only
the budget passed to run_shortfall_pass replaced.

    cd /opt/scheduler/package
    sudo -u scheduler /opt/scheduler/venv/bin/python ~/shortfall_budget_probe.py
"""
from __future__ import annotations

import argparse
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

TEST = "tests_staged/test_rc9_2_32_phase_c_shortfall.py"
METHOD = "C1ShortfallPass.test_the_pass_exports_a_listed_non_releasable_schedule"
CANDIDATES = (20.0, 40.0, 80.0)
STEP1_RUNS, STEP1_MEDIAN_LIMIT, STEP2_RUNS = 20, 120, 10
CORES = {0, 1}


def one_run(package: Path, budget: float) -> int:
    """Child process: run the unchanged test method with the budget replaced."""
    import importlib.util
    import unittest
    sys.path.insert(0, str(package / "tests_staged"))
    spec = importlib.util.spec_from_file_location("shortfall_probe_target", package / TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    original = module.E.run_shortfall_pass

    def with_budget(*args, **kwargs):
        kwargs["deterministic_time"] = budget
        return original(*args, **kwargs)

    module.E.run_shortfall_pass = with_budget
    suite = unittest.defaultTestLoader.loadTestsFromName(METHOD, module)
    result = unittest.TextTestRunner(stream=open(os.devnull, "w"), verbosity=0).run(suite)
    for _, trace in result.failures + result.errors:
        print(trace.strip().splitlines()[-1][:400], file=sys.stderr)
    return 0 if result.wasSuccessful() else 1


def pin() -> None:
    os.sched_setaffinity(0, CORES)


def measure(package: Path, budget: float, runs: int, loaded: bool, log) -> list:
    loads = []
    if loaded:
        loads = [subprocess.Popen([sys.executable, "-c", "while True: pass"], preexec_fn=pin) for _ in range(2)]
    rows = []
    try:
        for n in range(1, runs + 1):
            start = time.time()
            proc = subprocess.run([sys.executable, __file__, "--one", str(budget), "--package-root", str(package)],
                                  capture_output=True, text=True, preexec_fn=pin)
            wall = time.time() - start
            ok = proc.returncode == 0
            rows.append((ok, wall))
            note = "" if ok else "  " + (proc.stderr.strip().splitlines() or ["(no message)"])[-1][:300]
            log(f"  D={budget:g} {'loaded' if loaded else 'unloaded'} run {n}: {'PASS' if ok else 'FAIL'}  {wall:.1f} s{note}")
    finally:
        for p in loads:
            p.kill()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package-root", type=Path, default=Path.cwd())
    ap.add_argument("--one", type=float, help=argparse.SUPPRESS)
    ap.add_argument("--out", type=Path, default=Path("/tmp/shortfall_budget_probe.txt"))
    args = ap.parse_args()
    package = args.package_root.resolve()
    if args.one is not None:
        return one_run(package, args.one)
    if not (package / TEST).is_file():
        sys.exit(f"{TEST} not found under {package}: run this from the package folder.")
    lines = []

    def log(text: str) -> None:
        print(text, flush=True)
        lines.append(text)

    log(f"shortfall budget probe | {platform.machine()} | python {platform.python_version()} | "
        f"cpus {os.cpu_count()} | pinned to cores {sorted(CORES)} | {time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    chosen = None
    for budget in CANDIDATES:
        rows = measure(package, budget, STEP1_RUNS, False, log)
        median = statistics.median(w for _, w in rows)
        passes = sum(ok for ok, _ in rows)
        log(f"step 1 D={budget:g}: {passes}/{STEP1_RUNS} PASS, median {median:.1f} s")
        if passes == STEP1_RUNS and median <= STEP1_MEDIAN_LIMIT:
            chosen = budget
            break
    if chosen is None:
        log("RULE RESULT: no candidate met step 1 - nothing ships.")
    else:
        rows = measure(package, chosen, STEP2_RUNS, True, log)
        passes = sum(ok for ok, _ in rows)
        log(f"step 2 D={chosen:g} under load: {passes}/{STEP2_RUNS} PASS")
        log(f"RULE RESULT: D={chosen:g} " + ("ACCEPTED" if passes == STEP2_RUNS else "REJECTED at step 2 - nothing ships."))
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"(saved to {args.out})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
