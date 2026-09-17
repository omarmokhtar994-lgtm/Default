#!/usr/bin/env python3
"""S6-1 / S6-2: a nesting group with conflicting leave is a named failure, not a bare INFEASIBLE.

THE MODEL forces every member of a nesting group onto the leader, for each day:

    model.Add(off[member, d]   == off[leader, d])
    model.Add(leave[member, d] == leave[leader, d])
    model.Add(x[member, d, s]  == x[leader, d, s])

`leave[a, d]` is PINNED from the contract -- approved leave is an input, not a
decision. So two members of one nesting group with different approved leave
days produce `1 == 0`, and the whole model is INFEASIBLE in about 0.04s with
nothing naming the cause. The user sees "no schedule" and no reason.

THE EXISTING CHECK cannot catch it:

    if associate.nesting_group and any(associate.fixed_schedule):

It compares `fixed_schedule` only, and only for associates that HAVE one. The
model groups on `nesting_group` alone, so a group whose members carry leave but
no fixed schedule is constrained by the solver and never contract-checked. That
gap is S6-2; the silent INFEASIBLE it allows is S6-1.

THE FIX adds a check mirroring exactly what the model enforces, under the same
`fixed_enabled` condition the model uses, and emits a named contract failure.
This follows the convention B-11, B-12 and C-3 established in this work:
convert a silent wrong outcome into a named one.

Usage: apply_s61_nesting_leave_conflict.py <engine_file> [--dry-run]
"""
import ast, sys

ANCHOR = '''    if contradictory_groups:
        failures.append({
            "code": "CONTRADICTORY_EXACT_SCHEDULES_IN_NESTING_GROUP",
            "count": len(contradictory_groups), "examples": contradictory_groups[:20],
        })
'''

ADDITION = '''    if contradictory_groups:
        failures.append({
            "code": "CONTRADICTORY_EXACT_SCHEDULES_IN_NESTING_GROUP",
            "count": len(contradictory_groups), "examples": contradictory_groups[:20],
        })
    # S6-1/S6-2: the model forces every nesting-group member onto the leader's
    # off[], leave[] and shift assignment. leave[] is pinned from the contract,
    # so members with different approved leave give 1 == 0 and the model is
    # INFEASIBLE with nothing naming the cause. The check above compares only
    # fixed_schedule, and only for associates that have one, so it cannot see
    # this. Mirror what the model actually enforces, under the same condition.
    if parsed.fixed_enabled:
        nesting_preferences: Dict[str, List[Tuple[str, Tuple[str, ...]]]] = {}
        for associate in parsed.associates:
            if associate.nesting_group:
                nesting_preferences.setdefault(norm(associate.nesting_group), []).append(
                    (associate.name,
                     tuple(preference_kind(value) for value in associate.preferences))
                )
        conflicting_preference_groups = []
        for group, rows in nesting_preferences.items():
            if len(rows) < 2:
                continue
            if len({pattern for _, pattern in rows}) > 1:
                conflicting_preference_groups.append(
                    {"group": group, "members": [name for name, _ in rows]}
                )
        if conflicting_preference_groups:
            failures.append({
                "code": "CONFLICTING_LEAVE_OR_OFF_IN_NESTING_GROUP",
                "count": len(conflicting_preference_groups),
                "examples": conflicting_preference_groups[:20],
            })
'''


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()
    if "CONFLICTING_LEAVE_OR_OFF_IN_NESTING_GROUP" in src:
        print("  already applied"); return
    if ANCHOR not in src:
        sys.exit("ABORT: anchor not found in expected form; refusing to guess")
    out = src.replace(ANCHOR, ADDITION, 1)
    ast.parse(out)
    print("added CONFLICTING_LEAVE_OR_OFF_IN_NESTING_GROUP contract failure")
    print("  mirrors the model's own nesting constraint, under the same fixed_enabled guard")
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
