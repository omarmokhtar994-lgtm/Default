# Phase AJ: the owner's requests (2026-10-15, Egypt time)

© 2026 Omar Mokhtar. All rights reserved.

Noted from the owner's message of 2026-10-15, with one photo of the live site (RTA "+ Add", Overtime, Before the
shift, 4 h, for a 20:00 to 05:00 shift). The Phase AI package is installed on the server. Nothing is built yet:
defects get a failing test first, visual changes a sample first.

Owner, verbatim: "All good and installed / Found this bug while trying to get someone overtime before shift 4 hours /
Also we might add someone from TM or suppot members not part of the roaster to login to cover intervals they should
count in interval wise as well so we need an option to add that explaining he/she is support or tm and duration they
will logjn to save an interval"

| # | Request | Kind | Reading |
| --- | --- | --- | --- |
| 1 | Overtime before a 20:00 to 05:00 shift, 4 h (16:00 to 20:00), is refused with "Overtime has to start when the shift ends (05:00) or end when it starts (20:00)" | defect | See the root cause below |
| 2 | Add someone who is not on the roster (a team manager or a support member) who logs in to cover intervals; they count in the interval figures; the entry says whether they are support or TM and how long they log in | new | A "Cover from outside the roster" entry on the RTA: who, role (Team manager or Support), from and to; counted as staff in the intervals it covers |

## Item 1: root cause (traced, not yet fixed)

- "+ Add" offers every length up to 4 h for every kind (`ADD_LENGTHS` in `webapp/app.py`), but overtime is capped at
  2 h (`OVERTIME_MAX = 120` in `webapp/day.py`, the owner's rule from Phase O: "at most 2 hours").
- `add_activity` (`webapp/attendance.py`) reads a start more than 2 h before the shift as the next day
  (`lo += 1440 if lo < span[0] - OVERTIME_MAX`). 16:00 is 4 h before 20:00, so it became 16:00 the next day, and the
  first check failed with the wrong reason. After the shift, 4 h is refused with the right reason ("up to 2 hours").
- Before the shift with 3 h fails the same way. Every length up to 2 h works.

## Questions only the owner can answer

1. Overtime length: keep the 2 h cap (then "+ Add" offers only up to 2 h for overtime and says why), or raise it
   (to 4 h, or another number)? The rest gap between shifts is kept either way.
2. Cover from outside the roster:
   a. Who: typed as a name, or picked from the site's accounts (Team, People)?
   b. Does a person covering count as one full agent in each interval for the minutes they are logged in (part of
      an interval counts in part, as for everyone else)?
   c. Channels (Phone, Chat, Email): do they pick one channel, or count where the program needs them?
   d. Post to the Slack/Teams group like other changes (with the untick to keep it off)?
   e. Keep them out of the roster's hours, adherence and shrinkage, and list them on their own in Analysis and the
      exports?

## The owner's answers (2026-10-15, about 17:15 and 17:40 Egypt time)

1. Overtime length: "raise it to the options we do have": up to 4 h, the longest "+ Add" offers.
2. Cover from outside the roster: a. typed in; b. yes, one agent for the minutes logged in; c. they pick a channel
   when the program has channels; d. yes, post to the group like other changes; e. "Keep an option to add them or
   not like a check box to include them or not".

## Item 3 (owner, 2026-10-15, with a photo of the Timeline from 07:00)

Owner, verbatim: "One more but not showing after 00;00 the channel and phone blue color on the timeline blue color
is not seen". Kind: defect. Root cause: `channel_day._timelines` made a day's channel stretches only for shifts that
start that day and only up to midnight, so the part of a night shift after 00:00 had a stretch on neither day.
Fixed: the next day's view carries last night's stretches after midnight (the words stay with the day the shift
starts), and the 24 hours from a start join them into one stretch.

## Items 4 and 5 (owner, 2026-10-15, after installing the first Phase AJ package)

Owner, verbatim: "For the support tm cover should count in language as well so add language part, and i tried to
add 4 hours OT for an associate but it was breaking a rule of 12 hours so that stopped it it should show a warning
but still adds it"

| # | Request | Kind | Reading |
| --- | --- | --- | --- |
| 4 | Cover from outside the roster counts in the languages | change | A Language field (the program's languages, or none); the cover counts for that language row and, on its channel, for the channel's language rows |
| 5 | Overtime breaking the 12-hour rest rule is refused | change | Overtime is kept, with a warning that says the rest it leaves: on the page, in the + Add preview and in the day's log |
