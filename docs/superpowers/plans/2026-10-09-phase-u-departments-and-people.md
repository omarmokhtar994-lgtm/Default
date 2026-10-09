# Phase U: "With" picked from a program's departments and people (2026-10-09)

**Goal:** booking an aux picks "With" from two lists: first the department, then a person in it. Admins and supervisors keep these lists per program, so later analysis groups the same names the same way.

**Spec:** the owner's message of 2026-10-09:
"Can the who be categorized as well by 2 things department and names and those to be added for each program by admin or supervisor for each program individually and then that will popup as a drop down list while choosing them ? So i will add list of departments along with list of possible who to ensure consitenty for later on analysis"

**Global constraints:** CLAUDE.md applies, with these limits:
- No engine change.
- Tests are written first. A re-pin carries its reason in the test.
- Validation fails closed.
- Records keep the department and name as text, so a later change to the lists never rewrites history.

## Tasks
- U1 Store and `webapp/contacts.py`:
  - Two tables, `aux_departments` and `aux_people`, kept per program and shared by its LOBs.
  - The day's tables gain a `with_dept` column.
  - `ContactBook` has `lists`, `for_unit`, `add`, `add_many` (paste a list: one "Department, Name" per line, or two columns copied from Excel), `remove_person` and `remove_department`.
    - Duplicates are refused regardless of case.
    - A department may be up to 60 characters and a name up to 80.
    - `add_many` checks every line before keeping any; a bad line refuses the whole paste and names the line.
  - `pick_contact(lists, kind, dept, name)` returns the canonical pair, or a plain refusal.
  - When a program is deleted, its lists go with it.
- U2 Page `/setup/with?program=<key>`:
  - Admins see it for every program; a supervisor sees it for their own programs. Planners get a 403.
  - Under Manage, "Departments and people" follows the program picked on the left.
  - Each change is recorded and listed in Exports' "Other actions".
- U3 Booking:
  - When the program has a list, every aux form shows Department, then With (only that department's people). The routes check the pair against the list.
  - Without a list, Phase T's free text stays. Admins and supervisors also see a link to set the list.
  - The day log reads ", with Lina (Quality): reason".
  - Exports gain a "With department" column.
- U4 Browser check, screens, suite, gate, package, report.
