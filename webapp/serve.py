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
        "DATA_DIR": data_dir,
        "RUN_FILES_DAYS": int(days),
        "PACKAGE_ROOT": env.get("SCHEDULER_PACKAGE_ROOT", "").strip() or None,
        "PORT": int(env.get("SCHEDULER_PORT", "8080")),
        "PARALLEL": int(env.get("SCHEDULER_PARALLEL", "1")),
        "HTTPS": env.get("SCHEDULER_HTTPS", "1") != "0",
        "START_WORKER": True,
    }


def main() -> None:
    from waitress import serve
    from werkzeug.middleware.proxy_fix import ProxyFix

    from .app import create_app

    config = config_from_env(os.environ)
    app = create_app(config)
    # Caddy (on this machine) tells the app the visitor's address and that it came in over HTTPS.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # type: ignore[method-assign]
    print(f"Team Scheduler on http://{HOST}:{config['PORT']} (data {config['DATA_DIR']}, "
          f"package {config['PACKAGE_ROOT']})", flush=True)
    serve(app, host=HOST, port=config["PORT"], threads=8, max_request_body_size=26 * 1024 * 1024,
          ident="TeamScheduler")


if __name__ == "__main__":
    main()
