# © 2026 Omar Mokhtar. All rights reserved.
"""Login, CSRF and access decorators."""
from __future__ import annotations

import functools
import hmac
import secrets
from typing import Any, Callable

from flask import abort, current_app, g, redirect, request, session, url_for


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


def load_user() -> None:
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = current_app.extensions["store"].get_user(user_id)
    if user is None or not user["active"]:
        session.clear()  # disabled or deleted: out at once, not at the next login
        return
    g.user = user


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if g.user is None:
            return redirect(url_for("login", next=request.path))
        if g.user["must_change"] and request.endpoint not in {"change_password", "logout"}:
            return redirect(url_for("change_password"))
        return view(*args, **kwargs)
    return wrapped


def manager_required(view: Callable[..., Any]) -> Callable[..., Any]:
    """Admins and supervisors (who manage the planners of their own programs)."""
    @functools.wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not (g.user["is_admin"] or g.user["is_supervisor"]):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def admin_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @functools.wraps(view)
    @login_required
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapped
