# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: theme."""
from __future__ import annotations

from flask import redirect, request

from ..app import THEMES
from ..auth import safe_next


def register(app, ctx) -> None:
    """Add the theme routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- theme
    @app.route("/theme", methods=["POST"])
    def set_theme():  # type: ignore[no-untyped-def]
        """Light, dark, or the device's own setting ("system"); kept in a cookie
        so the page is drawn in that theme from the first byte."""
        response = redirect(safe_next(request.form.get("next", "")) or "/")  # only ever back to this site
        choice = request.form.get("theme", "")
        if choice in THEMES:
            response.set_cookie("theme", choice, max_age=365 * 86400, httponly=True, samesite="Lax",
                                secure=bool(ctx.config.get("HTTPS", True)))
        else:
            response.delete_cookie("theme")
        return response

