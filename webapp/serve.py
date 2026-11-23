# © 2026 Omar Mokhtar. All rights reserved.
"""Production server entry: Waitress on localhost; Caddy in front does HTTPS.

    SCHEDULER_DATA_DIR=/var/lib/scheduler SCHEDULER_PACKAGE_ROOT=/opt/scheduler/package \
        python -m webapp.serve

Settings come from the environment (deploy/scheduler-web.service sets them):
SCHEDULER_DATA_DIR (required: users, runs, results), SCHEDULER_PACKAGE_ROOT
(the installed production package), SCHEDULER_PORT (default 8080),
SCHEDULER_PARALLEL (runs at the same time, default 1: each run gets every CPU).
"""
from __future__ import annotations

import os
import sys
from typing import Any, Dict, Mapping

HOST = "127.0.0.1"  # never exposed directly; only Caddy talks to it


def config_from_env(env: Mapping[str, str]) -> Dict[str, Any]:
    data_dir = env.get("SCHEDULER_DATA_DIR", "").strip()
    if not data_dir:
        sys.exit("SCHEDULER_DATA_DIR is not set: the website needs a folder for its users and runs.")
    days = env.get("SCHEDULER_RUN_FILES_DAYS", "30").strip()
    if not days.isdigit() or not 30 <= int(days) <= 60:
        sys.exit(f"SCHEDULER_RUN_FILES_DAYS is {days!r}: run files are kept 30 to 60 days; give a number in that range.")
    return {
        "LIMITS": _limits(env),
        "DATA_DIR": data_dir,
        "RUN_FILES_DAYS": int(days),
        "PACKAGE_ROOT": env.get("SCHEDULER_PACKAGE_ROOT", "").strip() or None,
        "PORT": int(env.get("SCHEDULER_PORT", "8080")),
        "PARALLEL": int(env.get("SCHEDULER_PARALLEL", "1")),
        "HTTPS": env.get("SCHEDULER_HTTPS", "1") != "0",
        "START_WORKER": True,
    }


CONNECTION_LIMIT = 1000
THREADS = 8
# Phase BQ: waitress drops X-Forwarded-For unless told who may send it, and then every visitor looked like 127.0.0.1
# (one bot's wrong passwords held sign-in for everyone). Only Caddy, on this machine, is believed, and only for the
# visitor's address (the scheme and host stay as before).
PROXY = {"trusted_proxy": HOST, "trusted_proxy_count": 1, "trusted_proxy_headers": {"x-forwarded-for"}}


def _limits(env: Mapping[str, str]) -> Dict[str, int]:
    """Phase BQ: requests per minute for each signed-in person and for each address not signed in, and how many of
    the worker threads people not signed in may hold at once (the rest stay free for staff)."""
    out = {}
    for key, default, top in (("PER_USER", 600, None), ("PER_ADDRESS", 1200, None), ("ANON_BUSY", 4, THREADS - 1)):
        name = f"SCHEDULER_LIMIT_{key}"
        text = env.get(name, str(default)).strip()
        if not text.isdigit() or int(text) < 1 or (top and int(text) > top):
            sys.exit(f"{name} is {text!r}: give a whole number from 1" + (f" to {top}." if top else " up."))
        out[key] = int(text)
    return out


def main() -> None:
    from waitress import serve
    from werkzeug.middleware.proxy_fix import ProxyFix

    from .app import create_app

    from openpyxl.xml import DEFUSEDXML
    if not DEFUSEDXML:  # Phase AV: without it a workbook with an XML entity bomb could use up the server
        sys.exit("defusedxml is not installed: run pip install -r deploy/requirements.txt (a workbook's XML is not safe to read without it).")
    config = config_from_env(os.environ)
    app = create_app(config)
    # Caddy (on this machine) tells the app the visitor's address and that it came in over HTTPS.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]
    print(f"Team Scheduler on http://{HOST}:{config['PORT']} (data {config['DATA_DIR']}, "
          f"package {config['PACKAGE_ROOT']})", flush=True)
    # Phase AV: waitress refuses new connections past 100 open ones, and people waiting on a busy page each hold one
    serve(app, host=HOST, port=config["PORT"], threads=THREADS, max_request_body_size=26 * 1024 * 1024,
          connection_limit=CONNECTION_LIMIT, ident="TeamScheduler", **PROXY)


if __name__ == "__main__":
    main()
