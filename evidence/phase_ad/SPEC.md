# Phase AD spec: break rescue, cancel, bulk changes, undo and held group posts

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-10-11 (Egypt time), verbatim:

> Yes for your question and I need option to delete break as well totally if we are going ro cancel a break for
> someone, also i need to add a feature to group breaks and fail one interval down to 50% if that will rescue other
> intervals that should be another button away from fix breaks maybe next to it in case of emergency lets say we are
> aiming for a day coverage of 90% and interval is acceptable at 90% so we can collect some breaks in 1-2-3 intervals
> and fail those intervals to save like 6-8 other intervals but not to drop more than 50% if u got my point but this
> can be done maximum for 3 intervals not more and in order to save other intervals but that doesn't mean that sll
> breaks should be only for those 3 intervals but mainly to bulk in them and rest to be distributed to achieve our goal
> this can be done for interval wise only not weighted volume , also need a button to undo last move or 2 if needed
> like if we did fix breaks and i didn't like the view i can just undo same goes for the emergency button as well and
> any moves maybe max 2 moves back or something, also i need to havee the ability to bulk delete or change breaks for
> several associates at the same time, and after bulk moves or fix breaks or emergency button notification shouldn't
> be sent automatically instead a button should show up at the top of the page with a send button for the last bulk
> move if it's already pressed and someone is pressing it again for the same action should show up a popup that
> notification was sent for this move already are u sure u wanna send it again with same data ? Or no bulk moves done

Answers to the five questions: "First 2 points okay" (a cancelled break asks for a short reason, kept on the site
and in exports, not posted; Undo covers only your own last 2 changes); "3rd for full day based on current situation
as well and what we have lost by the time it's being pressed" (the 3-interval limit is for the whole day and counts
the intervals already lost before the press); "4 yes" (undoing a change already posted offers to send the
correction); "Yes as recommended" (no day-goal setting: as many intervals at the target as possible with the fewest
moves); "Also for bulk actions we can remove bulk of breaks". Samples 01 to 06 (`samples/`) then approved: "Go".

## What is built

1. **+ Add when nobody is on shift** (sample 06): opens on Overtime for the person whose shift starts right after or
   ends right before the interval, placed to cover it.
2. **Cancel a break** (sample 03): "Cancel break" in the break dialog asks why, then cancels; the person stays on
   the floor; Back to plan or Undo brings it back; the dialog's close button is "Close".
3. **Undo** (samples 05a, 05b): your own last 2 changes on this LOB's day, newest first, one at a time; a change
   that someone else changed afterwards is not undone and says why.
4. **Held group posts** (samples 05a, 05b): Rescue the day, Fix breaks and Change several breaks never post by
   themselves; a bar at the top of the RTA offers Send to group; sending a change already posted asks first;
   undoing a posted change offers Send the correction. Single changes post as before.
5. **Change several breaks** (sample 04): people, which break (Break 1, Lunch, Break 2 or every break not started),
   and Cancel (with a reason), Move by the same amount, Set the same time or Back to plan; Show the effect, then one
   apply.
6. **Rescue the day** (sample 02): re-places breaks not started to get the most intervals to the week's interval
   target, giving up at most 3 intervals in the whole day (intervals already lost before the press count), never
   below 50% of demand, only when it rescues more than it gives up; interval compliance, every interval the same.
7. **Fix the rest of the day's breaks** keeps its search; its apply becomes one change for Undo and is held from the
   group like the other bulk changes.
