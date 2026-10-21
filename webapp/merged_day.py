# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, B approved): the RTA's day for every LOB of a program as one page.

Each LOB's own 24 hours (the window the page shows) are moved onto the clock of the LOB the page was opened on, using
the zone picked in "Times in", then merged (``webapp.merge``). Everything the page keeps stays with the person's own
LOB: the lanes carry ``lob``, and a change posted from this page is routed to it (``lob_of``)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Callable, Dict, List, Optional

from .attendance import DayBook
from .clock import rta_shift
from .day import at_target, window_view
from .merge import merge_views, shift_view

CLOCK = ("Clocks change in this window for one of the LOBs, so they cannot be shown as one. "
         "Pick one LOB, or another day.")


def merged_page(days: DayBook, program: str, units: List[str], on: date, measure: str, start_frame: int, zone: str,
                own_zone_of: Callable[[str, date], str]) -> Optional[Dict[str, Any]]:
    """The page for the 24 hours from minute ``start_frame`` (of ``program``'s own clock) of ``on``, every LOB in
    ``units`` that has a schedule that day together; None when none has. Raises ValueError (said on the page) for
    a workbook that cannot be read, a clock change, intervals of different lengths or a person on two LOBs."""
    home = rta_shift(on, own_zone_of(program, on), zone)
    if home is None:
        raise ValueError(CLOCK)
    pages: Dict[str, Dict[str, Any]] = {}
    views: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for unit in units:
        if days.version(unit, on)[0] is None:
            missing.append(unit)
            continue
        moved = rta_shift(on, own_zone_of(unit, on), zone)
        if moved is None:
            raise ValueError(CLOCK)
        delta = moved - home  # its minutes + delta = the page's minutes
        page = days.page(unit, on, measure)
        step = page["view"]["interval"]
        start = start_frame - delta
        if start % step:
            raise ValueError("These LOBs' clocks do not line up on the interval, so they cannot be shown as one. "
                             "Pick one LOB.")
        held: Dict[int, Optional[Dict[str, Any]]] = {0: page["view"]}
        for d in range(start // 1440, (start + 1439) // 1440 + 1):
            if d:
                try:
                    held[d] = (days.page(unit, on + timedelta(days=d), measure) or {}).get("view")
                except ValueError:  # a workbook that cannot be read: its hours stay empty
                    held[d] = None
        pages[unit] = page
        views[unit] = shift_view(window_view(held, start, on), delta)
    if not views:
        return None
    merged = merge_views(views)
    weights = {u: sum(c["required"] for c in p["view"]["cells"]) for u, p in pages.items()}
    total = sum(weights.values())
    ratio = (sum(p["target"]["target"] * weights[u] for u, p in pages.items()) / total if total
             else next(iter(pages.values()))["target"]["target"])
    standing = at_target(merged["cells"], ratio)
    for cell, found in zip(merged["cells"], standing["cells"]):
        cell.update(cls=found["cls"], tight=found["tight"], over=found["over"])
    base = pages.get(program) or next(iter(pages.values()))
    log = sorted((e for u in pages for e in days.store.list_day_log(u, on.isoformat())), key=lambda e: e["id"])
    return {**base, "view": merged, "target": standing,
            "note": "Every LOB of the program together. A change made here is saved on the person's own LOB.",
            "stale": sum(p["stale"] for p in pages.values()),
            "unlisted": [x for p in pages.values() for x in p["unlisted"]],
            "log": log, "week": {"associates": [a for p in pages.values() for a in p["week"].get("associates", [])]},
            "merged": {"units": list(pages), "missing": missing,
                       "delta": {u: rta_shift(on, own_zone_of(u, on), zone) - home for u in pages}},
            "pages": pages}


def lob_of(days: DayBook, units: List[str], on: date, name: str) -> Optional[str]:
    """The LOB among ``units`` whose schedule for ``on`` (or the day before, for a shift running past midnight) lists
    ``name``; None when no LOB, or more than one, does."""
    key = " ".join(name.casefold().split())
    found = set()
    for unit in units:
        for day in (on, on - timedelta(days=1)):
            row = days.version(unit, day)[0]
            if row and any(" ".join(str(a["name"]).casefold().split()) == key
                           for a in json.loads(row["week"] or "{}").get("associates", [])):
                found.add(unit)
    return found.pop() if len(found) == 1 else None
