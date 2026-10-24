# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY: measures how consistent and how fair the channel planner is across made-up teams.

Each scenario is a team (names "Associate NN") planned Mon to Fri with the earlier days carried, in four arms:
baseline (fair off, tick off), fair, tick, fair + tick. Per arm: the fair spread (sum over groups of people with the
same channels and language, and over channels, of most hours minus fewest), channel changes and stretches under two
hours per person-day, hours short, and the slowest day. Rules are in evidence/phase_ay/REQUESTS.md.

    python tools/channel_scenarios.py [--only NAME ...] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webapp.channel_plan import plan_day, score_day  # noqa: E402

DAYS = (1, 2, 3, 4, 5)
RULES = {"segments": [[15, "Break 1"], [30, "Lunch"], [15, "Break 2"]], "by_length": [],
         "windows": {"break 1": {"earliest": None, "latest": None}, "lunch": {"earliest": None, "latest": None},
                     "break 2": {"earliest": None, "latest": None}},
         "edge_margin": None, "min_gap": 60, "preferred_gap": 150, "max_gap": 210, "max_concurrent": 4}
ARMS = {"baseline": (False, False), "fair": (True, False), "tick": (False, True), "fair+tick": (True, True)}


def need(scale: float, phone: Callable[[float], int], t: int) -> float:
    return round(phone(t / 60) * scale, 1)


def phone_h(h: float) -> int:
    return 0 if h < 8 or h >= 22 else 2 if h < 10 else 4 if h < 12 else 5 if h < 13 else 6 if h < 17 else 5 if h < 19 \
        else 3 if h < 21 else 2


def chat_h(h: float) -> int:
    return 0 if h < 8 or h >= 22 else 1 if h < 10 else 2 if h < 12 else 3 if h < 13 else 4 if h < 19 else 3 if h < 21 \
        else 1


def setup(scale: float = 1.0, languages: bool = True) -> Dict[str, Any]:
    grid = lambda fn: {d: {t: need(scale, fn, t) for t in range(0, 1440, 30)} for d in range(7)}  # noqa: E731
    rows = [{"channel": "P", "language": "Arabic", "minimum": 1, "start": 600, "end": 1200, "days": set(range(7)),
             "active": True}, {"channel": "C", "language": "Arabic", "minimum": 1, "start": 720, "end": 1200,
                               "days": set(range(7)), "active": True}] if languages else []
    return {"step": 30, "need": {"P": grid(phone_h), "C": grid(chat_h)}, "email_mode": "hours",
            "email_hours": {d: {"hours": 22.0 * scale, "languages": {}, "start": 480, "end": 1320} for d in range(7)},
            "rules": {"min_block": 60, "max_run": {"P": 120, "C": 0, "E": 0}, "order": ["P", "C", "E"],
                      "strict": True, "fair": True},
            "languages": rows, "blended": [], "notes": [], "tabs": [], "hours_tab": "Email Hours"}


def team(n: int, starts=(8, 10, 12, 13), skills: Callable[[int], str] = lambda i: "PCE",
         arabic: Callable[[int], bool] = lambda i: i % 3 == 0, length: int = 540) -> List[Dict[str, Any]]:
    people = []
    for i in range(1, n + 1):
        start = starts[(i - 1) * len(starts) // n] * 60
        k = (i - 1) % 4
        language = "Arabic" if arabic(i) else "English"
        people.append({"name": f"Associate {i:03d}", "language": language, "start": start, "end": start + length,
                       "breaks": [("Break 1", start + 120 + 15 * k, 15), ("Lunch", start + 255 + 15 * k, 30),
                                  ("Break 2", start + 420 + 15 * (k % 2), 15)],
                       "skills": skills(i), "counts_for": {language.casefold()}})
    return people


def mixed(i: int) -> str:
    return "PCE" if i % 5 in (0, 1, 2) else "PC" if i % 5 == 3 else "CE"


def specialists(i: int) -> str:
    return "P" if i <= 8 else "CE" if i <= 14 else "PCE"


SCENARIOS = {
    "small_10": lambda: (team(10, (8, 12)), setup(0.6)),
    "base_16": lambda: (team(16), setup()),
    "large_30": lambda: (team(30, skills=mixed), setup(1.8)),
    "specialists_20": lambda: (team(20, skills=specialists), setup(1.1)),
    "tight_16": lambda: (team(16), setup(1.4)),
    "slack_16": lambda: (team(16), setup(0.6)),
    "no_languages_16": lambda: (team(16), setup(languages=False)),
}


def run_arm(build, fair: bool, tick: bool) -> Dict[str, Any]:
    people, config = build()
    config["rules"] = dict(config["rules"], fair=fair, consistent=tick)
    carry: Dict[str, Dict[str, int]] = {}
    out = {"short": 0.0, "moves": 0, "stretches": 0, "slowest": 0.0, "problems": 0}
    for d in DAYS:
        began = time.time()
        plan = plan_day(people, config, RULES, d, carry=carry, move_breaks=False)
        out["slowest"] = max(out["slowest"], time.time() - began)
        got = score_day(people, plan, config, d, RULES)
        out["short"] += sum(got["short"].values()) + got["language_short"]
        out["moves"] += got["moves"]
        out["stretches"] += got["short_stretches"]
        out["problems"] += len(got["problems"])
        for name, blocks in plan["blocks"].items():
            for a, b, c in blocks:
                if c in "PCE":
                    carry.setdefault(name, {})[c] = carry.get(name, {}).get(c, 0) + b - a
    groups: Dict[Any, List[str]] = {}
    for p in people:
        groups.setdefault((p["skills"], p["language"]), []).append(p["name"])
    spread, worst = 0.0, 0.0
    for (skills, _), names in groups.items():
        if len(names) > 1:
            for c in skills:
                hours = [carry.get(n, {}).get(c, 0) / 60 for n in names]
                spread += max(hours) - min(hours)
                worst = max(worst, max(hours) - min(hours))
    days = len(DAYS) * len(people)
    return {"spread": round(spread, 2), "worst": round(worst, 2), "short": round(out["short"], 2),
            "moves_pp": round(out["moves"] / days, 2), "stretches_pp": round(out["stretches"] / days, 2),
            "slowest": round(out["slowest"], 1), "problems": out["problems"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--json")
    ap.add_argument("--arms", nargs="*", help="only these arms")
    ap.add_argument("--set", nargs="*", default=[], help="NAME=VALUE overrides of channel_plan constants")
    ap.add_argument("--seconds", type=float, help="search time of the first stage, to test whether time limits quality")
    args = ap.parse_args()
    import webapp.channel_plan as plan_module
    if args.seconds:
        plan_module.KEPT["max_time_in_seconds"] = args.seconds
    for item in args.set:
        key, value = item.split("=")
        setattr(plan_module, key, value if value.isalpha() else float(value) if "." in value else int(value))
    results: Dict[str, Dict[str, Any]] = {}
    for name, build in SCENARIOS.items():
        if args.only and name not in args.only:
            continue
        results[name] = {arm: run_arm(build, *flags) for arm, flags in ARMS.items() if not args.arms or arm in args.arms}
        print(name, json.dumps(results[name]), flush=True)
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
