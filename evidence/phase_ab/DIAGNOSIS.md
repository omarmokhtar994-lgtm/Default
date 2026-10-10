# Phase AB diagnosis: Teams and Slack group posts, 2026-10-10 Egypt time

Owner, 2026-10-10: "Start the Teams/Slack notifications now". Earlier asks this builds on: "send automatrd
notification/email/slack or teams messages based on specific choices we do for example. In case of break change to
send notification to the associate with his/her break change" and "For teams and slack on a group chat would this be
an easy setup ?"

## What the website does today

- Nothing leaves the website. There is no notification, mail or chat code anywhere in `webapp/` (searched for
  notif, webhook, smtp, urlopen and requests.post: no match; "slack" appears only as spare hours in `results.py`).
- Every change an RTA makes is already written to one place: `store.add_day_log(program, shift_date, associate,
  what, user_id)`. Its nine callers are all in `webapp/attendance.py` (`DayBook`):

  | Caller | What it writes (examples from the test server) |
  | --- | --- |
  | `move_break` | "Lunch moved 12:15 to 12:45", "Lunch back to plan (13:00)", "... (autopilot)" for Plan breaks automatically |
  | `add_activity` | "Overtime 17:00 to 18:00", "VTO ...", "Break ... added", "Coaching 14:00 to 14:30 (billable), with Lina: Call review after a complaint" |
  | `set_status` | "Sick", "Unplanned leave", "Late, arrived 09:20", "Left early at 15:00", aux for the whole shift |
  | `_call_in`, `_cancel_call_in` | "Day off cancelled: called in 08:00 - 17:00", "Call-in cancelled: back to the day off ..." |
  | `cancel_activity` | "Cancelled: Overtime 17:00 to 18:00" |
  | `channel_move`, `cancel_channel_move` | "Chat from 10:00 to 11:00 (was Phone)", "... taken back" |

- The RTA shows these lines under "Changes today" (`day.html`, `page.log`), with who made them and when.
- The `what` text of an aux carries its Why after a colon (`with_text`). A group post must not carry it, so posts are
  built from the parts, not by cutting the text.
- The day log has no kind column, so today a sender could tell a break move from a coaching only by reading the text.
  A kind recorded next to each line (a new column, added the way `store.py` already adds columns) makes the rule
  "which changes post" exact.

## What the server allows

- Outbound HTTPS works from the server: Caddy fetches its certificate over it, and the Oracle security list and
  `install.sh` only open inbound ports. `scheduler-web.service` has no outbound address filter.
- The service runs one process (waitress, 8 threads) that already runs background threads (`runs.py`: run workers and
  the cleaner). A sender thread fits the same pattern; what it has sent lives in the database, so a restart loses
  nothing.

## How a group link works (from the earlier answer, still current)

- Slack: an Incoming Webhooks app gives one link per channel (`https://hooks.slack.com/services/...`). Private
  channels work; group DMs do not.
- Teams: the old Office 365 connectors are retired. In the channel: More options > Workflows > "Send webhook alerts
  to a channel". The link is on `*.logic.azure.com` or, for newer flows, `*.api.powerplatform.com`. Posts appear from
  "Workflows". The flow belongs to whoever made it, so a shared account is safer.
- Anyone holding a link can post to the group, so a link is a secret. Project rule: "Notification secrets ... live
  only on the server, never in the repo or chat." Pasting it into an admin-only page stores it in the server's
  database, which keeps it on the server. The page shows only its last four characters after that.

## Proposed (samples 01 to 04, made-up "Associate NN" names, drawn from the test server's real log)

1. **Group post** (`samples/01_group_posts.png`): one post per LOB, two minutes after the last change, listing what
   changed, who changed it and a link that opens the RTA on that day. A change undone within the wait is left out.
   Sick and unplanned leave and the Why of an aux are never posted.
2. **Notifications page** for admins, under Manage (`samples/02_notifications_page.png`): every LOB with where it
   posts, On / Preview only / Off, which changes post, the wait, Save and Send test message, the last post as the
   group saw it, and recent posts with their result. How to get a link from Teams or Slack is on the page.
3. **The RTA** (`samples/03_rta_changes_today.png`, `samples/03b_break_dialog_tick.png`): each line under Changes
   today ends with Waiting, Posted to Teams and the time, or Not posted and why. The break dialog and + Add carry one
   tick, set by the LOB's rule, to leave a single change out.
4. **Optional morning post** (`samples/04_morning_breaks_post.png`): the day's planned breaks, by shift, at a time
   the admin picks.

## Safety in the build

- A link is accepted only over HTTPS and only on `hooks.slack.com`, `*.logic.azure.com` or
  `*.api.powerplatform.com`, checked when saved and again before each send; no redirects are followed. This keeps the
  website from being pointed at its own network.
- Links never appear in pages after saving, in exports, in the activity log or in error text. A failed post records
  the group's answer code and a plain reason, not the link.
- A send waits at most 10 seconds. RTA changes are never sent inside a page request; only Send test message is, so
  the admin sees the group's answer at once. A post that fails is tried again after 1, 5 and 15 minutes, then shows
  "Not posted" with the reason on the RTA and on the Notifications page.
- Preview only runs everything except the send, so an admin can watch a day's posts before turning them on.

## Not knowable from here

- Whether a Teams post can @mention a person by the schedule's Email column so they get an alert. Microsoft documents
  mentions in Adaptive Cards; I cannot test it against your Teams from this container. If wanted, Send test message
  would check it on your Teams before it is used.
- The real Teams and Slack apps were not reached from here (no account, and the network policy). Tests use a fake
  group that records what it receives.
