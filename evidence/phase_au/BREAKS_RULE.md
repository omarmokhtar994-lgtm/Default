# © 2026 Omar Mokhtar. All rights reserved.
# Break shape on the website's auto-breaks (owner, 2026-10-21)

Owner: breaks should normally be built as: first break 2 h up to 3.5 h after the shift starts; lunch after it, 2 to 3 h
from the first break; the last break after lunch and before the last hour of the shift. It may deviate later for
interval purposes. Answers: apply to the website auto-breaks (Suggest / Plan breaks) first, engine untouched; a preferred
shape that bends for intervals, not a hard rule.

Readings, taken as defaults (say if wrong):
- "2 to 3.5 h until the first break" = the first break starts 120 to 210 minutes after the shift starts.
- "2 to 3 h from the first" = the lunch starts 120 to 180 minutes after the first break ends (the work between them,
  as the engine's gaps count).
- "after lunch and before the last hour" = the last break starts after lunch ends and ends at least 60 minutes before the
  shift ends. Breaks between lunch and the last keep the engine's preferred gap.
- Shifts with no lunch in their break set: the first-break and last-break parts only.

## Pre-registered rule (written before any code)

Measured on the website's ready test week (every day, `Suggest` with nothing typed), old placement (arm A) against the new
(arm B). Accept B only if all hold:
1. Every placement still passes the engine's validator break checks (no BREAK_* failure) and typed breaks are kept as typed.
2. Shape fit: the share of people whose breaks all fit the shape is higher in B than in A, and every break that can fit
   (some time inside the shape is inside the hard rules) does.
3. Interval cost: the day's tightest buffer (hours, as RTA shows it) in B is not lower than in A by more than 0.25 h on any
   day, and the number of placements with more people on break than allowed is not higher.
4. A break whose shape window has no allowed time is placed as before (bends), not left empty.

## Result and owner decision (2026-10-21)

Arm A (old): 15 of 184 people fit the shape; tightest buffers by day 1.75, 3.25, 3.0, 2.75, 2.75, 2.0, 1.75 h.
Arm B1 (rule 3 as written, 0.25 h): 56 of 184 fit; buffers 1.75, 3.0, 3.0, 2.75, 2.75, 2.0, 1.75 h. The concurrent-break
limit (4 at once, 30%) lets only about 24 breaks start inside one 90-minute window, and the buffer ordering put the
floor ahead of the shape almost always.
Arm B2 (hold the shape while the interval stays at or above the need): 184 of 184 fit; buffers 1.5, 2.5, 3.0, 2.75, 2.25,
1.75, 1.5 h: at most 0.75 h below arm A, always at least 1.5 h above the need.
The owner picked B2, so rule 3 is amended to "not lower than A by more than 0.75 h and still above the need". Rules 1, 2 and
4 hold: the validator break checks still pass (tested), and typed breaks are kept.

## Cushion (owner, 2026-10-21: "keep at least 10 minutes in the interval")

Suggest's "safe" now means what the autopilot and the RTA colours mean (`day.at_target`): 100% of the need, or at the
target and at least `CUSHION` (10) person-minutes over it. The shape is held while a break leaves its intervals safe;
only when no allowed time does, a time within 0.25 h of the best is taken. Re-measured on the test week: 184 of 184 fit;
tightest buffers by day unchanged (1.5, 2.5, 3.0, 2.75, 2.25, 1.75, 1.5 h); no interval under the target.
