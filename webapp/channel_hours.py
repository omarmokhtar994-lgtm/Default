# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AP: the hours each channel is staffed, per day and per week, from the channel stretches a day view holds."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

CHANNEL_NAMES = {"P": "Phone", "C": "Chat", "E": "Email", "A": "All channels"}
ORDER = "PCEA"


def day_hours(view: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Hours by channel letter for one day view ({} when no channels are planned that day)."""
    runs = ((view or {}).get("channels") or {}).get("runs") or {}
    found: Dict[str, float] = {}
    for stretches in runs.values():
        for a, b, letter in stretches:
            found[letter] = found.get(letter, 0.0) + (b - a) / 60
    return {k: round(v, 2) for k, v in found.items()}


def week_hours(days: List[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    """Seven day views (Sunday first or as given; None for a day with no schedule) as one table: a row per channel
    with each day's hours and the week's, an all-channels row, and the days that have no channel plan."""
    per_day = [day_hours(v) for v in days]
    letters = sorted({k for d in per_day for k in d}, key=lambda k: (ORDER.find(k) if k in ORDER else 9, k))
    rows = [{"letter": k, "name": CHANNEL_NAMES.get(k, k), "days": [d.get(k, 0) for d in per_day],
             "total": round(sum(d.get(k, 0) for d in per_day), 2)} for k in letters]
    totals = [round(sum(d.values()), 2) for d in per_day]
    return {"rows": rows, "total": {"days": totals, "total": round(sum(totals), 2)},
            "unplanned": [i for i, d in enumerate(per_day) if not d]}
