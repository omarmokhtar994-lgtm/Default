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


# Modules that bind another module dynamically, which static import resolution
# cannot see. The validator loads the engine with load_engine(path) and calls
# it through `eng`, so a renamed engine function would pass every import check
# and crash only when the validator runs.
DYNAMIC_BINDINGS = {
    "independent_validator": {"eng": "l632_universal_scheduler"},
}


def module_level_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add((alias.asname or alias.name).split(".")[0])
    return names


def check_dynamic(modules: dict) -> int:
    failures = 0
    for stem, bindings in DYNAMIC_BINDINGS.items():
        if stem not in modules:
            continue
        path, tree = modules[stem]
        for alias, target in bindings.items():
            if target not in modules:
                print(f"{path}: dynamic binding {alias} -> {target}: target module not found")
                failures += 1
                continue
            ttree = modules[target][1]
            names = module_level_names(ttree)
            defs = function_defs(ttree)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
                        and node.value.id == alias):
                    if node.attr not in names:
                        failures += 1
                        print(f"{path}:{node.lineno}: {alias}.{node.attr} -> "
                              f"{target} has no such name")
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == alias):
                    fn = defs.get(node.func.attr)
                    if fn is None:
                        continue
                    if any(k.arg is None for k in node.keywords):
                        continue
                    if any(isinstance(a, ast.Starred) for a in node.args):
                        continue
                    keywords = {k.arg for k in node.keywords if k.arg}
                    for problem in accepts(fn, keywords, len(node.args)):
                        failures += 1
                        print(f"{path}:{node.lineno}: {alias}.{node.func.attr}() -> "
                              f"{target}.{fn.name}(): {problem}")
    return failures


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
    failures += check_dynamic(modules)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(check(Path(sys.argv[1] if len(sys.argv) > 1 else "engine")))
