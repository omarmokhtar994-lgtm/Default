# Phase BB checks (2026-10-25, Egypt time)

Depth on the dashboards, with the value always on the front face. Sample: `dash3d/`; real pages: `shots/`.

| Check | Result |
|---|---|
| New unit tests `test_bb_chart_depth.py` | 18, failed first, pass: faces exist, front face size unchanged, faces inside the picture, no tip, crowded chart flat, number above the top face, CSS rules, nothing in the block moves or animates |
| Saved chart (`test_ax_downloads`) | new browser test failed first (mixed colours saved as `color(srgb ...)`), fixed in `app.js` `plain()`; passes with PNG and SVG tests |
| Pages | Home, Incidents, Shrinkage, Programs in three looks, no sideways scroll |
| Left flat on purpose | line charts, heat tables, sparklines |
| Website suite, half 0 | 1033 tests OK (3 skipped) |
| Website suite, half 1 | 1192 tests OK |
| Browser suite | 103 tests OK |
| Release gate | run inside the package build (see the package record) |
