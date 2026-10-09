# Team Scheduler: design plan (v3, "control room")

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-10-07: redesign in the "Control room (dark)" direction (chosen from
four previews), keep the name "Team Scheduler". v1 (light limestone and Nile)
is replaced.

v3, 2026-10-10 (Phase XY, owner-approved Phase Y proposal and Phase X review):
colour means state. Everything you can press or move is ink; teal, amber, red
and violet only ever mean covered, short, gap and over-staffed. Every pair is
measured in `evidence/phase_y/PALETTE.md`. Font sizes are in rem, so the page
follows the reader's own text size.

## Subject, audience, job

- Subject: weekly contact-centre schedules, built and checked in 30-minute
  intervals.
- Audience: workforce planners and team leads, on office laptops, sometimes a
  phone.
- Primary job: start this week's run, watch it, and see at a glance how well
  the schedule covers the week before downloading it.

## Tokens

| Name | Hex | Role |
|---|---|---|
| Night shift | `#0E1A2B` | page background |
| Console | `#15243A` | panels |
| Rail | `#26395480` | lines, empty cells |
| Paper | `#E6EDF5` | text |
| Dim | `#8FA3BC` | secondary text |
| Covered | `#2BC4B4` | at or above target (glows); approved |
| Short | `#F2A93B` | below target, at or above the floor; in progress |
| Gap | `#E5534B` | below the floor or uncovered; not approved |
| Over | `#8A7BF0` | over-staffed beyond the cap |
| Action | `#E6EDF5` | links, buttons, the focus ring, picked items, breaks you can move (ink) |
| Edge | `#627389` | field and button edges (3.22:1 on panels) |
| Selected | `#1B2D47` | the background of a picked tab, chip or option |
| Done | `#54749A` | a finished stage (3.23:1 on panels) |
| Covered text, Over text | `#2BC4B4`, `#9086EE` | "covered" and "over-staffed" written as words |

The day look (the device's, or picked with the switch) has its own values for
each token in `app.css`: actions are navy ink (`#12233A`), edges `#77869A`, and
the status fills sit a step deeper (`#06A496`, `#C98304`, `#D53D38`,
`#7560E3`) with dark text on teal and amber and white text on red and violet,
so the four stay apart by lightness as well as hue (colour-blind check: worst
pair ΔE 8.6).

The four status colours are the heatmap's scale, so the page's colour always
means something; there is no decorative accent. The rule that keeps it true:

- A thing you can press, pick or move wears ink (`--action`), never a status
  colour. Picked means ink edge on `--selected`, not teal.
- A status written as a word uses its text token (`--covered-text`,
  `--short-ink`, `--gap-ink`, `--over-text`); text on a status fill uses
  `--on-covered`, `--on-short`, `--on-gap` or `--on-over`.
- Chart series never borrow a status colour: the "hours needed" level is a
  dashed ink line.
- Breaks on the RTA timeline are ink (you can move them); a moved break keeps
  a dashed outline where the engine planned it.

Type: **Saira Semi Condensed** (600/700) for headings, status words and every
big number, which reads like control-room signage and keeps figures narrow;
**Atkinson Hyperlegible Next** (400/600) for everything else. Tabular figures
throughout. Log text only: system monospace.

## Layout

```
Dashboard
+---------------------------------------------------------------+
| [mark] Team Scheduler                 Runs  People  Omar  Sign out |
+---------------------------------------------------------------+
| NOW: (stage ring) week42_NMG.xlsx  Running the schedule  41 min |
|      2 waiting in line                     (or: nothing running)  |
+----------------------+----------------------------------------+
| New run              | Latest schedule: week41_NMG.xlsx       |
| [drop workbook]      | [ week wall: 7 days x 48 half-hours ]  |
| (Quick)(Deep)(Check) | 85% fully covered  0 gaps  1 to review |
| [Check and run]      |                                        |
+----------------------+----------------------------------------+
| Runs: workbook | by | started | stage bar | coverage           |
+---------------------------------------------------------------+

Run page
+---------------------------------------------------------------+
| week42_NMG.xlsx                                   Approved    |
| (stage ring + stage names)   | week wall + legend             |
| 107 of 126 half-hours fully covered | 0 below floor | ...     |
| What to check (plain sentences from the validator)            |
| [Download the schedule] [All results (.zip)]                  |
| > Technical details (message, verdict lines, runner log)      |
+---------------------------------------------------------------+
```

Left-aligned. Panels: 10 px radius on the two big panels only, 4 px on cells
and chips; 1 px Rail border, no drop shadows (the glow is reserved for covered
heatmap cells and the active stage).

## The one bold element: the week wall

A 7 x 48 grid (Sunday first; one cell per half-hour) built from the run's own
`INDEPENDENT_VALIDATION.json` interval rows: each staffed half-hour is coloured
by after-breaks coverage against its requirement (Gap < floor, Short <
target, Covered at target, Over above the cap); half-hours with no
requirement are dark. Hovering or focusing a cell says "Mon 14:30 - 6 of 6
needed". On a run page the cells fade in once (the single orchestrated motion; off
under reduced motion); pages crossfade where the browser supports it. The dashboard shows the wall
of the latest finished schedule. Nothing on the wall is ever invented: a run
without validation data shows a sentence saying why, not a pattern.

The stage ring (Check, Safety gate, Schedule, Scoring, Result as five arcs)
replaces v1's bar on the run page and the NOW strip; the list keeps a thin bar.
The ring never claims a percentage: it shows the stage and the real elapsed
time.

## Review against generic defaults

- "Dark + one acid accent" is the common dark look: avoided; colour is the
  four-step coverage scale only.
- Identical rounded cards with shadows: avoided; two panels, a table, a grid.
- A "62%" progress ring was in the preview, but the runner reports no
  percentage, so the ring shows stage and elapsed time instead.
- No ALL-CAPS eyebrows, no "·"-joined meta lines, no → on buttons.

## Quality floor

360 px wide without horizontal scroll (the wall scrolls inside its panel on
a phone), visible focus ring (2 px ink outline, offset) that never hides under
the sticky top bar, AA contrast on text and 3:1 on field edges and status
cells, every colour also spelled out in words (legend, cell titles, chips),
`prefers-reduced-motion` respected. On a phone the RTA timeline gives each name
its own line and the attendance box 16 px text (no zoom on tap). A list that
acts when it changes waits for Enter when the keyboard moves it.
