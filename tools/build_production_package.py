#!/usr/bin/env python3
"""Assemble the RC9.2.2 production package from the repository.

Every earlier build of this zip was hand-assembled from files that lived only
in a scratch directory, which meant it could not be rebuilt after a container
restart and nothing checked that what shipped matched what was committed.

This builds it from the repo, refuses to ship a package whose offline gate does
not pass, and prints the sha256 of the result so a run can be tied back to it.

    python3 tools/build_production_package.py [--output DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "RC9_2_2_PRODUCTION_PACKAGE"

# (source, destination) relative to the repo root and the package root.
TREES = [
    ("engine", "engine"),
    ("tools", "tools"),
    ("tests", "tests"),
    ("evidence", "evidence"),
    ("packages/rc9_2_2_production/inputs", "inputs"),
    ("packages/rc9_2_2_production/runners", "runners"),
]
FILES = [
    ("run_tests.sh", "run_tests.sh"),
    ("CODE_AUDIT.md", "CODE_AUDIT.md"),
    ("packages/rc9_2_2_production/README.md", "README.md"),
    ("packages/rc9_2_2_production/SCENARIOS.json", "SCENARIOS.json"),
]
# Build artifacts and caches. Shipping a .pyc compiled from a different engine
# is a way to run code nobody reviewed.
EXCLUDE = {"__pycache__", ".ruff_cache", ".pytest_cache", ".git"}


def _ignore(_dir: str, names: list[str]) -> set[str]:
    return {n for n in names if n in EXCLUDE or n.endswith(".pyc")}


def build(output_dir: Path) -> Path:
    staging = output_dir / NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    for src_rel, dst_rel in TREES:
        src = ROOT / src_rel
        if not src.is_dir():
            raise SystemExit(f"missing required tree: {src_rel}")
        shutil.copytree(src, staging / dst_rel, ignore=_ignore)
    for src_rel, dst_rel in FILES:
        src = ROOT / src_rel
        if not src.is_file():
            raise SystemExit(f"missing required file: {src_rel}")
        shutil.copy2(src, staging / dst_rel)
    (staging / "run_tests.sh").chmod(0o755)

    # A package that ships without its own gate passing inside it is a package
    # whose guards were never run against the files that actually shipped.
    print("── running the offline gate inside the staged package")
    gate = subprocess.run(["bash", "run_tests.sh"], cwd=staging,
                          capture_output=True, text=True)
    print(gate.stdout.strip().splitlines()[-1] if gate.stdout.strip() else "(no output)")
    if gate.returncode != 0:
        print(gate.stdout[-4000:], file=sys.stderr)
        raise SystemExit("refusing to package: the staged gate did not pass")

    manifest = {
        "package": NAME,
        "engine_sha256": hashlib.sha256(
            (staging / "engine" / "_tools" / "l632_universal_scheduler.py").read_bytes()
        ).hexdigest(),
        "inputs": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((staging / "inputs").glob("*.xlsx"))
        },
    }
    (staging / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # The gate above imports the engine and runs ruff, both of which write
    # caches back into the staging tree - after the copy that excluded them.
    # The first build of this script shipped 25 such entries while carrying a
    # comment explaining why it must not, so purge them here, where it is the
    # last thing that happens before the zip is written.
    for cache in sorted(staging.rglob("*")):
        if cache.is_dir() and cache.name in EXCLUDE:
            shutil.rmtree(cache, ignore_errors=True)
    leftover = [p for p in staging.rglob("*")
                if p.suffix == ".pyc" or p.name in EXCLUDE]
    if leftover:
        raise SystemExit(f"refusing to package: build artifacts remain: {leftover[:5]}")

    zip_path = output_dir / f"{NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(output_dir))
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default=str(ROOT / "dist"))
    args = ap.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    zip_path = build(out)
    digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    with zipfile.ZipFile(zip_path) as zf:
        count = len(zf.namelist())
    print(f"\n{zip_path}")
    print(f"  files  {count}")
    print(f"  size   {zip_path.stat().st_size / 1e6:.2f} MB")
    print(f"  sha256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
