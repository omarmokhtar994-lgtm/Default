# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AC (deep review, finding 8, and earlier open items): time fields look like the other fields; the browser's
own bar takes the page colour of each look; a program or LOB name needs a letter or a number (a name of only dots
made a page address the browser rewrites); an upload left in the staging folder by a crash is swept after a day."""
import os
import re
import time
import unittest
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_runs import make_app, sign_in

CSS = (Path(__file__).resolve().parents[1] / "static" / "app.css").read_text(encoding="utf-8")


def rules_for(selector):
    """The declarations of every top-level rule that lists ``selector`` on its own (not inside another one)."""
    found = []
    for head, body in re.findall(r"([^{}]+)\{([^{}]*)\}", CSS):
        if selector in [s.strip() for s in head.split(",")]:
            found.append(body)
    return " ".join(found)


class TheTimeFields(unittest.TestCase):
    def test_time_fields_share_the_field_style(self):
        text, time_ = rules_for("input[type=text]"), rules_for("input[type=time]")
        for prop in ("padding", "font", "color", "background", "border", "border-radius"):
            with self.subTest(prop=prop):
                want = re.search(rf"(?<![-\w]){prop}:\s*([^;]+);", text).group(1).strip()
                got = re.search(rf"(?<![-\w]){prop}:\s*([^;]+);", time_)
                self.assertIsNotNone(got, f"input[type=time] has no {prop}")
                self.assertEqual(got.group(1).strip(), want)


class TheBrowserBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)

    def test_theme_color_meta(self):
        page = self.app.test_client().get("/login").get_data(as_text=True)  # no look picked: the device decides
        self.assertIn('<meta name="theme-color" content="#0E1A2B" media="(prefers-color-scheme: dark)">', page)
        self.assertIn('<meta name="theme-color" content="#EAEFF5" media="(prefers-color-scheme: light)">', page)
        client = sign_in(self.app, "omar", "Owner-pass-123")
        client.set_cookie("theme", "light")  # the look the person picked
        page = client.get("/").get_data(as_text=True)
        self.assertEqual(re.findall(r'<meta name="theme-color"[^>]*>', page), ['<meta name="theme-color" content="#EAEFF5">'])
        client.set_cookie("theme", "dark")  # the look the person picked
        page = client.get("/").get_data(as_text=True)
        self.assertEqual(re.findall(r'<meta name="theme-color"[^>]*>', page), ['<meta name="theme-color" content="#0E1A2B">'])


class TheNames(unittest.TestCase):
    def setUp(self):
        _, self.store, *_ = make_app(start_worker=False)
        self.book = ProgramBook(self.store)

    def test_names_of_only_dots_are_refused(self):
        pid = self.book.add_program("SAKS")
        for name in (".", "..", "...", " . . ", "-", "#"):
            with self.subTest(name=name):
                for call in (lambda: self.book.add_program(name), lambda: self.book.add_lob(pid, name),
                             lambda: self.book.rename(pid, None, name)):
                    with self.assertRaises(ValueError) as said:
                        call()
                    self.assertEqual(str(said.exception), "Use letters or numbers in the name.")
        self.assertTrue(self.book.add_lob(pid, "Tier 2."))  # dots beside letters are fine
        self.assertEqual(self.book.program(pid)["name"], "SAKS")


class TheStagingFolder(unittest.TestCase):
    def test_incoming_leftovers_are_swept(self):
        app, *_ = make_app(start_worker=False)
        queue = app.extensions["runs"]
        incoming = queue.runs_root / "_incoming"
        incoming.mkdir(exist_ok=True)
        old, fresh, other = incoming / "a1b2.upload", incoming / "c3d4.upload", incoming / "note.txt"
        for f in (old, fresh, other):
            f.write_bytes(b"PK")
        two_days_ago = time.time() - 2 * 86400
        os.utime(old, (two_days_ago, two_days_ago))
        os.utime(other, (two_days_ago, two_days_ago))
        queue.cleanup()
        self.assertFalse(old.exists())  # left by a crash between saving and handing over
        self.assertTrue(fresh.exists())  # may be on its way to a run right now
        self.assertTrue(other.exists())  # only uploads are swept


if __name__ == "__main__":
    unittest.main()
