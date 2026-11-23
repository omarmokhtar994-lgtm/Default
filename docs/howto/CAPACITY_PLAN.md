# The capacity plan (Phase BS)

Volumes, **Capacity** (after Months ahead). Per channel: how many people you need each week ahead against how many you will have, and the class
that closes the first gap.

## What you type
- **Head count today**: the people you have on the channel now, as full-time equivalents. Required: the number of people on the newest schedule is
  shown as a hint and is never used for you.
- **Hours a week per person** (40 if empty), **attrition, % a month** (0 if empty: type your program's own), **training weeks** (4), **nesting
  weeks** (2) and **output while nesting** (50 %).
- **Classes**: a start date (a Sunday) and the number of people. A class counts for nothing in training, for the nesting output while nesting, and
  in full after; it loses people to attrition like everyone else. A class started up to 26 weeks ago still counts.
- Everything is checked before anything is kept; a wrong figure is named and nothing changes.

## How it is worked out
1. The expected contacts of each week come from Months ahead (trend, season, events, holidays, your year-over-year rate).
2. Each day is spread over the intervals the way the last clean weeks were, and the people needed on the floor are counted as on the Staffing
   tab: Erlang for phone, Erlang with concurrency for chat, work over time for email, with the opening hours and minimum cover.
3. Floor hours over (hours a week x (1 - shrinkage)) is the people needed on the payroll. Shrinkage is the channel's, from Settings.
4. Available = head count, shrunk each week by attrition (monthly rate taken weekly), plus the classes.
5. The first week short gets a suggestion: a class of enough people (allowing for attrition during training and nesting), started early enough to
   be ready that week. If that start is already past, it starts next week and the page says it will be late.

The range beside Needed follows the range of the contacts on Months ahead. **Download the plan (Excel)** holds the same table, the figures used
and the suggestion.

## Limits
- With under half a year of history Months ahead (and so the plan) reaches 8 weeks at most.
- One interval shape (the latest weeks) is used for every week ahead.
- Handle time is the channel's (Settings, or the volume-weighted one of the recent weeks).
