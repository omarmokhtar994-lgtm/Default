#!/usr/bin/env python3
"""S13-2: delete six top-level functions that nothing references.

Two of them are worse than merely unused -- they read as live policy:

  run_joint_cp_sat_refinement_phase   105 lines, a COMPLETE superseded joint
                                      refinement phase. Anyone reading it would
                                      reasonably believe it is what runs.
  optimization_phase_budgets           37 lines, a budget planner whose numbers
                                      look authoritative and are allocated
                                      nowhere.

Reachability was established three ways before deleting:
  1. AST: the name appears as no Name load and no Attribute anywhere in the
     engine, its satellite modules, or the test suites.
  2. String constants: the name appears in no string literal, so it cannot be
     reached by getattr or a dispatch table.
  3. Textual: a grep across EVERY file type in the tree, not just .py, in case
     a shell script or config referenced it.

The one near-miss that check three caught: `next_sunday_qslot` shows three
textual hits, but two of them are `protected_next_sunday_qslots` in the
validator -- a different identifier that merely contains the substring. It is
still dead.

Usage: apply_s132_delete_dead_code.py <engine_file> [--dry-run]
"""
import ast, os, sys, collections

DEAD = [
    "fallback_break_gap_diagnostics",
    "next_sunday_qslot",
    "next_sunday_same_day_shift_can_cover",
    "merge_compliant_with_safe_incumbent",
    "optimization_phase_budgets",
    "run_joint_cp_sat_refinement_phase",
]


def referenced(tree_root, engine_path):
    """Every name loaded, attribute accessed, or written as a string, project-wide."""
    used, strings = collections.Counter(), set()
    for root, _, names in os.walk(tree_root):
        if "__pycache__" in root:
            continue
        for n in names:
            if not n.endswith(".py"):
                continue
            try:
                t = ast.parse(open(os.path.join(root, n), errors="replace").read())
            except Exception:
                continue
            for node in ast.walk(t):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                    used[node.id] += 1
                elif isinstance(node, ast.Attribute):
                    used[node.attr] += 1
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    strings.add(node.value)
    return used, strings


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    tree_root = os.path.abspath(os.path.join(os.path.dirname(path), "..", ".."))

    src = open(path).read()
    tree = ast.parse(src)
    spans = {n.name: (n.lineno, n.end_lineno)
             for n in tree.body if isinstance(n, ast.FunctionDef)}

    used, strings = referenced(tree_root, path)
    for name in DEAD:
        if name not in spans:
            print("  %s already gone" % name); continue
        if used[name] or name in strings:
            sys.exit("ABORT: %s is referenced (%d load(s), string=%s); refusing to delete"
                     % (name, used[name], name in strings))

    lines = src.splitlines(keepends=True)
    drop = set()
    removed = 0
    for name in DEAD:
        if name not in spans:
            continue
        a, b = spans[name]
        # also swallow blank lines immediately after, so no double gap is left
        end = b
        while end < len(lines) and lines[end].strip() == "":
            end += 1
        for i in range(a - 1, end):
            drop.add(i)
        removed += b - a + 1

    out = "".join(l for i, l in enumerate(lines) if i not in drop)
    ast.parse(out)

    # nothing else may have been disturbed
    after = {n.name for n in ast.parse(out).body if isinstance(n, ast.FunctionDef)}
    lost = (set(spans) - after) - set(DEAD)
    assert not lost, "collateral damage: %r" % sorted(lost)

    print("deleted %d dead top-level function(s), %d lines of definition" % (len(DEAD), removed))
    print("  remaining top-level functions: %d (was %d)" % (len(after), len(spans)))
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
