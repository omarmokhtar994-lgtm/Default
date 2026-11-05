# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC: where do channel changes happen, at a break (or lunch) or in the middle of a stretch? Plans Mon to Fri for a made-up team in
three settings (all off, Fixed, Balanced) and counts, per person-day, changes of channel with a break between the two blocks and without.
argv: scenario name (default base_16)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import channel_scenarios as cs
from webapp.channel_plan import plan_day

def split_changes(people, plan):
    mid = at_break = 0
    for p in people:
        name = p["name"]
        spans = [(s, s + m) for (_, _, m), s in zip(p["breaks"], plan["breaks"].get(name, [])) if s is not None]
        work = sorted((a, b, c) for a, b, c in plan["blocks"].get(name, []) if c in "PCE")
        for (a1, b1, c1), (a2, b2, c2) in zip(work, work[1:]):
            if c1 != c2:
                if any(b1 <= s and e <= a2 for s, e in spans) or a2 > b1:
                    at_break += 1
                else:
                    mid += 1
    return mid, at_break

def run(name, rules):
    people, config = cs.SCENARIOS[name]()
    config["rules"] = dict(config["rules"], **rules)
    carry, mid, brk, days = {}, 0, 0, 0
    for d in cs.DAYS:
        plan = plan_day(people, config, cs.RULES, d, carry=carry, move_breaks=False)
        m, b = split_changes(people, plan)
        mid, brk, days = mid + m, brk + b, days + len(people)
        for person, blocks in plan["blocks"].items():
            for a, b2, c in blocks:
                if c in "PCE":
                    carry.setdefault(person, {})[c] = carry.get(person, {}).get(c, 0) + b2 - a
    return round(mid / days, 2), round(brk / days, 2)

if __name__ == "__main__":
    scenario = sys.argv[1] if len(sys.argv) > 1 else "base_16"
    for label, rules in (("both off", dict(fair=False, consistent=False, balanced=False)), ("fixed", dict(fair=False, consistent=True, balanced=False)),
                         ("balanced", dict(fair=False, consistent=False, balanced=True))):
        mid, brk = run(scenario, rules)
        print(f"{scenario:10} {label:9} changes per person-day: in the middle of a stretch {mid}, at a break {brk}", flush=True)
