// © 2026 Omar Mokhtar. All rights reserved.
// Follows a run while it is in flight: stage ring, status word, place in line,
// how fresh the data is, and a clear notice when the connection drops (the
// last known state stays on screen). Reloads once the run ends, so the wall,
// findings and downloads appear. The dashboard refreshes every 30 s while
// something is running or waiting.
// A list that acts when it changes (attendance, a picker that shows another page) waits for Enter when the
// keyboard moves it (Phase XY, review finding 2): on a closed list one arrow press changes the value, so it used to
// save or leave the page on the first key. Enter acts; Esc or leaving the field puts the saved value back. A pick
// with the mouse, or from the open list, acts at once as before.
function keyedPick(field, act, says) {
  "use strict";
  var saved = field.value, keyed = false, note = null;
  var moves = /^(ArrowUp|ArrowDown|ArrowLeft|ArrowRight|Home|End|PageUp|PageDown)$/;
  function shown(value) {
    var o = field.options ? Array.prototype.filter.call(field.options, function (x) { return x.value === value; })[0] : null;
    return o ? o.text : value;
  }
  function clear() {
    field.classList.remove("pending");
    if (note) { note.parentNode.removeChild(note); note = null; }
  }
  function putBack() { if (note) { field.value = saved; clear(); } }
  field.addEventListener("keydown", function (e) {
    if (note && e.key === "Enter") { e.preventDefault(); clear(); act(); return; }
    if (note && e.key === "Escape") { e.preventDefault(); e.stopPropagation(); putBack(); return; }
    keyed = !e.altKey && !e.ctrlKey && !e.metaKey && (moves.test(e.key) || (e.key.length === 1 && e.key !== " "));
  });
  field.addEventListener("pointerdown", function () { keyed = false; });
  field.addEventListener("blur", putBack);
  field.addEventListener("change", function () {
    if (!keyed) { clear(); act(); return; }
    keyed = false;
    if (field.value === saved) { clear(); return; }
    field.classList.add("pending");
    var text = says(shown(field.value), shown(saved));
    if (note) { note.textContent = text; return; }
    note = document.createElement("p");
    note.className = "pick-note";
    note.setAttribute("role", "status");
    var after = field.closest(".tl-row") || field.closest("label") || field;
    after.parentNode.insertBefore(note, after.nextSibling);
    var mine = note;
    setTimeout(function () { if (note === mine) { mine.textContent = text; } }, 30);  // an empty live region first, then its words, so it is read out
  });
}
function showSays(next) { return "Press Enter to show " + next + ", or Esc to go back."; }

// Home refreshes every 30 s while something runs or waits, until the New run form is in use (Phase XY, review
// finding 2): a reload then would drop the chosen workbook. From then on the running schedule's ring is redrawn in
// place, as the run page does, and when it ends the panel says so with a link.
function homeRefresh(now) {
  "use strict";
  var form = document.querySelector("#newrun form"), touched = false, url = now.getAttribute("data-status-url");
  function inUse() {
    if (touched) { return; }
    touched = true;
    var note = document.createElement("p");
    note.className = "notice paused";
    note.textContent = "Updates paused while you fill in this form. They start again when you submit it.";
    form.insertBefore(note, form.firstChild);
  }
  if (form) { form.addEventListener("input", inUse); form.addEventListener("change", inUse); }
  function finished() {
    var link = now.querySelector(".now-title"), line = document.createElement("p");
    line.className = "now-done";
    line.setAttribute("role", "status");
    line.appendChild(document.createTextNode("This schedule finished. "));
    var open = document.createElement("a");
    open.href = link ? link.getAttribute("href") : "/";
    open.textContent = "Open it";
    line.appendChild(open);
    (now.querySelector(".now-text") || now).appendChild(line);
  }
  function tick() {
    if (!touched) { window.location.reload(); return; }
    if (!url) { return; }  // only waiting runs: nothing on the page to redraw
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok || r.redirected) { throw new Error("HTTP " + r.status); } return r.json(); })
      .then(function (s) {
        var word = now.querySelector(".ring-word"), arcs = now.querySelectorAll(".ring .arc");
        if (word) { word.textContent = s.label; word.dataset.status = s.status; }
        s.stages.forEach(function (stage, i) { if (arcs[i]) { arcs[i].setAttribute("class", "arc " + stage.state); } });
        if (s.final) { finished(); } else { setTimeout(tick, 30000); }
      })
      .catch(function () { setTimeout(tick, 30000); });
  }
  setTimeout(tick, 30000);
}

// The look: with no choice saved the page follows the device (Night watch, or Tide when the device is light), so the
// button for that look is shown as the one in use.
(function () {
  "use strict";
  var looks = document.querySelectorAll("button.look");
  if (!looks.length || document.documentElement.getAttribute("data-theme")) { return; }
  var light = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches;
  Array.prototype.forEach.call(looks, function (b) { b.setAttribute("aria-pressed", b.value === (light ? "light" : "dark") ? "true" : "false"); });
})();

// A focused or linked item stops below the sticky top bar (Phase XY, review finding 3). app.css gives a padding per
// screen width; a long name can wrap the bar to two rows, so the padding follows the bar's measured height.
(function () {
  "use strict";
  var bar = document.querySelector("header.top");
  if (!bar || typeof ResizeObserver !== "function") { return; }
  new ResizeObserver(function () {
    var h = bar.getBoundingClientRect().height;
    document.documentElement.style.scrollPaddingTop = h ? Math.ceil(h + 12) + "px" : "";
  }).observe(bar);
})();

// Back goes to the last page here that was a different page (Phase W): a save reloads the same page, so the
// browser's own previous page was often this one and Back looked dead. Pages are told apart by their path (the
// RTA on another day is still the RTA). With no such page, the link's own address (one level up) is used. The
// sign-in page is never a place to go back to (Phase AC).
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
  if (kind !== "/login" && (!last || last.url !== here.url)) { trail.push(here); }
  trail = trail.slice(-20);
  try { window.sessionStorage.setItem(KEY, JSON.stringify(trail)); } catch (e) { /* the link still works */ }
  var back = document.querySelector("[data-back]");
  if (!back) { return; }
  back.addEventListener("click", function (e) {
    for (var i = trail.length - 2; i >= 0; i--) {
      if (trail[i] && trail[i].kind !== kind && trail[i].kind !== "/login" && typeof trail[i].url === "string" &&
          /^\/(?![\/\\])/.test(trail[i].url)) {
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
    keyedPick(pick, function () {
      var week = pick.form.querySelector("select[name=week]");
      if (week && pick.name === "program") { week.disabled = true; }
      pick.form.submit();
    }, showSays);
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
  var shift = parseInt(root.dataset.shift, 10) || 0;  // Phase AI: times show this many minutes past the schedule's
  var status = document.getElementById("day-status");

  function post(url, fields) {
    var body = new URLSearchParams(fields);
    body.append("csrf_token", token ? token.value : "");
    body.append("program", root.dataset.program);
    body.append("tz", root.dataset.tz || "");  // the server reads the times as shown in this zone
    if (root.dataset.merge) { body.append("merge", "1"); }  // Phase AP: the page shows every LOB of the program; the server finds the person's LOB
    return fetch(url, { method: "POST", credentials: "same-origin", body: body, headers: { "Accept": "application/json" } })
      .then(function (r) { return r.json().then(function (d) { d._ok = r.ok; return d; }); });
  }
  function toMin(hhmm) { var p = (hhmm || "0:0").split(":"); return parseInt(p[0], 10) * 60 + parseInt(p[1], 10); }
  function toHm(m) { m = ((m % 1440) + 1440) % 1440; return ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + (m % 60)).slice(-2); }
  function say(text) { if (status) { status.textContent = text; status.hidden = !text; } }

  // ---- attendance
  var att = document.getElementById("att-dialog");
  // Phase AY (owner, 2026-10-23): a late login is from the allowance (2 hours, 2 times a month) or an incident; an early leave is always
  // from the allowance. The dialog says the duration and count as the time is typed, and past a limit asks for the account manager's
  // approval and a comment.
  var lateState = "", lateTimer = 0;
  function lateField(name) { return att ? att.querySelector("[name=" + name + "]") : null; }
  function lateKind() {
    if (lateState === "Left early") { return "allowance"; }
    var on = att.querySelector("input[name=late_kind]:checked");
    return on ? on.value : "";
  }
  function lateSetup(state) {
    lateState = state === "Late" || state === "Left early" ? state : "";
    if (!att) { return; }
    var box = att.querySelector("[data-late-kind]"), pol = att.querySelector("[data-policy]"), ok = att.querySelector("[data-approval]");
    box.hidden = lateState !== "Late";
    pol.hidden = !lateState; ok.hidden = true;
    Array.prototype.forEach.call(att.querySelectorAll("input[name=late_kind]"), function (r) { r.checked = false; });
    lateField("am_ok").checked = false; lateField("am_note").value = "";
    att.querySelector("[data-policy-text]").textContent = lateState === "Late" ? "Choose how this late login counts, then the time." : "";
  }
  function lateCheck() {
    if (!lateState) { return; }
    var kind = lateKind(), text = att.querySelector("[data-policy-text]"), ok = att.querySelector("[data-approval]");
    var when = (lateState === "Late" ? att.querySelector("input[name=to]") : att.querySelector("input[name=from]")).value;
    if (!kind) { text.textContent = "Choose how this late login counts, then the time."; ok.hidden = true; return; }
    if (!when) { text.textContent = ""; ok.hidden = true; return; }
    var pending = JSON.parse(att.dataset.pending || "{}");
    post(root.dataset.attCheckUrl, { date: pending.date, associate: pending.associate, status: lateState, from: att.querySelector("input[name=from]").value,
                                      to: att.querySelector("input[name=to]").value, late_kind: kind }).then(function (r) {
      if (!r._ok) { text.textContent = r.error || ""; ok.hidden = true; return; }
      text.textContent = r.policy.text + (r.policy.over.length ? " Over the allowance: " + r.policy.over.join("; ") +
        ". Needs the account manager's approval as an exception: tick it and write a comment to book it anyway." : "");
      ok.hidden = !r.policy.over.length;
      att.classList.toggle("yellow", r.policy.over.length > 0);
    });
  }
  if (att) {
    att.addEventListener("input", function () { window.clearTimeout(lateTimer); lateTimer = window.setTimeout(lateCheck, 250); });
  }
  Array.prototype.forEach.call(root.querySelectorAll("select.att"), function (sel) {
    var was = sel.value;
    keyedPick(sel, function () {
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
        state + (state === "Bio break" ? "" : parts[1] === "1" ? " (billable)" : " (non-billable)");
      att.querySelector("[data-who]").textContent = sel.dataset.name + ", shift " + sel.dataset.shift;
      from.hidden = state === "Late";
      to.hidden = state === "Left early";
      from.firstChild.textContent = state === "Left early" ? "Left at " : "From ";
      to.firstChild.textContent = state === "Late" ? "Arrived at " : "To ";
      hint.textContent = state === "Late" || state === "Left early" ? "" : "Leave both empty for the whole shift.";
      from.querySelector("input").value = ""; to.querySelector("input").value = ""; result.textContent = "";
      var auxBox = att.querySelector("[data-aux]");  // an aux says who it is with and why (Phase T)
      if (auxBox) {
        auxBox.hidden = parts.length < 2 || state === "Bio break";
        Array.prototype.forEach.call(auxBox.querySelectorAll("input, select"), function (i) {
          i.value = ""; i.dispatchEvent(new Event("change"));
        });
      }
      att.dataset.pending = JSON.stringify(fields);
      lateSetup(state);
      att.showModal();
      (state === "Late" ? to : from).querySelector("input").focus();
      att.onclose = function () { if (att.returnValue !== "saved") { sel.value = was; } att.returnValue = ""; };
    }, function (next, now) { return "Not saved yet. Press Enter to save " + next + ", or Esc to keep " + now + "."; });
  });
  if (att) {
    att.querySelector("[data-cancel]").addEventListener("click", function () { att.close("cancel"); });
    att.addEventListener("input", function () { att.querySelector(".dlg-result").textContent = ""; });  // said, now typing
    att.querySelector("[data-keep]").addEventListener("click", function () {
      var fields = JSON.parse(att.dataset.pending || "{}");
      fields.from = att.querySelector("input[name=from]").value;
      fields.to = att.querySelector("input[name=to]").value;
      if (lateState) {
        var kind = lateKind(), result0 = att.querySelector(".dlg-result");
        if (!kind) { result0.textContent = "Choose whether this late login is from the allowance or an incident."; return; }
        fields.late_kind = kind;
        var approval = att.querySelector("[data-approval]");
        if (!approval.hidden) {
          if (!lateField("am_ok").checked || !lateField("am_note").value.trim()) {
            result0.textContent = "Tick that the account manager approved it and write a comment to book it."; return;
          }
          fields.am_ok = "1"; fields.am_note = lateField("am_note").value.trim();
        }
      }
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
  var cancelRow = dlg.querySelector("[data-cancel-row]"), cancelAsk = dlg.querySelector("[data-cancel-ask]");
  var stepper = dlg.querySelector(".stepper");
  function openBreak(el, at) {
    current = { name: el.dataset.name, date: el.dataset.date, idx: el.dataset.idx, kind: el.dataset.kind,
                minutes: el.dataset.minutes };
    // Phase AD: a cancelled break only comes back (Back to plan); any other can also be cancelled, with a reason
    var gone = el.dataset.cancelled === "1";
    if (cancelAsk) { cancelAsk.hidden = true; }
    if (cancelRow) { cancelRow.hidden = gone; }
    stepper.hidden = gone; keep.hidden = gone;
    if (gone) {
      dlg.querySelector("#brk-h").textContent = "Bring back " + el.dataset.name + "'s " + el.dataset.kind;
      dlg.querySelector("[data-who]").textContent = el.dataset.minutes + " minutes, planned " + el.dataset.planned +
        ", cancelled. Back to plan puts it back at " + el.dataset.planned + ".";
      result.textContent = ""; fits.hidden = true; ask.hidden = true;
      dlg.showModal();
      dlg.querySelector("[data-plan]").focus();
      return;
    }
    var personLink = dlg.querySelector("[data-person-link]");
    if (personLink && root.dataset.personUrl) {
      personLink.href = root.dataset.personUrl + "&who=" + encodeURIComponent(el.dataset.name) + "#person";
    }
    // Phase AF (D4): after a drag the dialog is the confirmation: "Change Break 1 from 12:00 to 12:30?"
    dlg.querySelector("#brk-h").textContent = at ? "Change " + el.dataset.name + "'s " + el.dataset.kind + " from " +
      el.dataset.start + " to " + at + "?" : "Move " + el.dataset.name + "'s " + el.dataset.kind;
    if (!keep.dataset.word) { keep.dataset.word = keep.textContent; }
    keep.textContent = at ? "Yes, change it" : keep.dataset.word;
    dlg.querySelector("[data-who]").textContent = el.dataset.minutes + " minutes" +
      (el.dataset.shift ? " · shift " + el.dataset.shift : "") + " · planned " + el.dataset.planned +
      (el.dataset.start !== el.dataset.planned ? " · now " + el.dataset.start : "");
    input.value = at || el.dataset.start;
    var missedBox = dlg.querySelector("input[name=missed]"); if (missedBox) { missedBox.checked = false; }
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
    var fields = { date: current.date, associate: current.name, idx: current.idx, at: at };
    var tick = dlg.querySelector("input[name=post]");  // Phase AB: "Post to the group", unticked for one change
    if (tick) { fields.post_asked = "1"; if (tick.checked) { fields.post = "1"; } }
    var missed = dlg.querySelector("input[name=missed]");  // Phase AV: the break was missed, kept as an incident
    if (missed && missed.checked && at) { fields.missed = "1"; }
    post(root.dataset.breakUrl, fields)
      .then(function (r) {
        if (r._ok) { window.location.reload(); return; }
        keep.disabled = false; result.textContent = r.error || "That was not saved.";
      });
  }
  keep.addEventListener("click", function () { save(input.value); });
  dlg.querySelector("[data-plan]").addEventListener("click", function () { save(""); });
  if (cancelRow && cancelAsk) {
    var why = cancelAsk.querySelector("input[name=why]"), cancelSaid = cancelAsk.querySelector("[data-cancel-said]");
    function cancelProblem(text) {  // said next to the Why field, which it is about
      cancelSaid.textContent = text;
      if (text) { why.setAttribute("aria-invalid", "true"); } else { why.removeAttribute("aria-invalid"); }
    }
    cancelRow.querySelector("[data-cancel-break]").addEventListener("click", function () {
      cancelAsk.querySelector("[data-cancel-what]").textContent = "Cancel " + current.kind + " for " + current.name + "?";
      cancelAsk.querySelector("[data-cancel-mins]").textContent = current.minutes;
      cancelAsk.hidden = false; why.value = ""; cancelProblem(""); why.focus();
    });
    cancelAsk.querySelector("[data-cancel-no]").addEventListener("click", function () { cancelAsk.hidden = true; });
    cancelAsk.querySelector("[data-cancel-yes]").addEventListener("click", function () {
      var yes = this;
      if (!why.value.trim()) { cancelProblem("Say why the break is cancelled."); why.focus(); return; }
      cancelProblem("");
      yes.disabled = true;
      var fields = { date: current.date, associate: current.name, idx: current.idx, why: why.value };
      var tick = dlg.querySelector("input[name=post]");
      if (tick) { fields.post_asked = "1"; if (tick.checked) { fields.post = "1"; } }
      post(root.dataset.cancelUrl, fields).then(function (r) {
        if (r._ok) { window.location.reload(); return; }
        yes.disabled = false; cancelProblem(r.error || "The break was not cancelled: try again.");
      });
    });
  }

  // timeline: drag a break sideways (5-minute steps), or Enter / click to type the time
  Array.prototype.forEach.call(root.querySelectorAll("rect.brk"), function (rect) {
    rect.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openBreak(rect); }
    });
    rect.addEventListener("pointerdown", function (e) {
      if (rect.dataset.cancelled === "1") { openBreak(rect); return; }  // nothing to drag: it only comes back
      var svg = rect.ownerSVGElement, box = svg.getBoundingClientRect(), x0 = parseFloat(rect.getAttribute("x"));
      var startX = e.clientX, moved = 0;
      rect.setPointerCapture(e.pointerId);
      function move(ev) {
        moved = Math.round((ev.clientX - startX) / box.width * svg.viewBox.baseVal.width / 5) * 5;
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

  // board: drag a break chip to another row (same minute within the interval), or click it. Phase AI (owner: "Drag and
  // drop for breacks is lagging ... several places in the box are lagging and not working"): a pointer drag, not the
  // browser's own, so any part of a row takes it, the chip says the time it moves to while carried, the page scrolls
  // near its edges, and it works with a finger too.
  Array.prototype.forEach.call(root.querySelectorAll("button.chip-move"), function (b) {  // from one person's day
    b.addEventListener("click", function () {
      var person = document.getElementById("person-dialog");
      if (person && person.open) { person.close(); }
      openBreak(b);
    });
  });
  var board = root.querySelector(".rb"), scroller = root.querySelector(".rb-scroll");
  var carry = null;  // {chip, x0, y0, ghost, row, at, lifted}
  function rowAt(x, y) {
    var el = document.elementFromPoint(x, y);
    return el && board && board.contains(el) ? el.closest(".rb-row[data-t]") : null;
  }
  function timeFor(chip, row) {  // the row's start (the schedule's minutes) and the chip's minutes into its interval
    var into = (((toMin(chip.dataset.start) - shift) % step) + step) % step;
    return toHm(parseInt(row.dataset.t, 10) + into + shift);
  }
  function mark(row) {
    if (carry.row === row) { return; }
    if (carry.row) { carry.row.classList.remove("rb-drop"); }
    carry.row = row;
    carry.at = row ? timeFor(carry.chip, row) : null;
    if (row) { row.classList.add("rb-drop"); }
    carry.ghost.lastChild.textContent = carry.at ? " to " + carry.at : "";
  }
  function edgeScroll(x, y) {  // carried near an edge: the page (and the board sideways) follows
    var dy = y < 70 ? -18 : (y > window.innerHeight - 70 ? 18 : 0);
    if (dy) { window.scrollBy(0, dy); }
    if (scroller) {
      var r = scroller.getBoundingClientRect();
      var dx = x < r.left + 50 ? -18 : (x > r.right - 50 ? 18 : 0);
      if (dx) { scroller.scrollLeft += dx; }
    }
  }
  function drop() {
    if (!carry) { return; }
    var done = carry;
    carry = null;
    if (done.row) { done.row.classList.remove("rb-drop"); }
    if (done.ghost) { done.ghost.remove(); }
    done.chip.classList.remove("lifted");
    if (done.lifted) {
      done.chip.dataset.dragged = "1";  // the click that follows a drag opens nothing
      if (done.at && done.at !== done.chip.dataset.start) { openBreak(done.chip, done.at); }
    }
  }
  Array.prototype.forEach.call(root.querySelectorAll("button.chip[data-idx]"), function (chip) {
    chip.addEventListener("click", function () {
      if (chip.dataset.dragged) { delete chip.dataset.dragged; return; }
      openBreak(chip);
    });
    chip.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) { return; }
      carry = { chip: chip, x0: e.clientX, y0: e.clientY, ghost: null, row: null, at: null, lifted: false };
      chip.setPointerCapture(e.pointerId);
    });
    chip.addEventListener("pointermove", function (e) {
      if (!carry || carry.chip !== chip) { return; }
      if (!carry.lifted) {
        if (Math.abs(e.clientX - carry.x0) + Math.abs(e.clientY - carry.y0) < 6) { return; }
        carry.lifted = true;
        chip.classList.add("lifted");
        carry.ghost = document.createElement("div");
        carry.ghost.className = "chip-ghost";
        carry.ghost.setAttribute("aria-hidden", "true");
        var what = document.createElement("b");
        what.textContent = chip.dataset.name + ", " + chip.dataset.kind + " " + chip.dataset.start;
        carry.ghost.appendChild(what);
        carry.ghost.appendChild(document.createElement("span"));
        document.body.appendChild(carry.ghost);
      }
      carry.ghost.style.transform = "translate(" + (e.clientX + 12) + "px, " + (e.clientY + 12) + "px)";
      mark(rowAt(e.clientX, e.clientY));
      edgeScroll(e.clientX, e.clientY);
    });
    chip.addEventListener("pointerup", drop);
    chip.addEventListener("pointercancel", function () { if (carry) { carry.lifted = false; } drop(); });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && carry && carry.lifted) { carry.lifted = false; carry.row && carry.row.classList.remove("rb-drop"); carry.row = null; drop(); }
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
    var now = document.querySelector(".now");
    if (now && (now.querySelector(".ring") || /[1-9]\d* waiting/.test((now.querySelector(".now-queue .big") || {}).textContent || ""))) {
      homeRefresh(now);
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
    keyedPick(pick, function () {
      var target = pick.getAttribute("data-target") || "/overview?program={key}";
      window.location = target.replace("{key}", encodeURIComponent(pick.value));
    }, showSays);
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
  var whole = ["Unplanned leave", "Sick", "Public holiday", "Exam leave"], aux = ["Coaching", "Meeting", "Training", "System issue", "Task", "Bio break"];  // Phase AV: Bio break needs no who or why
  var usual = { "Break": "15", "Lunch": "30", "Overtime": "60", "Coaching": "30", "Meeting": "30",
                "Training": "60", "System issue": "15", "Task": "30", "Bio break": "10" };
  var seq = 0;
  // Day off cancelled (Phase S): the people off today, a Shift Library shift or typed start and end
  var working = form.querySelector("[data-who-working]"), off = form.querySelector("[data-who-off]");
  var dayoff = form.querySelector("[data-dayoff-fields]"), to = form.querySelector("[data-to-label]");
  var shiftPick = form.querySelector("select[data-shift-pick]");
  var fromInput = form.querySelector("input[name=from]"), toInput = form.querySelector("input[name=to]");
  // Phase AA: overtime before or after the shift, the times worked out from the person's shift and the length
  var otSide = form.querySelector("[data-ot-side]"), otShift = form.querySelector("[data-ot-shift]");
  var who = form.querySelector("select[name=associate]:not([data-off])");
  var title = document.getElementById("add-h"), tick = form.querySelector(".post-tick");
  var posts = (form.dataset.postKinds || "").split(" ");
  var dayRoot = document.querySelector("[data-day]");
  var shown = dayRoot ? parseInt(dayRoot.dataset.shift, 10) || 0 : 0;  // Phase AI: the zone the page shows
  function clock(m) { m = (((m + shown) % 1440) + 1440) % 1440; return ("0" + Math.floor(m / 60)).slice(-2) + ":" + ("0" + m % 60).slice(-2); }
  function overtimeSides(on) {
    if (!otSide) { return; }
    otSide.hidden = !on;
    var radios = otSide.querySelectorAll("input[name=side]");
    Array.prototype.forEach.call(radios, function (r) { r.disabled = !on; });
    var o = who && who.options[who.selectedIndex];
    if (!on || !o || !o.dataset.start) { return; }
    var start = parseInt(o.dataset.start, 10), end = parseInt(o.dataset.end, 10), m = parseInt(minutes.value, 10) || 0;
    otShift.textContent = o.value + "'s shift today: " + clock(start) + " to " + clock(end) + ".";
    var before = otSide.querySelector("input[value=before]"), after = otSide.querySelector("input[value=after]");
    var early = start - m < 0;  // it would start the day before: pick a shorter length or after the shift
    otSide.querySelector("[data-ot-time=before]").textContent = early ? "Would start the day before" : clock(start - m) + " to " + clock(start);
    otSide.querySelector("[data-ot-time=after]").textContent = clock(end) + " to " + clock(end + m);
    before.disabled = early;
    if (early && before.checked) { after.checked = true; }
  }
  function kind() { var c = form.querySelector("input[name=what]:checked"); return c ? c.value : ""; }
  function pickedShift() {
    var o = shiftPick && shiftPick.options[shiftPick.selectedIndex];
    return o && o.value ? o : null;
  }
  function shape(changedKind) {
    var k = kind(), calling = k === "Day off cancelled", isAux = aux.indexOf(k) >= 0;
    var auxFields = form.querySelector("[data-aux-fields]");
    var asks = isAux && k !== "Bio break";  // a bio break is never billable and says no who or why
    if (auxFields) {
      auxFields.hidden = !asks;
      Array.prototype.forEach.call(auxFields.querySelectorAll("input, select"), function (i) { i.disabled = !asks; i.required = asks; });
    }
    length.hidden = whole.indexOf(k) >= 0 || k === "Late" || k === "Left early" || calling;
    billable.hidden = !asks;
    from.hidden = whole.indexOf(k) >= 0 || k === "Overtime";
    from.querySelector("span").textContent = k === "Late" ? "Arrived at" : k === "Left early" ? "Left at" : "From";
    if (changedKind && usual[k]) { minutes.value = usual[k]; }
    overtimeSides(k === "Overtime");
    // Phase AY: the counts of breaks belong to overtime and a call-in only; the allowance or incident choice to a late login or early leave only
    var extra = form.querySelector("[data-extra-breaks]"), lateBox = form.querySelector("[data-add-late]");
    var lateKind = k === "Late" || k === "Left early";
    if (extra) {
      extra.hidden = !(k === "Overtime" || calling);
      Array.prototype.forEach.call(extra.querySelectorAll("input"), function (i) { i.disabled = extra.hidden; });
    }
    if (lateBox) {
      lateBox.hidden = !lateKind;
      Array.prototype.forEach.call(lateBox.querySelectorAll("input"), function (i) { i.disabled = !lateKind; });
      var incident = lateBox.querySelector("[data-incident]");  // an early leave is always from the allowance
      if (incident) {
        incident.hidden = k !== "Late";
        incident.querySelector("input").disabled = k !== "Late";
        if (k !== "Late") { lateBox.querySelector("input[value=allowance]").checked = true; }
      }
    }
    if (off) {
      off.hidden = !calling; off.querySelector("select").disabled = !calling;
      working.hidden = calling; working.querySelector("select").disabled = calling;
      dayoff.hidden = !calling; to.hidden = !calling;
      var o = pickedShift();
      if (changedKind && calling && o) { fromInput.value = o.dataset.from; toInput.value = o.dataset.to; }
    }
    submit.textContent = calling ? "Call in" : "Add " + k.toLowerCase();
    // Phase AC: the title follows Overtime (it falls before or after the shift, not in this interval), and the
    // "Post to the group" tick shows only for a change this LOB posts
    if (title) {
      var person = who && who.options[who.selectedIndex];
      title.textContent = k === "Overtime" && person ? "Add overtime for " + person.value : title.dataset.addTitle;
    }
    if (tick) {
      var picked = form.querySelector("input[name=what]:checked");
      tick.hidden = !picked || posts.indexOf(picked.closest("label").dataset.kind) < 0;
    }
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
  shape(!form.hasAttribute("data-keep-minutes"));  // Phase AD: a length the server picked to cover the hour stays
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

// Phase AF (C1): a click on a stretch fills in "Set the block" with that stretch's person, times and channel
(function () {
  const form = document.querySelector("[data-cp-edit]");
  if (!form) return;
  document.addEventListener("click", (event) => {
    const run = event.target.closest("[data-cp-run]");
    if (!run) return;
    event.preventDefault();
    form.elements.who.value = run.dataset.who;
    form.elements.start.value = run.dataset.from;
    form.elements.end.value = run.dataset.to;
    if ("PCE".includes(run.dataset.letter) && run.dataset.letter) form.elements.channel.value = run.dataset.letter;
    form.scrollIntoView({ block: "nearest" });
    form.elements.channel.focus();
  });
})();

// Phase AF (C3): a stretch on the RTA's Channels tab fills in "Change a channel"; Preview asks the server what the
// change would cause (new warnings and their fixes) before Apply keeps it
(function () {
  const form = document.querySelector("[data-ch-form]");
  const said = document.querySelector("[data-ch-said]");
  const button = form && form.querySelector("[data-ch-preview]");
  if (!form || !said || !button || !window.fetch) return;
  button.hidden = false;
  document.addEventListener("click", (event) => {
    const run = event.target.closest("[data-ch-run]");
    if (!run) return;
    event.preventDefault();
    form.elements.associate.value = run.dataset.who;
    form.elements.from.value = run.dataset.from;
    form.elements.to.value = run.dataset.to;
    said.textContent = "";
    form.scrollIntoView({ block: "nearest" });
    form.elements.channel.focus();
  });
  const line = (tag, text, cls) => { const el = document.createElement(tag); el.textContent = text; if (cls) el.className = cls; return el; };
  button.addEventListener("click", () => {
    if (!form.reportValidity()) return;
    said.textContent = "Checking…";
    fetch("/day/channel-preview", { method: "POST", body: new FormData(form), credentials: "same-origin" })
      .then((r) => r.json())
      .then((j) => {
        said.textContent = "";
        if (j.error) { said.appendChild(line("p", j.error, "alert bad")); return; }
        const box = line("div", "", "alert " + (j.level === "ok" ? "ok" : "bad"));
        box.appendChild(line("h3", j.text));
        if (!j.warnings.length) box.appendChild(line("p", "No new channel warning."));
        j.warnings.forEach((w) => box.appendChild(line("p", w)));
        j.fixes.forEach((f) => box.appendChild(line("p", "Proposed fix: " + f)));
        said.appendChild(box);
      })
      .catch(() => { said.textContent = "The preview could not be loaded. Apply still checks the change."; });
  });
})();

// Phase AF (D2, D3): hovering (or focusing) a shift bar or a break on the timeline shows its lines in a card
// (from the element's title, which stays the plain tooltip without a script)
(function () {
  const marks = document.querySelectorAll(".tl-track rect.tl-bar, .tl-track rect.brk, .tl-track rect.tl-ch");
  if (!marks.length) return;
  const card = document.createElement("div");
  card.className = "tl-tip";
  card.hidden = true;
  card.setAttribute("role", "tooltip");
  document.body.appendChild(card);
  const show = (el, x, y, more) => {
    const lines = ((more ? more + "\n" : "") + (el.dataset.tip || "")).split("\n").filter(Boolean);
    if (!lines.length) return;
    card.textContent = "";
    lines.forEach((text, i) => { const p = document.createElement(i ? "span" : "b"); p.textContent = text; card.appendChild(p); });
    card.hidden = false;
    const w = card.offsetWidth, h = card.offsetHeight;
    card.style.left = Math.min(x + 14, window.innerWidth - w - 8) + "px";
    card.style.top = Math.min(y + 14, window.innerHeight - h - 8) + "px";
  };
  const hide = () => { card.hidden = true; };
  marks.forEach((el) => {
    const title = el.querySelector("title");
    if (!title) return;
    el.dataset.tip = title.textContent;
    title.remove();
    el.addEventListener("focus", () => { const r = el.getBoundingClientRect(); show(el, r.left, r.bottom); });
    el.addEventListener("blur", hide);
  });
  // Phase AI (owner: "when i stand any wheree"): anywhere on a person's row shows their shift card; a break shows its own,
  // and a channel the card of the shift it is on (a row can hold two shifts)
  document.querySelectorAll(".tl-lane[data-tip]").forEach((lane) => {
    const bars = lane.querySelectorAll(".tl-track rect.tl-bar[data-tip]");
    const under = (x) => Array.prototype.find.call(bars, (bar) => {
      const r = bar.getBoundingClientRect();
      return x >= r.left && x <= r.right;
    });
    const at = (e) => {
      const mark = e.target.closest(".tl-track rect.brk[data-tip], .tl-track rect.tl-bar[data-tip]");
      const channel = e.target.closest(".tl-track rect.tl-ch[data-tip]");
      show(mark || (channel && under(e.clientX)) || lane, e.clientX, e.clientY, channel ? channel.dataset.tip : "");
    };
    lane.addEventListener("pointerenter", at);
    lane.addEventListener("pointermove", at);
    lane.addEventListener("pointerleave", hide);
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hide(); });
  window.addEventListener("scroll", hide, { passive: true });
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

// Phase Z: the "now" line on today's achievement, at the time of day the page was made (Egypt time, from the server)
(function () {
  // Phase AD: every strip with a now line (Today's achievement, and both of Rescue the day's)
  Array.prototype.forEach.call(document.querySelectorAll(".achv-strip[data-now]"), function (strip) {
    var mark = strip.querySelector(".achv-now");
    var minutes = parseInt(strip.getAttribute("data-now"), 10);
    if (!mark || isNaN(minutes)) return;
    var span = parseInt(strip.getAttribute("data-span"), 10) || 1440;  // Phase AU: an operating day can be shorter than 24 hours
    mark.style.left = (Math.min(Math.max(minutes, 0), span) / span * 100) + "%";
    mark.classList.add("placed");
  });
})();

// Phase AD: Send again for a bulk change already posted asks first (the page asks too when the script is off).
(function () {
  "use strict";
  var form = document.querySelector("form[data-resend]"), dlg = document.getElementById("resend-dialog");
  if (!form || !dlg || typeof dlg.showModal !== "function") { return; }
  form.addEventListener("submit", function (e) {
    if (form.querySelector("input[name=again]").value === "1") { return; }
    e.preventDefault();
    dlg.querySelector("[data-resend-said]").textContent = form.dataset.said || "";
    dlg.showModal();
    dlg.querySelector("[data-resend-no]").focus();
  });
  dlg.querySelector("[data-resend-yes]").addEventListener("click", function () {
    form.querySelector("input[name=again]").value = "1";
    dlg.close();
    form.submit();
  });
  dlg.querySelector("[data-resend-no]").addEventListener("click", function () { dlg.close(); });
})();

// Phase AD: Change several breaks: Pick all ticks (or clears) everyone in that shift.
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("[data-pick-all]"), function (b) {
    b.addEventListener("click", function () {
      var boxes = b.closest("[data-pick-group]").querySelectorAll("input[name=who]");
      var all = Array.prototype.every.call(boxes, function (x) { return x.checked; });
      Array.prototype.forEach.call(boxes, function (x) { x.checked = !all; });
    });
  });
})();

// Go to (Phase AG): Ctrl K, or the button in the top bar, searches pages, programs and the day's people
(function () {
  "use strict";
  var dialog = document.getElementById("goto");
  if (!dialog || typeof dialog.showModal !== "function") { return; }
  var input = dialog.querySelector("input[name=q]"), list = dialog.querySelector("#goto-list");
  var timer = null, seq = 0, picked = -1;
  function options() { return list.querySelectorAll("li[role=option]"); }
  function mark() {
    var o = options();
    Array.prototype.forEach.call(o, function (li, i) { li.setAttribute("aria-selected", i === picked ? "true" : "false"); });
    if (picked >= 0 && o[picked]) { input.setAttribute("aria-activedescendant", o[picked].id); o[picked].scrollIntoView({ block: "nearest" }); }
    else { input.removeAttribute("aria-activedescendant"); }
  }
  function render(items) {
    list.textContent = "";
    picked = items.length ? 0 : -1;
    var group = "";
    items.forEach(function (it, i) {
      if (it.group !== group) {
        group = it.group;
        var head = document.createElement("li");
        head.className = "goto-group"; head.setAttribute("role", "presentation"); head.textContent = group;
        list.appendChild(head);
      }
      var li = document.createElement("li"), a = document.createElement("a");
      li.setAttribute("role", "option"); li.id = "goto-" + i;
      a.href = it.url; a.textContent = it.label; a.tabIndex = -1;
      if (it.note) { var note = document.createElement("small"); note.textContent = it.note; a.appendChild(note); }
      li.appendChild(a); list.appendChild(li);
    });
    if (!items.length && input.value.trim()) {
      var none = document.createElement("li");
      none.className = "goto-none"; none.setAttribute("role", "presentation");
      none.textContent = "Nothing matches. Try a shorter word.";
      list.appendChild(none);
    }
    mark();
  }
  function load(q) {
    var mine = ++seq;
    var url = dialog.dataset.url + "?q=" + encodeURIComponent(q) + "&program=" + encodeURIComponent(dialog.dataset.program || "") +
      "&date=" + encodeURIComponent(dialog.dataset.date || "");
    fetch(url, { credentials: "same-origin" }).then(function (r) { return r.ok ? r.json() : { items: [] }; })
      .then(function (d) { if (mine === seq) { render(d.items || []); } }).catch(function () {});
  }
  function open() { input.value = ""; dialog.showModal(); input.focus(); load(""); }
  input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { load(input.value); }, 180); });
  input.addEventListener("keydown", function (e) {
    var o = options();
    if (e.key === "ArrowDown" && o.length) { picked = (picked + 1) % o.length; mark(); e.preventDefault(); }
    else if (e.key === "ArrowUp" && o.length) { picked = (picked - 1 + o.length) % o.length; mark(); e.preventDefault(); }
    else if (e.key === "Enter") { e.preventDefault(); if (picked >= 0 && o[picked]) { window.location.href = o[picked].querySelector("a").href; } }
  });
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K") && !dialog.open) { e.preventDefault(); open(); }
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-goto-open]"), function (b) { b.addEventListener("click", open); });
})();

// Phase AK (sample ak01 D): the Timeline's tracks stretch sideways (1440 minutes across the page), so the channel
// letters on them are drawn back to their true shape: each is narrowed or widened around its own middle by the
// track's height scale over its width scale.
(function () {
  "use strict";
  var tracks = document.querySelectorAll("svg.tl-track");
  if (!tracks.length) { return; }
  function fit() {
    Array.prototype.forEach.call(tracks, function (svg) {
      var box = svg.viewBox.baseVal, w = svg.clientWidth, h = svg.clientHeight;
      if (!box || !w || !h) { return; }
      var k = (h / box.height) / (w / box.width);
      Array.prototype.forEach.call(svg.querySelectorAll("text.tl-ch-t"), function (t) {
        var cx = t.getAttribute("data-cx");
        t.setAttribute("transform", "translate(" + cx + " 0) scale(" + k.toFixed(4) + " 1) translate(" + (-cx) + " 0)");
      });
    });
  }
  fit();
  window.addEventListener("resize", fit);
})();

// Phase AY (owner, 2026-10-23: "the timezone should match their own on the PC"): the browser's own zone is kept in a cookie, so the
// server counts "today" (the days back a role may still change) where the person is, not only in Egypt.
(function () {
  "use strict";
  var zone = "";
  try { zone = Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch (e) { return; }
  if (!zone || document.cookie.indexOf("pc_tz=" + zone) !== -1) { return; }
  document.cookie = "pc_tz=" + zone + "; path=/; max-age=31536000; SameSite=Lax" +
    (location.protocol === "https:" ? "; Secure" : "");
})();

// Phase AY (owner, 2026-10-23: "the hours timeline does not match the intervals below"): the Timeline's hour labels and hour lines
// were laid out for a 24-hour day, so on a shorter window ("Day starts at", the operating day) they drifted from the bars and the
// interval cells. They are placed here from the window's length in minutes (data-span on the axis row): a label every 2 hours, a
// line every hour.
(function () {
  "use strict";
  var axis = document.querySelector(".tl-axis[data-span]");
  if (!axis) { return; }
  var span = parseInt(axis.getAttribute("data-span"), 10);
  if (!span || span <= 0) { return; }
  var ticks = axis.querySelector(".tl-ticks");
  Array.prototype.forEach.call(ticks.children, function (t, i) { t.style.left = (100 * i * 120 / span).toFixed(3) + "%"; });
  ticks.classList.add("placed");
  Array.prototype.forEach.call(document.querySelectorAll("svg.tl-track"), function (svg) {
    svg.style.backgroundSize = (100 * 60 / span).toFixed(4) + "% 100%";
  });
})();

// Phase AO (owner, 2026-10-20): on People, "Name on the schedule" lists only the names on the schedules of the programs
// ticked in the same form, and the bulk team manager list only team managers who share a program with every ticked
// associate. Each name and team manager carries the program ids it belongs to (data-programs); the server still checks.
(function () {
  "use strict";
  var master = document.getElementById("roster-names");
  function ids(text) { return (text || "").split(" ").filter(Boolean); }
  function meets(have, want) { return have.some(function (id) { return want.indexOf(id) !== -1; }); }
  if (master) {
    var options = Array.prototype.slice.call(master.querySelectorAll("option"));
    Array.prototype.forEach.call(document.querySelectorAll("input[list='roster-names']"), function (field, n) {
      var form = field.form;
      if (!form) { return; }
      var own = document.createElement("datalist");
      own.id = "roster-names-" + n;
      master.parentNode.insertBefore(own, master.nextSibling);
      field.setAttribute("list", own.id);
      function fill() {
        var boxes = Array.prototype.slice.call(form.querySelectorAll("input[name='programs']"));
        var all = form.querySelector("input[name='all_programs']");
        var want = boxes.filter(function (b) { return b.checked || (all && all.checked); }).map(function (b) { return b.value; });
        own.textContent = "";
        options.forEach(function (o) {
          if (meets(ids(o.getAttribute("data-programs")), want)) { own.appendChild(o.cloneNode(true)); }
        });
      }
      form.addEventListener("change", fill);
      fill();
    });
  }
  var bulk = document.querySelector("form[action$='/admin/users/team']");
  if (bulk) {
    var select = bulk.querySelector("select[name='team_manager']");
    var narrow = function () {
      var asked = Array.prototype.slice.call(bulk.querySelectorAll("input[name='who']:checked"))
        .map(function (b) { return ids(b.getAttribute("data-programs")); });
      Array.prototype.forEach.call(select.options, function (o) {
        if (!o.value) { return; }
        var theirs = ids(o.getAttribute("data-programs"));
        var fits = theirs[0] === "all" || asked.every(function (have) { return meets(have, theirs); });
        o.hidden = o.disabled = !fits;
        if (!fits && o.selected) { select.value = ""; }
      });
    };
    bulk.addEventListener("change", narrow);
    narrow();
  }
  // Phase AU: a long list of people with a search box (data-filter names the list) and a count of those ticked
  Array.prototype.forEach.call(document.querySelectorAll("input[data-filter]"), function (box) {
    var list = document.getElementById(box.getAttribute("data-filter"));
    if (!list) { return; }
    var count = document.querySelector("[data-count-for='" + list.id + "']");
    var tally = function () {
      if (count) {
        var n = list.querySelectorAll("input[type='checkbox']:checked").length;
        count.textContent = n ? n + " picked" : "";
      }
    };
    box.addEventListener("input", function () {
      var text = box.value.trim().toLowerCase();
      Array.prototype.forEach.call(list.querySelectorAll(".exp-kind, [data-filter-row]"), function (row) {
        row.hidden = text !== "" && row.textContent.toLowerCase().indexOf(text) === -1;
      });
    });
    list.addEventListener("change", tally);
    tally();
  });
})();


// Downloads (Phase AX): on a page marked data-downloads, each chart is saved as a picture (PNG) or a drawing (SVG), each
// table as a CSV file that Excel opens. Built in the browser from what the page shows, so it is always what you see.
(function () {
  "use strict";
  var root = document.querySelector("[data-downloads]");
  if (!root) { return; }
  var page = root.getAttribute("data-downloads");
  var SVG_STYLE = ["fill", "stroke", "stroke-width", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity",
    "fill-opacity", "stroke-opacity", "font-family", "font-size", "font-weight", "text-anchor", "dominant-baseline"];

  var slug = function (text) {
    return (text || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").slice(0, 60);
  };
  var period = function () {
    var from = document.querySelector("input[name=from]"), to = document.querySelector("input[name=to]");
    return from && to && from.value && to.value ? from.value + "_to_" + to.value : "";
  };
  var nameFor = function (panel, ext) {
    var heading = panel.querySelector("h1, h2, h3");
    return [page, slug(heading ? heading.textContent : panel.getAttribute("aria-label")), period()]
      .filter(Boolean).join("_") + "." + ext;
  };
  var save = function (blob, name) {
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.setTimeout(function () { URL.revokeObjectURL(link.href); }, 4000);
  };

  var csvOf = function (table) {
    var cell = function (text) {
      text = text.replace(/\s+/g, " ").trim();
      return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
    };
    return Array.prototype.map.call(table.querySelectorAll("tr"), function (row) {
      return Array.prototype.map.call(row.children, function (c) { return cell(c.textContent); }).join(",");
    }).join("\r\n") + "\r\n";
  };

  var background = function (node) {
    for (; node; node = node.parentElement) {
      var colour = window.getComputedStyle(node).backgroundColor;
      if (colour && colour !== "transparent" && !/rgba\(.*,\s*0\)$/.test(colour)) { return colour; }
    }
    return "#ffffff";
  };
  // The chart's colours come from the page's stylesheet, which a saved file does not have: write them into the file.
  // (Attributes, not a style attribute: the page's content security policy allows no inline style.)
  var drawing = function (svg) {
    var copy = svg.cloneNode(true);
    var from = [svg].concat(Array.prototype.slice.call(svg.querySelectorAll("*")));
    var to = [copy].concat(Array.prototype.slice.call(copy.querySelectorAll("*")));
    from.forEach(function (node, i) {
      var seen = window.getComputedStyle(node);
      SVG_STYLE.forEach(function (prop) {
        var value = seen.getPropertyValue(prop);
        if (value) { to[i].setAttribute(prop, value); }
      });
      to[i].removeAttribute("class");
    });
    var box = svg.viewBox.baseVal;
    var width = box && box.width ? box.width : svg.getBoundingClientRect().width;
    var height = box && box.height ? box.height : svg.getBoundingClientRect().height;
    copy.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    copy.setAttribute("width", String(width));
    copy.setAttribute("height", String(height));
    var back = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    back.setAttribute("x", box ? String(box.x) : "0");
    back.setAttribute("y", box ? String(box.y) : "0");
    back.setAttribute("width", String(width));
    back.setAttribute("height", String(height));
    back.setAttribute("fill", background(svg));
    copy.insertBefore(back, copy.firstChild);
    return { text: new XMLSerializer().serializeToString(copy), width: width, height: height };
  };
  var picture = function (svg, name) {
    var made = drawing(svg);
    var scale = 2, image = new Image();
    image.onload = function () {
      var canvas = document.createElement("canvas");
      canvas.width = Math.round(made.width * scale);
      canvas.height = Math.round(made.height * scale);
      var ctx = canvas.getContext("2d");
      ctx.scale(scale, scale);
      ctx.drawImage(image, 0, 0, made.width, made.height);
      canvas.toBlob(function (blob) { if (blob) { save(blob, name); } }, "image/png");
    };
    image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(made.text);
  };

  var rows = new Map();
  var rowFor = function (panel) {
    if (!rows.has(panel)) {
      var row = document.createElement("p");
      row.className = "dl-row";
      panel.appendChild(row);
      rows.set(panel, row);
    }
    return rows.get(panel);
  };
  var button = function (panel, label, act) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "quiet";
    b.textContent = label;
    b.addEventListener("click", act);
    rowFor(panel).appendChild(b);
  };
  var tally = function (n, total) { return total > 1 ? " (" + n + ")" : ""; };
  var panels = Array.prototype.slice.call(root.querySelectorAll(".panel"));
  panels.forEach(function (panel) {
    var own = function (sel) {
      return Array.prototype.filter.call(panel.querySelectorAll(sel), function (n) {
        return n.closest(".panel") === panel;
      });
    };
    var charts = own("svg.chart"), tables = own("table");
    charts.forEach(function (svg, i) {
      button(panel, "Chart as PNG" + tally(i + 1, charts.length), function () { picture(svg, nameFor(panel, "png")); });
      button(panel, "Chart as SVG" + tally(i + 1, charts.length), function () {
        save(new Blob([drawing(svg).text], { type: "image/svg+xml" }), nameFor(panel, "svg"));
      });
    });
    tables.forEach(function (table, i) {
      button(panel, "Table as CSV" + tally(i + 1, tables.length), function () {
        save(new Blob(["﻿" + csvOf(table)], { type: "text/csv;charset=utf-8" }), nameFor(panel, "csv"));
      });
    });
  });
})();

// Phase AY (owner, 2026-10-23): an open page asks every 30 s whether what it shows has changed (the stamp the page was built
// from, against the server's now). A read-only page (data-mode "reload": My day, My week, Overview) reloads; a page where
// people are in the middle of something (data-mode "bar": the RTA day, Requests) shows a bar with a link instead, and so does
// a read-only page while a field has the focus or has been typed in. The asks are spread by up to 5 s so that many open pages
// do not ask in the same second, they stop while the tab is hidden (one ask when it comes back), and after a failed ask the
// wait doubles up to 5 minutes.
function liveWatch(box) {
  "use strict";
  var url = box.getAttribute("data-url"), stamp = box.getAttribute("data-stamp"), mode = box.getAttribute("data-mode");
  var BASE = 30000, MOST = 300000, delay = BASE, timer = null, busy = false, touched = false, shown = false;
  function typing() {
    var a = document.activeElement;
    return touched || !!(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
  }
  function bar() {
    if (shown) { return; }
    shown = true;
    var note = document.createElement("p"), link = document.createElement("a"), main = document.getElementById("main") || document.body;
    note.className = "notice live-bar";
    note.setAttribute("role", "status");
    note.appendChild(document.createTextNode("The page changed. "));
    link.href = window.location.href;
    link.textContent = "Refresh to see it";
    note.appendChild(link);
    main.insertBefore(note, main.firstChild);
  }
  function changed() {
    if (mode === "reload" && !typing()) { window.location.reload(); } else { bar(); }
  }
  function schedule() {
    window.clearTimeout(timer);
    if (shown || document.hidden) { return; }
    timer = window.setTimeout(ask, delay + Math.random() * 5000);
  }
  function ask() {
    if (busy || document.hidden) { return; }
    busy = true;
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" }, cache: "no-store" })
      .then(function (r) { if (!r.ok || r.redirected) { throw new Error("HTTP " + r.status); } return r.json(); })
      .then(function (s) {
        delay = BASE;
        if (s.stamp !== stamp) { changed(); }
      })
      .catch(function () { delay = Math.min(delay * 2, MOST); })
      .then(function () { busy = false; schedule(); });
  }
  document.addEventListener("input", function () { touched = true; });
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { window.clearTimeout(timer); } else { ask(); }
  });
  schedule();
}
(function () {
  "use strict";
  var live = document.getElementById("live");
  if (live) { liveWatch(live); }
})();
