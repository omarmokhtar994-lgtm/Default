#!/usr/bin/env bash
# Apply the staged fixes in fix-plan order, gating after every step.
#
# Each step is applied to the release tree and then the full gate is run. If any
# step fails the gate, the script stops immediately and leaves the tree at the
# last good state so the failure can be read rather than buried under the next
# change.
#
# Order is evidence/FIX_PLAN.md: W1, then W2 (B-12 before B-11 because B-11
# false-positives without the header fix), then C-3, then B-9, then W10.
# W3's fixtures need no application -- they are inputs.
#
#   ./apply_fix_plan.sh <tree>            apply and gate each step
#   ./apply_fix_plan.sh <tree> --dry-run  copy the tree first, touch nothing real
set -u
TREE="${1:?usage: apply_fix_plan.sh <tree> [--dry-run]}"
DRY="${2:-}"
TOOLS="$(cd "$(dirname "$0")" && pwd)"

if [ "$DRY" = "--dry-run" ]; then
  SCRATCH="$(dirname "$TREE")/fixplan_dryrun"
  rm -rf "$SCRATCH"; mkdir -p "$SCRATCH"
  cp -r "$TREE"/* "$SCRATCH"/ 2>/dev/null
  find "$SCRATCH" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
  TREE="$SCRATCH"
  echo "DRY RUN against a copy: $TREE"
fi

echo "=== baseline gate before touching anything ==="
if ! ( cd "$TREE" && bash run_tests.sh >/tmp/fixplan_gate0.log 2>&1 ); then
  echo "ABORT: the tree does not pass its own gate before any change."
  tail -20 /tmp/fixplan_gate0.log
  exit 2
fi
echo "    baseline: $(grep -E '^GATE' /tmp/fixplan_gate0.log)"
echo

step() {
  local name="$1"; shift
  echo "=== $name ==="
  if ! "$@"; then
    echo "    APPLIER FAILED -- stopping, tree left at the last good state"
    exit 1
  fi
  local log="/tmp/fixplan_gate_$(echo "$name" | tr -cd 'A-Za-z0-9').log"
  if ( cd "$TREE" && bash run_tests.sh >"$log" 2>&1 ); then
    echo "    $(grep -E '^GATE' "$log")"
  else
    echo "    GATE FAILED after $name -- stopping so the failure is readable"
    grep -E '\^\^ FAILED' "$log" | head -5
    exit 1
  fi
  echo
}

step "W1  floor losses get a cap and a gate" \
     python3 "$TOOLS/apply_w1_floor_loss_gate.py" "$TREE/engine"
step "W2a B-12 header row must not match a prose banner" \
     python3 "$TOOLS/apply_b12_header_row_day_anchor.py" "$TREE/engine"
step "W2b B-11 name-matched sheets fail closed" \
     python3 "$TOOLS/apply_b11_name_match_fail_closed.py" "$TREE/engine"
step "W2c C-3 preference vocabulary fails closed" \
     python3 "$TOOLS/apply_c3_preference_vocabulary.py" "$TREE/engine"
step "W7a B-9 independent checks for 7 decision metrics" \
     python3 "$TOOLS/apply_b9_metric_coverage.py" "$TREE/engine"

echo "=== W10 wire the staged tests into the gate ==="
cp "$TOOLS/../tests_staged/"*.py "$TREE/tests/" && echo "    copied $(ls -1 "$TOOLS/../tests_staged/"*.py | wc -l) suites into tests/"
if ( cd "$TREE" && bash run_tests.sh >/tmp/fixplan_gate_final.log 2>&1 ); then
  echo "    $(grep -E '^GATE' /tmp/fixplan_gate_final.log)"
else
  echo "    GATE FAILED with the new suites in place"
  grep -E '\^\^ FAILED' /tmp/fixplan_gate_final.log | head -5
  exit 1
fi

echo
echo "=== all steps applied and gated ==="
echo "Still to do by hand, because each needs a decision or a measurement:"
echo "  W4  delete the 90 permissive shadow defaults"
echo "  W5  the 18 cross-metric fallbacks (FX1 can prove this one)"
echo "  W6  enforce PHASE_MINIMUM_VIABLE_SECONDS   (needs A/B with repeats)"
echo "  W7b the three unmodelled subsystems        (authors' scoping call)"
echo "  W8  derive the 11 orderings from one definition"
echo "  W9  B-10 break-slice floor vs cap          (needs A/B with repeats)"
echo "  W11 break up run_case, delete 213 dead lines"
