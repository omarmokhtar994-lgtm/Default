# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC: how long each person stays on a channel. Plans Mon to Fri for a made-up team in a few settings and prints, per setting, the share
of person-days on one channel only, the average number of channels used a day, the lengths of the stretches (hours) and how many people have
the same channel as the day before. argv: scenario name (default base_16)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import channel_scenarios as cs
from webapp.channel_plan import plan_day

def stretches(blocks):
    """(channel, minutes) runs of one channel; a break or lunch does not end a run."""
    runs = []
    for a, b, c in sorted(blocks):
        if c not in "PCE":
            continue
        if runs and runs[-1][0] == c:
            runs[-1][1] += b - a
        else:
            runs.append([c, b - a])
    return runs

def measure(name, fair, tick):
    people, config = cs.SCENARIOS[name]()
    config["rules"] = dict(config["rules"], fair=fair, consistent=tick)
    carry, rows, main_by_day = {}, [], {}
    for d in cs.DAYS:
        plan = plan_day(people, config, cs.RULES, d, carry=carry, move_breaks=False)
        for person, blocks in plan["blocks"].items():
            runs = stretches(blocks)
            if not runs:
                continue
            minutes = {}
            for c, m in runs:
                minutes[c] = minutes.get(c, 0) + m
            rows.append((person, d, runs, minutes))
            main_by_day[(person, d)] = max(minutes, key=minutes.get)
            for a, b, c in blocks:
                if c in "PCE":
                    carry.setdefault(person, {})[c] = carry.get(person, {}).get(c, 0) + b - a
    one = sum(1 for r in rows if len(r[3]) == 1) / len(rows)
    chans = sum(len(r[3]) for r in rows) / len(rows)
    lens = [m / 60 for r in rows for _, m in r[2]]
    longest = sum(max(m for _, m in r[2]) / 60 for r in rows) / len(rows)
    same = [main_by_day[(p, d)] == main_by_day[(p, d - 1)] for (p, d) in main_by_day if (p, d - 1) in main_by_day]
    return {"one_channel_days": round(one, 2), "channels_per_day": round(chans, 2), "stretches_per_day": round(len(lens) / len(rows), 2),
            "avg_stretch_h": round(sum(lens) / len(lens), 2), "longest_stretch_h": round(longest, 2),
            "same_main_as_yesterday": round(sum(same) / max(1, len(same)), 2)}

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "base_16"
    for label, fair, tick in (("baseline", False, False), ("tick", False, True), ("fair+tick", True, True)):
        print(f"{scenario:16} {label:10}", measure(scenario, fair, tick), flush=True)
