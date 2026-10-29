#!/usr/bin/env python3
# © 2026 Omar Mokhtar. All rights reserved.
"""Run the revised candidate's checks and retain every actual result.

Default: full website, browser, route/page reviews and original package gate.
--offline: only the explicitly listed stdlib/pure checks, not a release pass.
--components: targeted real-runtime tests, not a release pass.
Missing dependencies never turn a failed/skipped integration check into PASS.
"""
import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFLINE = ["webapp.tests.test_an_decisions", "webapp.tests.test_an_zones",
           "webapp.tests.test_af_zones.TheClock", "webapp.tests.test_af_hover", "webapp.tests.test_day"]
COMPONENTS = OFFLINE + ["webapp.tests.test_an_correctness", "webapp.tests.test_an_routes",
                        "webapp.tests.test_an_http", "webapp.tests.test_an_repair", "webapp.tests.test_af_email_overnight"]


def test_totals(body, package_gate=False):
    """The gate's final total includes suites whose individual output is shortened."""
    if package_gate:
        totals = re.findall(r"(\d+) tests run, (\d+) skipped \(minimum", body)
        if totals:
            return tuple(map(int, totals[-1]))
    return (sum(map(int, re.findall(r"Ran (\d+) tests?", body))),
            sum(map(int, re.findall(r"skipped=(\d+)", body))))


def review_problems(name, body, output):
    """Historical review scripts print findings but can still exit successfully."""
    if name == "route_sweep":
        try:
            data = json.loads((output / "routes.json").read_text())
            findings = data["findings"]
            if not data["requests"] or set(findings) != {"exceptions", "5xx", "slow", "leaks", "odd"}:
                return ["Incomplete route review."]
            return [key for key, values in findings.items() if values] + (
                ["logged_errors"] if data["logged_errors"] else [])
        except (OSError, ValueError, KeyError, TypeError):
            return ["Missing or invalid route findings."]
    if name == "page_review":
        counts = re.findall(r"^problems: (\d+)$", body, re.MULTILINE)
        return [] if counts == ["0"] else ["Page review did not report zero problems."]
    if name in ("am_audit", "al_audit"):
        rows = re.findall(r"^(\d+) (\d+) (\S+) (\{.*\}) (csp|NO-CSP) (\[.*\])$", body, re.MULTILINE)
        problems = []
        if len(rows) != (8 if name == "am_audit" else 6):
            problems.append("Missing audit page results.")
        for width, status, path, metrics, csp, errors in rows:
            try:
                values = ast.literal_eval(metrics)
                if (int(status) != 200 or csp != "csp" or ast.literal_eval(errors)
                        or values["dup"] or values["unnamed"] or values["sw"] > values["vw"] + 1):
                    problems.append(f"Audit findings at {width}px: {path}")
            except (ValueError, SyntaxError, KeyError, TypeError):
                problems.append(f"Invalid audit result at {width}px: {path}")
        return problems
    return []


def main():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--components", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/phase_an_revised/validation")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    selected = "offline" if args.offline else "components" if args.components else "full"
    result = {"mode": selected, "status": "RUNNING", "checks": [],
              "generated_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
              "missing_dependencies": [m for m in ("flask", "werkzeug", "jinja2", "ortools", "playwright", "ruff")
                                       if importlib.util.find_spec(m) is None]}
    target = args.output / f"{selected}.json"
    env = dict(os.environ, PYTHON=sys.executable,
               PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))

    def record():
        target.write_text(json.dumps(result, indent=2) + "\n")

    def check(name, command, minimum=None, max_skips=0, timeout=1800):
        log = args.output / f"{selected}_{name}.log"
        began = time.monotonic()
        with log.open("w") as stream:
            try:
                code = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                      stderr=subprocess.STDOUT, timeout=timeout).returncode
            except subprocess.TimeoutExpired:
                stream.write("\nCHECK TIMED OUT\n")
                code = 124
        body = log.read_text(errors="replace")
        count, skipped = test_totals(body, package_gate=name == "package_gate")
        problems = review_problems(name, body, args.output)
        passed = code == 0 and (minimum is None or count >= minimum) and skipped <= max_skips and not problems
        item = {"name": name, "exit": code, "tests_reported": count, "skipped": skipped,
                "status": "PASS" if passed else "FAIL", "log": log.name,
                "seconds": round(time.monotonic() - began, 2)}
        if problems:
            item["review_problems"] = problems
        if "ModuleNotFoundError" in body or "No module named" in body:
            item["dependency_errors"] = sorted(set(re.findall(r"No module named ['\"]?([\w.]+)", body)))
        result["checks"].append(item)
        record()
        print(f"{name}: {item['status']} (exit {code}, {count} reported tests, {skipped} skipped)", flush=True)
        return passed

    tests = OFFLINE if args.offline else COMPONENTS
    passed = check("components", [sys.executable, "-m", "unittest", "-v", *tests], minimum=50)
    passed = check("compile", [sys.executable, "-m", "compileall", "-q", "webapp", "tools/validate_website_release.py"]) and passed
    passed = check("signatures", [sys.executable, "tools/check_cross_module_calls.py", "webapp"]) and passed
    if not args.offline and not args.components:
        passed = check("runtime", [sys.executable, "tools/runtime_environment_check.py"]) and passed
        passed = check("static", [sys.executable, "-m", "ruff", "check", "--isolated", "--select", "E9,F821", "webapp"]) and passed
        modules = ["webapp.tests." + p.stem for p in sorted((ROOT / "webapp/tests").glob("test_*.py"))
                   if "playwright" not in p.stem]
        for half in (0, 1):
            passed = check(f"website_{half}", [sys.executable, "-m", "unittest", "-v", *modules[half::2]],
                           minimum=1, max_skips=1) and passed
        total = sum(c["tests_reported"] for c in result["checks"] if c["name"].startswith("website_"))
        if total < 1183:
            result["website_count_error"] = f"Only {total} tests reported; the AM baseline ran 1183."
            passed = False
        passed = check("browser", [sys.executable, "-m", "unittest", "-v", "webapp.tests.test_ui_playwright"], minimum=77) and passed
        reviews = ROOT / "evidence/phase_am/tools"
        passed = check("route_sweep", [sys.executable, str(ROOT / "tools/review_website_routes.py"), str(args.output / "routes.json")]) and passed
        for name in ("am_audit", "al_audit"):
            screens = args.output / name
            screens.mkdir(exist_ok=True)
            passed = check(name, [sys.executable, str(reviews / f"{name}.py"), str(screens)]) and passed
        config = args.output / "review_server.json"
        config.unlink(missing_ok=True)
        log = args.output / "full_review_server.log"
        with log.open("w") as stream:
            server = subprocess.Popen([sys.executable, str(reviews / "review_server.py"), str(config)],
                                      cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 90
                while not config.exists() and server.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.2)
                if config.exists() and server.poll() is None:
                    screens = args.output / "page_screens"
                    screens.mkdir(exist_ok=True)
                    passed = check("page_review", [sys.executable, str(reviews / "page_review.py"), str(config), str(screens)]) and passed
                else:
                    result["checks"].append({"name": "page_review", "status": "BLOCKED", "log": log.name,
                                              "reason": "Review server did not start.", "exit": server.poll()})
                    passed = False
                    record()
            finally:
                if server.poll() is None:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
        passed = check("package_gate", ["bash", "run_tests.sh"], minimum=1537, max_skips=3) and passed
    result["status"] = ("OFFLINE_PASS" if args.offline else "COMPONENTS_PASS" if args.components else "PASS") if passed else "FAIL"
    result["production_approved"] = False
    record()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
