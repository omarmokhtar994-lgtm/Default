# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: an upload that is a zip bomb is refused before any workbook library opens it."""
import io
import re
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from webapp import zipcheck
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import make_app, sign_in, token


def bomb(megabytes, members=1):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for n in range(members):
            z.writestr(f"xl/worksheets/sheet{n}.xml", b"0" * (megabytes * 1024 * 1024))
    return out.getvalue()


class TheCheck(unittest.TestCase):
    def test_a_real_workbook_passes(self):
        path = make_ready(Path(tempfile.mkdtemp()) / "ready.xlsx")
        self.assertEqual(zipcheck.zip_problem(path), "")
        self.assertEqual(zipcheck.zip_problem(path.read_bytes()), "")

    def test_a_small_file_that_opens_huge_is_refused(self):
        data = bomb(30)                                         # 30 MB of zeros packs to about 30 KB
        self.assertLess(len(data), 1024 * 1024)
        self.assertEqual(zipcheck.zip_problem(data), zipcheck.PROBLEM)

    def test_the_limits_are_the_ones_named(self):
        with mock.patch.object(zipcheck, "MAX_MEMBER_BYTES", 5 * 1024 * 1024):
            self.assertEqual(zipcheck.zip_problem(bomb(6)), zipcheck.PROBLEM)
            self.assertEqual(zipcheck.zip_problem(bomb(4)), "")
        with mock.patch.object(zipcheck, "MAX_TOTAL_BYTES", 5 * 1024 * 1024):
            self.assertEqual(zipcheck.zip_problem(bomb(2, members=4)), zipcheck.PROBLEM)
        with mock.patch.object(zipcheck, "MAX_MEMBERS", 3):
            self.assertEqual(zipcheck.zip_problem(bomb(1, members=4)), zipcheck.PROBLEM)

    def test_a_file_that_is_not_a_zip_says_so(self):
        self.assertIn("not a readable", zipcheck.zip_problem(b"PK\x03\x04 broken"))


class TheUploads(unittest.TestCase):
    def test_the_run_upload_refuses_a_bomb_and_starts_nothing(self):
        app, store, *_ = make_app(start_worker=False)
        client = sign_in(app, "sara", "Sara-pass-1")
        before = len(store.list_runs())
        got = client.post("/runs", data={"csrf_token": token(client), "kind": "ready", "mode": "QUICK",
                                         "workbook": (io.BytesIO(bomb(30)), "week.xlsx")},
                          content_type="multipart/form-data", follow_redirects=True)
        self.assertIn("far larger once opened", got.get_data(as_text=True))
        self.assertEqual(len(store.list_runs()), before)

    def test_the_people_sheet_refuses_a_bomb(self):
        from webapp.bulk_users import read_people
        with self.assertRaises(ValueError) as caught:
            read_people(bomb(30), "people.xlsx")
        self.assertIn("far larger once opened", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
