#!/usr/bin/env python3
"""Create the three validated Phase C delivery packages for one scheduler case."""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

SCHEMA_VERSION = 2
DEFAULT_SINGLE_FILE_WARNING_BYTES = 8 * 1024 * 1024

PRODUCTION_PATTERNS = (
    "production/*BEST_BEFORE_BREAKS_SCHEDULE.xlsx",
    "production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
    "production/*MAX_TARGET_CANDIDATE.xlsx",
    "production/*MAX_FLOOR_CANDIDATE.xlsx",
    "production/PRODUCTION_ARTIFACT_MANIFEST.json",
    "*.l6_3_2_3_summary.csv",
    "PHASE_C_QUALITY_SUMMARY.json",
    "PHASE_C_QUALITY_SUMMARY.csv",
)
REVIEW_PATTERNS = (
    "*.l6_3_2_3_summary.csv",
    "*.l6_3_2_3_solver_audit.json",
    "*_CANDIDATE_LEADERBOARD.csv",
    "*_PARETO_EXPORT_MANIFEST.json",
    "production/PRODUCTION_ARTIFACT_MANIFEST.json",
    "PHASE_C_QUALITY_SUMMARY.json",
    "PHASE_C_QUALITY_SUMMARY.csv",
    "debug/RUN_IDENTITY.json",
    "debug/scheduler.log",
    "debug/TRANSACTION_LEDGER.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path, patterns: Sequence[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(files))


def file_record(root: Path, path: Path) -> dict:
    return {
        "path": str(path.relative_to(root)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_zip(root: Path, target: Path, files: Iterable[Path]) -> dict:
    selected = sorted(set(files))
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in selected:
            archive.write(path, arcname=str(path.relative_to(root)))
    with zipfile.ZipFile(target) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Corrupt ZIP member: {bad}")
    return {
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
        "file_count": len(selected),
        "zip_test": "PASS",
        "members": [file_record(root, path) for path in selected],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-root", type=Path, required=True)
    parser.add_argument(
        "--single-file-warning-bytes",
        type=int,
        default=DEFAULT_SINGLE_FILE_WARNING_BYTES,
    )
    args = parser.parse_args()

    root = args.case_root.resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    case = root.name
    production = collect(root, PRODUCTION_PATTERNS)
    review = collect(root, REVIEW_PATTERNS)
    debug = sorted(path for path in (root / "debug").rglob("*") if path.is_file()) if (root / "debug").exists() else []

    out = root / "packages"
    out.mkdir(exist_ok=True)
    records = {
        "01_PRODUCTION_ONLY": write_zip(root, out / f"{case}_01_PRODUCTION_ONLY.zip", production),
        "02_REVIEW_EVIDENCE": write_zip(root, out / f"{case}_02_REVIEW_EVIDENCE.zip", review),
        "03_FULL_DEBUG": write_zip(root, out / f"{case}_03_FULL_DEBUG.zip", debug),
    }

    warning_limit = max(1, int(args.single_file_warning_bytes))
    oversized = [
        file_record(root, path)
        for path in sorted(set(production + review + debug))
        if path.stat().st_size > warning_limit
    ]
    warnings = []
    if oversized:
        warnings.append({
            "code": "INDIVIDUAL_FILE_EXCEEDS_UPLOAD_WARNING_LIMIT",
            "warning_limit_bytes": warning_limit,
            "files": oversized,
            "action": "Keep raw evidence inside 03_FULL_DEBUG.zip or split the debug artifact before portal upload.",
        })

    required_roles = {
        "BEST_BEFORE_BREAKS_SCHEDULE": any("BEST_BEFORE_BREAKS_SCHEDULE" in path.name for path in production),
        "BEST_FINAL_AFTER_BREAKS_SCHEDULE": any("BEST_FINAL_AFTER_BREAKS_SCHEDULE" in path.name for path in production),
    }
    if not all(required_roles.values()):
        missing = [role for role, present in required_roles.items() if not present]
        raise RuntimeError(f"Missing required production artifact roles: {missing}")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "release_family": "R1.3.0-C_PRODUCTION_QUALITY",
        "case": case,
        "required_artifact_roles": required_roles,
        "packages": records,
        "warnings": warnings,
    }
    manifest_path = out / "PACKAGE_SPLIT_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
