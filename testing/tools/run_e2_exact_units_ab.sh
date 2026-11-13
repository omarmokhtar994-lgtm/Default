#!/usr/bin/env bash
# Phase E Task 2 A/B (evidence/phase_e/E_PLAN.md): every program x seed runs
# its OFF and ON workbooks side by side (2 runs at a time), production runner,
# QUICK 3,600 s, 2 workers. Resumable: a run with UNIVERSAL_RUN_STATUS.json is skipped.
#   tools/run_e2_exact_units_ab.sh <workbook dir> <runs dir>
set -u
WB="$1"; RUNS="$2"; mkdir -p "$RUNS"
ENGINE="$(cd "$(dirname "$0")/.." && pwd)/engine"
one() {
  local wb="$1" seed="$2" id; id="$(basename "$wb" .xlsx)_S$seed"
  if compgen -G "$RUNS/$id/UNIVERSAL_RUN_STATUS.json" >/dev/null; then echo "skip $id"; return 0; fi
  local t0; t0=$(date +%s)
  python3 "$ENGINE/RUN_UNIVERSAL_PRODUCTION.py" --input "$wb" --output-root "$RUNS" --schedule-id "$id" \
    --stage FULL_SCHEDULE --mode QUICK --time-limit 3600 --num-workers 2 --solver-random-seed "$seed" \
    --overwrite >"$RUNS/$id.log" 2>&1
  echo "$id rc=$? wall=$(( $(date +%s) - t0 ))s" | tee -a "$RUNS/DONE.txt"
}
for seed in 9000 9001; do
  for off in "$WB"/E2_*_OFF.xlsx; do
    on="${off%_OFF.xlsx}_ON.xlsx"
    one "$off" "$seed" & one "$on" "$seed" & wait
  done
done
