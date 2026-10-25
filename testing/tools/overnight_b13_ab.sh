#!/usr/bin/env bash
# Overnight B-13 measurement.
#
# BUDGET: 900s, not the production 3600s. Container restarts in this session are
# roughly hourly and have killed two 58-minute waves at ~75 minutes with nothing
# on disk. A 900s run completes a wave in about 16 minutes, which survives them.
# Both arms use the same budget, so the comparison stays valid; what it cannot do
# is transfer MAGNITUDES to production. The question B-13 asks is structural --
# does the control arm pin before_floor while the treatment arm ranges -- and a
# constraint that lets the solver degrade the before-state does so at any budget.
#
# B-13 is the only real defect among the behavioural findings, so the night is
# spent giving it statistical power rather than inventing work. Every run has a
# SKIP guard, so a container restart costs at most the wave in flight and this
# script can simply be relaunched.
#
# Wave order is by informativeness: AE_IT_B2B first, because that is where the
# degradation signature was clearest (before_floor pinned at 91 with the
# gameable bound active, ranging 91-98 without it).
set -u
SP=/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad
IN=$SP/ae/RC5_AE_REAL_SCHEDULES_QUICK_PACKAGE/inputs
CTL=$SP/rc5p/RC9_2_2_FIX_VALIDATION_RC5/engine/RUN_UNIVERSAL_PRODUCTION.py
TRT=$SP/b13_tree/engine/RUN_UNIVERSAL_PRODUCTION.py
OUT=$SP/b13ab; mkdir -p "$OUT"

run() {
  local arm=$1 runner=$2 case=$3 seed=$4
  local root="$OUT/${arm}_s${seed}"; mkdir -p "$root"
  if [ -f "$root/$case/UNIVERSAL_RUN_STATUS.json" ]; then echo "SKIP $arm $case s$seed"; return; fi
  # Reap a stale case lock. A container restart kills the solver without letting
  # it release RUN_LOCK.json, and the engine then correctly refuses to start
  # because the lock names a running case. Remove it ONLY when the pid it names
  # is actually gone, so a genuinely concurrent run is still protected.
  local lock="$root/$case/RUN_LOCK.json"
  if [ -f "$lock" ]; then
    local lpid
    lpid=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('pid',''))" "$lock" 2>/dev/null)
    if [ -n "$lpid" ] && ! kill -0 "$lpid" 2>/dev/null; then
      echo "REAPED stale lock $arm $case s$seed (dead pid $lpid)"
      rm -f "$lock"
    fi
  fi
  python3 "$runner" --input "$IN/$case.xlsx" --output-root "$root" \
    --schedule-id "$case" --stage FULL_SCHEDULE --mode QUICK \
    --time-limit 900 --num-workers 2 --solver-random-seed "$seed" --overwrite \
    > "$root/$case.log" 2>&1
  echo "DONE $arm $case s$seed rc=$? $(date -u +%H:%M:%S)"
}
pair() { run ctl "$CTL" "$1" "$2" & run b13 "$TRT" "$1" "$2" & }
wave() { echo "WAVE start $(date -u +%H:%M:%S): $1 s$2 + $3 s$4"; pair "$1" "$2"; pair "$3" "$4"; wait; echo "WAVE end $(date -u +%H:%M:%S)"; }

wave AE_IT_B2B    9000 AE_IT_B2B    9001
wave AE_IT_B2B    9002 AE_AR_Choice 9000
wave AE_AR_Choice 9001 AE_AR_Choice 9002
wave AE_IT_Choice 9000 AE_IT_Choice 9001
wave AE_IT_Choice 9002 AE_IT_B2B    9003
wave AE_IT_B2B    9004 AE_AR_Choice 9003
wave AE_AR_Choice 9004 AE_IT_Choice 9003
echo "OVERNIGHT COMPLETE $(date -u +%H:%M:%S)"
