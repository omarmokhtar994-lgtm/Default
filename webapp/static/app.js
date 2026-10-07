// © 2026 Omar Mokhtar. All rights reserved.
// Follows a run while it is in flight: stage ring, status word, place in line,
// how fresh the data is, and a clear notice when the connection drops (the
// last known state stays on screen). Reloads once the run ends, so the wall,
// findings and downloads appear. The dashboard refreshes every 30 s while
// something is running or waiting.
// Chart tips: any mark with data-tip shows it on hover, or on tap on a phone.
// The same numbers are in each chart's table view.
(function () {
  "use strict";
  var marks = document.querySelectorAll("[data-tip]");
  if (!marks.length) { return; }
  var tip = document.createElement("div");
  tip.className = "tip";
  tip.hidden = true;
  document.body.appendChild(tip);
  function show(e) {
    var text = e.target.getAttribute && e.target.getAttribute("data-tip");
    if (!text) { tip.hidden = true; return; }
    tip.textContent = text;
    tip.hidden = false;
    var x = Math.min(e.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
    var y = e.clientY - tip.offsetHeight - 12;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = (y < 8 ? e.clientY + 18 : y) + "px";
  }
  document.addEventListener("pointermove", show);
  document.addEventListener("pointerdown", show);
  document.addEventListener("scroll", function () { tip.hidden = true; }, { passive: true });
})();

(function () {
  "use strict";
  var run = document.querySelector("article.run");
  if (!run) {
    if (document.querySelector(".now .ring") || /[1-9]\d* waiting/.test((document.querySelector(".now-queue .big") || {}).textContent || "")) {
      setTimeout(function () { window.location.reload(); }, 30000);
    }
    return;
  }
  if (run.dataset.final === "yes") { return; }
  var url = run.dataset.statusUrl;
  var word = run.querySelector(".status-word");
  var ringWord = run.querySelector(".ring-word");
  var arcs = run.querySelectorAll(".ring .arc");
  var steps = run.querySelectorAll(".ring-steps li");
  var eta = run.querySelector(".progress .eta");
  var fresh = run.querySelector(".progress .fresh");
  var live = run.querySelector(".live");
  var log = run.querySelector("details.tech pre.log");
  var message = run.querySelector("p.message");
  var lastGood = null;

  function ago() {
    if (!lastGood || !fresh) { return; }
    var s = Math.round((Date.now() - lastGood) / 1000);
    fresh.hidden = false;
    fresh.textContent = s < 5 ? "Updated just now" : "Updated " + s + " s ago";
  }

  function minutes(m) {
    m = Math.max(0, Math.round(m));
    if (m < 60) { return m + " min"; }
    var h = Math.floor(m / 60), r = m % 60;
    return h + " h" + (r ? " " + (r < 10 ? "0" : "") + r + " min" : "");
  }

  function draw(s) {
    word.textContent = s.label;
    word.dataset.status = s.status;
    if (ringWord) { ringWord.textContent = s.label; ringWord.dataset.status = s.status; }
    s.stages.forEach(function (stage, i) {
      if (arcs[i]) { arcs[i].setAttribute("class", "arc " + stage.state); }
      if (steps[i]) { steps[i].className = stage.state || "todo"; steps[i].textContent = stage.label; }
    });
    if (eta) {
      if (s.status === "QUEUED" && s.eta_text) {
        eta.textContent = s.eta_text;
      } else if (s.started && s.eta) {
        eta.textContent = "Running for " + minutes((s.server_time - s.started) / 60) + "; about " +
          minutes(s.eta.finishes_in_min) + " left, " + s.eta.basis + ".";
      }
    }
    if (log && s.log) { log.textContent = s.log; }
    if (message && s.message) { message.textContent = s.message.split("\n")[0]; message.dataset.status = s.status; }
  }

  function poll() {
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) {
        if (r.redirected) { window.location.reload(); return null; }
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.json();
      })
      .then(function (s) {
        if (!s) { return; }
        lastGood = Date.now();
        live.hidden = true;
        draw(s);
        ago();
        if (s.final) { window.location.reload(); } else { setTimeout(poll, 3000); }
      })
      .catch(function () { live.hidden = false; setTimeout(poll, 8000); });
  }
  setInterval(ago, 1000);
  setTimeout(poll, 1500);
})();
