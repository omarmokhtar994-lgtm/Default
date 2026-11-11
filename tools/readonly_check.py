#!/usr/bin/env python3
# © 2026 Omar Mokhtar. All rights reserved.
"""Run the package as it runs on the server after hardening: root-owned code the website's account cannot write.

    sudo python3 tools/readonly_check.py [--gate] [--engine] [--package dist/RC9_2_2_PRODUCTION_PACKAGE.zip --web --run]

It copies the working tree (git-tracked files) to a scratch folder, seals it with deploy/seal_package.sh, and runs, as the unprivileged account
``nobody`` with PYTHONDONTWRITEBYTECODE and a cache prefix like the service's:

  1. the website's own test client: sign in, a page of every kind, a schedule download, with the data folder the only writable place;
  2. the compile of the engine's six files (what the engine's self-check does), without and with the cache prefix;
  3. with ``--engine``: the engine's selfcheck and one real run of the smallest example workbook;
  4. with ``--gate``: the release gate (run_tests.sh), which takes 15 to 30 minutes;
  5. with ``--package ZIP`` the copy is the built package (as the server gets it) instead of the git tree; with ``--web`` every non-browser website test
     module runs against the sealed package (a failure whose text says permission denied or read-only is a write into the code: reported apart from
     the others); with ``--run`` one real engine run of the smallest example workbook, results into a writable results folder.

After each step it lists any file under the code folder that was created or changed (there must be none) and prints a verdict. Exit code 1 when any
step failed or the code folder was touched. This is a local reproduction with Unix permissions, not a systemd mount namespace: it proves what the code
tries to write, not the live unit's settings (``systemctl show scheduler-web`` is the evidence for those)."""
import argparse
import concurrent.futures
import os
import zipfile
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NOBODY = ["setpriv", "--reuid=65534", "--regid=65534", "--clear-groups"]


def as_nobody(cmd, env, cwd, timeout):
    base = {"PATH": "/usr/bin:/bin:" + str(Path(sys.executable).parent), "HOME": "/nonexistent", "LANG": "C.UTF-8", **env}
    return subprocess.run([*NOBODY, "env", "-i", *[f"{k}={v}" for k, v in base.items()], *cmd], cwd=cwd, capture_output=True, text=True, timeout=timeout)


def snapshot(code: Path):
    return {str(p.relative_to(code)): (p.lstat().st_mtime_ns, p.lstat().st_size) for p in code.rglob("*")}


def touched(before, code: Path):
    after = snapshot(code)
    return sorted({p for p in after if before.get(p) != after[p]} | {p for p in before if p not in after})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--engine", action="store_true")
    ap.add_argument("--package", type=Path)
    ap.add_argument("--web", action="store_true")
    ap.add_argument("--run", action="store_true")
    args = ap.parse_args()
    if os.geteuid() != 0:
        print("run with sudo (it makes the copy root-owned and runs as nobody)")
        return 2
    work = Path(tempfile.mkdtemp(prefix="readonly-check-"))
    os.chmod(work, 0o755)
    code, data, tmp = work / "package", work / "data", work / "tmp"
    for d in (data, tmp):
        d.mkdir()
        os.chmod(d, 0o777)
    if args.package:
        with zipfile.ZipFile(args.package) as z:
            top = z.namelist()[0].split("/")[0] + "/"
            for info in z.infolist():
                rel = info.filename[len(top):]
                if rel and not info.is_dir() and ".." not in rel.split("/"):
                    target = code / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(info))
                    target.chmod(0o755 if info.external_attr >> 16 & 0o100 else 0o644)
    else:
        files = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout.split(b"\0")
        for rel in filter(None, (f.decode() for f in files)):
            src = REPO / rel
            if src.is_file():
                (code / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, code / rel)
    if not (code / "MANIFEST.json").exists():
        (code / "MANIFEST.json").write_text("{}\n")
    sealed = subprocess.run(["bash", str(REPO / "deploy" / "seal_package.sh"), str(code)], capture_output=True, text=True)
    print(sealed.stdout.strip() or sealed.stderr.strip())
    results = []
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(tmp / "pyc"), "TMPDIR": str(tmp), "SCHEDULER_DATA_DIR": str(data),
           "XDG_CACHE_HOME": str(data / "cache"), "RUFF_CACHE_DIR": str(data / "cache" / "ruff"), "PYTHONPATH": str(code),
           "PYTHON": sys.executable}                           # the service file sets PYTHON the same way: the runner's safety gate uses it
    py = sys.executable

    def step(name, cmd, timeout, extra=None, ok_codes=(0,)):
        before = snapshot(code)
        got = as_nobody(cmd, {**env, **(extra or {})}, code, timeout)
        changed = touched(before, code)
        good = got.returncode in ok_codes and not changed
        results.append((name, good))
        print(f"{'PASS' if good else 'FAIL'}  {name}" + (f"   code folder touched: {changed[:5]}" if changed else ""))
        if not good:
            print((got.stdout + got.stderr)[-1500:])
        return got

    step("the website's own tests that sign in and read pages (read-only code)",
         [py, "-m", "unittest", "webapp.tests.test_auth", "webapp.tests.test_security_review_regressions"], 600)
    compile_cmd = [py, "-c", "import py_compile,sys; [py_compile.compile(p, doraise=True) for p in sys.argv[1:]]",
                   *[str(code / "engine" / "_tools" / n) for n in ("l632_universal_scheduler.py",)]]
    bare = as_nobody(compile_cmd, {k: v for k, v in env.items() if k != "PYTHONPYCACHEPREFIX"}, code, 120)
    results.append(("an explicit compile WITHOUT a cache prefix fails in read-only code (the reported fault)", bare.returncode != 0))
    print(f"{'PASS' if bare.returncode != 0 else 'FAIL'}  explicit compile without a cache prefix is refused (as the earlier server run found)")
    step("an explicit compile of the engine's file with the cache prefix works and writes nothing into the code", compile_cmd, 120)
    if args.engine:
        step("the engine's selfcheck", [py, "engine/RUN_UNIVERSAL_PRODUCTION.py", "--selfcheck"], 900)
    if args.gate:
        step("the release gate (run_tests.sh)", ["bash", "run_tests.sh"], 3600, {"PYTHON": py})
    if args.web:
        skip = {l.strip() for l in (code / "webapp" / "tests" / "solver_modules.txt").read_text().splitlines() if l.startswith("test_")}
        mods = sorted(p.stem for p in (code / "webapp" / "tests").glob("test_*.py") if p.stem not in skip and "playwright" not in p.stem)

        home = work / "home"                                   # the service's own account has a home in the data folder (LibreOffice keeps its profile there)
        home.mkdir()
        os.chmod(home, 0o777)

        def one(mod):
            got = as_nobody([py, "-m", "unittest", f"webapp.tests.{mod}"], {**env, "TMPDIR": str(tmp), "HOME": str(home)}, code, 1800)
            return mod, got.returncode, got.stdout + got.stderr

        before = snapshot(code)
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            done = list(pool.map(one, mods))
        changed = touched(before, code)
        failed = [(m, out) for m, rc, out in done if rc]
        needs = ("Permission denied", "Read-only file system", "PermissionError", "EACCES")
        into_code = [m for m, out in failed if any(w in out for w in needs) and not all("/evidence/" in line for line in out.splitlines() if any(w in line for w in needs))]
        evidence_only = [m for m, out in failed if any(w in out for w in needs) and m not in into_code]
        print(f"web test modules: {len(done)} run, {len(done) - len(failed)} passed, {len(failed)} failed; "
              f"{len(into_code)} wrote or tried to write into the code; {len(evidence_only)} only tried to save a development screenshot under evidence/")
        for m in evidence_only:
            print(f"  development screenshot writer (not part of the website): {m}")
        for m, out in failed[:12]:
            print(f"  FAILED {m}: " + (out.strip().splitlines() or [''])[-1][:160])
        wrote = into_code
        results.append(("website test modules, none wrote into the code folder", not wrote and not changed))
        print(f"{'PASS' if not wrote and not changed else 'FAIL'}  no website test wrote into the code folder" + (f"   touched: {changed[:5]}" if changed else ""))
        (work / "web_failed.txt").write_text("\n".join(m for m, _ in failed))
        if failed:
            keep = REPO / "evidence" / "phase_sec" / "web_failures_readonly.txt"
            keep.write_text("\n\n".join(f"== {m}\n{out[-1500:]}" for m, out in failed))
    if args.run:
        inp = code / "inputs" / "NMG_SP_RC9_1_READY_FIXED.xlsx"
        res = work / "results"
        res.mkdir()
        os.chmod(res, 0o777)
        got = step("one real engine run (smallest example workbook, QUICK, a full schedule, 2 minutes of solving) into a writable results folder",
                   [py, "runners/rc922_runner.py", "--package-root", str(code), "--results-root", str(res), "--mode", "QUICK", "--num-workers", "2",
                    "--stage", "FULL_SCHEDULE", "--seeds", "1", "--time-limit", "120", "--input", str(inp)], 1800, ok_codes=(0, 2))   # 2 = built but not releasable (the verdict), not a failure to run
        verdict = [l for l in got.stdout.splitlines() if l.startswith("RELEASE VERDICT (run)")]
        print("   ", verdict[-1] if verdict else "no verdict line")
        sheets = [p for p in res.rglob("*.xlsx")]
        results.append(("the run wrote a schedule workbook into the results folder", bool(sheets)))
        print(f"{'PASS' if sheets else 'FAIL'}  the run wrote {len(sheets)} workbook(s) into the results folder")
        print("results written:", sum(1 for _ in res.rglob("*") if _.is_file()), "files")
    shutil.rmtree(work, ignore_errors=True)
    bad = [n for n, ok in results if not ok]
    print("\nALL STEPS PASSED: nothing tried to write the code folder." if not bad else f"\nFAILED: {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
