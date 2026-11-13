#!/usr/bin/env bash
# RC9.2.2 fast gate: pure selector/metric/parity/identity guards.
# No solver, no workbook, no network. Intended to run on every commit before any
# solver time is spent.
#
# Exit status is 0 only if every suite and both selfchecks pass.
set -euo pipefail
PY="${PYTHON:-python3}"
cd "$(dirname "$0")"

fail=0
total=0
tests_run=0
tests_skipped=0

# Count what each suite actually ran and skipped (audit F-01/F-15): the gate
# reported suites only, so 209 tests could drop out of it and nothing noticed.
count_tests() {
  local output="$1" ran skipped
  ran=$(echo "$output" | grep -oE "^Ran [0-9]+ test" | tail -1 | grep -oE "[0-9]+" || true)
  skipped=$(echo "$output" | grep -oE "skipped=[0-9]+" | tail -1 | grep -oE "[0-9]+" || true)
  tests_run=$((tests_run + ${ran:-0}))
  tests_skipped=$((tests_skipped + ${skipped:-0}))
}

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
  count_tests "$output"
  if [ "$status" -eq 0 ]; then
    echo "$output" | tail -3
  else
    echo "$output"
    echo "   ^^ FAILED: $suite (exit $status)"
    fail=1
  fi
  total=$((total + 1))
}

# A staged suite that collects zero tests exits 0 and would pass silently.
# Require unittest to report a non-zero count before crediting the suite.
run_staged_suite() {
  local suite="$1"
  echo "── $suite"
  set +e
  output="$("$PY" "$suite" 2>&1)"
  status=$?
  set -e
  count_tests "$output"
  if [ "$status" -ne 0 ]; then
    echo "$output"
    echo "   ^^ FAILED: $suite (exit $status)"
    fail=1
  elif ! echo "$output" | grep -qE "^Ran [1-9][0-9]* test"; then
    echo "$output"
    echo "   ^^ FAILED: $suite collected no tests"
    fail=1
  else
    echo "$output" | tail -3
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

# Candidate-tree suites. These target the RC9.2.2 hardened engine preserved
# under candidates/, not the production engine/ tree, so they are selected by
# RC9_ENGINE_DIR rather than by the tests/ glob above. They were written and
# mutation-checked but never executed by this gate, which is why the gate
# reported 9 suites while 7 more sat unrun in tests_staged/.
# The RC5 hardening line has been merged into engine/, so these suites now
# test the SHIPPING engine. candidates/RC9_2_2_HARDENED_RC5 remains as the
# pre-merge snapshot for provenance and is no longer what the gate exercises.
CANDIDATE_ENGINE="${RC9_CANDIDATE_DIR:-.}"
shopt -s nullglob
staged=(tests_staged/test_*.py)
shopt -u nullglob
if [ "${#staged[@]}" -eq 0 ]; then
  echo "NO STAGED SUITES FOUND under tests_staged/ — refusing to report success"
  exit 1
fi
if [ ! -d "$CANDIDATE_ENGINE/engine/_tools" ]; then
  echo "CANDIDATE TREE MISSING at $CANDIDATE_ENGINE — refusing to report success"
  exit 1
fi
for suite in "${staged[@]}"; do
  RC9_ENGINE_DIR="$PWD/$CANDIDATE_ENGINE/engine/_tools" \
  RC9_RUNNER="$PWD/$CANDIDATE_ENGINE/engine/RUN_UNIVERSAL_PRODUCTION.py" \
    run_staged_suite "$suite"
done

run_check "engine selfcheck" "$PY" engine/_tools/l632_universal_scheduler.py --selfcheck
run_check "wrapper selfcheck" "$PY" engine/RUN_UNIVERSAL_PRODUCTION.py --selfcheck

# Cross-module call-signature check. This is how the merge's
# build_global_budget_plan(diagnostics=...) TypeError got through: every suite
# and both selfchecks passed, because neither enters run_case, and ruff's F821
# does not see it -- the NAME resolves, only the keyword was wrong. A full
# 1800s run died on the first call. This catches it statically in under a
# second, and is verified to do so by removing the parameter again.
echo "── cross-module call signatures"
if "$PY" tools/check_cross_module_calls.py engine >/tmp/xmod.out 2>&1; then
  echo "   cross-module call signatures OK"
else
  echo "   cross-module call signatures FAILED"
  cat /tmp/xmod.out
  fail=1
fi

# Static undefined-name sweep. This is how the parse_time_to_minute NameError was
# found: neither the suites nor line-by-line reading caught a name that is called
# but defined nowhere. Skipped with a visible notice when ruff is absent, never
# silently.
echo "── undefined-name sweep"
if command -v ruff >/dev/null 2>&1; then
  if ruff check --isolated --select E9,F821 engine/ tools/ tests/ >/dev/null 2>&1; then
    echo "   undefined-name sweep OK"
  else
    echo "   undefined-name sweep FAILED"
    ruff check --isolated --select E9,F821 engine/ tools/ tests/ 2>&1 | tail -30
    fail=1
  fi
else
  echo "   SKIPPED (ruff not installed) — tests/test_rc9_2_1_engine_name_resolution.py"
  echo "   still runs an in-process cross-check"
fi

# Floors on what the gate must execute: a suite or test that silently stops
# running, or a skip that creeps in because an asset went missing, fails here.
echo "── test totals"
read -r min_tests max_skips < <("$PY" -c "import json;d=json.load(open('tests_staged/GATE_MINIMUMS.json'));print(d['min_tests'],d['max_skips'])")
echo "   $tests_run tests run, $tests_skipped skipped (minimum $min_tests run, at most $max_skips skipped)"
if [ "$tests_run" -lt "$min_tests" ]; then
  echo "   FAILED: fewer tests ran than tests_staged/GATE_MINIMUMS.json requires"
  fail=1
fi
if [ "$tests_skipped" -gt "$max_skips" ]; then
  echo "   FAILED: more tests skipped than tests_staged/GATE_MINIMUMS.json allows"
  fail=1
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "GATE PASS — $total suite(s), $tests_run tests ($tests_skipped skipped) + 2 selfchecks + cross-module call signatures + undefined-name sweep"
else
  echo "GATE FAIL — see failures above"
fi
exit $fail
