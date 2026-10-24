# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: sign in/out."""
from __future__ import annotations

import time

from flask import flash, g, redirect, render_template, request, session, url_for

from ..app import password_problem
from ..auth import csrf_token, login_required, safe_next, session_stamp
from ..store import clean_password


def register(app, ctx) -> None:
    """Add the sign in/out routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- sign in/out
    @app.route("/login", methods=["GET", "POST"])
    def login():  # type: ignore[no-untyped-def]
        error = ""
        if request.method == "POST":
            throttle, address = app.extensions["throttle"], request.remote_addr or ""
            typed = (request.form.get("username", "") or "").strip().lower()
            account = app.extensions["store"].get_user_by_name(typed) if typed else None
            # the typed name is kept only when it is an account: a wrong box may hold a password
            who = {"subject": account["username"] if account else "(no such username)",
                   "user_id": account["id"] if account else None}
            if throttle.held(address):  # Phase AT: too many wrong sign-ins from this address; not even a right password
                app.extensions["store"].add_event(kind="sign_in_held", detail=f"from {address}", **who)
                return render_template("login.html", error="Too many sign-in attempts from this device. Wait 15 "
                                                           "minutes and try again."), 429
            user, reason = app.extensions["store"].authenticate(request.form.get("username", ""),
                                                                request.form.get("password", ""))
            if user is None and reason not in ("disabled", "expired"):
                throttle.failed(address)
            if user is None:
                app.extensions["store"].add_event(kind="sign_in_failed", detail=f"from {address}: {reason}", **who)
            else:
                app.extensions["store"].add_event(kind="signed_in", detail=f"from {address}", **who)
            if user is not None:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                session["pw"] = session_stamp(user)
                session["at"] = time.time()  # Phase AU: when this session began (see end_other_sessions)
                csrf_token()
                return redirect(safe_next(request.args.get("next", "")) or url_for("home"))
            error = {"locked": "Too many wrong passwords: this account is locked for 15 minutes.",
                     "disabled": "This account is switched off. Ask your admin.",
                     "expired": "Your temporary password has expired. Ask your admin for a new one."}.get(
                         reason, "Wrong username or password.")
        return render_template("login.html", error=error)

    @app.route("/account/sessions/end", methods=["POST"])
    @login_required
    def end_other_sessions():  # type: ignore[no-untyped-def]
        """Phase AU: every other device is signed out (a lost phone); this one stays."""
        now = time.time()
        app.extensions["store"].end_other_sessions(g.user["id"], now)
        session["at"] = now + 0.001  # after the mark, so this device is the one that stays
        ctx._record("sessions_ended", subject=g.user["username"])
        flash("Every other device is signed out.")
        return redirect(url_for("change_password"))

    @app.route("/logout", methods=["POST"])
    def logout():  # type: ignore[no-untyped-def]
        if session.get("user_id") is not None:  # Phase AV: end this session on the server, not only in the browser
            app.extensions["store"].revoke_session(session["user_id"], session.get("at", 0))
        session.clear()
        return redirect(url_for("login"))

    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def change_password():  # type: ignore[no-untyped-def]
        error = ""
        if request.method == "POST":
            store = app.extensions["store"]
            if store.check_password(g.user["username"], request.form.get("current", "")) is None:
                error = "Your current password is not right."
            else:
                error = password_problem(request.form.get("new", ""), request.form.get("confirm", ""),
                                         g.user["username"])
            if not error and clean_password(request.form.get("new", "")) == clean_password(request.form.get("current", "")):
                error = "Choose a password different from your current one."  # a temporary one cannot be kept (Phase AU)
            if not error:
                store.set_password(g.user["id"], request.form["new"], must_change=False)
                session["pw"] = session_stamp(store.get_user(g.user["id"]))  # this device stays; others sign in again
                flash("Password changed.")
                return redirect(url_for("home"))
        return render_template("password.html", error=error, forced=bool(g.user["must_change"]))

