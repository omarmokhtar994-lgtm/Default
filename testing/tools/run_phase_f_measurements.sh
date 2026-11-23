#!/usr/bin/env bash
# Phase F measurements (evidence/phase_f/F_PLAN.md): pairs side by side,
# production runner, QUICK 3,600 s, 2 workers, seed 9000. Resumable.
#   tools/run_phase_f_measurements.sh <workbook dir> <runs dir>
set -u
WB="$1"; RUNS="$2"; mkdir -p "$RUNS"
ENGINE="$(cd "$(dirname "$0")/.." && pwd)/engine"
one() {
  local id="$1"
  if compgen -G "$RUNS/$id/UNIVERSAL_RUN_STATUS.json" >/dev/null; then echo "skip $id"; return 0; fi
  local t0; t0=$(date +%s)
  python3 "$ENGINE/RUN_UNIVERSAL_PRODUCTION.py" --input "$WB/$id.xlsx" --output-root "$RUNS" --schedule-id "$id" \
    --stage FULL_SCHEDULE --mode QUICK --time-limit 3600 --num-workers 2 --solver-random-seed 9000 \
    --overwrite >"$RUNS/$id.log" 2>&1
  echo "$id rc=$? wall=$(( $(date +%s) - t0 ))s" | tee -a "$RUNS/DONE.txt"
}
for pair in "F_CHAT_CTRL F_CHAT_HALF" "F_VOICE_CTRL F_VOICE_HALF" "F_NMGENSP_CTRL F_NMGENSP_HALF" \
            "F_AEITB2B_CTRL F_AEITB2B_RATIO40" "F_CHAT_RATIO40 F_CHAT_CTRL2"; do
  set -- $pair
  one "$1" & one "$2" & wait
done
