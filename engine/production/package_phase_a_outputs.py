#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, zipfile
from datetime import datetime, timezone
from pathlib import Path

PRODUCTION_PATTERNS = (
    "production/*BEST_BEFORE_BREAKS_SCHEDULE.xlsx",
    "production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx",
    "production/PRODUCTION_ARTIFACT_MANIFEST.json",
    "*.l6_3_2_3_summary.csv",
)
REVIEW_PATTERNS = (
    "*.l6_3_2_3_summary.csv", "*.l6_3_2_3_solver_audit.json",
    "*_CANDIDATE_LEADERBOARD.csv", "*_PARETO_EXPORT_MANIFEST.json",
    "production/PRODUCTION_ARTIFACT_MANIFEST.json", "debug/RUN_IDENTITY.json", "debug/scheduler.log",
)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()

def collect(root: Path, patterns) -> list[Path]:
    files=[]
    for pattern in patterns: files.extend(p for p in root.glob(pattern) if p.is_file())
    return sorted(set(files))

def write_zip(root: Path, target: Path, files: list[Path]) -> dict:
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files: zf.write(path, arcname=str(path.relative_to(root)))
    with zipfile.ZipFile(target) as zf:
        bad=zf.testzip()
        if bad: raise RuntimeError(f'Corrupt ZIP member: {bad}')
    return {'path':str(target),'size_bytes':target.stat().st_size,'sha256':sha256(target),'file_count':len(files),'zip_test':'PASS'}

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--case-root', type=Path, required=True); args=ap.parse_args()
    root=args.case_root.resolve(); case=root.name
    production=collect(root, PRODUCTION_PATTERNS)
    review=collect(root, REVIEW_PATTERNS)
    debug=sorted(p for p in (root/'debug').rglob('*') if p.is_file()) if (root/'debug').exists() else []
    out=root/'packages'; out.mkdir(exist_ok=True)
    records={
      '01_PRODUCTION_ONLY':write_zip(root,out/f'{case}_01_PRODUCTION_ONLY.zip',production),
      '02_REVIEW_EVIDENCE':write_zip(root,out/f'{case}_02_REVIEW_EVIDENCE.zip',review),
      '03_FULL_DEBUG':write_zip(root,out/f'{case}_03_FULL_DEBUG.zip',debug),
    }
    manifest={'schema_version':1,'generated_utc':datetime.now(timezone.utc).isoformat(),'case':case,'packages':records}
    (out/'PACKAGE_SPLIT_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps(manifest,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
