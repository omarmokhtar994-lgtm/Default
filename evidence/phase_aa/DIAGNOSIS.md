# Phase AA diagnosis, 2026-10-10 Egypt time

Owner, during Phase Z:

> Overtime can be before or after shift
>
> Cant find a way to delete uploaded schedule unneeded
>
> Create as well more tabs with easier view for different things such as schedule i can review any uploaded schedule
> not necessarily the last one maybe with a filter per week so we can choose the week and compare between all
> shedules and confirm on which one we will use along with same options in week view as well

Read from the code and checked on the Phase Z review server (made-up "Associate NN" data). Nothing was changed for
this diagnosis.

## 1. Overtime before the shift: the rule allows it, the form does not offer it

- The rule already accepts both: overtime must end when the shift starts or start when it ends, up to 2 hours,
  keeping the rest gap (`webapp/attendance.py`, `add_activity`).
- The **Overtime and VTO** tab and the board's **Add cover** panel already offer both sides ("Before the shift" /
  "After the shift").
- The **+ Add** dialog does not. For overtime it asks only **From** and **Length**, and From is the interval that was
  clicked. From a person's own panel ("+ Add something") From is their shift start, so overtime from there is
  08:00 to 09:00, inside the shift, and is always refused with "Overtime has to start when the shift ends or end
  when it starts". From any interval during the shift it is refused the same way. It only works if someone types the
  exact minute the shift starts minus the length, or the minute it ends, and nothing on the screen says so.

## 2. An unneeded upload cannot be deleted

- There is no delete for a run or an uploaded schedule anywhere on the site. Schedules are only removed by the
  automatic clean-up 13 months after their week (`ScheduleBook.cleanup`, `KEEP_DAYS = 395`), and run files after 30
  days.
- So a wrong or test upload stays in the week's schedules list, on Home's Runs table and in the menu for 13 months.

## 3. Reviewing any schedule of any week, and comparing them

- The menu's **Schedules** opens the schedule in use for the program's newest week (Phase Z). There is no way to pick
  another week there; older weeks are reached only through Home's Runs table or the Week page's arrows.
- Phase Z's week list shows a week's schedules side by side with one figure each (intervals fully covered after
  breaks) and Set in use. It does not compare what matters when choosing: intervals at the week's target, hours short
  and above demand, people and hours, rules broken, breaks planned, channel needs.
- The **Week** page shows only the schedule in use for the week; another schedule's week view
  (`/schedules/<id>/week`) is reached only from that schedule's own page.
