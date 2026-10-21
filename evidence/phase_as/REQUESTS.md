# Phase AS: break change requests, coaching requests, and the impact the RTA sees

© 2026 Omar Mokhtar. All rights reserved.

Received Wed 21 Oct 2026. A visual sample comes first: `samples/as01_break_and_coaching_requests.html` (light and dark).

## The owner's words

> I want to add in agent view that they can see when their breaks is scheduled and they can request to change their
> breaks to different time and it has to be approved by RTA on system as well this can be a separate tab or inside RTA
> view for the RTA to accept or reject the break time change and this option should be for the running day only but can
> exceed 00:00 so if the associate is scheduled from 22:00 to 07:00 then it can allow him from today 22:00 to 07:00 next
> day max. Also we need to create an option for team managers/departments to request coaching for a specific associate
> or associates and they go for RTA approval as well, or if they have access to RTA tab they can approve their own
> request as well. While RTA is approving any of those he should see the impact in case he approved that on intervals.
> Also associate while choosing a different break time he should see the intervals which will be most probably approved
> with high buffer then moderate buffer; as for low buffer it should show a warning that this will most probably be
> rejected as no availability in that interval.

## What the site already has that this builds on

- The RTA's break advice (`day.advice`): for a break moved to a time it names the gap warnings and the buffer of the
  tightest interval the break touches (staff-hours above or below the need), ranked best first.
- The RTA's "Find a time" for coaching (`meeting_slots`), and the day's records for a break move and an activity.
- Requests, with a first approval and the RTA's approval, for leave and swaps (`webapp/leave.py`, `swaps.py`), and the
  waiting count on the RTA.

## Proposal in the sample (owner decides)

1. **Break change (associate).** My week shows today's breaks. On the running day only, up to the end of the shift (past
   00:00 when the shift runs past it), an associate picks another start for one break from the legal times (the
   program's gaps between breaks). Each time shows High, Moderate or Low buffer. Low shows "likely to be rejected, no
   availability". The request goes to the RTA; the associate can cancel it until it is decided.
2. **Buffer words.** From the interval the move touches, after the move, in people on the floor against the need:
   High = at least one person above the need; Moderate = at the need, under one above; Low = below the need.
3. **Coaching (team managers, and departments if they get sign-ins).** A form for one or more associates, a day (the
   running day, or later days), a length and a time; each time shows the buffer for all picked people together.
4. **RTA.** A Requests tab section for break changes and coaching, each with the intervals before and after and the
   buffer words. Approve makes the break move or the coaching block on the day (with the usual checks); Reject needs a
   reason the requester sees. A requester who has RTA rights approves their own coaching request.

## Questions for the owner

1. Break changes: which breaks may be changed (all of them, or short breaks only, lunch too)?
2. Departments (Quality, Training and the like) are contacts in the "With" lists, not accounts. Do they get sign-ins
   (a new role), or does a team manager send the coaching request for them?
3. Coaching: only the running day like the break change, or also later days?
4. Buffer thresholds: is "one person above the need = High, at the need = Moderate, below = Low" right, or should
   High be more (two people, or a percentage of the need)?
