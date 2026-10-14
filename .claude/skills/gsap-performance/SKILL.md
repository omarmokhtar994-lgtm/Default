---
name: gsap-performance
description: Official GSAP skill for performance — prefer transforms, avoid layout thrashing, will-change, batching. Use when optimizing GSAP animations, reducing jank, or when the user asks about animation performance, FPS, or smooth 60fps.
license: MIT
---

# GSAP Performance

## Local notes (this repository)

Installed unchanged from greensock/gsap-skills at aed9cfd (MIT, GreenSock), apart from this note. Project rules
in `CLAUDE.md` outrank this skill.

- **GSAP is not on the website today.** The site is Flask and Jinja with plain JS, no npm build and no React,
  under a strict CSP. Adding GSAP is a new library, so the owner decides, with a sample first.
- **If adopted:**
  - Ship one pinned copy of `gsap.min.js` under `webapp/static/` (CSP `script-src 'self'`; no CDN).
  - Load it with a `<script src>` tag, never inline script.
- **The npm, React, Vue and Nuxt parts do not apply** here: there is no build step.
- **Reduced motion is required:** wrap every animation in `gsap.matchMedia()` with
  `(prefers-reduced-motion: reduce)` giving no movement, as `better-ui` and `better-accessibility` require.
- **Motion never carries meaning alone:** a state change also shows as text, colour or an icon.

## When to Use This Skill

Apply when optimizing GSAP animations for smooth 60fps, reducing layout/paint cost, or when the user asks about performance, jank, or best practices for fast animations.

**Related skills:** Build animations with **gsap-core** (transforms, autoAlpha) and **gsap-timeline**; for ScrollTrigger performance see **gsap-scrolltrigger**.

## Prefer Transform and Opacity

Animating **transform** (`x`, `y`, `scaleX`, `scaleY`, `rotation`, `rotationX`, `rotationY`, `skewX`, `skewY`) and **opacity** keeps work on the compositor and avoids layout and most paint. Avoid animating layout-heavy properties when a transform can achieve the same effect.

- ✅ Prefer: **x**, **y**, **scale**, **rotation**, **opacity**.
- ❌ Avoid when possible: **width**, **height**, **top**, **left**, **margin**, **padding** (they trigger layout and can cause jank).

GSAP’s **x** and **y** use transforms (translate) by default; use them instead of **left**/**top** for movement.

## will-change

Use **will-change** in CSS on elements that will animate. It hints the browser to promote the layer.

```css
will-change: transform;
```

## Batch Reads and Writes

GSAP batches updates internally. When mixing GSAP with direct DOM reads/writes or layout-dependent code, avoid interleaving reads and writes in a way that causes repeated layout thrashing. Prefer doing all reads first, then all writes (or let GSAP handle the writes in one go).

## Many Elements (Stagger, Lists)

- Use **stagger** instead of many separate tweens with manual delays when the animation is the same; it’s more efficient.
- For long lists, consider **virtualization** or animating only visible items; avoid creating hundreds of simultaneous tweens if it causes jank.
- Reuse timelines where possible; avoid creating new timelines every frame.

## Frequently updated properties (e.g. mouse followers)

Prefer **gsap.quickTo()** for properties that are updated often (e.g. mouse-follower x/y). It reuses a single tween instead of creating new tweens on each update. 

```javascript
let xTo = gsap.quickTo("#id", "x", { duration: 0.4, ease: "power3" }),
    yTo = gsap.quickTo("#id", "y", { duration: 0.4, ease: "power3" });

document.querySelector("#container").addEventListener("mousemove", (e) => {
  xTo(e.pageX);
  yTo(e.pageY);
});
```

## ScrollTrigger and Performance

- **pin: true** promotes the pinned element; pin only what’s needed.
- **scrub** with a small value (e.g. `scrub: 1`) can reduce work during scroll; test on low-end devices.
- Call **ScrollTrigger.refresh()** only when layout actually changes (e.g. after content load), not on every resize; debounce when possible.

## Reduce Simultaneous Work

- Pause or kill off-screen or inactive animations when they’re not visible (e.g. when the user navigates away).
- Avoid animating huge numbers of properties on many elements at once; simplify or sequence if needed.

## Best practices

- ✅ Animate **transform** and **opacity**; use **will-change** in CSS only on elements that animate.
- ✅ Use **stagger** instead of many separate tweens with manual delays when the animation is the same.
- ✅ Use **gsap.quickTo()** for frequently updated properties (e.g. mouse followers).
- ✅ Clean up or kill off-screen animations; call **ScrollTrigger.refresh()** when layout changes, debounced when possible.

## Do Not

- ❌ Animate **width**/ **height**/ **top**/ **left** for movement when **x**/ **y**/ **scale** can achieve the same look.
- ❌ Set **will-change** or **force3D** on every element “just in case”; use for elements that are actually animating.
- ❌ Create hundreds of overlapping tweens or ScrollTriggers without testing on low-end devices.
- ❌ Ignore cleanup; stray tweens and ScrollTriggers keep running and can hurt performance and correctness.
