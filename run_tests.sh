#!/usr/bin/env bash
# RC9.2.1 fast gate: pure selector/metric/parity/identity guards.
# No solver, no workbook, no network. Intended to run on every commit before any
# solver time is spent.
#
# Exit status is 0 only if every suite and both selfchecks pass.
set -euo pipefail
PY="${PYTHON:-python3}"
cd "$(dirname "$0")"

fail=0
total=0

run_suite() {
  local suite="$1"
  local output status
  echo "── $suite"
  # Capture rather than pipe: piping to `tail` truncates a failure to three
  # lines, which usually hides which assertion actually failed. On success we
  # print the summary; on failure we print everything.
  set +e
  output="$("$PY" "$suite" 2>&1)"
  status=$?
  set -e
  if [ "$status" -eq 0 ]; then
    echo "$output" | tail -3
  else
    echo "$output"
    echo "   ^^ FAILED: $suite (exit $status)"
    fail=1
  fi
  total=$((total + 1))
}

run_check() {
  local label="$1"; shift
  echo "── $label"
  if "$@" >/dev/null 2>&1; then
    echo "   $label OK"
  else
    echo "   $label FAILED"
    # Re-run visibly so the reason is in the log rather than swallowed.
    "$@" 2>&1 | tail -20 || true
    fail=1
  fi
}

shopt -s nullglob
suites=(tests/test_rc9_2_1_*.py)
shopt -u nullglob
if [ "${#suites[@]}" -eq 0 ]; then
  # An empty glob previously meant the loop body never ran and the gate passed
  # having tested nothing. A gate that cannot fail is worse than no gate.
  echo "NO TEST SUITES FOUND under tests/ — refusing to report success"
  exit 1
fi
for suite in "${suites[@]}"; do
  run_suite "$suite"
done

run_check "engine selfcheck" "$PY" engine/_tools/l632_universal_scheduler.py --selfcheck
run_check "wrapper selfcheck" "$PY" engine/RUN_UNIVERSAL_PRODUCTION.py --selfcheck

echo
if [ "$fail" -eq 0 ]; then
  echo "GATE PASS — $total suite(s) + 2 selfchecks"
else
  echo "GATE FAIL — see failures above"
fi
exit $fail
