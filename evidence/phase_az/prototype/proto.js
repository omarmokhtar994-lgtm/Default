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
    document.getElementById("view-day").hidden = view !== "day";
    document.getElementById("view-signin").hidden = view !== "signin";
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

  /* ---- controls ---- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-look-pick]"), function (b) { b.addEventListener("click", function () { setLook(b.getAttribute("data-look-pick")); }); });
  Array.prototype.forEach.call(document.querySelectorAll("[data-view-pick]"), function (b) { b.addEventListener("click", function () { setView(b.getAttribute("data-view-pick")); }); });
  document.querySelector("[data-try]").addEventListener("click", function () { setView("day"); window.setTimeout(stale, 350); });

  var saved = store("look"), dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  var start = /^[abc]$/.test(saved || "") ? saved : (dark ? "b" : "a");
  body.setAttribute("data-look", start); pressed("data-look-pick", start);
  var q = /[?&]look=([abc])/.exec(window.location.search);
  if (q) { body.setAttribute("data-look", q[1]); pressed("data-look-pick", q[1]); }
  var v = /[?&]view=(day|signin)/.exec(window.location.search);
  if (v) { setView(v[1]); }
}());
