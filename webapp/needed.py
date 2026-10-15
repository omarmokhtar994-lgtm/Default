# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AH: the Weeks page's Hours needed table (owner, 2026-10-15; samples ah01 and ah02 approved).

One row per interval and a column per day of the week, from the DayBook's own day pages: as recorded on the RTA
(sick and other absences, overtime, called-in days, aux and shrinkage) or as planned (the schedule alone). Each cell
is coloured by the week's target (``day.band``, tight under ``CUSHION`` minutes over it) and gives the hours needed to
reach 100% or, the RTA's choice, the target with ``CUSHION`` minutes to spare, in person-minutes rounded up to the
quarter hour. Rows needing nothing on any day fold. What fixes each cell comes from the day's plan (Rescue the day's
days off to cancel, then overtime): "Day off", "OT" or both; the filter shows only one kind. Below the table, what to
do per day with the people named; ``workbook`` writes the same table and the suggestions to Excel."""
from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Optional, Tuple

from .day import STEP, at_target, safe_level

AIMS = ("full", "target")            # hours needed to 100%, or to the target with 10 minutes to spare
BASES = ("recorded", "planned")      # as recorded on the RTA, or the schedule alone
SHOWS = ("all", "ot", "dayoff")      # every short interval, overtime needed, a day off to cancel
FILLS = {"ok": "D5F2EE", "warn": "FBE9C9", "bad": "F8D3D0"}  # the export's colours (sample ah02)


def pick(value: Optional[str], allowed: Tuple[str, ...]) -> str:
    """The value when it is one of ``allowed``, else the first (the default)."""
    return value if value in allowed else allowed[0]


def _hm(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def _cells(page: Dict[str, Any], aim: str) -> Dict[int, Dict[str, Any]]:
    view, target = page["view"], page["target"]["target"]
    step = view["interval"]
    standing = at_target(view["cells"], target)
    out = {}
    for c, s in zip(view["cells"], standing["cells"]):
        if c["required"] <= 0:
            continue
        goal = c["required"] if aim == "full" else safe_level(c["required"], target, step)
        short = max(0.0, goal * step - STEP * sum(c["slots"]))  # person-minutes
        out[c["t"]] = {"cls": s["cls"], "tight": s["tight"], "over": s["over"], "pct": s["pct"],
                       "hours": math.ceil(short / 15 - 1e-9) / 4, "fix": ""}
    return out


def _spans(plan: Optional[Dict[str, Any]]) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    if not plan:
        return [], []
    return ([(p["start"], p["end"]) for p in plan.get("proposals", [])],
            [(o["start"], o["end"]) for o in plan.get("overtime", [])])


def _verdict(plan: Dict[str, Any], cells: Dict[int, Dict[str, Any]], step: int) -> str:
    if plan.get("proposals"):
        people = sum(p["people"] for p in plan["proposals"])
        covers = sum(p["intervals"] for p in plan["proposals"])
        same = sum(min(1.0, cells[t]["hours"]) for p in plan["proposals"]
                   for t in range(p["start"], p["end"], step) if t in cells)
        return (f"Better: cancel {people} day{'s' if people != 1 else ''} off, then overtime for what is left. "
                f"A day off covers {covers} short intervals in one shift; the same by overtime would need about "
                f"{same:g} hours of overtime spread over several people.")
    if plan.get("overtime"):
        return (f"Overtime is enough: no day off to cancel would cover {plan.get('minimum', 6)} short intervals, so "
                "cancelling one would waste most of the shift.")
    return "Nothing to suggest: no day off to cancel and nobody can stay on or come in early within the rest rules."


def week_table(days: List[Dict[str, Any]], aim: str, show: str) -> Dict[str, Any]:
    """``days``: seven {date, page (or None), plan (``DayBook.dayoff_plan`` or None: no suggestions), why}."""
    pages = [d["page"] for d in days if d["page"]]
    step = pages[0]["view"]["interval"] if pages else 60
    target = pages[0]["target"]["target"] if pages else 0.9
    columns = []
    for d in days:
        cells = _cells(d["page"], aim) if d["page"] else {}
        dayoff, ot = _spans(d["plan"])
        for t, c in cells.items():
            tags = [name for name, spans in (("Day off", dayoff), ("OT", ot))
                    if c["hours"] > 0 and any(a <= t < b for a, b in spans)]
            c["fix"] = " + ".join(tags)
        columns.append(cells)

    def shown(c: Optional[Dict[str, Any]]) -> bool:
        if not c or c["hours"] <= 0:
            return False
        return show == "all" or (show == "ot" and "OT" in c["fix"]) or (show == "dayoff" and "Day off" in c["fix"])

    rows: List[Dict[str, Any]] = []
    fold: List[int] = []
    for t in range(0, 1440, step):
        line = [cells.get(t) for cells in columns]
        if not any(shown(c) for c in line):
            fold.append(t)
            continue
        if fold:
            rows.append({"fold": f"{_hm(fold[0])} to {_hm(fold[-1] + step)}"})
            fold = []
        rows.append({"time": _hm(t), "t": t, "cells": line, "dim": [bool(c) and not shown(c) for c in line]})
    if fold:
        rows.append({"fold": f"{_hm(fold[0])} to {_hm(fold[-1] + step)}"})
    every = [c for cells in columns for c in cells.values()]
    counts = {"all": sum(1 for c in every if c["hours"] > 0), "ot": sum(1 for c in every if "OT" in c["fix"]),
              "dayoff": sum(1 for c in every if "Day off" in c["fix"])}
    totals = [{"hours": sum(c["hours"] for c in cells.values()),
               "bad": sum(1 for c in cells.values() if c["cls"] == "bad"),
               "warn": sum(1 for c in cells.values() if c["cls"] == "warn"),
               "tight": sum(1 for c in cells.values() if c["tight"])} for cells in columns]
    cards = []
    for d, cells, total in zip(days, columns, totals):
        plan = d["plan"]
        if not plan or total["hours"] <= 0:
            continue
        cards.append({"date": d["date"], "hours": total["hours"], "verdict": _verdict(plan, cells, step),
                      "proposals": [{"text": p["text"], "covers": p["covers"], "rules": p.get("rules", ""),
                                     "candidates": [{"name": c["name"],
                                                     "said": "; ".join(([c["note"]] if c.get("note") else [])
                                                                       + (c.get("bends") or ["keeps every rule"]))}
                                                    for c in p["candidates"]]}
                                    for p in plan.get("proposals", [])],
                      "overtime": [{"text": o["text"], "names": [f"{x['name']} ({x['text']})" for x in o["offers"][:3]]}
                                   for o in plan.get("overtime", [])]})
    return {"step": step, "target": target, "aim": aim, "show": show, "rows": rows, "totals": totals,
            "counts": counts, "cards": cards,
            "days": [{"date": d["date"], "label": f"{d['date']:%a %d}", "why": d["why"]} for d in days]}


def workbook(table: Dict[str, Any], title: str) -> bytes:
    """The table in Excel with the same colours (sheet "Hours needed") and what to do per day ("What to do")."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Hours needed"
    ws.append([title])
    ws["A1"].font = Font(bold=True)
    ws.append(["Interval"] + [f"{d['date']:%a %d %b}" for d in table["days"]])
    for row in table["rows"]:
        if "fold" in row:
            ws.append([row["fold"], "No hours needed on any day"])
            continue
        line = [row["time"]]
        for c in row["cells"]:
            if not c:
                line.append("")
            elif c["hours"] <= 0:
                line.append(f"{c['pct']}%")
            else:
                line.append(f"{c['hours']:g} h ({c['pct']}%)" + (f" {c['fix']}" if c["fix"] else "")
                            + (" tight" if c["tight"] else ""))
        ws.append(line)
        for i, c in enumerate(row["cells"]):
            if c and c["cls"] in FILLS:
                ws.cell(ws.max_row, i + 2).fill = PatternFill("solid", fgColor=FILLS[c["cls"]])
    ws.append(["Hours needed"] + [t["hours"] for t in table["totals"]])
    ws.append([f"Below {round(100 * table['target'])}%"] + [t["bad"] for t in table["totals"]])
    ws.append([f"{round(100 * table['target'])}% to 99%"] + [t["warn"] for t in table["totals"]])
    ws.append(["Tight (under 10 minutes over the target)"] + [t["tight"] for t in table["totals"]])
    ws.column_dimensions["A"].width = 18
    for col in "BCDEFGH":
        ws.column_dimensions[col].width = 22
    todo = wb.create_sheet("What to do")
    todo.append(["Day", "Action", "Covers", "People"])
    for card in table["cards"]:
        on = f"{card['date']:%a %d %b}"
        todo.append([on, card["verdict"], "", ""])
        for p in card["proposals"]:
            todo.append([on, p["text"], p["covers"], ", ".join(f"{c['name']} ({c['said']})" for c in p["candidates"])])
        for o in card["overtime"]:
            todo.append([on, "Overtime " + o["text"], "", ", ".join(o["names"])])
    for col, width in zip("ABCD", (14, 60, 30, 90)):
        todo.column_dimensions[col].width = width
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
