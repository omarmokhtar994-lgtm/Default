# Part-timers, an 8.5 hour shift, hours worked, sites and the months ahead

© 2026 Omar Mokhtar. All rights reserved.

Phase BL (owner, 2026-11-07). Everything here is optional: leave a column or a setting empty and the program behaves exactly as before.

## In the input workbook (the Schedule sheet)

Add any of these four columns to the roster, next to the names. Headers are not case sensitive.

| Column | What it means |
|---|---|
| `Shift Length` | Hours, for example `8.5` or `9` or `5`. That person is only given shifts of that length, every day, in every step of the engine. The Shift Library must hold shifts of that length, and `Allowed Shift Durations Hours` must list it (for example `9, 8.5`). If not, the check says so by name before anything is solved. |
| `Employment Type` (or `Type`) | `Full time` or `Part time`. A part-timer's `Shift Length` is reserved for part-timers (see below); the other rules come from the other three columns. |
| `Off Days` | How many days off that person has in the week, 0 to 6, instead of the usual 2 (3 on the 11H/3OFF pattern). Days of leave still come out of the same seven days. |
| `Breaks` | How many breaks on a shift of that person's `Shift Length`: the first N breaks of the break set that length would have had. It needs `Shift Length` on the same row. Two rows with the same `Shift Length` must have the same `Breaks`, because break sets belong to a shift length (anyone else who works a shift of that length gets the same set). The break set for a length can also be written as an instruction row, as before. |

Two things to know when you mix lengths. A shift length that a `Part time` row names is reserved for part-timers: someone with no `Shift Length` of their own is not given it. Someone with no `Shift Length` may be given any other length the library holds, so to keep a full-timer to 9 hours (and not 8.5) give them `Shift Length` 9.

A value that cannot be read is refused by name (`HARD_INVALID_SHIFT_LENGTH`, `HARD_INVALID_ASSOCIATE_TYPE`, `HARD_INVALID_OFF_DAYS`, `HARD_INVALID_BREAKS`, `HARD_BREAKS_NEED_SHIFT_LENGTH`, `HARD_BREAKS_CONFLICT`, `HARD_BREAKS_EXCEED_SET`, `ASSOCIATE_SHIFT_LENGTH_NOT_IN_LIBRARY`).

The independent validator also checks `Shift Length` (`SHIFT_LENGTH_VIOLATION`). The A/B for the engine change is in `evidence/phase_bl/ab_columns_blank.md`: with the columns blank the first-stage model is identical to the one before.

## On the Volumes pages

- **Settings, Hours worked.** Per channel and weekday: when it opens and closes (`09:00` to `21:00`; `22:00` to `06:00` counts for the day it starts), or closed. Inside the hours every interval needs at least the minimum cover (phone and chat), even with no volume; outside them nobody. A day left empty is as before.
- **Settings, Sites.** Add the sites (and the LOB each is scheduled in), then rules: for a channel, on some days, between two times, the share each site takes (adding up to 100). Time no rule covers goes to the first site and is listed. Each site then has its own forecast, people needed and requirement tabs on the Forecast tab (the site buttons and the download buttons); upload each site's requirement tabs into that site's LOB run.
- **Events and holidays.** An event can now close a day or reduce its hours (Hours on those days), with the change in contacts left empty. A holiday in the past leaves its week out of the pattern the weekdays are learned from. Dates are typed for each year, because holidays move.
- **Email.** History may be a table of day totals (Date, Emails, optional AHT). With hours set, a day's email work is spread over the open intervals, so none is lost to the closed ones; with no hours set it is worked out per interval as before.
- **Months ahead.** A new tab: months, weeks and the days of a chosen week, per channel and per site, each with a range and how it was worked out (learned from the history, no seasonal pattern yet, your typed index, or trend only). A year of history learns the season; under a year the weeks the history has not seen are the trend alone, with a wider range, and you can type a seasonal index for those months; under 26 weeks only 8 weeks ahead are shown. Your year-over-year rate, events, promotions and holidays are applied on the days they touch.
