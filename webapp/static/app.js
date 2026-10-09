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

// Back goes to the last page here that was a different page (Phase W): a save reloads the same page, so the
// browser's own previous page was often this one and Back looked dead. Pages are told apart by their path (the
// RTA on another day is still the RTA). With no such page, the link's own address (one level up) is used.
(function () {
  "use strict";
  var KEY = "ts-trail";
  var kind = window.location.pathname;
  var here = { url: window.location.pathname + window.location.search, kind: kind };
  var trail = [];
  try {
    trail = JSON.parse(window.sessionStorage.getItem(KEY) || "[]");
    if (!Array.isArray(trail)) { trail = []; }
  } catch (e) { trail = []; }
  var last = trail[trail.length - 1];
  if (!last || last.url !== here.url) { trail.push(here); }
  trail = trail.slice(-20);
  try { window.sessionStorage.setItem(KEY, JSON.stringify(trail)); } catch (e) { /* the link still works */ }
  var back = document.querySelector("[data-back]");
  if (!back) { return; }
  back.addEventListener("click", function (e) {
    for (var i = trail.length - 2; i >= 0; i--) {
      if (trail[i] && trail[i].kind !== kind && typeof trail[i].url === "string" && /^\/(?![\/\\])/.test(trail[i].url)) {
        e.preventDefault();
        try { window.sessionStorage.setItem(KEY, JSON.stringify(trail.slice(0, i))); } catch (err) { /* fine */ }
        window.location.href = trail[i].url;
        return;
      }
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

// Pickers that show their choice at once (program, week, day, measure). Picking
// another program on the week view shows its weeks (the latest is chosen).
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("[data-autosubmit]"), function (pick) {
    pick.addEventListener("change", function () {
      var week = pick.form.querySelector("select[name=week]");
      if (week && pick.name === "program") { week.disabled = true; }
      pick.form.submit();
    });
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

// Slot swap: two people swap whole weeks. Checked on a copy first; its problems are
// shown before the swap is kept (Yes) or dropped (No), like a shift change.
(function () {
  "use strict";
  var open = document.querySelector("[data-swap-open]");
  var dialog = document.getElementById("swap-dialog");
  if (!open || !dialog || typeof dialog.showModal !== "function") { if (open) { open.hidden = true; } return; }
  var token = document.querySelector("input[name=csrf_token]");
  var first = dialog.querySelector("select[name=first]");
  var second = dialog.querySelector("select[name=second]");
  var reason = dialog.querySelector("input[name=reason]");
  var result = dialog.querySelector(".dlg-result");
  var ask = dialog.querySelector(".dlg-ask");
  var keep = dialog.querySelector("[data-keep]");
  var title = dialog.querySelector("#swap-h");
  var needsReason = false, seq = 0;

  function post(url, fields) {
    var body = new URLSearchParams(fields);
    body.append("csrf_token", token ? token.value : "");
    return fetch(url, { method: "POST", credentials: "same-origin", body: body, headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function check() {
    keep.disabled = true;
    ask.hidden = true;
    dialog.classList.remove("red", "yellow");
    if (!first.value || !second.value || first.value === second.value) {
      title.textContent = "Swap slots";
      result.textContent = first.value && first.value === second.value ? "Pick two different people." : "Pick two people.";
      return;
    }
    var mine = ++seq;
    title.textContent = "Checking this swap…";
    result.textContent = "The independent validator is checking the week (a few seconds).";
    post(dialog.dataset.checkUrl, { first: first.value, second: second.value }).then(function (found) {
      if (mine !== seq) { return; }
      if (!found._ok) { title.textContent = "This swap cannot be made"; result.textContent = found.error || ""; return; }
      result.textContent = "";
      var reds = 0, list = document.createElement("ul");
      list.className = "sevlist";
      (found.added || []).forEach(function (p) {
        var li = document.createElement("li"), b = document.createElement("b");
        li.className = p.severity;
        reds += p.severity === "red" ? 1 : 0;
        b.textContent = p.severity === "red" ? "Rule broken: " : "Warning: ";
        li.appendChild(b);
        li.appendChild(document.createTextNode(p.text));
        list.appendChild(li);
      });
      var yellows = (found.added || []).length - reds;
      title.textContent = reds ? "This swap breaks " + reds + " rule" + (reds === 1 ? "" : "s")
        : yellows ? "This swap adds " + yellows + " warning" + (yellows === 1 ? "" : "s") : "This swap adds no problems";
      dialog.classList.toggle("red", reds > 0);
      dialog.classList.toggle("yellow", !reds && yellows > 0);
      if (list.childNodes.length) { result.appendChild(list); }
      needsReason = list.childNodes.length > 0;
      ask.hidden = !needsReason;
      keep.disabled = false;
    }).catch(function () { if (mine === seq) { result.textContent = "The check did not answer: try again."; } });
  }
  open.addEventListener("click", function () {
    first.value = ""; second.value = ""; reason.value = "";
    check();
    dialog.showModal();
    first.focus();
  });
  first.addEventListener("change", check);
  second.addEventListener("change", check);
  dialog.querySelector("[data-cancel]").addEventListener("click", function () { seq++; dialog.close(); });
  keep.addEventListener("click", function () {
    if (needsReason && !reason.value.trim()) { reason.focus(); reason.setAttribute("aria-invalid", "true"); return; }
    keep.disabled = true;
    post(dialog.dataset.swapUrl, { first: first.value, second: second.value, reason: reason.value.trim() })
      .then(function (saved) {
        if (!saved._ok) { keep.disabled = false; result.textContent = saved.error || "Not saved."; return; }
        window.location.href = saved.url;
      });
  });
})();

// The day: attendance, and breaks moved in 5-minute steps. A drag (timeline or
// board) or a click opens the break dialog with the new time, its gap warnings and
// the best times for that break; nothing is kept until Save (Yes).
(function () {
  "use strict";
  var root = document.querySelector("[data-day]");
  if (!root) { return; }
  var token = root.querySelector("input[name=csrf_token]");
  var step = parseInt(root.dataset.step, 10) || 30;
  var status = document.getElementById("day-status");

  function post(url, fields) {
    var body = new URLSearchParams(fields);
    body.append("csrf_token", token ? token.value : "");
    body.append("program", root.dataset.program);
    return fetch(url, { method: "POST", credentials: "same-origin", body: body, headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function toMin(hhmm) { var p = (hhmm || "0:0").split(":"); return parseInt(p[0], 10) * 60 + parseInt(p[1], 10); }
  function toHm(m) { m = ((m % 1440) + 1440) % 1440; return ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + (m % 60)).slice(-2); }
  function say(text) { if (status) { status.textContent = text; status.hidden = !text; } }

  // ---- attendance
  var att = document.getElementById("att-dialog");
  Array.prototype.forEach.call(root.querySelectorAll("select.att"), function (sel) {
    var was = sel.value;
    sel.addEventListener("change", function () {
      var parts = sel.value.split("|"), state = parts[0];
      var fields = { date: sel.dataset.date, associate: sel.dataset.name, status: state, billable: parts[1] === "1" ? "1" : "" };
      if (state !== "Late" && state !== "Left early" && parts.length < 2) {
        post(root.dataset.attUrl, fields).then(function (r) {
          if (r._ok) { window.location.reload(); return; }
          sel.value = was; say(r.error || "That was not saved.");
        });
        return;
      }
      if (!att || typeof att.showModal !== "function") { sel.value = was; return; }
      var from = att.querySelector("[data-from]"), to = att.querySelector("[data-to]");
      var hint = att.querySelector("[data-hint]"), result = att.querySelector(".dlg-result");
      att.querySelector("#att-h").textContent = state === "Late" ? "Late login" : state === "Left early" ? "Early leave" :
        state + (parts[1] === "1" ? " (billable)" : " (non-billable)");
      att.querySelector("[data-who]").textContent = sel.dataset.name + ", shift " + sel.dataset.shift;
      from.hidden = state === "Late";
      to.hidden = state === "Left early";
      from.firstChild.textContent = state === "Left early" ? "Left at " : "From ";
      to.firstChild.textContent = state === "Late" ? "Arrived at " : "To ";
      hint.textContent = state === "Late" || state === "Left early" ? "" : "Leave both empty for the whole shift.";
      from.querySelector("input").value = ""; to.querySelector("input").value = ""; result.textContent = "";
      var auxBox = att.querySelector("[data-aux]");  // an aux says who it is with and why (Phase T)
      if (auxBox) {
        auxBox.hidden = parts.length < 2;
        Array.prototype.forEach.call(auxBox.querySelectorAll("input, select"), function (i) {
          i.value = ""; i.dispatchEvent(new Event("change"));
        });
      }
      att.dataset.pending = JSON.stringify(fields);
      att.showModal();
      (state === "Late" ? to : from).querySelector("input").focus();
      att.onclose = function () { if (att.returnValue !== "saved") { sel.value = was; } att.returnValue = ""; };
    });
  });
  if (att) {
    att.querySelector("[data-cancel]").addEventListener("click", function () { att.close("cancel"); });
    att.addEventListener("input", function () { att.querySelector(".dlg-result").textContent = ""; });  // said, now typing
    att.querySelector("[data-keep]").addEventListener("click", function () {
      var fields = JSON.parse(att.dataset.pending || "{}");
      fields.from = att.querySelector("input[name=from]").value;
      fields.to = att.querySelector("input[name=to]").value;
      var withWhom = att.querySelector("[name=with_whom]"), why = att.querySelector("input[name=why]");
      var dept = att.querySelector("select[name=with_dept]");
      if (withWhom && !withWhom.closest("[hidden]")) {
        fields.with_whom = withWhom.value; fields.why = why.value; fields.with_dept = dept ? dept.value : "";
      }
      post(root.dataset.attUrl, fields).then(function (r) {
        if (r._ok) { att.close("saved"); window.location.reload(); return; }
        att.querySelector(".dlg-result").textContent = r.error || "That was not saved.";
      });
    });
  }

  // ---- breaks
  var dlg = document.getElementById("break-dialog");
  if (!dlg || typeof dlg.showModal !== "function") { return; }
  var input = dlg.querySelector("input[name=at]"), result = dlg.querySelector(".dlg-result");
  var fits = dlg.querySelector(".fits"), ask = dlg.querySelector(".dlg-ask"), keep = dlg.querySelector("[data-keep]");
  var current = null, seq = 0, warned = false;

  function advise() {
    var mine = ++seq;
    result.textContent = "Checking…";
    fits.hidden = true;
    post(root.dataset.adviceUrl, { date: current.date, associate: current.name, idx: current.idx, at: input.value,
                                   measure: root.dataset.measure }).then(function (found) {
      if (mine !== seq) { return; }
      result.textContent = "";
      if (!found._ok) { result.textContent = found.error || ""; warned = false; ask.hidden = true; keep.textContent = "Save"; return; }
      var list = document.createElement("ul");
      list.className = "sevlist";
      (found.warnings || []).forEach(function (w) {
        var li = document.createElement("li"), b = document.createElement("b");
        li.className = "yellow"; b.textContent = "Warning: ";
        li.appendChild(b); li.appendChild(document.createTextNode(w)); list.appendChild(li);
      });
      (found.channels || []).forEach(function (w) {  // Phase V: the channel a move would leave short
        var li = document.createElement("li"), b = document.createElement("b");
        li.className = "yellow"; b.textContent = "Channels: ";
        li.appendChild(b); li.appendChild(document.createTextNode(w)); list.appendChild(li);
      });
      if (list.childNodes.length) { result.appendChild(list); }
      warned = list.childNodes.length > 0;
      dlg.classList.toggle("yellow", warned);
      ask.hidden = !warned;
      keep.textContent = warned ? "Yes, keep " + input.value : "Save " + input.value;
      var ul = fits.querySelector("ul");
      ul.textContent = "";
      (found.fits || []).forEach(function (f) {
        var li = document.createElement("li"), b = document.createElement("button");
        b.type = "button";
        var m = Math.round(Math.abs(f.buffer) * 60);
        b.textContent = f.start + " to " + f.end + ": " + (f.buffer >= 0 ? "+" : "−") + Math.floor(m / 60) + ":" +
          ("0" + (m % 60)).slice(-2) + " buffer at its tightest";
        b.addEventListener("click", function () { input.value = f.start; advise(); });
        li.appendChild(b); ul.appendChild(li);
      });
      fits.hidden = !(found.fits || []).length;
    }).catch(function () { if (mine === seq) { result.textContent = "The check did not answer: try again."; } });
  }
  function openBreak(el, at) {
    current = { name: el.dataset.name, date: el.dataset.date, idx: el.dataset.idx };
    var personLink = dlg.querySelector("[data-person-link]");
    if (personLink && root.dataset.personUrl) {
      personLink.href = root.dataset.personUrl + "&who=" + encodeURIComponent(el.dataset.name) + "#person";
    }
    dlg.querySelector("#brk-h").textContent = "Move " + el.dataset.name + "'s " + el.dataset.kind;
    dlg.querySelector("[data-who]").textContent = el.dataset.minutes + " minutes" +
      (el.dataset.shift ? " · shift " + el.dataset.shift : "") + " · planned " + el.dataset.planned +
      (el.dataset.start !== el.dataset.planned ? " · now " + el.dataset.start : "");
    input.value = at || el.dataset.start;
    keep.disabled = false;
    dlg.showModal();
    input.focus();
    advise();
  }
  dlg.querySelectorAll("[data-step]").forEach(function (b) {
    b.addEventListener("click", function () { input.value = toHm(toMin(input.value) + parseInt(b.dataset.step, 10)); advise(); });
  });
  input.addEventListener("change", advise);
  dlg.querySelector("[data-cancel]").addEventListener("click", function () { seq++; dlg.close(); });
  function save(at) {
    keep.disabled = true;
    post(root.dataset.breakUrl, { date: current.date, associate: current.name, idx: current.idx, at: at })
      .then(function (r) {
        if (r._ok) { window.location.reload(); return; }
        keep.disabled = false; result.textContent = r.error || "That was not saved.";
      });
  }
  keep.addEventListener("click", function () { save(input.value); });
  dlg.querySelector("[data-plan]").addEventListener("click", function () { save(""); });

  // timeline: drag a break sideways (5-minute steps), or Enter / click to type the time
  Array.prototype.forEach.call(root.querySelectorAll("rect.brk"), function (rect) {
    rect.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openBreak(rect); }
    });
    rect.addEventListener("pointerdown", function (e) {
      var svg = rect.ownerSVGElement, box = svg.getBoundingClientRect(), x0 = parseFloat(rect.getAttribute("x"));
      var startX = e.clientX, moved = 0;
      rect.setPointerCapture(e.pointerId);
      function move(ev) {
        moved = Math.round((ev.clientX - startX) / box.width * 1440 / 5) * 5;
        rect.setAttribute("x", x0 + moved);
      }
      function up() {
        rect.removeEventListener("pointermove", move);
        rect.removeEventListener("pointerup", up);
        rect.setAttribute("x", x0);
        openBreak(rect, moved ? toHm(toMin(rect.dataset.start) + moved) : null);
      }
      rect.addEventListener("pointermove", move);
      rect.addEventListener("pointerup", up);
    });
  });

  // board: drag a break chip to another row (same minute within the interval), or click it
  var dragged = null;
  Array.prototype.forEach.call(root.querySelectorAll("button.chip-move"), function (b) {  // from one person's day
    b.addEventListener("click", function () {
      var person = document.getElementById("person-dialog");
      if (person && person.open) { person.close(); }
      openBreak(b);
    });
  });
  Array.prototype.forEach.call(root.querySelectorAll("button.chip[data-idx]"), function (chip) {
    chip.addEventListener("click", function () { openBreak(chip); });
    chip.addEventListener("dragstart", function (e) { dragged = chip; e.dataTransfer.setData("text/plain", chip.dataset.name); });
  });
  Array.prototype.forEach.call(root.querySelectorAll(".rb-row[data-t]"), function (row) {
    row.addEventListener("dragover", function (e) { if (dragged) { e.preventDefault(); row.classList.add("drop"); } });
    row.addEventListener("dragleave", function () { row.classList.remove("drop"); });
    row.addEventListener("drop", function (e) {
      e.preventDefault();
      row.classList.remove("drop");
      if (!dragged) { return; }
      var start = toMin(dragged.dataset.start);
      openBreak(dragged, toHm(parseInt(row.dataset.t, 10) + start % step));
      dragged = null;
    });
  });
})();

// Wallboard: reload every minute while it shows today live.
(function () {
  "use strict";
  var wall = document.querySelector("[data-wallboard]");
  if (wall && wall.dataset.live === "yes") { setTimeout(function () { window.location.reload(); }, 60000); }
})();

// Print buttons (the handover note).
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("[data-print]"), function (b) {
    b.addEventListener("click", function () { window.print(); });
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

// The upload form: picking a program (and LOB) fills in what its program starts
// from: the first weekday (Sunday or Monday), the run length and the advanced
// options; a date or option the person picked themselves is kept.
(function () {
  "use strict";
  var pick = document.querySelector("select[data-program-pick]");
  var select = document.querySelector("select[name=week_start][data-start-days]");
  if (!pick || !select) { return; }
  var form = pick.form;
  var touched = {};
  Array.prototype.forEach.call(form.querySelectorAll("select, input[type=radio]"), function (el) {
    if (el !== pick) { el.addEventListener("change", function () { touched[el.name] = true; }); }
  });
  var from = select.getAttribute("data-today") || "";
  function defaults() {
    var option = pick.options[pick.selectedIndex];
    var group = option && option.parentNode.tagName === "OPTGROUP" ? option.parentNode : null;
    try { return JSON.parse((group && group.getAttribute("data-defaults")) || "{}"); } catch (e) { return {}; }
  }
  function apply() {
    var d = defaults();
    if (d.start_day !== undefined && !touched.week_start) {
      var around = new Date((select.value || from) + "T00:00:00");
      var hit = Array.prototype.filter.call(select.options, function (o) {
        return o.getAttribute("data-day") === String(d.start_day) && o.value &&
          Math.abs(new Date(o.value + "T00:00:00") - around) < 4 * 86400000;
      })[0];
      if (hit) { select.value = hit.value; }
    }
    if (d.run_mode && !touched.mode) {
      var radio = form.querySelector("input[name=mode][value=" + d.run_mode + "]");
      if (radio) { radio.checked = true; }
    }
    Object.keys(d.options || {}).forEach(function (name) {
      var field = form.querySelector("select[name=" + name + "]");
      if (field && !touched[name]) { field.value = d.options[name]; }
    });
  }
  pick.addEventListener("change", apply);
  if (pick.value) { apply(); }  // a program already picked (on the left or by the link) brings its defaults
})();

// The left menu: picking a program (and LOB) opens the same page for it; on a
// phone the menu starts closed above the page.
(function () {
  "use strict";
  var pick = document.querySelector("select[data-unit-pick]");
  if (pick) {
    pick.addEventListener("change", function () {
      var target = pick.getAttribute("data-target") || "/overview?program={key}";
      window.location = target.replace("{key}", encodeURIComponent(pick.value));
    });
  }
  var menu = document.querySelector("details[data-menu]");
  if (menu && window.matchMedia && window.matchMedia("(max-width: 900px)").matches) { menu.open = false; }
})();

// RTA's "+ Add" and one person's day (Phase R): drawn by the server as open dialogs, shown here as
// modals. The Add dialog asks the server what the floor would look like before anything is kept.
(function () {
  "use strict";
  ["add-dialog", "person-dialog"].forEach(function (id) {
    var d = document.getElementById(id);
    if (d && typeof d.showModal === "function") { d.close(); d.showModal(); }
  });
  var add = document.getElementById("add-dialog");
  var form = add && add.querySelector("form[data-preview]");
  if (!form || !form.querySelector("input[name=what]")) { return; }
  var effect = form.querySelector("[data-effect]"), length = form.querySelector("[data-length]");
  var billable = form.querySelector("[data-billable]"), from = form.querySelector("[data-from-label]");
  var submit = form.querySelector("button[type=submit]"), minutes = form.querySelector("select[name=minutes]");
  var whole = ["Unplanned leave", "Sick"], aux = ["Coaching", "Meeting", "Training", "System issue"];
  var usual = { "Break": "15", "Lunch": "30", "Overtime": "60", "VTO": "60", "Coaching": "30", "Meeting": "30",
                "Training": "60", "System issue": "15" };
  var seq = 0;
  // Day off cancelled (Phase S): the people off today, a Shift Library shift or typed start and end
  var working = form.querySelector("[data-who-working]"), off = form.querySelector("[data-who-off]");
  var dayoff = form.querySelector("[data-dayoff-fields]"), to = form.querySelector("[data-to-label]");
  var shiftPick = form.querySelector("select[data-shift-pick]");
  var fromInput = form.querySelector("input[name=from]"), toInput = form.querySelector("input[name=to]");
  function kind() { var c = form.querySelector("input[name=what]:checked"); return c ? c.value : ""; }
  function pickedShift() {
    var o = shiftPick && shiftPick.options[shiftPick.selectedIndex];
    return o && o.value ? o : null;
  }
  function shape(changedKind) {
    var k = kind(), calling = k === "Day off cancelled", isAux = aux.indexOf(k) >= 0;
    var auxFields = form.querySelector("[data-aux-fields]");
    if (auxFields) {
      auxFields.hidden = !isAux;
      Array.prototype.forEach.call(auxFields.querySelectorAll("input, select"), function (i) { i.disabled = !isAux; i.required = isAux; });
    }
    length.hidden = whole.indexOf(k) >= 0 || k === "Late" || k === "Left early" || calling;
    billable.hidden = aux.indexOf(k) < 0;
    from.hidden = whole.indexOf(k) >= 0;
    from.querySelector("span").textContent = k === "Late" ? "Arrived at" : k === "Left early" ? "Left at" : "From";
    if (changedKind && usual[k]) { minutes.value = usual[k]; }
    if (off) {
      off.hidden = !calling; off.querySelector("select").disabled = !calling;
      working.hidden = calling; working.querySelector("select").disabled = calling;
      dayoff.hidden = !calling; to.hidden = !calling;
      var o = pickedShift();
      if (changedKind && calling && o) { fromInput.value = o.dataset.from; toInput.value = o.dataset.to; }
    }
    submit.textContent = calling ? "Call in" : "Add " + k.toLowerCase();
  }
  if (shiftPick) {
    shiftPick.addEventListener("change", function () {
      var o = pickedShift();
      if (o) { fromInput.value = o.dataset.from; toInput.value = o.dataset.to; }
    });
    [fromInput, toInput].forEach(function (el) {
      el.addEventListener("change", function () {
        var o = pickedShift();  // typed times that no longer match the picked shift are typed times
        if (o && (fromInput.value !== o.dataset.from || toInput.value !== o.dataset.to)) { shiftPick.value = ""; }
      });
    });
  }
  function preview() {
    var mine = ++seq;
    fetch(form.dataset.preview, { method: "POST", credentials: "same-origin", body: new URLSearchParams(new FormData(form)),
                                  headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); })
      .then(function (d) {
        if (mine !== seq) { return; }
        effect.textContent = d._ok ? d.text : (d.error || "That cannot be added.");
        effect.className = "effect " + (d._ok ? d.level : "bad");
        showChannels(d._ok ? d : {});
      })
      .catch(function () { if (mine === seq) { effect.textContent = "The effect could not be worked out; you can still add it."; } });
  }
  // Phase V: what the booking does to the channels, and times that keep every channel and language covered
  var channelEffect = form.querySelector("[data-channel-effect]");
  function showChannels(d) {
    if (!channelEffect) { return; }
    channelEffect.textContent = "";
    var lines = d.channels || [];
    channelEffect.hidden = lines.length === 0;
    lines.forEach(function (line) {
      var p = document.createElement("p");
      p.textContent = "Channels: " + line;
      channelEffect.appendChild(p);
    });
    if (lines.length && d.better && d.better.length) {
      var p = document.createElement("p");
      p.textContent = "Times that keep every channel and language covered: ";
      d.better.forEach(function (t) {
        var b = document.createElement("button");
        b.type = "button";
        b.className = "chip";
        b.textContent = "Use " + t;
        b.addEventListener("click", function () { fromInput.value = t; preview(); });
        p.appendChild(b);
      });
      channelEffect.appendChild(p);
    } else if (lines.length) {
      var q = document.createElement("p");
      q.textContent = "No nearby time keeps every channel covered; booking anyway is allowed and stays on the Channels tab.";
      channelEffect.appendChild(q);
    }
  }
  form.addEventListener("change", function (e) { shape(e.target.name === "what"); preview(); });
  shape(true);
  preview();
})();

// The upload form (Phase R): build the schedule with the engine, or upload a ready one (shifts already made;
// the engine does not run, so its run length and options are hidden).
(function () {
  "use strict";
  var kinds = document.querySelectorAll("input[data-run-kind]");
  if (!kinds.length) { return; }
  var form = kinds[0].form;
  function shape() {
    var picked = form.querySelector("input[data-run-kind]:checked");
    var ready = picked && picked.value === "ready";
    Array.prototype.forEach.call(form.querySelectorAll("[data-build-only]"), function (el) { el.hidden = ready; });
    var button = form.querySelector("[data-submit-label]");
    if (button) { button.textContent = ready ? "Check and upload" : "Check and run"; }
  }
  Array.prototype.forEach.call(kinds, function (k) { k.addEventListener("change", shape); });
  shape();
})();

// "With" from the program's lists (Phase U): the department first, then only the people in it.
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("select[data-with-dept]"), function (dept) {
    var scope = dept.closest("form") || dept.parentNode.parentNode;
    var person = scope.querySelector("select[data-with-person]");
    if (!person) { return; }
    function show() {
      Array.prototype.forEach.call(person.options, function (o) {
        if (!o.value) { return; }
        var mine = o.dataset.dept === dept.value;
        o.hidden = !mine; o.disabled = !mine;
        if (!mine && o.selected) { person.value = ""; }
      });
    }
    dept.addEventListener("change", show);
    show();
  });
})();

// Phase V: a click on a cell of the channel grid fills in "Set the block" (who, from, to one minimum block later)
(function () {
  const form = document.querySelector("[data-cp-edit]");
  const table = document.querySelector(".cp-grid");
  if (!form || !table) return;
  const block = parseInt(table.dataset.block || "60", 10);
  const minutes = (t) => parseInt(t.slice(0, 2), 10) * 60 + parseInt(t.slice(3, 5), 10);
  const clock = (m) => String(Math.floor(m / 60) % 24).padStart(2, "0") + ":" + String(m % 60).padStart(2, "0");
  table.addEventListener("click", (event) => {
    const cell = event.target.closest("[data-cp-cell]");
    if (!cell) return;
    const start = minutes(cell.dataset.t);
    let shiftEnd = minutes(cell.closest("tr").dataset.end || "23:59");
    if (shiftEnd <= start) shiftEnd += 1440;
    form.elements.who.value = cell.dataset.who;
    form.elements.start.value = cell.dataset.t;
    form.elements.end.value = clock(Math.min(start + block, shiftEnd));
    form.elements.channel.focus();
  });
})();

// Exports (Phase W): the file comes through a script so the page can say what is happening ("Preparing", then
// "Ready" or what went wrong) instead of loading with no end; without a script the form is a plain download.
(function () {
  "use strict";
  var form = document.querySelector("form[data-export]");
  if (!form || !window.fetch || !window.URLSearchParams || !window.FormData || !window.URL) { return; }
  var box = form.querySelector("[data-export-status]");
  var button = form.querySelector("button[type=submit]");
  if (!box || !button) { return; }
  var label = button.textContent;
  function failed(text) {
    box.className = "alert bad";
    box.textContent = "";
    var h = document.createElement("h3");
    h.textContent = "The export did not finish";
    var p = document.createElement("p");
    p.textContent = text;
    box.appendChild(h);
    box.appendChild(p);
  }
  form.addEventListener("submit", function (e) {
    if (typeof form.checkValidity === "function" && !form.checkValidity()) { return; }
    e.preventDefault();
    var url = form.action + "?" + new URLSearchParams(new FormData(form)).toString();
    var started = Date.now();
    var seconds = function () { return Math.round((Date.now() - started) / 1000); };
    button.disabled = true;
    button.textContent = "Preparing your export…";
    box.hidden = false;
    box.className = "exp-wait";
    var tick = function () {
      box.textContent = seconds() + " s. Working out the period you picked; long periods take longer. You can keep " +
        "working in another tab: the file downloads by itself when it is ready.";
    };
    tick();
    var timer = window.setInterval(tick, 1000);
    fetch(url, { headers: { "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) {
          return r.json().catch(function () { return {}; }).then(function (j) {
            throw new Error(j.error || ("The server answered " + r.status + ". Try again, or pick a shorter period."));
          });
        }
        if (r.redirected && /^\/login(?:$|\?)/.test(new URL(r.url).pathname + new URL(r.url).search)) {
          throw new Error("You were signed out: sign in again, then download.");
        }
        if ((r.headers.get("Content-Type") || "").indexOf("text/html") === 0) {
          throw new Error("The server sent a page instead of the file. Reload this page, then download again.");
        }
        var said = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(r.headers.get("Content-Disposition") || "");
        var name = said ? decodeURIComponent(said[1]) : "Team_Scheduler_export";
        return r.blob().then(function (blob) { return { blob: blob, name: name }; });
      })
      .then(function (got) {
        var href = window.URL.createObjectURL(got.blob);
        var link = document.createElement("a");
        link.href = href;
        link.download = got.name;
        document.body.appendChild(link);
        link.click();
        link.remove();
        box.className = "exp-ok";
        box.textContent = "Ready: " + got.name + " (" + Math.max(1, Math.round(got.blob.size / 1024)) + " KB) " +
          "downloaded in " + seconds() + " s. ";
        var again = document.createElement("a");
        again.href = href;
        again.download = got.name;
        again.textContent = "Download again";
        box.appendChild(again);
      })
      .catch(function (err) {
        failed(err && err.message && err.message !== "Failed to fetch" ? err.message :
          "The connection was lost before the file arrived. Pick a shorter period, then download again.");
      })
      .then(function () {
        window.clearInterval(timer);
        button.disabled = false;
        button.textContent = label;
      });
  });
})();

// The upload form (Phase W): once a program and a start date are picked, say what that week already has, so a
// second schedule for the same week is a choice, not a surprise. Nothing is blocked.
(function () {
  "use strict";
  var box = document.querySelector("[data-week-check]");
  if (!box || !window.fetch) { return; }
  var form = box.closest("form");
  var program = form && form.querySelector("select[name=program]");
  var week = form && form.querySelector("select[name=week_start]");
  if (!program || !week) { return; }
  var text = box.querySelector("p");
  function check() {
    if (!program.value || !week.value) { box.hidden = true; return; }
    var url = box.getAttribute("data-url") + "?program=" + encodeURIComponent(program.value) +
      "&week=" + encodeURIComponent(week.value);
    fetch(url, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : { count: 0 }; })
      .then(function (j) {
        text.textContent = j.text || "";
        box.hidden = !j.count;
      }).catch(function () { box.hidden = true; });
  }
  program.addEventListener("change", check);
  week.addEventListener("change", check);
  check();
})();
