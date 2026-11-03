# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: the volume forecast, from the program's own history (owner, 2026-11-03: "I can give the count of calls for next week and it
automatically calculates calls per interval", "see trends", "calculate the OTF").

What it does, in the order a planner thinks:
  1. ``build_profile``: from the last weeks of actual volume, the shape of each weekday (the share of the day in each interval) and of the week
     (the share of the week on each weekday). Days that would spoil the shape (a holiday at a fifth of the usual volume, a day the planner names)
     are left out and listed; a weekday with fewer than three usable weeks is called thin and borrows part of its shape from the others.
  2. ``suggest_total``: from the weekly totals, a suggested total for next week with a range (a robust trend line, damped, and the spread
     around it). A suggestion only: the planner's own number always wins.
  3. ``forecast_week``: the planner's week total (or day totals) spread over days and intervals as whole numbers that add up exactly.
  4. ``otf`` and ``band``: offered divided by forecast, as a percent, and where it sits against a band (default 90 to 110).

Weekdays are Python's (Monday is 0, Sunday is 6); the pages convert to the program's week start. Pure functions, standard library only.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

LOW_DAY = 0.25      # a day under a quarter of its weekday's usual total is left out
HIGH_DAY = 2.5      # a day over two and a half times it is left out
MIN_WEEKS = 3       # usable weeks for a weekday to stand on its own shape


@dataclass
class Profile:
    step: int
    shares: Dict[int, List[float]]          # weekday -> share of the day in each interval (adds to 1; all 0 on a closed weekday)
    day_shares: Dict[int, float]            # weekday -> share of the week (adds to 1 over the weekdays seen)
    weeks_used: Dict[int, int]              # weekday -> usable weeks behind its shape
    excluded: List[Tuple[str, str]] = field(default_factory=list)   # (date, why)
    thin: List[int] = field(default_factory=list)                   # weekdays with fewer than MIN_WEEKS usable weeks
    closed: List[int] = field(default_factory=list)                 # weekdays that had no volume at all in the weeks looked at


def _normalise(values: Sequence[float]) -> List[float]:
    total = sum(values)
    return [v / total for v in values] if total > 0 else [0.0] * len(values)


def build_profile(days: Dict[date, List[float]], step: int, weeks: int = 8, today: Optional[date] = None,
                  exclude: Iterable[date] = ()) -> Profile:
    """The shape of each weekday and of the week from the ``weeks`` weeks before ``today``. ``days`` maps a date to its volume per interval."""
    if step <= 0 or 1440 % step:
        raise ValueError("The interval must divide a day.")
    slots = 1440 // step
    today = today or date.today()
    first = today - timedelta(weeks=weeks)
    named = {d for d in exclude}
    window = {d: v for d, v in days.items() if first <= d < today}
    for d, v in window.items():
        if len(v) != slots:
            raise ValueError(f"{d.isoformat()} has {len(v)} intervals; a {step}-minute day has {slots}.")
        if any(x < 0 for x in v):
            raise ValueError(f"{d.isoformat()} has a negative volume.")
    if not window:
        raise ValueError("There is no volume history in the last weeks to build a shape from.")

    excluded: List[Tuple[str, str]] = []
    usable: Dict[int, List[List[float]]] = {w: [] for w in range(7)}
    totals: Dict[int, List[float]] = {w: [] for w in range(7)}
    seen: Dict[int, int] = {w: 0 for w in range(7)}
    for wd in range(7):
        mine = sorted((d, v) for d, v in window.items() if d.weekday() == wd)
        seen[wd] = len(mine)
        live = [(d, v) for d, v in mine if d not in named and sum(v) > 0]
        for d, v in mine:
            if d in named:
                excluded.append((d.isoformat(), "left out by you"))
        median_total = statistics.median(sum(v) for _, v in live) if live else 0.0
        for d, v in live:
            if sum(v) < LOW_DAY * median_total:
                excluded.append((d.isoformat(), "far below a usual day (a holiday or an outage?)"))
            elif sum(v) > HIGH_DAY * median_total:
                excluded.append((d.isoformat(), "far above a usual day"))
            else:
                usable[wd].append(_normalise(v))
                totals[wd].append(sum(v))
    excluded.sort()
    empty_only = {wd for wd in range(7)
                  if seen[wd] and all(d not in named and sum(v) <= 0 for d, v in window.items() if d.weekday() == wd)}

    own: Dict[int, List[float]] = {}
    for wd in range(7):
        if usable[wd]:
            own[wd] = _normalise([statistics.median(day[i] for day in usable[wd]) for i in range(slots)])
    stable = [wd for wd in own if len(usable[wd]) >= MIN_WEEKS] or list(own)
    if not stable:
        raise ValueError("Every day in the last weeks was left out or had no volume.")
    pooled = _normalise([sum(own[wd][i] for wd in stable) / len(stable) for i in range(slots)])

    shares: Dict[int, List[float]] = {}
    thin: List[int] = []
    closed: List[int] = []
    for wd in range(7):
        n = len(usable[wd])
        if seen[wd] and not n and wd in empty_only:
            closed.append(wd)       # looked at, and always empty: the weekday is closed
            shares[wd] = [0.0] * slots
            continue
        if n >= MIN_WEEKS:
            shares[wd] = own[wd]
        else:
            thin.append(wd)
            weight = n / MIN_WEEKS
            mine = own.get(wd)
            shares[wd] = _normalise([(weight * mine[i] if mine else 0.0) + (1 - weight) * pooled[i] for i in range(slots)])
    medians = {wd: statistics.median(totals[wd]) if totals[wd] else 0.0 for wd in range(7)}
    week = sum(medians.values())
    day_shares = {wd: (medians[wd] / week if week > 0 else 0.0) for wd in range(7)}
    return Profile(step=step, shares=shares, day_shares=day_shares, weeks_used={wd: len(usable[wd]) for wd in range(7)},
                   excluded=excluded, thin=sorted(thin), closed=sorted(closed))


def _theil_sen(values: Sequence[float]) -> Tuple[float, float]:
    """A robust line through the series: (slope, level at the last point)."""
    n = len(values)
    slopes = [(values[j] - values[i]) / (j - i) for i in range(n) for j in range(i + 1, n)]
    slope = statistics.median(slopes) if slopes else 0.0
    intercept = statistics.median(values[i] - slope * i for i in range(n))
    return slope, intercept + slope * (n - 1)


def suggest_total(weekly_totals: Sequence[float]) -> Optional[Tuple[int, int, int]]:
    """(suggested, low, high) for next week from the last up to eight weekly totals, oldest first; None with fewer than three weeks.

    The level is where a robust line ends; the trend adds half of one week's slope (damped: a short run of growth is not a law); the range is
    the spread of the weeks around the line (about an 80 percent band)."""
    series = [float(v) for v in weekly_totals][-8:]
    if len(series) < 3:
        return None
    slope, level = _theil_sen(series)
    suggested = max(0.0, level + 0.5 * slope)
    fitted_end = level
    residuals = [series[i] - (fitted_end - slope * (len(series) - 1 - i)) for i in range(len(series))]
    centre = statistics.median(residuals)
    mad = statistics.median(abs(r - centre) for r in residuals)
    spread = 1.28 * 1.4826 * mad
    return int(round(suggested)), int(round(max(0.0, suggested - spread))), int(round(suggested + spread))


def distribute(total: int, shares: Sequence[float]) -> List[int]:
    """``total`` spread over ``shares`` as whole numbers that add up to ``total`` (the largest remainders get the leftovers)."""
    if int(total) != total or total < 0:
        raise ValueError("A volume is a whole number, zero or more.")
    total = int(total)
    weight = sum(shares)
    if any(s < 0 for s in shares):
        raise ValueError("A share cannot be negative.")
    if weight <= 0:
        if total:
            raise ValueError("There is nothing to spread the volume over.")
        return [0] * len(shares)
    exact = [total * s / weight for s in shares]
    out = [int(math.floor(x)) for x in exact]
    left = total - sum(out)
    order = sorted(range(len(shares)), key=lambda i: (-(exact[i] - out[i]), i))
    for i in order[:left]:
        out[i] += 1
    return out


def forecast_week(total: int, profile: Profile, day_totals: Optional[Dict[int, int]] = None) -> Dict[int, List[int]]:
    """A week of volume per interval, by weekday, from the week's total. Typed day totals are kept exactly; the rest of the total is shared by
    the other days in proportion to their usual share of the week."""
    if int(total) != total or total < 0:
        raise ValueError("The week's volume is a whole number, zero or more.")
    typed = {int(d): int(v) for d, v in (day_totals or {}).items() if v is not None}
    for d, v in typed.items():
        if d not in range(7) or v < 0:
            raise ValueError("A day's volume is a whole number, zero or more.")
    left = int(total) - sum(typed.values())
    if left < 0:
        raise ValueError("The days add up to more than the week's volume.")
    rest = [d for d in range(7) if d not in typed]
    if not rest and left:
        raise ValueError("The days add up to less than the week's volume.")
    per_day = dict(typed)
    if rest:
        part = distribute(left, [profile.day_shares[d] for d in rest])
        per_day.update(dict(zip(rest, part)))
    week: Dict[int, List[int]] = {}
    for d in range(7):
        if per_day[d] and sum(profile.shares[d]) <= 0:
            raise ValueError("That weekday has no hours of its own in the history; give it no volume or fix the history.")
        week[d] = distribute(per_day[d], profile.shares[d])
    return week


def otf(actual: float, forecast: float) -> Optional[float]:
    """Offered over forecast, in percent; None when there was no forecast (an empty interval says nothing, it is not 0 percent)."""
    if forecast is None or forecast <= 0:
        return None
    return 100.0 * actual / forecast


def otf_total(actuals: Sequence[float], forecasts: Sequence[float]) -> Optional[float]:
    """Offered over forecast for a day or a week: the ratio of the sums, so a busy interval counts for more than a quiet one."""
    return otf(sum(actuals), sum(forecasts))


def band(value: Optional[float], low: float = 90.0, high: float = 110.0) -> str:
    """Where an OTF sits: "under" below the band, "on" inside it (the ends count as inside), "over" above, "none" without a value."""
    if value is None:
        return "none"
    if value < low:
        return "under"
    if value > high:
        return "over"
    return "on"
