#!/bin/bash
# © 2026 Omar Mokhtar. All rights reserved.
# The website's browser tests (Playwright, Chromium at /opt/pw-browsers/chromium), verbose, into the log $1.
# Run from the repository root; PY is the web venv's python. They rewrite older phases' screenshots: restore those
# with git checkout before committing.
PY=${PY:-python3}
$PY -m unittest -v webapp.tests.test_ui_playwright > "$1" 2>&1
echo "EXIT $?" >> "$1"
