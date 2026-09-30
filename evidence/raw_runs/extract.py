#!/usr/bin/env python3
"""Copy the per-run evidence behind each published A/B into this tree (audit F-11).

For every run folder of a measured set it keeps what a third party needs to
recompute the published scores without the 0.5-2 GB of workbooks and debug
checkpoints each set produced:

  <run>/<run>.l6_3_2_3_summary.csv   the engine's own summary row
  <run>/INDEPENDENT_VALIDATION.json.gz
  <run>/UNIVERSAL_RUN_STATUS.json    runner return code and gate decision
  <run>/UNIVERSAL_RUN_IDENTITY.json  input/engine/parameter identity
  <run>/SOLVER_AUDIT_EXTRACT.json.gz every solver-audit key under 30 KB; the
                                     bulky search traces are dropped and named
  <run>/RUNNER_LOG_TAIL.txt          last 60 lines of the run's console log

A folder that exists but has no summary (a killed run) is copied with whatever
it has, so the scorers can tell "killed" from "missing".

    python3 evidence/raw_runs/extract.py SCRATCH_ROOT
"""
import gzip
import json
import shutil
import sys
from pathlib import Path

SETS = {  # scratch folder -> evidence folder it backs
    "s2e2e": "s2par_e2e",
    "dnbs_e2e": "dnbs_e2e",
    "dnbs3600": "dnbs_e2e_3600",
    "dnbs3600b": "dnbs_e2e_3600b",
    "seedtime": "seed_portfolio_ab",
    "div": "profile_diversity_ab",
    "fblab": "break_load_feedback_ab",
}
KEY_LIMIT = 30_000
HERE = Path(__file__).resolve().parent


def gz_json(obj, path: Path) -> None:
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, default=str)


def extract_run(src: Path, dst: Path) -> str:
    dst.mkdir(parents=True, exist_ok=True)
    for pattern in ("*_summary.csv", "UNIVERSAL_RUN_STATUS.json", "UNIVERSAL_RUN_IDENTITY.json"):
        for f in src.glob(pattern):
            shutil.copy2(f, dst / f.name)
    validation = src / "INDEPENDENT_VALIDATION.json"
    if validation.exists():
        gz_json(json.loads(validation.read_text(encoding="utf-8")), dst / "INDEPENDENT_VALIDATION.json.gz")
    audits = sorted(src.glob("*solver_audit.json"))
    if audits:
        audit = json.loads(audits[0].read_text(encoding="utf-8"))
        kept, dropped = {}, {}
        for key, value in audit.items():
            size = len(json.dumps(value, default=str))
            (kept if size <= KEY_LIMIT else dropped)[key] = value if size <= KEY_LIMIT else size
        kept["_extract"] = {"source": audits[0].name, "key_limit_bytes": KEY_LIMIT,
                            "dropped_keys_bytes": dropped}
        gz_json(kept, dst / "SOLVER_AUDIT_EXTRACT.json.gz")
    log = src.parent / f"{src.name}.log"
    if log.exists():
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        (dst / "RUNNER_LOG_TAIL.txt").write_text("\n".join(lines[-60:]) + "\n", encoding="utf-8")
    return "FINISHED" if list(src.glob("*_summary.csv")) else "NO_SUMMARY"


def main() -> int:
    scratch = Path(sys.argv[1])
    index = {}
    for name, target in SETS.items():
        out = scratch / name / "out"
        if not out.is_dir():
            print(f"missing set {out}", file=sys.stderr)
            return 2
        runs = {}
        for run in sorted(p for p in out.iterdir() if p.is_dir()):
            runs[run.name] = extract_run(run, HERE / target / run.name)
        sha = scratch / name / "ENGINE_SHA.txt"
        if sha.exists():
            shutil.copy2(sha, HERE / target / "ENGINE_SHA.txt")
        index[target] = {"scratch_set": name, "runs": runs}
        print(f"{target}: {len(runs)} runs, {sum(v == 'NO_SUMMARY' for v in runs.values())} without a summary")
    (HERE / "INDEX.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
