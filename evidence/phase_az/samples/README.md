# Look samples (Phase AZ, owner 2026-10-25: "fancy background, floating note, new palette, fully redesign")

Static pages, made-up "Associate NN" names, no inline script or style; nothing under `webapp/` changes until the owner picks one.
`python3 build.py` writes the pages and styles, `python3 shoot.py` the screenshots in `shots/` (desktop 1440 and phone 390, the day
page also scrolled). Text pairs measured: ink on panel 15 to 18, secondary text 7 to 8, buttons 7 to 10, the note 14 to 18.

- **A Tide**: light, a cool sea-glass wash behind plain panels; the wash drifts very slowly (off with reduced motion).
- **B Night watch**: dark deep blue, a faint dot grid that fades out, a crisp now line.
- **C Paper**: light, flat and quick, a dot grid and one ink-blue accent. The lightest to draw.

All three: the live "page changed" note floats at the bottom while you scroll (a pill with Refresh; on a phone it is a full-width bar),
channel colours and the four status colours keep their meaning, and the weight is the same fonts, no images.

Round 2 (after trying taste, impeccable and Emil Kowalski's skills, 2026-10-25): actions are ink in every look (colour means state, as
`webapp/DESIGN.md` says); no glow, no decorative dot, no gradient or glass as decoration; the note enters in 280 ms with a strong
ease-out and its dot pulses three times, not forever; buttons press down 3%; figures are tabular. The taste skill covers landing pages
and says dashboards are out of scope, so it was applied to sign-in and to the rules that carry over (no em dashes, no decorative dots,
one accent, contrast on every button).
