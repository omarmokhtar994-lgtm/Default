# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP: the hours each channel is staffed, per day and per week, from the channel stretches a day view holds."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

NONE = "No channel planned"  # the letter the day view gives stretches with no channel
CHANNEL_NAMES = {"P": "Phone", "C": "Chat", "E": "Email", "A": "All channels (blended time)", NONE: NONE}
ORDER = ["P", "C", "E", "A", NONE]


def day_hours(view: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Hours by channel letter for one day view ({} when no channels are planned that day). Breaks are not work and
    are left out."""
    runs = ((view or {}).get("channels") or {}).get("runs") or {}
    found: Dict[str, float] = {}
    for stretches in runs.values():
        for a, b, letter in stretches:
            if letter not in CHANNEL_NAMES:
                continue
            found[letter] = found.get(letter, 0.0) + (b - a) / 60
    return {k: round(v, 2) for k, v in found.items()}


def week_hours(days: List[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Seven day views (Sunday first or as given; None for a day with no schedule) as one table: a row per channel
    with each day's hours and the week's, an all-channels row, and the days that have no channel plan."""
    per_day = [day_hours(v) for v in days]
    letters = sorted({k for d in per_day for k in d}, key=ORDER.index)
    rows = [{"letter": k, "name": CHANNEL_NAMES.get(k, k), "days": [d.get(k, 0) for d in per_day],
             "total": round(sum(d.get(k, 0) for d in per_day), 2)} for k in letters]
    totals = [round(sum(d.values()), 2) for d in per_day]
    return {"rows": rows, "total": {"days": totals, "total": round(sum(totals), 2)},
            "unplanned": [i for i, d in enumerate(per_day) if not d]}


def combine(weeks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Several ``week_hours`` tables (one per LOB) as one: each channel's hours added by day; a day has no channel
    plan only when no LOB has one."""
    letters = sorted({r["letter"] for w in weeks for r in w["rows"]}, key=ORDER.index)
    rows = []
    for k in letters:
        days = [round(sum(next((r["days"][i] for r in w["rows"] if r["letter"] == k), 0) for w in weeks), 2)
                for i in range(7)]
        rows.append({"letter": k, "name": CHANNEL_NAMES.get(k, k), "days": days, "total": round(sum(days), 2)})
    totals = [round(sum(w["total"]["days"][i] for w in weeks), 2) for i in range(7)]
    return {"rows": rows, "total": {"days": totals, "total": round(sum(totals), 2)},
            "unplanned": [i for i in range(7) if all(i in w["unplanned"] for w in weeks)]}
