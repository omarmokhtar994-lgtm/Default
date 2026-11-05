# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: the volume forecast, from the program's own history (owner, 2026-11-03: "I can give the count of calls for next week and it
automatically calculates calls per interval", "see trends", "calculate the OTF").

What it does, in the order a planner thinks:
  1. ``choose_weeks``: the last N whole weeks (six unless asked otherwise) that are clean. Every weekday is read from the same weeks, so six Sundays means
     six Saturdays: a week with a holiday, an outage, a missing or part day, an odd total, or one the planner leaves out is dropped as a whole and an older
     clean week steps in. What was dropped, and why, is kept for the page.
  2. ``build_profile``: from those weeks, each weekday's interval shape and the week's day mix. Days and weeks are first turned into shares of their own
     totals (the normalising), so busier weeks do not outweigh quieter ones.
  3. ``suggest_total``: from the chosen weeks' totals, a suggested total with a range (a robust trend line that respects gaps, damped, and the spread
     around it). A suggestion only: the planner's own number always wins.
  4. ``forecast_week``: the planner's week total (or day totals) spread over days and intervals as whole numbers that add up exactly.
  5. ``otf`` and ``band``: offered divided by forecast, as a percent, and where it sits against a band (default 90 to 110).

Weekdays are Python's (Monday is 0, Sunday is 6); the pages convert to the program's week start. Pure functions, standard library only.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

LOW_DAY = 0.25      # a day under a quarter of its weekday's usual total is far below usual (a holiday, an outage)
HIGH_DAY = 2.5      # and over two and a half times it is far above
PART_DAY = 0.5      # a day with under half the usual number of busy intervals has only part of its data
LOW_WEEK, HIGH_WEEK = 0.6, 1.6   # a week whose total is outside this share of the usual week is left out
MIN_WEEKS = 3       # fewest clean weeks a shape can stand on
EXTRA_LOOKBACK = 8  # older weeks that may step in for a week that was left out


@dataclass
class WeekChoice:
    """The whole weeks a shape is read from. Every open weekday is read from all of them, so each has the same number of days."""
    used: List[date]                                   # week starts, oldest first
    skipped: List[Tuple[str, str]]                     # (week start, why), newest first; only weeks newer than the oldest one used
    open_days: List[int]                               # Python weekdays that carry volume
    closed: List[int]                                  # Python weekdays that had none in most weeks
    wanted: int
    short: bool                                        # fewer clean weeks than wanted


@dataclass
class Profile:
    step: int
    shares: Dict[int, List[float]]          # weekday -> share of the day in each interval (adds to 1; all 0 on a closed weekday)
    day_shares: Dict[int, float]            # weekday -> share of the week (adds to 1 over the open weekdays)
    weeks_used: Dict[int, int]              # weekday -> weeks behind its shape: the same for every open weekday
    used: List[str] = field(default_factory=list)                     # week starts used, oldest first
    skipped: List[Tuple[str, str]] = field(default_factory=list)      # (week start, why)
    closed: List[int] = field(default_factory=list)
    short: bool = False


def _normalise(values: Sequence[float]) -> List[float]:
    total = sum(values)
    return [v / total for v in values] if total > 0 else [0.0] * len(values)


_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def choose_weeks(days: Dict[date, List[float]], step: int, week_start: date, weeks: int = 6, exclude_weeks: Iterable[str] = (),
                 extra: int = EXTRA_LOOKBACK) -> WeekChoice:
    """The ``weeks`` most recent clean whole weeks before the week starting ``week_start``. A week is clean when every open weekday has its day, no day
    is far below or above its weekday's usual, no day holds only part of its data, the week's total is near the usual, and the planner has not left it
    out. A week that is not clean is left out as a whole (with its reason) and the next older clean week steps in, so every weekday is read from the
    same weeks: six Sundays means six Saturdays."""
    if step <= 0 or 1440 % step:
        raise ValueError("The interval must divide a day.")
    slots = 1440 // step
    for d, v in days.items():
        if len(v) != slots:
            raise ValueError(f"{d.isoformat()} has {len(v)} intervals; a {step}-minute day has {slots}.")
    named = set(exclude_weeks)
    cands: List[Tuple[date, Dict[int, Tuple[date, List[float]]]]] = []
    for k in range(1, weeks + extra + 1):
        start = week_start - timedelta(weeks=k)
        got = {}
        for off in range(7):
            day = start + timedelta(days=off)
            if day in days:
                got[day.weekday()] = (day, days[day])
        cands.append((start, got))
    seen = [(s, g) for s, g in cands if g]
    if not seen:
        raise ValueError("There is no volume history in the weeks before this one to build a shape from.")
    oldest = min(s for s, _ in seen)
    cands = [(s, g) for s, g in cands if s >= oldest]
    # a weekday is open when most weeks that have data have volume on it
    live = {w: sum(1 for _, g in cands if w in g and sum(g[w][1]) > 0) for w in range(7)}
    open_days = [w for w in range(7) if live[w] * 2 >= len(cands)]
    closed = [w for w in range(7) if w not in open_days]
    if not open_days:
        raise ValueError("No weekday has volume in most of the weeks.")

    def complete(g: Dict[int, Tuple[date, List[float]]]) -> Optional[str]:
        for w in open_days:
            if w not in g or sum(g[w][1]) <= 0:
                return f"no volume on {_NAMES[w]}"
        return None

    whole = [(s, g) for s, g in cands if s.isoformat() not in named and complete(g) is None]
    med_total = {w: statistics.median(sum(g[w][1]) for _, g in whole) for w in open_days} if whole else {}
    med_busy = {w: statistics.median(sum(1 for v in g[w][1] if v > 0) for _, g in whole) for w in open_days} if whole else {}
    med_week = statistics.median(sum(sum(g[w][1]) for w in open_days) for _, g in whole) if whole else 0.0

    def why_not(start: date, g: Dict[int, Tuple[date, List[float]]]) -> Optional[str]:
        if start.isoformat() in named:
            return "left out by you"
        missing = complete(g)
        if missing:
            return missing
        for w in open_days:
            total = sum(g[w][1])
            if med_total[w] > 0 and total < LOW_DAY * med_total[w]:
                return f"{_NAMES[w]} was far below a usual {_NAMES[w]} (a holiday or an outage?)"
            if med_total[w] > 0 and total > HIGH_DAY * med_total[w]:
                return f"{_NAMES[w]} was far above a usual {_NAMES[w]}"
            if med_busy[w] > 0 and sum(1 for v in g[w][1] if v > 0) < PART_DAY * med_busy[w]:
                return f"{_NAMES[w]} has only part of its day"
        week_total = sum(sum(g[w][1]) for w in open_days)
        if med_week > 0 and not LOW_WEEK * med_week <= week_total <= HIGH_WEEK * med_week:
            return "the week's total is far from the usual week"
        return None

    used: List[date] = []
    skipped: List[Tuple[str, str]] = []
    for start, g in cands:                                   # newest first
        if len(used) == weeks:
            break
        reason = why_not(start, g)
        if reason:
            skipped.append((start.isoformat(), reason))
        else:
            used.append(start)
    return WeekChoice(used=sorted(used), skipped=skipped, open_days=open_days, closed=closed, wanted=weeks, short=len(used) < weeks)


def build_profile(days: Dict[date, List[float]], step: int, choice: WeekChoice) -> Profile:
    """The shape of each open weekday and of the week from the chosen weeks. Each day is turned into shares of its own total and each week into
    shares of its own total, so a busier week counts the same as a quieter one (no level bias); the median of those shares over the same weeks gives
    each weekday's interval shape and the week's day mix."""
    if len(choice.used) < MIN_WEEKS:
        why = "; ".join(f"{w}: {r}" for w, r in choice.skipped[:4])
        raise ValueError(f"Only {len(choice.used)} clean week{'s' if len(choice.used) != 1 else ''} of history; the shape needs at least {MIN_WEEKS}."
                         + (f" Left out: {why}." if why else ""))
    slots = 1440 // step
    per_day: Dict[int, List[List[float]]] = {w: [] for w in choice.open_days}
    day_mix: Dict[int, List[float]] = {w: [] for w in choice.open_days}
    for start in choice.used:
        totals = {}
        for w in choice.open_days:
            day = next(start + timedelta(days=o) for o in range(7) if (start + timedelta(days=o)).weekday() == w)
            per_day[w].append(_normalise(days[day]))
            totals[w] = sum(days[day])
        week = sum(totals.values())
        for w in choice.open_days:
            day_mix[w].append(totals[w] / week)
    shares = {w: (_normalise([statistics.median(row[i] for row in per_day[w]) for i in range(slots)]) if w in per_day else [0.0] * slots) for w in range(7)}
    mix = _normalise([statistics.median(day_mix[w]) if w in day_mix else 0.0 for w in range(7)])
    return Profile(step=step, shares=shares, day_shares={w: mix[w] for w in range(7)},
                   weeks_used={w: (len(choice.used) if w in per_day else 0) for w in range(7)},
                   used=[d.isoformat() for d in choice.used], skipped=list(choice.skipped), closed=list(choice.closed), short=choice.short)


def _theil_sen(points: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """A robust line through (x, y) points: (slope, level at the last x)."""
    pts = sorted(points)
    slopes = [(pts[j][1] - pts[i][1]) / (pts[j][0] - pts[i][0]) for i in range(len(pts)) for j in range(i + 1, len(pts)) if pts[j][0] != pts[i][0]]
    slope = statistics.median(slopes) if slopes else 0.0
    last = pts[-1][0]
    level = statistics.median(y - slope * (x - last) for x, y in pts)
    return slope, level


def suggest_total(points: Sequence[Tuple[int, float]]) -> Optional[Tuple[int, int, int]]:
    """(suggested, low, high) for the forecast week from the chosen weeks' totals, as (x, total) with x the week's offset from the forecast week
    (last week is -1; a skipped week leaves a gap that the line respects); None with fewer than three weeks.

    The level is where a robust line ends; the trend adds the line's slope over the weeks ahead, damped by half each week (a short run of growth is not
    a law); the range is the spread of the weeks around the line (about an 80 percent band)."""
    pts = [(float(x), float(y)) for x, y in points]
    if len(pts) < MIN_WEEKS:
        return None
    slope, level = _theil_sen(pts)
    last_x = max(x for x, _ in pts)
    ahead = int(round(0 - last_x))                       # weeks from the last chosen week to the forecast week
    reach = sum(0.5 ** k for k in range(1, max(ahead, 1) + 1))
    suggested = max(0.0, level + slope * reach)
    residuals = [y - (level + slope * (x - last_x)) for x, y in pts]
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
