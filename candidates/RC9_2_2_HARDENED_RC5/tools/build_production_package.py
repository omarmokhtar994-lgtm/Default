#!/usr/bin/env python3
"""Build hash-manifested RC9.2.2 production-candidate and validation ZIPs."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE = "L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2"
PRODUCTION_NAME = "RC9_2_2_MAX_COVERAGE_RC5_RELEASE_CANDIDATE"
VALIDATION_NAME = "RC9_2_2_FIX_VALIDATION_RC5"
EXCLUDED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ignored(_directory: str, names: list[str]) -> set[str]:
    return {
        name for name in names
        if name in EXCLUDED_NAMES
        or name.endswith((".pyc", ".inspect.ndjson"))
        or (name.startswith("RC921_") and name.endswith(".ipynb"))
    }


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=ignored)


def copy_file(relative: str, stage: Path) -> None:
    source = ROOT / relative
    if not source.is_file():
        raise RuntimeError(f"missing required file: {relative}")
    target = stage / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def verify_contract() -> None:
    manifest = json.loads((ROOT / "SCENARIOS.json").read_text(encoding="utf-8"))
    actual_engine = sha256(ROOT / "engine" / "_tools" / "l632_universal_scheduler.py")
    if actual_engine != manifest.get("engine_sha256"):
        raise RuntimeError("SCENARIOS.json engine hash does not match the engine")
    for row in manifest.get("scenarios", []):
        workbook = ROOT / "inputs" / row["input"]
        if not workbook.is_file() or sha256(workbook) != row.get("input_sha256"):
            raise RuntimeError(f"scenario input identity mismatch: {row.get('scenario_id')}")


def write_manifest(stage: Path, package_name: str, package_kind: str) -> None:
    records = []
    for path in sorted(value for value in stage.rglob("*") if value.is_file()):
        records.append({
            "path": path.relative_to(stage).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    manifest = {
        "schema_version": 1,
        "package": package_name,
        "package_kind": package_kind,
        "release": RELEASE,
        "release_status": "NO_GO_PENDING_RC5_TARGETED_RUNTIME_REVIEW",
        "production_ready": False,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_sha256": sha256(stage / "engine" / "_tools" / "l632_universal_scheduler.py"),
        "files": records,
    }
    (stage / "BUILD_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def zip_and_verify(stage: Path, target: Path) -> dict:
    temporary = target.with_suffix(target.suffix + ".tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(value for value in stage.rglob("*") if value.is_file()):
            archive.write(path, f"{stage.name}/{path.relative_to(stage).as_posix()}")
    with zipfile.ZipFile(temporary) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"corrupt ZIP member: {bad}")
        manifest_name = f"{stage.name}/BUILD_MANIFEST.json"
        manifest = json.loads(archive.read(manifest_name))
        for record in manifest["files"]:
            data = archive.read(f"{stage.name}/{record['path']}")
            if hashlib.sha256(data).hexdigest() != record["sha256"]:
                raise RuntimeError(f"ZIP manifest mismatch: {record['path']}")
    temporary.replace(target)
    return {
        "path": str(target), "sha256": sha256(target),
        "size_bytes": target.stat().st_size,
        "file_count": len(manifest["files"]) + 1, "zip_test": "PASS",
    }


def populate_production(stage: Path) -> None:
    for tree in ("engine", "runners", "tools", "inputs"):
        copy_tree(ROOT / tree, stage / tree)
    for relative in (
        "README.md", "CHANGELOG_RC9_2_2_HARDENED_RC2.md", "CHANGELOG_RC9_2_2_HARDENED_RC3.md", "CHANGELOG_RC9_2_2_HARDENED_RC4.md", "CHANGELOG_RC9_2_2_HARDENED_RC5.md",
        "FINAL_VALIDATION_AND_READINESS_REPORT.md", "FINAL_POST_FIX_AUDIT_RC4.md", "FINAL_POST_FIX_AUDIT_RC5.md", "TEST_PLAN_AND_RESULTS.md",
        "DEPENDENCY_INSTALLATION_RECORD.md", "RELEASE_STATUS.json", "SCENARIOS.json", "MANIFEST.json",
        "run_tests.sh", "validation_evidence/RC4_PREFLIGHT_MATRIX.json", "validation_evidence/RC4_RUNTIME_ENVIRONMENT_CHECK.json",
        "evidence/RC9_1_BASELINE.json", "evidence/RC9_1_BASELINE_PROVENANCE.txt",
    ):
        copy_file(relative, stage)


def populate_validation(stage: Path) -> None:
    for tree in ("engine", "runners", "tools", "tests", "inputs", "validation_evidence"):
        copy_tree(ROOT / tree, stage / tree)
    # The tooling-integrity tests exercise RC9.1 comparison behavior and need
    # the consolidated baseline as part of the validation package itself.
    for relative in ("evidence/RC9_1_BASELINE.json", "evidence/RC9_1_BASELINE_PROVENANCE.txt"):
        copy_file(relative, stage)
    for relative in (
        "README.md", "CHANGELOG_RC9_2_2_HARDENED_RC2.md", "CHANGELOG_RC9_2_2_HARDENED_RC3.md", "CHANGELOG_RC9_2_2_HARDENED_RC4.md", "CHANGELOG_RC9_2_2_HARDENED_RC5.md",
        "FINAL_VALIDATION_AND_READINESS_REPORT.md", "FINAL_POST_FIX_AUDIT_RC4.md", "FINAL_POST_FIX_AUDIT_RC5.md", "TEST_PLAN_AND_RESULTS.md",
        "DEPENDENCY_INSTALLATION_RECORD.md", "RELEASE_STATUS.json", "SCENARIOS.json", "MANIFEST.json",
        "run_tests.sh", "validation_evidence/RC4_PREFLIGHT_MATRIX.json", "validation_evidence/RC4_RUNTIME_ENVIRONMENT_CHECK.json",
    ):
        copy_file(relative, stage)


def build(output: Path) -> list[dict]:
    gate = subprocess.run(["bash", "run_tests.sh"], cwd=ROOT, capture_output=True, text=True)
    if gate.returncode:
        print(gate.stdout[-6000:], file=sys.stderr)
        print(gate.stderr[-6000:], file=sys.stderr)
        raise RuntimeError("offline gate failed; refusing to package")
    verify_contract()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name, kind, populate in (
        (PRODUCTION_NAME, "PRODUCTION_RELEASE_CANDIDATE", populate_production),
        (VALIDATION_NAME, "FIX_AND_REGRESSION_VALIDATION", populate_validation),
    ):
        with tempfile.TemporaryDirectory(prefix=f".{name}_", dir=output) as temp:
            stage = Path(temp) / name
            stage.mkdir()
            populate(stage)
            write_manifest(stage, name, kind)
            results.append(zip_and_verify(stage, output / f"{name}.zip"))
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    results = build(args.output.resolve())
    print(json.dumps({"status": "PASS", "artifacts": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
