# Phase AN: bring ChatGPT's reviewed website fixes onto the branch. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take the accepted parts of ChatGPT's deep-review work (three delivery rounds) onto branch
`ccr-90ec94cc-a37tqk`, with the owner's four decisions, then check and package it.

**Architecture:** Claude reviewed each round on a scratch copy of the branch head. The final round's `webapp/`
files, the review tools and the `deploy/requirements.txt` pin are copied over; the engine, the protected workbooks and
the gate's staged tests stay as they were.

**Tech Stack:** Flask, Jinja, SQLite, OR-Tools CP-SAT (in a child process for channel solves), unittest, Playwright.

**Spec:** `evidence/phase_an/REQUESTS.md`.

## Global Constraints

- CLAUDE.md: engine, `engine/regression_assets` and the three baseline workbooks untouched; no test weakened to pass;
  no unrequested behaviour change; strict CSP; sentence case; "Associate NN" names; copyright line; CSRF on every POST;
  commit and push only to the designated branch; times in Egypt time.
- Owner: A keep the fixes; B Fix channels as in AM; C short manual blocks warn; D no draft lock.

## Review Focus

1. A page form that posts to Plan breaks or Plan channels must never answer 409 for a missing token (D).
2. Fix channels must not plan tomorrow's shifts or move last night's people (B).
3. A saved hand-set block under the minimum stretch is kept, with a warning (C).
4. A solver crash or timeout keeps the draft and the website up.
5. A converted download across a clock change refuses a repeated or missing hour with a message, never a guess.

---

### Task 1: Review the rounds

- [x] Round 1: suite 1214 tests, 6 broken by the draft guard; four unrequested behaviour changes found.
- [x] Round 2 (Hardened): suite 1238 OK, browser 77 OK, gate PASS on Claude's side.
- [x] Round 3 (Completed): read the diff against Hardened (RTA fallback in a window where one offset cannot hold,
  ambiguous source hours refused, one gate test rewritten).

### Task 2: Overlay and check

- [ ] Copy `webapp/`, `tools/review_website_routes.py`, `tools/validate_website_release.py` and `deploy/requirements.txt`
  from the final round. Do not copy `tests_staged/test_rc9_2_19_joint_solve_isolation.py` (ruling 2).
- [ ] pyflakes clean except the known old imports; the new tests pass; the website suite in two halves; browser tests.
- [ ] Page review, route sweep, interface reviews; evidence in `evidence/phase_an/CHECKS.md`.

### Task 3: Package

- [ ] Handoff and phase history; release notes; build with `tools/build_production_package.py`; split in 26 MB parts;
  report.

## Rulings while building (each with what it costs if wrong)

See `evidence/phase_an/REQUESTS.md`, "Rulings".
