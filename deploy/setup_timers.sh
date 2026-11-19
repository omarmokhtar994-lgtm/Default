#!/usr/bin/env bash
# © 2026 Omar Mokhtar. All rights reserved.
#
# Team Scheduler: put the nightly database copy and the 15-minute disk alert in place (Phase BT). Run by install.sh and update.sh;
# on its own, after a package or patch that brings it:
#
#     sudo bash /opt/scheduler/package/deploy/setup_timers.sh
#
# Safe to run again. It never overwrites /etc/scheduler/disk-alert.env (where you name the alert's group). See deploy/disk_alert_setup.md.
# DRY_RUN=1 prints the system commands instead of running them and writes the rendered files under DRY_ROOT (used by the tests).
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
PREFIX="${DRY_ROOT:-}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR=/opt/scheduler
DATA_DIR=/var/lib/scheduler
run() { if [ "$DRY_RUN" = 1 ]; then printf '[dry run] %s\n' "$*"; else "$@"; fi; }

if [ "$DRY_RUN" != 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "Run it with sudo:  sudo bash $0"
  exit 1
fi
for f in db_backup.py disk_alert.py scheduler-backup.service scheduler-backup.timer disk-alert.service disk-alert.timer; do
  [ -f "$SRC/$f" ] || { echo "TIMERS STOPPED: $SRC/$f is missing." >&2; exit 1; }
done

echo "==> Nightly database copy and disk alert"
run install -d -o root -g root -m 700 /var/backups/scheduler
mkdir -p "$PREFIX/etc/systemd/system"
for unit in scheduler-backup.service scheduler-backup.timer disk-alert.service disk-alert.timer; do
  sed -e "s|{{APP_DIR}}|$APP_DIR|g" -e "s|{{DATA_DIR}}|$DATA_DIR|g" "$SRC/$unit" > "$PREFIX/etc/systemd/system/$unit"
  [ "$DRY_RUN" = 1 ] || chmod 644 "$PREFIX/etc/systemd/system/$unit"
done
ENV_FILE="$PREFIX/etc/scheduler/disk-alert.env"
if [ ! -f "$ENV_FILE" ]; then
  mkdir -p "$(dirname "$ENV_FILE")"
  cat > "$ENV_FILE" <<'TXT'
# Team Scheduler disk alert settings (kept across updates). See /opt/scheduler/package/deploy/disk_alert_setup.md.
# To post alerts to a Teams or Slack group, remove the # below and type the LOB's name exactly as on the Notifications page.
# Never put a link here: the alert uses the link the website already keeps for that LOB.
# ALERT_UNIT=
# WARN=80
# CRIT=90
TXT
  [ "$DRY_RUN" = 1 ] || chmod 644 "$ENV_FILE"
fi
run systemctl daemon-reload
run systemctl enable --now scheduler-backup.timer disk-alert.timer
if [ "$DRY_RUN" != 1 ]; then
  echo "==> First copy now (the timer makes one every night)"
  systemctl start scheduler-backup.service || echo "The first copy failed: see  sudo journalctl -u scheduler-backup -n 20" >&2
  systemctl start disk-alert.service || echo "The disk alert failed: see  sudo journalctl -u disk-alert -n 20" >&2
  systemctl list-timers scheduler-backup.timer disk-alert.timer --no-pager || true
fi
