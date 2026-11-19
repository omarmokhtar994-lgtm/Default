#!/usr/bin/env python3
"""Create the three validated Phase C delivery packages for one scheduler case."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
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
    "INDEPENDENT_VALIDATION.json",
    "INDEPENDENT_VALIDATION.csv",
    "UNIVERSAL_RUN_STATUS.json",
    "UNIVERSAL_RUN_IDENTITY.json",
    "input_snapshot/*.xlsx",
)
REVIEW_PATTERNS = (
    "*.l6_3_2_3_summary.csv",
    "*.l6_3_2_3_solver_audit.json",
    "*_CANDIDATE_LEADERBOARD.csv",
    "*_PARETO_EXPORT_MANIFEST.json",
    "production/PRODUCTION_ARTIFACT_MANIFEST.json",
    "PHASE_C_QUALITY_SUMMARY.json",
    "PHASE_C_QUALITY_SUMMARY.csv",
    "INDEPENDENT_VALIDATION.json",
    "INDEPENDENT_VALIDATION.csv",
    "UNIVERSAL_RUN_IDENTITY.json",
    "UNIVERSAL_RUN_STATUS.json",
    "input_snapshot/*.xlsx",
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


def write_zip(root: Path, target: Path, files: Iterable[Path], *, package_set_id: str, component: str) -> dict:
    selected = sorted(set(files))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.publishing.{os.getpid()}")
    members = [file_record(root, path) for path in selected]
    component_manifest = {
        "schema_version": 1,
        "package_set_id": package_set_id,
        "component": component,
        "case": root.name,
        "members": members,
        "purpose": "Self-contained component manifest. Verify this ZIP before combining it with sibling components.",
    }
    component_bytes = (json.dumps(component_manifest, indent=2) + "\n").encode("utf-8")
    try:
        with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in selected:
                archive.write(path, arcname=str(path.relative_to(root)))
            archive.writestr("COMPONENT_MANIFEST.json", component_bytes)
        with zipfile.ZipFile(temporary) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"Corrupt ZIP member: {bad}")
        # Replace only after the complete archive has been written and tested.
        # A Colab disconnect or packager exception therefore cannot leave a
        # truncated file at the final production filename.
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "path": str(target),
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
        "file_count": len(selected) + 1,
        "zip_test": "PASS",
        "members": members + [{
            "path": "COMPONENT_MANIFEST.json",
            "size_bytes": len(component_bytes),
            "sha256": hashlib.sha256(component_bytes).hexdigest(),
        }],
        "package_set_id": package_set_id,
        "component": component,
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

    # Check required roles BEFORE writing anything. This check used to run after
    # the three ZIPs were already on disk, so a case missing a required schedule
    # still produced a *_01_PRODUCTION_ONLY.zip - just with no manifest beside
    # it. Anything downstream that globs for the production ZIP would collect an
    # incomplete package with nothing to warn it.
    required_roles = {
        "BEST_BEFORE_BREAKS_SCHEDULE": any("BEST_BEFORE_BREAKS_SCHEDULE" in path.name for path in production),
        "BEST_FINAL_AFTER_BREAKS_SCHEDULE": any("BEST_FINAL_AFTER_BREAKS_SCHEDULE" in path.name for path in production),
    }
    if not all(required_roles.values()):
        missing = [role for role, present in required_roles.items() if not present]
        raise RuntimeError(f"Missing required production artifact roles: {missing}")

    manifest_path = root / "production" / "PRODUCTION_ARTIFACT_MANIFEST.json"
    validation_path = root / "INDEPENDENT_VALIDATION.json"
    if not manifest_path.is_file() or not validation_path.is_file():
        raise RuntimeError("Production manifest and independent validation evidence are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    legacy_clean_seal = (
        manifest.get("production_ready") is True
        and manifest.get("approval_status") == "APPROVED_AUTOMATED_RELEASE_GATES"
    )
    hard_gate_seal = manifest.get("automated_hard_gates_passed") is True
    if not (legacy_clean_seal or hard_gate_seal):
        raise RuntimeError("Production manifest has not been sealed by the release pipeline")
    if validation.get("status") != "PASS" or int(validation.get("hard_fail_count", 1) or 0) != 0:
        raise RuntimeError("Independent validation is not a clean PASS")
    final_record = (manifest.get("two_artifact_contract") or {}).get("BEST_FINAL_AFTER_BREAKS_SCHEDULE") or {}
    final_path = root / str(final_record.get("path", ""))
    final_hash = sha256(final_path) if final_path.is_file() else None
    if (
        not final_path.is_file()
        or final_hash != validation.get("output_sha256")
        or final_hash != final_record.get("sha256")
    ):
        raise RuntimeError("Validated final workbook identity does not match the production manifest")
    input_snapshots = [path for path in production if "input_snapshot" in path.parts and path.suffix.lower()==".xlsx"]
    if len(input_snapshots)!=1 or sha256(input_snapshots[0])!=validation.get("input_sha256"):
        raise RuntimeError("Validated input identity does not match the packaged input snapshot")
    if (manifest.get("solver") or {}).get("engine_sha256")!=validation.get("engine_sha256"):
        raise RuntimeError("Validated engine identity does not match the production manifest")

    warning_limit = max(1, int(args.single_file_warning_bytes))
    oversized = [
        file_record(root, path)
        for path in sorted(set(production + review + debug))
        if path.stat().st_size > warning_limit
    ]
    warnings = []
    if hard_gate_seal and not legacy_clean_seal:
        warnings.append({
            "code": "AUTOMATED_HARD_GATES_PASSED_HUMAN_APPROVAL_PENDING",
            "release_disposition": manifest.get("release_disposition", "REVIEW_ONLY"),
            "quality_gate_status": manifest.get("quality_gate_status", "NOT_EVALUATED"),
            "action": "Do not use the production ZIP operationally until the quality gate and human approval requirements are satisfied.",
        })
    if manifest.get("quality_gate_status") == "FAIL":
        warnings.append({
            "code": "PRODUCTION_QUALITY_GATE_BLOCKED",
            "action": "Retain the generated schedule for review; remediate the quality failures or obtain documented approval.",
        })
    if oversized:
        warnings.append({
            "code": "INDIVIDUAL_FILE_EXCEEDS_UPLOAD_WARNING_LIMIT",
            "warning_limit_bytes": warning_limit,
            "files": oversized,
            "action": "Keep raw evidence inside 03_FULL_DEBUG.zip or split the debug artifact before portal upload.",
        })

    out = root / "packages"
    out.mkdir(exist_ok=True)
    generated_utc = datetime.now(timezone.utc).isoformat()
    package_set_id = hashlib.sha256(f"{case}|{generated_utc}|{os.getpid()}".encode()).hexdigest()[:20]
    # Build and verify the entire set in a private directory. The final
    # aggregate manifest is installed last; a disconnect cannot leave a set
    # that is presented as complete without its completion record.
    with tempfile.TemporaryDirectory(prefix=f".{case}_package_set_", dir=out) as staging:
        staging_path = Path(staging)
        records = {
            "01_PRODUCTION_ONLY": write_zip(root, staging_path / f"{case}_01_PRODUCTION_ONLY.zip", production, package_set_id=package_set_id, component="01_PRODUCTION_ONLY"),
            "02_REVIEW_EVIDENCE": write_zip(root, staging_path / f"{case}_02_REVIEW_EVIDENCE.zip", review, package_set_id=package_set_id, component="02_REVIEW_EVIDENCE"),
            "03_FULL_DEBUG": write_zip(root, staging_path / f"{case}_03_FULL_DEBUG.zip", debug, package_set_id=package_set_id, component="03_FULL_DEBUG"),
        }
        for component, record in records.items():
            final_path = out / Path(record["path"]).name
            record["path"] = str(final_path)
            # Verify the staged file one more time before it becomes visible.
            with zipfile.ZipFile(staging_path / Path(record["path"]).name) as archive:
                if archive.testzip():
                    raise RuntimeError(f"Corrupt staged ZIP: {component}")
            (staging_path / Path(record["path"]).name).replace(final_path)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": generated_utc,
            "release_family": "R1.3.0-C_PRODUCTION_QUALITY",
            "case": case,
            "package_set_id": package_set_id,
            "completion_status": "COMPLETE",
            "required_artifact_roles": required_roles,
            "release_disposition": manifest.get("release_disposition", "LEGACY_CLEAN_RELEASE"),
            "production_ready": bool(manifest.get("production_ready") is True),
            "quality_gate_status": manifest.get("quality_gate_status", "NOT_EVALUATED"),
            "packages": records,
            "warnings": warnings,
        }
        manifest_path = out / "PACKAGE_SPLIT_MANIFEST.json"
        manifest_temporary = staging_path / "PACKAGE_SPLIT_MANIFEST.json"
        manifest_temporary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        manifest_temporary.replace(manifest_path)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
