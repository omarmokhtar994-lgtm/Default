#!/usr/bin/env bash
# RC9.2.1 fast gate: pure selector/metric/parity guards. No solver, no workbook.
# Intended to run on every commit before any solver time is spent.
set -euo pipefail
PY="${PYTHON:-python3}"
cd "$(dirname "$0")"
fail=0
for suite in tests/test_rc9_2_1_*.py; do
  echo "── $suite"
  "$PY" "$suite" 2>&1 | tail -3 || fail=1
done
echo "── engine selfcheck"
"$PY" engine/_tools/l632_universal_scheduler.py --selfcheck >/dev/null || fail=1
echo "   engine selfcheck OK"
echo "── wrapper selfcheck"
"$PY" engine/RUN_UNIVERSAL_PRODUCTION.py --selfcheck >/dev/null || fail=1
echo "   wrapper selfcheck OK"
exit $fail
