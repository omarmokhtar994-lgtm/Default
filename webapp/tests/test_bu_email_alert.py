# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BU (owner, 2026-11-19: alerts "can it be an email", then "1" = the owner's Gmail sends to itself with an app password): the disk alert
and a failed nightly copy also send an email. The password is read from a file systemd hands the service (LoadCredential), never printed."""
import importlib.util
import io
import json
import os
import smtplib
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"


def load(name):
    spec = importlib.util.spec_from_file_location(name, DEPLOY / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = load("mail_alert")
A = load("disk_alert")
B = load("db_backup")
SECRET = "abcd efgh ijkl mnop"
EMAIL = {"ALERT_EMAIL": "associate01@example.com", "SMTP_USER": "associate01@example.com"}


def password_file(text=SECRET):
    folder = Path(tempfile.mkdtemp())
    (folder / "smtp-password").write_text(text)
    return folder


class TheEmail(unittest.TestCase):
    def send(self, env, smtp=None, folder=None):
        folder = folder or password_file()
        out = io.StringIO()
        full = {"CREDENTIALS_DIRECTORY": str(folder), **env}
        smtp = smtp or mock.MagicMock()
        with mock.patch.dict("os.environ", full, clear=True), mock.patch.object(M.smtplib, "SMTP", smtp), redirect_stdout(out):
            got = M.send("A subject", "A text")
        return got, smtp, out.getvalue()

    def test_without_an_address_it_is_not_set_up_and_connects_to_nothing(self):
        got, smtp, _ = self.send({})
        self.assertIsNone(got)
        smtp.assert_not_called()

    def test_it_sends_over_tls_to_gmail_with_the_app_password_without_its_spaces(self):
        got, smtp, out = self.send(EMAIL)
        self.assertTrue(got)
        smtp.assert_called_once_with("smtp.gmail.com", 587, timeout=20)
        server = smtp.return_value.__enter__.return_value
        server.starttls.assert_called_once()
        self.assertIsNotNone(server.starttls.call_args.kwargs.get("context"))
        server.login.assert_called_once_with("associate01@example.com", "abcdefghijklmnop")
        msg = server.send_message.call_args[0][0]
        self.assertEqual((msg["To"], msg["From"], msg["Subject"]), ("associate01@example.com", "associate01@example.com", "A subject"))
        self.assertIn("A text", msg.get_content())
        self.assertNotIn("abcd", out)

    def test_a_missing_or_empty_password_is_said_and_nothing_is_tried(self):
        for folder in (password_file(""), Path(tempfile.mkdtemp())):
            got, smtp, out = self.send(EMAIL, folder=folder)
            self.assertFalse(got)
            smtp.assert_not_called()
            self.assertIn("password", out)

    def test_a_refused_sign_in_is_a_failure_and_never_shows_the_password(self):
        smtp = mock.MagicMock()
        smtp.return_value.__enter__.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad " + SECRET.encode())
        got, _, out = self.send(EMAIL, smtp=smtp)
        self.assertFalse(got)
        self.assertIn("535", out)
        self.assertNotIn("abcd", out)
        self.assertNotIn("abcdefghijklmnop", out)

    def test_a_network_error_is_a_failure(self):
        got, _, out = self.send(EMAIL, smtp=mock.MagicMock(side_effect=OSError("timed out")))
        self.assertFalse(got)
        self.assertIn("OSError", out)

    def test_bad_settings_are_refused_by_name(self):
        for bad, words in (({"SMTP_PORT": "lots"}, "SMTP_PORT"), ({"ALERT_EMAIL": "not an address"}, "ALERT_EMAIL"), ({"SMTP_USER": ""}, "SMTP_USER")):
            got, smtp, out = self.send({**EMAIL, **bad})
            self.assertFalse(got, bad)
            smtp.assert_not_called()
            self.assertIn(words, out)


class TheDiskAlertByEmail(unittest.TestCase):
    def run_main(self, pct, mail_ok, unit="", state=None):
        tmp = Path(tempfile.mkdtemp())
        sf = tmp / "state.json"
        if state is not None:
            sf.write_text(json.dumps(state))
        usage = mock.Mock(used=int(pct * 10 ** 9), total=100 * 10 ** 9)
        env = {"ALERT_STATE": str(sf), "SCHEDULER_DATA_DIR": str(tmp), "ALERT_UNIT": unit, "DISK_PATH": str(tmp)}
        with mock.patch.dict("os.environ", env), mock.patch.object(A.shutil, "disk_usage", return_value=usage), \
                mock.patch.object(A, "post", return_value=True) as posted, mock.patch.object(A.MAIL, "send", return_value=mail_ok) as mailed:
            code = A.main([])
        return code, posted, mailed, sf

    def test_a_full_disk_is_emailed_with_the_same_words(self):
        code, posted, mailed, sf = self.run_main(95, mail_ok=True)
        self.assertEqual(code, 0)
        posted.assert_not_called()
        subject, text = mailed.call_args[0]
        self.assertEqual((subject, text), A.words("rise", 95, 95 * 10 ** 9 / 2 ** 30, 100 * 10 ** 9 / 2 ** 30))
        self.assertEqual(json.loads(sf.read_text())["level"], "crit")

    def test_a_failed_email_is_not_remembered_so_it_is_tried_again(self):
        code, _, _, sf = self.run_main(95, mail_ok=False)
        self.assertEqual(code, 1)
        self.assertFalse(sf.exists())

    def test_email_and_group_together_both_go(self):
        code, posted, mailed, _ = self.run_main(95, mail_ok=True, unit="Group A")
        self.assertEqual((code, posted.call_count, mailed.call_count), (0, 1, 1))

    def test_with_no_email_set_up_it_works_as_before(self):
        code, posted, mailed, sf = self.run_main(95, mail_ok=None)
        self.assertEqual((code, posted.call_count), (0, 0))
        self.assertEqual(json.loads(sf.read_text())["level"], "crit")

    def test_a_fine_disk_sends_no_email(self):
        _, _, mailed, _ = self.run_main(30, mail_ok=True)
        mailed.assert_not_called()


class TheBackupByEmail(unittest.TestCase):
    def test_a_failed_night_is_emailed_and_a_good_one_is_not(self):
        tmp = Path(tempfile.mkdtemp())
        env = {"SCHEDULER_DATA_DIR": str(tmp / "nothing"), "BACKUP_DIR": str(tmp / "b"), "KEEP": "14"}
        with mock.patch.dict("os.environ", env), mock.patch.object(B.MAIL, "send", return_value=True) as mailed:
            self.assertEqual(B.main([]), 1)
        subject, text = mailed.call_args[0]
        self.assertIn("backup failed", subject.lower())
        self.assertIn("not found", text)
        (tmp / "data").mkdir()
        import sqlite3
        sqlite3.connect(tmp / "data" / "scheduler.db").close()
        env["SCHEDULER_DATA_DIR"] = str(tmp / "data")
        with mock.patch.dict("os.environ", env), mock.patch.object(B.MAIL, "send", return_value=True) as mailed:
            self.assertEqual(B.main([]), 0)
        mailed.assert_not_called()


class TheSetup(unittest.TestCase):
    def dry(self, existing=None):
        out = Path(tempfile.mkdtemp())
        if existing is not None:
            (out / "etc" / "scheduler").mkdir(parents=True)
            (out / "etc" / "scheduler" / "smtp-password").write_text(existing)
        env = dict(os.environ, DRY_RUN="1", DRY_ROOT=str(out))
        proc = subprocess.run(["bash", str(DEPLOY / "setup_timers.sh")], capture_output=True, text=True, env=env, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        return out

    def test_both_services_get_the_password_from_systemd_and_read_the_settings(self):
        units = self.dry() / "etc" / "systemd" / "system"
        for name in ("disk-alert.service", "scheduler-backup.service"):
            text = (units / name).read_text(encoding="utf-8")
            self.assertIn("LoadCredential=smtp-password:/etc/scheduler/smtp-password", text, name)
            self.assertIn("EnvironmentFile=-/etc/scheduler/disk-alert.env", text, name)

    def test_an_empty_root_only_password_file_is_made_once_and_never_overwritten(self):
        out = self.dry()
        made = out / "etc" / "scheduler" / "smtp-password"
        self.assertEqual(made.read_text(), "")
        self.assertEqual(made.stat().st_mode & 0o777, 0o600)
        kept = self.dry(existing="already typed") / "etc" / "scheduler" / "smtp-password"
        self.assertEqual(kept.read_text(), "already typed")

    def test_the_settings_file_offers_the_email_lines(self):
        made = (self.dry() / "etc" / "scheduler" / "disk-alert.env").read_text(encoding="utf-8")
        for line in ("# ALERT_EMAIL=", "# SMTP_USER=", "# SMTP_HOST=smtp.gmail.com", "# SMTP_PORT=587"):
            self.assertIn(line, made)

    def test_the_setup_note_says_how_to_type_the_password_without_it_showing(self):
        note = (DEPLOY / "disk_alert_setup.md").read_text(encoding="utf-8")
        self.assertIn("read -rs", note)
        self.assertIn("App password", note)


if __name__ == "__main__":
    unittest.main()
