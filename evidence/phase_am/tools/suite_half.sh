#!/bin/bash
# © 2026 Omar Mokhtar. All rights reserved.
# The website's test modules without the browser ones, half $1 of $2 (0 or 1 of 2), verbose, into the log $3.
# Run from the repository root; PY is the web venv's python (deploy/requirements.txt, pyflakes, playwright).
PY=${PY:-python3}
mods=$(ls webapp/tests | grep -E "^test_.*\.py$" | grep -v playwright | sed 's/\.py$//; s/^/webapp.tests./' | awk -v k="$1" -v n="$2" 'NR % n == k' | tr '\n' ' ')
$PY -m unittest -v $mods > "$3" 2>&1
echo "EXIT $?" >> "$3"
