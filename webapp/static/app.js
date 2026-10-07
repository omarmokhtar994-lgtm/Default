// © 2026 Omar Mokhtar. All rights reserved.
// Follows a run's status while it is in flight; reloads once it ends so the
// download and resume buttons appear. Nothing else runs in the browser.
(function () {
  "use strict";
  var run = document.querySelector("article.run");
  if (!run || run.dataset.final === "yes") { return; }
  var url = run.dataset.statusUrl;
  var word = run.querySelector(".status-word");
  var bar = run.querySelector(".stagebar");
  var log = run.querySelector("pre.log");

  function draw(s) {
    word.textContent = s.label;
    word.dataset.status = s.status;
    s.stages.forEach(function (stage, i) {
      var li = bar.children[i];
      if (!li) { return; }
      li.className = stage.state;
      li.firstChild.textContent = stage.label;
    });
    bar.setAttribute("aria-label", "Progress: " + s.label);
    if (log && s.log) {
      var atBottom = log.scrollTop + log.clientHeight >= log.scrollHeight - 8;
      log.textContent = s.log;
      if (atBottom) { log.scrollTop = log.scrollHeight; }
    }
  }

  function poll() {
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r.status === 302 || r.redirected) { window.location.reload(); return null; }
        return r.ok ? r.json() : null;
      })
      .then(function (s) {
        if (!s) { setTimeout(poll, 8000); return; }
        draw(s);
        if (s.final) { window.location.reload(); } else { setTimeout(poll, 3000); }
      })
      .catch(function () { setTimeout(poll, 8000); });
  }
  setTimeout(poll, 1500);
})();
