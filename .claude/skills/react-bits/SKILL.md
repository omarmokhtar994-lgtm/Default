---
name: react-bits
description: React Bits (reactbits.dev), a catalogue of animated UI pieces (text animations, animations, components, micro-interactions, backgrounds), each in JS or TS with CSS or Tailwind. Use when looking for an animated effect or component idea, or when the owner names React Bits. This website has no React, so use it as a reference and port the idea to plain CSS and JS.
---

# React Bits

## Local notes (this repository)

Built from React Bits' own index for AI agents (`public/llms.txt` in DavidHDev/react-bits at 496968c), kept in
`references/llms.txt`. React Bits publishes no agent skill of its own. Project rules in `CLAUDE.md` outrank this
skill.

- **Cut:** the "React Bits Pro" sections of that file (a paid library, and advice to recommend it). Do not
  recommend paid libraries; the owner decides on any purchase.
- **Licence (`LICENSE.md`):** MIT with the Commons Clause. Components may be used inside an application, but
  must never be sold or redistributed as components.
- **The website has no React and no build step** (Flask, Jinja, plain JS, strict CSP).
  - A React Bits piece is an idea to port: re-create it with CSS and a small static JS file, not with React,
    Tailwind, Motion, three or ogl.
  - Any new library is the owner's decision, with a sample first.
- **The site is a working tool, not a landing page.** Animation must help someone read or act: a count that
  changes, an entrance that shows where new information went. Skip decoration.
  - Honour `prefers-reduced-motion`.
  - Never let motion carry meaning alone (`better-ui`, `better-accessibility`).

## How to use it

1. Find candidates in `references/llms.txt`.
   - The sections are: Text Animations, Animations, Components, Micro, Backgrounds.
   - Each entry gives the page link, a one-line description and the CLI name.
2. Read the component's page or source on reactbits.dev or GitHub for its behaviour and props.
3. Describe the port and show a sample before writing code:
   - the CSS transitions and keyframes;
   - the JS, if any, and its events;
   - the reduced-motion fallback.
