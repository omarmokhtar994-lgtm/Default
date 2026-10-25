// © 2026 Omar Mokhtar. All rights reserved.
(function () {
  "use strict";
  var body = document.body, note = document.getElementById("note"), msg = document.getElementById("note-msg"),
      act = document.getElementById("note-act"), noteTimer = 0, noteAction = null;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");

  function store(key, value) { try { if (value === undefined) { return window.localStorage.getItem(key); } window.localStorage.setItem(key, value); } catch (e) { return null; } return null; }

  /* ---- look and page ---- */
  function pressed(attr, value) {
    Array.prototype.forEach.call(document.querySelectorAll("[" + attr + "]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute(attr) === value ? "true" : "false"); });
  }
  function setLook(look) {
    var change = function () { body.setAttribute("data-look", look); pressed("data-look-pick", look); };
    if (document.startViewTransition && !reduce.matches) { document.startViewTransition(change); } else { change(); }
    store("look", look);
  }
  function setView(view) {
    Array.prototype.forEach.call(document.querySelectorAll(".view"), function (v) { v.hidden = v.id !== "view-" + view; });
    window.scrollTo(0, 0);
    body.setAttribute("data-view", view);
    pressed("data-view-pick", view);
    var s = document.getElementById("signin-main");
    s.classList.remove("in");
    if (view === "signin") { void s.offsetWidth; s.classList.add("in"); }
  }

  /* ---- the floating note ---- */
  function showNote(text, kind, label, action, ms) {
    window.clearTimeout(noteTimer);
    msg.innerHTML = text;
    note.setAttribute("data-kind", kind);
    act.hidden = !label;
    act.textContent = label || "";
    noteAction = action || null;
    note.classList.add("on");
    if (ms) { noteTimer = window.setTimeout(hideNote, ms); }
  }
  function hideNote() { window.clearTimeout(noteTimer); note.classList.remove("on"); }
  act.addEventListener("click", function () { var f = noteAction; hideNote(); if (f) { f(); } });
  document.getElementById("note-x").addEventListener("click", hideNote);
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { hideNote(); } });

  /* ---- a change by someone else, then Refresh ---- */
  function stale() {
    showNote("<b>This page is out of date.</b> Associate 04\u2019s break moved at 14:35.", "stale", "Refresh", function () {
      var lane = document.querySelector('.lane[data-who="Associate 04"]');
      if (lane) { lane.classList.remove("flash"); void lane.offsetWidth; lane.classList.add("flash"); }
    });
  }

  /* ---- answer a request: the row closes, and the note offers Undo ---- */
  var asks = document.getElementById("asks"), count = document.getElementById("askcount"), empty = document.getElementById("empty");
  function left() { return asks.querySelectorAll(".ask:not(.gone)").length; }
  function refreshCount() {
    var n = left();
    count.textContent = n + (n === 1 ? " request" : " requests");
    empty.hidden = n !== 0;
  }
  asks.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-act]");
    if (!b) { return; }
    var row = b.closest(".ask"), verb = b.getAttribute("data-act") === "approve" ? "Approved" : "Declined", who = row.getAttribute("data-who");
    row.classList.add("gone");
    refreshCount();
    showNote("<b>" + verb + "</b> " + who + "\u2019s " + row.getAttribute("data-kind") + ".", "done", "Undo", function () { row.classList.remove("gone"); refreshCount(); }, 6000);
  });

  /* ---- sign in ---- */
  var form = document.getElementById("form"), pw = document.getElementById("p"), perr = document.getElementById("perr");
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!pw.value) { perr.hidden = false; pw.setAttribute("aria-invalid", "true"); pw.focus(); return; }
    perr.hidden = true; pw.removeAttribute("aria-invalid");
    setView("day");
    showNote("<b>Signed in.</b> Welcome back, Sara.", "done", "", null, 3000);
  });
  pw.addEventListener("input", function () { if (pw.value) { perr.hidden = true; pw.removeAttribute("aria-invalid"); } });


  /* ---- long lists: pages with a filter, and the lane list scrolls inside its own box ---- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-pager]"), function (box) {
    var rows = Array.prototype.slice.call(box.querySelectorAll(".prow")), size = parseInt(box.getAttribute("data-size"), 10) || 10, page = 0, day = "", text = "";
    var label = box.querySelector("[data-pager-label]"), pg = box.querySelector("[data-pager-page]"), prev = box.querySelector("[data-pager-prev]"),
        next = box.querySelector("[data-pager-next]"), none = box.querySelector("[data-pager-empty]"), wrap = box.querySelector(".scroll");
    function draw() {
      var hit = rows.filter(function (r) { return (!day || r.getAttribute("data-day") === day) && (!text || (r.getAttribute("data-text") || r.textContent).toLowerCase().indexOf(text) !== -1); });
      var pages = Math.max(1, Math.ceil(hit.length / size)); page = Math.min(page, pages - 1);
      rows.forEach(function (r) { r.hidden = true; });
      hit.slice(page * size, page * size + size).forEach(function (r) { r.hidden = false; });
      var from = hit.length ? page * size + 1 : 0, to = Math.min(hit.length, page * size + size);
      label.textContent = hit.length ? from + " to " + to + " of " + hit.length : "0 results";
      pg.textContent = "Page " + (page + 1) + " of " + pages; prev.disabled = page === 0; next.disabled = page >= pages - 1; none.hidden = hit.length !== 0;
      if (wrap) { wrap.scrollTop = 0; }
    }
    prev.addEventListener("click", function () { page -= 1; draw(); }); next.addEventListener("click", function () { page += 1; draw(); });
    Array.prototype.forEach.call(box.querySelectorAll("[data-day-pick]"), function (b) {
      b.addEventListener("click", function () {
        day = b.getAttribute("data-day-pick") === "All days" ? "" : b.getAttribute("data-day-pick"); page = 0;
        Array.prototype.forEach.call(box.querySelectorAll("[data-day-pick]"), function (o) { o.setAttribute("aria-pressed", o === b ? "true" : "false"); });
        draw();
      });
    });
    var find = box.querySelector("[data-pager-search]");
    if (find) { find.addEventListener("input", function () { text = find.value.trim().toLowerCase(); page = 0; draw(); }); }
    draw();
  });
  var laneFind = document.getElementById("lane-find"), laneBox = document.getElementById("lane-scroll"), laneCount = document.getElementById("lane-count");
  function laneFilter() {
    var t = laneFind.value.trim().toLowerCase(), n = 0;
    Array.prototype.forEach.call(laneBox.querySelectorAll(".lane"), function (l) { var ok = !t || l.getAttribute("data-who").toLowerCase().indexOf(t) !== -1; l.hidden = !ok; if (ok) { n += 1; } });
    laneCount.textContent = n === 1 ? "1 person" : n + " people";
  }
  laneFind.addEventListener("input", laneFilter);
  document.getElementById("jump-now").addEventListener("click", function () { laneBox.scrollTop = 0; laneBox.focus(); });


  /* ---- RTA list: the viewer chooses a scrolling panel or the whole list (kept in this browser only) ---- */
  function laneMode(mode) {
    laneBox.setAttribute("data-mode", mode);
    if (mode === "whole") { laneBox.removeAttribute("tabindex"); laneBox.removeAttribute("role"); laneBox.removeAttribute("aria-label"); }
    else { laneBox.setAttribute("tabindex", "0"); laneBox.setAttribute("role", "region"); laneBox.setAttribute("aria-label", "Who is on what, scrolls"); }
    Array.prototype.forEach.call(document.querySelectorAll("[data-lane-mode]"), function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-lane-mode") === mode ? "true" : "false"); });
    store("lanes", mode);
  }
  Array.prototype.forEach.call(document.querySelectorAll("[data-lane-mode]"), function (b) { b.addEventListener("click", function () { laneMode(b.getAttribute("data-lane-mode")); }); });
  laneMode(store("lanes") === "whole" ? "whole" : "scroll");

  /* ---- controls ---- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-look-pick]"), function (b) { b.addEventListener("click", function () { setLook(b.getAttribute("data-look-pick")); }); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-view-pick]"), function (b) { b.addEventListener("click", function () { setView(b.getAttribute("data-view-pick")); }); });
  document.querySelector("[data-try]").addEventListener("click", function () { setView("day"); window.setTimeout(stale, 350); });

  var saved = store("look"), dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  var start = /^[abc]$/.test(saved || "") ? saved : (dark ? "b" : "a");
  body.setAttribute("data-look", start); pressed("data-look-pick", start);
  var q = /[?&]look=([abc])/.exec(window.location.search);
  if (q) { body.setAttribute("data-look", q[1]); pressed("data-look-pick", q[1]); }
  var v = /[?&]view=(day|home|week|people|requests|schedules|wallboard|signin)/.exec(window.location.search);
  if (v) { setView(v[1]); }
}());
