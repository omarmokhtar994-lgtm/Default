# Phase AG: redesign plan for samples (v4 "Shift desk")

© 2026 Omar Mokhtar. All rights reserved.

Owner, 2026-10-14: "a full redesign to the website colors tabs everything ... act as if ur the planner or RTA how
would u like to view and what would be easier for your eyes and day to day show me first". Also leave requests,
associate self-service and shift swaps (items 1 to 3), and the two things left from Phase AF (every RTA tab in
another zone; the rest of the week on Overview). Samples only; nothing is built until the owner picks.

## Read of the brief

An internal operations console used all day: the RTA analyst watches today minute by minute, the planner works the
week, the supervisor approves requests, and associates (new) check their own week on a phone. The design has to be
easy on the eyes for eight hours and put "what is happening now" first.

## What changes, and why (as the person using it)

1. **Now first.** Today the RTA page stacks title, undo bar, achievement, tiles, shrinkage and forms before the
   timeline. In v4 the day strip and the floor share the first screen; a right-hand "Now" column lists the next hour
   (breaks starting, people late), what needs attention and requests waiting. Nothing important needs a scroll.
2. **Navigation by job.** The left menu groups pages by what you are doing: Today, This week, Requests, Insights,
   Setup, with a count where something waits for you. Program, day and time zone sit in one context bar at the top
   of every page instead of each page's own form. "Go to" (Ctrl K) jumps to any page, program or person.
3. **Fewer, clearer tabs.** The RTA's nine tabs become six: Floor, Intervals, Channels, Adherence, Fix the day
   (Rescue, overtime and VTO, days off to cancel, change several breaks) and Find a time.
4. **Smaller titles, more data.** The 2.5 rem page titles go; the context bar says where you are.
5. **Colour still means state.** Teal covered, amber short, red gap, violet over-staffed, measured and approved in
   Phase Y, stay as they are. Phone, Chat and Email keep their hues. Everything you press is ink.

## Tokens

| Name | Night (default) | Day | Role |
|---|---|---|---|
| Canvas | `#0C1320` | `#EEF2F7` | page |
| Rail | `#080D17` | `#FFFFFF` | the left menu |
| Surface | `#121C2B` | `#FFFFFF` | panels |
| Raised | `#192538` | `#F4F7FA` | picked tab, hovered row, dialogs |
| Line | `#24324A` | `#D3DBE6` | dividers, empty cells |
| Ink | `#EBF0F7` | `#12203A` | text and every action |
| Dim | `#93A3B9` | `#536379` | secondary text |
| Covered, Short, Gap, Over | `#2BC4B4` `#F2A93B` `#E5534B` `#8A7BF0` | `#06A496` `#C98304` `#D53D38` `#7560E3` | state only |
| Phone, Chat, Email | `#3E6FD8` `#B4479A` `#4D7D8D` | same | channel only |

Radius rule: panels 12 px, controls 8 px, status chips round, grid cells 3 px.

## Type

- **Archivo** (one variable family, width 62 to 125): headings set wide (width 112, weight 700), figures set
  condensed (width 75, weight 650, tabular). The same family carries both, so a board of numbers reads like one
  voice; the width does the work that a second display face did before.
- **Atkinson Hyperlegible Next** stays for text and labels: built for legibility, which matters on an eight-hour
  shift.
- Both self-hosted (no Google Fonts link at run time).

## The one bold element: the day strip

A 24-hour band at the top of every day page (one cell per interval, coloured by state, a breathing "now" marker,
hour ticks) with the day's figures beside it. It is also the scrubber: clicking an hour scrolls the floor there. The
same strip, small, shows the impact of a leave or swap request, and the associate's own day on the phone.

## Motion (CSS only; no new library)

- The "now" marker breathes slowly (it is live); off under reduced motion.
- Tabs and the requests list cross-fade (View Transitions where the browser has them).
- Approving a request folds its row into "Approved" with a check: feedback, not decoration.
- On the phone, request sheets slide up. GSAP and Lenis are not needed for any of this.

## New dependency to decide

Icons: Phosphor (MIT), about 35 SVG files served from the site itself (no CDN, fits the CSP). The menu can collapse
to icons only, which needs them.

## Review against generic defaults

- Dark page with one acid accent: avoided; no accent, colour is state.
- Identical rounded cards with shadows: avoided; the floor and the Now column are two panels, lists use dividers.
- No all-caps labels, no labels above every heading, no middle-dot meta lines, no arrows on buttons, no monospace
  for figures (Archivo condensed with tabular figures instead).
