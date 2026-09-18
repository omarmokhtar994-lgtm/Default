#!/usr/bin/env python3
"""B-13: bound the joint refinement against MEASURED constants, not model variables.

THE DEFECT. Two bounds in the joint refinement model compare a solver-controlled
left side against a solver-controlled right side:

    model.Add(sum(target_hits) >= sum(before_target_hits) - cap)
    model.Add(sum(floor_hits)  >= sum(before_floor_hits)  - cap)

`before_target_hit` and `before_floor_hit` are both `model.NewBoolVar`. So
"after >= before - cap" is satisfiable two ways: protect the after-state, which
is the intent, or LOWER THE BEFORE-STATE, which is cheaper. Measured on three
paired seeds, the solver took the cheaper route -- AE_IT_B2B's before_floor
pinned at exactly 91 whenever the bound was active, against 91/98/97 when it
was not, with a worse after-floor every time.

THE CORRECT PATTERN ALREADY EXISTS twelve lines below, in the same function:

    if min_after_target is not None and target_hits:
        model.Add(sum(target_hits) >= max(0, int(min_after_target)))

`min_after_target` and `min_after_floor` are caller-supplied INTEGERS. Nothing
on the right-hand side can move, so the bound cannot be gamed.

It is passed at two call sites and left None at two others. Where it is None,
the only active protection is the gameable one.

THE FIX. Derive the measured before-counts from the incumbent inside the
function -- `anchor_candidates` is already a parameter, so no new plumbing --
and bound against those integers. The variable-versus-variable bounds go.

Usage: apply_b13_constant_joint_bounds.py <engine_file> [--dry-run]
"""
import ast, sys

OLD = '''    if before_target_hits and target_hits:
        model.Add(sum(target_hits) >= sum(before_target_hits) - parsed.quality_max_target_losses_from_breaks)'''

NEW = '''    # B-13: these bounds used to read
    #     sum(after_hits) >= sum(before_hits) - cap
    # with BOTH sides solver-controlled, because before_*_hit is a NewBoolVar.
    # That is satisfiable by lowering the before-state instead of protecting the
    # after-state, and three paired seeds showed the solver doing exactly that.
    # Bound against the incumbent's MEASURED counts instead: an integer cannot
    # be moved to buy slack. anchor_candidates is already in scope, so the
    # measured values need no new plumbing.
    _measured_before = anchor_candidates[0][1].metrics if anchor_candidates else {}
    _measured_before_target = int(_measured_before.get("before_target", 0) or 0)
    _measured_before_floor = int(_measured_before.get("before_floor", 0) or 0)
    if target_hits and _measured_before_target:
        model.Add(sum(target_hits) >= max(
            0, _measured_before_target - int(parsed.quality_max_target_losses_from_breaks)))'''

OLD2 = '''    if getattr(parsed, "target_loss_gate_mode", "warn") == "fail" and floor_hits and before_floor_hits:
        model.Add(sum(floor_hits) >= sum(before_floor_hits) - getattr(parsed, "quality_max_target_losses_from_breaks", 6))'''

NEW2 = '''    if floor_hits and _measured_before_floor:
        model.Add(sum(floor_hits) >= max(
            0, _measured_before_floor - int(parsed.quality_max_floor_losses_from_breaks)))'''


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()
    if "_measured_before_target" in src:
        print("  already applied"); return
    for old in (OLD, OLD2):
        if old not in src:
            sys.exit("ABORT: anchor missing, refusing to guess:\n%s" % old[:100])
    out = src.replace(OLD, NEW, 1).replace(OLD2, NEW2, 1)
    ast.parse(out)
    print("both joint bounds now compare against the incumbent's MEASURED counts")
    print("  target bound: was unconditional and gameable, now a constant bound")
    print("  floor  bound: now active again, but against a constant, with the floor cap")
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
