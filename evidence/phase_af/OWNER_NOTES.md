# Phase AF: owner notes, consolidated (not built yet)

Notes from the owner's messages of 2026-10-12 and 2026-10-14, with the owner's answers merged into each point.
Consolidated 2026-10-14 at the owner's request ("read all above and consolidate points"). Nothing here is built.
The usual order applies when the phase starts: diagnose, samples for approval, then failing tests first.

The owner's earlier photos (the RTA day view for a Monday, and the "Who is on what" grid on Plan channels) show
real names, so they are not in the repository; rows are described by position. "(was N)" gives the point's
number in the earlier version of this file.

## A. Input workbook and settings

- **A1. Channel tabs at 60 minutes, both ways (was 1).**
  - A 60-minute program reads Chat, Phone and Email 60 Min grids.
  - A 30-minute program also accepts 60 Min grids, splitting each hour.
  - Today a grid whose minutes differ from the program's interval is refused.
- **A2. Email Hours past midnight (was 2).**
  - A window such as 16:00 to 04:00 or 16:00 to 07:00 works.
  - Today it is refused ("the window must start before it ends").
  - Today an evening shift also gets Email only before midnight: `webapp/channel_plan.py:68` and `:245` cut at
    1440.
- **A3. Channel Setup: specific, roomy, drop-downs (was 4).**
  - More rows for language minimums. The blank workbook has 6 (rows 15 to 20).
  - Every column is a drop-down: channel, language, times, days, active.
  - Languages come from Language Setup, the list the engine reads.
  - **Must add up:** a channel's language window sits inside that language's coverage in Language Setup, and
    anything else is refused. The owner's example: English covered 16:00 to 07:00 rules out a channel row of 15:00
    to 08:00.
  - "Weekends" and "Weekdays" read the same as in Language Setup (Weekends = Sat + Sun). Today Channel Setup
    refuses "Weekends".
  - The sheet states that Days means the day a window starts. For example, Mon - Fri 16:00 to 07:00 does not
    cover Sunday night.
- **A4. The operating day's start (was 13).** For shifts past midnight (for example 16:00 to 07:00), the
  operating day's start is set in the program's settings or in the input workbook. D1 uses it.
- **A5. Time zone at upload (was 17).** Choose the schedule's time zone when uploading, and change it after
  upload. D5 shows other zones.

## B. Channel planning rules

- **B1. Plan channels for the whole week (was 6).** One action plans every day. Today Plan channels plans one
  day at a time.
- **B2. No break while someone is alone (was 7).**
  - Hold the break until a second person who can take the queue is on: same language preferred, otherwise
    anyone who can take it.
  - If nobody comes before the person's shift ends, plan breaks normally.
  - Nobody waits more than 4 hours for the first break, even when alone.
  - The owner's example: the first UK associate starts at 10:00 and breaks at 10:15, alone until the second UK
    associate starts at about 13:00.
  - Confirm this reading with the sample.
- **B3. No 15-minute stint before a break (was 8).** Never put someone on a channel for 15 minutes and then a
  break. The minimum block holds next to breaks and shift starts too. The owner's example: a single "A" at 10:00
  before the 10:15 break.

## C. Channel views, changes and export

- **C1. Runs, not 15-minute cells (was 9).** One box per stretch: an hour on Phone is one box, then the next
  channel. This applies on Plan channels and on the RTA (owner: yes).
- **C2. Each associate's channels on the RTA (was 5).**
  - Who is on which channel, and when, visible on the RTA itself, drawn as runs.
  - Today the RTA's Channels tab shows warnings, fixes and Take back. The per-person grid is only on Plan
    channels.
- **C3. Change channels from the RTA (was 11).**
  - Like breaks and the other changes, with warnings and proposed fixes.
  - Each change goes through the RTA's journal, Undo and group posts.
- **C4. Export the channel plan (was 10).** The view as on screen, in Excel, perhaps one tab per day.

## D. RTA timeline and views

- **D1. Operating day or calendar day (was 13).** A switch shows the operating day from its start (A4), for
  example 16:00 to 07:00 the next morning, or the calendar day, 00:00 to 23:59.
- **D2. Hover on a shift bar (was 14).** Shows:
  - shift start, end and length;
  - time left until logout;
  - time worked so far.
- **D3. Hover on a break (was 15).** Shows:
  - hours since the last break;
  - hours from shift start to that break.

  It also works in the interval view.
- **D4. Drag a break to move it (was 16).**
  - It snaps to 5-minute steps.
  - A confirmation asks "Change <break> from Y to Z?" and lists any rule the new time breaks (gap, window,
    language or channel minimum) before Yes or No.
  - The break dialog stays as the keyboard path, and the strict CSP stays.
- **D5. View in any time zone (was 17).** Every tab can show another zone. For example, a schedule uploaded in
  Egypt time is shown in EST on the RTA.
- **D6. A quick day summary on the RTA (was 22).** Today there is one summary line: on shift, short and above
  demand, language gaps, channel warnings. The owner wants a quicker view of the day.

## E. Shrinkage and statuses

- **E1. Out-of-office shrinkage on the RTA (was 20),** next to in-office shrinkage.
  - Which statuses count as shrinkage, in office and out of office, is a program setting.
  - The admin or a supervisor maps it.
- **E2. Task status (was 21).** Records "with who" and "why", like the other aux.
- **E3. Public holiday status (was 21).** Works like Sick or Unplanned.
  - It is not shrinkage for Sutherland (the company), but it is for the client.
  - So out-of-office shrinkage has two kinds: Sutherland and client.

## F. Saving the day and the week

- **F1. Proposed day-off cancellations (was 18).**
  - The RTA proposes which days off to cancel, day by day. For example: "2 people from 16:00 and 1 from 22:00
    save the day".
  - If that is not enough, it proposes the overtime needed per interval.
- **F2. "More consistent" (was 19).** The owner's words: "also more consistent should show up same as after
  break and before break". The meaning is not yet confirmed (see G).
- **F3. Known absences for the rest of the week (was 23).**
  - Enter on the RTA the absences already known for later days, such as unplanned leave or sick.
  - From them, show a summary, perhaps on Week, of the overtime needed per day and the days off to cancel.
- **F4. Placement (was 24).** Some of this can sit on Overview instead of the RTA.

## Defects to diagnose first

- **X1. Red cells where nothing is needed (was 3).** On a Monday, the language rows ("Bilingual / French /
  English on the floor") show a red or orange 0 from about 04:00 to 07:00.
  - "Needed on the floor" is blank there.
  - The owner closes Saturday and Sunday nights at 04:00.
  - Find which rule draws these cells: the Language Setup coverage windows and days, or the channel language
    rows.
- **X2. "Bilingual on the floor" listed twice (was 3)** at the bottom of the same panel.
- **X3. A break in a shift's first cell (was 7).** In the photo, the second UK associate's row starts with a
  break.

## Still to settle with samples

- **F2:** two possible readings:
  - overtime proposals come as whole blocks before or after a shift (as + Add's overtime already does), not
    scattered intervals;
  - the proposals show the before-and-after effect, the way break changes do.
- **A5 and D5, zones:** named zones (Africa/Cairo, America/New_York), so summer time follows the date: Egypt is +2
  or +3, US Eastern is EST or EDT.
- **A5 and D5, day edges:** in another zone a day's edges move. A Cairo Monday starts on Sunday afternoon in New
  York. Which day does a page show?
- **F1:** which days off may be cancelled, keeping the weekly-hours, rest-day and days-in-a-row rules.
- **E1 and E3:** the starting mapping of statuses to shrinkage, and whether the RTA shows Sutherland and client
  shrinkage side by side.
- **B2:** confirm the reading of the 4-hour rule.

## Suggested grouping when the phase starts (for the owner to decide)

1. **Defects X1 to X3, and A2:** wrong results today.
2. **Workbook and planner:** A1, A3, B1, B2, B3.
3. **Channel views, export and RTA channel changes:** C1 to C4.
4. **RTA timeline:** D1 to D4, D6.
5. **Time zones:** A4, A5, D5. These touch every page, so they get a design of their own.
6. **Shrinkage, statuses, day-off and week outlook:** E1 to E3, F1 to F4.

## From the 2026-10-11 workbook review (your side, no website change)

- Email Hours' short windows (Sun and Mon rows) and the grids' short nights (Sun and Mon columns) look one day
  apart; check which is right.
- "Bilingual" counts only for people whose language is Bilingual, or whose Language Setup row covers it.
- The English rows with a minimum of 0 do nothing.
- Chat is blank from 16:00 to 18:30 while Phone needs people from 16:00; check that this is intended.
