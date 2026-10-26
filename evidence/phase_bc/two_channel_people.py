# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC: people who work only two channels (Chat and Email) in the made-up specialists_20 team, Mon to Fri: hours per channel, the longest stretch
and the number of stretches a day, with no tick, Fixed, and Balanced. argv: scenario (default specialists_20)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import channel_scenarios as cs
from webapp.channel_plan import plan_day

def run(name, rules):
    people, config = cs.SCENARIOS[name]()
    config["rules"] = dict(config["rules"], **rules)
    two = {p["name"] for p in people if len(p["skills"]) == 2}
    carry, hours, longest, stretches, days = {}, {"C": 0, "E": 0}, 0.0, 0, 0
    for d in cs.DAYS:
        plan = plan_day(people, config, cs.RULES, d, carry=carry, move_breaks=False)
        for person, blocks in plan["blocks"].items():
            runs, last = [], None
            for a, b, c in sorted(blocks):
                if c not in "PCE":
                    continue
                carry.setdefault(person, {})[c] = carry.get(person, {}).get(c, 0) + b - a
                if person in two:
                    hours[c] = hours.get(c, 0) + (b - a) / 60
                    if last == c:
                        runs[-1] += b - a
                    else:
                        runs.append(b - a)
                    last = c
            if runs:
                longest += max(runs) / 60
                stretches += len(runs)
                days += 1
    return {"people": len(two), "chat_h": round(hours["C"], 1), "email_h": round(hours["E"], 1), "chat_share": round(hours["C"] / (hours["C"] + hours["E"]), 2),
            "longest_stretch_h": round(longest / days, 2), "stretches_per_day": round(stretches / days, 2)}

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "specialists_20"
    for label, rules in (("no tick", dict(fair=True, consistent=False, balanced=False)), ("fixed", dict(fair=True, consistent=True, balanced=False)),
                         ("balanced", dict(fair=True, consistent=False, balanced=True))):
        print(f"{scenario} {label:9}", run(scenario, rules), flush=True)
