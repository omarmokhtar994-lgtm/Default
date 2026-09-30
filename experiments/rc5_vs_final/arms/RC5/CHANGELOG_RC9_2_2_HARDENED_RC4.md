# Changelog — RC9.2.2 Correction Package RC4

Engine release remains `L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2`.
RC4 is the approved residual-correction package after RC3.

## Corrections

- Fixed next-Sunday language repair donor selection so it uses the reserve
  key's actual day instead of a stale scan variable.
- Restored a nonzero runner return code when the engine completes without a
  validated final workbook. Explicit validation skips remain nonzero too.
- Retained multiple working windows for the same language, including split
  windows and multiple day-specific rows, while preserving legacy single-window
  compatibility.
- Added `Language Working Window` to the generated Instructions template.
- Added `Coverage Days` to generated Language Setup sheets with an enforced
  dropdown and safe common day/range values.
- Invalid Coverage Days now fail the input contract before CP-SAT instead of
  silently becoming all seven days.
- Invalid clock values no longer wrap with modulo arithmetic; malformed
  language, requirement, shrinkage, and allowed-start times fail the input
  contract before CP-SAT.
- Unknown language `Active` values, malformed language minima, malformed
  numeric demand/shrinkage cells, duplicate roster names, and duplicate
  employee IDs now fail closed instead of being silently coerced or
  overwritten.
- The manifest runner now terminates the complete solver process group on
  timeout or Colab interruption, preserving safe resume behavior.
- Phase C ZIPs are written to a temporary path, verified, and atomically
  published so an interrupted package build cannot leave a truncated final ZIP.
- All shipped input workbooks now have enforced validation alerts; their
  canonical parsed scheduling contracts and manifest identities were rechecked.
- The legacy Phase-A packager is disabled as a fail-closed compatibility stub.
- The production wrapper now protects each case with an atomic lock and
  immediate heartbeat, reclaiming only dead/partial locks for safe resume.
- Split evidence packaging now stages the complete set and places a
  self-contained `COMPONENT_MANIFEST.json` in every component ZIP.
- The RC9.2.2 output UX layer is integrated into the active polisher, including
  the `Read Me First` / Schedule Control Center dashboard and audit styling.
- The current RC4 no-Drive Colab notebook now references the RC4 validation
  package, exposes exact resume, and has a safe interruption path.
- All approved changes are covered by targeted regression tests.

Two approved deferred modules were intentionally left unchanged per the
approved scope; they are documented only in the deep-dive audit's
``Deferred Items (Out of Scope)`` section.

This remains a release candidate until the required current-build solver and
quality gates pass.
