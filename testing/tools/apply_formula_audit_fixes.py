"""Apply formula-audit fixes F-2, F-3, F-4 and F-5 to the engine.

Each is provably inert on every workbook in the corpus (see
evidence/formula_audit/FINDINGS.md): no real workbook has an off-grid shift,
overrides an overage cap, or sets a loss gate mode, and the F-3 figures are
reporting only. F-1 changes the model and is applied separately behind an A/B.

Every edit is an exact anchor replacement that must match exactly once, so a
drifted engine fails loudly here instead of being patched in the wrong place.
"""
from __future__ import annotations

import sys
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine" / "_tools" / "l632_universal_scheduler.py"

EDITS = [
    # ---------------------------------------------------------------- F-5
    ("F-5 target loss gate: restore its own HARD warning",
     '''    if target_loss_gate_mode not in {"off", "warn", "fail"}:
        target_loss_gate_mode = "warn"
    # #49:''',
     '''    if target_loss_gate_mode not in {"off", "warn", "fail"}:
        target_loss_gate_mode = "warn"
        parser_warnings.append("HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE: unknown value; use OFF, WARN, or FAIL.")
    # #49:'''),
    ("F-5 floor loss gate: name itself, not the target gate",
     '''    if floor_loss_gate_mode not in {"off", "warn", "fail"}:
        floor_loss_gate_mode = "warn"
        parser_warnings.append("HARD_INVALID_TARGET_LOSS_FROM_BREAKS_GATE_MODE: unknown value; use OFF, WARN, or FAIL.")''',
     '''    if floor_loss_gate_mode not in {"off", "warn", "fail"}:
        floor_loss_gate_mode = "warn"
        parser_warnings.append("HARD_INVALID_FLOOR_LOSS_FROM_BREAKS_GATE_MODE: unknown value; use OFF, WARN, or FAIL.")'''),

    # ---------------------------------------------------------------- F-4
    ("F-4 overage caps: percent only at >= 10, and let the order check fire",
     '''    for value_name, value in [
        ("soft", overage_soft_cap_ratio),
        ("severe", overage_severe_cap_ratio),
        ("extreme", overage_extreme_cap_ratio),
    ]:
        if value > 1.5:
            if value_name == "soft":
                overage_soft_cap_ratio = value / 100.0
            elif value_name == "severe":
                overage_severe_cap_ratio = value / 100.0
            else:
                overage_extreme_cap_ratio = value / 100.0
    overage_soft_cap_ratio = max(target_ratio, overage_soft_cap_ratio)
    overage_severe_cap_ratio = max(overage_soft_cap_ratio, overage_severe_cap_ratio)
    overage_extreme_cap_ratio = max(overage_severe_cap_ratio, overage_extreme_cap_ratio)''',
     '''    # Caps sit ABOVE 100%, so the `> 1.5 -> /100` rule Target and Floor use
    # cannot apply here: it turned a legitimate 1.6 (160%) into 0.016. Only a
    # bare number of 10 or more can be a percentage ("135" -> 1.35); no
    # plausible cap is ten times demand. The order of the three caps is NOT
    # forced here: validate_input_contract rejects a mis-ordered set as
    # INVALID_OVERAGE_CAP_ORDER, which a silent max() chain used to make
    # unreachable.
    if overage_soft_cap_ratio >= 10:
        overage_soft_cap_ratio /= 100.0
    if overage_severe_cap_ratio >= 10:
        overage_severe_cap_ratio /= 100.0
    if overage_extreme_cap_ratio >= 10:
        overage_extreme_cap_ratio /= 100.0'''),

    # ---------------------------------------------------------------- F-3
    ("F-3 shared workdays helper, defined next to the capacity code",
     '''def break_capacity_headcount_requirement(''',
     '''def default_workdays_per_week(parsed: ParsedInput) -> int:
    """Days one associate works in a week, for converting weekly capacity.

    4 for 10.5-hour-or-longer shift rosters (4x10 / 4x11), otherwise 5. The one
    place this is decided, so the capacity, break-resilience, coverage-split and
    break-headcount estimates cannot disagree about the length of a week.
    """
    durations = getattr(parsed, "allowed_shift_durations", None)
    return 4 if durations and min(durations) >= 630 else 5


def break_capacity_headcount_requirement('''),
    ("F-3 break headcount: a weekly deficit is divided by a weekly contribution",
     '''    net_per_associate = max(1, typical_shift_q - break_q_per_shift)
    additional_hc = int(math.ceil(deficit / net_per_associate)) if deficit else 0''',
     '''    net_per_associate = max(1, typical_shift_q - break_q_per_shift)
    # `deficit` is per WEEK (every worked day of the roster); one associate
    # contributes net_per_associate per SHIFT. Dividing a weekly deficit by one
    # day's contribution counted each added associate as working one day a
    # week and overstated the recommendation by roughly the days-per-week
    # factor (AE_AR_Choice: 7 recommended, 2 correct).
    net_per_associate_week = net_per_associate * default_workdays_per_week(parsed)
    additional_hc = int(math.ceil(deficit / net_per_associate_week)) if deficit else 0'''),
    ("F-3 coverage split: use the shared workdays, not a hard-coded 5",
     '''        workdays = max(1, 7 - 2)
        concurrent_ceiling''',
     '''        workdays = default_workdays_per_week(parsed)
        concurrent_ceiling'''),
]
# the two existing inline definitions become calls to the shared helper
INLINE = ('    default_workdays = 4 if parsed.allowed_shift_durations and '
          'min(parsed.allowed_shift_durations) >= 630 else 5')
INLINE_NEW = '    default_workdays = default_workdays_per_week(parsed)'

# ---------------------------------------------------------------- F-2
F2_ANCHOR = '''    if not parsed.shifts:
        failures.append({"code": "NO_LEGAL_SHIFTS", "detail": "No legal shifts were parsed from Shift Library."})'''
F2_NEW = F2_ANCHOR + '''
    # Every coverage function floors to 15-minute quarters (start_min // 15,
    # duration_min // 15), and _parse_shifts accepts any duration within 5
    # minutes of an allowed one. An off-grid shift would therefore be modelled
    # silently wrong: 09:00-17:57 becomes 8h45, a 09:10 start is credited from
    # 09:00. Reject it instead.
    off_grid = [shift.label for shift in parsed.shifts
                if shift.start_min % 15 or shift.duration_min % 15]
    if off_grid:
        failures.append({
            "code": "SHIFT_OFF_QUARTER_GRID",
            "detail": "Shift start and length must be whole 15-minute quarters.",
            "examples": off_grid[:20],
        })'''


def main() -> int:
    text = ENGINE.read_text(encoding="utf-8")
    for name, old, new in EDITS:
        count = text.count(old)
        if count != 1:
            print(f"ABORT {name}: anchor matched {count} times, expected 1")
            return 1
        text = text.replace(old, new, 1)
        print(f"applied  {name}")
    n_inline = text.count(INLINE)
    if n_inline != 2:
        print(f"ABORT F-3 inline workdays: matched {n_inline} times, expected 2")
        return 1
    text = text.replace(INLINE, INLINE_NEW)
    print("applied  F-3 capacity_diagnostics + break_resilience_diagnostics use the shared helper")
    if text.count(F2_ANCHOR) != 1:
        print("ABORT F-2: anchor did not match exactly once")
        return 1
    text = text.replace(F2_ANCHOR, F2_NEW, 1)
    print("applied  F-2 off-grid shifts are a contract failure")
    ENGINE.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
