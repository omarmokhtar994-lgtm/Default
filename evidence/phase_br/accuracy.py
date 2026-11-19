# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BR: the forecast measured against a known truth (rules: evidence/phase_br/RULES.md, written before the first run).

Made-up histories: 30-minute intervals, Poisson counts around a known weekday shape. R1 scores the interval shape (M today, A mean, P pooled) given the
true week total; R2 scores the people needed with one handle time for the week (today) against a handle time per weekday and interval (H).
Run from the repository root:  PYTHONPATH=. python evidence/phase_br/accuracy.py FIRST_SEED   (seeds FIRST_SEED to FIRST_SEED + 4)"""
import math
import random
import statistics
import sys
from datetime import date, timedelta

from webapp import erlang
from webapp import forecast as F

STEP, SLOTS = 30, 48
WEEKS = 6
TARGET = date(2026, 6, 7)        # a Sunday; the history is the weeks before it
LEVELS = (1500, 7000, 35000, 200000)
DAY_MIX = {0: 0.17, 1: 0.165, 2: 0.16, 3: 0.155, 4: 0.15, 5: 0.10, 6: 0.10}   # Python weekdays; a lighter weekend
K = 20                           # R2: contacts at which an interval's own handle time counts half


def day_shape(weekday, grow=1.0):
    """Shares of the day per interval: open 08:00 to 24:00, a morning peak at 11:00 and an evening one at 19:00 (``grow`` scales the evening)."""
    raw = []
    for s in range(SLOTS):
        h = s / 2.0 + 0.25
        if h < 8:
            raw.append(0.0)
            continue
        morning = math.exp(-((h - 11.0) ** 2) / 4.0)
        evening = (0.8 if weekday < 5 else 1.1) * grow * math.exp(-((h - 19.0) ** 2) / 5.0)
        raw.append(0.08 + morning + evening)
    total = sum(raw)
    return [v / total for v in raw]


def poisson(rng, lam):
    if lam <= 0:
        return 0
    if lam > 60:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def true_aht(slot, varying):
    if not varying:
        return 300.0
    if slot >= 40:
        return 300.0 * 1.25
    if 16 <= slot < 22:
        return 300.0 * 0.85
    return 300.0


def expected_week(level, week_no, drift):
    """weekday -> expected count per interval; ``week_no`` counts weeks, the target week being WEEKS."""
    grow = 1.02 ** week_no if drift else 1.0
    return {w: [level * DAY_MIX[w] * v for v in day_shape(w, grow)] for w in range(7)}


def history(rng, level, drift, varying):
    """Days of counts and recorded handle times for the WEEKS weeks before TARGET, and the target week's truth."""
    days, aht = {}, {}
    for k in range(WEEKS):
        start = TARGET - timedelta(weeks=WEEKS - k)
        exp = expected_week(level, k, drift)
        for off in range(7):
            day = start + timedelta(days=off)
            counts = [poisson(rng, lam) for lam in exp[day.weekday()]]
            days[day] = [float(c) for c in counts]
            aht[day] = [rng.gammavariate(c, true_aht(s, varying)) / c if c else None for s, c in enumerate(counts)]
    return days, aht, expected_week(level, WEEKS, drift)


def profile_m(days):
    choice = F.choose_weeks(days, STEP, TARGET, WEEKS)
    return choice, F.build_profile(days, STEP, choice)


def shapes(days, choice, how):
    """weekday -> shape by ``how`` ("A" mean of day shares, "P" pooled counts)."""
    out = {}
    for w in range(7):
        rows = [days[d] for d in days if d.weekday() == w and d - timedelta(days=(d.weekday() + 1) % 7) in choice.used]
        if how == "A":
            shares = [F._normalise(r) for r in rows]
            out[w] = F._normalise([statistics.mean(r[i] for r in shares) for i in range(SLOTS)])
        else:
            out[w] = F._normalise([sum(r[i] for r in rows) for i in range(SLOTS)])
    return out


def wape(forecast, truth):
    diff = sum(abs(f - t) for w in range(7) for f, t in zip(forecast[w], truth[w]))
    return 100.0 * diff / sum(sum(truth[w]) for w in range(7))


def r1(seed, level, drift):
    rng = random.Random(seed * 1000 + level + (7 if drift else 0))
    days, _, truth = history(rng, level, drift, False)
    choice, prof = profile_m(days)
    total = int(round(sum(sum(v) for v in truth.values())))
    out = {"M": wape(F.forecast_week(total, prof), truth)}
    for how in ("A", "P"):
        alt = F.Profile(step=STEP, shares=shapes(days, choice, how), day_shares=prof.day_shares, weeks_used=prof.weeks_used)
        out[how] = wape(F.forecast_week(total, alt), truth)
    return out


def needs(calls, aht):
    return erlang.agents_needed(calls, aht, STEP * 60, 0.8, 20, 0.88) if calls > 0 else 0


def r2(seed, level, varying):
    rng = random.Random(seed * 7919 + level + (3 if varying else 0))
    days, aht, truth = history(rng, level, False, varying)
    choice, prof = profile_m(days)
    total = int(round(sum(sum(v) for v in truth.values())))
    week = F.forecast_week(total, prof)
    used = [d for d in days if d - timedelta(days=(d.weekday() + 1) % 7) in choice.used]
    vol = sum(days[d][s] for d in used for s in range(SLOTS) if aht[d][s] is not None)
    single = sum(days[d][s] * aht[d][s] for d in used for s in range(SLOTS) if aht[d][s] is not None) / vol
    grid = {}
    for w in range(7):
        grid[w] = []
        for s in range(SLOTS):
            n = sum(days[d][s] for d in used if d.weekday() == w and aht[d][s] is not None)
            own = sum(days[d][s] * aht[d][s] for d in used if d.weekday() == w and aht[d][s] is not None) / n if n else single
            weight = n / (n + K)
            grid[w].append(weight * own + (1 - weight) * single)
    true_need = [needs(truth[w][s], true_aht(s, varying)) for w in range(7) for s in range(SLOTS)]
    one = [needs(week[w][s], single) for w in range(7) for s in range(SLOTS)]
    per = [needs(week[w][s], grid[w][s]) for w in range(7) for s in range(SLOTS)]
    base = sum(true_need)
    return {"single": 100.0 * sum(abs(a - b) for a, b in zip(one, true_need)) / base,
            "H": 100.0 * sum(abs(a - b) for a, b in zip(per, true_need)) / base}


def main(first):
    seeds = range(first, first + 5)
    print(f"Seeds {first} to {first + 4}; each figure is the mean over the five seeds.\n")
    print("R1, interval shape: WAPE % against the known expected counts")
    print(f"{'history':>14} {'M (today)':>10} {'A mean':>10} {'P pooled':>10}")
    cases = [(f"{lv:,}", lv, False) for lv in LEVELS] + [("drift 7,000", 7000, True)]
    r1_rows = {}
    for name, lv, drift in cases:
        runs = [r1(s, lv, drift) for s in seeds]
        r1_rows[name] = {k: statistics.mean(r[k] for r in runs) for k in ("M", "A", "P")}
        print(f"{name:>14} {r1_rows[name]['M']:>10.2f} {r1_rows[name]['A']:>10.2f} {r1_rows[name]['P']:>10.2f}")
    for cand in ("A", "P"):
        lower = sum(1 for r in r1_rows.values() if r[cand] < r["M"])
        worst = max(r[cand] - r["M"] for r in r1_rows.values())
        print(f"  {cand}: lower than M on {lower} of 5; largest excess {worst:+.2f} points; mean {statistics.mean(r[cand] for r in r1_rows.values()):.2f}"
              f" (M {statistics.mean(r['M'] for r in r1_rows.values()):.2f})")
    print("\nR2, people needed per interval: error % against the needs with the true counts and true handle time")
    print(f"{'history':>22} {'one handle time':>16} {'H by interval':>14}")
    for varying in (True, False):
        for lv in LEVELS:
            runs = [r2(s, lv, varying) for s in seeds]
            one, per = statistics.mean(r["single"] for r in runs), statistics.mean(r["H"] for r in runs)
            name = f"{lv:,} {'varying' if varying else 'flat'}"
            print(f"{name:>22} {one:>16.2f} {per:>14.2f}   {'H lower' if per < one else 'H not lower'} ({per - one:+.2f})")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
