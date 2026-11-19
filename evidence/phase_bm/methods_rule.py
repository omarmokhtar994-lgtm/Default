# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM: the pre-registered test of methods.md. Four made-up histories with a known truth; the last four weeks are held out one at a time; the
method the back-test picks (from the weeks before the held-out week only) against the trend. Run from the repository root:

    python evidence/phase_bm/methods_rule.py [margin] [first seed]"""
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from webapp import forecast_methods as M  # noqa: E402

START = date(2025, 6, 1)
WEEKS = 70


def make(kind, seed):
    r = random.Random(seed)
    out = []
    for i in range(WEEKS):
        level = 10000.0
        noise = 0.06
        if kind == "rise":
            level *= 1.008 ** i
        elif kind == "season":
            level *= 1 + 0.25 * math.sin(2 * math.pi * i / 52.0)
            noise = 0.05
        elif kind == "shift" and i >= WEEKS - 12:
            level *= 1.3
        out.append((START + timedelta(weeks=i), max(0.0, level * (1 + r.gauss(0, noise)))))
    return out


def wape(pairs):
    return sum(abs(f - a) for f, a in pairs) / sum(a for _, a in pairs)


MARGIN = float(sys.argv[1]) if len(sys.argv) > 1 else None      # candidate 2: take the pick only at this share of the trend's back-test error
FIRST = int(sys.argv[2]) if len(sys.argv) > 2 else 11
rows, kept = [], 0
for kind, seed in (("flat", FIRST), ("rise", FIRST + 1), ("season", FIRST + 2), ("shift", FIRST + 3)):
    series = make(kind, seed)
    picked, trend, names = [], [], []
    for i in range(WEEKS - 4, WEEKS):
        target, actual = series[i]
        clean = [w for w in series[:i] if w[0] not in M.unusual(series[:i])]
        test = M.backtest(clean, target)
        best = test["best"] or "trend"
        if MARGIN is not None and best != "trend":
            trend_error = test["methods"].get("trend", {}).get("wape")
            if trend_error is None or test["methods"][best]["wape"] > MARGIN * trend_error:
                best = "trend"
        names.append(best)
        picked.append((M.predict(best, clean, target), actual))
        trend.append((M.predict("trend", clean, target), actual))
    p, t = wape(picked), wape(trend)
    rows.append((kind, names, p, t))
    print(f"{kind:7s} picked {100 * p:5.2f} %  trend {100 * t:5.2f} %  methods {names}")
no_worse = sum(1 for _, _, p, t in rows if p <= t)
worst = max(p - t for _, _, p, t in rows)
print(f"no higher than the trend on {no_worse} of 4; largest excess {100 * worst:.2f} points")
print("RULE MET" if no_worse >= 3 and worst <= 0.02 else "RULE NOT MET")
