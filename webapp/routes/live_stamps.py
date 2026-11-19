# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: open pages ask whether they changed."""
from __future__ import annotations

from datetime import timedelta
from typing import Dict

from flask import abort, g, jsonify, request, url_for
from werkzeug.exceptions import NotFound

from ..app import clean_program
from ..auth import login_required
from ..clock import EGYPT, SHOWN
from ..live import KINDS as LIVE_KINDS, Stamps, digest, lanes_of
from .. import app as A  # the clock and a few seams are read through the app module, so tests can replace them


def register(app, ctx) -> None:
    """Add the open pages ask whether they changed routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- open pages ask whether they changed (Phase AY)
    app.extensions["live"] = Stamps()

    def _live_stamp(kind: str, program: str = "", on_text: str = "") -> str:
        """The stamp of what a page of this kind shows to this person (``webapp/live.py``); "" when there is nothing to show."""
        stamps, user = app.extensions["live"], g.user
        if (kind == "me") != bool(user["is_associate"]):
            abort(404)  # an associate's account is stamped for its own pages only, and staff for theirs
        if kind == "me":
            key = ctx._my_unit()
            if not key:
                return ""

            def mine() -> str:
                today, name, days = ctx._local_now(key).date(), user["roster_name"], app.extensions["days"]
                seen = []
                for d in (today - timedelta(days=1), today, today + timedelta(days=1)):
                    try:
                        seen.append([d.isoformat(), lanes_of(days.page(key, d, shared=True), name)])
                    except ValueError:  # a day whose input workbook is not kept: the page leaves it out too
                        seen.append([d.isoformat(), []])
                leave, swaps = app.extensions.get("leave"), app.extensions.get("swaps")
                return digest([seen, leave.mine(key, name) if leave else [], swaps.mine(key, name) if swaps else [],
                               app.extensions["changes"].mine(key, user["id"])])
            return stamps.get(("me", user["id"]), mine)
        key = (clean_program(program) if program and ctx._access().can_open(clean_program(program)) else
               ctx._requests_unit()) if kind == "requests" else clean_program(program)
        if not key or not ctx._access().can_open(key):
            abort(404)
        if kind == "requests":
            def waiting() -> str:
                leave, swaps = app.extensions.get("leave"), app.extensions.get("swaps")
                return digest([leave.waiting(key) if leave else [], swaps.waiting(key) if swaps else [],
                               app.extensions["changes"].waiting(key)])
            return stamps.get(("requests", key), waiting)
        on = ctx._date(on_text) or A.datetime.now(EGYPT).date()

        def day() -> str:
            try:
                return digest(lanes_of(app.extensions["days"].page(key, on, shared=True)))
            except ValueError:
                return ""
        return stamps.get(("day", key, on.isoformat(), SHOWN.get()), day)

    @app.route("/live/stamp")
    @login_required
    def live_stamp():  # type: ignore[no-untyped-def]
        """Phase AY: a very small answer, asked every 30 seconds by a page that is open (static/app.js, liveWatch)."""
        kind = request.args.get("kind", "")
        if kind not in LIVE_KINDS:
            abort(404)
        stamps = app.extensions["live"]
        answer = _live_stamp(kind, request.args.get("program", ""), request.args.get("date", ""))
        if stamps.asked % 500 == 0:
            app.logger.info(stamps.line())
        response = jsonify(stamp=answer)
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.template_global()
    def live_state(kind: str, program: str = "", on: str = "") -> Dict[str, str]:
        """What a page hands the watcher: where to ask, and the stamp it was built from."""
        query = {"kind": kind, **({"program": program} if program else {}), **({"date": on} if on else {})}
        try:
            return {"url": url_for("live_stamp", **query), "stamp": _live_stamp(kind, program, on)}
        except NotFound:  # a program the person may not open (a merged view): the page just does not watch
            return {"url": "", "stamp": ""}

