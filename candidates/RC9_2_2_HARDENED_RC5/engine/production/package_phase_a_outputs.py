#!/usr/bin/env python3
"""Deprecated Phase A packaging entry point.

RC9.2.2 has one release packaging contract: Phase C. This compatibility file
is retained so old automation fails clearly instead of silently creating a
weaker three-ZIP delivery that bypasses exact-output validation and sealing.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "DEPRECATED PACKAGER: Phase A is disabled. Use "
        "engine/production/package_phase_c_outputs.py after independent "
        "validation has sealed the case.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
