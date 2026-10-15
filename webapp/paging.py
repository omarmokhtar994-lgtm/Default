# © 2026 Omar Mokhtar. All rights reserved.
"""Long lists, 20 at a time (Phase AI; owner, 2026-10-15: "instead of endless scrolling they might have some pages")."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

PAGE_SIZE = 20
AROUND = 2  # page numbers shown each side of the one open


def page_of(rows: Sequence[Any], asked: int, size: int = PAGE_SIZE) -> Tuple[List[Any], Optional[Dict[str, Any]]]:
    """The rows of page ``asked`` (counted from 1; one out of range gives the nearest page) and what the pager shows,
    or None when everything fits on one page. ``numbers`` lists the page numbers to link, None for a gap."""
    pages = max(1, -(-len(rows) // size))
    page = min(max(asked, 1), pages)
    shown = list(rows[(page - 1) * size: page * size])
    if pages == 1:
        return shown, None
    near = sorted({1, pages} | set(range(max(1, page - AROUND), min(pages, page + AROUND) + 1)))
    numbers: List[Optional[int]] = []
    for n in near:
        if numbers and n - numbers[-1] > 1:
            numbers.append(None)
        numbers.append(n)
    return shown, {"page": page, "pages": pages, "total": len(rows), "first": (page - 1) * size + 1,
                   "last": (page - 1) * size + len(shown), "numbers": numbers}
