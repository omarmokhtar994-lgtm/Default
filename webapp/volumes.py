# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI: volumes, forecast, people needed and how the week went (owner, 2026-11-03).

One ``VolumeBook`` per site. It keeps a program's actual volumes per channel (``webapp/volumes_io.py`` reads them in), turns a typed week total
into calls per day and interval from the program's own last weeks (``webapp/forecast.py``), works out the people needed on the floor with Erlang
for programs counted by service level or volume weighted (``webapp/erlang.py``), and reports how a week went: offered over forecast, the trend of
that over the weeks, and for one day the calls, the people the system asked for, the people Erlang says the calls needed, and who was there.

Everything is computed when a page is opened from the stored actuals and the typed week totals; no forecast grid is stored. Days run in the input
sheet's order (Sun to Sat); intervals are the program's interval (30 minutes unless its schedule says otherwise). The people needed are the people
on the floor: the engine adds the program's shrinkage itself when it builds the schedule, so the requirement workbook is not divided by it.
"""
from __future__ import annotations

import io
import math
from datetime import date, datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from . import erlang, forecast as F
from .channel_template import _head, _title
from .volumes_io import CHANNELS, DAY_NAMES, ParsedVolumes

MAX_TOTAL = 5_000_000
MIN_DAYS_IN_A_WEEK = 5          # a week counts in the weekly totals when it holds at least this many days of data
TREND_WEEKS = 8
FALLBACK_AHT = {"Phone": 300.0, "Chat": 420.0, "Email": 600.0}

DEFAULTS: Dict[str, Dict[str, Any]] = {
    "Phone": {"aht": None, "sl_target": 80, "sl_seconds": 20, "occupancy": 88, "shrinkage": 30, "concurrency": 1.0,
              "forecast_weeks": 8, "band_low": 90, "band_high": 110},
    "Chat": {"aht": None, "sl_target": 80, "sl_seconds": 30, "occupancy": 85, "shrinkage": 30, "concurrency": 2.0,
             "forecast_weeks": 8, "band_low": 90, "band_high": 110},
    "Email": {"aht": None, "sl_target": 80, "sl_seconds": 3600, "occupancy": 85, "shrinkage": 30, "concurrency": 1.0,
              "forecast_weeks": 8, "band_low": 90, "band_high": 110},
}
RANGES = {"aht": (10, 7200), "sl_target": (50, 100), "sl_seconds": (5, 86400), "occupancy": (50, 100), "shrinkage": (0, 60),
          "concurrency": (1, 5), "forecast_weeks": (4, 26), "band_low": (50, 100), "band_high": (100, 200)}
LABELS = {"aht": "Handle time (seconds)", "sl_target": "Service level target (%)", "sl_seconds": "Answer within (seconds)",
          "occupancy": "Highest occupancy (%)", "shrinkage": "Shrinkage (%)", "concurrency": "Chats at once per agent",
          "forecast_weeks": "Weeks of history for the shape", "band_low": "OTF on target from (%)", "band_high": "OTF on target up to (%)"}
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
        if not text.isdigit():
            raise ValueError(f"{what} is a whole number of zero or more.")
        value = int(text)
    if not isinstance(value, int) or value < 0 or value > MAX_TOTAL:
        raise ValueError(f"{what} is a whole number from 0 to {MAX_TOTAL:,}.")
    return value


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
        self.store.set_volume_settings(key, merged, user_id)

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

    def save_actuals(self, key: str, parsed: ParsedVolumes, user_id: Optional[int]) -> Dict[str, Dict[str, int]]:
        if parsed.problems:
            raise ValueError("The table has problems; nothing was saved.")
        return {channel: self.store.replace_volume_rows(key, channel, rows, user_id) for channel, rows in parsed.rows.items()}

    def _slots(self, key: str) -> int:
        return 1440 // self.step(key)

    def history(self, key: str, channel: str, before: date, weeks: int) -> Dict[date, List[float]]:
        """Volume per interval for each day in the ``weeks`` weeks before ``before`` that has any."""
        step, slots = self.step(key), self._slots(key)
        rows = self.store.volume_rows(key, channel, (before - timedelta(weeks=weeks)).isoformat(), (before - timedelta(days=1)).isoformat())
        days: Dict[date, List[float]] = {}
        for r in rows:
            grid = days.setdefault(date.fromisoformat(r["day"]), [0.0] * slots)
            grid[min(slots - 1, r["minute"] // step)] += r["offered"]
        return days

    def _aht(self, key: str, channel: str, before: date, weeks: int) -> float:
        rows = self.store.volume_rows(key, channel, (before - timedelta(weeks=weeks)).isoformat(), (before - timedelta(days=1)).isoformat())
        weighted = sum(r["aht"] * r["offered"] for r in rows if r["aht"] and r["offered"] > 0)
        volume = sum(r["offered"] for r in rows if r["aht"] and r["offered"] > 0)
        return round(weighted / volume, 1) if volume else FALLBACK_AHT[channel]

    def weekly_totals(self, key: str, channel: str, anchor: date, weeks: int) -> List[Tuple[str, int]]:
        """(week start, calls) for each of the ``weeks`` weeks before the week starting ``anchor`` that has at least five days of data; oldest first."""
        out = []
        for k in range(weeks, 0, -1):
            first = anchor - timedelta(weeks=k)
            rows = self.store.volume_rows(key, channel, first.isoformat(), (first + timedelta(days=6)).isoformat())
            if len({r["day"] for r in rows}) >= MIN_DAYS_IN_A_WEEK:
                out.append((first.isoformat(), int(round(sum(r["offered"] for r in rows)))))
        return out

    # ---------------------------------------------------------------- the forecast
    def _needs(self, key: str, channel: str, calls: List[List[int]], aht: float, s: Dict[str, Any]):
        step_s = self.step(key) * 60
        needs: List[List[float]] = []
        service: List[List[Optional[float]]] = []
        for day in calls:
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
            needs.append(n_row)
            service.append(s_row)
        return needs, (None if channel == "Email" else service)

    def forecast(self, key: str, channel: str, week_start: date, total: Any = None, day_totals: Optional[Dict[int, Any]] = None,
                 today: Optional[date] = None) -> Dict[str, Any]:
        """The week starting ``week_start`` for one channel: calls per day (Sun to Sat) and interval, from the typed total (else the saved one, else the
        suggestion), and for service-level programs the people needed and the service level they give."""
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        s = self.settings(key)[channel]
        typed = None if total in (None, "") else _whole(total, "The week's calls")
        typed_days = {int(d): _whole(v, "A day's calls") for d, v in (day_totals or {}).items() if v not in (None, "")}
        step, slots = self.step(key), self._slots(key)
        out: Dict[str, Any] = {"channel": channel, "week_start": week_start.isoformat(), "step": step, "days": list(DAY_NAMES), "calls": [],
                               "needs": None, "service": None, "total": None, "source": None, "suggestion": None, "aht": None,
                               "profile": None, "error": ""}
        hist = self.history(key, channel, week_start, s["forecast_weeks"])
        if not hist:
            out["error"] = f"There is no {channel} history in the {s['forecast_weeks']} weeks before this week. Add actual volumes first."
            return out
        try:
            profile = F.build_profile(hist, step, weeks=s["forecast_weeks"], today=week_start)
        except ValueError as exc:
            out["error"] = str(exc)
            return out
        weekly = self.weekly_totals(key, channel, week_start, s["forecast_weeks"])
        found = F.suggest_total([t for _, t in weekly])
        if found:
            out["suggestion"] = {"value": found[0], "low": found[1], "high": found[2], "weeks": weekly}
        saved = self.store.volume_forecast(key, channel, week_start.isoformat())
        if typed is not None:
            total_used, source = typed, "typed"
        elif saved:
            total_used, source = saved["total"], "saved"
            typed_days = typed_days or {int(d): v for d, v in saved["days"].items()}
        elif found:
            total_used, source = found[0], "suggestion"
        else:
            out["error"] = "There are not enough weeks of history for a suggestion; type the week's calls."
            out["profile"] = self._profile_note(profile)
            return out
        week = F.forecast_week(total_used, profile, {py_day(d): v for d, v in typed_days.items()})
        calls = [list(week[py_day(d)]) for d in range(7)]
        aht = float(s["aht"]) if s["aht"] else self._aht(key, channel, week_start, s["forecast_weeks"])
        out.update(calls=calls, total=total_used, source=source, aht=aht, profile=self._profile_note(profile),
                   day_totals={d: sum(calls[d]) for d in range(7)})
        if self.uses_erlang(key):
            out["needs"], out["service"] = self._needs(key, channel, calls, aht, s)
        return out

    def _profile_note(self, p: F.Profile) -> Dict[str, Any]:
        return {"weeks_used": {DAY_NAMES[site_day(w)]: n for w, n in p.weeks_used.items()},
                "thin": [DAY_NAMES[site_day(w)] for w in p.thin], "closed": [DAY_NAMES[site_day(w)] for w in p.closed],
                "excluded": [list(x) for x in p.excluded]}

    def save_forecast(self, key: str, channel: str, week_start: date, total: Any, day_totals: Dict[int, Any], user_id: Optional[int]) -> None:
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        n = _whole(total, "The week's calls")
        days = {str(int(d)): _whole(v, "A day's calls") for d, v in (day_totals or {}).items() if v not in (None, "")}
        if sum(days.values()) > n:
            raise ValueError("The days add up to more than the week's calls.")
        self.store.set_volume_forecast(key, channel, week_start.isoformat(), n, days, user_id)

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
            raise ValueError("There is no forecast with people needed to write.")
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

    def _otf_week(self, key: str, channel: str, week_start: date, today: date) -> Optional[Dict[str, Any]]:
        saved = self.store.volume_forecast(key, channel, week_start.isoformat())
        if not saved:
            return None
        f = self.forecast(key, channel, week_start, total=saved["total"], day_totals={int(d): v for d, v in saved["days"].items()}, today=today)
        return None if f["error"] else f

    def report(self, key: str, channel: str, week_start: date, on: Optional[date] = None, today: Optional[date] = None) -> Dict[str, Any]:
        """How the week starting ``week_start`` went for one channel: offered over forecast, the trend, and for the day ``on`` the staffing lines."""
        if channel not in CHANNELS:
            raise ValueError("The channel is Phone, Chat or Email.")
        today = today or _today()
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
        fc = self._otf_week(key, channel, week_start, today)
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
            ff = fc if k == 0 else self._otf_week(key, channel, wk, today)
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
            fallback = float(s["aht"]) if s["aht"] else self._aht(key, channel, on - timedelta(days=1), s["forecast_weeks"])
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
