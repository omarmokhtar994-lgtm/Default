# Phase AG colour samples (owner's answer 7: "feel free to change colors ... show me first")

© 2026 Omar Mokhtar. All rights reserved.

Owner's pick, 2026-10-15: "I recommend A as well but keep deep ocean as well as a third option so to have 3 views".
Applied: Graphite night is the default, Graphite day is the day look, and Deep ocean is a third look ("Ocean look" in
the top bar). The current navy is retired.

What changes is the family of surfaces (page, menu, panels, lines, text). The status colours (teal covered, amber
short, red gap, violet over-staffed) and the channel colours (Phone, Chat, Email) stay as they are in every option:
they are the measured, colour-blind-checked set, and colour still means state only.

| Option | Night (default) | Day | Idea |
| --- | --- | --- | --- |
| Current | navy `#0E1A2B`, panels `#15243A` | blue-grey `#EAEFF5`, white panels | Phase Y |
| A Graphite | neutral `#111418`, panels `#181C22` | neutral `#F1F2F4`, white panels | no blue cast; the status colours carry all the colour, easier on the eyes over a night shift |
| B Deep ocean | deeper navy `#0A1220`, panels `#111C2E` | blue-grey `#E6EDF6`, white panels | the current family, with more separation between page, panels and lines |

Contrast (WCAG, measured by `src/palettes.py`, in `CONTRAST.txt`): every option passes. Body text 13.2:1 or more,
secondary text 5.4:1 or more, field edges 3.2:1 or more, status fills 3.1:1 or more against panels. A and B
measure a little higher than the current palette on every pair.

Screens: `rta_*`, `requests_*` and `me_*` (phone, 390 px) for each option and look, rendered on the review server
with an override sheet (`src/colshot.py`).
