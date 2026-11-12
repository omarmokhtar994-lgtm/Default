# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BO baseline: on made-up days ("Associate NN"), how the day page's break tools compare with each other on the page's own figures.
Arms: as planned (no change); Fix rest of the day (day.replan, greedy); Replan the day's breaks (day.replan fresh, greedy); Rescue the day with
nothing given up (rescue.solve, exact CP-SAT). Counted by day_view and at_target, the way the page counts.
    python evidence/phase_bo/bench_breaks.py [--json out.json]"""
import json, random, sys, time
sys.path.insert(0, ".")
from webapp import rescue
from webapp.day import at_target, day_view, replan
from webapp.versions import DAYS

D, TARGET = 3, 0.9
hm = lambda m: f"{m // 60:02d}:{m % 60:02d}"


def build(n, seed, tight):
    rnd = random.Random(seed)
    people, breaks = [], []
    for i in range(n):
        start = rnd.choice(range(420, 721, 30))
        end = start + 540
        name = f"Associate {i + 1:03d}"
        people.append({"name": name, "slot": str(i + 1), "language": "ENG", "days": ["OFF"] * D + [f"{hm(start)} - {hm(end)}"] + ["OFF"] * (6 - D)})
        for kind, minutes, at in (("Break 1", 15, 120), ("Lunch", 30, 240), ("Break 2", 15, 390)):  # the same offsets for all: breaks bunch up
            breaks.append({"associate": name, "day": DAYS[D], "kind": kind, "start": hm(start + at), "minutes": minutes})
    wk = {"associates": people, "breaks": breaks}
    inp = {"interval": 30, "required": {D: {}}, "languages": [], "previous_saturday": [], "gap_min": 60, "gap_max": 210}
    v = day_view(wk, inp, D, {}, {})
    for c in v["cells"]:
        if c["plan"] > 0:
            inp["required"][D][c["t"]] = round(rnd.uniform(tight - 0.12, tight + 0.08) * c["plan"], 1)
    return wk, inp


def figures(wk, inp, moves):
    v = day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in moves})
    a = at_target(v["cells"], TARGET)
    need = [c for c in v["cells"] if c["required"] > 0]
    short = sum(max(0.0, c["required"] - c["now"]) for c in need) * inp["interval"] / 60
    return {"at": a["now"], "of": a["intervals"], "safe": a.get("safe"), "short_h": round(short, 1), "moves": len(moves)}


rows = []
for n, tight in ((20, 0.95), (20, 1.05), (35, 0.95), (35, 1.05), (50, 0.95), (50, 1.05)):
    for seed in (1, 2):
        wk, inp = build(n, seed, tight)
        v = day_view(wk, inp, D, {}, {})
        row = {"case": f"n={n} need={tight} seed={seed}", "planned": figures(wk, inp, [])}
        for arm, run in (("fix", lambda: replan(v, inp, 0, target=TARGET)["moves"]),
                         ("fresh", lambda: replan(v, inp, 0, target=TARGET, fresh=True)["moves"]),
                         ("exact", lambda: rescue.solve(v, inp, TARGET, None, 0))):
            t = time.time()
            out = run()
            moves = out["moves"] if isinstance(out, dict) else out
            row[arm] = {**figures(wk, inp, moves), "s": round(time.time() - t, 1), **({"solver": out.get("solver")} if isinstance(out, dict) else {})}
        rows.append(row)
        print(row["case"], "| planned", row["planned"]["at"], "| fix", row["fix"]["at"], row["fix"]["s"], "| fresh", row["fresh"]["at"], row["fresh"]["s"],
              "| exact", row["exact"]["at"], row["exact"]["s"], row["exact"].get("solver"), "of", row["planned"]["of"], flush=True)
if "--json" in sys.argv:
    json.dump(rows, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
