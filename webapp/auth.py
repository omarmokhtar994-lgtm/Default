# © 2026 Omar Mokhtar. All rights reserved.
"""Login, CSRF and access decorators."""
from __future__ import annotations

import functools
import hashlib
import hmac
import re
import secrets
from typing import Any, Callable, Dict, Optional

from flask import abort, current_app, g, redirect, request, session, url_for

# Phase AG: the only pages an associate's account opens; anything else sends them to My week (or is refused).
ASSOCIATE_PAGES = frozenset({"static", "login", "logout", "set_theme", "change_password", "me", "me_leave",
                             "me_leave_cancel", "me_swap", "me_swap_answer", "me_breaks", "me_breaks_ask",
                             "me_breaks_cancel", "end_other_sessions", "live_stamp"})
SAFE_NEXT = re.compile(r"/(?![/\\])[^\x00-\x20\x7f\\]*")  # a path here: no second slash, no backslash or control character


def associate_allowed(endpoint: Optional[str]) -> bool:
    return endpoint in ASSOCIATE_PAGES


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf() -> None:
    """Every POST carries the session's token, or it is refused (400)."""
    if request.method != "POST":
        return
    sent = request.form.get("csrf_token", "")
    expected = session.get("csrf", "")
    if not expected or not hmac.compare_digest(sent, expected):
        abort(400, description="This form expired or did not come from this site. Reload the page and try again.")


def safe_next(target: str) -> str:
    """``target`` when it is a path on this site, else "". A browser drops tabs and line breaks from an address and
    reads a backslash as a slash, so "/<tab>/example.com" would leave the site: none of them is allowed (Phase AC)."""
    target = target or ""
    return target if SAFE_NEXT.fullmatch(target) else ""


def session_stamp(user: Dict[str, Any]) -> str:
    """Changes whenever the password does: a session carrying an older stamp is signed out (Phase AC)."""
    return hashlib.sha256(str(user["password_hash"]).encode("utf-8")).hexdigest()[:16]


def load_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = current_app.extensions["store"].get_user(user_id)
    if user is None or not user["active"]:
        session.clear()  # disabled or deleted: out at once, not at the next login
        return
    stamp = session_stamp(user)
    if "pw" not in session:
        session["pw"] = stamp  # a session from before Phase AC: kept, and stamped now
    elif session["pw"] != stamp:
        session.clear()  # the password changed since this session signed in (a reset, or changed elsewhere)
        return
    if current_app.extensions["store"].session_revoked(user_id, session.get("at", 0)):
        session.clear()  # this session was signed out: a copy of its cookie is no use (Phase AV)
        return
    if session.get("at", 0) < user.get("sessions_from", 0):
        session.clear()  # "sign out other devices" was pressed after this session signed in (Phase AU)
        return
    g.user = user


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None:
            asked = request.full_path if request.query_string else request.path  # with its program and date
            return redirect(url_for("login", next=asked))
        if g.user["must_change"] and request.endpoint not in {"change_password", "logout"}:
            return redirect(url_for("change_password"))
        return view(*args, **kwargs)
    return wrapped


def manager_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Admins, and (Phase AK) the roles an admin allows this page on Roles (supervisors by default)."""
    from .permissions import ENDPOINTS, allowed

    @functools.wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        key = ENDPOINTS.get(request.endpoint or "")
        if not (g.user["is_admin"] or (key and allowed(current_app.extensions["store"], g.user, key))):
            abort(403, description="Your role cannot open this page.")
        return view(*args, **kwargs)
    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not g.user["is_admin"]:
            abort(403, description="Only admins can open this page.")
        return view(*args, **kwargs)
    return wrapped
