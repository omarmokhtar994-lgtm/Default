#!/usr/bin/env bash
# © 2026 Omar Mokhtar. All rights reserved.
#
# Team Scheduler: one-command install on an Ubuntu server (Oracle Always Free
# ARM, Ubuntu 22.04 or 24.04). From the unzipped package folder:
#
#     sudo bash deploy/install.sh
#
# What it does: installs Python and Caddy, copies the package to
# /opt/scheduler, creates a Python environment with the pinned solver, opens
# ports 80 and 443 in the server's own firewall, starts the website behind
# HTTPS at https://<your-ip>.sslip.io, and asks you to choose the admin
# username and password (typed at the prompt, never stored in a file).
# Safe to run again: it keeps users, runs and results.
#
# DRY_RUN=1 prints the system commands instead of running them and writes the
# rendered service and Caddy files under DRY_ROOT (used by the tests).
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
PREFIX="${DRY_ROOT:-}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/opt/scheduler
DATA_DIR=/var/lib/scheduler
VENV="$APP_DIR/venv"

say()  { printf '\n==> %s\n' "$*"; }
fail() { printf '\nINSTALL STOPPED: %s\n' "$*" >&2; exit 1; }
run()  { if [ "$DRY_RUN" = 1 ]; then printf '[dry run] %s\n' "$*"; else "$@"; fi; }
as_scheduler() { run runuser -u scheduler -- env PYTHONPATH="$APP_DIR/package" PATH="$VENV/bin:$PATH" "$@"; }

if [ "$DRY_RUN" != 1 ] && [ "$(id -u)" -ne 0 ]; then
  echo "Run it with sudo:  sudo bash deploy/install.sh"
  exit 1
fi
[ -d "$SRC/webapp" ] && [ -f "$SRC/deploy/requirements.txt" ] || fail "run this from the unzipped package folder (webapp/ and deploy/ not found next to it)."
if [ ! -f "$SRC/MANIFEST.json" ]; then
  [ "$DRY_RUN" = 1 ] || fail "MANIFEST.json not found: use the production package ZIP, not a copy of the repository."
fi
grep -qx 'ortools==9.15.6755' "$SRC/deploy/requirements.txt" || fail "deploy/requirements.txt must pin ortools==9.15.6755."

# ---------------------------------------------------------------- packages
say "Installing system packages (Python, firewall tools, Caddy)"
export DEBIAN_FRONTEND=noninteractive
run apt-get update -y
run apt-get install -y python3 python3-venv python3-pip unzip curl gpg iptables-persistent netfilter-persistent \
    debian-keyring debian-archive-keyring apt-transport-https
if ! command -v caddy >/dev/null 2>&1 || [ "$DRY_RUN" = 1 ]; then
  # Caddy's own package repository (https://caddyserver.com/docs/install#debian-ubuntu-raspbian)
  run bash -c "curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg"
  run bash -c "curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list"
  run apt-get update -y
  run apt-get install -y caddy
fi
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || fail "Python 3.10 or newer is needed (Ubuntu 22.04 or 24.04)."

# ---------------------------------------------------------------- user, files
say "Creating the 'scheduler' service account and folders"
if ! id scheduler >/dev/null 2>&1 || [ "$DRY_RUN" = 1 ]; then
  run useradd --system --home-dir "$DATA_DIR" --shell /usr/sbin/nologin scheduler
fi
run install -d -o scheduler -g scheduler -m 750 "$DATA_DIR"
run install -d -m 755 "$APP_DIR"

say "Copying the package to $APP_DIR/package"
run rm -rf "$APP_DIR/package.new"
run cp -a "$SRC" "$APP_DIR/package.new"
run rm -rf "$APP_DIR/package.new/results"
if [ -d "$APP_DIR/package" ] || [ "$DRY_RUN" = 1 ]; then
  run rm -rf "$APP_DIR/package.previous"
  run mv "$APP_DIR/package" "$APP_DIR/package.previous"
fi
run mv "$APP_DIR/package.new" "$APP_DIR/package"
run chown -R scheduler:scheduler "$APP_DIR/package"

say "Creating the Python environment with the pinned solver (a few minutes)"
[ -x "$VENV/bin/python" ] && [ "$DRY_RUN" != 1 ] || run python3 -m venv "$VENV"
run "$VENV/bin/pip" install --quiet --upgrade pip
run "$VENV/bin/pip" install --quiet -r "$APP_DIR/package/deploy/requirements.txt"
run "$VENV/bin/python" "$APP_DIR/package/tools/runtime_environment_check.py"

# ---------------------------------------------------------------- web address
if [ -z "${DOMAIN:-}" ]; then
  IP="$(curl -4 -fsS --max-time 10 https://api.ipify.org || true)"
  [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "could not find this server's public IP address. Run again with DOMAIN=<ip-with-dashes>.sslip.io"
  DOMAIN="${IP//./-}.sslip.io"
fi
say "Web address: https://$DOMAIN"

render() {  # render <template> <target>
  local target="$PREFIX$2"
  mkdir -p "$(dirname "$target")"
  sed -e "s|{{APP_DIR}}|$APP_DIR|g" -e "s|{{DATA_DIR}}|$DATA_DIR|g" -e "s|{{DOMAIN}}|$DOMAIN|g" "$1" > "$target"
}
render "$SRC/deploy/scheduler-web.service" /etc/systemd/system/scheduler-web.service
render "$SRC/deploy/Caddyfile.template" /etc/caddy/Caddyfile

# ---------------------------------------------------------------- firewall
say "Opening ports 80 and 443 in the server firewall (nothing else)"
# Oracle's Ubuntu images end the INPUT chain with REJECT, so these go first.
iptables -C INPUT -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null && [ "$DRY_RUN" != 1 ] \
  || run iptables -I INPUT 1 -p tcp --dport 80 -m conntrack --ctstate NEW -j ACCEPT
iptables -C INPUT -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT 2>/dev/null && [ "$DRY_RUN" != 1 ] \
  || run iptables -I INPUT 1 -p tcp --dport 443 -m conntrack --ctstate NEW -j ACCEPT
run netfilter-persistent save

# ---------------------------------------------------------------- admin
if [ "$DRY_RUN" = 1 ] || ! runuser -u scheduler -- env PYTHONPATH="$APP_DIR/package" "$VENV/bin/python" -m webapp.manage --data-dir "$DATA_DIR" has-admin; then
  say "Create your admin account"
  ADMIN_USER="${ADMIN_USER:-}"
  ADMIN_NAME="${ADMIN_NAME:-}"
  [ -n "$ADMIN_USER" ] || read -rp "Admin username (for example omar): " ADMIN_USER
  [ -n "$ADMIN_NAME" ] || read -rp "Your name as the team should see it: " ADMIN_NAME
  echo "Now type the admin password twice (at least 10 characters; it is not shown)."
  as_scheduler python -m webapp.manage --data-dir "$DATA_DIR" create-admin "$ADMIN_USER" --name "$ADMIN_NAME"
else
  say "An admin account already exists: keeping it"
fi

# ---------------------------------------------------------------- start
say "Starting the website"
run systemctl daemon-reload
run systemctl enable --now scheduler-web
run systemctl restart scheduler-web
run systemctl enable caddy
run systemctl restart caddy

if [ "$DRY_RUN" != 1 ] && [ -t 0 ]; then
  read -rp "Run the safety gate now so the first run starts straight away? Takes 15-30 minutes. [Y/n] " WARM
  if [ "${WARM:-Y}" != "n" ] && [ "${WARM:-Y}" != "N" ]; then
    as_scheduler python -m webapp.manage --data-dir "$DATA_DIR" check-package --package-root "$APP_DIR/package"
  fi
fi

cat <<EOF

Team Scheduler is installed.

  Open:     https://$DOMAIN
  Sign in:  with the admin username and password you just chose.
  Add your team on the People page; each person chooses their own password
  at first sign-in. Results are kept 30 days.

If the page does not open, check that ports 80 and 443 are open in the
Oracle Cloud console (Networking > your VCN > Security List > Ingress rules):
see deploy/ORACLE_SETUP_GUIDE.md.
EOF
