#!/usr/bin/env python3
"""Re-check the frozen Phase A closure evidence.

Every check in this script used to be a bare `assert`.  `python -O` strips
assert statements, so under `-O` the script printed its PASS line having
verified nothing at all - a gate that cannot fail.  The checks now branch and
the script returns a non-zero exit code, so it is usable from a shell gate.

The evidence file it reads is a frozen historical artifact.  It is not present
in this repository, and it must never be regenerated or reconstructed: a
fabricated baseline is worse than a missing one.  When it is absent this script
says so and returns 3, which is distinct from a verification failure (2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "qa" / "PHASE_A_CLOSURE_EVIDENCE.json"

EXPECTED_STATUS = "FROZEN_PHASE_A_CHECKPOINT_NOT_DEPLOYED"

# (gate name, field, predicate, human description)
CHECKS = (
    ("MIGRATED_FAST70_FRESH_SOLVER", "passed",
     lambda v: v == 70, "all 70 migrated fast scenarios passed"),
    ("THIN_OVERNIGHT_BREAK_RESILIENCE", "no_break_exceptions",
     lambda v: v == 0, "no break exceptions"),
    ("FIXED_FLEXIBLE_AND_HARD_FLOOR", "probe_status",
     lambda v: v in {"OPTIMAL", "FEASIBLE"}, "probe solved"),
    ("FEASIBLE_11H_3OFF_MICRO_T42", "break_status",
     lambda v: v in {"OPTIMAL", "FEASIBLE"}, "break stage solved"),
    ("FEASIBLE_DIRECTIONAL_SKILL_MICRO_T44", "language_gap_count",
     lambda v: v == 0, "no language gaps"),
    ("GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD", "classification",
     lambda v: v == "EXPECTED_GUARDED_REJECTION_DIAGNOSTIC", "guarded rejection"),
    ("11H_SKILL_REDUNDANCY_GUARD", "exception_lower_bound",
     lambda v: v == 12, "proven exception lower bound of 12"),
)


def verify(data: dict) -> list[str]:
    """Return a list of failure descriptions; empty means the evidence holds."""
    failures: list[str] = []
    status = data.get("status")
    if status != EXPECTED_STATUS:
        failures.append(f"status is {status!r}, expected {EXPECTED_STATUS!r}")

    gates = {gate.get("gate"): gate for gate in data.get("gates", [])}
    for name, field, predicate, description in CHECKS:
        gate = gates.get(name)
        if gate is None:
            failures.append(f"{name}: gate absent from the evidence")
            continue
        if field not in gate:
            # An absent field is not a satisfied one.
            failures.append(f"{name}: no {field!r} recorded, cannot confirm {description}")
            continue
        value = gate[field]
        if not predicate(value):
            failures.append(f"{name}: {field}={value!r} fails {description}")
    return failures


def main() -> int:
    if not EVIDENCE.exists():
        print(f"Phase A closure evidence not present: {EVIDENCE}", file=sys.stderr)
        print("This is a frozen historical artifact. Do not regenerate it - a "
              "reconstructed baseline proves nothing. Restore the original file "
              "to run this check.", file=sys.stderr)
        return 3
    try:
        data = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Phase A closure evidence unreadable: {exc}", file=sys.stderr)
        return 3

    failures = verify(data)
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", file=sys.stderr)
        return 2

    print(json.dumps({
        "status": "PASS",
        "release": data.get("release"),
        "engine_sha256": data.get("engine_sha256"),
        "checks_verified": len(CHECKS) + 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
