# Phase BA ledger (plan: docs/superpowers/plans/2026-10-25-phase-ba-build.md)

Pre-flight: tasks 2 to 7 all touch `webapp/static/app.css` and `webapp/templates/base.html` or `day.html`; no shared function signatures. Rule: one commit per task, CSS edits appended in a clearly named block per task.

Task 1: complete. Icons for Shrinkage and Incidents (menu rules), palette (look), account links with icons. `tools/build_icons_css.py` regenerated from Phosphor core `main` SVGs (the pinned 2.1.1 tag is not fetchable here); the diff against the old `icons.css` is additions only, so no existing shape changed. Tests: `test_ba_icons` 3/3, `test_ag_look` 8/8.
