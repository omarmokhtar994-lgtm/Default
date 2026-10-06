# Project rules (outrank every skill in .claude/skills)

Standing rules from the project owner. When a skill's advice conflicts with one
of these, the rule wins.

- Never regenerate, recreate or fabricate historical baseline workbooks or results.
- The RC9.1 baseline-protected workbooks keep their exact bytes:
  AE_AR_B2B.xlsx, Cricut_Voice_RC9_1_READY_SKELETON.xlsx, NMG_SP_RC9_1_READY_FIXED.xlsx.
  `engine/regression_assets` is protected. TDD's "delete the code and start
  over" applies to new code only, never to these.
- Do not weaken validation, and do not modify or delete tests, to make tests pass.
  Re-pin a test only when the measured contract changed, and say why in the test.
- Do not hide errors. Do not silently change scenario roster or demand values.
- No speculative behaviour changes: back each one with a pre-registered A/B rule
  or a measured configuration.
- Commit and push only to the session's designated branch. Report times in
  Egypt time (UTC+3).
- The release gate is `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Installed skills and how they apply here

- systematic-debugging, test-driven-development, verification-before-completion:
  the default way to fix defects (root cause, failing test first, evidence before
  claiming done).
- writing-plans, executing-plans: multi-step phases. Run inline (executing-plans);
  subagent-driven-development and requesting-code-review dispatch subagents, so
  use them only when the owner asks for that.
- receiving-code-review: weighing external reviews (e.g. ChatGPT evaluations).
- changelog-generator: release notes for a production package.
- cpsat-engine-modeling (project skill, from the CP-SAT Primer): any change,
  diagnosis or benchmark of a CP-SAT model in this repository.
- python-testing-patterns, property-based-testing: test design (Hypothesis is a
  new dependency: the owner decides). python-error-handling, python-anti-patterns:
  fail-closed validation and review checklists; apply to code being changed, not
  as repo-wide refactors (no type-hint or style sweeps without a request).
- python-performance-optimization: profiling CPU/memory (the engine has OOM history).
- find-skills: discovering more skills (skills.sh search is blocked by the
  network policy here; browse the source repos on GitHub instead).
