# © 2026 Omar Mokhtar. All rights reserved.
"""Free text in a downloaded workbook stays text. openpyxl stores a string that starts with "=" as a formula, so a reason, a name or a language
typed by one person ("=HYPERLINK(...)") would be a live formula in a file another person opens in Excel (source audit 2026-11-11). The downloads
that carry typed text call ``keep_text`` on a sheet they have filled: any cell that would be a formula becomes a plain string with its words
unchanged. Use it only on sheets that hold no formulas of their own."""
from __future__ import annotations

from typing import Any


def keep_text(ws: Any) -> None:
    """Make every cell of ``ws`` that would be stored as a formula a plain string instead."""
    for row in ws.iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"
