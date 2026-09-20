#!/usr/bin/env python3
"""Default joint refinement OFF at QUICK and SMOKE. Evidence-backed.

WHY

Measured across 55 runs on 10 workbooks:
  * 69 attempts on 7 workbooks where the phase executed -> improved: 0, always.
  * Isolated A/B on AE_AR_B2B at 1800s with --disable-joint-refinement:
        peak RSS 8197 MB -> 820 MB   (-90%)
        stage1/stage2 attempts identical (9 / 2)
        coverage identical (166/165/167 vs 166/165/168, floor +1)
  * Corpus-wide: every workbook where it ran peaked in GB (GDI 5254 MB,
    NMG_EN_AND_SP 3389 MB, AE_IT_Choice 2017 MB); both where it never ran
    stayed under 610 MB.
  * It is the mechanism behind the 3600s OOM kill.

SCOPE -- DELIBERATELY NARROW

Only QUICK and SMOKE change. DEEP and OVERNIGHT keep the phase ON because they
allot it 5400s and 8400s respectively and NEITHER HAS BEEN MEASURED. Every run
in the evidence above is QUICK at 300-1800s. Changing an untested configuration
on the strength of a tested one is the error this review keeps catching.

`--joint-refinement-reserve-sec 0` does NOT disable the phase -- measured: it
merely shrinks the allocation (241s -> 87s) and the phase still runs. The only
switch that works is `--disable-joint-refinement`.

An escape hatch is added: `--enable-joint-refinement` forces it back on at any
mode, so the old behaviour stays reachable without editing code.

Usage:  apply_joint_default_off.py <engine_tree> [--check]
"""
from __future__ import annotations
import sys
from pathlib import Path

MODE_OLD = """        'SMOKE': {'time_limit': 900, 'joint': 120, 'safe': 120, 'post': 60, 'target': 60, 'final': 60, 'adaptive': 6, 'joint_attempts': 4, 'joint_no_improve': 2},
        'QUICK': {'time_limit': 3600, 'joint': 900, 'safe': 180, 'post': 180, 'target': 180, 'final': 120, 'adaptive': 18, 'joint_attempts': 16, 'joint_no_improve': 6},"""

MODE_NEW = """        # joint_enabled False at SMOKE/QUICK: 69 attempts across 7 workbooks
        # produced improved: 0, while the phase accounted for ~90% of peak RSS
        # (8197 MB -> 820 MB when disabled, coverage unchanged) and caused the
        # 3600s OOM. DEEP and OVERNIGHT keep it ON -- they allot it 5400s and
        # 8400s and have NOT been measured.
        'SMOKE': {'time_limit': 900, 'joint': 120, 'joint_enabled': False, 'safe': 120, 'post': 60, 'target': 60, 'final': 60, 'adaptive': 6, 'joint_attempts': 4, 'joint_no_improve': 2},
        'QUICK': {'time_limit': 3600, 'joint': 900, 'joint_enabled': False, 'safe': 180, 'post': 180, 'target': 180, 'final': 120, 'adaptive': 18, 'joint_attempts': 16, 'joint_no_improve': 6},"""

ARG_OLD = "    p.add_argument('--selfcheck', action='store_true')"
ARG_NEW = """    p.add_argument('--enable-joint-refinement', action='store_true',
                   help='Force joint refinement on. Off by default at SMOKE/QUICK, where it '
                        'was measured to improve nothing across 69 attempts while accounting '
                        'for ~90% of peak memory. On by default at DEEP/OVERNIGHT.')
    p.add_argument('--selfcheck', action='store_true')"""

CMD_OLD = "        command.append('--disable-bundled-fallbacks')"
CMD_NEW = """        command.append('--disable-bundled-fallbacks')
    if not mode_defaults.get('joint_enabled', True) and not args.enable_joint_refinement:
        command.append('--disable-joint-refinement')"""


def apply(tree: Path, check_only: bool = False) -> int:
    target = tree / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"
    src = target.read_text()

    if "joint_enabled" in src:
        print("ALREADY APPLIED")
        return 0

    for name, old in (("mode defaults", MODE_OLD), ("cli arg", ARG_OLD), ("command build", CMD_OLD)):
        if src.count(old) != 1:
            print(f"FAIL: {name} anchor found {src.count(old)} times, expected 1")
            return 1

    src = src.replace(MODE_OLD, MODE_NEW, 1)
    src = src.replace(ARG_OLD, ARG_NEW, 1)
    src = src.replace(CMD_OLD, CMD_NEW, 1)

    if check_only:
        print("WOULD PATCH: mode defaults + cli arg + command build")
        return 0

    target.write_text(src)
    print(f"APPLIED: joint refinement OFF at SMOKE/QUICK, ON at DEEP/OVERNIGHT -> {target}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(apply(Path(args[0]), check_only="--check" in sys.argv))
