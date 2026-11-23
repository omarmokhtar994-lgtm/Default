# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BY (owner, 2026-11-23: "Yes build the roster name to team manager sheet"): the sheet a planner uploads on the RTA, one per LOB, with two
columns, Roster name and Team manager, and the same sheet back as a download. Read with the people sheet's own safe reader (size, rows, card numbers
and the like are refused in words); this module only reads and writes files."""
from __future__ import annotations

import io
from typing import Dict

from openpyxl import Workbook
from openpyxl.styles import Font

from .bulk_users import _norm, _rows, _safe
from .upload_guard import look_rows

HEAD = ("Roster name", "Team manager")
MAX_NAMES = 2000
LONGEST = 80
NOT_A_SHEET = "Upload the team managers sheet: an Excel (.xlsx) or CSV file with the columns Roster name and Team manager. Download it from the RTA."


def _text(value: object) -> str:
    return " ".join(str(value).split()) if value is not None else ""


def read(data: bytes, filename: str) -> Dict[str, str]:
    """Roster name -> team manager from an uploaded sheet; rows with no team manager are left out. ValueError, in words, for anything else."""
    rows = _rows(data, filename)
    refused = look_rows(rows, "the team managers sheet")
    if refused:
        raise ValueError(refused)
    head = next((i for i, row in enumerate(rows) if {_norm(c) for c in row} >= {"roster name", "team manager"}), None)
    if head is None:
        raise ValueError(NOT_A_SHEET)
    cols = {_norm(c): i for i, c in enumerate(rows[head]) if c not in (None, "")}
    name_at, tm_at = cols["roster name"], cols["team manager"]
    found: Dict[str, str] = {}
    seen: Dict[str, int] = {}
    for n, row in enumerate(rows[head + 1:], start=head + 2):
        name = _text(row[name_at]) if name_at < len(row) else ""
        tm = _text(row[tm_at]) if tm_at < len(row) else ""
        if not name or not tm:
            continue
        if len(name) > LONGEST or len(tm) > LONGEST:
            raise ValueError(f"Row {n}: a name is longer than {LONGEST} characters.")
        if name in found and found[name] != tm:
            raise ValueError(f"{name} is on rows {seen[name]} and {n} with two team managers. Keep one row for each person.")
        found.setdefault(name, tm)
        seen.setdefault(name, n)
        if len(found) > MAX_NAMES:
            raise ValueError(f"The sheet holds more than {MAX_NAMES:,} names.")
    if not found:
        raise ValueError("The sheet has no names with a team manager in it.")
    return found


def workbook(mapping: Dict[str, str]) -> bytes:
    """The sheet as kept, by roster name (an example row when empty, as a template)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Team managers"
    ws.append(list(HEAD))
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for name, tm in (sorted(mapping.items(), key=lambda x: x[0].casefold()) or [("Associate 01", "Team Manager 01")]):
        ws.append([_safe(name), _safe(tm)])
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 28
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
