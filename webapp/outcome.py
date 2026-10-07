# © 2026 Omar Mokhtar. All rights reserved.
"""The engine's own outcome for a run, shaped for the run page.

The engine writes BUSINESS_OUTCOME.json next to every run: a headline, a plain
summary, what blocks a schedule, who and when is affected, the coverage it
could not meet, and what to change. The page shows those words; this module
only groups, orders and formats them. Two blocker codes get plain wording
(their meaning is fixed in the engine's contract check); any other code is
shown humanised with its values, never dropped.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

OUTCOME = "BUSINESS_OUTCOME.json"
READY = "DIAGNOSTICS_ONLY_COMPLETE"  # a readiness check: input read, hard rules satisfiable
# The input, the policy or the resources must change before this workbook can
# be scheduled (rerunning the same file gives the same answer).
CHANGE_NEEDED = {"INPUT_OR_POLICY_ACTION_REQUIRED", "INPUT_OR_RESOURCE_ACTION_REQUIRED",
                 "POLICY_OR_RESOURCE_ACTION_REQUIRED"}
SHORTFALL = "HARD_RULE_SHORTFALL_SCHEDULE_FOR_REVIEW"
DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
PLAIN = {
    "ZERO_ACTIVE_INTERVAL_PROVABLY_IMPOSSIBLE": "{day} {time}: there is demand, but no one on the roster can be working then",
    "HARD_FLOOR_PROVABLY_IMPOSSIBLE": "{day} {time}: even with everyone who can work then, the hard floor cannot be met",
}
MAX_ROWS = 20


def read(results_dir: Path) -> Optional[Dict[str, Any]]:
    """The outcome in the run's case folder (not the gate report's), or None."""
    root = Path(results_dir)
    if not root.is_dir():
        return None
    for case in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        try:
            data = json.loads((case / OUTCOME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("outcome_code"):
            return data
    return None


def compact(outcome: Dict[str, Any]) -> Dict[str, str]:
    """What the run row keeps (the files are deleted after 30 days)."""
    return {"code": str(outcome.get("outcome_code") or ""), "category": str(outcome.get("outcome_category") or ""),
            "headline": str(outcome.get("headline") or "")}


def cannot_schedule(code: str, category: str) -> bool:
    return category in CHANGE_NEEDED or code == SHORTFALL


def _humanise(code: str) -> str:
    words = code.replace("_", " ").strip().lower()
    return words[:1].upper() + words[1:]


def _finding(item: Any) -> str:
    if not isinstance(item, dict):
        return str(item)
    if item.get("rule") and item.get("finding"):
        return f"{item['rule']}: {item['finding']}"
    for key in ("detail", "message", "headline", "summary"):
        if item.get(key):
            return str(item[key])
    code = str(item.get("code") or item.get("failure_code") or item.get("type") or "Finding")
    if code in PLAIN:
        try:
            return PLAIN[code].format(**item)
        except (KeyError, IndexError):
            pass
    values = ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in item.items()
                       if k not in ("code", "failure_code", "type") and v not in (None, "", [], {}))
    return _humanise(code) + (f" ({values})" if values else "")


def _days(days: List[str]) -> str:
    order = sorted({d for d in days if d in DAYS}, key=DAYS.index)
    others = [d for d in dict.fromkeys(days) if d not in DAYS]
    idx = [DAYS.index(d) for d in order]
    if len(idx) > 2 and idx == list(range(idx[0], idx[-1] + 1)):
        text = f"{order[0]} to {order[-1]}"
    else:
        text = ", ".join(order)
    return ", ".join([t for t in (text, *others) if t])


def _people(examples: List[dict]) -> List[Dict[str, str]]:
    groups: Dict[tuple, List[str]] = {}
    for e in examples:
        key = (str(e.get("associate") or "Unknown associate"), str(e.get("shift") or ""), str(e.get("window") or ""))
        groups.setdefault(key, []).append(str(e.get("day") or ""))
    return [{"associate": a, "days": _days(days), "shift": s, "window": w} for (a, s, w), days in groups.items()]


def _shortfall(row: dict) -> str:
    when = " ".join(str(row.get(k) or "") for k in ("day", "time")).strip()
    what = row.get("meaning") or row.get("rule") or "Coverage minimum"
    return f"{when}: {what}, needs {row.get('required')}, short by {row.get('short_by', row.get('shortfall'))}"


def _action(text: str) -> str:
    """The engine's recommended action, without sentences about developer tools."""
    sentences = re.split(r"(?<=\.)\s+", str(text).strip())
    return " ".join(s for s in sentences if "tools/" not in s).strip()


def view(outcome: Dict[str, Any]) -> Dict[str, Any]:
    code, category = str(outcome.get("outcome_code") or ""), str(outcome.get("outcome_category") or "")
    blockers = list(dict.fromkeys(_finding(f) for f in outcome.get("resource_findings") or []))
    examples = [e for e in outcome.get("affected_examples") or [] if isinstance(e, dict)]
    people = _people(examples)
    rows = [r for r in outcome.get("shortfall_rows") or [] if isinstance(r, dict)]
    return {
        "code": code, "category": category,
        "headline": str(outcome.get("headline") or ""),
        "summary": str(outcome.get("plain_language_summary") or ""),
        "blockers": blockers,
        "people": people[:MAX_ROWS], "people_rows": len(people), "people_total": len(examples),
        "shortfalls": [_shortfall(r) for r in rows[:MAX_ROWS]], "shortfalls_total": len(rows),
        "actions": [a for a in (_action(t) for t in outcome.get("recommended_actions") or []) if a],
        "cannot_schedule": cannot_schedule(code, category),
        "ready": code == READY,
    }
