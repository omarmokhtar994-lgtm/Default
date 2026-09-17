#!/usr/bin/env python3
"""B-9: give six decision-driving metrics an independent check.

Each of these six is read by a release gate or by candidate selection, and
until now only the engine computed it -- the parity gate could not catch an
engine-side error in any of them because nothing else derived the number.

This applier makes the independent validator derive all six from the workbook
cells it already parses, and adds them to the canonical parity surface so a
disagreement becomes a gate failure rather than an unnoticed difference.

Run with the path to a release tree:
    python3 apply_b9_metric_coverage.py <tree>/engine
"""
import sys
from pathlib import Path

# (canonical name, engine key, validator key) -- the validator key is a new
# name only where the validator's existing vocabulary uses next_sunday_*.
NEW_FIELDS = [
    ("target_losses_from_breaks",
     ("target_losses_from_breaks",)),
    ("floor_losses_from_breaks",
     ("floor_losses_from_breaks",)),
    ("before_severe_floor_gap_count",
     ("before_severe_floor_gap_count",)),
    ("hard_floor_gap_count",
     ("hard_floor_gap_count",)),
    ("week_boundary_hard_failure_count",
     ("week_boundary_hard_failure_count", "next_sunday_hard_failure_count")),
    ("week_boundary_max_adjacent_raw_change",
     ("week_boundary_max_adjacent_raw_change", "next_sunday_max_adjacent_raw_change")),
    ("week_boundary_max_coverage_ratio",
     ("week_boundary_max_coverage_ratio", "next_sunday_max_coverage_ratio")),
]

ALIAS_BLOCK = "".join(
    '    "%s": (%s),\n' % (canon, ", ".join('"%s"' % a for a in aliases) + ("," if len(aliases) == 1 else ""))
    for canon, aliases in NEW_FIELDS
)

CANON_ANCHOR = """    "week_boundary_imbalance_violation_count": (
        "week_boundary_imbalance_violation_count", "next_sunday_imbalance_violation_count"
    ),
}
"""
CANON_REPLACEMENT = """    "week_boundary_imbalance_violation_count": (
        "week_boundary_imbalance_violation_count", "next_sunday_imbalance_violation_count"
    ),
    # B-9: six fields that a release gate or candidate selection reads, added
    # to the parity surface once the independent validator derived them too.
    # Before this, an engine-side error in any of them was invisible: nothing
    # else computed the number, so there was nothing to disagree with.
""" + ALIAS_BLOCK + "}\n"

# week_boundary_max_coverage_ratio is a ratio, not a count.
INT_ANCHOR = """    if not name.endswith("_ratio_observed") and name not in {
        "after_avoidable_overage_fte_sum","""
INT_REPLACEMENT = """    if not name.endswith("_ratio_observed") and name not in {
        "week_boundary_max_coverage_ratio",
        "after_avoidable_overage_fte_sum","""

# ---------------------------------------------------------------------------
# Validator: collect EVERY adjacency delta, not only the violating ones.
# The engine's week_boundary_max_adjacent_raw_change is a max over all
# adjacent pairs; taking it over violations only would report 0 on a clean
# schedule where the engine reports the true largest step.
VAL_ADJ_ANCHOR = """        delta=abs(int(current_raw)-int(previous_raw))
        allowed=eng.next_sunday_adjacent_raw_limit(parsed,int(previous_i),int(current_i))
        if delta>allowed:"""
VAL_ADJ_REPLACEMENT = """        delta=abs(int(current_raw)-int(previous_raw))
        allowed=eng.next_sunday_adjacent_raw_limit(parsed,int(previous_i),int(current_i))
        # Every adjacency contributes to the observed maximum step, including
        # the ones that stay inside their limit.
        next_adjacent_deltas.append(delta)
        if delta>allowed:"""

VAL_ADJ_INIT_ANCHOR = "    next_overage_cap_violations=[]; next_imbalance=[]\n"
VAL_ADJ_INIT_REPLACEMENT = "    next_overage_cap_violations=[]; next_imbalance=[]; next_adjacent_deltas=[]\n"

VAL_METRIC_ANCHOR = """        "quality_gate_issue_count":len(quality_issues),"""
VAL_METRIC_REPLACEMENT = """        # B-9: independently derived counterparts for six metrics that decide
        # hard validity or candidate selection.  Each is recomputed from the
        # parsed workbook rows above, never read from the optimizer audit.
        "target_losses_from_breaks":sum(
            1 for r in interval_rows
            if float(r['before_pct'])+1e-9>=parsed.target_ratio
            and float(r['after_pct'])+1e-9<parsed.target_ratio),
        "floor_losses_from_breaks":sum(
            1 for r in interval_rows
            if float(r['before_pct'])+1e-9>=parsed.floor_ratio
            and float(r['after_pct'])+1e-9<parsed.floor_ratio),
        "before_severe_floor_gap_count":sum(
            1 for r in interval_rows if float(r['before_pct'])+1e-9<severe_threshold),
        # Mirrors the engine exactly: no hard floor configured means the count
        # is 0, NOT a fall back to the soft floor.  The HARD_FLOOR failure
        # above deliberately falls back; this metric deliberately does not.
        "hard_floor_gap_count":(
            0 if parsed.hard_floor_ratio is None
            else sum(1 for r in interval_rows
                     if float(r['after_pct'])+1e-9<float(parsed.hard_floor_ratio))),
        "next_sunday_hard_failure_count":(
            len(next_floor_gaps)+len(next_zero)+len(next_language)+len(next_opening)
            +(len(next_blank)
              if parsed.blank_requirement_mode=="hard_no_current_week_staffing" else 0)),
        "next_sunday_max_adjacent_raw_change":max(next_adjacent_deltas,default=0),
        "next_sunday_max_coverage_ratio":round(
            max((float(r['pct']) for r in next_rows),default=0.0),8),
        "quality_gate_issue_count":len(quality_issues),"""


def patch(path: Path, pairs) -> None:
    text = path.read_text()
    for anchor, replacement in pairs:
        if replacement in text:
            print("  already applied: %s" % path.name)
            return
        if text.count(anchor) != 1:
            raise SystemExit(
                "ABORT %s: anchor found %d times, expected exactly 1:\n%s"
                % (path.name, text.count(anchor), anchor[:120]))
        text = text.replace(anchor, replacement)
    path.write_text(text)
    print("  patched: %s" % path)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    engine = Path(sys.argv[1])
    patch(engine / "_tools" / "canonical_metrics.py",
          [(CANON_ANCHOR, CANON_REPLACEMENT), (INT_ANCHOR, INT_REPLACEMENT)])
    patch(engine / "tools" / "independent_validator.py",
          [(VAL_ADJ_INIT_ANCHOR, VAL_ADJ_INIT_REPLACEMENT),
           (VAL_ADJ_ANCHOR, VAL_ADJ_REPLACEMENT),
           (VAL_METRIC_ANCHOR, VAL_METRIC_REPLACEMENT)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
