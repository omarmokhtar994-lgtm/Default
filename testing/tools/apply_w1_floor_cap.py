#!/usr/bin/env python3
"""#49: tighten the W1 floor-loss cap from 5% to 3% of active intervals.

WHY, FROM DATA NOT CONVENTION

WFM sources are explicit that service targets should be derived from your own
cost and tolerance analysis rather than borrowed benchmarks -- the familiar
80/20 standard has no scientific basis and persists by habit. So this was
derived from 56 runs across 10 workbooks.

Observed floor intervals lost to break placement:

    zero loss in 33 of 56 runs
    median 0, mean 1.2, p95 = 6
    worst case ever: 8 intervals on a 264-interval schedule = 3.0%

Against those runs, what each cap would actually reject:

    CURRENT  max(3, 5% of active)  ->   0 of 56  (0%)   <- never fires
             max(3, 4% of active)  ->   1 of 56  (2%)
    CHOSEN   max(3, 3% of active)  ->   1 of 56  (2%)
             max(1, 2% of active)  ->   7 of 56  (12%)
             absolute 3            ->   8 of 56  (14%)

The current 5% cap has never fired. It is the same inert-guard pattern already
found in B-13 (a bound comparing NewBoolVar on both sides) and A40 (a
concurrency penalty at 1:140,000). A gate that cannot fire protects nothing.

3% catches the genuine outlier while rejecting 2% rather than 12%, and stays
proportional so it scales with schedule size.

NOT CHANGED: the TARGET loss cap on line 2947, which shares the 5% constant.
That is a separate policy with its own evidence and is out of scope here.

The workbook override ("Maximum Floor Losses From Breaks") is untouched, so any
roster can still set its own value.

Usage:  apply_w1_floor_cap.py <engine_tree> [--check]
"""
from __future__ import annotations
import sys
from pathlib import Path

OLD = "    default_floor_loss_cap = max(3, int(math.ceil(active_interval_count * 0.05)))"
NEW = """    # #49: 3%, derived from 56 runs across 10 workbooks. The previous 5% cap
    # fired on 0 of those 56 -- an inert guard, the same pattern as B-13 and
    # A40. Worst observed loss was 8 intervals on 264 active (3.0%); 3% rejects
    # that outlier and 2% of runs overall, where 2% would reject 12%.
    default_floor_loss_cap = max(3, int(math.ceil(active_interval_count * 0.03)))"""


def apply(tree: Path, check_only: bool = False) -> int:
    target = tree / "engine" / "_tools" / "l632_universal_scheduler.py"
    src = target.read_text()
    if "#49: 3%, derived from" in src:
        print("ALREADY APPLIED")
        return 0
    if src.count(OLD) != 1:
        print(f"FAIL: anchor found {src.count(OLD)} times, expected 1")
        return 1
    # guard: the target-loss cap two lines up must NOT be touched
    if src.count("default_target_loss_cap = max(3, int(math.ceil(active_interval_count * 0.05)))") != 1:
        print("FAIL: target loss cap not in its expected form; aborting to avoid touching it")
        return 1
    src = src.replace(OLD, NEW, 1)
    if check_only:
        print("WOULD PATCH floor cap 5% -> 3%, target cap untouched")
        return 0
    target.write_text(src)
    print("APPLIED: floor loss cap 5% -> 3% (target loss cap untouched)")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(apply(Path(args[0]), check_only="--check" in sys.argv))
