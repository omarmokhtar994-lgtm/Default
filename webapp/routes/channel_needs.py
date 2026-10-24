# © 2026 Omar Mokhtar. All rights reserved.
"""Website routes: channel needs for a schedule."""
from __future__ import annotations

import io
import os
import secrets
import tempfile
from pathlib import Path

from flask import abort, flash, redirect, request, send_file, url_for
from werkzeug.utils import secure_filename

from ..auth import login_required
from ..channel_template import channel_workbook
from ..day import read_inputs
from ..zipcheck import zip_problem


def register(app, ctx) -> None:
    """Add the channel needs for a schedule routes to ``app``; ``ctx`` holds the helpers the areas share."""
    # ------------------------------------------------------------- channel needs for a schedule (Phase Z)
    @app.route("/runs/<run_id>/channel-needs.xlsx")
    @login_required
    def channel_needs_download(run_id: str):  # type: ignore[no-untyped-def]
        """The channel needs workbook made for this run's week: the needs added to it when there are some (to
        change them), else the empty tabs at the run's interval."""
        run = ctx._run_or_404(run_id)
        book = ctx._book()
        source = book.input_path(run_id)
        if not source.is_file():
            abort(404)
        name = secure_filename(f"Channel_needs_{run.get('program') or run_id}_{run.get('week_start') or ''}"
                               ).rstrip("_") + ".xlsx"
        added_needs = book.root / run_id / "channels.xlsx"
        if added_needs.is_file():
            return send_file(added_needs, as_attachment=True, download_name=name)
        inputs = read_inputs(source)
        with tempfile.TemporaryDirectory() as folder:
            made = channel_workbook(Path(folder) / name, inputs["interval"],
                                    [lang["name"] for lang in inputs["languages"]])
            data = io.BytesIO(made.read_bytes())
        return send_file(data, as_attachment=True, download_name=name,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/runs/<run_id>/channel-needs", methods=["POST"])
    @login_required
    def channel_needs_add(run_id: str):  # type: ignore[no-untyped-def]
        """Add channel needs to this schedule (anyone who can edit its versions): kept with the run, no new run."""
        run = ctx._run_or_404(run_id)
        back = redirect(url_for("run_schedules", run_id=run_id) + "#channels")
        upload = request.files.get("workbook")
        if upload is None or not os.path.basename(upload.filename or "").lower().endswith(".xlsx"):
            flash("Pick the channel needs workbook (.xlsx) to add.")
            return back
        incoming = ctx._queue().runs_root / "_incoming"
        incoming.mkdir(exist_ok=True)
        path = incoming / f"{secrets.token_hex(8)}.upload"
        upload.save(path)
        too_big = zip_problem(path)  # Phase AU
        if too_big:
            path.unlink(missing_ok=True)
            flash(too_big)
            return back
        refused = ctx._upload_refused(path, upload.filename or "", structure=False)  # Phase AV
        if refused:
            flash(refused)
            return back
        try:
            lines = ctx._book().attach_channels(run_id, path)
        except ValueError as exc:
            flash(f"These channel needs were not added: {exc}")
            return back
        finally:
            path.unlink(missing_ok=True)
        warnings = sum(1 for level, _ in lines if level == "warn")
        ctx._record("channel_needs_added", run, detail=f"{warnings} warning{'s' if warnings != 1 else ''}")
        flash(f"Channel needs added to {run['workbook']}: " + (
            f"{warnings} warning{'s' if warnings != 1 else ''}, listed under Channels. They never change the schedule."
            if warnings else "checked, no warnings.") + " Plan channels is ready.")
        return back

