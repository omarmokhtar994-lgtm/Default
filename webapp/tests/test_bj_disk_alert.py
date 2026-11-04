# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: the server disk filled up): the disk alert says what it should, when it should, and never spams."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("disk_alert", Path(__file__).resolve().parents[2] / "deploy" / "disk_alert.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)
H = 3600


class TheDecision(unittest.TestCase):
    def test_nothing_to_say_while_the_disk_is_fine(self):
        self.assertEqual(A.decide(40, {}, 1000), (None, {"level": "ok", "at": 0.0}))

    def test_it_speaks_when_the_level_rises(self):
        self.assertEqual(A.decide(83, {}, 1000), ("rise", {"level": "warn", "at": 1000}))
        self.assertEqual(A.decide(95, {"level": "warn", "at": 500}, 1000), ("rise", {"level": "crit", "at": 1000}))
        self.assertEqual(A.decide(99, {}, 1000)[0], "rise")

    def test_it_does_not_repeat_until_its_time(self):
        s = {"level": "crit", "at": 1000}
        self.assertEqual(A.decide(95, s, 1000 + 5 * H)[0], None)
        self.assertEqual(A.decide(95, s, 1000 + 6 * H)[0], "repeat")
        w = {"level": "warn", "at": 1000}
        self.assertEqual(A.decide(85, w, 1000 + 23 * H)[0], None)
        self.assertEqual(A.decide(85, w, 1000 + 24 * H)[0], "repeat")

    def test_it_says_when_things_improve_and_when_they_are_normal_again(self):
        self.assertEqual(A.decide(85, {"level": "crit", "at": 1}, 2)[0], "improve")
        self.assertEqual(A.decide(50, {"level": "warn", "at": 1}, 2), ("clear", {"level": "ok", "at": 2}))

    def test_a_disk_hovering_just_under_the_line_does_not_flap(self):
        for pct in (79.9, 78, 77.1):
            what, new = A.decide(pct, {"level": "warn", "at": 1}, 2)
            self.assertEqual((what, new["level"]), (None, "warn"), pct)
        self.assertEqual(A.decide(76, {"level": "warn", "at": 1}, 2)[0], "clear")

    def test_a_test_message_says_it_is_a_test(self):
        title, text = A.words("test", 10, 4.0, 45.0)
        self.assertIn("test", title.lower())
        self.assertIn("no action is needed", text)

    def test_after_a_clear_a_new_rise_is_said_again(self):
        _, s = A.decide(50, {"level": "warn", "at": 1}, 2)
        self.assertEqual(A.decide(85, s, 3)[0], "rise")

    def test_the_words_say_what_to_do_and_never_contain_a_link(self):
        for what, pct in (("rise", 85), ("rise", 95), ("clear", 50)):
            title, text = A.words(what, pct, 38.0, 45.0)
            self.assertNotIn("http", title + text)
            self.assertIn(f"{pct}%", text)
        self.assertIn("Free", A.words("rise", 95, 43.0, 45.0)[1])


class ThePost(unittest.TestCase):
    def folder(self, link="https://hooks.slack.com/services/T000/B000/XXXX", unit="Group A"):
        import sqlite3
        tmp = Path(tempfile.mkdtemp())
        db = sqlite3.connect(tmp / "scheduler.db")
        db.execute("create table notify_settings (unit text primary key, link text not null default '', service text not null default '')")
        db.execute("insert into notify_settings (unit, link) values (?, ?)", (unit, link))
        db.commit()
        db.close()
        return tmp

    def test_it_posts_with_the_websites_sender_and_never_prints_the_link(self):
        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with mock.patch("webapp.notify.post_json", return_value=(True, 200)) as sender, redirect_stdout(out):
            self.assertTrue(A.post("Group A", self.folder(), "A title", "A text"))
        self.assertEqual(sender.call_count, 1)
        self.assertEqual(sender.call_args[0][0], "https://hooks.slack.com/services/T000/B000/XXXX")
        self.assertNotIn("hooks.slack.com", out.getvalue())
        self.assertNotIn("XXXX", out.getvalue())

    def test_it_works_when_the_database_cannot_be_written(self):
        import os
        tmp = self.folder()
        os.chmod(tmp / "scheduler.db", 0o444)
        os.chmod(tmp, 0o555)
        try:
            with mock.patch("webapp.notify.post_json", return_value=(True, 200)):
                self.assertTrue(A.post("Group A", tmp, "t", "x"))
        finally:
            os.chmod(tmp, 0o755)

    def test_no_such_group_a_bad_link_or_no_database_post_nothing(self):
        with mock.patch("webapp.notify.post_json", return_value=(True, 200)) as sender:
            self.assertFalse(A.post("Nobody", self.folder(), "t", "x"))
            self.assertFalse(A.post("Group A", self.folder(link="https://example.com/not-a-group"), "t", "x"))
            self.assertFalse(A.post("Group A", Path(tempfile.mkdtemp()), "t", "x"))
        sender.assert_not_called()

    def test_a_refused_post_is_a_failure_so_it_is_tried_again(self):
        with mock.patch("webapp.notify.post_json", return_value=(False, 500)):
            self.assertFalse(A.post("Group A", self.folder(), "t", "x"))


class TheRun(unittest.TestCase):
    def run_main(self, pct, state=None, unit="", post_ok=True, argv=()):
        tmp = Path(tempfile.mkdtemp())
        sf = tmp / "state.json"
        if state is not None:
            sf.write_text(json.dumps(state))
        usage = mock.Mock(used=int(pct * 10 ** 9), total=100 * 10 ** 9)
        env = {"ALERT_STATE": str(sf), "SCHEDULER_DATA_DIR": str(tmp), "ALERT_UNIT": unit, "DISK_PATH": str(tmp)}
        with mock.patch.dict("os.environ", env), mock.patch.object(A.shutil, "disk_usage", return_value=usage), \
                mock.patch.object(A, "post", return_value=post_ok) as sent:
            code = A.main(list(argv))
        return code, sent, sf

    def test_a_full_disk_with_no_group_named_only_logs_and_remembers(self):
        code, sent, sf = self.run_main(95)
        self.assertEqual(code, 0)
        sent.assert_not_called()
        self.assertEqual(json.loads(sf.read_text())["level"], "crit")

    def test_a_full_disk_with_a_group_posts_once_then_stays_quiet(self):
        code, sent, sf = self.run_main(95, unit="Group A")
        self.assertEqual((code, sent.call_count), (0, 1))
        code, sent, _ = self.run_main(95, state=json.loads(sf.read_text()), unit="Group A")
        self.assertEqual((code, sent.call_count), (0, 0))

    def test_a_failed_post_is_not_remembered_so_it_is_tried_again(self):
        code, sent, sf = self.run_main(95, unit="Group A", post_ok=False)
        self.assertEqual(code, 1)
        self.assertFalse(sf.exists())

    def test_a_fine_disk_says_nothing(self):
        code, sent, _ = self.run_main(30, unit="Group A")
        self.assertEqual((code, sent.call_count), (0, 0))

    def test_test_mode_posts_whatever_the_level_and_keeps_no_state(self):
        code, sent, sf = self.run_main(10, unit="Group A", argv=["--test"])
        self.assertEqual((code, sent.call_count), (0, 1))
        self.assertFalse(sf.exists())

    def test_a_damaged_state_file_is_treated_as_empty(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / "state.json").write_text("{not json")
        usage = mock.Mock(used=90 * 10 ** 9, total=100 * 10 ** 9)
        with mock.patch.dict("os.environ", {"ALERT_STATE": str(tmp / "state.json"), "ALERT_UNIT": "", "DISK_PATH": str(tmp)}), \
                mock.patch.object(A.shutil, "disk_usage", return_value=usage):
            self.assertEqual(A.main([]), 0)


if __name__ == "__main__":
    unittest.main()
