#!/usr/bin/env python3
"""Solver scenarios that try to make the engine degrade badly.

Each scenario is a small workbook built from scratch (make_case.build) and run
through the PRODUCTION runner (engine + independent validator + parity gate),
exactly as a user would run it. The result row records what the run ended as,
whether a schedule was published, and what the clean-room checker
(tools/clean_room_check.py, no engine code) says about that schedule.

    python3 solver_scenarios.py OUT_DIR [scenario ids...] [--time-limit 300] [--workers 2]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import make_case  # noqa: E402

NAMES = [f"Agent {c}" for c in "ABCDEFGHIJKLMNOPQRST"]
DAY_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(6, 12)]
ALL_SHIFTS = [f"{h:02d}:00 - {(h + 9) % 24:02d}:00" for h in range(24)]


def roster(k, lang="English"):
    return [(n, lang) for n in NAMES[:k]]


def day_demand(v, start=8, end=20):
    return lambda d, m: v if start * 60 <= m < end * 60 else None


SCENARIOS = {
    "S01_BASELINE": dict(
        why="sanity: 10 agents, 3 FTE 08:00-20:00, day shifts",
        expect="PASS with a validated schedule",
        spec=dict(roster=roster(10), demand=day_demand(3), shifts=DAY_SHIFTS)),
    "S02_DEMAND_SLIGHTLY_ABOVE_CAPACITY": dict(
        why="demand ~10% above what 10 agents can staff",
        expect="a schedule that covers as much as possible and names the deficit",
        spec=dict(roster=roster(10), demand=day_demand(4.4), shifts=DAY_SHIFTS)),
    "S03_DEMAND_MASSIVELY_ABOVE_CAPACITY": dict(
        why="demand 3x what the roster can staff",
        expect="best achievable schedule published with the deficit stated (not a refusal)",
        spec=dict(roster=roster(10), demand=day_demand(12), shifts=DAY_SHIFTS)),
    "S04_ONE_IMPOSSIBLE_INTERVAL": dict(
        why="0.5 FTE at Sun 03:00 that no legal shift can reach; everything else easy",
        expect="schedule for the solvable week, with Sun 03:00 named as uncoverable",
        spec=dict(roster=roster(10), shifts=DAY_SHIFTS,
                  demand=lambda d, m: 0.5 if (d == 0 and m == 180) else (3 if 8 * 60 <= m < 20 * 60 else None))),
    "S05_LANGUAGE_SHORTAGE": dict(
        why="Spanish minimum 1 from 08:00-20:00 every day, only 2 Spanish agents (10 shifts for 14 needed)",
        expect="schedule with Spanish gaps named, or refusal naming Spanish",
        spec=dict(roster=[(n, "Spanish" if i < 2 else "English") for i, n in enumerate(NAMES[:10])],
                  demand=day_demand(3), shifts=DAY_SHIFTS,
                  language_setup=[{"Language": "Spanish", "Coverage Start": "08:00", "Coverage End": "20:00",
                                   "Active?": "Yes", "Coverage Group": "Spanish", "Minimum Per Interval": 1,
                                   "Coverage Days": "All"},
                                  {"Language": "English", "Coverage Start": "00:00", "Coverage End": "00:00",
                                   "Active?": "Yes", "Coverage Group": "English", "Minimum Per Interval": 0}])),
    "S06_FULL_WEEK_LEAVE": dict(
        why="one associate on approved Leave all 7 days; otherwise S01",
        expect="PASS; that associate is Leave all week",
        spec=dict(roster=roster(10), demand=day_demand(3), shifts=DAY_SHIFTS,
                  preferences={"Agent A": ["Leave"] * 7})),
    "S07_SIX_LEAVE_DAYS": dict(
        why="one associate on Leave Mon-Sat (6 days); Strict 2 OFF",
        expect="PASS; Leave honoured, no impossible OFF demand",
        spec=dict(roster=roster(10), demand=day_demand(3), shifts=DAY_SHIFTS,
                  preferences={"Agent A": [None] + ["Leave"] * 6})),
    "S08_24x7_WEEK_BOUNDARY": dict(
        why="24/7 demand, overnight shifts crossing Sat->Sun, previous-Saturday carry-in",
        expect="PASS; clean-room and validator agree incl. Saturday spill",
        spec=dict(roster=roster(14), demand=lambda d, m: 2 if 7 * 60 <= m < 23 * 60 else 1, shifts=ALL_SHIFTS,
                  previous_saturday={"Agent A": "22:00 - 07:00", "Agent B": "20:00 - 05:00"})),
    "S09_LONE_NIGHT_BREAKS": dict(
        why="24/7, 6 agents: nights can be held by one person, whose own breaks leave nobody",
        expect="schedule with overlap at night, or a named no-break exception need",
        spec=dict(roster=roster(6), demand=lambda d, m: 1 if 8 * 60 <= m < 20 * 60 else 0.3, shifts=ALL_SHIFTS)),
    "S10_FIXED_IN_BLANK_HOURS": dict(
        why="fixed 22:00 starts while the blank-interval rule forbids staffing outside 08:00-20:00",
        expect="refused naming the fixed requests and the blank rule",
        spec=dict(roster=roster(10), demand=day_demand(3), shifts=DAY_SHIFTS + ["22:00 - 07:00"],
                  instructions={"Fixed Request Use": "Yes",
                                "Blank Interval Staffing Rule": "No new staffing in blank intervals"},
                  fixed={"Agent A": ["22:00 - 07:00"] * 5 + ["OFF", "OFF"]})),
    "S11_OVERNIGHT_DAY_WINDOW": dict(
        why="Spanish minimum 1, Mon-Fri 18:00-05:00 (day-specific overnight). Two Spanish agents are hard-OFF "
            "Sun+Mon; the third is hard-OFF Sat+Sun. Business meaning (window opens Mon..Fri) is feasible.",
        expect="schedule produced; Monday 00:00-05:00 needs no Spanish (it is Sunday night)",
        spec=dict(roster=[(n, "Spanish" if i < 3 else "English") for i, n in enumerate(NAMES[:12])],
                  demand=lambda d, m: 2, shifts=ALL_SHIFTS,
                  preferences={"Agent A": ["OFF", "OFF"] + [None] * 5,
                               "Agent B": ["OFF", "OFF"] + [None] * 5,
                               "Agent C": ["OFF"] + [None] * 5 + ["OFF"]},
                  language_setup=[{"Language": "Spanish", "Coverage Start": "18:00", "Coverage End": "05:00",
                                   "Active?": "Yes", "Coverage Group": "Spanish", "Minimum Per Interval": 1,
                                   "Coverage Days": "Mon-Fri"}])),
    "S12_OVERLAPPING_SKILLS": dict(
        why="bilingual agents can cover Spanish and English; Spanish minimum 1 all day; English-only cannot",
        expect="PASS; Spanish minimum met only by Spanish/bilingual agents",
        spec=dict(roster=[(n, "Bilingual" if i < 4 else "English") for i, n in enumerate(NAMES[:10])],
                  demand=day_demand(3), shifts=DAY_SHIFTS,
                  language_setup=[{"Language": "Spanish", "Coverage Start": "08:00", "Coverage End": "20:00",
                                   "Active?": "Yes", "Coverage Group": "Spanish", "Minimum Per Interval": 1},
                                  {"Language": "Bilingual", "Coverage Start": "00:00", "Coverage End": "00:00",
                                   "Can Cover Languages": "Spanish, English", "Active?": "Yes",
                                   "Coverage Group": "Bilingual", "Minimum Per Interval": 0}])),
    "S13_24x7_UNDERSTAFFED": dict(
        why="24/7 demand of 3 FTE every hour, 10 agents (about 75% of the hours needed), overnight shifts allowed",
        expect="best achievable schedule with the deficit named (current-week floor is soft)",
        spec=dict(roster=roster(10), demand=lambda d, m: 3, shifts=ALL_SHIFTS)),
    "S14_DUPLICATE_PREFERENCE_ROW": dict(
        why="Agent A appears twice on Preference: row 1 = approved Leave on Monday; row 2 = OFF Friday and Saturday",
        expect="refused as a duplicate, or Leave Monday honoured",
        spec=dict(roster=roster(10), demand=day_demand(3), shifts=DAY_SHIFTS,
                  preference_rows=[("Agent A", [None, "Leave", None, None, None, None, None]),
                                   ("Agent A", [None, None, None, None, None, "OFF", "OFF"])])),
}


def run_one(sid, out_dir: Path, time_limit: int, workers: int, seed: int = 9000, suffix: str = ""):
    sc = SCENARIOS[sid]
    case_dir = out_dir / "inputs"
    case_dir.mkdir(parents=True, exist_ok=True)
    wb = case_dir / f"{sid}.xlsx"
    make_case.build(sc["spec"], wb)
    schedule_id = sid + suffix
    stale = out_dir / "runs" / schedule_id
    if stale.exists():
        import shutil
        shutil.rmtree(stale)
    cmd = [sys.executable, "-u", str(ROOT / "engine" / "RUN_UNIVERSAL_PRODUCTION.py"), "--input", str(wb),
           "--output-root", str(out_dir / "runs"), "--schedule-id", schedule_id, "--mode", "QUICK",
           "--time-limit", str(time_limit), "--num-workers", str(workers),
           "--solver-random-seed", str(seed)]
    started = time.time()
    with (out_dir / f"{schedule_id}.log").open("w") as log:
        rc = subprocess.call(cmd, stdout=log, stderr=subprocess.STDOUT)
    root = out_dir / "runs" / schedule_id
    status = json.loads((root / "UNIVERSAL_RUN_STATUS.json").read_text()) if (root / "UNIVERSAL_RUN_STATUS.json").exists() else {}
    audit_path = next(iter(sorted(root.glob("*solver_audit.json"))), None)
    audit = json.loads(audit_path.read_text()) if audit_path else {}
    outcome = (root / "BUSINESS_OUTCOME.txt").read_text()[:1500] if (root / "BUSINESS_OUTCOME.txt").exists() else ""
    finals = sorted((root / "production").glob("*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx")) if root.exists() else []
    any_xlsx = sorted(p.name for p in root.glob("*.xlsx")) if root.exists() else []
    clean = None
    target = finals[0] if finals else next(iter(sorted(root.glob("*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"))), None)
    if target is not None:
        cr = root / "CLEAN_ROOM.json"
        subprocess.call([sys.executable, str(ROOT / "tools" / "clean_room_check.py"), "--input", str(wb),
                         "--output", str(target), "--json-out", str(cr)] +
                        (["--audit", str(audit_path)] if audit_path else []) +
                        (["--validation", str(root / "INDEPENDENT_VALIDATION.json")]
                         if (root / "INDEPENDENT_VALIDATION.json").exists() else []),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if cr.exists():
            c = json.loads(cr.read_text())
            clean = {"checked": str(target.name), "violations": c["violations_by_rule"],
                     "engine_mismatches": c.get("engine_mismatches"), "validator_mismatches": c.get("validator_mismatches"),
                     "metrics": c["metrics"]}
    row = {
        "scenario": schedule_id, "why": sc["why"], "expected": sc["expect"],
        "runner_rc": rc, "elapsed_sec": round(time.time() - started, 1),
        "engine_status": audit.get("status"), "artifact_state": audit.get("artifact_state"),
        "independent_validation": (status.get("independent_validation") or {}).get("status"),
        "published_final": [p.name for p in finals], "workbooks_in_case_root": any_xlsx,
        "selected_metrics": {k: (audit.get("selected_candidate") or {}).get("metrics", {}).get(k)
                             for k in ("after_target", "after_floor", "active_intervals", "language_gap_count")},
        "run_id": (audit.get("run_identity") or {}).get("run_id"),
        "business_outcome": outcome, "clean_room": clean,
        "pre_solver_failures": [f.get("code") for f in (audit.get("pre_solver_contract_validation") or {}).get("failures", [])],
        "hard_probe": (audit.get("hard_feasibility_probe") or {}).get("cp_status"),
    }
    (out_dir / f"{schedule_id}.result.json").write_text(json.dumps(row, indent=1, default=str))
    print(json.dumps({k: row[k] for k in ("scenario", "runner_rc", "elapsed_sec", "engine_status",
                                          "independent_validation", "published_final", "pre_solver_failures",
                                          "hard_probe")}, default=str), flush=True)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--time-limit", type=int, default=300)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=9000)
    ap.add_argument("--suffix", default="")
    a = ap.parse_args()
    for sid in (a.ids or list(SCENARIOS)):
        run_one(sid, a.out_dir, a.time_limit, a.workers, a.seed, a.suffix)


if __name__ == "__main__":
    main()
