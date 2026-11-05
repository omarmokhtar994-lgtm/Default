# GDI week of 18 Oct: why English, Bilingual and French got 23:00 to 08:00 and 01:00 to 10:00 starts

© 2026 Omar Mokhtar. All rights reserved.

Owner's question (2026-10-21): the engine scheduled some associates 23:00 to 08:00, and in other versions 01:00 to 10:00,
"despite all settings in the input sheet is refusing that for English, bilingual and French". Files: the input workbook
(version 5) and the engine's after-breaks schedule. The engine is protected and was not changed.
Real names are in the owner's files only; none are copied here.

## What the input says (read from the workbook, both files carry the same settings)

- **Instructions, "Language Working Window": blank.** The engine reads blank as OFF (`language_working_window_mode`
  defaults to "OFF"). The engine's own help says: "OFF keeps Coverage Start/End as a coverage minimum only (default).
  MINIMUM_ROWS also bounds working hours for language rows with a minimum >= 1. ALL_ROWS bounds every active row."
- **"Allowed Shift Start Window": absent.** The engine's contract sheet says "Unrestricted" and "Legal Shift Count 24".
- **Shift Library and Shift Catalog list every hourly 9 h start**, including 23:00 - 08:00, 00:00 - 09:00 and 01:00 - 10:00.
- **Language Setup:** English, French and Bilingual: coverage 16:00 to 07:00 on weekdays, 16:00 to 04:00 on weekends,
  minimum 1 for English and French, 0 for Bilingual. UK: all day weekdays, 10:00 to 04:00 weekends, minimum 1.

So nothing in the input refuses those starts. With the window blank, the Language Setup hours only say when a language
must be covered; they do not say when a person of that language may work.

## What the engine produced (after-breaks schedule)

23:00 starts: Bilingual 5 person-days (2 people), French 1 person-day, UK 3 person-days. 01:00 starts: UK 3 person-days.
No English start at 23:00 or 01:00 in this version. UK is a 24-hour language, so its late starts are allowed on any reading.

## Two things the owner needs to know

1. **To limit when a language works, set Instructions, "Language Working Window" to ALL_ROWS** (or MINIMUM_ROWS).
   The website's New schedule form already has this option (`--language-working-window`).
2. **Even then, the window limits when a shift may START, not when it ends** (engine docstring of
   `shift_within_language_window`). A 16:00 to 07:00 window contains 23:00 and 01:00, so those starts stay legal.
   To forbid them, the window must end earlier for starts (for example 16:00 to 22:00), which would also change the
   coverage the Language Setup row asks for. A start limit for everyone is the separate "Allowed Shift Start Window".

## Check runs (2026-10-21, scratch copies of the owner's input, Quick, before breaks only; none are in the repository)

1. **The ALL_ROWS run** was stopped after more than an hour (the machine was busy). The start-window arithmetic above
   is from the engine's own rule, not from that run.
2. **Coverage Split, group written "English, UK":** four variants (exclusive or not, ratio 1 or blank, blank staffing
   allowed) all gave "No schedule satisfies all hard rules together". Cause, from the engine log: "English, UK cannot
   cover its own window: 0 eligible associates". The sheet finds a group's members by a single language name from the
   "Can Cover Languages" lists, not by the "English, UK" label of the Coverage Group column.
3. **Control (the unmodified input):** still searching after 25 minutes, so the input itself is feasible.
4. **Coverage Split, group written "UK", 07:00 to 16:00, ratio 1, Exclusive Yes, Active Yes:** RELEASABLE in 15 minutes.
   Starts by language in the best before-breaks schedule: English 16:00 to 22:00 only, French 16:00 to 22:00 only,
   Bilingual 16:00 to 22:00 only (no 23:00, 00:00 or 01:00 start for any of the three); UK and Trilingual keep the late
   and early starts (UK 23:00, 01:00, 03:00, 07:00 to 13:00; the one Trilingual person 23:00). Coverage before breaks:
   135 of 140 active intervals at the 100% target, all 140 at the 80% floor.

Row that works: Coverage Split sheet, below the grey help row: `UK` | 07:00 | 16:00 | 1 | Yes | Yes.
Catches: no days column (all 7 days); Trilingual belongs to the UK group, so that person may still start late; with
Language Working Window ALL_ROWS the UK weekend window (10:00 to 04:00) would clash with a 07:00 start on weekends.
