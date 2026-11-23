#!/usr/bin/env python3
"""B-12: a single-term header lookup still matches a prose banner.

_find_header_row was hardened once already, after the Language Setup banner in
NMG13 satisfied ["language", "minimum"] on its own.  That fix requires the
terms to land in DISTINCT cells -- which does nothing when there is only ONE
term.  All three name-matched sheets look up ["name"], and the Preference
banner in NMG13 reads:

    "Optional: enter Leave/OFF/shift preference by day. Sheet name
     intentionally matches legacy engine spelling."

It contains "name", so row 2 is chosen as the header over the real one on
row 4.

On this corpus the consequence is latent, not live: with no day headers found
on row 2, every column resolves by positional fallback to name_col+2..+8,
which happens to equal the real layout, so the right cells are still read.  It
survives on the same luck the _day_columns docstring already calls out -- "a
property of the sample, not a guarantee".  A Preference sheet whose day block
does not start two columns after the name would be read from the wrong columns
and would assign the wrong leave and OFF days, silently.

It is also a live blocker for B-11: with unmatched rows failing closed, the
real header row 4 ("SF Name") is read as a data row and reported as an unknown
associate, so two workbooks would fail their contract for no reason.

The fix uses a structural property rather than a guess about prose: among the
rows that already pass the term test, prefer one whose headers bind all seven
weekdays.  A fully bound day header is not something a banner produces.  It is
strictly additive -- when no candidate binds seven days, the existing answer is
returned unchanged -- and it is enabled only at the three day-bearing
name-matched call sites.

    python3 apply_b12_header_row_day_anchor.py <tree>/engine
"""
import sys
from pathlib import Path

SIG_ANCHOR = '''def _find_header_row(ws: Any, required_terms: Sequence[str], max_rows: int = 30) -> int:
'''
SIG_REPLACEMENT = '''def _find_header_row(
    ws: Any,
    required_terms: Sequence[str],
    max_rows: int = 30,
    prefer_day_columns: bool = False,
) -> int:
'''

BODY_ANCHOR = '''    terms = [norm(x) for x in required_terms]
    loose_match: Optional[int] = None
    for r in range(1, min(ws.max_row, max_rows) + 1):
        vals = [norm(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)]
        if not all(any(term in value for value in vals) for term in terms):
            continue
        if _terms_in_distinct_cells(terms, vals):
            return r
        if loose_match is None:
            loose_match = r
    return loose_match if loose_match is not None else 1
'''
BODY_REPLACEMENT = '''    terms = [norm(x) for x in required_terms]
    loose_match: Optional[int] = None
    strict_match: Optional[int] = None
    day_anchored: Optional[int] = None
    for r in range(1, min(ws.max_row, max_rows) + 1):
        vals = [norm(ws.cell(r, c).value) for c in range(1, ws.max_column + 1)]
        if not all(any(term in value for value in vals) for term in terms):
            continue
        # B-12: requiring DISTINCT cells does nothing for a single term, so a
        # one-word lookup like ["name"] is still satisfied by a prose banner.
        # A row that binds all seven weekdays is a header; a banner is not.
        if prefer_day_columns and day_anchored is None:
            if len(_day_columns(ws, r)) == 7:
                day_anchored = r
        if _terms_in_distinct_cells(terms, vals):
            if strict_match is None:
                strict_match = r
            if not prefer_day_columns:
                return r
        elif loose_match is None:
            loose_match = r
    if day_anchored is not None:
        return day_anchored
    if strict_match is not None:
        return strict_match
    return loose_match if loose_match is not None else 1
'''

# The three day-bearing name-matched sheets.  Previous week scheduled carries a
# Saturday column only, binds no seven-day header anywhere, and so is
# unaffected -- it is passed the flag for consistency, not for effect.
CALL_SITES = [
    ('''        header = _find_header_row(ws, ["name"])
        headers = {norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
        name_col = next((c for h, c in headers.items() if "name" in h), 1)
''',
     '''        header = _find_header_row(ws, ["name"], prefer_day_columns=True)
        headers = {norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
        name_col = next((c for h, c in headers.items() if "name" in h), 1)
'''),
    ('''        header = _find_header_row(prev, ["name"])
''',
     '''        header = _find_header_row(prev, ["name"], prefer_day_columns=True)
'''),
    ('''    header = _find_header_row(ws, ["name"])
    headers = {norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
    name_col = next((c for h, c in headers.items() if "name" in h), None)
''',
     '''    header = _find_header_row(ws, ["name"], prefer_day_columns=True)
    headers = {norm(ws.cell(header, c).value): c for c in range(1, ws.max_column + 1)}
    name_col = next((c for h, c in headers.items() if "name" in h), None)
'''),
]


def patch(path: Path, pairs) -> None:
    text = path.read_text()
    for anchor, replacement in pairs:
        if replacement in text:
            print("  already applied: %s" % path.name)
            return
        if text.count(anchor) != 1:
            raise SystemExit(
                "ABORT %s: anchor found %d times, expected exactly 1:\n%s"
                % (path.name, text.count(anchor), anchor[:160]))
        text = text.replace(anchor, replacement)
    path.write_text(text)
    print("  patched: %s" % path)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    engine = Path(sys.argv[1])
    patch(engine / "_tools" / "l632_universal_scheduler.py",
          [(SIG_ANCHOR, SIG_REPLACEMENT), (BODY_ANCHOR, BODY_REPLACEMENT)] + CALL_SITES)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
