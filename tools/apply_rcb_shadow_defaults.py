#!/usr/bin/env python3
"""RC-B: delete the permissive shadow defaults on ParsedInput field reads.

`getattr(parsed, "x", <shadow>)` where `x` is a declared dataclass field is
dead code: the attribute always exists, so the shadow never fires. Collapsing
it to `parsed.x` is therefore a behaviour-preserving refactor.

It is worth doing because the shadows are not neutral. They are systematically
MORE PERMISSIVE than the declared defaults:

    whole_week_max_adjacent_raw_change      declared 3      shadow 999999
    whole_week_max_imbalance_violations     declared 0      shadow 999999
    whole_week_max_overage_cap_violations   declared 0      shadow 999999
    whole_week_overage_cap_ratio            declared 1.35   shadow 2.0
    employee_max_weekend_load_delta         declared 3      shadow 999999
    employee_max_overnight_load_delta       declared 3      shadow 999999
    employee_max_late_shift_load_delta      declared 3      shadow 999999
    employee_min_preference_satisfaction    declared 0.5    shadow 0.0
    skill_allocation_audit_enabled          declared True   shadow False
    quality_gate_mode                       declared 'fail' shadow 'off'
    employee_quality_gate_mode              declared 'warn' shadows 'off' AND 'warn'
    whole_week_gate_mode                    declared 'warn' shadows 'off' AND 'warn'

So the file reads as though the policy were "unlimited / off" when the policy
is actually a real limit. Two fields disagree with THEMSELVES between call
sites, which is the clearest sign this is a habit rather than a decision.

Two fields are deliberately left alone because they are NOT declared on
ParsedInput, which makes their shadow load-bearing:

    qslots_per_interval
    _shift_day_demand_fit_cache

Usage:  apply_rcb_shadow_defaults.py <engine_file> [--dry-run]
"""
import ast, sys

LEAVE_ALONE = {"qslots_per_interval", "_shift_day_demand_fit_cache"}


def declared_fields(tree):
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "ParsedInput":
            for st in node.body:
                if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                    out[st.target.id] = (
                        ast.unparse(st.value) if st.value is not None else "<required>"
                    )
    return out


def targets(tree, declared):
    """Every collapsible getattr(parsed, "<declared field>", <shadow>) call."""
    found = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and len(node.args) == 3 and not node.keywords
                and isinstance(node.args[0], ast.Name) and node.args[0].id == "parsed"
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)):
            continue
        field = node.args[1].value
        if field in LEAVE_ALONE or field not in declared:
            continue
        found.append((node.lineno, node.col_offset, node.end_lineno,
                      node.end_col_offset, field, ast.unparse(node.args[2]),
                      declared[field]))
    return found


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()
    tree = ast.parse(src)
    declared = declared_fields(tree)
    hits = targets(tree, declared)

    lines = src.splitlines(keepends=True)
    # byte offset of the start of each line
    starts, off = [], 0
    for ln in lines:
        starts.append(off)
        off += len(ln)

    def pos(lineno, col):
        return starts[lineno - 1] + col

    # rewrite back-to-front so earlier offsets stay valid
    edits = sorted(hits, key=lambda h: (h[0], h[1]), reverse=True)
    out = src
    divergent = 0
    for lineno, col, end_lineno, end_col, field, shadow, decl in edits:
        if shadow != decl:
            divergent += 1
        a, b = pos(lineno, col), pos(end_lineno, end_col)
        out = out[:a] + "parsed." + field + out[b:]

    # the rewrite must not change how the file parses beyond these calls
    ast.parse(out)
    remaining = targets(ast.parse(out), declared)
    assert not remaining, "collapse incomplete: %d site(s) left" % len(remaining)

    print("collapsed %d getattr-with-shadow site(s) across %d field(s)"
          % (len(hits), len({h[4] for h in hits})))
    print("  of those, %d had a shadow DIFFERENT from the declared default" % divergent)
    print("  left alone (shadow is load-bearing): %s" % ", ".join(sorted(LEAVE_ALONE)))
    if dry:
        print("  --dry-run: nothing written")
        return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
