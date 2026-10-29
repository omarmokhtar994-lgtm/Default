# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AZ (owner, 2026-10-24: "make sure all our code, engine and website, is fully organized"): the website's routes
move out of the one 5,000-line ``create_app`` into one module per area. This pins what the site registers, so the move
changes no address, endpoint, method, hook, filter or extension. ``route_map.json`` was written from the code before the
move (``python -m webapp.tests.test_az_route_map --write``); change it only when a route is added or removed on purpose."""
import json
import sys
import unittest
from pathlib import Path

from webapp.tests.test_runs import make_app

PINNED = Path(__file__).with_name("route_map.json")


def current_map():
    app, *_ = make_app(start_worker=False)
    rules = sorted([r.rule, r.endpoint, sorted(m for m in r.methods if m not in ("HEAD", "OPTIONS")),
                    sorted(r.defaults or {})] for r in app.url_map.iter_rules())
    hooks = {"before_request": sorted(f.__name__ for fs in app.before_request_funcs.values() for f in fs),
             "after_request": sorted(f.__name__ for fs in app.after_request_funcs.values() for f in fs),
             "context_processors": sorted(f.__name__ for fs in app.template_context_processors.values() for f in fs),
             "filters": sorted(app.jinja_env.filters), "globals": sorted(app.jinja_env.globals),
             "error_handlers": sorted(str(k) for d in app.error_handler_spec.values() for k in d),
             "url_defaults": sorted(f.__name__ for fs in app.url_default_functions.values() for f in fs),
             "extensions": sorted(app.extensions)}
    return json.loads(json.dumps({"rules": rules, "hooks": hooks}, sort_keys=True))


class TheSiteMap(unittest.TestCase):
    def test_the_routes_and_hooks_are_the_ones_pinned(self):
        pinned, now = json.loads(PINNED.read_text(encoding="utf-8")), current_map()
        self.assertEqual(now["rules"], pinned["rules"])
        self.assertEqual(now["hooks"], pinned["hooks"])


if __name__ == "__main__":
    if "--write" in sys.argv:
        PINNED.write_text(json.dumps(current_map(), indent=1, sort_keys=True), encoding="utf-8")
    else:
        unittest.main()
