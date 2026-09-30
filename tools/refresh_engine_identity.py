#!/usr/bin/env python3
"""Point the package manifest and the release identity at the engine on disk.

SCENARIOS.json's engine_sha256 is what the Colab runner verifies before it
spends solver time (verify_engine), and RELEASE_IDENTITY_RC9_2_2.json records
the engine a release claims. Both must name the engine that ships.

    python3 tools/refresh_engine_identity.py [--previous SHA256]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
MANIFEST = ROOT / "packages" / "rc9_2_2_production" / "SCENARIOS.json"
IDENTITY = ROOT / "engine" / "RELEASE_IDENTITY_RC9_2_2.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--previous", help="engine sha256 this release supersedes (kept if omitted)")
    args = ap.parse_args()
    digest = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST.read_text())
    manifest["engine_sha256"] = digest
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    identity = json.loads(IDENTITY.read_text())
    if args.previous:
        identity["previous_engine_file_sha256"] = args.previous
    identity["engine_file_sha256"] = digest
    identity["generated_utc"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    IDENTITY.write_text(json.dumps(identity, indent=2) + "\n")
    print(f"engine sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
