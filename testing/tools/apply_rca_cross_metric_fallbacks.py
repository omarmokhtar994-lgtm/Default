#!/usr/bin/env python3
"""RC-A: a missing metric must fail, not silently become a different metric.

THE DEFECT. Eighteen reads have the shape

    metrics.get("after_floor", metrics.get("after_80", 0))

If `after_floor` is absent, the code reports `after_80` AS THOUGH IT WERE the
floor. Those are the same number only when the coverage floor happens to be
0.80. On a workbook with floor 0.60 they differ -- measured at 86 against 72 on
the FLOOR_NOT_80 fixture -- and every downstream gate, ranking and report then
uses the wrong quantity with no signal that anything happened.

The same shape substitutes an unprefixed metric for a before-break one
(`before_severe_floor_gap_count` -> `severe_floor_gap_count`), which silently
crosses a stage boundary, and `before_raw_min` -> `before_raw`, which
substitutes a raw value for a minimum.

WHAT THE EVIDENCE SAYS. Instrumented build, four real workbooks, full solves:

    NO CROSS-METRIC FALLBACK EVER FIRED

So all eighteen are dead on the current corpus. That is the argument for fixing
them cheaply -- and NOT the argument for deleting them silently. RC-B taught
that lesson the hard way: its shadow defaults looked equally dead by
inspection, and duck-typed callers fired them on the first gate run.

THE FIX. Replace the cross-metric fallback with a read that FAILS, naming the
missing metric. A quantity that is always present loses nothing; a quantity
that ever goes missing now produces a diagnosable error at the point of loss
instead of a plausible wrong number several layers downstream.

This follows the convention the rest of this work established: B-11, B-12 and
C-3 all converted silent substitution into named failure.

Usage: apply_rca_cross_metric_fallbacks.py <engine_file> [--dry-run]
"""
import ast, re, sys

# outer key -> inner key that is a DIFFERENT quantity
PAIRS = [
    ("before_floor", "before_80"),
    ("after_floor", "after_80"),
    ("before_severe_floor_gap_count", "severe_floor_gap_count"),
    ("before_max_consecutive_floor_gaps", "max_consecutive_floor_gaps"),
    ("before_raw_min", "before_raw"),
]

HELPER = '''

class MissingMetricError(KeyError):
    """A decision metric was absent where the engine required it."""


def require_metric(metrics, key, alt_that_was_substituted=None):
    """Read a decision metric, failing loudly when it is absent.

    This replaces `metrics.get(key, metrics.get(other, 0))`. That shape reported
    a DIFFERENT quantity under the name of the missing one -- `after_80` as
    `after_floor`, an unprefixed gap count as a before-break one -- and every
    gate downstream then scored the wrong number with no signal.

    Measured across four real workbooks, the substitution never fired, so this
    costs nothing on known inputs. It exists so that an input which DOES drop a
    metric produces a named error here rather than a plausible wrong answer
    somewhere further on.
    """
    if key in metrics:
        return metrics[key]
    raise MissingMetricError(
        "required metric %r is missing; refusing to substitute %r, which is a "
        "different quantity whenever the coverage floor is not 0.80"
        % (key, alt_that_was_substituted)
    )
'''


def main():
    path = sys.argv[1]
    dry = "--dry-run" in sys.argv[2:]
    src = open(path).read()

    if "def require_metric(" not in src:
        anchor = list(re.finditer(r'^(?:import|from) .*$', src, re.M))[-1]
        src = src[:anchor.end()] + "\n" + HELPER + src[anchor.end():]

    total = 0
    for outer, inner in PAIRS:
        pat = re.compile(
            r'(\w[\w\.\[\]\(\)\'"]*)\.get\("%s",\s*\1\.get\("%s",\s*[^\)]+\)\)' % (outer, inner))
        src, n = pat.subn(
            lambda m: 'require_metric(%s, "%s", "%s")' % (m.group(1), outer, inner), src)
        total += n

    ast.parse(src)
    print("converted %d silent cross-metric fallback(s) into named failures" % total)
    for outer, inner in PAIRS:
        print("   %-38s no longer silently becomes %s" % (outer, inner))
    if dry:
        print("  --dry-run: nothing written"); return
    open(path, "w").write(src)
    print("  patched: %s" % path)


if __name__ == "__main__":
    main()
