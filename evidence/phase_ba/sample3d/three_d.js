// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var fine = window.matchMedia("(hover: hover) and (pointer: fine)"), calm = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!fine.matches || calm.matches) { return; }
  Array.prototype.forEach.call(document.querySelectorAll(".tile"), function (t) {
    t.addEventListener("pointermove", function (e) {
      var r = t.getBoundingClientRect(), x = (e.clientX - r.left) / r.width - .5, y = (e.clientY - r.top) / r.height - .5;
      t.style.setProperty("--ry", (x * 6).toFixed(2) + "deg"); t.style.setProperty("--rx", (-y * 6).toFixed(2) + "deg");
    });
    t.addEventListener("pointerleave", function () { t.style.removeProperty("--rx"); t.style.removeProperty("--ry"); });
  });
  document.addEventListener("visibilitychange", function () { document.documentElement.classList.toggle("paused", document.hidden); });
})();
