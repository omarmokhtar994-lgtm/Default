# © 2026 Omar Mokhtar. All rights reserved.
"""Phase I task 2: upload, check, queue, run, score, download, expire.

The production runner, input check, gate and scorer are replaced by
webapp/tests/fakes.py so the website's own logic is tested in seconds; the
real runner is exercised end to end separately (evidence/phase_i)."""
import html
import io
import json
import re
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from webapp.app import create_app
from webapp.store import Store

FAKES = Path(__file__).with_name("fakes.py")
TOKEN = re.compile(r'name="csrf_token" value="([^"]+)"')
FINAL = {"DONE", "FAILED", "REJECTED", "INTERRUPTED", "STOPPED", "EXPIRED"}


def make_app(start_worker=True, gate_fails=False, **extra):
    data = Path(tempfile.mkdtemp())
    package = data / "package"
    package.mkdir()
    (package / "MANIFEST.json").write_text('{"package": "test"}', encoding="utf-8")
    gate_marker = data / "gate_calls"
    if gate_fails:
        Path(str(gate_marker) + ".fail").write_text("x")
    fake = [sys.executable, str(FAKES)]
    config = {"DATA_DIR": str(data), "SECRET_KEY": "t", "TESTING": True, "HTTPS": False,
              "PACKAGE_ROOT": str(package), "START_WORKER": start_worker,
              "RUNNER_CMD": fake + ["runner"], "CHECK_CMD": fake + ["check"],
              "SCORE_CMD": fake + ["score"], "GATE_CMD": fake + ["gate", str(gate_marker)]}
    config.update(extra)
    app = create_app(config)
    store = Store(data / "scheduler.db")
    store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
    return app, store, data, gate_marker


def client_for(app):
    client = app.test_client()
    tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
    client.post("/login", data={"username": "sara", "password": "Sara-pass-1", "csrf_token": tok})
    return client


def token(client):
    return TOKEN.search(client.get("/").get_data(as_text=True)).group(1)


def upload(client, name="week42.xlsx", data=b"PK\x03\x04 fake workbook", mode="QUICK"):
    return client.post("/runs", data={"csrf_token": token(client), "mode": mode,
                                      "workbook": (io.BytesIO(data), name)},
                       content_type="multipart/form-data", follow_redirects=False)


def run_id_of(response):
    return response.headers["Location"].rstrip("/").split("/")[-1]


def wait(store, run_id, statuses=FINAL, seconds=30):
    end = time.time() + seconds
    while time.time() < end:
        run = store.get_run(run_id)
        if run and run["status"] in statuses:
            return run
        time.sleep(0.1)
    raise AssertionError(f"run {run_id} still {store.get_run(run_id)['status']}")


class UploadAndCheck(unittest.TestCase):
    def test_upload_rejects_non_xlsx_and_oversize(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        page = upload(client, name="notes.txt")
        self.assertIn("Upload an Excel workbook (.xlsx)", client.get("/").get_data(as_text=True)
                      if page.status_code == 302 else page.get_data(as_text=True))
        self.assertEqual(store.list_runs(), [])
        big = upload(client, data=b"x" * (26 * 1024 * 1024))
        self.assertEqual(big.status_code, 413)

    def test_check_rejection_is_shown_with_its_message(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        run_id = run_id_of(upload(client, name="bad_week.xlsx"))
        run = store.get_run(run_id)
        self.assertEqual(run["status"], "REJECTED")
        # As the reader sees it: the page HTML-escapes the quotes.
        page = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("Schedule!C7: unknown associate 'Zed'", page)


class RunningAndResults(unittest.TestCase):
    def test_accepted_run_goes_through_to_done_with_zip_and_verdict(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        run = wait(store, run_id)
        self.assertEqual((run["status"], run["exit_code"]), ("DONE", 0))
        self.assertIn("RELEASABLE", run["verdict"])
        download = client.get(f"/runs/{run_id}/download")
        self.assertEqual(download.status_code, 200)
        names = zipfile.ZipFile(io.BytesIO(download.data)).namelist()
        self.assertTrue(any(n.endswith("_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx") for n in names), names)
        schedule = client.get(f"/runs/{run_id}/schedule")
        self.assertEqual((schedule.status_code, schedule.data), (200, b"schedule"))

    def test_failed_runner_exit_code_is_shown(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="FAILS.xlsx"))
        run = wait(store, run_id)
        self.assertEqual(run["exit_code"], 2)
        self.assertIn("Not approved", client.get(f"/runs/{run_id}").get_data(as_text=True))

    def test_two_runs_queue_and_both_finish(self):
        app, store, *_ = make_app()
        client = client_for(app)
        first = run_id_of(upload(client, name="SLOW1.xlsx"))
        second = run_id_of(upload(client, name="week43.xlsx"))
        time.sleep(0.8)
        self.assertEqual(store.get_run(second)["status"], "QUEUED")
        self.assertEqual(wait(store, first)["status"], "DONE")
        self.assertEqual(wait(store, second)["status"], "DONE")

    def test_stop_a_running_run(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="SLOW2.xlsx"))
        wait(store, run_id, {"RUNNING"})
        client.post(f"/runs/{run_id}/stop", data={"csrf_token": token(client)})
        self.assertEqual(wait(store, run_id)["status"], "STOPPED")


class RestartAndResume(unittest.TestCase):
    def test_restart_marks_running_as_interrupted(self):
        app, store, data, _ = make_app(start_worker=False)
        store.add_run("abc123abc123", 1, "week.xlsx", "QUICK", "RUNNING")
        create_app(dict(app.config, START_WORKER=False))
        self.assertEqual(store.get_run("abc123abc123")["status"], "INTERRUPTED")

    def test_resume_passes_resume_flag(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        store.update_run(run_id, status="INTERRUPTED")
        client.post(f"/runs/{run_id}/resume", data={"csrf_token": token(client)})
        wait(store, run_id)
        argv = json.loads((data / "runs" / run_id / "results" / "argv.json").read_text())
        self.assertIn("--resume", argv["flags"])


class TheSafetyGate(unittest.TestCase):
    def test_gate_runs_once_per_package_and_failure_blocks_runs(self):
        app, store, data, marker = make_app()
        client = client_for(app)
        for name in ("a.xlsx", "b.xlsx"):
            wait(store, run_id_of(upload(client, name=name)))
        self.assertEqual(marker.read_text(), "1")
        app2, store2, data2, marker2 = make_app(gate_fails=True)
        client2 = client_for(app2)
        run = wait(store2, run_id_of(upload(client2)))
        self.assertEqual(run["status"], "FAILED")
        self.assertIn("safety gate", run["message"].lower())

    def test_skip_guards_only_with_pass_stamp(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        argv = json.loads((data / "runs" / run_id / "results" / "argv.json").read_text())
        self.assertIn("--skip-guards", argv["flags"])
        stamp = next((data / "runs" / "_gate").glob("*.json"))
        self.assertEqual(json.loads(stamp.read_text())["status"], "PASS")


class Retention(unittest.TestCase):
    def test_runs_older_than_30_days_expire(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        queue = app.extensions["runs"]
        self.assertEqual(queue.cleanup(now=time.time() + 29 * 86400), 0)
        self.assertEqual(queue.cleanup(now=time.time() + 31 * 86400), 1)
        self.assertEqual(store.get_run(run_id)["status"], "EXPIRED")
        self.assertFalse((data / "runs" / run_id).exists())
        self.assertEqual(client.get(f"/runs/{run_id}/download").status_code, 404)


class Access(unittest.TestCase):
    def test_downloads_need_login(self):
        app, store, *_ = make_app()
        run_id = run_id_of(upload(client_for(app)))
        wait(store, run_id)
        anonymous = app.test_client()
        self.assertEqual(anonymous.get(f"/runs/{run_id}/download").status_code, 302)
        self.assertEqual(anonymous.get(f"/runs/{run_id}/schedule").status_code, 302)


class TheRunnerCommand(unittest.TestCase):
    def test_runner_command_matches_production_flags(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, mode="DEEP"))
        wait(store, run_id)
        argv = json.loads((data / "runs" / run_id / "results" / "argv.json").read_text())["argv"]
        joined = " ".join(argv)
        for needle in ("--package-root", "--results-root", "--mode DEEP", "--stage FULL_SCHEDULE",
                       "--num-workers", "--input", "--resume"):
            self.assertIn(needle, joined)
        self.assertNotIn("--seeds", joined)  # DEEP: the runner's own default (best of 4)
        quick = run_id_of(upload(client, name="q.xlsx", mode="QUICK"))
        wait(store, quick)
        quick_argv = json.loads((data / "runs" / quick / "results" / "argv.json").read_text())["argv"]
        self.assertIn("--seeds 2", " ".join(quick_argv))


if __name__ == "__main__":
    unittest.main()
