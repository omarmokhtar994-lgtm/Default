# Phase AK: channel colours, times in on a schedule, RTA tools on the day's 24 hours, team managers and adjustable roles. Implementation Plan

© 2026 Omar Mokhtar. All rights reserved.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task,
> inline (the owner's choice). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner's four items of 2026-10-15 (evening) with the answers given: channel colours D on the Timeline;
"Times in" on a schedule; Fix the day's breaks, Rescue the day and Change several breaks on the 24 hours from "Day
starts at"; a Team manager role with associates assigned to one, and what each role may see and do set by the admin.

**Architecture:** Colours are CSS tokens and the Timeline's SVG. The schedule page reads the RTA's zone helpers. The
three RTA tools take the window view the Timeline already uses (`day.window_view`) and keep each move on its shift's
own date. Roles get one new flag (`is_team_manager`) and associates one link (`team_manager_id`); a new module
`webapp/permissions.py` holds the catalogue of what can be allowed, the defaults that keep today's behaviour, and
the check every route and template uses.

**Tech Stack:** Flask, Jinja, SQLite, vanilla JS, unittest, Playwright.

**Spec:** `evidence/phase_ak/REQUESTS.md` (the owner's words, sample ak01 and the answers).

## Global Constraints

- CLAUDE.md: engine untouched; failing test first; re-pin only for an owner-changed contract, saying why; strict CSP
  (no inline script, style or handlers); sentence case; "Associate NN" names in fixtures; the copyright line in the
  first 4 lines of every website file; CSRF on every POST; Egypt time; push to the session's branch only.
- Colours (owner: D): Phone `#1A47A8`, Chat `#C2549F`, Email `#A6D96A`, the bar `#9AA1AA` where the day has a
  channel plan; P and C letters white, E letter `#1B1F24`; letters only on stretches of 30 minutes or more and never
  under a break.
- Team managers (owner): a new role next to Supervisor; assigned per associate on the People page and many at once;
  admins and supervisors may approve for an absent team manager; swaps need the team managers of both people; every
  request says where it is waiting.
- Roles (owner): the admin sets what Planner, Team manager and Supervisor may see and do. Admin keeps everything;
  associates keep My week only.

## Review Focus

1. An associate with no team manager: their request must still be decidable (by any team manager of the program,
   and by the backups), never stuck. Test in Task 5.
2. Both people of a swap with the same team manager: one approval is enough, not two. Test in Task 5.
3. A permission turned off must block the action on the server, not only hide the link (a POST sent by hand gets
   403). Test in Task 6.
4. A window that starts mid-day: a break moved by Fix the day's breaks on a shift from the day before is kept on
   that day, at the right minute. Test in Task 3.
5. Turning off every permission for a role must not lock the admin out or break the menu. Test in Task 6.

---

### Task 1: Channel colours D on the Timeline

**Files:** Modify `webapp/static/app.css` (tokens `--ch-phone`, `--ch-chat`, `--ch-email`, `--ch-ink`, new
`--ch-email-ink`, `.tl-bar.has-ch`), `webapp/templates/day.html` (Timeline bar class, channel rect height = bar,
letters), `webapp/DESIGN.md` (the channel set). Test: `webapp/tests/test_ak_colours.py`.

- [ ] Failing tests: the tokens hold D's hex values; a day with a channel plan draws `class="tl-bar has-ch"`, channel
  rects at the bar's y and height, `<text class="tl-ch-t">P</text>` on a 30-minute Phone stretch and none on a
  20-minute one, and no letter whose x falls inside a break.
- [ ] Implement; run; commit.

### Task 2: Times in on a schedule

**Files:** Modify `webapp/app.py` (`schedules` view at `/runs/<run_id>/schedules`), `webapp/templates/schedules.html`.
Test: `webapp/tests/test_ak_schedule_zone.py`.

- [ ] Failing tests: the page has the `Times in` select (the RTA's zones, the program's choice kept as on the RTA);
  with another zone picked every shift cell and break time is shown moved (`moved_text`) and the page says the
  schedule's own zone; the edit forms carry the hidden `tz` and the server moves typed times back
  (`to_schedule`) before `ScheduleBook.change`.
- [ ] Implement with `shown(moved)` as `day_page` does; run; commit.

### Task 3: RTA tools on the 24 hours from "Day starts at"

**Files:** Modify `webapp/day.py` (`replan` gets the view's origin: index i is minute `origin + i * STEP`; people
are every segment, each with its `date`), `webapp/attendance.py` (`replan`, `rescue`, bulk helpers take the window
page), `webapp/app.py` (`WINDOW_TABS` gains `replan`, `rescue`, `bulk`; the apply routes take `name|idx|start|date`),
`webapp/templates/day.html` (the forms send the date; the notice that the tools work on the schedule's day goes).
Test: `webapp/tests/test_ak_window_tools.py`.

- [ ] Failing tests: with `start=07:00`, Fix the day's breaks proposes moves for a shift that began the day before
  and its apply keeps the break on that shift's own date at the right minute; Rescue the day and Change several
  breaks list people of both days in the window; with `start=00:00` every result equals today's.
- [ ] Implement; run the existing replan, rescue and bulk tests too; commit.

### Task 4: The Team manager role and assigning associates

**Files:** Modify `webapp/store.py` (users: `is_team_manager`, `team_manager_id`, added on start for old
databases), `webapp/access.py` (`role()` returns "Team manager"; supervisors manage team managers as they manage
planners), `webapp/app.py` (`/admin/users`: the role choice, the Team manager pick per associate, and a bulk form
`/admin/users/team` taking `who` (user ids) and `team_manager`), `webapp/templates/admin_users.html`.
Test: `webapp/tests/test_ak_team_managers.py`.

- [ ] Failing tests: an admin adds a Team manager account; the People page sets an associate's team manager and sets
  three at once; only team managers who share the associate's program are offered and accepted (else refused with a
  reason); a database from before gets both columns.
- [ ] Implement; run; commit.

### Task 5: Approvals by team manager, backups, both team managers for swaps, where a request waits

**Files:** Modify `webapp/leave.py` (`may_decide`, `decide`, `count_for`, `waiting_on(row) -> str`),
`webapp/swaps.py` (`decide` records `tm_a` and `tm_b`; status stays `waiting_tm` until both sides are approved;
`waiting_on`), `webapp/store.py` (swap_requests: `tm_a`, `tm_b`), `webapp/templates/requests.html`, `me.html`.
Test: `webapp/tests/test_ak_approvals.py`.

- [ ] Failing tests: the assigned team manager approves their associate's leave, another team manager is refused
  ("Waiting for Team Manager 01, the team manager of Associate 03"); an admin or supervisor approves in their place;
  an associate with no team manager can be approved by any team manager of the program; a swap between two teams
  needs both team managers (the first approval says "waiting for Team Manager 02"); same team manager, one approval;
  a backup approves both sides at once; the Requests page and My week say where each request is waiting.
- [ ] Implement; run the existing leave and swap tests; commit.

### Task 6: Adjustable roles

**Files:** Create `webapp/permissions.py` (`CATALOGUE: Dict[str, Tuple[str, Dict[str, bool]]]` key -> (label,
defaults for "Planner", "Team manager", "Supervisor"); `ENDPOINTS: Dict[str, str]` endpoint -> key;
`allowed(store, user, key) -> bool`); modify `webapp/store.py` (table `role_permissions(role, key, allowed)`),
`webapp/app.py` (a `before_request` check from `ENDPOINTS`, 403 with the reason; `manager_required` and the
`is_admin or is_supervisor` flags read `allowed`; page `/admin/roles` for admins), `webapp/templates/base.html`
(menu links shown only when allowed), new `webapp/templates/roles.html`. Test: `webapp/tests/test_ak_roles.py`.

Catalogue (defaults Planner / Team manager / Supervisor): RTA, see the day (yes/yes/yes); RTA, change the day
(yes/no/yes); Overview and wallboard (yes/yes/yes); Weeks and schedules, see (yes/yes/yes); Schedules, change
(yes/no/yes); Run and upload schedules (yes/no/yes); Analysis and programs (yes/yes/yes); Exports (yes/yes/yes);
Coaching (yes/yes/yes); Team page (yes/yes/yes); Approve requests as team manager (no/yes/yes); Give the RTA's
approval (yes/no/yes); Manage people (no/no/yes); Departments, channels, targets, shrinkage, operating day and
leave balances (no/no/yes). Admin-only pages stay admin-only.

- [ ] Failing tests: with the defaults every existing test's planner and supervisor do what they did; turning
  "Exports" off for planners hides the menu link and answers 403 to `/exports/download`; turning "Approve requests"
  on for planners lets a planner decide; the admin page saves the matrix (CSRF, admin only, 403 for others); all
  off for a role still renders Home for that role; an admin is never blocked.
- [ ] Implement; run; commit.

### Task 7: Reviews, checks and the package

- [ ] Website review skills on the changed files (web-interface-guidelines, better-*, web-quality-audit,
  accessibility, best-practices, performance, core-web-vitals), security-and-hardening and security-review on roles
  and approvals; the fixes they find, each with its test.
- [ ] Suite, browser tests, gate, page review at 360 and 1440 px in the three looks, route sweep; CHECKS.md; release
  notes (changelog-generator); handoff; package; report.

## Rulings while building (each with what it costs if wrong)

- Item 2: the menu's Schedules list already has "Times in"; the schedule it opens (`/runs/<id>/schedules`) did not,
  so that is the page. Cost: a second page if the owner meant another.
- Item 4 (d, not answered): an associate with no team manager is approved by any team manager of the program, and
  by the backups, as now. Cost: one condition.
- Task 6 defaults keep today's behaviour for planners and supervisors; team managers start with seeing pages and
  approving their team. Cost: the admin changes them on the new page.
