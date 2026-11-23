#!/usr/bin/env bash
# © 2026 Omar Mokhtar. All rights reserved.
#
# Team Scheduler: make the installed code read-only for the website's account.
#
#     sudo bash deploy/seal_package.sh /opt/scheduler/package          seal it (root owns it; the scheduler account may read and run, not change)
#     sudo bash deploy/seal_package.sh --check /opt/scheduler/package  only look, change nothing; exit 1 and say why when it is not sealed
#
# Why: the website runs as the "scheduler" account. If that account owned its own code, anything that got into the website could rewrite it and the
# change would survive a restart. With root as the owner the account can still read and run everything and write only /var/lib/scheduler.
# Sealing also deletes every __pycache__ (compiled copies a writable install may have left): only the source is run, and the service is told
# not to write new ones (PYTHONDONTWRITEBYTECODE; see scheduler-web.service).
# Run by install.sh, update.sh and apply_patch.sh after they put code in place. It never follows a symbolic link and never touches /var/lib/scheduler.
set -euo pipefail

CHECK=0
if [ "${1:-}" = "--check" ]; then CHECK=1; shift; fi
PKG="${1:-}"
[ -n "$PKG" ] && [ -d "$PKG/webapp" ] && [ -f "$PKG/MANIFEST.json" ] || { echo "give the package folder (it has webapp/ and MANIFEST.json), for example /opt/scheduler/package" >&2; exit 2; }
PKG="$(cd "$PKG" && pwd -P)"
case "$PKG" in /|/var|/var/lib|/var/lib/scheduler|/home|/root|/etc|/usr|/opt) echo "refusing: $PKG is not a package folder" >&2; exit 2;; esac

problems=0
note() { printf '  %s\n' "$*"; problems=$((problems + 1)); }

look() {
  # anything not owned by root, or writable by its group or by anyone
  while IFS= read -r line; do note "$line"; done < <(find "$PKG" \( ! -user root -o ! -group root \) -printf 'not owned by root:root: %p (%u:%g)\n' 2>/dev/null | head -20)
  while IFS= read -r line; do note "$line"; done < <(find "$PKG" ! -type l -perm /022 -printf 'writable by group or others: %p (%m)\n' 2>/dev/null | head -20)
  # compiled copies
  while IFS= read -r line; do note "$line"; done < <(find "$PKG" -type d -name __pycache__ -printf 'compiled copies present: %p\n' 2>/dev/null | head -5)
  # a link that leaves the package could point at something the website account can change
  while IFS= read -r link; do
    target="$(readlink -f "$link" 2>/dev/null || true)"
    case "$target" in "$PKG"/*) ;; *) note "link leaves the package: $link -> ${target:-?}";; esac
  done < <(find "$PKG" -type l 2>/dev/null | head -50)
  # a file with several names could be one the website account can change under another name
  while IFS= read -r line; do note "$line"; done < <(find "$PKG" -type f -links +1 -printf 'file with more than one name: %p (%n names)\n' 2>/dev/null | head -10)
  # the website account must still be able to read what it runs
  if id -u scheduler >/dev/null 2>&1 && command -v runuser >/dev/null 2>&1; then
    for f in MANIFEST.json webapp/app.py runners/rc922_runner.py; do
      [ -e "$PKG/$f" ] || continue
      runuser -u scheduler -- test -r "$PKG/$f" || note "the scheduler account cannot read $PKG/$f"
    done
    runuser -u scheduler -- test -w "$PKG/webapp/app.py" && note "the scheduler account can still write $PKG/webapp/app.py" || true
  fi
}

if [ "$CHECK" = 1 ]; then
  look
  if [ "$problems" -eq 0 ]; then echo "SEALED: $PKG is owned by root and cannot be changed by the website's account."; exit 0; fi
  echo "NOT SEALED ($problems finding(s) above)."; exit 1
fi

[ "$(id -u)" -eq 0 ] || { echo "Run it with sudo." >&2; exit 1; }
find "$PKG" -type d -name __pycache__ -prune -exec rm -rf {} +
chown -R -h root:root "$PKG"
chmod -R go-w,a+rX "$PKG"
look
if [ "$problems" -eq 0 ]; then echo "SEALED: $PKG is owned by root; the website's account can read and run it, not change it."; exit 0; fi
echo "SEALING DID NOT TAKE EFFECT ($problems finding(s) above)." >&2; exit 1
