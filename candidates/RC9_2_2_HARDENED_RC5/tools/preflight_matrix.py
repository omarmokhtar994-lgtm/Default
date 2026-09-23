#!/usr/bin/env python3
"""Parse every manifest workbook and record the fail-closed contract result."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine" / "_tools"))
import l632_universal_scheduler as engine  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "SCENARIOS.json").read_text(encoding="utf-8"))
    rows = []
    for scenario in manifest["scenarios"]:
        path = ROOT / "inputs" / scenario["input"]
        row = {"scenario_id": scenario["scenario_id"], "input": scenario["input"]}
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            parsed = engine.parse_input(path)
            preflight = engine.validate_input_contract(parsed)
            row.update({
                "status": preflight["status"],
                "failure_count": len(preflight.get("failures") or []),
                "warning_count": len(preflight.get("warnings") or []),
                "warning_codes": [value.get("code") for value in preflight.get("warnings") or []],
                "sha256": digest,
                "manifest_hash_match": digest == scenario["input_sha256"],
                "associates": len(parsed.associates),
                "shift_count": len(parsed.shifts),
                "shift_durations_minutes": sorted({shift.duration_min for shift in parsed.shifts}),
                "use_11h_3off": parsed.use_11h_3off,
                "run_stage": parsed.run_stage,
                "run_depth": parsed.run_depth,
                "language_working_window": parsed.language_working_window_mode,
            })
        except Exception as exc:
            row.update({"status": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
        rows.append(row)
    result = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "engine_release": engine.VERSION,
        "engine_sha256": hashlib.sha256((ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_bytes()).hexdigest(),
        "manifest_engine_hash_match": hashlib.sha256((ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_bytes()).hexdigest() == manifest["engine_sha256"],
        "status": "PASS" if (
            hashlib.sha256((ROOT / "engine" / "_tools" / "l632_universal_scheduler.py").read_bytes()).hexdigest() == manifest["engine_sha256"]
            and all(row.get("status") in {"PASS", "WARN"} and row.get("manifest_hash_match") for row in rows)
        ) else "FAIL",
        "rows": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
