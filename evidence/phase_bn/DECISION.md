# Phase BN: the owner's decision (2026-11-12), noted, not built yet

Owner: "change Tide with A and Night with B and add C as a fourth theme. Don't act now, just note."

- **Tide (light) is replaced by A, Atelier** (`evidence/phase_bn/samples/a_atelier.css`, palette in `palette_sheet.png`).
- **Night watch (dark, the default) is replaced by B, Lacquer** (`b_lacquer.css`).
- **C, Platinum (graphite) is added as a fourth look** (`c_platinum.css`).
- **Drafting table stays** as the third existing look, so the site has four looks: Atelier, Lacquer, Drafting table, Platinum.
- The shared motion in `common.css` (page cross-fade, press, easing, all off under reduced motion) goes with them.
- Status colours and channel colours stay the measured set. Fonts stay the two self-hosted ones.

## Open points for when this is built (assumptions, to confirm or change then)
1. Names in the top bar: assumed the new names (Atelier, Lacquer, Platinum), since the colours change.
2. Cookie values: `light` and `dark` keep working (they now draw Atelier and Lacquer); Platinum gets a new value (`graphite`); `draft` and the ignored old `ocean` are unchanged.
3. The default stays the dark look (now Lacquer).
4. The samples re-skin only; new layouts were not decided.
5. Needed when built: the contrast check of every pair in the new looks (`evidence/phase_ba/contrast.py`), the route sweep and page review in all four looks at 1440 and 390 px, the interface checklist, then the full chain and the package.
