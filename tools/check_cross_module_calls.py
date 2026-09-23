"""Static check: do cross-module calls match the signatures they target?

The merge shipped a caller from one lineage and its callee from another:

    build_global_budget_plan(..., diagnostics=...)   # scheduler
    def build_global_budget_plan(... )               # phase_b_maturity, no such arg

Every suite passed and both selfchecks passed, because neither enters
run_case. A real 1800s run died on the first call. ruff's F821 does not see
this -- the name resolves, only the keyword is wrong.

This walks each module's imports of local sibling modules, resolves the
imported callables to their definitions, and checks every call site's keywords
and positional count against the real signature.

Exit 0 when every call is compatible, 1 otherwise.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path


def function_defs(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    out: dict[str, ast.FunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
    return out


def accepts(fn: ast.FunctionDef, keywords: set[str], positional: int) -> list[str]:
    a = fn.args
    names = {arg.arg for arg in (a.posonlyargs + a.args + a.kwonlyargs)}
    problems: list[str] = []
    if a.kwarg is None:
        for key in sorted(keywords - names):
            problems.append(f"unexpected keyword {key!r}")
    positional_slots = len(a.posonlyargs) + len(a.args)
    if a.vararg is None and positional > positional_slots:
        problems.append(
            f"{positional} positional args but only {positional_slots} accepted")
    required = [arg.arg for arg in (a.posonlyargs + a.args)]
    defaulted = len(a.defaults)
    required_names = required[:len(required) - defaulted] if defaulted else required
    supplied = set(required_names[:positional]) | keywords
    for arg in a.kwonlyargs:
        idx = a.kwonlyargs.index(arg)
        if a.kw_defaults[idx] is None and arg.arg not in supplied:
            problems.append(f"missing required keyword-only arg {arg.arg!r}")
    for name in required_names:
        if name not in supplied:
            problems.append(f"missing required arg {name!r}")
    return problems


def check(root: Path) -> int:
    modules: dict[str, tuple[Path, ast.AST]] = {}
    for path in sorted(root.rglob("*.py")):
        try:
            modules[path.stem] = (path, ast.parse(path.read_text(encoding="utf-8")))
        except (OSError, SyntaxError) as exc:
            print(f"SKIP {path}: {exc}")
    failures = 0
    for stem, (path, tree) in modules.items():
        imported: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in modules:
                for alias in node.names:
                    imported[alias.asname or alias.name] = node.module
        if not imported:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            target = imported.get(node.func.id)
            if target is None:
                continue
            defs = function_defs(modules[target][1])
            fn = defs.get(node.func.id)
            if fn is None:
                continue
            if any(k.arg is None for k in node.keywords):
                continue  # **kwargs splat at the call site; cannot decide statically
            if any(isinstance(a, ast.Starred) for a in node.args):
                continue
            keywords = {k.arg for k in node.keywords if k.arg}
            for problem in accepts(fn, keywords, len(node.args)):
                failures += 1
                print(f"{path}:{node.lineno}: {node.func.id}() -> "
                      f"{target}.{fn.name}(): {problem}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1] if len(sys.argv) > 1 else "engine")))
