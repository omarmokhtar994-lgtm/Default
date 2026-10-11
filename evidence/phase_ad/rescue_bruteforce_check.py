"""Independent check of Rescue the day on small made-up days: try every placement of the breaks on a 30-minute grid,
count each with the page's own day_view, keep the placements the rules allow, and compare the best with what the
solver finds (on its finer 5-minute grid it must do at least as well, and its answer must itself obey the rules)."""
import itertools, random, sys, time
sys.path.insert(0, "/home/user/Default")
from webapp import rescue
from webapp.day import at_target, day_view
from webapp.versions import DAYS
D = 3
def hm(m): return f"{m // 60:02d}:{m % 60:02d}"

def build(seed):
    rnd = random.Random(seed)
    people, breaks = [], []
    for i in range(rnd.choice((3, 4))):
        start = rnd.choice((480, 540, 600))
        end = start + rnd.choice((300, 360))
        name = f"Associate {i + 1:03d}"
        people.append({"name": name, "slot": str(i + 1), "language": "ARA",
                       "days": ["OFF"] * D + [f"{hm(start)} - {hm(end)}"] + ["OFF"] * (6 - D)})
        breaks.append({"associate": name, "day": DAYS[D], "kind": "Lunch", "start": hm(start + rnd.choice((60, 120, 180))), "minutes": 60})
    wk = {"associates": people, "breaks": breaks}
    inp = {"interval": 60, "required": {D: {}}, "languages": [], "previous_saturday": [], "gap_min": None, "gap_max": None}
    v = day_view(wk, inp, D, {}, {})
    for c in v["cells"]:
        if c["plan"] > 0:
            inp["required"][D][c["t"]] = round(rnd.uniform(0.75, 1.25) * c["plan"] + 0.4, 1)
    return wk, inp

def judge(before_cells, after_cells, target, may):
    """(valid, at, given) for a placement: the rules, counted from the page's figures."""
    at = given = 0
    for b, a in zip(before_cells, after_cells):
        r = b["required"]
        if r <= 0:
            continue
        ok_b, ok_a = b["now"] >= target * r - 1e-9, a["now"] >= target * r - 1e-9
        at += ok_a
        if a["now"] < min(b["now"], 0.5 * r) - 1e-9:
            return False, 0, 0  # below 50% (or below where it was, if lower)
        if not ok_a and a["now"] < b["now"] - 1e-9:
            given += 1  # fell, and is not at the target
    return given <= may, at, given

worse = 0
rows = []
for seed in range(24):
    wk, inp = build(seed)
    v = day_view(wk, inp, D, {}, {})
    target = 0.9
    segs = {l["name"]: l["segments"][0] for l in v["lanes"]}
    choices = []
    for name, s in segs.items():
        b = s["breaks"][0]
        choices.append([(name, b["idx"], t) for t in range(s["start"], s["end"] - 60 + 1, 30)])
    best = {may: (-1, 99) for may in range(4)}
    for combo in itertools.product(*choices):  # each placement counted once by the page, judged for every allowance
        after = day_view(wk, inp, D, {}, {(0, n, i): t for n, i, t in combo})
        for may in range(4):
            valid, at, given = judge(v["cells"], after["cells"], target, may)
            if valid and (at, -given) > (best[may][0], -best[may][1]):
                best[may] = (at, given)
    before_at = at_target(v["cells"], target)["now"]
    for may in range(4):
        found = rescue.solve(v, inp, target, None, may, seconds=20.0)
        after = day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in found["moves"]})
        valid, at, given = judge(v["cells"], after["cells"], target, may)
        rows.append((seed, may, before_at, best[may], at, given, valid, found["status"], found["solver"]))
        flag = "PROBLEM" if (not valid or at < best[may][0] or (at == best[may][0] and given > best[may][1])) else "ok"
        worse += flag == "PROBLEM"
        print(flag, f"seed={seed} may={may} before={before_at} grid-best={best[may]} solver=({at}, {given}) "
              f"valid={valid} {found['status']} {found['solver']}", flush=True)
print("cases", len(rows), "problems", worse)
print("solver beat the 30-minute grid in", sum(1 for r in rows if r[4] > r[3][0]), "cases;",
      "rescued something in", sum(1 for r in rows if r[4] > r[2]), "cases;",
      "gave up at least one in", sum(1 for r in rows if r[5] > 0), "cases", flush=True)
