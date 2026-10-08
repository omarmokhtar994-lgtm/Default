// © 2026 Omar Mokhtar. All rights reserved.
// Follows a run while it is in flight: stage ring, status word, place in line,
// how fresh the data is, and a clear notice when the connection drops (the
// last known state stays on screen). Reloads once the run ends, so the wall,
// findings and downloads appear. The dashboard refreshes every 30 s while
// something is running or waiting.
// The look: with no choice saved the page follows the device, so the switch
// offers the other one.
(function () {
  "use strict";
  var button = document.querySelector("[data-theme-toggle]");
  if (!button || document.documentElement.getAttribute("data-theme")) { return; }
  if (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches) {
    button.value = "dark";
    button.textContent = "Dark look";
  }
})();

// Back goes to the page you came from when you came from this site; the
// link's own address (the page's parent) is the fallback.
(function () {
  "use strict";
  var back = document.querySelector("[data-back]");
  if (!back) { return; }
  back.addEventListener("click", function (e) {
    if (document.referrer.indexOf(window.location.origin + "/") === 0 && window.history.length > 1) {
      e.preventDefault();
      window.history.back();
    }
  });
})();

// The upload area takes a dropped workbook (Excel .xlsx only); the file
// button still works the usual way.
(function () {
  "use strict";
  var zone = document.querySelector("[data-drop]");
  if (!zone) { return; }
  var input = zone.querySelector("input[type=file]");
  var chosen = zone.querySelector(".chosen");
  function show(text, bad) {
    chosen.textContent = text;
    chosen.classList.toggle("bad", !!bad);
  }
  input.addEventListener("change", function () {
    if (input.files.length) { show(input.files[0].name); }
  });
  ["dragenter", "dragover"].forEach(function (kind) {
    zone.addEventListener(kind, function (e) { e.preventDefault(); zone.classList.add("over"); });
  });
  ["dragleave", "drop"].forEach(function (kind) {
    zone.addEventListener(kind, function () { zone.classList.remove("over"); });
  });
  zone.addEventListener("drop", function (e) {
    e.preventDefault();
    var files = e.dataTransfer && e.dataTransfer.files;
    if (!files || !files.length) { return; }
    if (!/\.xlsx$/i.test(files[0].name)) {
      show(files[0].name + " is not an Excel workbook (.xlsx)." +
           (input.files.length ? " Still chosen: " + input.files[0].name : ""), true);
      return;
    }
    input.files = files;
    show(files[0].name);
  });
  // A file dropped anywhere else would open in the browser and leave the site.
  ["dragover", "drop"].forEach(function (kind) {
    document.addEventListener(kind, function (e) {
      if (!zone.contains(e.target)) { e.preventDefault(); }
    });
  });
})();

// Week view: picking another program shows its weeks (the latest is chosen).
(function () {
  "use strict";
  var pick = document.querySelector("[data-autosubmit]");
  if (!pick) { return; }
  pick.addEventListener("change", function () {
    var week = pick.form.querySelector("select[name=week]");
    if (week) { week.disabled = true; }
    pick.form.submit();
  });
})();

// Schedule editor: click a shift, pick the new one; the change is checked on a
// copy first and its problems are shown before it is kept (Yes) or dropped (No).
(function () {
  "use strict";
  var grid = document.querySelector("table.edgrid");
  var dialog = document.getElementById("edit-dialog");
  if (!grid || !dialog || typeof dialog.showModal !== "function") { return; }
  var token = document.querySelector("input[name=csrf_token]");
  var select = dialog.querySelector("select[name=value]");
  var reason = dialog.querySelector("input[name=reason]");
  var result = dialog.querySelector(".dlg-result");
  var ask = dialog.querySelector(".dlg-ask");
  var keep = dialog.querySelector("[data-keep]");
  var who = dialog.querySelector("[data-who]");
  var title = dialog.querySelector("#dlg-h");
  var cell = null, needsReason = false, seq = 0;

  function post(url, fields) {
    var body = new URLSearchParams(fields);
    body.append("csrf_token", token ? token.value : "");
    return fetch(url, { method: "POST", credentials: "same-origin", body: body,
                        headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }

  function show(found) {
    result.textContent = "";
    var list = document.createElement("ul");
    list.className = "sevlist";
    (found.added || []).forEach(function (p) {
      var li = document.createElement("li");
      li.className = p.severity;
      var b = document.createElement("b");
      b.textContent = (p.severity === "red" ? "Rule broken: " : "Warning: ");
      li.appendChild(b);
      li.appendChild(document.createTextNode(p.text));
      list.appendChild(li);
    });
    var reds = (found.added || []).filter(function (p) { return p.severity === "red"; }).length;
    var yellows = (found.added || []).length - reds;
    title.textContent = reds ? "This change breaks " + reds + " rule" + (reds === 1 ? "" : "s")
      : yellows ? "This change adds " + yellows + " warning" + (yellows === 1 ? "" : "s") : "This change adds no problems";
    dialog.classList.toggle("red", reds > 0);
    dialog.classList.toggle("yellow", !reds && yellows > 0);
    if (list.childNodes.length) { result.appendChild(list); }
    needsReason = list.childNodes.length > 0;
    ask.hidden = !needsReason;
    keep.disabled = false;
  }

  function check() {
    var mine = ++seq;
    keep.disabled = true;
    title.textContent = "Checking this change…";
    result.textContent = "The independent validator is checking the week (a few seconds).";
    if (select.value === cell.dataset.value) {
      title.textContent = "No change";
      result.textContent = "This is the shift already planned.";
      return;
    }
    post(grid.dataset.checkUrl, { associate: cell.dataset.name, day: cell.dataset.day, value: select.value })
      .then(function (found) {
        if (mine !== seq) { return; }
        if (!found._ok) { title.textContent = "This change cannot be made"; result.textContent = found.error || ""; return; }
        show(found);
      })
      .catch(function () { if (mine === seq) { result.textContent = "The check did not answer: try again."; } });
  }

  grid.addEventListener("click", function (e) {
    var b = e.target.closest("button.ed");
    if (!b) { return; }
    cell = b;
    who.textContent = b.dataset.name + ", " + b.dataset.day + ": now " + (b.dataset.value || "nothing");
    select.value = b.dataset.value;
    reason.value = "";
    ask.hidden = true;
    keep.disabled = true;
    dialog.classList.remove("red", "yellow");
    title.textContent = "Change a shift";
    result.textContent = "Pick the new shift.";
    dialog.showModal();
    select.focus();
  });
  select.addEventListener("change", check);
  dialog.querySelector("[data-cancel]").addEventListener("click", function () { seq++; dialog.close(); });
  keep.addEventListener("click", function () {
    if (needsReason && !reason.value.trim()) { reason.focus(); reason.setAttribute("aria-invalid", "true"); return; }
    keep.disabled = true;
    post(grid.dataset.changeUrl, { associate: cell.dataset.name, day: cell.dataset.day, value: select.value,
                                   reason: reason.value.trim() })
      .then(function (saved) {
        if (!saved._ok) { keep.disabled = false; result.textContent = saved.error || "Not saved."; return; }
        window.location.href = saved.url;
      });
  });
})();

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
