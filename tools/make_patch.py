#!/usr/bin/env python3
# © 2026 Omar Mokhtar. All rights reserved.
"""Make a small patch for the website from the files changed since a package was built (Phase AW).

    python3 tools/make_patch.py BASE_PACKAGE.zip NAME [--output DIR]

BASE_PACKAGE.zip is the package that is installed on the server. The patch holds the website, deploy and tool files of this
working tree that differ from it (or are new), with the sha256 of each file as the package has it, and ``apply_patch.sh``.
The patch is ``NAME.zip``. On the server:  sudo bash apply_patch.sh NAME.zip   (see deploy/apply_patch.sh)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
TREES = ("webapp/", "deploy/", "tools/")  # what a package carries of the website; the engine is never patched
SKIP = ("__pycache__/", ".pyc")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def package_files(base: Path) -> Dict[str, str]:
    """Path (inside the package folder) -> sha256, for the website files of a package zip."""
    found: Dict[str, str] = {}
    with zipfile.ZipFile(base) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            _, _, rel = name.partition("/")
            if rel.startswith(TREES) and not any(s in rel for s in SKIP):
                found[rel] = sha(z.read(name))
    return found


def changed(base: Path, root: Path = ROOT) -> List[Dict[str, Optional[str]]]:
    """The files of ``root`` that differ from the package or are not in it, and what the package had (None: new)."""
    old = package_files(base)
    out: List[Dict[str, Optional[str]]] = []
    for tree in TREES:
        for path in sorted((root / tree).rglob("*")):
            rel = path.relative_to(root).as_posix()
            if not path.is_file() or any(s in rel for s in SKIP):
                continue
            new = sha(path.read_bytes())
            if old.get(rel) != new:
                out.append({"path": rel, "old_sha256": old.get(rel), "new_sha256": new})
    return out


def build(base: Path, name: str, out: Path, root: Path = ROOT) -> Optional[Path]:
    """Write ``out/name.zip``; None when nothing differs from the package."""
    files = changed(base, root)
    if not files:
        return None
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"{name}.zip"
    meta = {"name": name, "base_package_sha256": sha(base.read_bytes()), "files": files}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("PATCH.json", json.dumps(meta, indent=1))
        z.write(root / "deploy" / "apply_patch.sh", "apply_patch.sh")
        for f in files:
            z.write(root / f["path"], "files/" + f["path"])
    return target


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("base")
    ap.add_argument("name")
    ap.add_argument("--output", default=str(ROOT / "dist"))
    args = ap.parse_args(argv)
    target = build(Path(args.base), args.name, Path(args.output))
    if target is None:
        print("Nothing differs from that package: no patch needed.")
        return 1
    files = json.loads(zipfile.ZipFile(target).read("PATCH.json"))["files"]
    print(f"{target}  {len(files)} files  {target.stat().st_size / 1024:.0f} KB  sha256 {sha(target.read_bytes())}")
    for f in files:
        print(("  new      " if f["old_sha256"] is None else "  changed  ") + f["path"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
