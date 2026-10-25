# Design Calibration

Use this reference after gathering context and before declaring the design system. Its purpose is to turn a brief into visible decisions, not to decorate the response with scores.

## 1. Design Read

Write a compact read containing:

- **Artifact**: landing page, dashboard, prototype, slide deck, visualization, campaign page, and so on.
- **Audience**: who must understand, trust, or act.
- **Visual language**: a specific family such as restrained builder SaaS, kinetic editorial, warm humanist, or institutional data-first. Avoid empty labels such as "modern" or "clean."
- **Mode**: greenfield, extension, redesign-preserve, or redesign-overhaul.
- **Constraints**: brand, accessibility, platform, viewport, content, deadline, and supplied assets.

If two plausible readings would produce materially different work, ask one focused question. Otherwise state the read and proceed.

## 2. Five Dials (whole numbers 1 to 10)

**Visual Variance** (compositional departure from familiar patterns): 1–3 stable grids, symmetry, low surprise; 4–6 one or two asymmetric moves; 7–8 strong art direction, off-grid moments; 9–10 experimental, only when comprehension and brand permit.

**Motion Intensity** (how much meaning is carried through time): 1–2 static, state feedback only; 3–4 hover, focus, short entry transitions; 5–7 sequenced reveals, state choreography; 8–10 cinematic, pinning, scrubbing. Every animation must communicate hierarchy, feedback, causality, or narrative. Honor reduced motion whenever motion exceeds simple state feedback.

**Information Density** (useful information per viewport, not clutter): 1–3 gallery-like; 4–6 balanced marketing/product; 7–8 analytical, operational, comparison-heavy; 9–10 cockpit-like, needs strong grouping, scanning and progressive disclosure.

**Asset Dependence** (reliance on real imagery, screenshots, illustration, identity assets): 1–3 typography, data or interface structure can carry it; 4–6 a few key visuals help; 7–10 fails without high-fidelity assets. At 7+, inventory assets before layout. Do not hide missing assets with decorative CSS.

**Brand Fidelity** (how strictly existing identity and interaction language is preserved): 1–3 new or exploratory; 4–6 adapt recognizable cues; 7–8 preserve core assets, tokens, voice, signature patterns; 9–10 extension-level, new work appears native.

## 3. Presets (starting points, not mandatory)

| Brief | Variance | Motion | Density | Assets | Fidelity |
|---|---:|---:|---:|---:|---:|
| Mainstream SaaS landing | 6 | 5 | 4 | 6 | 5 |
| Creative studio / campaign | 8 | 7 | 3 | 8 | 4 |
| Developer tool landing | 6 | 5 | 5 | 6 | 6 |
| Data dashboard | 4 | 3 | 8 | 3 | 7 |
| Public-sector service | 3 | 2 | 6 | 3 | 9 |
| Editorial presentation | 7 | 5 | 4 | 7 | 5 |
| Existing-product extension | match | match | match | match | 10 |
| Redesign · Preserve | current + 1 max | current + 1 max | match | match | 9 |
| Redesign · Overhaul | 6–8 | 4–7 | match content | 6–9 | 5–7 |

## 4. Resolve Conflicts

- High variance + high density: preserve a stable navigation and grid spine; concentrate experimentation in one layer.
- High motion + high density: animate transitions or focus, not every element.
- High assets + low fidelity: establish a new visual bible before generating or sourcing a set.
- High assets + high fidelity: source official assets first; generation may extend the world but must not replace identity-critical material.
- High fidelity + overhaul request: identify which brand invariants survive before changing the visual language.
- Accessibility constraints override aesthetic scores. Reduce motion, clarify hierarchy, and preserve contrast without asking permission.

## 5. Optional Image-First Branch

Only for a visually important greenfield or overhaul task (campaign landing page, brand launch, product hero). Skip for extensions, repairs, dashboards, forms, data tables, or when the user supplied Figma, screenshots or a mature design system. (Not used in this repository: image generation tools are not installed.)

## 6. Completion Test

The calibration is successful only if someone can point from each dial to concrete consequences in the artifact. If changing a score would not change the plan, remove the score or make the mapping explicit.
