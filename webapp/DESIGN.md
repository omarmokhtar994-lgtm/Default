# Team Scheduler: design plan

© 2026 Omar Mokhtar. All rights reserved.

## Subject, audience, job

- Subject: weekly shift schedules for contact-centre programs, built in 30-minute
  intervals from a workbook.
- Audience: workforce planners and team leads, on office laptops and sometimes
  on a phone.
- Primary job: upload this week's workbook, see it move through check, safety
  gate, solving and scoring, then download the approved schedule.

## Tokens

| Name | Hex | Role |
|---|---|---|
| Nile | `#0F4F5C` | structure: header, primary buttons, focus ring |
| Limestone | `#EEF1EC` | page background (cool, grey-green, not cream) |
| Ink | `#16252B` | text |
| Shift amber | `#E2A13B` | the one accent: shift bars and "in progress" |
| Covered green | `#2E8A66` | approved |
| Gap red | `#B8432F` | rejected / not approved |
| Mist | `#C9D3CF` | lines, empty interval cells |

Type: **Bricolage Grotesque** (headings, the workbook name, big status words;
weight 700, tight tracking, sentence case) and **Atkinson Hyperlegible Next**
(everything else; designed for legibility, tabular figures for times). Log
output only uses the system monospace, because it is literal runner output.
Scale (1.25): 13 / 16 / 20 / 25 / 31 / 39 px; body line-height 1.5, measure
under 72 characters.

## Layout

Left-aligned throughout; one 1120 px column; panels have a 6 px radius, a
1 px Mist border and no shadow.

```
Login (wide)                         Dashboard
+---------------------+-----------+  +-------------------------------------+
| Sun Mon ... Sat     |  Sign in  |  | Team Scheduler         Runs People |
| ▃▃▃  ▃▃▃▃  ▃▃ ...   |  [user ]  |  +----------------+--------------------+
| (week of shift bars)|  [pass ]  |  | New run        | Recent runs        |
|                     |  [Sign in]|  | [drop workbook]| name   stage-bar   |
+---------------------+-----------+  | (QUICK)(DEEP)  | name   stage-bar   |
                                     | [Check and run]|                    |
Run page                             +----------------+--------------------+
+-----------------------------------------------+
| week42.xlsx                     Approved       |
| [Check][Safety gate][Schedule][Scoring][Result]|  <- the stage bar
| verdict lines, downloads, Stop / Resume        |
| ▸ Runner log                                   |
+-----------------------------------------------+
```

## The one bold element: the stage bar

A run's five stages (Check, Safety gate, Schedule, Scoring, Result) are a real
sequence, so they are drawn as one horizontal bar of five segments, styled
like a shift block on a roster: finished stages filled Nile, the current one
amber with a slow left-to-right fill, a failed stage red, a stopped one
hatched. The same bar, small, sits on every row of the runs list. The login
page's week of shift bars is the same visual language at rest. Everything
else is quiet.

## Review against generic defaults (what changed)

- First idea was a cream background with a serif display: that is the most
  common generated look. Changed to cool Limestone and a grotesque.
- First idea had identical rounded cards with shadows for each run: changed to
  a flat table-like list whose information is the stage bar itself.
- Dropped an all-caps label above each heading and "·"-joined meta lines: the
  run page says "QUICK, started by Sara" in a sentence instead.
- No numbered 01/02/03 markers: the stage bar already shows the sequence.
- Motion: only the current stage's fill (shows something is happening) and it
  stops under `prefers-reduced-motion`.

## Quality floor

Works down to 360 px wide with no horizontal scroll; visible focus ring
(3 px Nile outline with offset); contrast AA for text; status never shown by
colour alone (each segment has its word); forms have labels.
