#!/usr/bin/env python3
"""#38a: independently verify the employee_quality release gate.

WHY THIS ONE FIRST

`production_quality_gate.gate_results` holds nine gates that authorise release.
Counting references inside independent_validator.py, six are independently
recomputed and three are not:

    employee_quality   WARN  <- currently FIRING, zero validator references
    language_reserve   PASS        zero validator references
    skill_allocation   PASS        zero validator references

employee_quality is the one actually returning a verdict other than PASS, so
the engine is reporting a quality problem that nothing checks. That is the
gate worth closing first.

skill_allocation is deliberately NOT addressed: zero of nine corpus workbooks
define skills, so the gate passes trivially and a validator for it could not be
tested -- the same trap as nesting groups (0 of 15 workbooks).

WHAT IS RECOMPUTED, INDEPENDENTLY

From the OUTPUT WORKBOOK rather than the engine's in-memory skeleton, which is
what makes it a check rather than an echo:

  * late-shift load per associate   (start >= 18:00 or < 04:00)
  * overnight load                  (shift ends after midnight)
  * weekend load                    (Sunday and Saturday columns)
  * isolated OFF days               (an OFF sandwiched between two shifts)

Each load is reduced to a spread (max - min across the roster) and compared
against the declared caps: employee_max_late_shift_load_delta,
employee_max_overnight_load_delta, employee_max_weekend_load_delta.

Findings are reported as WARNINGS, not hard failures, because the engine's own
gate mode for this is `warn` by default. The validator must not be stricter
than the policy it is auditing; it exists to confirm the number, not to invent
one.

Usage:  apply_employee_quality_validation.py <engine_tree> [--check]
"""
from __future__ import annotations
import sys
from pathlib import Path

HELPER = '''

def independent_employee_quality(parsed, assignments, shift_map):
    """Recompute the employee_quality gate from the OUTPUT schedule.

    Independent by construction: it reads the published assignment grid, not
    the engine's skeleton object, so an engine that mis-scores its own gate
    cannot hide it here.

    Mirrors employee_operational_quality(): late shifts start at or after 18:00
    or before 04:00; overnight shifts end past midnight; weekend is the Sunday
    and Saturday columns; an isolated OFF is an OFF with a shift either side,
    evaluated circularly across the week boundary.
    """
    late, overnight, weekend = [], [], []
    isolated_off = 0
    for assoc in parsed.associates:
        row = assignments.get(norm(assoc.name)) or [""] * 7
        kinds, shifts = [], []
        for value in row[:7]:
            key = norm(value)
            if key == "off":
                kinds.append("off"); shifts.append(None)
            elif key in {"leave", "pto", "vacation"}:
                kinds.append("leave"); shifts.append(None)
            elif key in shift_map:
                kinds.append("shift"); shifts.append(shift_map[key])
            else:
                kinds.append("blank"); shifts.append(None)
        while len(kinds) < 7:
            kinds.append("blank"); shifts.append(None)

        late.append(sum(1 for s in shifts
                        if s is not None and (s.start_min >= 18 * 60 or s.start_min < 4 * 60)))
        overnight.append(sum(1 for s in shifts if s is not None and s.end_abs_min > 1440))
        weekend.append(sum(1 for d in (0, 6) if shifts[d] is not None))
        isolated_off += sum(
            1 for d in range(7)
            if kinds[d] == "off" and kinds[(d - 1) % 7] == "shift" and kinds[(d + 1) % 7] == "shift"
        )

    def spread(values):
        return (max(values) - min(values)) if values else 0

    return {
        "late_shift_load_delta": spread(late),
        "overnight_load_delta": spread(overnight),
        "weekend_load_delta": spread(weekend),
        "isolated_offday_violation_count": isolated_off,
        "roster_size": len(parsed.associates),
    }

'''

CALL = '''    # #38a: independently recompute the employee_quality gate. It is one of
    # three release gates the engine previously self-reported with no check,
    # and the only one observed returning a verdict other than PASS.
    employee_quality_independent = independent_employee_quality(parsed, assignments, shift_map)
    for _key, _cap_attr, _label in (
        ("late_shift_load_delta", "employee_max_late_shift_load_delta", "LATE_SHIFT"),
        ("overnight_load_delta", "employee_max_overnight_load_delta", "OVERNIGHT"),
        ("weekend_load_delta", "employee_max_weekend_load_delta", "WEEKEND"),
    ):
        _cap = getattr(parsed, _cap_attr, None)
        _observed = employee_quality_independent[_key]
        if isinstance(_cap, int) and _cap >= 0 and _observed > _cap:
            warnings.append({
                "type": f"EMPLOYEE_QUALITY_{_label}_LOAD_SPREAD",
                "observed_spread": _observed,
                "declared_cap": _cap,
                "note": "recomputed from the output schedule, independently of the engine gate",
            })

'''

ANCHOR = "    shift_map={norm(s.label):s for s in parsed.shifts}\n    failures=[]; warnings=[]\n"
RESULT_OLD = '        "metrics":metrics,'
RESULT_NEW = '        "metrics":metrics,\n        "employee_quality_independent":employee_quality_independent,'


def apply(tree: Path, check_only: bool = False) -> int:
    target = tree / "engine" / "tools" / "independent_validator.py"
    src = target.read_text()
    if "def independent_employee_quality(" in src:
        print("ALREADY APPLIED")
        return 0
    for name, anchor in (("helper anchor", "def max_gap_run("),
                         ("call anchor", ANCHOR),
                         ("result anchor", RESULT_OLD)):
        if src.count(anchor) != 1:
            print(f"FAIL: {name} found {src.count(anchor)} times, expected 1")
            return 1
    src = src.replace("def max_gap_run(", HELPER.strip("\n") + "\n\ndef max_gap_run(", 1)
    src = src.replace(ANCHOR, ANCHOR + CALL, 1)
    src = src.replace(RESULT_OLD, RESULT_NEW, 1)
    if check_only:
        print("WOULD PATCH: helper + gate recomputation + result field")
        return 0
    target.write_text(src)
    print(f"APPLIED: independent employee_quality verification -> {target}")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(apply(Path(args[0]), check_only="--check" in sys.argv))
