# Phase S: the owner's fixes after Phase R (2026-10-09)

**Goal:** fix the seven points the owner raised after installing Phase R.

**Spec:** the owner's message of 2026-10-09:
1. The upload form should select the program/LOB picked in the left menu.
2. A schedule uploaded without a program can't be found or assigned to one.
3. The schedule name and start date can't be changed after upload.
4. Day off cancelled: the shift start and end can't be chosen by hand, and it isn't in the RTA view.
5. Uploaded (ready) schedules have no summary.
6. Find a time opens a popup for 1 associate and shows no times.
7. Anything else that needs fixing.

**Global constraints:** CLAUDE.md applies, with these limits:
- No engine change; protected workbooks keep their bytes.
- Tests are written first. Re-pin a test only when its contract changed, and give the reason in the test.
- Programs are picked from the list, never typed (Phase R).
- Times are in Egypt time.

## Tasks
- S1 Find a time:
  - The person dialog reads `who`. On the meeting tab `who` is the finder's list of people, so the dialog must not read it there.
  - Test: `TheDayPage.test_find_a_time_for_two_people_opens_no_person_dialog`.
- S2 Upload form:
  - When there is no `?program=`, preselect the left-menu unit (`nav_unit`).
  - Tests: in `test_runs`.
- S3 Schedules page:
  - Show each run's start date, workbook and program.
  - Add an "Edit details" link that opens the run page's details editor.
- S4 Runs without a program:
  - A "Not filed under a program" panel for people who may file them.
  - Each run gets a Program-and-LOB select that files it through the existing run edit, which writes the audit.
- S5 Day off cancelled in RTA's "+ Add":
  - Lists the people who are off that day.
  - The shift comes from the Shift Library or from a manual start and end.
  - The manual times are checked: the end comes after the start, and the length is at most 12 h.
- S6 Ready schedule summary:
  - Coverage figures from the version's checks on the ready run page.
- S7 Sweep, then the release:
  - Fix the phone overflow found by the crawl.
  - Run the website suite, then the gate and the package, take screens and write the report.
