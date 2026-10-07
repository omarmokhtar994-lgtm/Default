# © 2026 Omar Mokhtar. All rights reserved.
"""The team scheduler website: Flask application factory and routes."""
from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

from .auth import admin_required, check_csrf, csrf_token, load_user, login_required
from .store import Store

COPYRIGHT = "© 2026 Omar Mokhtar. All rights reserved."
MIN_PASSWORD = 10


def _secret_key(data_dir: Path) -> str:
    path = data_dir / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        os.chmod(path, 0o600)
    return path.read_text(encoding="utf-8").strip()


def password_problem(new: str, confirm: str, username: str) -> str:
    if len(new) < MIN_PASSWORD:
        return f"Use at least {MIN_PASSWORD} characters."
    if new != confirm:
        return "The two new passwords are different."
    if username.lower() in new.lower():
        return "Do not put your username in your password."
    return ""


def create_app(config: Dict[str, Any]) -> Flask:
    app = Flask(__name__)
    data_dir = Path(config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.update(
        SECRET_KEY=config.get("SECRET_KEY") or _secret_key(data_dir),
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(config.get("HTTPS", True)),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
    )
    app.config.update({k: v for k, v in config.items() if k not in {"SECRET_KEY"}})
    app.extensions["store"] = Store(data_dir / "scheduler.db")

    @app.before_request
    def _before() -> None:
        check_csrf()
        load_user()

    @app.after_request
    def _headers(response):  # type: ignore[no-untyped-def]
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; frame-ancestors 'none'")
        return response

    @app.context_processor
    def _globals() -> Dict[str, Any]:
        return {"csrf_token": csrf_token, "copyright": COPYRIGHT, "user": g.get("user")}

    # ------------------------------------------------------------- sign in/out
    @app.route("/login", methods=["GET", "POST"])
    def login():  # type: ignore[no-untyped-def]
        error = ""
        if request.method == "POST":
            user, reason = app.extensions["store"].authenticate(request.form.get("username", ""),
                                                                request.form.get("password", ""))
            if user is not None:
                session.clear()
                session.permanent = True
                session["user_id"] = user["id"]
                csrf_token()
                target = request.args.get("next", "")
                return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("home"))
            error = {"locked": "Too many wrong passwords: this account is locked for 15 minutes.",
                     "disabled": "This account is switched off. Ask your admin."}.get(
                         reason, "Wrong username or password.")
        return render_template("login.html", error=error)

    @app.route("/logout", methods=["POST"])
    def logout():  # type: ignore[no-untyped-def]
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
            if not error:
                store.set_password(g.user["id"], request.form["new"], must_change=False)
                flash("Password changed.")
                return redirect(url_for("home"))
        return render_template("password.html", error=error, forced=bool(g.user["must_change"]))

    # ------------------------------------------------------------- admin
    @app.route("/admin/users", methods=["GET", "POST"])
    @admin_required
    def admin_users():  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        error = ""
        if request.method == "POST":
            username = request.form.get("username", "").strip().lower()
            password = request.form.get("password", "")
            if not username or not username.replace(".", "").replace("_", "").replace("-", "").isalnum():
                error = "Usernames use letters, numbers, dots, dashes or underscores."
            elif any(u["username"] == username for u in store.list_users()):
                error = f"{username} already exists."
            elif len(password) < MIN_PASSWORD:
                error = f"Give a temporary password of at least {MIN_PASSWORD} characters."
            else:
                store.add_user(username, request.form.get("display_name", ""), password,
                               is_admin=request.form.get("is_admin") == "on", must_change=True)
                flash(f"Added {username}. They choose their own password at first sign-in.")
                return redirect(url_for("admin_users"))
        return render_template("admin_users.html", users=store.list_users(), error=error)

    @app.route("/admin/users/<int:user_id>/<action>", methods=["POST"])
    @admin_required
    def admin_user_action(user_id: int, action: str):  # type: ignore[no-untyped-def]
        store = app.extensions["store"]
        target = store.get_user(user_id)
        if target is None:
            abort(404)
        if target["id"] == g.user["id"] and action == "disable":
            flash("You cannot switch off your own account.")
        elif action == "disable":
            store.set_active(user_id, False)
            flash(f"{target['username']} is switched off.")
        elif action == "enable":
            store.set_active(user_id, True)
            flash(f"{target['username']} is switched on.")
        elif action == "reset":
            temporary = secrets.token_urlsafe(9)
            store.set_password(user_id, temporary, must_change=True)
            flash(f"Temporary password for {target['username']}: {temporary} "
                  "(shown once; they choose their own at next sign-in).")
        else:
            abort(404)
        return redirect(url_for("admin_users"))

    # ------------------------------------------------------------- home
    @app.route("/")
    @login_required
    def home():  # type: ignore[no-untyped-def]
        runs = app.extensions.get("runs")
        return render_template("dashboard.html", runs=app.extensions["store"].list_runs(),
                               queue=runs)

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def _error(err):  # type: ignore[no-untyped-def]
        messages = {403: "This page is for admins.", 404: "There is nothing here.",
                    413: "That file is larger than 25 MB."}
        text = messages.get(err.code) or getattr(err, "description", "") or "Something went wrong."
        return render_template("error.html", code=err.code, message=text), err.code

    return app
