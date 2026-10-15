# Phase AL: the owner's requests

© 2026 Omar Mokhtar. All rights reserved.

Received Thu 15 Oct 2026, about 23:15 Egypt time, after the Phase AK package.

## The owner's words

> I didn't like the green color that much
> We need to add fairness for channels now as a start during the day/week etc
> Also why consistent schedule is not being captured now from the engine run zip as we discussed previously

## 1. Email colour

The Email colour from sample ak01 (option D, `#A6D96A`) is not liked. Sample al01
(`evidence/phase_al/samples/al01_email_colour_{light,dark}.png`) puts four other colours next to the installed one.
Phone and Chat stay as they are. The status colours already use teal (covered), amber (short), red (below the floor)
and violet (over-staffed), so those hues are left out.

| Option | Email | Letter | Notes |
| --- | --- | --- | --- |
| A (recommended) | paper white `#E9E4D8` | dark, 13:1 | Phone dark, Chat mid, Email light: told apart by lightness, and no status hue |
| B | ice blue `#C9E2F2` | dark, 12:1 | light, but in Phone's blue family |
| C | deep green `#2F7D5B` | white, 5:1 | calmer, still green |
| D | brown `#8A5A3B` | white, 5.8:1 | between the amber and red status hues, but much duller |

The sample draws its letters at each stretch's middle, even under a break. The website already places them on a
break-free piece of 30 minutes or more.

Still open from Phase AK: the C letter, white on Chat `#C2549F`, measures 4.15:1, under WCAG's 4.5:1 for small text.
`#B04A90` would give 4.97:1.

## 2. Fairness for channels

What exists today. The channel planner (`webapp/channel_plan.py`, Plan channels on a schedule) has a "fair spread"
term, switched on per program in the channel setup. It reads the minutes each person had on each channel earlier in
the week and nudges them towards the channel they had least. Its weight is 1, the lowest of all: it only breaks ties
after coverage, languages, the longest stretch, break moves and channel changes. No page shows how fair a day or week
was.

Questions for the owner:

1. **What does fair mean?**
   - (a) Same share: each person's minutes on each channel close to the team's average, among people who can work
     that channel.
   - (b) Turns: nobody stays on one channel all day; the least-liked channel is passed round.
   - (c) Both.
2. **Over what?** Within the day, over the week, or both: each day fair, and the week evening out what a day could
   not.
3. **Against coverage.** When fairness costs an interval (one person short on Chat at 14:00), coverage wins
   (recommended), or fairness wins up to a limit you set?
4. **"As a start".** First step:
   - (a) A fairness view: per person, minutes and share on Phone, Chat and Email for the day and the week, with who
     is furthest from even (recommended to start).
   - (b) The planner weighs fairness more.
   - (c) Both in this phase.
5. **Who is compared?** Only people with the same channels, and the same language, against each other
   (recommended), or everyone?

## 3. The more consistent schedule from the engine run

**Root cause (found, no change made yet).**
- Since 2026-10-04 (audit F-35 follow-up), the engine never rewrites the schedule it picks.
- When the shift consistency polish makes the week steadier with no worse coverage, the engine writes the polished
  week beside it as `<id>_MORE_CONSISTENT_CANDIDATE.xlsx`. The independent validator checks it. The run's
  `OUTCOME.txt` says "A more consistent version of this schedule … use either." The test is
  `tests_staged/test_rc9_2_37_more_consistent_candidate.py`.
- The website never picks that file up. When a run finishes, `RunManager.keep_schedules` → `Schedules.ensure` keeps
  only two workbooks as versions: `*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx` ("Tool, after breaks") and the before
  breaks one (`webapp/runs.py` 121-145, `webapp/schedules.py` 158-182).
- So the steadier week is in the run's files and results zip, but it never appears as a version, on Schedules or on
  the RTA.
- Phase AF's F2 ("consistent shifts", owner 2026-10-14) was built as the rule for the RTA's own proposals: a
  proposed shift matches the person's days before and after. Taking the engine's file in was not built.

Proposed fix (TDD):
- When the run has a `*_MORE_CONSISTENT_CANDIDATE.xlsx` that the validator passed with no worse coverage, keep it as
  a third version, "Tool, more consistent".
- Show its steadiness next to the selected one: start-time movement and distinct start times, from the engine's own
  record.
- The planner picks which version is in use, as today. Nothing is set in use by itself.

Questions for the owner:

6. Should the more consistent version be **set in use by itself** when the engine passed it, or only offered
   (recommended: offered; the engine's rule since 2026-10-04 is "the planner chooses")?
7. **Runs already finished** on the server: add their more consistent version too, once, when the new package
   starts (recommended), or only for new runs?
