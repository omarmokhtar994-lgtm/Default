#!/usr/bin/env python3
# © 2026 Omar Mokhtar. All rights reserved.
"""A map of the scheduling engine, written from its code (Phase AZ; owner, 2026-10-25: "a map for later fixes").

    python3 tools/engine_map.py --write     write docs/ENGINE_MAP.md
    python3 tools/engine_map.py --check     exit 1 when the written map no longer matches the engine

The map holds the engine's functions by job, the stages of ``run_case``, who calls what, the process-wide switches, the places
that pin the engine's hash, and a symptom-to-place table. It reads the engine; it never changes it. It holds line numbers and
the engine's sha256, so any engine edit makes ``--check`` fail until the map is written again (``tools/refresh_engine_identity.py``
does that as part of the identity refresh)."""
from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "engine" / "_tools" / "l632_universal_scheduler.py"
OUT = ROOT / "docs" / "ENGINE_MAP.md"
SCAN = ("engine", "tools", "tests", "tests_staged", "webapp", "deploy")
RUNNERS = "packages/rc9_2_2_production/runners"  # the package ships it as runners/; the map names it the repository way


def scan_dirs(root: Path) -> List[Tuple[Path, str]]:
    """The folders the map reads, as (directory, name shown), the same in the repository and in the shipped package
    (which holds neither packages/colab_2700s_runners nor packages/release_gate_report.py)."""
    found = [(root / f, f) for f in SCAN]
    found.append((root / RUNNERS if (root / RUNNERS).is_dir() else root / "runners", RUNNERS))
    return found
SWITCHES = ("FINAL_RECOVERY_ENDGAME_ENABLED", "STAGE1_PROFILE_ROTATION", "BREAK_LOAD_FEEDBACK_ENABLED",
            "DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED", "SHIFT_CONSISTENCY_CLI_OVERRIDE", "SOLVER_DETERMINISTIC_TIME")
PINS = ("engine_file_sha256", "engine_sha256", "sha256_file(ENGINE)", "verify_engine")
MAJOR = 100  # lines: a function this long is a stage of its own in the outline of run_case
JOBS: List[Tuple[str, str]] = [  # first match wins; the name is matched with its leading underscores removed
    ("Run control and command line", r"^(run_case|main|build_arg_parser|cli_search_controls|.*budget.*)$"),
    ("Search phases (`run_*`)", r"^run_"),
    ("Files, hashing and small utilities", r"^(norm|safe_name|ensure_parent|sha256|verify_xlsx|atomic_|write_json|write_csv|ceil_units|"
                                           r"import_cp_sat|git_repository|canonical_hash|to_float|strict_float|yes$|tri_state|minute_of_day|"
                                           r"minute_in_inclusive|configure_solver)"),
    ("Input reading and contract", r"^(parse|read_|validate_input|input_|canonical|coerce|split_|authored|normalize_|require_input|"
                                   r"instruction|find_header|sheet_|discover|detect_interval|day_columns|is_day_header|report_|alias|"
                                   r"terms_in|blank_requirement|case_identity|synchronize|optional_instruction|add_half_hour|forced_long|"
                                   r"add_11h|long_mode|half_hour)"),
    ("Languages", r"language"),
    ("Breaks", r"break|solve_breaks"),
    ("Preferences, OFF days and fixed requests", r"preference|off_|^required_off|fixed_|weekly_off"),
    ("Shifts and rest", r"^(shift|rest_|previous_saturday|hhmm|shifts?_)|time|slot"),
    ("Metrics", r"metric|calculate_metrics"),
    ("Coverage, demand and capacity", r"coverage|capacity|demand|next_sunday|whole_week|overage|opening|scaled|volume_weight|cyclic_active"),
    ("Skeleton search (stage 1)", r"skeleton|aggregate_|stage1|profile|pattern"),
    ("Joint, repair and neighbourhood search", r"joint|repair|donor|coordinated|adaptive|neighbourhood|anchor|isolated"),
    ("Candidate selection", r"select|candidate|target_priority|deficit|tradeoff"),
    ("Output and publishing", r"^(write_|publish|business|output|cleanup|export|save_|load_|normalized_output|production_|compact_)"),
    ("Audit and self-check", r"audit|structural|validate|selfcheck"),
    ("Shift consistency polish", r"consistency"),
    ("Tiers, exceptions and quality figures", r"tier|exception|pareto|frontier|quality|hard_floor|near_feasible|benchmark|status_name"),
    ("Workbook styling", r"replace_sheet|style_header|autosize|display_rows"),
    ("Time reserves and machine limits", r"reserve|memory|telemetry|probe_retry|stage2"),
]
SYMPTOMS = [  # (what you see, where to look first); every name is checked to exist
    ("The workbook is misread or refused", ["parse_input", "validate_input_contract", "preference_kind"]),
    ("A language minimum is not met", ["language_rules_at", "language_reserve_status", "associate_language_windows",
                                       "solve_joint_shift_off_language_break_refinement"]),
    ("A break is placed too late, too early or too many at once", ["solve_breaks", "maximum_concurrent_breaks",
                                                                    "run_day_neighbourhood_break_search"]),
    ("A coverage figure on the output is wrong", ["calculate_metrics", "coverage_vars", "coverage_quality_limits"]),
    ("An OFF or shift request is not honoured", ["preference_kind", "required_off_days", "add_weekly_off_rule"]),
    ("A different candidate is published than expected", ["select_export_candidates", "target_priority_tradeoff_select",
                                                           "_candidate_quality_tuple"]),
    ("The output workbook and the validator disagree", ["write_output_workbook", "structural_schedule_audit",
                                                         "publish_business_outcome"]),
    ("A run takes longer or shorter than asked", ["run_case", "main", "stage1_minimum_budget_seconds"]),
    ("The first (skeleton) search is weak", ["build_skeleton", "skeleton_profiles", "aggregate_pattern_mix_guidance"]),
    ("A fixed or nested shift is broken", ["rest_compatible", "previous_saturday_compatible", "shift_parts"]),
]


def job_of(name: str) -> str:
    bare = name.lstrip("_")
    for job, pattern in JOBS:
        if re.search(pattern, bare):
            return job
    return "Other helpers"


def read_engine(path: Path = ENGINE):
    text = path.read_text(encoding="utf-8")
    return text, ast.parse(text)


def build(engine: Path = ENGINE, root: Path = ROOT) -> str:
    text, tree = read_engine(engine)
    digest = hashlib.sha256(engine.read_bytes()).hexdigest()
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    size = lambda n: n.end_lineno - n.lineno + 1  # noqa: E731
    lines = text.split("\n")

    callers: Dict[str, Set[str]] = collections.defaultdict(set)
    for fname, node in funcs.items():
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id in funcs and sub.id != fname:
                callers[sub.id].add(fname)

    users: Dict[str, Set[str]] = collections.defaultdict(set)  # engine name -> files outside the engine file
    own = engine.resolve()
    for base, shown in scan_dirs(root):
        for path in sorted(base.rglob("*.py")):
            if path.resolve() == own or "__pycache__" in path.parts:
                continue
            body = path.read_text(encoding="utf-8", errors="ignore")
            if "l632_universal_scheduler" not in body:
                continue
            aliases = set(re.findall(r"import\s+l632_universal_scheduler\s+as\s+(\w+)", body))
            aliases |= set(re.findall(r"(\w+)\s*=\s*(?:importlib\.)?import_module\(\s*[\"']l632_universal_scheduler", body))
            names = set(re.findall(r"from\s+l632_universal_scheduler\s+import\s+\(?([^)\n]+)", body))
            used = {x.strip("() ") for chunk in names for x in re.split(r"[,\s]+", chunk)}
            for alias in aliases:
                used |= set(re.findall(r"\b" + re.escape(alias) + r"\.(\w+)", body))
            rel = (Path(shown) / path.relative_to(base)).as_posix()
            if rel.startswith(("tests/", "tests_staged/")) or "/tests/" in rel:
                continue  # tests change often and use the engine freely; the map lists the code that depends on it
            for name in used:
                if name in funcs or name in {c.name for c in classes}:
                    users[name].add(rel)

    out: List[str] = []
    add = out.append
    add("# Engine map")
    add("")
    add("Written by `tools/engine_map.py` from `engine/_tools/l632_universal_scheduler.py`; do not edit by hand. "
        "`python3 tools/engine_map.py --check` fails when the engine has changed since this was written.")
    add("")
    add(f"- File: `{engine.relative_to(root).as_posix()}`, sha256 `{digest}`")
    add(f"- {len(lines):,} lines; {len(funcs)} functions, {len(classes)} classes")
    add("")

    # ---------------------------------------------------------------- run_case
    rc = funcs["run_case"]
    block = next(n for n in rc.body if isinstance(n, ast.With))
    add("## 1. The stages of `run_case`")
    add("")
    add(f"`run_case` is lines {rc.lineno} to {rc.end_lineno} ({size(rc):,} lines, {len(rc.args.args) + len(rc.args.kwonlyargs)} "
        f"parameters). Its body is one `with` block (lines {block.lineno} to {block.end_lineno}) of {len(block.body)} statements in "
        "sequence. The outline below is read from what it calls, in order of first call; a function of "
        f"{MAJOR} lines or more is a stage of its own.")
    add("")
    add("| Order | First call at line | Function | Lines | Job |")
    add("|---|---|---|---|---|")
    seen, order = set(), 0
    calls = sorted((c.lineno, c.func.id) for c in ast.walk(block)
                   if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id in funcs)
    for line, fname in calls:
        if fname in seen or fname == "run_case" or size(funcs[fname]) < MAJOR:
            continue
        seen.add(fname)
        order += 1
        add(f"| {order} | {line} | `{fname}` | {size(funcs[fname])} | {job_of(fname)} |")
    add("")
    add("Blocks inside `run_case` of 70 lines or more, in order:")
    add("")
    add("| Lines | Size | Starts with |")
    add("|---|---|---|")
    for n in block.body:
        if size(n) >= 70:
            first = lines[n.lineno - 1].strip().replace("|", "\\|")[:90]
            add(f"| {n.lineno} to {n.end_lineno} | {size(n)} | `{first}` |")
    add("")

    # ---------------------------------------------------------------- functions by job
    by_job: Dict[str, List[str]] = collections.defaultdict(list)
    for fname in funcs:
        by_job[job_of(fname)].append(fname)
    add("## 2. Functions by job")
    add("")
    add("| Job | Functions | Lines |")
    add("|---|---|---|")
    order_jobs = [j for j, _ in JOBS] + ["Other helpers"]
    for job in order_jobs:
        names = by_job.get(job, [])
        if names:
            add(f"| {job} | {len(names)} | {sum(size(funcs[x]) for x in names):,} |")
    add("")
    for job in order_jobs:
        names = sorted(by_job.get(job, []), key=lambda x: funcs[x].lineno)
        if not names:
            continue
        add(f"### {job}")
        add("")
        add("| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |")
        add("|---|---|---|---|---|---|")
        for fname in names:
            node = funcs[fname]
            doc = (ast.get_docstring(node) or "").strip().split("\n")[0].replace("|", "\\|")[:100]
            who = sorted(callers.get(fname, ()))
            who_text = ", ".join(f"`{w}`" for w in who[:4]) + (f" +{len(who) - 4}" if len(who) > 4 else "")
            ext = sorted(users.get(fname, ()))
            ext_text = f"{len(ext)} file{'s' if len(ext) != 1 else ''}" if ext else ""
            add(f"| `{fname}` | {node.lineno} to {node.end_lineno} | {size(node)} | {who_text} | {ext_text} | {doc} |")
        add("")

    # ---------------------------------------------------------------- outside use
    add("## 3. What is used from outside the engine file")
    add("")
    add("Names that other code (the wrapper, the validator, the tools, the website; not the tests, which use the engine freely) uses, "
        "by number of files. A change to one of these reaches those files.")
    add("")
    add("| Name | Files | Examples |")
    add("|---|---|---|")
    for name, files in sorted(users.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:40]:
        add(f"| `{name}` | {len(files)} | {', '.join(f'`{f}`' for f in sorted(files)[:3])} |")
    add("")

    # ---------------------------------------------------------------- switches
    add("## 4. Process-wide switches")
    add("")
    add("Module-level names written with `global` and read elsewhere. Code moved to another module must read them as "
        "`settings.NAME`, never `from x import NAME`, or a write would not be seen.")
    add("")
    add("| Switch | Defined at line | Written in | Read in |")
    add("|---|---|---|---|")
    for name in SWITCHES:
        defined = next((n.lineno for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign)) and any(
            isinstance(s, ast.Name) and s.id == name for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
            for s in ast.walk(t))), 0)
        wrote, read = set(), set()
        for fname, node in funcs.items():
            declared = any(isinstance(g, ast.Global) and name in g.names for g in ast.walk(node))
            touches = any(isinstance(s, ast.Name) and s.id == name for s in ast.walk(node))
            if declared:
                wrote.add(fname)
            elif touches:
                read.add(fname)
        add(f"| `{name}` | {defined} | {', '.join(f'`{x}`' for x in sorted(wrote)) or '-'} | "
            f"{', '.join(f'`{x}`' for x in sorted(read)) or '-'} |")
    add("")

    # ---------------------------------------------------------------- pins
    add("## 5. Places that pin or check the engine's hash")
    add("")
    add("After any engine edit, these must agree with the new file: run `python3 tools/refresh_engine_identity.py "
        "--previous <old sha256>`, then `python3 tools/engine_map.py --write`, then the gate.")
    add("")
    add("The two data files that hold it are `engine/RELEASE_IDENTITY_RC9_2_2.json` (`engine_file_sha256`) and "
        "`packages/rc9_2_2_production/SCENARIOS.json` (`engine_sha256`); the refresh script writes both. The code that reads or "
        "checks it:")
    add("")
    add("| File | Lines that name the hash |")
    add("|---|---|")
    rows = collections.Counter()
    for base, shown in scan_dirs(root) + [(root, "")]:
        pattern = "*.py" if shown else "*.json"
        for path in sorted(base.glob("**/" + pattern) if shown else base.glob(pattern)):
            if "__pycache__" in path.parts or path.name.startswith("test_") or path.name == "engine_map.py":
                continue
            rel = (Path(shown) / path.relative_to(base)).as_posix()
            if rel.startswith(("webapp/", "evidence/", "dist/", "candidates/", "experiments/", "docs/")):
                continue
            if rel == "SCENARIOS.json":  # the package's copy of packages/rc9_2_2_production/SCENARIOS.json: the map must read the same there
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").split("\n"), start=1):
                if any(p in line for p in PINS) and "sha256" in line.lower():
                    rows[rel] += 1
    for rel in sorted(rows):
        add(f"| `{rel}` | {rows[rel]} |")
    add("")

    # ---------------------------------------------------------------- symptoms
    add("## 6. Where to look first")
    add("")
    add("| What you see | Look at (line) |")
    add("|---|---|")
    for symptom, names in SYMPTOMS:
        missing = [x for x in names if x not in funcs]
        if missing:
            raise SystemExit(f"engine_map: the symptom table names functions the engine no longer has: {missing}")
        add(f"| {symptom} | " + ", ".join(f"`{x}` ({funcs[x].lineno})" for x in names) + " |")
    add("")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    text = build()
    if args.write:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out} ({len(text.splitlines())} lines)")
        return 0
    if args.check:
        if not args.out.exists() or args.out.read_text(encoding="utf-8") != text:
            print(f"{args.out} does not match the engine: run python3 tools/engine_map.py --write", file=sys.stderr)
            return 1
        print("engine map matches the engine")
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
