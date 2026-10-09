# Colour and design proposal (Phase Y), 2026-10-09 Egypt time

Owner: "Colors design everything u can change but show me". Nothing on the website has changed: `proposal.css` is
layered over the real pages only to draw the samples in `samples/`. It becomes the site's colours only after approval.

## The idea in one line

Colour means the floor's state, never "you can press this". Teal is covered, amber is short, red is a gap, violet is
over-staffed, wherever they appear; links, buttons, picked tabs, the focus ring and breaks you can drag are ink (near-white
on the night look, navy on the day look). That is the rule `webapp/DESIGN.md` already states ("the page's colour always
means something; there is no decorative accent"); today the actions break it by using the covered teal.

Kept as they are: the control-room look, the night and day looks, the type (Saira Semi Condensed and Atkinson
Hyperlegible Next), the layout, the brand mark, the meaning of every status colour and the night look's status colours.

## What is wrong today (measured)

| What | Night look | Day look | Needs |
| --- | --- | --- | --- |
| Field and button edges against the panel | 1.33:1 | 1.39:1 | 3:1 |
| Teal and amber status cells against the panel | 7.18, 7.82 | 2.75, 2.17 | 3:1 |
| Text on teal and amber cells | 8.04, 8.75 (dark text) | 2.75, 2.16 (white text) | 4.5:1 |
| Over-staffed cells, their numbers | 5.14; counts 4.17 (faded) | 4.23; counts 3.57 | 4.5:1 |
| Teal used as text (channel table, "Called in") | 7.18 | 2.75 | 4.5:1 |
| Violet used as text (supervisor role) | 4.59 | 4.13 | 4.5:1 |
| A finished stage on the progress ring and bars | 2.37 | 2.15 | 3:1 |
| White text on the email channel colour | 4.41 | 4.41 | 4.5:1 |
| Links and buttons share the covered teal | same hue (184°) | same hue (184°) | 15° apart |
| Breaks on the RTA timeline | amber, the "short" colour | amber | its own meaning |
| Moved breaks | violet, the "over-staffed" colour | violet | its own meaning |
| "Hours needed" line on Analysis | orange, 13° from the red "gap" | same | 15° apart |
| Date fields' calendar | always dark | dark on a light page | follows the look |

## The proposed tokens

New roles (both looks), values measured against what they sit on:

| Token | Role | Night look | Day look |
| --- | --- | --- | --- |
| `--action` | links, buttons, focus ring, picked items, breaks you can move | `#E6EDF5` | `#12233A` |
| `--action-hover` | a hovered filled button | `#FFFFFF` | `#22385A` |
| `--on-action` | the label on a filled button | `#0E1A2B` | `#FFFFFF` |
| `--edge` | field and button edges | `#627389` | `#77869A` |
| `--selected` | the background of a picked tab, chip or option | `#1B2D47` | `#E3EAF2` |
| `--done` | a finished stage | `#54749A` (was `#3E5F86`) | `#7692B4` (was `#9DB3CE`) |
| `--covered-text` | "covered" written as text | `#2BC4B4` | `#0B776C` |
| `--over-text` | "over-staffed" written as text | `#9086EE` | `#715ED8` |
| `--on-covered`, `--on-short` | text on those fills | `#0E1A2B` | `#0E1A2B` |
| `--on-gap`, `--on-over` | text on those fills | `#0E1A2B` | `#FFFFFF` |
| `--ch-email` | the email channel | `#4D7D8D` (was `#4F7F8F`) | same |

Day-look status fills (the night look keeps its own): teal and amber a step deeper with dark text on them; red and
violet a step deeper with white text, so the four are told apart by lightness as well as hue.

| Status | Now (day) | Proposed (day) |
| --- | --- | --- |
| Covered | `#22AE9F` | `#06A496` |
| Short | `#E9A23B` | `#C98304` |
| Gap | `#DE5048` | `#D53D38` |
| Over-staffed | `#7B6BE6` | `#7560E3` |

## Every pair, proposed (WCAG 2 contrast)

| Pair | Needs | Night look | Day look |
| --- | --- | --- | --- |
| Body text on panel | 4.5:1 | 13.23 | 15.82 |
| Secondary text on panel | 4.5:1 | 6.05 | 6.25 |
| Secondary text on page | 4.5:1 | 6.77 | 5.40 |
| Links and actions on panel | 4.5:1 | 13.23 | 15.82 |
| Links and actions on page | 4.5:1 | 14.81 | 13.69 |
| Label on a filled button | 4.5:1 | 14.81 | 15.82 |
| Field and button edge on panel | 3.0:1 | 3.22 | 3.71 |
| Field and button edge on page | 3.0:1 | 3.61 | 3.21 |
| Focus ring on panel | 3.0:1 | 13.23 | 15.82 |
| Finished stage on panel | 3.0:1 | 3.23 | 3.21 |
| Covered fill on panel | 3.0:1 | 7.18 | 3.11 |
| Short fill on panel | 3.0:1 | 7.82 | 3.12 |
| Gap fill on panel | 3.0:1 | 4.21 | 4.61 |
| Over-staffed fill on panel | 3.0:1 | 4.59 | 4.63 |
| Text on covered | 4.5:1 | 8.04 | 5.63 |
| Text on short | 4.5:1 | 8.75 | 5.60 |
| Text on gap | 4.5:1 | 4.72 | 4.61 |
| Text on over-staffed | 4.5:1 | 5.14 | 4.63 |
| Covered as text | 4.5:1 | 7.18 | 5.43 |
| Short as text | 4.5:1 | 7.82 | 6.26 |
| Gap as text | 4.5:1 | 6.85 | 6.54 |
| Over-staffed as text | 4.5:1 | 5.08 | 4.89 |
| A break (ink) on a shift bar | 3.0:1 | 3.08 | 3.58 |


Every pair passes; the closest is 2.5% over its threshold.

Colour-blind check of the four day-look status fills (dataviz palette validator, all pairs): **pass**; worst pair red
and amber ΔE 8.6 under deuteranopia (target 8), 15.7 with full colour vision (target 15). A first try with all four at
the same lightness failed (ΔE 4.4), which is why red and violet sit darker than teal and amber. The night look's fills
are unchanged and passed before (worst ΔE 14.1).

## Verification

- axe-core 4.14 (WCAG 2.2 A and AA) on 71 pages, each with and without `proposal.css`:
  - night look: colour-contrast failures on 10 pages (734 elements) now, **none** with the proposal;
  - day look: colour-contrast failures on 16 pages (1,721 elements) now, **none** with the proposal;
  - the only failures left in both are the two non-colour ones from the Phase X review (unnamed scroll boxes on 11
    pages, break buttons inside a timeline image on 3), which the colours do not touch.
- The four day-look status fills in the dataviz palette validator, all pairs: pass (above).
- A focused break: the first version of the proposal hid its focus ring (ink ring on an ink break). Fixed with an ink
  outline 2 px out, checked in both looks (`samples/10_break_focus.png`).
- Not verified: Windows high-contrast mode, and real phones (the colours were measured, not looked at on a device).

## What you approve

1. **The colour fixes** (no change of style): visible field edges, readable numbers on the status colours, the day
   look's deeper status colours, the finished-stage colour, the email channel, date pickers that follow the look.
2. **Colour means state**: links, buttons, picked items and the focus ring in ink instead of teal (samples 1, 6, 9).
3. **The RTA timeline and board**: breaks in ink, moved breaks with a dashed edge, the "Hours needed" chart line
   dashed ink (samples 2, 3, 4, 8).

They can be approved separately; 1 is needed for accessibility whatever is decided on 2 and 3.
