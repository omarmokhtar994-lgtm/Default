# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: volumes, forecast, people needed and how the week went (owner, 2026-11-03).

One ``VolumeBook`` per site. It keeps a program's actual volumes per channel (``webapp/volumes_io.py`` reads them in), turns a typed week total
into calls per day and interval from the program's own last weeks (``webapp/forecast.py``), works out the people needed on the floor with Erlang
for programs counted by service level or volume weighted (``webapp/erlang.py``), and reports how a week went: offered over forecast, the trend of
that over the weeks, and for one day the calls, the people the system asked for, the people Erlang says the calls needed, and who was there.

A suggestion is computed when a page is opened from the stored actuals (the same N whole weeks for every weekday), the planner's events, AI periods,
growth rates and last year's totals (``webapp/drivers.py``). A forecast the planner saves keeps its own grid and the weeks and handle time behind it
(Phase BJ), so later changes to the history, events or settings do not move it; the people needed are always worked out from the grid and the
current settings. Days run in the input sheet's order (Sun to Sat); intervals are the program's interval (30 minutes unless its schedule says
otherwise). The people needed are the people on the floor: the engine adds the program's shrinkage itself when it builds the schedule, so the
requirement workbook is not divided by it.
"""
from __future__ import annotations

import io
import math
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from . import drivers as D, erlang, forecast as F, volumes_zone as Z
from . import open_hours as H
from .channel_template import _head, _title
from .volumes_io import CHANNELS, DAY_NAMES, FIRST_DAY, ParsedVolumes

MAX_TOTAL = 5_000_000
LAST_WEEK = date(2100, 1, 1)
MIN_DAYS_IN_A_WEEK = 5          # a week counts in the weekly totals when it holds at least this many days of data
TREND_WEEKS = 8
FALLBACK_AHT = {"Phone": 300.0, "Chat": 420.0, "Email": 600.0}

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "Phone": {"aht": None, "sl_target": 80, "sl_seconds": 20, "occupancy": 88, "shrinkage": 30, "concurrency": 1.0,
              "forecast_weeks": 6, "band_low": 90, "band_high": 110},
    "Chat": {"aht": None, "sl_target": 80, "sl_seconds": 30, "occupancy": 85, "shrinkage": 30, "concurrency": 2.0,
             "forecast_weeks": 6, "band_low": 90, "band_high": 110},
    "Email": {"aht": None, "sl_target": 80, "sl_seconds": 3600, "occupancy": 85, "shrinkage": 30, "concurrency": 1.0,
              "forecast_weeks": 6, "band_low": 90, "band_high": 110},
}
RANGES = {"aht": (10, 7200), "sl_target": (50, 100), "sl_seconds": (5, 86400), "occupancy": (50, 100), "shrinkage": (0, 60),
          "concurrency": (1, 5), "forecast_weeks": (3, 26), "band_low": (50, 100), "band_high": (100, 200)}
LABELS = {"aht": "Handle time (seconds)", "sl_target": "Service level target (%)", "sl_seconds": "Answer within (seconds)",
          "occupancy": "Highest occupancy (%)", "shrinkage": "Shrinkage (%)", "concurrency": "Chats at once per agent",
          "forecast_weeks": "Weeks of history (the same weeks for every weekday)", "band_low": "OTF on target from (%)", "band_high": "OTF on target up to (%)"}
EGYPT = ZoneInfo("Africa/Cairo")


def _today() -> date:
    return datetime.now(EGYPT).date()


def _whole(value: Any, what: str) -> int:
    """A whole number of calls from a number or the text a form sent ("12,600"); ValueError in words otherwise."""
    if isinstance(value, bool):
        raise ValueError(f"{what} is a whole number.")
    if isinstance(value, float):
        if value != int(value):
            raise ValueError(f"{what} is a whole number.")
        value = int(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace(" ", "")
        if not text.isdecimal():                                   # not isdigit: "²" is a digit that int() cannot read
            raise ValueError(f"{what} is a whole number of zero or more.")
        value = int(text)
    if not isinstance(value, int) or value < 0 or value > MAX_TOTAL:
        raise ValueError(f"{what} is a whole number from 0 to {MAX_TOTAL:,}.")
    return value


def _check_week(week_start: date) -> None:
    """A week between 2015 and 2100; outside that the calendar arithmetic runs off the end of Python's dates, so it is refused in words instead."""
    if not FIRST_DAY <= week_start < LAST_WEEK:
        raise ValueError(f"Pick a week between {FIRST_DAY.year} and {LAST_WEEK.year}.")


def site_day(weekday: int) -> int:
    """Python's weekday (Monday 0) as the input sheet's day index (Sunday 0)."""
    return (weekday + 1) % 7


def py_day(index: int) -> int:
    return (index - 1) % 7


class VolumeBook:
    def __init__(self, store: Any, measure_of: Callable[[str], str] = lambda key: "interval",
                 staffing: Callable[[str, date], Optional[Dict[int, Tuple[float, float, float]]]] = lambda key, on: None,
                 step_of: Callable[[str], int] = lambda key: 30):
        self.store = store
        self.measure_of = measure_of
        self.staffing = staffing
        self.step_of = step_of

    # ---------------------------------------------------------------- settings
    def settings(self, key: str) -> Dict[str, Dict[str, Any]]:
        saved = self.store.volume_settings(key) or {}
        return {ch: {**DEFAULTS[ch], **{k: v for k, v in (saved.get(ch) or {}).items() if k in DEFAULTS[ch]}} for ch in CHANNELS}

    def zone(self, key: str) -> str:
        """The time zone the program's volumes are kept in (Cairo, the site's own, unless set): every interval of every day is in it."""
        saved = self.store.volume_settings(key) or {}
        return saved["zone"] if saved.get("zone") in Z.NAMES else Z.HOME

    def set_zone(self, key: str, zone: Any, user_id: Optional[int]) -> None:
        """Change the zone the volumes are read in. Volumes already held are not moved: they were kept in the zone they were saved in, so change it before adding
        any, or delete and add them again."""
        Z.check_zone(zone)
        saved = {**(self.store.volume_settings(key) or {}), "zone": zone}
        self.store.set_volume_settings(key, saved, user_id)

    def set_settings(self, key: str, data: Dict[str, Dict[str, Any]], user_id: Optional[int]) -> None:
        """Save settings for some channels (merged with what is kept). Everything is checked first: nothing is saved when anything is wrong."""
        merged = self.settings(key)
        for channel, values in data.items():
            if channel not in CHANNELS:
                raise ValueError("The channel is Phone, Chat or Email.")
            for name, raw in values.items():
                if name not in DEFAULTS[channel]:
                    raise ValueError("That setting does not exist.")
                if name == "aht" and (raw is None or str(raw).strip() == ""):
                    merged[channel]["aht"] = None
                    continue
                try:
                    number = float(str(raw).replace(",", "")) if not isinstance(raw, (int, float)) else float(raw)
                except ValueError:
                    raise ValueError(f"{LABELS[name]} is a number.") from None
                low, high = RANGES[name]
                if not math.isfinite(number) or not low <= number <= high:
                    raise ValueError(f"{LABELS[name]} is {low} to {high}.")
                merged[channel][name] = int(number) if name not in ("concurrency", "aht") and number == int(number) else number
            if merged[channel]["band_low"] >= merged[channel]["band_high"]:
                raise ValueError("The OTF band starts below where it ends.")
        self.store.set_volume_settings(key, {**(self.store.volume_settings(key) or {}), **merged, "zone": self.zone(key)}, user_id)

    def open_hours(self, key: str) -> Dict[str, Dict[str, Any]]:
        """The hours each channel is worked and its minimum cover (Phase BL). Nothing set is ``{"min_cover": 1, "days": {}}``: open all day, as before."""
        saved = (self.store.volume_settings(key) or {}).get("hours")
        saved = saved if isinstance(saved, dict) else {}
        return {ch: H.read(saved.get(ch)) for ch in CHANNELS}

    def set_open_hours(self, key: str, data: Dict[str, Dict[str, Any]], user_id: Optional[int]) -> None:
        """Save the hours of some channels (merged with what is kept). Everything is checked first: nothing is saved when anything is wrong."""
        merged = self.open_hours(key)
        for channel, hours in data.items():
            if channel not in CHANNELS:
                raise ValueError("The channel is Phone, Chat or Email.")
            merged[channel] = H.read(hours)
        self.store.set_volume_settings(key, {**(self.store.volume_settings(key) or {}), "hours": merged}, user_id)

    def uses_erlang(self, key: str) -> bool:
        return self.measure_of(key) in ("sl", "volume")

    def step(self, key: str) -> int:
        return int(self.step_of(key) or 30)

    # ---------------------------------------------------------------- the data held
    def coverage(self, key: str, channel: str) -> Dict[str, Any]:
        days = self.store.volume_days(key, channel)
        if not days:
            return {"days": 0, "first": None, "last": None, "weeks": []}
        weeks = sorted({(date.fromisoformat(d) - timedelta(days=(date.fromisoformat(d).weekday() + 1) % 7)).isoformat() for d in days})
        return {"days": len(days), "first": days[0], "last": days[-1], "weeks": weeks}

    def save_actuals(self, key: str, parsed: ParsedVolumes, user_id: Optional[int], cells: bool = False) -> Dict[str, Dict[str, int]]:
        """Keep checked rows. A day in the rows replaces that day as a whole, unless ``cells``: rows moved from another time zone replace only their own intervals."""
        if parsed.problems:
            raise ValueError("The table has problems; nothing was saved.")
        save = self.store.upsert_volume_cells if cells else self.store.replace_volume_rows
        return {channel: save(key, channel, rows, user_id) for channel, rows in parsed.rows.items()}

    def convert_actuals(self, key: str, parsed: ParsedVolumes, from_zone: Any) -> ParsedVolumes:
        """Checked rows read in ``from_zone`` as rows in the program's zone. Everything is converted or nothing is: a time the clocks cannot place refuses the lot, in words."""
        to_zone = self.zone(key)
        Z.check_zone(from_zone, "The zone the file is in")
        if parsed.problems or from_zone == to_zone:
            return parsed
        out = ParsedVolumes(notes=list(parsed.notes))
        for channel, rows in parsed.rows.items():
            said: List[str] = []
            moved, problems = Z.convert_rows(rows, from_zone, to_zone, self.step(key), said)
            out.notes += [f"{channel}: {n}" for n in said]
            out.problems += [f"{channel}: {p}" for p in problems]
            if not problems:
                out.rows[channel] = moved
                days = sorted({r[0] for r in moved})
                out.summary[channel] = {"rows": len(moved), "days": len(days), "first": days[0], "last": days[-1]}
        if out.problems:
            out.rows, out.summary = {}, {}
        else:
            out.notes.append(f"Read in {Z.NAMES[from_zone].split(' (')[0]} time and kept in {Z.NAMES[to_zone].split(' (')[0]} time, the program's; "
                             "an evening there can be the next morning here, so the first and last days hold only part of a day until the next upload fills them.")
        return out

    def _slots(self, key: str) -> int:
        return 1440 // self.step(key)

    def history(self, key: str, channel: str, before: date, weeks: int) -> Dict[date, List[float]]:
        """Volume per interval for each day with any in the ``weeks`` weeks before ``before``, and the older weeks that may step in for one left out."""
        step, slots = self.step(key), self._slots(key)
        rows = self.store.volume_rows(key, channel, (before - timedelta(weeks=weeks + F.EXTRA_LOOKBACK)).isoformat(),
                                      (before - timedelta(days=1)).isoformat())
        days: Dict[date, List[float]] = {}
        for r in rows:
            grid = days.setdefault(date.fromisoformat(r["day"]), [0.0] * slots)
            grid[min(slots - 1, r["minute"] // step)] += r["offered"]
        return days

    def _aht(self, key: str, channel: str, used: Sequence[date]) -> float:
        """The handle time of the weeks used, weighted by volume; the channel's usual when those weeks carry none."""
        weighted = volume = 0.0
        for start in used:
            for r in self.store.volume_rows(key, channel, start.isoformat(), (start + timedelta(days=6)).isoformat()):
                if r["aht"] and r["offered"] > 0:
                    weighted += r["aht"] * r["offered"]
                    volume += r["offered"]
        return round(weighted / volume, 1) if volume else FALLBACK_AHT[channel]

    # ---------------------------------------------------------------- what is known about the weeks ahead
    def drivers(self, key: str) -> Dict[str, Any]:
        """Events, AI periods, growth rates, last year's totals and the weeks left out, for a program (empty until something is entered)."""
        return D.clean_document(self.store.volume_drivers(key))

    def _keep(self, key: str, doc: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
        self.store.set_volume_drivers(key, doc, user_id)
        return doc

    def add_driver(self, key: str, which: str, row: Dict[str, Any], user_id: Optional[int]) -> Dict[str, Any]:
        return self._keep(key, D.add_row(self.drivers(key), which, row), user_id)

    def remove_driver(self, key: str, which: str, ident: str, user_id: Optional[int]) -> Dict[str, Any]:
        return self._keep(key, D.remove_row(self.drivers(key), which, ident), user_id)

    def set_growth(self, key: str, yoy: Any, method: Any, user_id: Optional[int]) -> Dict[str, Any]:
        return self._keep(key, D.with_growth(self.drivers(key), yoy, method), user_id)

    def set_last_year(self, key: str, week_start: date, values: Any, user_id: Optional[int]) -> Dict[str, Any]:
        """Last year's totals for the same week as ``week_start`` (52 weeks earlier, so the same weekdays)."""
        _check_week(week_start)
        return self._keep(key, D.with_last_year(self.drivers(key), (week_start - timedelta(days=364)).isoformat(), values), user_id)

    def set_skip_weeks(self, key: str, weeks: Any, user_id: Optional[int]) -> Dict[str, Any]:
        return self._keep(key, D.with_skip_weeks(self.drivers(key), weeks), user_id)

    # ---------------------------------------------------------------- the forecast
    def _needs(self, key: str, channel: str, calls: List[List[int]], aht: float, s: Dict[str, Any]):
        step_s = self.step(key) * 60
        hours = self.open_hours(key)[channel]
        needs: List[List[float]] = []
        service: List[List[Optional[float]]] = []
        for d, day in enumerate(calls):
            n_row, s_row = [], []
            for c in day:
                if channel == "Phone":
                    n = erlang.agents_needed(c, aht, step_s, s["sl_target"] / 100.0, s["sl_seconds"], s["occupancy"] / 100.0) if c else 0
                    sl = round(erlang.service_level(n, c, aht, step_s, s["sl_seconds"]) * 100, 1) if c else None
                elif channel == "Chat":
                    n = erlang.chat_agents_needed(c, aht, step_s, s["sl_target"] / 100.0, s["sl_seconds"], s["concurrency"],
                                                  s["occupancy"] / 100.0) if c else 0
                    sl = round(erlang.service_level(n, c, aht / s["concurrency"], step_s, s["sl_seconds"]) * 100, 1) if c else None
                else:
                    n = round(erlang.workload_agents(c, aht, step_s, s["occupancy"] / 100.0), 2) if c else 0
                    sl = None
                n_row.append(n)
                s_row.append(sl)
            open_ranges = H.ranges(hours, d)  # Phase BL: nobody outside the hours, at least the minimum cover inside them
            if open_ranges is not None:
                kept = H.apply(n_row, open_ranges, self.step(key), 0 if channel == "Email" else hours["min_cover"])
                for i, (was, now) in enumerate(zip(n_row, kept)):
                    if now != was:
                        c = day[i]
                        if channel == "Phone":
                            s_row[i] = round(erlang.service_level(now, c, aht, step_s, s["sl_seconds"]) * 100, 1) if (c and now) else None
                        elif channel == "Chat":
                            s_row[i] = round(erlang.service_level(now, c, aht / s["concurrency"], step_s, s["sl_seconds"]) * 100, 1) if (c and now) else None
                n_row = kept
            needs.append(n_row)
            service.append(s_row)
        return needs, (None if channel == "Email" else service)

    @staticmethod
    def _weeks_wanted(s: Dict[str, Any], weeks: Any) -> int:
        try:
            wanted = int(s["forecast_weeks"] if weeks is None else weeks)
        except (TypeError, ValueError):
            raise ValueError("Weeks of history is 3 to 26.") from None
        if not 3 <= wanted <= 26:
            raise ValueError("Weeks of history is 3 to 26.")
        return wanted

    @staticmethod
    def _dates(week_start: date) -> List[date]:
        """The seven dates of the week in the input sheet's order (Sunday first)."""
        out: List[Optional[date]] = [None] * 7
        for k in range(7):
            d = week_start + timedelta(days=k)
            out[site_day(d.weekday())] = d
        return out  # type: ignore[return-value]

    def _read(self, key: str, channel: str, week_start: date, wanted: int, skip: Sequence[str], out: Optional[Dict[str, Any]] = None):
        """The history, the weeks chosen from it, their shape and their weekly totals. ValueError in words when the history cannot carry a shape; the
        weeks chosen are put into ``out`` first, so they are shown even then."""
        step = self.step(key)
        hist = self.history(key, channel, week_start, wanted)
        if not hist:
            raise ValueError(f"There is no {channel} history in the weeks before this week. Add actual volumes first.")
        choice = F.choose_weeks(hist, step, week_start, weeks=wanted, exclude_weeks=skip)
        if out is not None:
            out["weeks"] = {"wanted": wanted, "used": [d.isoformat() for d in choice.used], "skipped": [list(x) for x in choice.skipped], "short": choice.short}
        profile = F.build_profile(hist, step, choice)
        points = [(-((week_start - start).days // 7), int(round(sum(sum(hist[start + timedelta(days=o)]) for o in range(7)
                                                                  if start + timedelta(days=o) in hist)))) for start in choice.used]
        return hist, choice, profile, points

    @staticmethod
    def _history_base(channel: str, points: Sequence[Tuple[int, int]], doc: Dict[str, Any], notes: List[str]):
        """(method, value, low, high) for the week from the history alone: the measured trend, or the typed year-over-year rate when the planner chose it."""
        found = F.suggest_total(points)
        method, value, low, high = "trend", (found[0] if found else None), (found[1] if found else None), (found[2] if found else None)
        if doc["growth"]["method"] == "growth":
            yoy = doc["growth"]["yoy"].get(channel)
            if yoy is None:
                notes.append(f"The year-over-year rate is chosen but none is typed for {channel}, so its measured trend is used.")
            else:
                method, value = "growth", int(round(D.growth_level(points, yoy)))
                if found and found[0] > 0:                               # the history's own spread, carried to the grown level
                    low, high = int(round(value * found[1] / found[0])), int(round(value * found[2] / found[0]))
                else:                                                    # a flat-zero trend has no spread to carry
                    low = high = None
        return method, value, low, high

    def _moved_in(self, key: str, channel: str, week_start: date, dates: Sequence[date], doc: Dict[str, Any], skip: Sequence[str],
                  shapes: Sequence[float], notes: List[str]) -> List[float]:
        """Contacts per day that AI takes off other channels and that arrive on ``channel``: the share of what each source loses, from the source's own
        history-based forecast. A destination day with no hours of its own takes none."""
        moved = [0.0] * 7
        for src in CHANNELS:
            rows = [r for r in doc["ai"] if r["channel"] == src and r["move_to"] == channel and src != channel]
            if not rows:
                continue
            ss = self.settings(key)[src]
            try:
                _, _, prof, pts = self._read(key, src, week_start, int(ss["forecast_weeks"]), skip)
            except ValueError:
                notes.append(f"{src} has no usable history, so nothing is counted as moving from {src} to {channel}.")
                continue
            _, base, _, _ = self._history_base(src, pts, doc, notes)
            if not base:
                continue
            events = D.day_factors(doc["events"], [], src, dates)
            before_ai = [base * prof.day_shares[py_day(d)] * events[d] for d in range(7)]
            got = D.ai_moves(rows, src, dates, before_ai).get(channel)
            if got:
                moved = [a + b for a, b in zip(moved, got)]
        for d in range(7):
            if moved[d] > 0 and shapes[d] <= 0:
                notes.append(f"{channel} has no hours on {DAY_NAMES[d]}, so contacts moved from another channel for that day are not counted.")
                moved[d] = 0.0
        return moved

    def _suggest(self, key: str, channel: str, week_start: date, profile: F.Profile, points: Sequence[Tuple[int, int]], doc: Dict[str, Any],
                 skip: Sequence[str], kind: str, dates: Sequence[date], notes: List[str]):
        """(suggestion, last_year, why not): the week's calls from the history (or last year), then every event and AI period in turn, then what AI moves
        in from other channels."""
        yoy = doc["growth"]["yoy"].get(channel)
        ly_week = (week_start - timedelta(days=364)).isoformat()
        raw = doc["last_year"].get(ly_week, {}).get(channel)
        last_year = None if raw is None else {"week": ly_week, "total": raw, "grown": D.last_year_total(raw, yoy), "yoy": yoy}
        method, value, low, high = self._history_base(channel, points, doc, notes)
        if kind == "last_year":
            if last_year is None:
                return None, last_year, (f"There is no last-year figure for {channel}: type last year's total for the week starting {ly_week}, "
                                         f"or start from the history.")
            method, value, low, high = "last_year", last_year["grown"], None, None
        if value is None:
            return None, last_year, "There are not enough clean weeks for a suggestion; type the week's calls."
        shares = [profile.day_shares[py_day(d)] for d in range(7)]
        wf = D.waterfall(value, shares, dates, channel, doc["events"], doc["ai"])
        moved = self._moved_in(key, channel, week_start, dates, doc, skip, [sum(profile.shares[py_day(d)]) for d in range(7)], notes)
        move_total = int(round(sum(moved)))
        steps = list(wf["steps"])
        if move_total:
            steps.append({"kind": "move", "id": None, "name": "Moved in from other channels", "change": None, "days": [d for d in range(7) if moved[d] > 0],
                          "delta": move_total, "total": wf["total"] + move_total})
        ratio = wf["total"] / value if value else 1.0
        sug = {"base": value, "method": method, "final": wf["total"] + move_total, "value": wf["total"] + move_total, "steps": steps,
               "low": None if low is None else int(round(low * ratio)) + move_total, "high": None if high is None else int(round(high * ratio)) + move_total}
        return sug, last_year, ""

    def forecast(self, key: str, channel: str, week_start: date, total: Any = None, day_totals: Optional[Dict[int, Any]] = None,
                 weeks: Any = None, skip_weeks: Optional[Sequence[str]] = None, base: str = "history") -> Dict[str, Any]:
        """The week starting ``week_start`` for one channel: calls per day (Sun to Sat) and interval, from the typed total (else the saved forecast, else the
        suggestion), and for service-level programs the people needed and the service level they give.

        ``weeks`` is how many clean whole weeks every weekday is read from (the channel's setting, six unless changed); ``skip_weeks`` are week starts the
        planner leaves out (the stored ones unless given). ``base`` is where the suggestion starts: the "history" (its trend, or the year-over-year rate when
        chosen) or "last_year". Events and AI periods change the suggestion step by step; with a typed total they only shape its days. A saved forecast
        is returned as it was saved."""
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        _check_week(week_start)
        if base not in ("history", "last_year"):
            raise ValueError("Start from the history or from last year.")
        s = self.settings(key)[channel]
        wanted = self._weeks_wanted(s, weeks)
        typed = None if total in (None, "") else _whole(total, "The week's calls")
        typed_days = {int(d): _whole(v, "A day's calls") for d, v in (day_totals or {}).items() if v not in (None, "")}
        step, slots = self.step(key), self._slots(key)
        out: Dict[str, Any] = {"channel": channel, "week_start": week_start.isoformat(), "step": step, "days": list(DAY_NAMES), "calls": [],
                               "needs": None, "service": None, "total": None, "source": None, "needs_total": False, "suggestion": None, "aht": None, "profile": None,
                               "weeks": None, "last_year": None, "last_year_week": (week_start - timedelta(days=364)).isoformat(), "notes": [],
                               "day_factors": [1.0] * 7, "base": base, "error": ""}
        try:
            doc = self.drivers(key)
        except ValueError:
            out["error"] = "The events and AI periods saved for this program could not be read. Ask for them to be cleared and enter them again."
            return out
        skip = [str(x) for x in (doc["skip_weeks"] if skip_weeks is None else skip_weeks)]
        out["skip_weeks"] = sorted(skip)
        dates = self._dates(week_start)
        saved = self.store.volume_forecast(key, channel, week_start.isoformat())
        grid = saved.get("grid") if saved else None
        grid_ok = bool(grid) and len(grid) == 7 and all(len(r) == slots for r in grid)
        if saved and grid and not grid_ok:
            out["notes"].append("The forecast saved for this week was made at a different interval, so it is rebuilt from its saved week total.")
        use_saved = typed is None and not typed_days and grid_ok
        problem, profile, choice, points = "", None, None, []
        try:
            _, choice, profile, points = self._read(key, channel, week_start, wanted, skip, out)
        except ValueError as exc:
            problem = str(exc)
        sug, why_not = None, problem
        if profile is not None:
            sug, out["last_year"], why_not = self._suggest(key, channel, week_start, profile, points, doc, skip, base, dates, out["notes"])
            if sug:
                out["suggestion"] = {**sug, "weeks": [(d.isoformat(), t) for d, (_, t) in zip(choice.used, points)]}
        if use_saved:
            basis = saved.get("basis") or {}
            calls, total_used, source = [list(map(int, r)) for r in grid], int(saved["total"]), "saved"
            out["weeks"] = basis.get("weeks") or out["weeks"]
            out["profile"] = basis.get("profile")
            out["day_factors"] = basis.get("day_factors") or out["day_factors"]
            aht = float(s["aht"]) if s["aht"] else float(basis.get("aht") or FALLBACK_AHT[channel])
        else:
            if profile is None:
                out["error"] = problem
                return out
            factors = D.day_factors(doc["events"], doc["ai"], channel, dates)
            shape = [profile.day_shares[py_day(d)] * factors[d] for d in range(7)]
            if typed is not None:
                total_used, source, weights = typed, "typed", shape
                out["day_factors"] = factors
            elif saved:
                total_used, source, weights = int(saved["total"]), "saved", [profile.day_shares[py_day(d)] for d in range(7)]
                typed_days = typed_days or {int(d): v for d, v in saved["days"].items()}
            else:                                                  # the total is the planner's: the suggestion is only shown, never taken
                out["needs_total"] = True
                out["profile"] = self._profile_note(profile)
                if why_not and sug is None and profile is not None and base == "last_year":
                    out["notes"].append(why_not)
                return out
            if sum(weights) <= 0:
                weights = [profile.day_shares[py_day(d)] for d in range(7)]
            shaped = replace(profile, day_shares={py_day(d): weights[d] for d in range(7)})
            week = F.forecast_week(total_used, shaped, {py_day(d): v for d, v in typed_days.items()})
            calls = [list(week[py_day(d)]) for d in range(7)]
            aht = float(s["aht"]) if s["aht"] else self._aht(key, channel, choice.used)
            out["profile"] = self._profile_note(profile)
        out.update(calls=calls, total=total_used, source=source, aht=aht, day_totals={d: sum(calls[d]) for d in range(7)})
        if self.uses_erlang(key):
            out["needs"], out["service"] = self._needs(key, channel, calls, aht, s)
        return out

    def view_in(self, key: str, f: Dict[str, Any], week_start: date, zone: Any) -> Dict[str, Any]:
        """The forecast ``f`` with its grids read in ``zone`` (a copy; ``f`` itself is untouched). The program's own zone, or a forecast with no grid, comes back as it is."""
        Z.check_zone(zone, "The zone to show")
        own = self.zone(key)
        if zone == own or not f.get("calls"):
            return f
        step = f["step"]
        out = dict(f)
        out["calls"] = Z.rotate_grid(f["calls"], week_start, own, zone, step, "sum")
        if f.get("needs"):
            out["needs"] = Z.rotate_grid(f["needs"], week_start, own, zone, step, "max")
        if f.get("service"):
            out["service"] = Z.rotate_grid(f["service"], week_start, own, zone, step, "first")
        out["day_totals"] = {d: sum(out["calls"][d]) for d in range(7)}
        out["show_zone"] = zone
        return out

    def _profile_note(self, p: F.Profile) -> Dict[str, Any]:
        return {"weeks_used": {DAY_NAMES[site_day(w)]: n for w, n in p.weeks_used.items()}, "used": list(p.used),
                "skipped": [list(x) for x in p.skipped], "closed": [DAY_NAMES[site_day(w)] for w in p.closed], "short": p.short}

    def save_forecast(self, key: str, channel: str, week_start: date, total: Any, day_totals: Dict[int, Any], user_id: Optional[int],
                      weeks: Any = None, skip_weeks: Optional[Sequence[str]] = None) -> None:
        """Keep the forecast as it is now: the week's total, the typed days, and the calls per day and interval with the weeks, handle time and drivers
        behind them, so later changes to the history, events or settings do not move it. Refused without history to spread the total over."""
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        _check_week(week_start)
        n = _whole(total, "The week's calls")
        days = {str(int(d)): _whole(v, "A day's calls") for d, v in (day_totals or {}).items() if v not in (None, "")}
        if sum(days.values()) > n:
            raise ValueError("The days add up to more than the week's calls.")
        f = self.forecast(key, channel, week_start, total=n, day_totals={int(d): v for d, v in days.items()}, weeks=weeks, skip_weeks=skip_weeks)
        if f["error"]:
            raise ValueError(f["error"])
        basis = {"weeks": f["weeks"], "profile": f["profile"], "aht": f["aht"], "day_factors": f["day_factors"], "step": f["step"],
                 "from": f["suggestion"]["method"] if f["suggestion"] else ""}
        self.store.set_volume_forecast(key, channel, week_start.isoformat(), n, days, user_id, grid=f["calls"], basis=basis)

    # ---------------------------------------------------------------- grids to copy
    def grid(self, values: Sequence[Sequence[Any]], step: int, empty: str = "") -> List[List[Any]]:
        """The input sheet's layout: a header (Interval, Sun ... Sat) and a row per interval of the day; a number per cell, ready to paste."""
        rows: List[List[Any]] = [["Interval", *DAY_NAMES]]
        slots = 1440 // step
        for i in range(slots):
            minute = i * step
            row: List[Any] = [f"{minute // 60:02d}:{minute % 60:02d}"]
            for d in range(7):
                value = values[d][i] if d < len(values) and i < len(values[d]) else None
                row.append(empty if value is None else value)
            rows.append(row)
        return rows

    def requirement_workbook(self, key: str, week_start: date, forecasts: Dict[str, Dict[str, Any]]) -> bytes:
        """``FT Wise {n} Min`` (the channels added up: people needed on the floor) and a ``{Channel} {n} Min`` tab each, in the input sheet's layout."""
        if not self.uses_erlang(key):
            raise ValueError("This program is counted by interval compliance, so there is no Erlang requirement to write.")
        step = self.step(key)
        chosen = {ch: f for ch, f in forecasts.items() if ch in CHANNELS and f and f.get("needs")}
        if not chosen:
            raise ValueError("Save a forecast for at least one channel first: the requirement tabs are written from saved forecasts.")
        slots = 1440 // step
        wb = Workbook()
        wb.remove(wb.active)
        total = [[round(sum(f["needs"][d][i] for f in chosen.values()), 2) for i in range(slots)] for d in range(7)]

        def tab(name: str, note: str, values: List[List[float]]) -> None:
            ws = wb.create_sheet(name)
            _title(ws, name, note)
            _head(ws, 4, ["Interval", *DAY_NAMES])
            ws.column_dimensions["A"].width = 11
            for i in range(slots):
                minute = i * step
                ws.cell(5 + i, 1, f"{minute // 60:02d}:{minute % 60:02d}")
                for d in range(7):
                    ws.cell(5 + i, 2 + d, values[d][i])
            ws.freeze_panes = "B5"

        tab(f"FT Wise {step} Min", f"People needed on the floor per interval for the week of {week_start.isoformat()}, from the forecast with "
            "Erlang; the schedule engine adds the program's shrinkage itself.", total)
        for ch in sorted(chosen):
            tab(f"{ch} {step} Min", f"{ch}: people needed on the floor per interval, from {chosen[ch]['total']:,} forecast contacts.", chosen[ch]["needs"])
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    # ---------------------------------------------------------------- how did we do
    def _actual(self, key: str, channel: str, week_start: date) -> Tuple[List[List[int]], List[List[Optional[float]]], List[date]]:
        step, slots = self.step(key), self._slots(key)
        dates: List[Optional[date]] = [None] * 7
        for k in range(7):
            d = week_start + timedelta(days=k)
            dates[site_day(d.weekday())] = d
        rows = self.store.volume_rows(key, channel, week_start.isoformat(), (week_start + timedelta(days=6)).isoformat())
        offered = [[0.0] * slots for _ in range(7)]
        aht_sum = [[0.0] * slots for _ in range(7)]
        aht_vol = [[0.0] * slots for _ in range(7)]
        index = {d.isoformat(): i for i, d in enumerate(dates)}
        for r in rows:
            i, slot = index[r["day"]], min(slots - 1, r["minute"] // step)
            offered[i][slot] += r["offered"]
            if r["aht"] and r["offered"] > 0:
                aht_sum[i][slot] += r["aht"] * r["offered"]
                aht_vol[i][slot] += r["offered"]
        aht = [[(aht_sum[d][i] / aht_vol[d][i]) if aht_vol[d][i] > 0 else None for i in range(slots)] for d in range(7)]
        return [[int(round(v)) for v in day] for day in offered], aht, dates  # type: ignore[return-value]

    def _otf_week(self, key: str, channel: str, week_start: date) -> Optional[Dict[str, Any]]:
        """The forecast saved for the week, as it was saved (its own grid); one saved before grids were kept is rebuilt from today's history."""
        saved = self.store.volume_forecast(key, channel, week_start.isoformat())
        if not saved:
            return None
        grid = saved.get("grid")
        if grid and len(grid) == 7 and all(len(r) == self._slots(key) for r in grid):
            return {"calls": [list(map(int, r)) for r in grid], "total": int(saved["total"])}
        f = self.forecast(key, channel, week_start)
        return None if f["error"] else f

    def report(self, key: str, channel: str, week_start: date, on: Optional[date] = None) -> Dict[str, Any]:
        """How the week starting ``week_start`` went for one channel: offered over forecast, the trend, and for the day ``on`` the staffing lines."""
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        _check_week(week_start)
        s = self.settings(key)[channel]
        step = self.step(key)
        actual, actual_aht, dates = self._actual(key, channel, week_start)
        actual_total = sum(sum(d) for d in actual)
        out: Dict[str, Any] = {"channel": channel, "week_start": week_start.isoformat(), "step": step, "days": list(DAY_NAMES),
                               "dates": [d.isoformat() for d in dates], "actual": actual, "actual_total": actual_total, "forecast": None,
                               "forecast_total": None, "otf": None, "band": None, "day_otf": None, "week_otf": None, "note": "",
                               "trend": [], "staffing": None, "uses_erlang": self.uses_erlang(key), "settings": s}
        if not actual_total:
            out["note"] = "No actual volume has been uploaded for this week."
        fc = self._otf_week(key, channel, week_start)
        if fc is None and not out["note"]:
            out["note"] = "No forecast was saved for this week, so there is no offered-over-forecast figure. Save one on the Forecast tab."
        if fc is not None and actual_total:
            calls = fc["calls"]
            out.update(forecast=calls, forecast_total=fc["total"])
            out["otf"] = [[F.otf(actual[d][i], calls[d][i]) for i in range(len(calls[d]))] for d in range(7)]
            out["band"] = [[F.band(v, s["band_low"], s["band_high"]) for v in row] for row in out["otf"]]
            out["day_otf"] = [F.otf_total(actual[d], calls[d]) for d in range(7)]
            out["week_otf"] = F.otf_total([v for d in actual for v in d], [v for d in calls for v in d])
        for k in range(TREND_WEEKS - 1, -1, -1):
            wk = week_start - timedelta(weeks=k)
            ff = fc if k == 0 else self._otf_week(key, channel, wk)
            if ff is None:
                continue
            act = actual if k == 0 else self._actual(key, channel, wk)[0]
            a_tot = sum(sum(d) for d in act)
            if a_tot:
                out["trend"].append({"week": wk.isoformat(), "forecast": ff["total"], "actual": a_tot,
                                     "otf": F.otf_total([v for d in act for v in d], [v for d in ff["calls"] for v in d])})
        if on is not None:
            out["staffing"] = self._staffing(key, channel, on, actual, actual_aht, dates, s)
        return out

    def _staffing(self, key: str, channel: str, on: date, actual, actual_aht, dates, s) -> Dict[str, Any]:
        step, slots = self.step(key), self._slots(key)
        got = self.staffing(key, on)
        base: Dict[str, Any] = {"date": on.isoformat(), "required": None, "planned": None, "floor": None, "at_actual": None,
                                "modelled_sl": None, "note": ""}
        if got is None:
            base["note"] = "There is no schedule in use for that day, so the system's requirement and who was on the floor are not shown."
            return base
        d = next((i for i, x in enumerate(dates) if x == on), None)
        required = [(got.get(i * step) or (None, None, None))[0] for i in range(slots)]
        planned = [(got.get(i * step) or (None, None, None))[1] for i in range(slots)]
        floor = [(got.get(i * step) or (None, None, None))[2] for i in range(slots)]
        base.update(required=required, planned=planned, floor=floor)
        if self.uses_erlang(key) and d is not None:
            step_s = step * 60
            fallback = float(s["aht"]) if s["aht"] else FALLBACK_AHT[channel]
            at, sl = [], []
            for i in range(slots):
                calls = actual[d][i]
                aht = actual_aht[d][i] or fallback
                if channel == "Phone":
                    n = erlang.agents_needed(calls, aht, step_s, s["sl_target"] / 100.0, s["sl_seconds"], s["occupancy"] / 100.0) if calls else 0
                    eff = aht
                elif channel == "Chat":
                    n = erlang.chat_agents_needed(calls, aht, step_s, s["sl_target"] / 100.0, s["sl_seconds"], s["concurrency"],
                                                  s["occupancy"] / 100.0) if calls else 0
                    eff = aht / s["concurrency"]
                else:
                    n = round(erlang.workload_agents(calls, aht, step_s, s["occupancy"] / 100.0), 2) if calls else 0
                    eff = None
                at.append(n)
                if channel != "Email" and calls and floor[i] is not None:
                    sl.append(round(erlang.service_level(max(0, int(round(floor[i]))), calls, eff, step_s, s["sl_seconds"]) * 100, 1))
                else:
                    sl.append(None)
            base["at_actual"] = at
            base["modelled_sl"] = None if channel == "Email" else sl
            base["note"] = ("Needed at actual calls and the service level are modelled with Erlang from the calls and handle time that came and the "
                            "people on the floor; they are not the ACD's own figures.")
        return base
