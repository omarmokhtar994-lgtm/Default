#!/usr/bin/env python3
"""C-3 (register #3): the preference vocabulary is two exact words.

`preference_kind` recognises exactly `off` and `leave`. Everything else returns
"other", and "other" falls through all three blocking branches of
`associate_day_eligible_shifts`, so the person is schedulable. Measured:
`Annual Leave`, `Leave Day`, `A/L`, `AL`, `Vacation`, `Sick`, `Leave - approved`,
`Leve`, `OFF (approved)`, `Off Day`, `Rest`, `RD` and `X` all produce no
constraint and no warning. The Preference sheet carries zero data validations in
every shipped workbook and its own banner invites free text.

This is B-11 one level down: B-11 catches an unmatched NAME, this catches a
matched name whose VALUE is not understood. Fixing B-11 alone leaves the
cheaper half of the hole open.

Two parts, and the second matters more than the first:

  1. Widen the vocabulary to the forms planners actually write.
  2. Stop treating an unrecognised non-blank cell as silence. Widening alone
     just moves the cliff; step 2 removes it.

Step 2 is deliberately implemented in `validate_input_contract` rather than in
the sheet parsers. That keeps it independent of the B-11 applier, which edits
`_parse_preferences` and `_parse_fixed_nesting` -- the two can be applied in
either order without conflicting.

    python3 apply_c3_preference_vocabulary.py <tree>/engine
"""
import sys
from pathlib import Path

VOCAB_ANCHOR = '''def preference_kind(value: str) -> str:
    s = norm(value)
    if not s or s in {"none", "planned", "plan", "blank"}:
        return "blank"
    if s == "off":
        return "off"
    if s == "leave":
        return "leave"
    if shift_parts(value):
        return "shift"
    return "other"
'''

VOCAB_NEW = '''# C-3: the words planners actually write into the Preference sheet. The sheet
# is free text by design -- it carries no data validation in any shipped
# workbook and its own banner says "enter Leave/OFF/shift preference by day" --
# so the vocabulary has to cover the ordinary synonyms rather than two exact
# tokens. Anything still unrecognised is reported by validate_input_contract,
# never silently dropped; see UNRECOGNISED_PREFERENCE_VALUE below.
LEAVE_WORDS = frozenset({
    "leave", "annual leave", "annual", "a/l", "al", "vacation", "holiday",
    "leave day", "leave - approved", "leave approved", "approved leave",
    "sick", "sick leave", "s/l", "sl", "unpaid leave", "maternity",
    "paternity", "bereavement",
})
OFF_WORDS = frozenset({
    "off", "off day", "offday", "day off", "rest", "rest day", "rd", "x",
    "week off", "weekly off", "wo",
})


def preference_kind(value: str) -> str:
    s = norm(value)
    if not s or s in {"none", "planned", "plan", "blank"}:
        return "blank"
    if s in OFF_WORDS:
        return "off"
    if s in LEAVE_WORDS:
        return "leave"
    if shift_parts(value):
        return "shift"
    return "other"
'''

CONTRACT_ANCHOR = '''    if not parsed.associates:
        failures.append({"code": "NO_ROSTER", "detail": "No named roster rows were parsed."})
'''

CONTRACT_NEW = '''    if not parsed.associates:
        failures.append({"code": "NO_ROSTER", "detail": "No named roster rows were parsed."})
    # C-3: a non-blank preference or fixed cell the engine does not understand
    # is a value the planner meant something by. Dropping it silently is how
    # approved leave disappears -- "other" blocks nothing in
    # associate_day_eligible_shifts. Fail closed and name the cell, exactly as
    # an unmatched roster name does.
    unrecognised_preferences = []
    for associate in parsed.associates:
        for day_index in range(7):
            for source, values in (("preference", associate.preferences),
                                   ("fixed request", associate.fixed_schedule)):
                raw = values[day_index] if day_index < len(values) else ""
                if str(raw).strip() and preference_kind(raw) == "other":
                    unrecognised_preferences.append({
                        "associate": associate.name,
                        "day": DAY_NAMES[day_index],
                        "sheet": source,
                        "value": str(raw).strip(),
                    })
    if unrecognised_preferences:
        failures.append({
            "code": "UNRECOGNISED_PREFERENCE_VALUE",
            "count": len(unrecognised_preferences),
            "examples": unrecognised_preferences[:20],
            "detail": (
                "These cells are neither blank, a recognised OFF/leave word, nor a "
                "shift time, so the engine cannot tell what was intended and would "
                "otherwise ignore them. Correct the spelling or use a recognised value."
            ),
        })
'''


def patch(path: Path, pairs) -> None:
    text = path.read_text()
    for anchor, new in pairs:
        if new in text:
            print("  already applied: %s" % path.name)
            return
        if text.count(anchor) != 1:
            raise SystemExit("ABORT %s: anchor found %d times, expected 1:\n%s"
                             % (path.name, text.count(anchor), anchor[:160]))
        text = text.replace(anchor, new)
    path.write_text(text)
    print("  patched: %s" % path)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    engine = Path(sys.argv[1])
    patch(engine / "_tools" / "l632_universal_scheduler.py",
          [(VOCAB_ANCHOR, VOCAB_NEW), (CONTRACT_ANCHOR, CONTRACT_NEW)])
    print("""
NOTE: this makes an unrecognised preference cell a CONTRACT FAILURE. On the
15-workbook corpus that fires zero times -- every shipped workbook writes
exactly "Leave" or "OFF", which is why C-3 stayed latent. It will fire the
first time a human types into the sheet the engine asks them to type into,
which is the entire point.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
