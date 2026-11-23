#!/usr/bin/env python3
"""Make every dropdown in a workbook reject values outside its list.

The two-tab template builder (tools/build_input_template.py) created its
dropdowns with openpyxl's defaults, which leave showErrorMessage off: Excel
shows the list but accepts anything typed. RC5's shipped workbooks enforced
every validation. Without enforcement a yes/no instruction can hold "Enable"
or "Yes.", which the engine reads as "No" (audit finding F-18 / C-2).

This rewrites only the attributes of <dataValidation> elements:
showErrorMessage="1", errorStyle="stop" and an error title/message. Every
other zip member is copied byte for byte, every other byte of each sheet is
unchanged, and --check proves it: cell values and the engine's canonical
contract hash are compared before and after.

Do NOT run it on a baseline-protected workbook (one whose sha256 prefix is named
in evidence/RC9_1_BASELINE.json): its exact bytes are the RC9.1 comparison key.

    python3 tools/enforce_workbook_validations.py WORKBOOK.xlsx [...]      # rewrite in place
    python3 tools/enforce_workbook_validations.py --check WORKBOOK.xlsx    # report only
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

TAG = re.compile(rb"<dataValidation\b[^>]*>")
ERROR_TITLE = b"Value not allowed"
ERROR_TEXT = b"Choose a value from the list. Typed values outside the list are not accepted."


def _set_attr(tag: bytes, name: bytes, value: bytes) -> bytes:
    pattern = re.compile(rb'\s' + name + rb'="[^"]*"')
    if pattern.search(tag):
        return pattern.sub(b" " + name + b'="' + value + b'"', tag, count=1)
    closing = b"/>" if tag.endswith(b"/>") else b">"
    return tag[: -len(closing)] + b" " + name + b'="' + value + b'"' + closing


def enforce_tag(tag: bytes) -> bytes:
    for name, value in ((b"showErrorMessage", b"1"), (b"errorStyle", b"stop"),
                        (b"errorTitle", ERROR_TITLE), (b"error", ERROR_TEXT)):
        tag = _set_attr(tag, name, value)
    return tag


def unenforced_count(path: Path) -> tuple:
    total = open_ = 0
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if name.startswith("xl/worksheets/") and name.endswith(".xml"):
                for tag in TAG.findall(zf.read(name)):
                    total += 1
                    open_ += b'showErrorMessage="1"' not in tag
    return total, open_


def rewrite(path: Path) -> int:
    changed = 0
    with zipfile.ZipFile(path) as src:
        infos = src.infolist()
        payload = {info.filename: src.read(info.filename) for info in infos}
    for name, data in payload.items():
        if name.startswith("xl/worksheets/") and name.endswith(".xml"):
            new = TAG.sub(lambda m: enforce_tag(m.group(0)), data)
            if new != data:
                payload[name] = new
                changed += 1
    tmp = path.with_suffix(".tmp.xlsx")
    with zipfile.ZipFile(tmp, "w") as dst:
        for info in infos:
            dst.writestr(info, payload[info.filename], compress_type=info.compress_type)
    tmp.replace(path)
    return changed


def cell_values(path: Path) -> dict:
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=False)
    return {(ws.title, c.coordinate): c.value
            for ws in wb.worksheets for row in ws.iter_rows() for c in row if c.value is not None}


def contract_hash(path: Path):
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "engine" / "_tools"))
    import l632_universal_scheduler as engine
    parsed = engine.parse_input(path)
    return engine.canonical_hash(engine.canonical_contract_snapshot(parsed))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workbooks", nargs="+", type=Path)
    ap.add_argument("--check", action="store_true", help="report only; exit 1 if any dropdown is unenforced")
    args = ap.parse_args()
    bad = 0
    for path in args.workbooks:
        total, open_ = unenforced_count(path)
        if args.check:
            print(f"{path.name}: {total} validations, {open_} unenforced")
            bad += open_ > 0
            continue
        before_cells, before_hash = cell_values(path), contract_hash(path)
        sheets = rewrite(path)
        after_cells, after_hash = cell_values(path), contract_hash(path)
        if before_cells != after_cells or before_hash != after_hash:
            print(f"{path.name}: CONTENT CHANGED - refusing", file=sys.stderr)
            return 2
        print(f"{path.name}: {total} validations enforced in {sheets} sheet(s); "
              f"cell values and contract hash unchanged")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
