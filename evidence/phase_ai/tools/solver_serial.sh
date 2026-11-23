#!/bin/bash
# © 2026 Omar Mokhtar. All rights reserved.
# The test modules of webapp/tests/solver_modules.txt, one at a time, verbose, into the log $1. Run it on its own, after the two halves of
# suite_half.sh have finished: a channel solve stops on the clock, so it must not share the processors with another one.
PY=${PY:-python3}
status=0
for m in $(grep '^test_' webapp/tests/solver_modules.txt); do
  $PY -m unittest -v webapp.tests.$m >> "$1" 2>&1 || status=1
done
echo "EXIT $status" >> "$1"
