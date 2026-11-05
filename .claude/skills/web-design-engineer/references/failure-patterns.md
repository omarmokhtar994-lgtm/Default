# Contextual Failure Patterns

Use this catalog to catch recurring AI-generated design failures. Read only the sections relevant to the artifact. These are strong defaults with explicit exceptions, not universal taste laws.

## Marketing and Multi-section Pages

- **Repeated section header formula**: no tiny uppercase eyebrow above every heading (mechanical rhythm). Exceptions: manuals, indexed editorial systems, established brand pattern. Repair: remove low-information labels; vary hierarchy.
- **Zigzag monotony**: avoid three or more consecutive left/right image-text splits. Repair: full-width proof, vertical narrative, comparison, gallery, diagram.
- **Default centered hero**: do not choose centered headline + gradient + two CTAs without brief support. Exceptions: manifestos, launch statements, search-first utilities.
- **Decorative trust theater**: no fabricated metrics, testimonials, logos, security badges, "used by" claims. Repair: labeled placeholder or real proof.
- **CTA duplication**: keep labels for the same intent consistent.

## Layout and Components

- **Cardification**: use containers only when grouping, selection or elevation carries meaning. Detect: every paragraph, metric and icon in a rounded card. Repair: whitespace, alignment, dividers, one shared surface.
- **Bento without rhythm**: every cell needs content and a compositional role; no blank filler cells.
- **Shape drift**: define a radius grammar and follow it; assign radius by component role.
- **Split-header filler**: avoid a large left headline with a small floating right paragraph when the split communicates nothing.

## Typography and Content

- **Generic display typography**: do not reach automatically for Inter, Roboto, Arial, system-ui, Fraunces or Instrument Serif as the identity-bearing display choice. Exceptions: existing brand/system, accessibility, intentional neutrality.
- **Micro-label noise**: decorative version numbers, fake coordinates, weather, status dots, section numbers, metadata that does not help the user. Delete or connect to real state.
- **Copy-shaped decoration**: vague claims, fake precision, slogans, captions written only to fill space.
- **Unreadable hero**: CTA below the initial viewport, clipped display text, copy/image competition.

## Imagery and Brand

- **CSS as counterfeit asset**: do not replace a recognizable product, logo or interface with decorative CSS shapes.
- **Image-label clutter**: no pills and captions over imagery unless they identify, control or explain it.
- **Generated-world drift**: multi-image output changes palette, material, lighting or brand symbols.

## Motion and Interaction

- **Motion for spectacle only**: every animation needs a hierarchy, feedback, causality or narrative purpose. Detect: removing it changes no understanding.
- **Scroll-state rendering**: do not update broad state on every scroll or pointer frame; use CSS, IntersectionObserver or an animation library.
- **Repeated spectacle**: avoid multiple marquees, pinned chapters, magnetic controls or competing ambient loops on one surface; pick one signature moment.
- **Missing reduced-motion path**: motion beyond simple state feedback must collapse cleanly; content order and interaction completion must not rely on animation.

## Dashboards and Product UI

- **Marketing styling on operational UI**: giant headlines, excessive whitespace, cinematic cards impede scanning. Raise density, stabilize the grid, clarify state, prioritize task completion.
- **Decorative data visualization**: gradients, 3D, shadows or animation obscure comparison and scale. Improve data-ink ratio, labels, semantic colour, accessible alternatives.
- **Happy-path-only components**: add loading, empty, error, permission, disabled and overflow states.

## Final Use

Report only consequential failures. Do not dump the whole catalog into the user-facing response. Fix safe in-scope problems directly; surface exceptions and tradeoffs when they affect intent.
