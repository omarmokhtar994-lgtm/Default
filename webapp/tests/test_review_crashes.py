# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AC (deep review, findings 2, 6 and 7): the workbook caches shared by the server's threads never crash a page
(34 KeyError and RuntimeError in 8 threads before), a date past the calendar's end is treated as no date instead of a
server error, and a request with the wrong method gets the site's own page that says what to do."""
import shutil
import sys
import tempfile
import threading
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from openpyxl import Workbook

from webapp import channels, day
from webapp.tests.test_runs import make_app, sign_in


def hammer(call, files, threads=8, rounds=1500):
    errors = Counter()
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # switch threads as often as possible: the race shows within a second

    def work(k):
        for n in range(rounds):
            try:
                call(files[(k * 7 + n) % len(files)])
            except Exception as exc:  # noqa: BLE001 (what the test counts)
                errors[type(exc).__name__] += 1
    try:
        ts = [threading.Thread(target=work, args=(k,)) for k in range(threads)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
    finally:
        sys.setswitchinterval(old)
    return errors


class TheCaches(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.files = []
        for i in range(20):
            f = self.dir / f"f{i}.xlsx"
            f.write_bytes(b"x" * (i + 1))
            self.files.append(f)

    def test_channel_cache_survives_threads(self):
        with mock.patch.object(channels, "_asks_for_someone", lambda path: True):
            channels._CACHE.clear()
            errors = hammer(channels.has_channel_needs, self.files)
        self.assertEqual(errors, Counter())

    def test_input_cache_survives_threads(self):
        # each call gets its own empty workbook, as each request loads its own file: one openpyxl workbook shared
        # by threads raises by itself (it makes cells as they are read), which is not what this test measures
        with mock.patch.object(day, "load_workbook", lambda path, data_only=True: Workbook()), \
                mock.patch.object(day, "KEEP", 3):
            day._CACHE.clear()
            errors = hammer(day.read_inputs, self.files, rounds=300)
        self.assertEqual(errors, Counter())

    def test_a_slow_read_does_not_block_other_files(self):
        started, release = threading.Event(), threading.Event()

        def slow(path):
            if path.name == "f0.xlsx":
                started.set()
                release.wait(5)
            return True
        with mock.patch.object(channels, "_asks_for_someone", slow):
            channels._CACHE.clear()
            reader = threading.Thread(target=channels.has_channel_needs, args=(self.files[0],))
            reader.start()
            self.assertTrue(started.wait(5))
            took = time.monotonic()
            channels.has_channel_needs(self.files[1])
            took = time.monotonic() - took
            release.set()
            reader.join(5)
        self.assertLess(took, 1.0)


class TheEdges(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(START_WORKER=False)
        cls.app.config["PROPAGATE_EXCEPTIONS"] = True
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")

    def test_far_dates_are_refused_not_crashed(self):
        for url in ("/day?program=X&date=9999-12-31", "/day?program=X&date=0001-01-01", "/overview?date=9999-12-31",
                    "/day/handover?date=9999-12-31", "/day/wallboard?date=9999-12-31", "/week?week=9999-12-26",
                    "/schedules?week=9999-12-26", "/exports/download?kind=runs&from=0001-01-01&to=9999-12-31",
                    "/coach?from=9999-12-31", "/?week=9999-12-26"):
            with self.subTest(url=url):
                got = self.client.get(url)
                self.assertLess(got.status_code, 500, url)

    def test_wrong_method_says_what_to_do(self):
        got = self.client.get("/runs")
        self.assertEqual(got.status_code, 405)
        page = got.get_data(as_text=True)
        self.assertIn("This address opens only from its form.", page)
        self.assertIn("Go back, then send the form again.", page)
        self.assertIn('class="leftnav"', page)  # the site's own layout, not the framework's page


if __name__ == "__main__":
    unittest.main()
