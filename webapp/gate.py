# © 2026 Omar Mokhtar. All rights reserved.
"""The package's offline safety gate, run once per installed package version.

The production runner normally runs the full offline gate (run_tests.sh)
before every run: 15-30 minutes each time. The website runs it once for the
installed package (keyed by the sha256 of its MANIFEST.json), keeps a PASS
stamp, and only then lets runs pass --skip-guards. The runner's engine
fingerprint and runtime checks still run on every run (--skip-guards does not
skip them). A failed gate is never cached: the next run tries again, and no
run starts until it passes.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

GATE_TIMEOUT_SECONDS = 3600
_lock = threading.Lock()


class GateFailed(RuntimeError):
    pass


def manifest_sha256(package_root: Path) -> str:
    manifest = Path(package_root) / "MANIFEST.json"
    if not manifest.is_file():
        raise GateFailed(f"the package has no MANIFEST.json ({manifest})")
    return hashlib.sha256(manifest.read_bytes()).hexdigest()


def stamp_path(gate_dir: Path, package_root: Path) -> Path:
    return Path(gate_dir) / f"{manifest_sha256(package_root)}.json"


def passed_stamp(gate_dir: Path, package_root: Path) -> Optional[dict]:
    """The PASS stamp for the installed package, or None."""
    try:
        path = stamp_path(gate_dir, package_root)
        stamp = json.loads(path.read_text(encoding="utf-8"))
    except (GateFailed, OSError, ValueError):
        return None
    return stamp if stamp.get("status") == "PASS" else None


def ensure(package_root: Path, gate_dir: Path, gate_cmd: List[str]) -> dict:
    """Return the PASS stamp, running the gate first if this package has none.

    Raises GateFailed (with the gate's last lines) when the gate fails."""
    with _lock:
        stamp = passed_stamp(gate_dir, package_root)
        if stamp is not None:
            return stamp
        sha = manifest_sha256(package_root)
        gate_dir = Path(gate_dir)
        gate_dir.mkdir(parents=True, exist_ok=True)
        log = gate_dir / f"{sha}.log"
        try:
            proc = subprocess.run(gate_cmd, cwd=str(package_root), capture_output=True, text=True,
                                  timeout=GATE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            raise GateFailed(f"the safety gate did not finish within {GATE_TIMEOUT_SECONDS // 60} minutes")
        except OSError as exc:
            raise GateFailed(f"the safety gate could not start: {exc}")
        output = (proc.stdout or "") + (proc.stderr or "")
        log.write_text(output, encoding="utf-8")
        lines = [line for line in output.strip().splitlines() if line.strip()]
        summary = lines[-1] if lines else ""
        if proc.returncode != 0:
            tail = "\n".join(lines[-15:])
            raise GateFailed(f"the safety gate failed (exit code {proc.returncode}). "
                             f"Gate log: {log}\n{tail}")
        stamp = {"status": "PASS", "manifest_sha256": sha, "summary": summary,
                 "checked_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        stamp_path(gate_dir, package_root).write_text(json.dumps(stamp, indent=2), encoding="utf-8")
        return stamp
