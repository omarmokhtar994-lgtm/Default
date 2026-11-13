# The forecast: interval, time zones, hourly history and the methods (Phase BM)

The Volumes page reads as three steps: **1. Data** (what really came in), **2. Forecast** (the week's contacts, from your number), **3. Staffing**
(the people needed and the files the schedule reads). Months ahead, How we did and Settings follow.

## Hourly history
- A file whose rows are an hour apart is taken: each hour is shared evenly over the program's intervals, and the check says so.
- A 30-minute sheet with a number on the hour and zero on every half hour is read the same way (at least six hours of volume in the day).
- Days already held like that are listed on the Data tab ("N Phone days look hourly"). One press shares them; every day's total stays the same.
- A real half-hourly day is left alone: one non-zero half hour is enough to keep it as it is.

## Every 30 or 60 minutes
- Forecast, Staffing and How we did have an "Every" picker: the program's own interval, and 30 and 60 minutes where they are coarser.
- Contacts are added up; people needed is the larger of the intervals inside (the hour must cover its busier half); the service level is weighted
  by the contacts. The downloads follow the choice.
- The requirement tabs for the schedule stay at the program's interval.

## Time zones
- Volumes are kept in the program's zone (Settings, "The volumes are kept in"). Every tab says which zone it shows.
- "Show times in" on Forecast, Staffing and How we did reads the page in another zone. It changes nothing that is kept and needs no right to edit.
- A forecast in another zone takes the hours past the week's edge from the forecasts saved for the weeks before and after; where none is saved, this
  week's own pattern stands in, and the page says which.
- How we did in another zone reads the real days either side of the week. Its staffing lines stay in the program's zone, like the schedule.
- Data: "Times in" on each upload and on the typed grid moves the numbers into the program's zone when they are saved.
- Hours worked: "Hours typed in" on Settings moves the hours into the program's zone by today's difference between the two zones. Check them again
  after the clocks change. If two days' hours would land on one weekday, type them in the program's zone.
- The requirement tabs are always in the program's zone. Months ahead works in days and weeks and stays in the program's zone.

## How well each method did
- Under "Help with the number" the forecast shows a table: five ways to work out the week from the history (the trend, the last four weeks, last
  week, the same week last year grown, and the middle of the others), what each says for this week, and its average miss on your own last weeks
  (each week worked out from the weeks before it only).
- "Use this number" puts a method's number into the box. Nothing is used unless you take it; the total is yours.
- The suggestion itself stays the trend. Two rules for taking the best method automatically were written down first and tested on made-up
  histories; both failed (`evidence/phase_bm/methods.md`), so the site shows the evidence and leaves the choice to you.
- Unusual weeks (far from the line through the others) are left out of the test and named under the table.
