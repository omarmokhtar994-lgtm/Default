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

Load the matching skill (Skill tool) at the start of each step it covers;
following it from memory does not count. Typical triggers: a defect or a
result below expectation -> systematic-debugging; any engine change ->
cpsat-engine-modeling + test-driven-development; before reporting a result or
verdict -> verification-before-completion; before a long full-CPU run ->
python-performance-optimization.

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
- frontend-design (anthropics/skills, Apache-2.0): visual design of any web UI
  (the team scheduler website): plan palette/type/layout first, avoid templated defaults.
- webapp-testing (anthropics/skills, Apache-2.0): Playwright checks and screenshots of
  the website before reporting it done.
- Website review skills. They suggest fixes; they never override the rules above. Every
  fix keeps the strict CSP (no inline script, style or event handlers; their React and
  Tailwind examples translate to plain Jinja, CSS and JS), copy stays in sentence case,
  and the engine stays untouched.
  - better-interface, better-accessibility, better-colors, better-layout,
    better-typography, better-ui, better-writing (jakubkrehel/skills @d574cc8, MIT):
    review a page or a change before a website phase ships; better-writing for labels,
    errors and empty states. interface-review (same source) runs only when typed as
    /interface-review and reviews a branch's interface changes.
  - web-interface-guidelines (vercel-labs/web-interface-guidelines @434b7f9, MIT; a pinned
    local copy, because the upstream skill downloads its rules at run time): the quick
    checklist for changed templates, CSS and JS.
  - web-quality-audit, accessibility, best-practices, performance, core-web-vitals
    (addyosmani/web-quality-skills @afa8da9, MIT; analyze.sh not installed): whole-site
    audits, security headers, page speed. Evidence comes from Playwright here (no
    Lighthouse or DevTools MCP); SEO is out of scope for an internal tool behind a sign-in.
    For accessibility, use addyosmani's skill for a site audit and better-accessibility for
    a single change.
- find-skills: discovering more skills (skills.sh search is blocked by the
  network policy here; browse the source repos on GitHub instead).
