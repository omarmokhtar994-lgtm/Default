#!/usr/bin/env bash
# © 2026 Omar Mokhtar. All rights reserved.
#
# Team Scheduler: put the previous version back (the one update.sh kept in /opt/scheduler/package.previous), exactly as it was, including its
# service file. Runs in flight are interrupted (each shows Interrupted with a Resume button). Users, runs and results are not touched.
#
#     sudo bash /opt/scheduler/package/deploy/rollback.sh
#
# This puts back the previous code AND the previous service file, so after rolling back past the read-only-code hardening the service can write
# its code again (as it could before). Update again to harden it. The version rolled back from is kept in /opt/scheduler/package.rolled-back.
set -euo pipefail

APP_DIR=/opt/scheduler
DATA_DIR=/var/lib/scheduler
VENV="$APP_DIR/venv"
fail() { printf '\nROLLBACK STOPPED: %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || { echo "Run it with sudo:  sudo bash $0"; exit 1; }
[ -d "$APP_DIR/package.previous/webapp" ] && [ -f "$APP_DIR/package.previous/deploy/scheduler-web.service" ] || fail "there is no previous version to go back to ($APP_DIR/package.previous)."
[ -d "$APP_DIR/package/webapp" ] || fail "$APP_DIR/package is not a package folder; nothing was changed."

ACTIVE="$("$VENV/bin/python" - "$DATA_DIR/scheduler.db" <<'PY'
import sqlite3, sys
try:
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    rows = db.execute("select workbook, status from runs where status in ('GATE','RUNNING','SCORING')").fetchall()
except sqlite3.Error:
    rows = []
print("\n".join(f"  {w} ({s.lower()})" for w, s in rows))
PY
)"
if [ -n "$ACTIVE" ]; then
  echo "These runs are in progress and will be interrupted (they can be resumed afterwards):"
  echo "$ACTIVE"
  read -rp "Roll back now anyway? [y/N] " GO
  [ "${GO:-N}" = "y" ] || [ "${GO:-N}" = "Y" ] || fail "nothing changed; try again when the runs have finished."
fi

echo "==> Stopping the website"
systemctl stop scheduler-web
rm -rf "$APP_DIR/package.rolled-back"
mv "$APP_DIR/package" "$APP_DIR/package.rolled-back"
mv "$APP_DIR/package.previous" "$APP_DIR/package"
sed -e "s|{{APP_DIR}}|$APP_DIR|g" -e "s|{{DATA_DIR}}|$DATA_DIR|g" \
    "$APP_DIR/package/deploy/scheduler-web.service" > /etc/systemd/system/scheduler-web.service
systemctl daemon-reload
systemctl start scheduler-web
echo "==> The previous version is running again. The one rolled back from is in $APP_DIR/package.rolled-back."
