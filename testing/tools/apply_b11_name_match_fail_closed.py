#!/usr/bin/env python3
"""B-11: name-matched input sheets must fail closed.

Three input sheets match rows to the roster by exact normalized name.  A row
that does not match is currently dropped:

  * Preference -- silently.  Preferences carry approved LEAVE and hard OFF,
    so a name typed differently from the roster discards that person's leave,
    makes them available to the solver, and schedules them.  Nothing warns.
  * Fixed Request -- silently, unless EVERY row misses.
  * Previous week scheduled -- an advisory, while a DUPLICATE on the same
    sheet is a hard failure.  A dropped Sunday rest-gap carry-in is not less
    serious than a duplicate.

The parity architecture cannot catch any of this: the independent validator
parses the same input contract, sees the same absent leave, and correctly
concludes the schedule satisfies every rule it can see.  Both sides are
consistently wrong about the same thing.  Parity proves the engine computed
the contract correctly, never that the contract is what the scheduler wrote.

This applier makes all three fail closed, joining the 27 HARD_ codes the
engine already has.

The one escape is a NAMED acknowledgement list in the Instructions sheet --
"Known Departed Associates" -- because a real roster loses people and an
unconditional block would be unusable.  It is deliberately not a suppression
flag: each name must be written out, and every acknowledged row is still
reported as a visible warning, so a dropped row is never invisible.

    python3 apply_b11_name_match_fail_closed.py <tree>/engine
"""
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Parse the acknowledgement list.
HELPER_ANCHOR = '''def _parse_preferences(
    wb: Any,
    associates: List[Associate],
    parser_warnings: Optional[List[str]] = None,
) -> None:
'''
HELPER_REPLACEMENT = '''def _parse_departed_acknowledgements(im: Dict[str, Any]) -> Set[str]:
    """Names the scheduler has explicitly declared as no longer on the roster.

    This is the only escape from the unmatched-row contract failures below.
    It is a list of names rather than a boolean on purpose: acknowledging that
    one person left must not also silence a typo in someone else's name.
    """
    raw = _instruction_get(
        im, ["Known Departed Associates", "Departed Associates", "Former Associates"], "")
    if raw in (None, ""):
        return set()
    text = str(raw).replace(";", ",").replace("\\n", ",")
    return {norm(part) for part in text.split(",") if norm(part)}


def _report_unmatched_name(
    parser_warnings: Optional[List[str]],
    code: str,
    sheet: str,
    supplied_name: str,
    acknowledged: Set[str],
    carries_data: bool = True,
) -> None:
    """Report an unmatched row, hard unless it asserts nothing or was acknowledged.

    An unmatched row that carries no value asserts no constraint, so dropping
    it cannot lose anything and failing the contract over it would be noise.
    SAKS_NEW ships exactly such a row: a 51st Preference line against a
    50-person roster with every day cell empty.

    An unmatched row that DOES carry a value is the dangerous case, and stays a
    contract failure. The engine cannot tell a misspelling of a roster member
    from someone who genuinely left -- the same SAKS row carries a real
    previous-Saturday shift on the boundary sheet -- and that is the reason to
    make a human reconcile it rather than to guess.

    An acknowledged name still produces a warning. The list exists to let a run
    proceed, never to make a dropped row invisible.
    """
    if parser_warnings is None:
        return
    if not carries_data:
        parser_warnings.append(
            f"UNMATCHED_EMPTY_ROW_IGNORED: {supplied_name!r} on the {sheet} sheet is not in "
            f"the Schedule roster. The row is empty, so no constraint was lost."
        )
        return
    if norm(supplied_name) in acknowledged:
        parser_warnings.append(
            f"DEPARTED_ASSOCIATE_ROW_IGNORED: {supplied_name!r} on the {sheet} sheet is not in "
            f"the Schedule roster and was ignored because it is listed under "
            f"'Known Departed Associates'."
        )
        return
    parser_warnings.append(
        f"{code}: {supplied_name!r} on the {sheet} sheet is not in the Schedule roster. "
        f"Correct the spelling, or list the name under 'Known Departed Associates' in "
        f"Instructions to confirm the row should be dropped."
    )


def _parse_preferences(
    wb: Any,
    associates: List[Associate],
    parser_warnings: Optional[List[str]] = None,
    acknowledged_departed: Optional[Set[str]] = None,
) -> None:
'''

# ---------------------------------------------------------------------------
# 2. Preference sheet: the silent one.
PREF_ANCHOR = '''        for r in range(header + 1, ws.max_row + 1):
            assoc = by_name.get(norm(ws.cell(r, name_col).value))
            if assoc:
                assoc.preferences = [str(ws.cell(r, c).value or "").strip() for c in day_cols]
'''
PREF_REPLACEMENT = '''        for r in range(header + 1, ws.max_row + 1):
            supplied_name = str(ws.cell(r, name_col).value or "").strip()
            assoc = by_name.get(norm(supplied_name))
            if assoc:
                assoc.preferences = [str(ws.cell(r, c).value or "").strip() for c in day_cols]
            elif supplied_name:
                # Preferences carry approved leave and hard OFF. Dropping a
                # populated row schedules someone who is not available.
                _report_unmatched_name(
                    parser_warnings, "HARD_PREFERENCE_UNKNOWN_ASSOCIATE",
                    "Preference", supplied_name, acknowledged,
                    carries_data=any(
                        str(ws.cell(r, c).value or "").strip() for c in day_cols))
'''

PREF_ACK_ANCHOR = '''    ws = _sheet_by_alias(wb, ["Preference", "Prefrence", "Preferences"])
    by_name = {norm(a.name): a for a in associates}
'''
PREF_ACK_REPLACEMENT = '''    acknowledged = acknowledged_departed or set()
    ws = _sheet_by_alias(wb, ["Preference", "Prefrence", "Preferences"])
    by_name = {norm(a.name): a for a in associates}
'''

# ---------------------------------------------------------------------------
# 3. Previous week scheduled: resolve the asymmetry with the duplicate check.
PREV_ANCHOR = '''            elif parser_warnings is not None:
                parser_warnings.append(
                    f"PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE: {supplied_name!r} is not in the Schedule roster and was ignored."
                )
'''
PREV_REPLACEMENT = '''            else:
                # A duplicate on this sheet is already a hard failure. An
                # unknown name drops the Sunday rest-gap carry-in entirely,
                # which is not the lesser defect.
                _report_unmatched_name(
                    parser_warnings, "HARD_PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE",
                    "Previous week scheduled", supplied_name, acknowledged,
                    carries_data=bool(str(prev.cell(r, sat_col).value or "").strip()))
'''

# The soft warning that mirrored the old advisory code now has nothing to
# collect: the code is HARD_ and validate_input_contract fails on it directly.
SOFT_ANCHOR = '''    unknown_previous_saturday = [
        warning for warning in parsed.parser_warnings
        if warning.startswith("PREVIOUS_SATURDAY_UNKNOWN_ASSOCIATE:")
    ]
    if unknown_previous_saturday:
        warnings.append({
            "code": "UNKNOWN_PREVIOUS_SATURDAY_ASSOCIATE",
            "count": len(unknown_previous_saturday),
            "examples": unknown_previous_saturday[:20],
            "detail": "Unknown historical names are ignored; confirm that the current roster's boundary values are complete where needed.",
        })
'''
SOFT_REPLACEMENT = '''    # B-11: an unknown name on any name-matched sheet is now a contract
    # failure (HARD_*), handled generically above. What remains here is the
    # acknowledged-departure case, which proceeds but stays visible.
    departed_rows_ignored = [
        warning for warning in parsed.parser_warnings
        if warning.startswith("DEPARTED_ASSOCIATE_ROW_IGNORED:")
    ]
    if departed_rows_ignored:
        warnings.append({
            "code": "DEPARTED_ASSOCIATE_ROW_IGNORED",
            "count": len(departed_rows_ignored),
            "examples": departed_rows_ignored[:20],
            "detail": "Rows for explicitly acknowledged departed associates were dropped. Confirm each person has genuinely left the roster.",
        })
    empty_rows_ignored = [
        warning for warning in parsed.parser_warnings
        if warning.startswith("UNMATCHED_EMPTY_ROW_IGNORED:")
    ]
    if empty_rows_ignored:
        warnings.append({
            "code": "UNMATCHED_EMPTY_ROW_IGNORED",
            "count": len(empty_rows_ignored),
            "examples": empty_rows_ignored[:20],
            "detail": "Rows whose name is not on the roster and which carry no value were dropped. Nothing was lost, but a stale name may indicate the sheet is out of date.",
        })
'''

# ---------------------------------------------------------------------------
# 4. Fixed Request: one missed row among many was silent.
FIXED_SIG_ANCHOR = '''def _parse_fixed_nesting(wb: Any, associates: List[Associate], parser_warnings: List[str]) -> None:
'''
FIXED_SIG_REPLACEMENT = '''def _parse_fixed_nesting(
    wb: Any,
    associates: List[Associate],
    parser_warnings: List[str],
    acknowledged_departed: Optional[Set[str]] = None,
) -> None:
'''

FIXED_ANCHOR = '''    by_name = {norm(a.name): a for a in associates}
    matched = 0
    for r in range(header + 1, ws.max_row + 1):
        assoc = by_name.get(norm(ws.cell(r, name_col).value))
        if not assoc:
            continue
        if active_col and not yes(ws.cell(r, active_col).value, True):
            continue
        matched += 1
'''
FIXED_REPLACEMENT = '''    acknowledged = acknowledged_departed or set()
    by_name = {norm(a.name): a for a in associates}
    matched = 0
    for r in range(header + 1, ws.max_row + 1):
        supplied_name = str(ws.cell(r, name_col).value or "").strip()
        # The active flag is checked before the name: a row the workbook has
        # switched off asserts nothing, so whose name is on it does not matter.
        if active_col and not yes(ws.cell(r, active_col).value, True):
            continue
        assoc = by_name.get(norm(supplied_name))
        if not assoc:
            if supplied_name:
                row_values = [str(ws.cell(r, c).value or "").strip() for c in day_cols]
                row_group = (str(ws.cell(r, group_col).value or "").strip()
                             if group_col else "")
                _report_unmatched_name(
                    parser_warnings, "HARD_FIXED_REQUEST_UNKNOWN_ASSOCIATE",
                    "Fixed Request", supplied_name, acknowledged,
                    carries_data=bool(any(row_values) or row_group))
            continue
        matched += 1
'''

# ---------------------------------------------------------------------------
# 5. Wire the list through parse_input.
CALL_ANCHOR = '''    _parse_preferences(wb, associates, parser_warnings)
'''
CALL_REPLACEMENT = '''    acknowledged_departed = _parse_departed_acknowledgements(im)
    _parse_preferences(wb, associates, parser_warnings, acknowledged_departed)
'''
CALL2_ANCHOR = '''        _parse_fixed_nesting(wb, associates, parser_warnings)
'''
CALL2_REPLACEMENT = '''        _parse_fixed_nesting(wb, associates, parser_warnings, acknowledged_departed)
'''


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
    patch(engine / "_tools" / "l632_universal_scheduler.py", [
        (HELPER_ANCHOR, HELPER_REPLACEMENT),
        (PREF_ACK_ANCHOR, PREF_ACK_REPLACEMENT),
        (PREF_ANCHOR, PREF_REPLACEMENT),
        (PREV_ANCHOR, PREV_REPLACEMENT),
        (SOFT_ANCHOR, SOFT_REPLACEMENT),
        (FIXED_SIG_ANCHOR, FIXED_SIG_REPLACEMENT),
        (FIXED_ANCHOR, FIXED_REPLACEMENT),
        (CALL_ANCHOR, CALL_REPLACEMENT),
        (CALL2_ANCHOR, CALL2_REPLACEMENT),
    ])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
