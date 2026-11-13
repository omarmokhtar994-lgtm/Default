# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP (sample ap01, A and B; owner, 2026-10-21: only the LOBs of one program merge): LOBs shown as one.

A day view of each LOB, moved onto one clock with ``shift_view``, becomes one view with ``merge_views``: one
requirement, one staffed count and one shrinkage per interval, each person kept with their own LOB (``lob`` on the
lane), so an edit made on the merged view is saved on that person's LOB. ``merge_intervals`` does the same for the
rows of a week."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from .day import _moved

SUMMED = ("required", "plan", "now", "absent", "aux", "late_early", "breaks", "overtime", "vto", "outside")
ADDED_TILES = ("planned", "present", "absent", "late_early", "aux", "moved", "overtime", "vto", "called_in", "cover")


def same_interval(views: Dict[str, Dict[str, Any]]) -> None:
    """One interval length for every LOB, else a ValueError naming the LOBs."""
    steps = {key: v["interval"] for key, v in views.items()}
    if len(set(steps.values())) > 1:
        said = ", ".join(f"{key}: {step} minutes" for key, step in steps.items())
        raise ValueError(f"These LOBs use different interval lengths ({said}), so they cannot be shown as one. "
                         "Pick one LOB.")


def shift_view(view: Dict[str, Any], by: int) -> Dict[str, Any]:
    """A copy of ``view`` with every time ``by`` minutes later (a LOB uploaded in another zone, put on the shared
    clock). The view itself is not changed."""
    def later(items, *keys):
        return [{**x, **{k: x[k] + by for k in keys if k in x}} for x in items]

    out = {**view, "cells": later(view["cells"], "t"),
           "lanes": [{**ln, "segments": [_moved(s, by) for s in ln["segments"]]} for ln in view["lanes"]],
           "languages": [{**row, "cells": later(row["cells"], "t")} for row in view.get("languages") or []],
           "outside": later(view.get("outside") or [], "start", "end")}
    if "start" in view:
        out["start"] = view["start"] + by
    ch = view.get("channels")
    if ch:
        out["channels"] = {**ch, "runs": {n: [(a + by, b + by, c) for a, b, c in r] for n, r in (ch.get("runs") or {}).items()},
                           "warnings": later(ch.get("warnings") or [], "t0", "t1"),
                           "rows": [{**r, "cells": later(r["cells"], "t")} for r in ch.get("rows") or []]}
    return out


def _cell(cells: List[Dict[str, Any]], step: int) -> Dict[str, Any]:
    first = cells[0]
    out = {**first}
    for k in SUMMED:
        out[k] = sum(c[k] for c in cells)
    out["required"], out["plan"], out["now"] = round(out["required"], 3), round(out["plan"], 1), round(out["now"], 1)
    out["slots"] = [sum(x) for x in zip(*(c["slots"] for c in cells))]
    out["low"] = min(out["slots"])
    required, here = out["required"], out["now"]
    if required <= 0:
        return {**out, "need": 0, "pm": None, "plan_pm": None, "cls": "none"}
    pm = (here - required) * step / 60
    return {**out, "need": math.ceil(required - 1e-9), "pm": round(pm, 2),
            "plan_pm": round((out["plan"] - required) * step / 60, 2),
            "cls": "ok" if pm >= -1e-9 else ("warn" if here > required - 1 else "bad")}


def _languages(views: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: Dict[str, List[Dict[str, Any]]] = {}
    for v in views.values():
        for row in v.get("languages") or []:
            rows.setdefault(row["name"], []).append(row)
    out = []
    for name, mine in rows.items():
        cells = []
        for i, first in enumerate(mine[0]["cells"]):
            parts = [r["cells"][i] for r in mine if i < len(r["cells"]) and r["cells"][i]["count"] is not None]
            if not parts:
                cells.append({"t": first["t"], "count": None, "cls": "none"})
                continue
            count, minimum = sum(p["count"] for p in parts), sum(p.get("minimum", 0) for p in parts)
            cells.append({"t": first["t"], "count": count, "minimum": minimum,
                          "cls": "bad" if count < minimum else ("warn" if count == 0 else "lok")})
        out.append({**mine[0], "minimum": sum(r["minimum"] for r in mine),
                    "eligible": sorted({e for r in mine for e in r["eligible"]}), "cells": cells,
                    "gaps": sum(1 for c in cells if c["cls"] in ("bad", "warn"))})
    return out


def _channels(views: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    having = [v["channels"] for v in views.values() if v.get("channels")]
    if not having:
        return None
    runs: Dict[str, Any] = {}
    timelines: Dict[str, Any] = {}
    for ch in having:
        runs.update(ch.get("runs") or {})
        timelines.update(ch.get("timelines") or {})
    return {"runs": runs, "timelines": timelines, "rows": [], "warnings": [], "now": {}, "unplanned": [],
            "changes": [], "planned": any(ch.get("planned") for ch in having), "merged": True}


def merge_views(views: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """The views of several LOBs (already on one clock, keyed by LOB) as one. Raises ValueError for a different
    interval length, a person named in two LOBs, or cells that do not line up."""
    same_interval(views)
    seen: Dict[str, str] = {}
    for key, v in views.items():
        for ln in v["lanes"]:
            if ln["name"] in seen:
                raise ValueError(f"{ln['name']} is on both {seen[ln['name']]} and {key}, so these LOBs cannot be shown "
                                 "as one. Pick one LOB.")
            seen[ln["name"]] = key
    first = next(iter(views.values()))
    grid = [c["t"] for c in first["cells"]]
    for key, v in views.items():
        if [c["t"] for c in v["cells"]] != grid:
            raise ValueError(f"The times of {key} do not line up with the others, so these LOBs cannot be shown as "
                             "one. Pick one LOB.")
    step = first["interval"]
    cells = [_cell([v["cells"][i] for v in views.values()], step) for i in range(len(grid))]
    window = "start" in first

    def order(lane):
        own = [s["start"] for s in lane["segments"] if s["offset"] == 0]
        if window or not own:
            return (min(s["start"] for s in lane["segments"]), lane["name"])
        return (min(own) + 1440, lane["name"])

    lanes = sorted(({**ln, "lob": key} for key, v in views.items() for ln in v["lanes"]), key=order)
    languages = _languages(views)
    with_demand = [c for c in cells if c["pm"] is not None]
    tiles = {k: sum(v["tiles"].get(k, 0) for v in views.values()) for k in ADDED_TILES}
    tiles.update({"short_hours": round(sum(-c["pm"] for c in with_demand if c["pm"] < 0), 1),
                  "plan_short_hours": round(sum(-c["plan_pm"] for c in with_demand
                                                if c.get("plan_pm") is not None and c["plan_pm"] < 0), 1),
                  "short_intervals": sum(1 for c in with_demand if c["pm"] < 0),
                  "over_hours": round(sum(c["pm"] for c in with_demand if c["pm"] > 0), 1),
                  "language_gaps": sum(r["gaps"] for r in languages)})
    out = {**first, "lanes": lanes, "cells": cells, "languages": languages, "tiles": tiles,
           "channels": _channels(views), "outside": [o for v in views.values() for o in v.get("outside") or []]}
    return out


def merge_intervals(rows_by_unit: Dict[str, List[list]]) -> List[list]:
    """The week's interval rows of several LOBs (already in one zone) as one: [day, "HH:MM", required, after_eff,
    after_raw, before_eff, before_raw, severe]; columns 2 to 6 add up, the last is set when any LOB has it."""
    found: Dict[Tuple[int, str], list] = {}
    for rows in rows_by_unit.values():
        for r in rows:
            mine = found.setdefault((r[0], r[1]), [r[0], r[1], 0, 0, 0, 0, 0, 0])
            for i in range(2, 7):
                mine[i] += r[i]
            mine[7] = max(mine[7], r[7])
    return [[d, t, round(a, 3), round(b, 3), c, round(e, 3), f, g]
            for (d, t), (_, _, a, b, c, e, f, g) in sorted(found.items())]
