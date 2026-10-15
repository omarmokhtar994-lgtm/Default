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
  Egypt time (Africa/Cairo clock: UTC+3 in summer, UTC+2 in winter).
- The release gate is `run_tests.sh` with `tests_staged/GATE_MINIMUMS.json`.

## Carrying on in a new chat (owner, 2026-10-15)

Read `docs/HANDOFF.md` first: where the work stands, how a phase runs, how to run the checks. The owner's standing
preferences from earlier chats:

- Chat replies in caveman style (terse, every technical fact kept); code, commits and docs in normal prose.
- Efficiency: no check-ins between tasks; once the owner says go ahead, finish the phase through to the package.
- Website files: strict CSP, sentence-case copy, and `© 2026 Omar Mokhtar. All rights reserved.` in their first 4
  lines. Data in fixtures, samples and screens uses made-up "Associate NN" names, never real employees.
- The server's private key, passwords and notification secrets never go in the repository, chat, logs or command
  lines, and are never asked for or searched for. The owner installs packages on the server themselves.

## Coding guidelines (Karpathy)

Added at the owner's request (2026-10-14) from forrestchang/andrej-karpathy-skills @2c60614 (MIT), which
draws on Andrej Karpathy's notes on common LLM coding mistakes. The project rules above win where they differ.
These lean toward caution over speed; for trivial tasks, use judgment.

1. **Think before coding.**
   - State assumptions.
   - When there are several readings, name them rather than picking one silently.
   - Say so when a simpler way exists.
   - If something is unclear, stop and name it.
   - Here, ask the owner only about decisions that are theirs (samples, behaviour changes, new dependencies).
     Otherwise take the sensible default and say which one.
2. **Simplicity first.**
   - Write the minimum code that solves the problem.
   - No features, abstractions or configurability nobody asked for.
   - If 200 lines could be 50, rewrite.
   - This never relaxes fail-closed validation of inputs that can really occur.
3. **Surgical changes.**
   - Touch only what the request needs.
   - Match the existing style.
   - Do not improve neighbouring code, comments or formatting.
   - Mention unrelated dead code instead of deleting it.
   - Remove only what your own change left unused.
   - Every changed line traces to the request.
4. **Goal-driven execution.**
   - Turn the task into checks: a failing test that reproduces the bug, then make it pass; tests green before
     and after a refactor.
   - For multi-step work, state a short plan with a check per step, and loop until each check passes.

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
- security-and-hardening, observability-and-instrumentation, documentation-and-adrs
  (addyosmani/agent-skills @1be8e34, MIT; each has local notes at the top):
  - security-and-hardening: any website change that touches sign-in, sessions, uploads,
    group links or other secrets, or outbound posts.
  - observability-and-instrumentation: adding or reviewing logging on the server. A metrics
    or tracing stack is a new dependency: the owner decides.
  - documentation-and-adrs: recording why a decision was made, in this repository's own
    layout (docs/superpowers/plans, evidence/phase_xx), not a new docs/decisions folder.
  - The rest of that pack is not installed: it repeats skills already in use (TDD,
    debugging, review, planning, performance).
- Design and motion skills the owner asked for (2026-10-14). Same limits as the website review
  skills: they suggest, the rules above and `webapp/DESIGN.md` decide, and a new library or a
  visual change goes to the owner as a sample first.
  - From the owner's claude.ai account (synced each session; not in this repository):
    design-taste-frontend ("taste"), impeccable, design-md ("awesome design", DESIGN.md files of
    well-known sites), playwright-cli, img2threejs (image to a three.js model; no three.js on the site).
  - In this repository, each with local notes:
    - ui-ux-pro-max (nextlevelbuilder @7246805, MIT): local searchable UX rules; never `--persist`.
    - gsap-* (greensock/gsap-skills @aed9cfd, official, MIT, 8 skills).
    - lenis (official README, darkroomengineering @bc152f9, MIT).
    - react-bits (React Bits' own AI index @496968c; MIT + Commons Clause; ideas to port, no React).
    - graphify (safishamsi/graphify @041771b): only on /graphify; code-only by default;
      `graphify-out/` is git-ignored.
  - "Web design guidelines" is web-interface-guidelines above.
- find-skills: discovering more skills (skills.sh search is blocked by the
  network policy here; browse the source repos on GitHub instead).
