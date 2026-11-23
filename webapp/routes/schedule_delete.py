# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: delete a schedule."""
from __future__ import annotations

import shutil

from flask import abort, flash, redirect, request, url_for

from ..auth import login_required
from ..runs import ACTIVE


def register(app, ctx) -> None:
    """Add the delete a schedule routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- delete a schedule (Phase AA)
    @app.route("/runs/<run_id>/delete", methods=["POST"])
    @login_required
    def run_delete(run_id: str):  # type: ignore[no-untyped-def]
        """Delete a schedule that is not needed (owner, 2026-10-10: "Uploader or admin"): admins and the person who
        uploaded or ran it, any schedule not in use and not running. The days' records stay; the log keeps it."""
        run = ctx._run_or_404(run_id)
        if not ctx._may_delete(run):
            abort(403)
        program, week = run.get("program") or "", run.get("week_start") or ""
        back = redirect(url_for("schedules_for", program=program, week=week) if program else url_for("home"))
        if request.form.get("confirm") != "1":
            flash("Tick the box to confirm, then press Delete schedule.")
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        if run["status"] in ACTIVE + ("QUEUED",):
            flash(f"{run['workbook']} is still running: stop it first, then delete it.")
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        try:
            count = ctx._book().delete_run(run_id)
        except ValueError as exc:
            flash(str(exc))
            return redirect(url_for("run_schedules", run_id=run_id) + "#delete")
        shutil.rmtree(ctx._queue().run_dir(run_id), ignore_errors=True)
        ctx._record("run_deleted", run, detail=f"{count} version{'s' if count != 1 else ''}")
        flash(f"Deleted {run['workbook']}." if not count else
              f"Deleted {run['workbook']} and its {count} version{'s' if count != 1 else ''}.")
        return back

