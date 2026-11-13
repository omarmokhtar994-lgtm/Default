# © 2026 Omar Mokhtar. All rights reserved.
"""Disk alert for the Team Scheduler server (owner, 2026-11-04: the disk filled up, the website could not write to its database, nobody could sign in).

Run every 15 minutes by a systemd timer (see disk_alert_setup.md). It reads how full the disk under the website's data folder is and:
  * always writes one line to the system journal (``journalctl -u disk-alert``);
  * when a group is named (``ALERT_UNIT`` = a LOB's name as on the Notifications page), also posts a short message to that LOB's saved group with the website's own
    sender, so no link is ever typed, printed or logged here. It posts when the level rises (80 % warning, 90 % critical), again every 6 hours while critical and every
    24 hours while a warning, and once when the disk is back to normal. A failed post is tried again at the next run.
Settings (environment, all optional): DISK_PATH, WARN (80), CRIT (90), ALERT_UNIT, SCHEDULER_DATA_DIR, ALERT_STATE.
``python disk_alert.py --test`` posts a test message to the named group whatever the level.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

REPEAT = {"warn": 24 * 3600, "crit": 6 * 3600}
CLEAR_MARGIN = 3          # the disk must be this many points under the warning level before it counts as normal again


def level_of(pct: float, warn: float, crit: float) -> str:
    return "crit" if pct >= crit else "warn" if pct >= warn else "ok"


def decide(pct: float, state: Dict[str, Any], now: float, warn: float = 80.0, crit: float = 90.0) -> Tuple[Optional[str], Dict[str, Any]]:
    """(what to say or None, the state to keep if it is said). What is said: "rise", "repeat", "improve" or "clear"."""
    level = level_of(pct, warn, crit)
    before = state.get("level", "ok")
    at = float(state.get("at") or 0)
    if level == "ok" and before != "ok" and pct >= warn - CLEAR_MARGIN:
        level = "warn"                                            # a little under the line is not normal yet: stay a warning, say nothing new
        return None, {"level": before if before == "warn" else "warn", "at": at}
    rank = {"ok": 0, "warn": 1, "crit": 2}
    if rank[level] > rank[before]:
        return "rise", {"level": level, "at": now}
    if rank[level] < rank[before]:
        return ("clear" if level == "ok" else "improve"), {"level": level, "at": now}
    if level != "ok" and now - at >= REPEAT[level]:
        return "repeat", {"level": level, "at": now}
    return None, {"level": level, "at": at}


def words(what: str, pct: float, used_gb: float, total_gb: float) -> Tuple[str, str]:
    free = total_gb - used_gb
    base = f"The disk is {pct:.0f}% full ({used_gb:.0f} GB of {total_gb:.0f} GB used, {free:.0f} GB free)."
    if what == "test":
        return "Team Scheduler server: disk alert test", base + " This is a test message: no action is needed."
    if what == "clear":
        return "Team Scheduler server: disk back to normal", base
    if pct >= 90:
        return "Team Scheduler server: disk almost full", base + " Below about 1 GB free the website cannot save anything and nobody can sign in. Free space now (old run files, old backups)."
    return "Team Scheduler server: disk filling up", base + " Free some space soon (old run files, old backups) so it does not reach 100%."


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    path = os.environ.get("DISK_PATH", "/var/lib/scheduler")
    warn, crit = float(os.environ.get("WARN", "80")), float(os.environ.get("CRIT", "90"))
    unit = os.environ.get("ALERT_UNIT", "").strip()
    data_dir = Path(os.environ.get("SCHEDULER_DATA_DIR", "/var/lib/scheduler"))
    state_file = Path(os.environ.get("ALERT_STATE", str(data_dir / ".disk_alert_state.json")))
    usage = shutil.disk_usage(path)
    pct, used_gb, total_gb = 100.0 * usage.used / usage.total, usage.used / 2 ** 30, usage.total / 2 ** 30
    try:
        state = json.loads(state_file.read_text())
    except (OSError, ValueError):
        state = {}
    now = time.time()
    if "--test" in argv:
        what, new = "test", state
    else:
        what, new = decide(pct, state, now, warn, crit)
    print(f"disk {pct:.0f}% used ({used_gb:.0f} of {total_gb:.0f} GB), level {level_of(pct, warn, crit)}, {'saying ' + what if what else 'nothing new to say'}", flush=True)
    if what is None:
        return 0
    if not unit:
        print("ALERT_UNIT is not set, so only this journal line is written.", flush=True)
        new_ok = True
    else:
        new_ok = post(unit, data_dir, *words(what, pct, used_gb, total_gb))
    if new_ok and "--test" not in argv:
        try:
            state_file.write_text(json.dumps(new))
        except OSError as exc:
            print(f"could not keep the state ({exc.__class__.__name__}); it will say it again next time", flush=True)
    return 0 if new_ok else 1


def post(unit: str, data_dir: Path, title: str, text: str) -> bool:
    """Post to the LOB's saved group with the website's own sender. The link is read here and never printed."""
    import sqlite3
    from webapp import notify as N
    try:                                      # read only: opening the website's own store may write, and a full disk is when this has to work
        db = sqlite3.connect(f"file:{data_dir / 'scheduler.db'}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        row = db.execute("select * from notify_settings where unit = ?", (unit,)).fetchone()
        db.close()
    except sqlite3.Error as exc:
        print(f"could not read the group settings ({exc.__class__.__name__}): nothing posted", flush=True)
        return False
    settings = dict(row) if row else None
    if not settings or not settings.get("link"):
        print(f"no group link is saved for '{unit}': nothing posted", flush=True)
        return False
    try:
        service = N.check_link(settings["link"])
    except ValueError:
        print("the saved group link is not a Teams or Slack link: nothing posted", flush=True)
        return False
    ok, code = N.post_json(settings["link"], N.body_for(service, N.Post(title=title, footer=text), settings["link"]))
    print("posted to the group" if ok else f"the group did not accept the post (code {code})", flush=True)
    return bool(ok)


if __name__ == "__main__":
    raise SystemExit(main())
