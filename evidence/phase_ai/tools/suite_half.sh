#!/bin/bash
# © 2026 Omar Mokhtar. All rights reserved.
# The website's test modules without the browser ones, half $1 of $2 (0 or 1 of 2), verbose, into the log $3.
# Run from the repository root; PY is the web venv's python (deploy/requirements.txt, pyflakes, playwright).
# The modules in webapp/tests/solver_modules.txt are left out: they run one at a time with solver_serial.sh (two halves at once halve
# each channel solve's search, and their measured limits fail; evidence/phase_bl/channel_solver_ab.md).
PY=${PY:-python3}
mods=$(ls webapp/tests | grep -E "^test_.*\.py$" | grep -v playwright | sed 's/\.py$//' | grep -vxF -f <(grep '^test_' webapp/tests/solver_modules.txt) \
  | sed 's/^/webapp.tests./' | awk -v k="$1" -v n="$2" 'NR % n == k' | tr '\n' ' ')
$PY -m unittest -v $mods > "$3" 2>&1
echo "EXIT $?" >> "$3"
