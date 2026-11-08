# © 2026 Omar Mokhtar. All rights reserved.
"""Sites and who takes which contacts (Phase BL, owner, 2026-11-07).

A program has sites (a name, and the LOB the site is scheduled in) and rules: for a channel, on some weekdays, between two times, the share in
percent each site takes. The document is ``{"sites": [{"name", "lob"}], "rules": [{"channel", "days", "from", "to", "shares"}]}``; days are 0 for
Sunday, times are minutes from midnight, and ``to`` may run past 1440 (a rule 22:00 to 06:00 belongs to the day that starts it). Rules of one channel
may not overlap, a rule's shares add to 100, and time no rule covers goes to the first site. Pure functions, no store."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .volumes_io import CHANNELS, DAY_NAMES

MAX_SITES = 6
MAX_NAME = 40
MAX_LOB = 80
MAX_RULES = 60


def _empty() -> Dict[str, Any]:
    return {"sites": [], "rules": []}


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(str(value).replace(",", "")) if not isinstance(value, (int, float)) else float(value)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def _minute(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{what} is a time in minutes.")
    return value


def _days_text(days: List[int]) -> str:
    return ", ".join(DAY_NAMES[d] for d in days)


def clean(raw: Any) -> Dict[str, Any]:
    """The document, checked whole; ValueError in words when anything is wrong (nothing is kept then)."""
    if not isinstance(raw, dict):
        raise ValueError("The sites are a list of sites and a list of rules.")
    sites_raw, rules_raw = raw.get("sites") or [], raw.get("rules") or []
    if not isinstance(sites_raw, (list, tuple)) or not isinstance(rules_raw, (list, tuple)):
        raise ValueError("The sites are a list of sites and a list of rules.")
    if len(sites_raw) > MAX_SITES:
        raise ValueError(f"At most {MAX_SITES} sites.")
    if len(rules_raw) > MAX_RULES:
        raise ValueError(f"At most {MAX_RULES} rules.")
    sites: List[Dict[str, str]] = []
    seen: set = set()
    for row in sites_raw:
        name = " ".join(str((row or {}).get("name", "") if isinstance(row, dict) else "").split())
        if not name:
            raise ValueError("Give each site a name.")
        if len(name) > MAX_NAME:
            raise ValueError(f"A site name is at most {MAX_NAME} characters.")
        if name.casefold() in seen:
            raise ValueError(f"{name} is in the list twice.")
        seen.add(name.casefold())
        lob = " ".join(str(row.get("lob", "") or "").split())[:MAX_LOB]
        sites.append({"name": name, "lob": lob})
    names = [s["name"] for s in sites]
    if rules_raw and not names:
        raise ValueError("Add the sites before the rules.")
    rules: List[Dict[str, Any]] = []
    taken: Dict[Tuple[str, int], List[bool]] = {}
    for row in rules_raw:
        if not isinstance(row, dict) or row.get("channel") not in CHANNELS:
            raise ValueError("Each rule is for a channel: Phone, Chat or Email.")
        channel = row["channel"]
        days = row.get("days")
        if not isinstance(days, (list, tuple)) or not days or any(isinstance(d, bool) or not isinstance(d, int) or not 0 <= d <= 6 for d in days):
            raise ValueError(f"{channel}: pick at least one day of the week.")
        days = sorted(set(days))
        start, end = _minute(row.get("from"), f"{channel}: the start"), _minute(row.get("to"), f"{channel}: the end")
        label = f"{channel}, {_days_text(days)}"
        if not 0 <= start < 1440:
            raise ValueError(f"{label}: the start is a time of day.")
        if end == start:
            raise ValueError(f"{label}: the start and the end are the same time.")
        if not start < end <= start + 1440:
            raise ValueError(f"{label}: the end is a time after the start, at most 24 hours later.")
        shares_raw = row.get("shares")
        if not isinstance(shares_raw, dict) or not shares_raw:
            raise ValueError(f"{label}: give the share of each site.")
        shares = {n: 0.0 for n in names}
        for site, value in shares_raw.items():
            if site not in shares:
                raise ValueError(f"{label}: {site} is not one of the sites.")
            number = _number(value)
            if number is None or not 0 <= number <= 100:
                raise ValueError(f"{label}: the share for {site} is a number from 0 to 100.")
            shares[site] = number
        if abs(sum(shares.values()) - 100.0) > 0.01:
            raise ValueError(f"{label}: the shares add up to {sum(shares.values()):g}, and have to add up to 100.")
        for day in days:
            for d, lo, hi in _pieces(day, start, end):
                mask = taken.setdefault((channel, d), [False] * 1440)
                if any(mask[lo:hi]):
                    first = next(m for m in range(lo, hi) if mask[m])
                    raise ValueError(f"{channel}, {DAY_NAMES[d]}: two rules overlap at {first // 60:02d}:{first % 60:02d}.")
                mask[lo:hi] = [True] * (hi - lo)
        rules.append({"channel": channel, "days": days, "from": start, "to": end, "shares": shares})
    return {"sites": sites, "rules": rules}


def read(raw: Any) -> Dict[str, Any]:
    """A stored document; anything damaged reads as no sites rather than being trusted."""
    try:
        return clean(raw)
    except ValueError:
        return _empty()


def _pieces(day: int, start: int, end: int) -> List[Tuple[int, int, int]]:
    """The (day, from, to) pieces of a rule's window on its day and, past midnight, on the next one."""
    out = [(day, start, min(end, 1440))]
    if end > 1440:
        out.append(((day + 1) % 7, 0, end - 1440))
    return out


def _coverage(doc: Dict[str, Any], channel: str) -> List[List[Optional[Dict[str, float]]]]:
    """Per weekday and minute of the day, the shares of the rule that covers it (None where none does)."""
    grid: List[List[Optional[Dict[str, float]]]] = [[None] * 1440 for _ in range(7)]
    for rule in doc["rules"]:
        if rule["channel"] != channel:
            continue
        for day in rule["days"]:
            for d, lo, hi in _pieces(day, rule["from"], rule["to"]):
                for m in range(lo, hi):
                    grid[d][m] = rule["shares"]
    return grid


def split(doc: Dict[str, Any], channel: str, day: int, minute: int) -> Dict[str, float]:
    """The share in percent each site takes of ``channel`` contacts on weekday ``day`` (0 = Sunday) at ``minute``; the first site takes what no rule covers."""
    names = [s["name"] for s in doc["sites"]]
    if not names:
        return {}
    for rule in doc["rules"]:
        if rule["channel"] != channel:
            continue
        for d in rule["days"]:
            for pd, lo, hi in _pieces(d, rule["from"], rule["to"]):
                if pd == day and lo <= minute < hi:
                    return dict(rule["shares"])
    return {n: (100.0 if n == names[0] else 0.0) for n in names}


def table(doc: Dict[str, Any], channel: str, step: int) -> List[List[Dict[str, float]]]:
    """``split`` for every weekday and interval of a week (rows Sunday to Saturday), worked out once."""
    names = [s["name"] for s in doc["sites"]]
    if not names:
        return [[{} for _ in range(1440 // step)] for _ in range(7)]
    grid = _coverage(doc, channel)
    default = {n: (100.0 if n == names[0] else 0.0) for n in names}
    return [[grid[d][i * step] or default for i in range(1440 // step)] for d in range(7)]


def gaps(doc: Dict[str, Any], channel: str) -> Dict[int, List[Tuple[int, int]]]:
    """The times no rule covers, per weekday, for a channel that has rules (they go to the first site). Empty for a channel with no rules."""
    if not any(r["channel"] == channel for r in doc["rules"]):
        return {}
    grid, out = _coverage(doc, channel), {}
    for d in range(7):
        runs, start = [], None
        for m in range(1441):
            open_ = m < 1440 and grid[d][m] is None
            if open_ and start is None:
                start = m
            elif not open_ and start is not None:
                runs.append((start, m))
                start = None
        if runs:
            out[d] = runs
    return out
