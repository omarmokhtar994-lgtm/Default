# © 2026 Omar Mokhtar. All rights reserved.
"""Stand-ins for the production runner, input check, gate and scorer, so the
website's run logic is tested in seconds. Each writes what it was asked to do
next to its output, so a test can check the exact command line."""
import json
import sys
import time
from pathlib import Path


def runner(argv):
    def opt(name):
        return argv[argv.index(name) + 1]
    flags = [a for a in argv if a in ("--resume", "--skip-guards", "--overwrite")]
    results = Path(opt("--results-root"))
    stem = Path(opt("--input")).stem.upper()
    case = results / stem
    case.mkdir(parents=True, exist_ok=True)
    (results / "argv.json").write_text(json.dumps({"argv": argv, "flags": flags}), encoding="utf-8")
    print("[run] fake runner started", flush=True)
    delay = 3.0 if "SLOW" in stem else 0.2
    time.sleep(delay)
    if "SHORTFALL" in stem:  # no schedule meets every hard rule: one for review instead
        (case / f"{stem}_L6_3_2_3_HARD_RULE_SHORTFALL_SCHEDULE.xlsx").write_bytes(b"shortfall")
    else:
        (case / f"{stem}_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx").write_bytes(b"schedule")
    if "REAL" in stem:  # the trimmed validator/audit files of the Phase I real run
        import shutil
        real = Path(__file__).with_name("fixtures") / "real_run" / "NMG_SP_RC9_1_READY_FIXED"
        for f in real.iterdir():
            shutil.copy(f, case / f.name)
    (case / f"{stem}_L6_3_2_3_BEST_BEFORE_BREAKS_SCHEDULE.xlsx").write_bytes(b"before")
    # Phase L: the engine's own outcome, copied from real runs (names replaced).
    # The real runner exits 2 for a readiness check too: it scores release
    # gates, which a run that builds no schedule always fails.
    outcomes = Path(__file__).with_name("fixtures") / "outcomes"
    kind = next((k for k in ("NOTREADY", "READY", "CONFLICT", "SHORTFALL") if k in stem), None)
    if kind:
        source = {"NOTREADY": "conflict", "READY": "ready", "CONFLICT": "conflict", "SHORTFALL": "shortfall"}[kind]
        (case / "BUSINESS_OUTCOME.json").write_bytes((outcomes / f"{source}.json").read_bytes())
    print("[run] fake runner done", flush=True)
    return 2 if "FAILS" in stem or kind else 0


def check(argv):
    name = Path(argv[0]).name
    if "bad" in name.lower():
        print("Schedule!C7: unknown associate 'Zed'\nRESULT: REJECTED")
        return 1
    print("RESULT: ACCEPTED - ready to run")
    return 0


def score(argv):
    results = Path(argv[0])
    cases = sorted(p for p in results.iterdir() if p.is_dir() and not p.name.startswith("_"))
    verdict = "REVIEW_REQUIRED" if any("REVIEW" in c.name for c in cases) else "RELEASABLE"
    for case in cases:
        print(f"RELEASE VERDICT {case.name}: {verdict}")
    print(f"RELEASE VERDICT (run): {verdict}")
    return 0


def gate(argv):
    marker = Path(argv[0])
    count = int(marker.read_text()) + 1 if marker.exists() else 1
    marker.write_text(str(count))
    ok = not Path(str(marker) + ".fail").exists()
    print("GATE PASS — 75 suite(s), 1529 tests (2 skipped)" if ok else "GATE FAIL — see failures above")
    return 0 if ok else 1


if __name__ == "__main__":
    role = sys.argv[1]
    sys.exit({"runner": runner, "check": check, "score": score, "gate": gate}[role](sys.argv[2:]))
