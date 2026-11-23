# © 2026 Omar Mokhtar. All rights reserved.
"""Check the website's pinned Python packages (deploy/requirements.txt) against known security advisories with pip-audit.

Run it from the repository root before a release, on a machine with internet access:
    pip install pip-audit      (into the web venv; it is not one of the site's own requirements)
    python tools/audit_dependencies.py
Exit status: 0 no known vulnerability, 1 a vulnerability was found (the list is printed), 2 the check could not run
(pip-audit missing, or no network). The offline release gate cannot run it, so it is a manual step before a release."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, List, Optional

REQUIREMENTS = Path(__file__).resolve().parents[1] / "deploy" / "requirements.txt"


def main(run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
         which: Callable[[str], Optional[str]] = shutil.which, requirements: Path = REQUIREMENTS,
         out=sys.stdout) -> int:
    tool = which("pip-audit")
    if tool is None:
        print("pip-audit is not installed. Run: pip install pip-audit", file=out)
        return 2
    if not requirements.is_file():
        print(f"{requirements} not found.", file=out)
        return 2
    done = run([tool, "-r", str(requirements)], capture_output=True, text=True, timeout=300)
    print((done.stdout or "") + (done.stderr or ""), file=out)
    if done.returncode == 0:
        return 0
    text = (done.stdout or "") + (done.stderr or "")
    # pip-audit exits 1 for a found vulnerability and also when it cannot reach its sources; tell them apart
    return 1 if "Found" in text and "vulnerab" in text else 2


if __name__ == "__main__":
    sys.exit(main())
