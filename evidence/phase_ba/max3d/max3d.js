// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var root = document.documentElement;
  if (/[?&]flat\b/.test(location.search)) { root.classList.add("flat"); }
  // the week as blocks, drawn once from made-up figures: 7 columns, each a top, a side and a base
  var heights = [2.4, 3.1, 2.8, 3.6, 3.0, 1.8, 1.4], colours = ["var(--ok)", "var(--ok)", "var(--ok)", "var(--short)", "var(--ok)", "var(--gap)", "var(--ok)"], row = document.createElement("div");
  row.className = "row";
  heights.forEach(function (h, i) {
    var c = document.createElement("div"); c.className = "col"; c.style.setProperty("--h", h + "rem"); c.style.setProperty("--c", colours[i]);
    ["top", "front", "right"].forEach(function (k) { var f = document.createElement("i"); f.className = k; c.appendChild(f); });
    row.appendChild(c);
  });
  document.getElementById("blocks").appendChild(row);
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)"), calm = window.matchMedia("(prefers-reduced-motion: reduce)");
  // stop everything that moves when the tab is hidden or the stack is off screen
  document.addEventListener("visibilitychange", function () { root.classList.toggle("paused", document.hidden); });
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (e) { root.classList.toggle("still", !e[0].isIntersecting); }).observe(document.querySelector(".stage"));
  }
  if (!fine.matches || calm.matches) { return; }
  Array.prototype.forEach.call(document.querySelectorAll(".tile"), function (t) {
    t.addEventListener("pointermove", function (e) {
      var r = t.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
      t.style.setProperty("--ry", (x * 6).toFixed(2) + "deg"); t.style.setProperty("--rx", (-y * 6).toFixed(2) + "deg");
    });
    t.addEventListener("pointerleave", function () { t.style.removeProperty("--rx"); t.style.removeProperty("--ry"); });
  });
  var deck = document.getElementById("deck"), queued = false, last = null;  // the stack leans a little toward the pointer, one write per frame
  document.addEventListener("pointermove", function (e) {
    last = e;
    if (queued) { return; }
    queued = true;
    window.requestAnimationFrame(function () {
      queued = false;
      deck.style.setProperty("--tz", (-32 + (last.clientX / window.innerWidth - .5) * 8).toFixed(1) + "deg");
      deck.style.setProperty("--tx", (58 - (last.clientY / window.innerHeight - .5) * 6).toFixed(1) + "deg");
    });
  }, { passive: true });
})();
