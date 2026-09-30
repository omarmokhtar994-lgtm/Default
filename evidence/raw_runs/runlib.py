"""Fail-closed reader for the per-run evidence in evidence/raw_runs (audit F-19).

The A/B scorers used to treat a missing run as a score of 0, so on an empty
directory score_deep.py printed "DEEP VERDICT: adopt E" and exited 0. Here:

* a run folder that does not exist is MISSING: the scorer must abort, because
  the evidence is incomplete and no verdict can be drawn from it;
* a folder without a summary, or whose runner exited nonzero, is a FAILED run
  (killed, crashed or rejected): it scores as "no validated schedule", which is
  what the pre-registered rules count against the arm;
* a run scores after_target only if validator PASS, 0 hard failures and metric
  parity PASS.
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import sys
from pathlib import Path

RAW = Path(os.environ.get("RAW_RUNS_ROOT") or Path(__file__).resolve().parent)


class IncompleteEvidence(SystemExit):
    def __init__(self, missing):
        print("INCOMPLETE EVIDENCE - no verdict. Missing run folders:", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        super().__init__(2)


def _json(path: Path):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    gz = path.with_name(path.name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as fh:
            return json.load(fh)
    return None


def load(run_dir: Path) -> dict:
    """One run's scored outcome. Raises nothing; MISSING is reported, not scored."""
    run_dir = Path(run_dir)
    if not run_dir.is_dir():
        return {"state": "MISSING", "dir": str(run_dir)}
    status = _json(run_dir / "UNIVERSAL_RUN_STATUS.json") or {}
    summaries = sorted(run_dir.glob("*_summary.csv"))
    rows = list(csv.DictReader(open(summaries[0], encoding="utf-8"))) if summaries else []
    if not rows:
        return {"state": "FAILED", "reason": f"no summary (runner rc {status.get('return_code')})",
                "after": None, "before": None, "valid": False, "audit": {}}
    row = rows[-1]
    validation = _json(run_dir / "INDEPENDENT_VALIDATION.json") or {}
    valid = (validation.get("status") == "PASS" and int(validation.get("hard_fail_count") or 0) == 0
             and (validation.get("metric_parity") or {}).get("status") == "PASS"
             and row.get("after_target") not in (None, ""))
    before = float(row["best_before_target"]) if row.get("best_before_target") not in (None, "") else None
    return {
        "state": "OK" if valid else "FAILED",
        "reason": "" if valid else (
            f"no independent validation (runner rc {status.get('return_code')})" if not validation else
            f"validator {validation.get('status')}, hard {validation.get('hard_fail_count')}, "
            f"parity {(validation.get('metric_parity') or {}).get('status')}"),
        "after": int(float(row["after_target"])) if valid else None,
        "raw_after": row.get("after_target"),
        "before": before,
        "valid": valid,
        "audit": _json(run_dir / "SOLVER_AUDIT_EXTRACT.json") or _json(next(iter(sorted(run_dir.glob("*solver_audit.json"))), run_dir / "_none_")) or {},
    }


def load_all(paths: dict) -> dict:
    """Load every expected run; abort with exit 2 if any folder is missing."""
    out = {key: load(path) for key, path in paths.items()}
    missing = [out[k]["dir"] for k in paths if out[k]["state"] == "MISSING"]
    if missing:
        raise IncompleteEvidence(missing)
    return out


def engine_sha(set_dir: Path) -> str:
    f = Path(set_dir) / "ENGINE_SHA.txt"
    if not f.exists():
        raise IncompleteEvidence([str(f)])
    return f.read_text().split()[0]
