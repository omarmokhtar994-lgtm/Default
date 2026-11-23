// © 2026 Omar Mokhtar. All rights reserved.
// Phase BQ: the page-to-page crossfade (@view-transition in app.css). Chromium 157 skips some of them and rejects the
// transition's promises with InvalidStateError ("Transition was aborted because of invalid state"); nothing handled
// that, so about one click in six left an uncaught error on the page. Only that skip is handled here: the page has
// loaded, only the fade was skipped. Any other error is thrown on as before. Loaded in the head, without defer, so
// it listens before the new page is revealed.
(function () {
  "use strict";
  function watch(e) {
    var vt = e.viewTransition;
    if (!vt) { return; }
    var skipped = function (err) { if (!err || err.name !== "InvalidStateError") { throw err; } };
    vt.ready.catch(skipped);
    vt.finished.catch(skipped);
    if (vt.updateCallbackDone) { vt.updateCallbackDone.catch(skipped); }
  }
  window.addEventListener("pagereveal", watch);
  window.addEventListener("pageswap", watch);
})();
