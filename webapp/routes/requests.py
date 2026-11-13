# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: requests."""
from __future__ import annotations

from typing import Any, Dict, List

from flask import g, render_template, request, session

from ..app import clean_program
from ..attendance import hm
from ..auth import login_required
from ..clock import EGYPT
from ..permissions import allowed
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the requests routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- requests (Phase AG)
    def _requests_unit() -> str:
        key = clean_program(request.values.get("program", ""))
        if key and ctx._access().can_open(key):
            return key
        units = [k for p in ctx._access().programs() for k in p["units"]]
        remembered = session.get("unit", "")
        return remembered if remembered in units else (units[0] if units else "")

    def _change_rows(key: str) -> List[Dict[str, Any]]:
        """Phase AS: the waiting break changes and coaching, each with the intervals it touches (before, after, buffer)."""
        book, rows, now = app.extensions["changes"], [], ctx._local_now(key)
        book.expire_overdue(key, now)  # Phase AU: a request whose time has come is closed, and its asker told
        waiting = book.waiting(key)
        for r in waiting:
            r["overlaps"], r["stale"] = book.overlaps(r, waiting), book.stale_note(r, now)
            try:
                r["impact"], r["impact_note"] = book.impact(r), ""
                r["alternatives"] = book.alternatives(r, now)  # the nearest times, from what the RTA holds now
                if r["kind"] == "coaching":  # the other answer to "billable?", so the RTA sees what correcting it does
                    r["other_impact"] = book.impact(r, billable=not r["d"].get("billable"))
            except (ValueError, KeyError, StopIteration) as exc:  # a day that cannot be worked out is said, not hidden
                r["impact"], r["impact_note"], r["alternatives"] = [], f"The impact cannot be worked out: {exc}", []
            rows.append(r)
        return rows

    @app.route("/requests")
    @login_required
    def requests_page():  # type: ignore[no-untyped-def]
        """Leave waiting for a decision, each day with what it costs; what was decided lately; balances."""
        key = _requests_unit()
        leave = app.extensions.get("leave")
        waiting = leave.waiting(key) if leave and key else []
        for r in waiting:
            r["mine"] = leave.may_decide(r, g.user)
        swaps = app.extensions.get("swaps")
        swap_rows = swaps.waiting(key) if swaps and key else []
        for w in swap_rows:  # Phase AK: their team managers, or a backup
            w["mine"] = swaps.may_decide(w, g.user)
        return render_template("requests.html", unit=key, label=ctx._unit_filter(key) if key else "", waiting=waiting,
                               decided=ctx._paged(leave.decided(key, limit=None) if leave and key else [], "done_page",
                                              "done-h"),
                               swaps=swap_rows, changes=_change_rows(key) if key else [],
                               changes_decided=app.extensions["changes"].decided(key) if key else [],
                               may_change=allowed(app.extensions["store"], g.user, "rta_change"), hm=hm,
                               can_ask_coaching=ctx._can_ask_coaching(),
                               swaps_decided=ctx._paged(swaps.decided(key, limit=None) if swaps and key else [],
                                                    "swaps_done_page", "done-h"),
                               manager=allowed(app.extensions["store"], g.user, "setup"),
                               year=A.datetime.now(EGYPT).year)

    ctx._change_rows = _change_rows
    ctx._requests_unit = _requests_unit
