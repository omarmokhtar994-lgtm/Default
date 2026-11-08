# © 2026 Omar Mokhtar. All rights reserved.
"""The weeks and months ahead from the history (Phase BL, owner, 2026-11-07).

A robust line through the weekly totals (growth held to 50 percent a year), times a seasonal index for each week of the year the history has seen.
What the history has not seen is said so: ``basis`` is "learned" (a week of the year the history covers), "unseen" (it does not: the trend alone, a
wider band), "typed" (the planner typed an index for that month) or "trend" (under 26 weeks of history: the trend alone, at most 8 weeks ahead).
The planner's year-over-year rate, when given, replaces the measured trend. Pure: dates and numbers in, dicts out, no store."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from . import drivers as D
from .forecast import MIN_WEEKS, _theil_sen

SEASONAL_WEEKS = 52          # a year: every week of the year the history covers is learned
PARTIAL_WEEKS = 26           # half a year: the weeks it covers are learned, the rest are the trend alone
TREND_REACH = 8              # under half a year: the trend alone, this many weeks ahead
MAX_YEARLY_GROWTH = 0.5      # the measured trend is held to this much of the level in a year: a short run of growth is not a law
LOOK_BACK_WEEKS = 104        # two years are enough to learn a season
MIN_YEARLY_PAIRS = 4         # same-week-a-year-earlier comparisons needed before the trend is taken from them
BAND = {"learned": 10.0, "unseen": 20.0, "typed": 15.0, "trend": 15.0}     # percent each side of the expected figure; a range, not a statistic


def woy(day: date) -> int:
    """The week of the year, 0 to 51: seven-day buckets from 1 January, the last day or two joining the last bucket."""
    return min(51, (day.timetuple().tm_yday - 1) // 7)


@dataclass
class Model:
    kind: str                                  # "seasonal", "partial" or "trend"
    weeks: int                                 # whole weeks the line and the index stand on
    last: date                                 # the newest of them
    level: float                               # the line's value at that week
    slope: float                               # per week, held to MAX_YEARLY_GROWTH
    index: Dict[int, float] = field(default_factory=dict)      # week of the year -> index, for the weeks of the year the history covers


def fit(weekly: Sequence[Tuple[date, float]], left_out: Iterable[date] = ()) -> Model:
    """The model from whole weeks' totals ((Sunday, total) pairs); ``left_out`` are weeks to ignore (a holiday week, a week the planner left out)."""
    skip = set(left_out)
    pts = sorted((d, float(t)) for d, t in weekly if d not in skip)[-LOOK_BACK_WEEKS:]
    if len(pts) < MIN_WEEKS:
        raise ValueError(f"A forecast for the months ahead needs at least {MIN_WEEKS} whole weeks of history.")
    first = pts[0][0]
    xy = [(float((d - first).days) / 7.0, t) for d, t in pts]
    slope, level = _theil_sen(xy)
    last_x = xy[-1][0]
    n = len(pts)
    kind = "seasonal" if n >= SEASONAL_WEEKS else "partial" if n >= PARTIAL_WEEKS else "trend"
    if n >= SEASONAL_WEEKS + MIN_YEARLY_PAIRS:
        # with a year and more the trend is the median change from the same week a year earlier: that comparison cancels the season, which a line
        # through the weeks would mistake for growth (and carry on)
        before = {d: t for d, t in pts}
        changes = [(t - before[d - timedelta(weeks=52)]) / 52.0 for d, t in pts if d - timedelta(weeks=52) in before]
        if len(changes) >= MIN_YEARLY_PAIRS:
            slope = statistics.median(changes)
            level = sum(t - slope * (x - last_x) for (_, t), (x, _) in zip(pts[-52:], xy[-52:])) / len(pts[-52:])   # the mean of the latest year, season-neutral
    held = MAX_YEARLY_GROWTH * max(level, 0.0) / 52.0
    kept = max(-held, min(held, slope))
    index: Dict[int, float] = {}
    if kind != "trend":
        raw: Dict[int, List[float]] = {}
        for (d, t), (x, _) in zip(pts, xy):
            line = level + slope * (x - last_x)
            if line > 0:
                raw.setdefault(woy(d), []).append(t / line)
        mean = {w: sum(v) / len(v) for w, v in raw.items()}
        for w in mean:                         # a week's index is the mean of it and its neighbours (the year wraps), so one odd week cannot make a season
            near = [mean[v] for v in ((w - 1) % 52, w, (w + 1) % 52) if v in mean]
            index[w] = sum(near) / len(near)
    return Model(kind=kind, weeks=n, last=pts[-1][0], level=level, slope=kept, index=index)


def project(model: Model, week_start: date, yoy: Optional[float] = None, typed: Optional[Dict[int, float]] = None) -> Optional[Dict[str, Any]]:
    """The expected total of the week starting ``week_start`` with a band, how it was worked out, and the index used; None beyond what the history can
    reach (a trend alone is not shown past 8 weeks). ``yoy`` is the planner's year-over-year percent; ``typed`` maps a month (1 to 12) to a percent of the
    trend, used only for a week of the year the history has not seen."""
    ahead = (week_start - model.last).days / 7.0
    if model.kind == "trend" and ahead > TREND_REACH:
        return None
    level = model.level * D.weekly_factor(yoy, ahead) if yoy is not None else model.level + model.slope * ahead
    level = max(0.0, level)
    if model.kind == "trend":
        basis, idx = "trend", 1.0
    elif woy(week_start) in model.index:
        basis, idx = "learned", model.index[woy(week_start)]
    elif typed and (week_start + timedelta(days=3)).month in typed:
        basis, idx = "typed", typed[(week_start + timedelta(days=3)).month] / 100.0
    else:
        basis, idx = "unseen", 1.0
    expected = level * idx
    band = BAND[basis] / 100.0
    return {"expected": expected, "low": expected * (1 - band), "high": expected * (1 + band), "basis": basis, "index": idx}
