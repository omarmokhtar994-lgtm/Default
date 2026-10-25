# Existing UI and Redesign Protocol

Read this reference before modifying an existing visual product.

## 1. Classify the Mode

- **Extension**: add or change a bounded element inside the current system. Match the existing vocabulary. Do not "improve" unrelated surfaces.
- **Redesign · Preserve**: modernize while retaining identity, information architecture, content voice, and behavioral contracts. Prefer targeted evolution.
- **Redesign · Overhaul**: introduce a new visual language while retaining the agreed product, content, and technical contracts. Overhaul is not permission to rewrite everything.

If preserve versus overhaul would materially change the result and the request is ambiguous, ask one focused question.

## 2. Audit Before Editing

Record the current state in project notes or a concise redesign brief.

- **Visual system**: color roles and actual usage ratios; type families, scale, weights, line lengths; spacing rhythm and container widths; radius, border, shadow, elevation rules; icons, illustration, photography; motion durations, easing, triggers, feedback style.
- **Product and content**: page tree, navigation, key journeys; existing content blocks and their purpose; brand voice, legal copy, localization, real data; loading, empty, error, disabled, permission states.
- **Technical contracts**: routes, slugs, anchors, deep links; form field names, order, validation, autofill; analytics events, data attributes, test selectors; component APIs; accessibility semantics, keyboard behavior, focus order, announcements; SEO metadata.
- **Quality debt**: separate into Preserve (recognizable or contract-critical strengths), Improve (weak hierarchy, spacing, contrast, responsiveness, craft), Remove (clutter, broken patterns, dead interactions, fabricated content).

## 3. Protected Contracts

Never change these silently: route structure, slugs, anchor IDs, primary navigation labels; brand logo, wordmark, identity-critical assets; form field names/order or submission behavior; legal, consent, privacy, pricing, compliance copy; analytics events, selectors, experiment identifiers; existing accessibility wins; public component APIs or persistent-state keys; user-provided content and real data. Ask for authorization when the requested outcome genuinely requires a protected-contract change.

## 4. Modernization Order

Apply the lowest-risk lever that solves the problem, then reassess:

1. Correct functional and accessibility failures.
2. Repair hierarchy and typography.
3. Normalize spacing, alignment, and responsive behavior.
4. Consolidate tokens and remove rogue styling.
5. Improve states and interaction feedback.
6. Add justified motion.
7. Recompose hero or key sections.
8. Replace full blocks only when they cannot be repaired.

In Preserve mode, stop once the brief is satisfied. Do not turn incremental work into a portfolio redesign.

## 5. Dial Guidance

- Extension: match all existing dials; Brand Fidelity 10.
- Preserve: keep density and assets stable; change variance/motion by at most one point unless requested.
- Overhaul: derive new variance/motion from the brief, but retain a content-density map so information is not lost.

## 6. Before-and-After Plan

For non-trivial redesigns, state: Mode, Preserve, Improve, Remove, Protected contracts, Design Read + dials, Highest-risk change, Rollback / fallback. A decision record, not an essay.

## 7. Verification

The default self-check confirms scope and protected contracts by inspection. Run executable browser acceptance only when the user asks for it (here: `webapp-testing`), with regression checks for the preserved journeys.
