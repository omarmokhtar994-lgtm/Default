# Phase AF: owner notes on channels and the RTA (not built yet)

Recorded 2026-10-12, 06:37 Egypt time. The owner said: "take those as notes, don't act on them now" and "take a
note of all those points to be fixed next, along with whatever will be added as well". Nothing here is built.
The usual order applies when the phase starts: diagnose, samples for approval, then failing tests first.

The owner sent two photos of the live site:
- **Photo 1:** the RTA day view for a Monday.
- **Photo 2:** the "Who is on what" grid on Plan channels, 10:00 to 16:00.

The photos show real names, so they are not copied into the repository; rows are described by position.

## The owner's points

1. **Channel tabs at 60 minutes.** Accept Chat, Phone and Email 60 Min grids too. Today a grid whose minutes
   differ from the program's interval is refused ("... does not match the program's 30-minute interval").
2. **Email Hours logic.** A window that crosses midnight must work: 16:00 to 04:00, or 16:00 to 07:00.
   - Today every such row is refused ("the window must start before it ends").
   - Even with a same-day window, an evening shift gets Email only before midnight. Both
     `webapp/channel_plan.py:68` and `:245` cut at 1440.
   - This is option C from the 2026-10-11 answer.
3. **Red cells where nothing is needed (photo 1, Monday).**
   - The language rows ("Bilingual / French / English on the floor") show a red or orange 0 from about 04:00 to
     07:00.
   - "Needed on the floor" is blank there.
   - The owner's setup closes Saturday and Sunday nights at 04:00, so Monday 04:00 to 07:00 has no coverage and
     should not be red.
   - The owner has changed "Weekends" to "Sat - Sun" in the workbook.
   - Diagnose first which rule draws these cells. Candidates: Language Setup coverage windows and days, or the
     channel language rows.
   - Also check why the bottom of the panel shows "Bilingual on the floor" twice.
4. **Input workbook, Channel Setup.**
   - Make it more specific.
   - Give the language minimums more rows; the blank workbook has 6 (rows 15 to 20).
   - Make every column a drop-down: channel, language, times, days, active.
   - Take the language list from the languages the engine reads (Language Setup), so the channel minimums and the
     engine's language minimums add up (owner: "so they can add up").
   - Related, from 2026-10-11: Channel Setup refuses "Weekends", which Language Setup accepts as Sat + Sun. A
     drop-down removes the mismatch; the reader could accept Weekends and Weekdays too.
5. **RTA: each associate's channels for the day.** The owner could not find, on the RTA, which channel each
   person is on and when. That causes confusion when following the plan.
   - Today: the RTA has a Channels tab (warnings, fixes, Take back), and the per-person grid is on the schedule's
     Plan channels page.
   - The owner wants it visible on the RTA itself.
6. **Plan channels for the whole week.** The schedule's Plan channels page plans one day at a time. Add one
   action that plans every day of the week.
7. **Breaks when someone is alone (photo 2).**
   - Row 1, the first UK associate, starts at 10:00 and takes a break at 10:15. Nobody else is on the floor
     until row 2 starts at about 13:00, so the queue is uncovered.
   - The break should wait until a second person (here, the second UK associate) is on.
   - Also check: row 2 shows a break (B) in its first cell.
8. **No 15-minute stint before a break.** Do not put someone on a channel for 15 minutes and then a break, as
   row 1's single "A" at 10:00 before the 10:15 break does. The minimum block should hold next to breaks and
   shift starts too.
9. **Show runs, not 15-minute cells.** In "Who is on what", draw one box per stretch: an hour on Phone is one
   box, then the next channel. The view only changes where the channel changes.
10. **Export the channel plan.**
    - The same view as on screen, in Excel.
    - Perhaps one tab per day.
11. **Change channels from the RTA tab,** like breaks and the other changes:
    - with warnings and proposed fixes;
    - each change follows the RTA's existing journal, Undo and group-post rules.
12. **Open list.** The owner may add more points. Add them here before the phase starts.

## To settle with samples (not yet asked)

- **Point 1:** two possible readings:
  - a 60-minute program reads 60 Min grids;
  - a 30-minute program also accepts a 60 Min grid and splits each hour into two halves.
  - Which one, or both?
- **Point 4:** what "add up" should check. For example, warn when the channel language minimums at a time exceed
  the language's minimum on the floor, or fall short of it.
- **Point 7:** the rule for "alone":
  - only someone who speaks the same language, or anyone who can take the queue;
  - what happens when nobody else comes in before the break window ends.
- **Point 9:** whether the RTA view (point 5) uses the same runs.
