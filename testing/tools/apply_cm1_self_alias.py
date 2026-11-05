#!/usr/bin/env python3
"""CM-1: one canonical field does not list its own name as an alias.

Every entry in the alias table names its own canonical key first:

    "after_avoidable_overage_stddev_fte": (
        "after_avoidable_overage_stddev_fte", "avoidable_overage_stddev_fte"),

One does not. It names a variant that drops "avoidable_":

    "after_avoidable_overage_top10_concentration": (
        "after_overage_top10_concentration", "avoidable_overage_top10_concentration"),

The field resolves today through its second alias, which is why parity passes.
It is one rename away from silently failing to resolve, and it is the only
field of 48 with this shape, so it reads as a typo rather than a decision.

Usage: apply_cm1_self_alias.py <canonical_metrics.py> [--dry-run]
"""
import sys

OLD = '''    "after_avoidable_overage_top10_concentration": (
        "after_overage_top10_concentration", "avoidable_overage_top10_concentration"
    ),'''
NEW = '''    "after_avoidable_overage_top10_concentration": (
        "after_avoidable_overage_top10_concentration",
        "after_overage_top10_concentration", "avoidable_overage_top10_concentration"
    ),'''


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()
    if NEW in src:
        print("  already fixed"); return
    if OLD not in src:
        sys.exit("ABORT: alias entry not in the expected form; refusing to guess")
    out = src.replace(OLD, NEW, 1)
    import ast; ast.parse(out)
    print("added the field's own name as its first alias")
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(out)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
