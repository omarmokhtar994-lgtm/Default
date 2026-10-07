#!/usr/bin/env bash
# © 2026 Omar Mokhtar. All rights reserved.
#
# Team Scheduler: install a new package version on the server, keeping every
# user, run and result. Upload the new ZIP to the server, then:
#
#     sudo bash /opt/scheduler/package/deploy/update.sh ~/RC9_2_2_PRODUCTION_PACKAGE.zip
#
# Runs in flight are interrupted by the restart (each shows Interrupted with a
# Resume button), so the script asks first if any are running. The new
# package gets its own safety gate (the first run, or now if you say yes).
set -euo pipefail

APP_DIR=/opt/scheduler
DATA_DIR=/var/lib/scheduler
VENV="$APP_DIR/venv"
ZIP="${1:-}"

fail() { printf '\nUPDATE STOPPED: %s\n' "$*" >&2; exit 1; }
as_scheduler() { runuser -u scheduler -- env PYTHONPATH="$APP_DIR/package" PATH="$VENV/bin:$PATH" "$@"; }

[ "$(id -u)" -eq 0 ] || { echo "Run it with sudo:  sudo bash $0 <new package .zip>"; exit 1; }
[ -n "$ZIP" ] && [ -f "$ZIP" ] || fail "give the new package ZIP, for example: sudo bash $0 ~/RC9_2_2_PRODUCTION_PACKAGE.zip"
[ -x "$VENV/bin/python" ] || fail "Team Scheduler is not installed here yet: run deploy/install.sh from the package first."

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
unzip -q "$ZIP" -d "$WORK"
MANIFEST="$(find "$WORK" -maxdepth 3 -name MANIFEST.json | head -n 1)"
[ -n "$MANIFEST" ] || fail "MANIFEST.json not found in $ZIP: is that the production package ZIP?"
NEW="$(dirname "$MANIFEST")"
[ -d "$NEW/webapp" ] && [ -f "$NEW/deploy/requirements.txt" ] || fail "this package has no website (webapp/, deploy/)."

ACTIVE="$("$VENV/bin/python" - "$DATA_DIR/scheduler.db" <<'PY'
import sqlite3, sys
try:
    db = sqlite3.connect(sys.argv[1])
    rows = db.execute("select workbook, status from runs where status in ('GATE','RUNNING','SCORING')").fetchall()
except sqlite3.Error:
    rows = []
print("\n".join(f"  {w} ({s.lower()})" for w, s in rows))
PY
)"
if [ -n "$ACTIVE" ]; then
  echo "These runs are in progress and will be interrupted (they can be resumed afterwards):"
  echo "$ACTIVE"
  read -rp "Update now anyway? [y/N] " GO
  [ "${GO:-N}" = "y" ] || [ "${GO:-N}" = "Y" ] || fail "nothing changed; try again when the runs have finished."
fi

echo "==> Stopping the website"
systemctl stop scheduler-web
echo "==> Installing the new package (the old one is kept in $APP_DIR/package.previous)"
rm -rf "$APP_DIR/package.previous"
mv "$APP_DIR/package" "$APP_DIR/package.previous"
cp -a "$NEW" "$APP_DIR/package"
rm -rf "$APP_DIR/package/results"
chown -R scheduler:scheduler "$APP_DIR/package"
"$VENV/bin/pip" install --quiet -r "$APP_DIR/package/deploy/requirements.txt"
if ! "$VENV/bin/python" "$APP_DIR/package/tools/runtime_environment_check.py"; then
  echo "The new package's runtime check failed: putting the previous package back."
  rm -rf "$APP_DIR/package"
  mv "$APP_DIR/package.previous" "$APP_DIR/package"
  systemctl start scheduler-web
  fail "runtime check failed for the new package; the previous version is running again."
fi
sed -e "s|{{APP_DIR}}|$APP_DIR|g" -e "s|{{DATA_DIR}}|$DATA_DIR|g" \
    "$APP_DIR/package/deploy/scheduler-web.service" > /etc/systemd/system/scheduler-web.service
systemctl daemon-reload
systemctl start scheduler-web
echo "==> The website is running the new package."

if [ -t 0 ]; then
  read -rp "Run the new package's safety gate now (15-30 minutes)? [Y/n] " WARM
  if [ "${WARM:-Y}" != "n" ] && [ "${WARM:-Y}" != "N" ]; then
    as_scheduler python -m webapp.manage --data-dir "$DATA_DIR" check-package --package-root "$APP_DIR/package"
  fi
fi
