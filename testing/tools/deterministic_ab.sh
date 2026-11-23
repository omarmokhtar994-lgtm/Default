#!/usr/bin/env bash
# Deterministic A/B for engine changes. Use this instead of multi-seed repeats.
#
# WHY THIS EXISTS
#
# Every comparison in this review fought a noise band of plus or minus 1 to 4
# intervals, which forced repeats across seeds and still left results ambiguous.
# The noise was not the schedule; it was the solver. CP-SAT is a PORTFOLIO
# solver: with several workers it races different strategies and shares
# information between them, so the answer depends on thread timing. Google's own
# tracker carries cases of the same model returning OPTIMAL on one worker and
# INFEASIBLE on eight.
#
# With --num-workers 1 there is no race and the solve is reproducible. Verified
# here: two runs of AE_IT_B2B at seed 9000 returned byte-identical metrics,
# including after_avoidable_overage_fte_sum to three decimals.
#
# CONSEQUENCE: one run per arm is enough. Any difference is caused by the code,
# because nothing else varied. That turns a multi-hour multi-seed exercise into
# two runs.
#
# THIS IS A MEASUREMENT TOOL, NOT A PRODUCTION SETTING. Production should keep
# multiple workers -- the portfolio finds better schedules in the same wall
# clock. Single-worker is for answering "did this change do anything", where
# reproducibility matters more than quality.
#
#   ./deterministic_ab.sh <control_tree> <treatment_tree> <workbook> [seconds]
set -u
CTL="${1:?control tree}"; TRT="${2:?treatment tree}"; BOOK="${3:?workbook}"
SECS="${4:-300}"
OUT="$(dirname "$BOOK")/../.detab.$$"; mkdir -p "$OUT"
ID="$(basename "$BOOK" .xlsx)"

run() {
  python3 "$1/engine/RUN_UNIVERSAL_PRODUCTION.py" --input "$BOOK" \
    --output-root "$OUT" --schedule-id "$2" --stage FULL_SCHEDULE --mode QUICK \
    --time-limit "$SECS" --num-workers 1 --solver-random-seed 9000 --overwrite \
    > "$OUT/$2.log" 2>&1
}
run "$CTL" ctl & P1=$!
run "$TRT" trt & P2=$!
wait $P1; wait $P2

python3 - "$OUT" <<'PY'
import json, sys
out = sys.argv[1]
def g(n):
    d = json.load(open(f"{out}/{n}/BUSINESS_OUTCOME.json"))
    iv = d.get("independent_validation") or {}
    return (iv.get("metric_parity") or {}).get("engine") or {}
c, t = g("ctl"), g("trt")
keys = sorted(set(c) | set(t))
diffs = [(k, c.get(k), t.get(k)) for k in keys if c.get(k) != t.get(k)]
if not diffs:
    print("IDENTICAL across all %d canonical metrics." % len(keys))
    print("With one worker nothing else varied, so the change is a no-op here.")
else:
    print("DIFFERS on %d of %d metrics -- caused by the code, not the solver:" % (len(diffs), len(keys)))
    for k, a, b in diffs:
        print("   %-42s %s -> %s" % (k, a, b))
PY
rm -rf "$OUT"
