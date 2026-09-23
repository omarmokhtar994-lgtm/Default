#!/usr/bin/env python3
"""Fail-closed dependency and CP-SAT compatibility check for RC9.2.2."""
from __future__ import annotations
import argparse
import importlib
import importlib.metadata
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED = {
    "ortools": ("9.15.6755", True),
    "openpyxl": ("3.1.2", False),
    "pandas": ("2.2.0", False),
    "numpy": ("1.26.0", False),
    "scipy": ("1.11.0", False),
}

def version_tuple(value: str) -> tuple[int, ...]:
    parts=[]
    for token in value.split("."):
        digits="".join(ch for ch in token if ch.isdigit())
        if not digits: break
        parts.append(int(digits))
    return tuple(parts)

def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--json-out",type=Path)
    args=parser.parse_args()
    rows=[]; failures=[]
    for package,(required,exact) in REQUIRED.items():
        try:
            actual=importlib.metadata.version(package)
            importlib.import_module(package)
            ok=(actual==required) if exact else version_tuple(actual)>=version_tuple(required)
            status="PASS" if ok else "FAIL_VERSION"
        except Exception as exc:
            actual=None; status="MISSING_OR_BROKEN"
            failures.append({"package":package,"required":required,"error":f"{type(exc).__name__}: {exc}"})
        else:
            if not ok: failures.append({"package":package,"required":required,"actual":actual,"exact":exact})
        rows.append({"package":package,"required":required,"actual":actual,"exact":exact,"status":status})
    cp_sat_status="NOT_RUN"
    if not any(row["package"]=="ortools" and row["status"]!="PASS" for row in rows):
        try:
            from ortools.sat.python import cp_model
            model=cp_model.CpModel(); x=model.NewBoolVar("x"); model.Add(x==1)
            solver=cp_model.CpSolver(); cp_sat_status=solver.Solve(model).name
            if cp_sat_status not in {"OPTIMAL","FEASIBLE"}:
                failures.append({"package":"ortools","error":f"CP-SAT smoke returned {cp_sat_status}"})
        except Exception as exc:
            cp_sat_status="ERROR"
            failures.append({"package":"ortools","error":f"CP-SAT smoke: {type(exc).__name__}: {exc}"})
    result={
        "schema_version":1,"generated_utc":datetime.now(timezone.utc).isoformat(),
        "status":"PASS" if not failures else "FAIL","python":platform.python_version(),
        "platform":platform.platform(),"packages":rows,"cp_sat_smoke":cp_sat_status,
        "failures":failures,
    }
    text=json.dumps(result,indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True,exist_ok=True)
        args.json_out.write_text(text+"\n",encoding="utf-8")
    return 0 if not failures else 2

if __name__=="__main__":
    raise SystemExit(main())
