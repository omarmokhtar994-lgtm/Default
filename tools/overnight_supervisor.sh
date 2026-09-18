#!/usr/bin/env bash
# Keep the overnight measurement alive across container restarts.
#
# Watches for the DRIVER, not for solver processes. The earlier version checked
# whether any solver was running, which meant a single orphaned run looked like
# healthy work and three supervisors accumulated without the driver ever
# starting. The driver is the thing that must exist.
SP=/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad
LOCKDIR="$SP/.supervisor.lock"
# one supervisor only
if ! mkdir "$LOCKDIR" 2>/dev/null; then exit 0; fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

while true; do
  grep -q "OVERNIGHT COMPLETE" "$SP/overnight.log" 2>/dev/null && break
  driver=0
  for p in $(pgrep -f "overnight.sh" 2>/dev/null); do
    ps -p "$p" -o args= 2>/dev/null | grep -q "^bash $SP/overnight.sh" && driver=1 && break
  done
  if [ "$driver" = "0" ]; then
    echo "SUPERVISOR relaunching driver $(date -u +%H:%M:%S)" >> "$SP/overnight.log"
    bash "$SP/overnight.sh" >> "$SP/overnight.log" 2>&1
  fi
  sleep 90
done
