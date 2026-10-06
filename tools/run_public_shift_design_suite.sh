#!/usr/bin/env bash
# Run the public shift-design workbooks through the production runner at the
# production budget (QUICK 3,600 s, 2 workers, seed 9000), two at a time.
# Resumable: a case whose run folder already holds UNIVERSAL_RUN_STATUS.json is
# skipped, so a container restart only costs the runs in flight.
#   tools/run_public_shift_design_suite.sh <workbooks dir> <runs dir>
set -u
WB="$1"; RUNS="$2"; mkdir -p "$RUNS"
ENGINE="$(cd "$(dirname "$0")/.." && pwd)/engine"
run_case() {
  local wb="$1" id; id="$(basename "$wb" .xlsx)"
  if compgen -G "$RUNS/$id*/UNIVERSAL_RUN_STATUS.json" >/dev/null || compgen -G "$RUNS/$id*/*/UNIVERSAL_RUN_STATUS.json" >/dev/null; then
    echo "skip $id"; return 0; fi
  local t0; t0=$(date +%s)
  python3 "$ENGINE/RUN_UNIVERSAL_PRODUCTION.py" --input "$wb" --output-root "$RUNS" --schedule-id "$id" \
    --stage FULL_SCHEDULE --mode QUICK --time-limit 3600 --num-workers 2 --solver-random-seed 9000 \
    --overwrite >"$RUNS/$id.log" 2>&1
  echo "$id rc=$? wall=$(( $(date +%s) - t0 ))s" | tee -a "$RUNS/DONE.txt"
}
export -f run_case; export RUNS ENGINE
ls "$WB"/PUB_SDB_*.xlsx | xargs -P 2 -I{} bash -c 'run_case "$@"' _ {}
