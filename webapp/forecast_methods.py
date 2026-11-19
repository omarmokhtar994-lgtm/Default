# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BM: several ways to work out a week's contacts from the weeks before it, and a back-test that says which one this program's own history
supports. Everything here is weekly totals: the shape of the week (days and intervals) is ``forecast.py``'s.

A series is ``[(week start, total), ...]`` of clean whole weeks, oldest first; gaps (weeks left out) are fine. No method reads the target week or
any week after it."""
from __future__ import annotations

import statistics
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import forecast as F

Series = Sequence[Tuple[date, float]]
METHODS = ("trend", "recent", "last_week", "seasonal", "blend")
WORDS = {"trend": "the trend of the last weeks", "recent": "the last four weeks, the newest counting most", "last_week": "last week",
         "seasonal": "the same week last year, grown by this year's level", "blend": "the middle of the other methods"}
TREND_WEEKS = 6     # weeks the trend line is drawn through, as the page's default pattern weeks
MIN_TRAIN = 4       # weeks a tested week needs before it
MIN_TESTED = 4      # tested weeks a pick needs
YEAR = timedelta(days=364)


def _before(series: Series, target: date) -> List[Tuple[date, float]]:
    return sorted((d, float(t)) for d, t in series if d < target)


def predict(name: str, series: Series, target: date) -> Optional[float]:
    """The week starting ``target`` by method ``name``, from the weeks strictly before it; None when the method has too little to go on."""
    if name not in METHODS:
        raise ValueError("The method is one of: " + ", ".join(METHODS) + ".")
    past = _before(series, target)
    if not past:
        return None
    if name == "last_week":
        return past[-1][1]
    if name == "trend":
        found = F.suggest_total([(-((target - d).days // 7), t) for d, t in past[-TREND_WEEKS:]])
        return None if found is None else float(found[0])
    if name == "recent":
        last = past[-4:]
        if len(last) < 3:
            return None
        weights = range(1, len(last) + 1)
        return sum(w * t for w, (_, t) in zip(weights, last)) / sum(weights)
    if name == "seasonal":
        by_week = dict(past)
        then = by_week.get(target - YEAR)
        pairs = [(t, by_week[d - YEAR]) for d, t in past[-4:] if d - YEAR in by_week]
        if then is None or len(pairs) < 3 or sum(b for _, b in pairs) <= 0:
            return None
        return then * sum(a for a, _ in pairs) / sum(b for _, b in pairs)
    others = [v for v in (predict(n, past, target) for n in METHODS if n != "blend") if v is not None]
    return statistics.median(others) if len(others) >= 2 else None


def unusual(series: Series) -> Dict[date, str]:
    """Weeks whose total sits far from the robust line through all of them (more than 3.5 robust deviations and at least a quarter off the line),
    with the reason in words. Fewer than six weeks, or a history with no spread, marks nothing."""
    pts = sorted((d, float(t)) for d, t in series)
    if len(pts) < 6:
        return {}
    first = pts[0][0]
    xy = [((d - first).days / 7.0, t) for d, t in pts]
    slope, level = F._theil_sen(xy)
    last_x = xy[-1][0]
    line = [level + slope * (x - last_x) for x, _ in xy]
    residuals = [y - fit for (_, y), fit in zip(xy, line)]
    centre = statistics.median(residuals)
    mad = statistics.median(abs(r - centre) for r in residuals)
    out: Dict[date, str] = {}
    for (d, total), fit, r in zip(pts, line, residuals):
        far = abs(r - centre) > 3.5 * 1.4826 * mad if mad > 0 else abs(r - centre) > 0
        if far and fit > 0 and abs(total - fit) >= 0.25 * fit:
            out[d] = f"an unusual week: {int(round(total)):,} contacts where the weeks around it point to about {int(round(fit)):,}"
    return out


def backtest(series: Series, target: date, weeks: int = 8) -> Dict[str, Any]:
    """Each of the last ``weeks`` weeks before ``target`` that has at least ``MIN_TRAIN`` weeks before it, predicted by every method from the weeks
    before it only. ``methods``: name -> {"wape": sum of absolute misses over sum of actuals, "bias": sum of misses over sum of actuals (below zero:
    it comes in low), "tested": n} for the methods that answered every tested week; ``best``: the lowest wape (the earlier name on a tie), None with
    fewer than ``MIN_TESTED`` tested weeks or no volume; ``range``: the best method's 80th percentile absolute miss as a share of the actual."""
    past = _before(series, target)
    tested = [i for i in range(len(past)) if i >= MIN_TRAIN][-weeks:]
    actual_sum = sum(past[i][1] for i in tested)
    out: Dict[str, Any] = {"tested": len(tested), "methods": {}, "best": None, "range": None, "weeks": [past[i][0].isoformat() for i in tested]}
    if not tested or actual_sum <= 0:
        return out
    shares: Dict[str, List[float]] = {}
    for name in METHODS:
        misses: List[float] = []
        for i in tested:
            got = predict(name, past[:i], past[i][0])
            if got is None:
                break
            misses.append(got - past[i][1])
        else:
            out["methods"][name] = {"wape": round(sum(abs(m) for m in misses) / actual_sum, 4), "bias": round(sum(misses) / actual_sum, 4),
                                    "tested": len(misses)}
            shares[name] = sorted(abs(m) / past[i][1] for m, i in zip(misses, tested) if past[i][1] > 0)
    if len(tested) >= MIN_TESTED and out["methods"]:
        best = min(out["methods"], key=lambda n: (out["methods"][n]["wape"], METHODS.index(n)))
        out["best"] = best
        ranked = shares[best]
        out["range"] = round(ranked[min(len(ranked) - 1, int(0.8 * len(ranked)))], 4) if ranked else 0.0
    return out
