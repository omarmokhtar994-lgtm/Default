#!/bin/bash
# © 2026 Omar Mokhtar. All rights reserved.
# Apply a small website patch made by tools/make_patch.py (Phase AW) to the installed package.
#   sudo bash apply_patch.sh PATCH.zip          apply it
#   sudo bash apply_patch.sh --rollback DIR     put back the files a patch replaced (DIR is the backup it printed)
# It checks that the installed files are exactly the ones the patch was made for, backs up what it replaces, copies the new
# files, restarts the website and checks that it answers; if it does not, the old files are put back at once.
# For tests: APP_DIR changes where the package is, PATCH_NO_SERVICE=1 skips the restart and the check.
set -u
APP_DIR="${APP_DIR:-/opt/scheduler}"
PKG="$APP_DIR/package"
VENV="$APP_DIR/venv"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
fail() { echo "PATCH STOPPED: $1"; exit 1; }
restart() {
  [ "${PATCH_NO_SERVICE:-0}" = "1" ] && return 0
  systemctl restart scheduler-web || return 1
  for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/login || true)"
    [ "$code" = "200" ] && return 0
  done
  return 1
}
put_back() {  # $1 = backup folder
  while IFS= read -r rel; do
    if [ -f "$1/files/$rel" ]; then cp -p "$1/files/$rel" "$PKG/$rel"; fi
  done < "$1/replaced.txt"
  while IFS= read -r rel; do rm -f "$PKG/$rel"; done < "$1/added.txt"
}
if [ "${1:-}" = "--rollback" ]; then
  B="${2:-}"; [ -d "$B" ] || fail "give the backup folder the patch printed."
  put_back "$B"; restart || fail "the website did not answer after the rollback: ask for help."
  echo "Rolled back: the files are as they were before the patch."; exit 0
fi
[ "$(id -u)" -eq 0 ] || [ "${PATCH_NO_SERVICE:-0}" = "1" ] || fail "run it with sudo:  sudo bash $0 PATCH.zip"
ZIP="${1:-}"; [ -f "$ZIP" ] || fail "give the patch zip, for example: sudo bash $0 ~/PATCH.zip"
[ -d "$PKG/webapp" ] || fail "no installed website found under $PKG."
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT
unzip -q "$ZIP" -d "$WORK" || fail "this is not a patch zip."
[ -f "$WORK/PATCH.json" ] || fail "PATCH.json is missing: is this a patch from tools/make_patch.py?"
"$PY" - "$WORK" "$PKG" <<'PY' || exit 1
import hashlib, json, sys
from pathlib import Path
work, pkg = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((work / "PATCH.json").read_text())
bad = []
for f in meta["files"]:
    rel = f["path"]
    have = pkg / rel
    now = hashlib.sha256(have.read_bytes()).hexdigest() if have.is_file() else None
    if now not in (f["old_sha256"], f["new_sha256"]):
        bad.append(rel)
    if hashlib.sha256((work / "files" / rel).read_bytes()).hexdigest() != f["new_sha256"]:
        print("PATCH STOPPED: the patch file is damaged:", rel); sys.exit(1)
if bad:
    print("PATCH STOPPED: these installed files are not the ones this patch was made for (another patch or a different package?):")
    for b in bad[:10]:
        print("  ", b)
    sys.exit(1)
print("Checked:", len(meta["files"]), "files match the package this patch is for.")
PY
STAMP="$(date +%Y%m%d-%H%M%S)"
NAME="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['name'])" "$WORK/PATCH.json")"
B="$APP_DIR/patch-backups/$NAME-$STAMP"
mkdir -p "$B/files"; : > "$B/replaced.txt"; : > "$B/added.txt"
while IFS= read -r rel; do
  if [ -f "$PKG/$rel" ]; then
    mkdir -p "$B/files/$(dirname "$rel")"; cp -p "$PKG/$rel" "$B/files/$rel"; echo "$rel" >> "$B/replaced.txt"
  else
    echo "$rel" >> "$B/added.txt"
  fi
done < <("$PY" -c "import json,sys; [print(f['path']) for f in json.load(open(sys.argv[1]))['files']]" "$WORK/PATCH.json")
echo "Backup of the replaced files: $B"
while IFS= read -r rel; do
  mkdir -p "$PKG/$(dirname "$rel")"; cp -p "$WORK/files/$rel" "$PKG/$rel"
done < <("$PY" -c "import json,sys; [print(f['path']) for f in json.load(open(sys.argv[1]))['files']]" "$WORK/PATCH.json")
if [ "$(id -u)" -eq 0 ]; then chown -R scheduler:scheduler "$PKG" 2>/dev/null || true; fi
if ! "$PY" -m py_compile $(cd "$PKG" && ls webapp/*.py | sed "s|^|$PKG/|") 2>/dev/null; then
  put_back "$B"; fail "a patched file does not compile: the old files are back."
fi
if [ "${PATCH_NO_SERVICE:-0}" != "1" ] && grep -q '"deploy/requirements.txt"' "$WORK/PATCH.json"; then
  "$VENV/bin/pip" install --quiet -r "$PKG/deploy/requirements.txt" || true
fi
if ! restart; then
  echo "The website did not answer after the patch: putting the old files back."
  put_back "$B"; restart || true
  fail "patch undone; the website runs the files it had before."
fi
echo "The patch is applied and the website answers."
echo "To undo it later:  sudo bash $0 --rollback $B"
