// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var note = document.getElementById("note");
  if (!note) { return; }
  var hide = note.querySelector(".x");
  function show() { note.hidden = false; note.classList.add("show"); }
  window.setTimeout(show, 600);
  if (hide) { hide.addEventListener("click", function () { note.hidden = true; }); }
})();
