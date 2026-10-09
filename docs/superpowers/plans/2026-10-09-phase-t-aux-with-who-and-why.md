# Phase T: every aux says who it is with and why (2026-10-09)

**Goal:** booking an aux takes two answers: who it is with and why. Both are kept with the record and shown on the day. They are written in the day log and appear in the exports.

**Spec:** the owner's message of 2026-10-09:
"in case of any aux being placed like meeting coaching etc we need to specify with who and why in a comment while reserving and to reflect in the export report".

**Global constraints:** CLAUDE.md applies, with these limits:
- No engine change.
- Tests are written first. A re-pin carries its reason in the test.
- Validation fails closed: a missing answer is refused with a plain message. Nothing is cut short silently.

## Tasks
- T1 Store and DayBook:
  - `with_whom` and `why` columns on `attendance` and `activities`, added by the start-up migration.
  - `aux_details(kind, with_whom, why) -> (with_whom, why)` checks the answers:
    - Whitespace is cleaned.
    - Both answers are required for Coaching, Meeting, Training and System issue (`AUX`).
    - "With" may be at most 80 characters and "Why" at most 200.
    - Other kinds get `("", "")`.
  - `set_status`, `add_activity`, `add_item` and `book_session` take `with_whom` and `why`. They store both and add ", with X: why" to the day log text.
  - The day view carries both answers on each segment and activity.
- T2 Routes and screens:
  - Every web route that books an aux requires both answers through `aux_details`: `/day/add`, `/day/activity`, `/day/attendance` and `/day/book`.
  - Where the fields appear:
    - the "+ Add" dialog;
    - the attendance popup used by the timeline and the person popup;
    - Find a time.
  - "With" suggests the team's names; any name can be typed.
  - Both answers are shown in the person popup, the day's activity list and the handover note.
- T3 Exports: the Attendance and Activities sheets gain "With" and "Why" columns.
- T4 Browser check, screenshots, website suite, gate, package, report.
