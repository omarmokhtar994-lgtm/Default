# © 2026 Omar Mokhtar. All rights reserved.
"""Nightly copy of the website's database (Phase BT, owner, 2026-11-19: "go ahead with both, no off-server copy").

Run each night by scheduler-backup.timer (see disk_alert_setup.md), as root. It copies scheduler.db with SQLite's own backup, which is
consistent while the website is running, checks the copy (integrity_check), compresses it and keeps it in BACKUP_DIR as
scheduler-YYYY-MM-DD-HHMMSS.db.gz (folder 700, file 600: the database holds the Teams and Slack group links). Then it keeps the newest KEEP
copies and deletes older ones of that name only. Fail-closed: a missing or damaged database, or too little free space, stops it with a message
and exit 1, and then no older copy is deleted. The copies stay on this server: they protect against a bad change or a damaged database, not
against losing the server.
Settings (environment, all optional): SCHEDULER_DATA_DIR (/var/lib/scheduler), BACKUP_DIR (/var/backups/scheduler), KEEP (14)."""
from __future__ import annotations

import gzip
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

NAME = re.compile(r"^scheduler-\d{4}-\d{2}-\d{2}-\d{6}\.db\.gz$")


class BackupError(Exception):
    pass


def backup(db: Path, dest: Path, now: datetime) -> Path:
    """Copy ``db`` into ``dest`` as a checked, compressed file; return its path. Raises BackupError and leaves nothing behind on failure."""
    if not db.is_file():
        raise BackupError(f"the database was not found at {db}")
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(dest, 0o700)
    size = db.stat().st_size
    free = shutil.disk_usage(dest).free
    if free < 2 * size + 512 * 2 ** 20:            # the plain copy and the compressed one, and room left for the website
        raise BackupError(f"only {free / 2 ** 20:.0f} MB free: a copy of the {size / 2 ** 20:.0f} MB database would leave the website too little")
    target = dest / f"scheduler-{now:%Y-%m-%d-%H%M%S}.db.gz"
    with tempfile.TemporaryDirectory(dir=dest, prefix=".work-") as work:
        plain = Path(work) / "copy.db"
        try:
            src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            out = sqlite3.connect(plain)
            try:
                src.backup(out)
                check = out.execute("pragma integrity_check").fetchone()[0]
            finally:
                out.close()
                src.close()
        except sqlite3.Error as exc:
            raise BackupError(f"the database could not be read ({exc})") from None
        if check != "ok":
            raise BackupError(f"the copy failed its integrity check ({check})")
        packed = Path(work) / target.name
        with open(plain, "rb") as fin, gzip.open(packed, "wb", compresslevel=6) as fout:
            shutil.copyfileobj(fin, fout)
        os.chmod(packed, 0o600)
        os.replace(packed, target)
    return target


def prune(dest: Path, keep: int) -> List[Path]:
    """Delete all but the newest ``keep`` copies made by ``backup``; other files in the folder are left alone. Returns what was deleted."""
    if keep < 1:
        raise ValueError("keep at least one copy")
    copies = sorted(p for p in dest.iterdir() if p.is_file() and NAME.match(p.name))
    gone = copies[:-keep]
    for p in gone:
        p.unlink()
    return gone


def main(argv: Optional[list] = None) -> int:
    data_dir = Path(os.environ.get("SCHEDULER_DATA_DIR", "/var/lib/scheduler"))
    dest = Path(os.environ.get("BACKUP_DIR", "/var/backups/scheduler"))
    try:
        keep = int(os.environ.get("KEEP", "14"))
        if keep < 1:
            raise ValueError
    except ValueError:
        print("KEEP is the number of nightly copies to keep, a whole number of 1 or more.", flush=True)
        return 2
    try:
        made = backup(data_dir / "scheduler.db", dest, datetime.now())
    except (BackupError, OSError) as exc:
        print(f"BACKUP FAILED: {exc}. No older copy was deleted.", flush=True)
        return 1
    gone = prune(dest, keep)
    print(f"backup made: {made} ({made.stat().st_size / 2 ** 20:.1f} MB); {len(gone)} older copies deleted, newest {keep} kept", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
