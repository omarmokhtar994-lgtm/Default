#!/usr/bin/env python3
"""W1: give floor losses from breaks a cap and a gate of their own.

Register #1, and the only finding with a live observation: sweep case 2
(AE_AR_Choice) lost 3 floor intervals to break placement, the quality gate
returned PASS, and the run's floor came out one below the authors' baseline.

Three defects in the current code:

1. `floor_losses_from_breaks` is computed (8074), exported to the leaderboard
   (12394) and used in a near-feasible test (9986) -- but no release gate ever
   reads it. `production_quality_gate` checks only the target metric.
2. The one bound that touches it, at 14310, borrows
   `quality_max_target_losses_from_breaks`. No floor-loss cap exists anywhere
   in the contract; the target budget was authored for a different metric.
3. That bound applies only when `target_loss_gate_mode == "fail"`, whose
   declared default is "warn", while the target bound beside it is
   unconditional. So by default floor losses are unconstrained in joint
   refinement while target losses are hard-capped.

Floor is the safety threshold *below* target. Losing it to break placement is
the more serious of the two losses, and it is the one with neither a cap nor a
gate.

The new field mirrors the target one exactly -- same scaled default, its own
gate mode defaulting to "warn" -- so no currently-passing run starts failing.
That is deliberate: making the loss VISIBLE is the fix, and choosing a tighter
default is a scheduling-policy decision for the RC5 authors on more evidence
than one observation. See the note at the end of this file.

    python3 apply_w1_floor_loss_gate.py <tree>/engine
"""
import sys
from pathlib import Path

FIELD_ANCHOR = """    quality_max_target_losses_from_breaks: int = 6
    target_loss_gate_mode: str = "warn"
"""
FIELD_NEW = """    quality_max_target_losses_from_breaks: int = 6
    target_loss_gate_mode: str = "warn"
    # W1: floor losses get their own budget. Borrowing the target budget made
    # a limit authored for one metric silently govern another.
    quality_max_floor_losses_from_breaks: int = 6
    floor_loss_gate_mode: str = "warn"
"""

PARSE_ANCHOR = """    if target_loss_gate_mode not in {"off", "warn", "fail"}:
        target_loss_gate_mode = "warn"
"""
PARSE_NEW = """    if target_loss_gate_mode not in {"off", "warn", "fail"}:
        target_loss_gate_mode = "warn"
    default_floor_loss_cap = max(3, int(math.ceil(active_interval_count * 0.05)))
    quality_max_floor_losses_from_breaks = max(0, int(round(to_float(_instruction_get(
        im, ["Maximum Floor Intervals Lost From Breaks", "Maximum Break Floor Losses"],
        default_floor_loss_cap
    ), default_floor_loss_cap))))
    floor_loss_gate_mode = norm(_instruction_get(
        im, ["Floor Loss From Breaks Gate Mode", "Break Floor Loss Gate Mode"], "warn"
    ))
    if floor_loss_gate_mode not in {"off", "warn", "fail"}:
        floor_loss_gate_mode = "warn"
"""

CONSTRUCT_ANCHOR = """        quality_max_target_losses_from_breaks=quality_max_target_losses_from_breaks,
        target_loss_gate_mode=target_loss_gate_mode,
"""
CONSTRUCT_NEW = """        quality_max_target_losses_from_breaks=quality_max_target_losses_from_breaks,
        target_loss_gate_mode=target_loss_gate_mode,
        quality_max_floor_losses_from_breaks=quality_max_floor_losses_from_breaks,
        floor_loss_gate_mode=floor_loss_gate_mode,
"""

PAYLOAD_ANCHOR = """            "maximum_target_losses_from_breaks": getattr(parsed, "quality_max_target_losses_from_breaks", 999999),
            "target_loss_gate_mode": getattr(parsed, "target_loss_gate_mode", "warn"),
"""
PAYLOAD_NEW = """            "maximum_target_losses_from_breaks": parsed.quality_max_target_losses_from_breaks,
            "target_loss_gate_mode": parsed.target_loss_gate_mode,
            "maximum_floor_losses_from_breaks": parsed.quality_max_floor_losses_from_breaks,
            "floor_loss_gate_mode": parsed.floor_loss_gate_mode,
"""

GATE_ANCHOR = """    apply(getattr(parsed, "target_loss_gate_mode", "warn"), target_loss_issues, "target_loss")
"""
GATE_NEW = """    apply(parsed.target_loss_gate_mode, target_loss_issues, "target_loss")

    # W1: floor losses were computed and exported but gated nowhere.
    floor_loss_issues: List[Dict[str, Any]] = []
    if int(metrics.get("floor_losses_from_breaks", 0) or 0) > parsed.quality_max_floor_losses_from_breaks:
        floor_loss_issues.append({
            "code": "FLOOR_LOSSES_FROM_BREAKS_EXCEEDED",
            "actual": int(metrics.get("floor_losses_from_breaks", 0) or 0),
            "maximum": parsed.quality_max_floor_losses_from_breaks,
        })
    apply(parsed.floor_loss_gate_mode, floor_loss_issues, "floor_loss")
"""

REPORT_ANCHOR = """        "target_losses_from_breaks": int(metrics.get("target_losses_from_breaks", 0) or 0),
        "maximum_target_losses_from_breaks": getattr(parsed, "quality_max_target_losses_from_breaks", 999999),
"""
REPORT_NEW = """        "target_losses_from_breaks": int(metrics.get("target_losses_from_breaks", 0) or 0),
        "maximum_target_losses_from_breaks": parsed.quality_max_target_losses_from_breaks,
        "floor_losses_from_breaks": int(metrics.get("floor_losses_from_breaks", 0) or 0),
        "maximum_floor_losses_from_breaks": parsed.quality_max_floor_losses_from_breaks,
"""

# The joint-refinement bound: use the floor budget, and apply it unconditionally
# exactly as the target bound above it already does.
JOINT_ANCHOR = """    if before_target_hits and target_hits:
        model.Add(sum(target_hits) >= sum(before_target_hits) - getattr(parsed, "quality_max_target_losses_from_breaks", 999999))
    if getattr(parsed, "target_loss_gate_mode", "warn") == "fail" and floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - getattr(parsed, "quality_max_target_losses_from_breaks", 999999))
"""
JOINT_NEW = """    if before_target_hits and target_hits:
        model.Add(sum(target_hits) >= sum(before_target_hits) - parsed.quality_max_target_losses_from_breaks)
    # W1: this used the TARGET budget, and only when the TARGET gate was in
    # fail mode -- so by default floor losses were unbounded here while target
    # losses were hard-capped. It now uses the floor budget, unconditionally,
    # exactly as the target bound above does.
    if floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - parsed.quality_max_floor_losses_from_breaks)
"""


# ---------------------------------------------------------------------------
# The gate roster is pinned by a test, deliberately, so a new gate cannot
# appear without someone deciding it should. `floor_loss` is such a decision,
# and it DOES route through apply(), so the guard's intent is preserved: the
# list gains one entry, the assertion still proves every gate uses the helper.
TEST_ANCHOR = """        self.assertEqual(sorted(gate["gate_results"]), [
            "break_concurrency", "coverage", "employee_quality", "language_reserve",
            "next_sunday_balance", "skill_allocation", "target_loss",
            "whole_week_balance"])
"""
TEST_NEW = """        self.assertEqual(sorted(gate["gate_results"]), [
            "break_concurrency", "coverage", "employee_quality", "floor_loss",
            "language_reserve", "next_sunday_balance", "skill_allocation",
            "target_loss", "whole_week_balance"])
"""


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
    patch(engine / "_tools" / "l632_universal_scheduler.py", [
        (FIELD_ANCHOR, FIELD_NEW),
        (PARSE_ANCHOR, PARSE_NEW),
        (CONSTRUCT_ANCHOR, CONSTRUCT_NEW),
        (PAYLOAD_ANCHOR, PAYLOAD_NEW),
        (GATE_ANCHOR, GATE_NEW),
        (REPORT_ANCHOR, REPORT_NEW),
        (JOINT_ANCHOR, JOINT_NEW),
    ])
    tests = engine.parent / "tests" / "test_rc9_2_1_rule_semantics.py"
    if tests.exists():
        patch(tests, [(TEST_ANCHOR, TEST_NEW)])
    print("""
NOTE FOR THE AUTHORS -- two decisions left open deliberately:

  1. The default cap mirrors the target one: max(3, ceil(active * 0.05)).
     On AE_AR_Choice that is 8, so its observed 3 floor losses would be
     REPORTED but would not trip the gate. Making the loss visible is the fix;
     choosing a tighter floor budget is a scheduling-policy call that needs
     more evidence than one observation.

  2. The joint-refinement bound at 14310 is now unconditional, matching the
     target bound beside it. That is the one part of this patch that can change
     a produced schedule, so it needs its own A/B with repeats -- multi-worker
     runs are nondeterministic and the effect size is around one interval.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
