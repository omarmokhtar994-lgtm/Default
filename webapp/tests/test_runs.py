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
FINAL = {"DONE", "REVIEW", "FAILED", "REJECTED", "INTERRUPTED", "STOPPED", "EXPIRED"}


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


def upload(client, name="week42.xlsx", data=b"PK\x03\x04 fake workbook", mode="QUICK", **fields):
    return client.post("/runs", data={"csrf_token": token(client), "mode": mode,
                                      "workbook": (io.BytesIO(data), name), **fields},
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

    def test_review_required_verdict_is_never_shown_as_approved(self):
        # The runner exits 0 for RELEASABLE and for REVIEW_REQUIRED (only
        # NOT_RELEASABLE fails it), so the run's label follows the verdict.
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REVIEW_week.xlsx"))
        run = wait(store, run_id, FINAL | {"REVIEW"})
        self.assertEqual((run["status"], run["exit_code"]), ("REVIEW", 0))
        page = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("Needs review", page)
        self.assertNotIn(">Approved<", page)
        self.assertIn("REVIEW_REQUIRED", page)
        self.assertEqual(client.get(f"/runs/{run_id}/schedule").status_code, 200)
        self.assertIn("Needs review", client.get("/").get_data(as_text=True))

    def test_readiness_check_says_ready_not_approved(self):
        app, store, *_ = make_app()
        client = client_for(app)
        # Re-pinned in Phase L: a readiness check is judged by the engine's own
        # outcome (DIAGNOSTICS_ONLY_COMPLETE), because the real runner exits 2
        # for every readiness check (its release scoring fails a run that builds
        # no schedule; owner: "smoke showing not approved regularly"). The fake
        # writes that outcome for READY workbooks; the word is the approved
        # sample's "Ready to run".
        run_id = run_id_of(upload(client, name="READY_week.xlsx", mode="SMOKE"))
        run = wait(store, run_id)
        self.assertEqual(run["status"], "DONE")
        page = client.get(f"/runs/{run_id}").get_data(as_text=True)
        self.assertIn(">Ready to run<", page)
        self.assertNotIn(">Approved<", page)

    def test_summary_saved_when_a_run_finishes(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx"))
        wait(store, run_id)
        saved = json.loads((data / "runs" / run_id / "summary.json").read_text())
        self.assertEqual(saved["numbers"]["fully_covered"], 107)
        self.assertEqual(app.extensions["runs"].summary(run_id)["staffing"]["roster"], 7)
        plain = run_id_of(upload(client, name="week44.xlsx"))
        wait(store, plain)
        self.assertIsNone(app.extensions["runs"].summary(plain))

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


class TheVerdictLabel(unittest.TestCase):
    def test_label_reads_the_verdict_word_not_its_note(self):
        from webapp.runs import outcome
        self.assertEqual(outcome("QUICK", "RELEASE VERDICT (run): RELEASABLE - gate 5: none configured")[0], "DONE")
        self.assertEqual(outcome("QUICK", "RELEASE VERDICT (run): REVIEW_REQUIRED - gate 5 behind")[0], "REVIEW")
        self.assertEqual(outcome("QUICK", "no verdict line")[0], "REVIEW")


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


class TheControlRoomPages(unittest.TestCase):
    """Phase J task 2 (server side): what the redesigned pages say."""

    def test_run_page_shows_the_week_wall_and_numbers(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx"))
        wait(store, run_id)
        page = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertEqual(page.count('class="cell '), 2 * 126)  # after and before breaks, same places
        self.assertIn("107 of 126 half-hours fully covered", page)
        self.assertIn("Fri 21:30: 2 people on break at the same time", page)
        self.assertIn("about 73 spare productive hours", page)
        self.assertIn("Tue 20:30", page)

    def test_run_without_validation_says_why(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        page = client.get(f"/runs/{run_id}").get_data(as_text=True)
        self.assertNotIn('class="cell ', page)
        self.assertIn("No coverage data for this run", page)

    def test_technical_details_are_folded(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="FAILS.xlsx"))
        wait(store, run_id)
        page = client.get(f"/runs/{run_id}").get_data(as_text=True)
        self.assertRegex(page, r'<details class="tech">')
        self.assertIn("Not approved", page)

    def test_queue_position_and_start_estimate_are_shown(self):
        app, store, *_ = make_app()
        client = client_for(app)
        first = run_id_of(upload(client, name="SLOW_a.xlsx"))
        wait(store, first, {"RUNNING"})
        second = run_id_of(upload(client, name="week45.xlsx"))
        page = client.get(f"/runs/{second}").get_data(as_text=True)
        self.assertIn("1 run ahead of you", page)
        self.assertIn("Starts in about", page)
        self.assertIn("Egypt time", page)
        board = client.get("/").get_data(as_text=True)
        self.assertIn("1 waiting", board)
        wait(store, second)

    def test_dashboard_shows_the_latest_wall(self):
        app, store, *_ = make_app()
        client = client_for(app)
        wait(store, run_id_of(upload(client, name="REAL_week.xlsx")))
        board = html.unescape(client.get("/").get_data(as_text=True))
        self.assertIn("Latest schedule", board)
        self.assertEqual(board.count('class="cell '), 126)
        self.assertIn("85%", board)  # 107 of 126 fully covered

    def test_server_error_page_is_friendly(self):
        app, store, *_ = make_app(start_worker=False)

        def boom():
            raise RuntimeError("unexpected")
        app.add_url_rule("/boom", "boom", boom)
        app.testing = False
        app.config["PROPAGATE_EXCEPTIONS"] = False
        response = client_for(app).get("/boom")
        self.assertEqual(response.status_code, 500)
        self.assertIn("Something went wrong on our side. Your runs are safe. Tell your admin.",
                      html.unescape(response.get_data(as_text=True)))


class TheAdvancedOptions(unittest.TestCase):
    """Phase J task 6: the Colab notebook's settings, folded under the mode."""

    def argv(self, data, run_id):
        return " ".join(json.loads((data / "runs" / run_id / "results" / "argv.json").read_text())["argv"])

    def test_advanced_options_reach_the_runner(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, mode="OVERNIGHT", language_window="ALL_ROWS",
                                  coverage_measure="VOLUME_WEIGHTED", stage="BEFORE_BREAKS_ONLY"))
        wait(store, run_id)
        argv = self.argv(data, run_id)
        for needle in ("--mode OVERNIGHT", "--language-working-window ALL_ROWS",
                       "--coverage-objective-weighting VOLUME_WEIGHTED", "--stage BEFORE_BREAKS_ONLY"):
            self.assertIn(needle, argv)
        page = client.get(f"/runs/{run_id}").get_data(as_text=True)
        self.assertIn("All rows", page)

    def test_follow_the_workbook_adds_no_flags(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, language_window="workbook", coverage_measure="workbook"))
        wait(store, run_id)
        argv = self.argv(data, run_id)
        self.assertNotIn("--language-working-window", argv)
        self.assertNotIn("--coverage-objective-weighting", argv)
        self.assertIn("--stage FULL_SCHEDULE", argv)

    def test_unknown_option_values_are_refused(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        upload(client, language_window="EVERYTHING")
        self.assertEqual(store.list_runs(), [])
        self.assertIn("Choose one of the listed options", client.get("/").get_data(as_text=True))

    def test_old_database_gains_the_options_column(self):
        import sqlite3
        data = Path(tempfile.mkdtemp())
        db = sqlite3.connect(data / "scheduler.db")
        db.executescript("""create table users (id integer primary key, username text unique not null,
            display_name text not null, password_hash text not null, is_admin integer not null default 0,
            active integer not null default 1, must_change integer not null default 1,
            failed integer not null default 0, locked_until real not null default 0, created real not null);
            create table runs (id text primary key, user_id integer not null, workbook text not null,
            mode text not null, status text not null, message text not null default '', exit_code integer,
            verdict text not null default '', created real not null, started real, finished real,
            resume integer not null default 0);
            insert into users values (1,'sara','Sara','x',0,1,0,0,0,0);
            insert into runs (id,user_id,workbook,mode,status,created) values ('abcabcabcabc',1,'w.xlsx','QUICK','DONE',0);""")
        db.commit()
        db.close()
        run = Store(data / "scheduler.db").get_run("abcabcabcabc")
        self.assertEqual(run["options"], "")


class TheProgramTags(unittest.TestCase):
    """Phase K task 2: program and week on every run; figures kept after the files expire."""

    def test_upload_records_program_and_week(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        run_id = run_id_of(upload(client, program="NMG Spanish", week_start="2026-10-11"))
        run = store.get_run(run_id)
        self.assertEqual((run["program"], run["week_start"]), ("NMG Spanish", "2026-10-11"))

    def test_week_must_be_a_date(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        upload(client, program="NMG", week_start="next week")
        self.assertEqual(store.list_runs(), [])

    def test_metrics_saved_when_a_run_finishes(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx", program="NMG", week_start="2026-10-11"))
        wait(store, run_id)
        m = json.loads(store.get_run(run_id)["metrics"])
        self.assertEqual((m["associates"], m["fully_covered"], m["active"]), (7, 107, 126))
        self.assertEqual(m["outcome"], "DONE")  # kept with the figures: the status is lost on expiry

    def test_history_survives_file_expiry(self):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx", program="NMG", week_start="2026-10-11"))
        wait(store, run_id)
        app.extensions["runs"].cleanup(now=time.time() + 31 * 86400)
        run = store.get_run(run_id)
        self.assertEqual(run["status"], "EXPIRED")
        self.assertEqual(json.loads(run["metrics"])["fully_covered"], 107)

    def test_runs_finished_before_the_update_join_the_history(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx"))
        wait(store, run_id)
        store.update_run(run_id, metrics="")  # as a run finished before program history existed
        self.assertEqual(app.extensions["runs"].backfill(), 1)
        m = json.loads(store.get_run(run_id)["metrics"])
        self.assertEqual((m["fully_covered"], m["outcome"]), (107, "DONE"))
        self.assertEqual(app.extensions["runs"].backfill(), 0)  # once only

    def test_untagged_runs_can_be_tagged(self):
        app, store, *_ = make_app(start_worker=False)
        store.add_user("lina", "Lina", "Lina-pass-12", must_change=False)
        client = client_for(app)
        run_id = run_id_of(upload(client))
        other = app.test_client()
        tok = TOKEN.search(other.get("/login").get_data(as_text=True)).group(1)
        other.post("/login", data={"username": "lina", "password": "Lina-pass-12", "csrf_token": tok})
        refused = other.post(f"/runs/{run_id}/tag", data={"csrf_token": token(other), "program": "X",
                                                          "week_start": "2026-10-11"})
        self.assertEqual(refused.status_code, 403)
        client.post(f"/runs/{run_id}/tag", data={"csrf_token": token(client), "program": "NMG",
                                                 "week_start": "2026-10-11"})
        run = store.get_run(run_id)
        self.assertEqual((run["program"], run["week_start"]), ("NMG", "2026-10-11"))

    def test_old_database_gains_analytics_columns(self):
        import sqlite3
        data = Path(tempfile.mkdtemp())
        db = sqlite3.connect(data / "scheduler.db")
        db.executescript("""create table users (id integer primary key, username text unique not null,
            display_name text not null, password_hash text not null, is_admin integer not null default 0,
            active integer not null default 1, must_change integer not null default 1,
            failed integer not null default 0, locked_until real not null default 0, created real not null);
            create table runs (id text primary key, user_id integer not null, workbook text not null,
            mode text not null, status text not null, message text not null default '', exit_code integer,
            verdict text not null default '', created real not null, started real, finished real,
            resume integer not null default 0, options text not null default '');
            insert into users values (1,'sara','Sara','x',0,1,0,0,0,0);
            insert into runs (id,user_id,workbook,mode,status,created) values ('abcabcabcabc',1,'w.xlsx','QUICK','DONE',0);""")
        db.commit()
        db.close()
        run = Store(data / "scheduler.db").get_run("abcabcabcabc")
        self.assertEqual((run["program"], run["week_start"], run["metrics"]), ("", "", ""))


def seed_week(store, program, week, outcome="DONE", by=1, n=[0], **changes):
    """A finished run with stored figures, as a run of the real Phase I workbook would leave."""
    from webapp.results import metrics, summarize
    m = metrics(summarize(Path(__file__).with_name("fixtures") / "real_run"))
    m.update(changes, outcome=outcome)
    n[0] += 1
    run_id = f"{n[0]:012x}"
    store.add_run(run_id, by, f"{program}_{week}.xlsx", "QUICK", outcome, program=program, week_start=week)
    store.update_run(run_id, metrics=json.dumps(m), started=time.time() - 3600, finished=time.time())
    return run_id


class TheAnalyticsPages(unittest.TestCase):
    """Phase K task 5: programs, one program's history, the team."""

    def setUp(self):
        self.app, self.store, *_ = make_app(start_worker=False)
        self.client = client_for(self.app)
        seed_week(self.store, "NMG", "2026-09-27", associates=8, fully_covered=100)
        seed_week(self.store, "NMG", "2026-10-04", associates=8, fully_covered=102)
        seed_week(self.store, "NMG", "2026-10-11")  # the real run: 7 associates, 107 of 126
        seed_week(self.store, "AE/AR <B2B>", "2026-10-11", outcome="REVIEW", associates=12)

    def page(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return html.unescape(response.get_data(as_text=True))

    def test_programs_page_lists_programs_with_latest_figures(self):
        body = self.page("/programs")
        self.assertIn("NMG", body)
        self.assertIn("3 weeks", body)
        self.assertIn("85%", body)  # 107 of 126 after breaks, the latest NMG week
        self.assertRegex(body, r"7\s*<[^>]*>\s*down 1")  # associates with the change from last week

    def test_program_page_shows_history_insights_and_suggestions(self):
        body = self.page("/programs/NMG")
        self.assertIn("Associates: 7 this week, down 1 from 8 in the week of 04 Oct.", body)
        self.assertIn("Fully covered before breaks: 99%, so breaks cost 14 points this week.", body)
        self.assertIn("at 90% it is met in 96%", body)
        for chart in ("Associates per week", "Coverage before and after breaks", "Hours available and needed",
                      "What stops 100%", "If the interval target were lower", "Hours that keep coming up short"):
            self.assertIn(chart, body)
        self.assertEqual(body.count('<details class="tableview">'), 6)
        self.assertIn("2026-10-11", body)  # the week-by-week table

    def test_program_weeks_filter_limits_the_history(self):
        body = self.page("/programs/NMG?weeks=2")
        self.assertNotIn("27 Sep", body)
        self.assertIn("04 Oct", body)

    def test_program_names_are_escaped_and_url_safe(self):
        raw = self.client.get("/programs").get_data(as_text=True)
        self.assertNotIn("<B2B>", raw)
        self.assertIn("/programs/AE/AR%20%3CB2B%3E", raw)
        self.assertIn("12", self.page("/programs/AE/AR%20%3CB2B%3E"))
        self.assertEqual(self.client.get("/programs/Nothing").status_code, 404)

    def test_team_page(self):
        body = self.page("/team")
        self.assertIn("Sara", body)
        self.assertRegex(body, r"Sara</td>\s*<td>4</td>")

    def test_analytics_need_login(self):
        anonymous = self.app.test_client()
        for url in ("/programs", "/programs/NMG", "/team"):
            self.assertEqual(anonymous.get(url).status_code, 302, url)

    def test_upload_form_offers_program_and_week(self):
        body = self.page("/")
        self.assertIn('name="program"', body)
        self.assertIn('<option value="NMG">', body)
        self.assertIn('name="week_start" type="date"', body)

    def test_run_page_lets_the_owner_tag_the_run(self):
        run_id = seed_week(self.store, "", "")
        self.assertIn(f'action="/runs/{run_id}/tag"', self.page(f"/runs/{run_id}"))


class TheThemes(unittest.TestCase):
    """Phase L: light or dark, the person's choice; the system's choice until they pick."""

    def test_theme_cookie_sets_the_page_theme(self):
        app, *_ = make_app(start_worker=False)
        client = client_for(app)
        self.assertNotIn("data-theme=", client.get("/").get_data(as_text=True).split(">", 2)[1])
        response = client.post("/theme", data={"csrf_token": token(client), "theme": "light", "next": "/programs"})
        self.assertEqual(response.headers["Location"], "/programs")
        self.assertIn("theme=light", response.headers["Set-Cookie"])
        self.assertIn('<html lang="en" data-theme="light">', client.get("/").get_data(as_text=True))
        client.post("/theme", data={"csrf_token": token(client), "theme": "system"})
        self.assertIn('<html lang="en">', client.get("/").get_data(as_text=True))

    def test_theme_toggle_needs_csrf(self):
        app, *_ = make_app(start_worker=False)
        client = client_for(app)
        self.assertEqual(client.post("/theme", data={"theme": "light"}).status_code, 400)

    def test_theme_only_returns_to_this_site(self):
        app, *_ = make_app(start_worker=False)
        client = client_for(app)
        response = client.post("/theme", data={"csrf_token": token(client), "theme": "dark",
                                                "next": "https://evil.example/"})
        self.assertEqual(response.headers["Location"], "/")

    def test_sign_in_page_follows_the_theme_too(self):
        app, *_ = make_app(start_worker=False)
        client = app.test_client()
        client.set_cookie("theme", "light")
        self.assertIn('data-theme="light"', client.get("/login").get_data(as_text=True))


class TheEngineOutcome(unittest.TestCase):
    """Phase L task 1: why a run stopped and what to change, on its own page."""

    def test_failed_run_page_shows_why_and_what_to_change(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="CONFLICT_week.xlsx"))
        run = wait(store, run_id)
        self.assertEqual(run["status"], "FAILED")
        self.assertEqual(run["message"], "No schedule satisfies all hard rules together")
        body = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("Can't be scheduled", body)
        self.assertIn("Why it stopped", body)
        self.assertIn("What to change in the input workbook", body)
        self.assertIn("widen that language's Coverage Start/End in Language Setup", body)
        self.assertIn("Associate 1 (English)", body)
        self.assertIn("Mon to Thu", body)
        self.assertNotIn("tools/check_input_workbook.py", body.split("Technical details")[0])
        self.assertNotIn('action="/runs/%s/resume"' % run_id, body)  # the same file would fail the same way
        self.assertIn("Upload the corrected workbook", body)

    def test_outcome_survives_file_expiry(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="CONFLICT_week.xlsx"))
        wait(store, run_id)
        app.extensions["runs"].cleanup(now=time.time() + 31 * 86400)
        self.assertEqual(json.loads(store.get_run(run_id)["engine_outcome"])["headline"],
                         "No schedule satisfies all hard rules together")
        self.assertIn("No schedule satisfies all hard rules together",
                      html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True)))

    def test_shortfall_schedule_offered_for_review(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="SHORTFALL_week.xlsx"))
        wait(store, run_id)
        body = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("Sun 03:00: Nobody on the floor after breaks, needs 1, short by 1", body)
        self.assertIn("Download the shortfall schedule (for review)", body)
        self.assertNotIn(">Download the schedule<", body)
        got = client.get(f"/runs/{run_id}/shortfall")
        self.assertEqual(got.data, b"shortfall")

    def test_crash_without_outcome_keeps_resume(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="FAILS_week.xlsx"))
        run = wait(store, run_id)
        self.assertEqual(run["status"], "FAILED")
        body = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn("Not approved", body)
        self.assertIn("the engine wrote no outcome", body)
        self.assertIn(f'action="/runs/{run_id}/resume"', body)


class TheReadinessCheck(unittest.TestCase):
    """Phase L task 2: a readiness check says Ready to run or Not ready (never
    Not approved), and a ready one starts the real run from the same workbook."""

    def ready_run(self, **fields):
        app, store, data, _ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="READY_week.xlsx", mode="SMOKE", **fields))
        wait(store, run_id)
        return app, store, client, run_id

    def test_readiness_judged_by_engine_outcome(self):
        app, store, client, run_id = self.ready_run()
        run = store.get_run(run_id)
        self.assertEqual((run["status"], run["exit_code"]), ("DONE", 2))  # the runner's 2 is its release scoring
        self.assertIn(">Ready to run<", client.get(f"/runs/{run_id}").get_data(as_text=True))

    def test_readiness_not_ready_shows_reason(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="NOTREADY_week.xlsx", mode="SMOKE"))
        run = wait(store, run_id)
        self.assertEqual(run["status"], "FAILED")
        body = html.unescape(client.get(f"/runs/{run_id}").get_data(as_text=True))
        self.assertIn(">Not ready<", body)
        self.assertIn("Why it is not ready", body)
        self.assertNotIn("/resume", body)

    def test_readiness_without_an_outcome_is_not_ready(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="plain_week.xlsx", mode="SMOKE"))
        self.assertEqual(wait(store, run_id)["status"], "FAILED")  # fail closed: no outcome, no "ready"

    def test_readiness_page_offers_start_not_resume(self):
        app, store, client, run_id = self.ready_run()
        body = client.get(f"/runs/{run_id}").get_data(as_text=True)
        self.assertIn(f'action="/runs/{run_id}/start"', body)
        for mode in ("QUICK", "DEEP", "OVERNIGHT"):
            self.assertIn(f'name="mode" value="{mode}"', body)
        self.assertIn("Start the run", body)
        self.assertNotIn("/resume", body)

    def test_old_readiness_checks_are_read_again_at_startup(self):
        """Checks finished under the old rule (runner exit code) read "Not approved";
        their engine outcome is read again when the website starts."""
        app, store, client, run_id = self.ready_run()
        store.update_run(run_id, status="FAILED", engine_outcome="",
                         message="Not approved: the runner exited with code 2.")  # as the old rule left it
        not_ready = run_id_of(upload(client, name="NOTREADY_old.xlsx", mode="SMOKE"))
        wait(store, not_ready)
        store.update_run(not_ready, engine_outcome="")
        self.assertEqual(app.extensions["runs"].backfill_outcomes(), 2)
        run = store.get_run(run_id)
        self.assertEqual(run["status"], "DONE")
        self.assertTrue(run["message"].startswith("Ready to run"))
        self.assertEqual(store.get_run(not_ready)["status"], "FAILED")
        self.assertEqual(json.loads(store.get_run(not_ready)["engine_outcome"])["code"], "HARD_RULE_COMBINATION_INFEASIBLE")
        self.assertEqual(app.extensions["runs"].backfill_outcomes(), 0)  # once only

    def test_start_from_readiness_queues_the_same_workbook(self):
        app, store, client, run_id = self.ready_run(program="NMG", week_start="2026-10-11", language_window="ALL_ROWS")
        response = client.post(f"/runs/{run_id}/start", data={"csrf_token": token(client), "mode": "QUICK"})
        new_id = run_id_of(response)
        self.assertNotEqual(new_id, run_id)
        new, old = store.get_run(new_id), store.get_run(run_id)
        self.assertEqual((new["mode"], new["program"], new["week_start"], new["options"], new["workbook"]),
                         ("QUICK", "NMG", "2026-10-11", old["options"], "READY_week.xlsx"))
        queue = app.extensions["runs"]
        self.assertEqual(queue.input_path(new_id).read_bytes(), queue.input_path(run_id).read_bytes())

    def test_start_takes_only_a_real_run_mode(self):
        app, store, client, run_id = self.ready_run()
        before = len(store.list_runs())
        client.post(f"/runs/{run_id}/start", data={"csrf_token": token(client), "mode": "SMOKE_OR_WHATEVER"})
        self.assertEqual(len(store.list_runs()), before)

    def test_start_needs_the_input(self):
        app, store, client, run_id = self.ready_run()
        import shutil
        shutil.rmtree(app.extensions["runs"].input_path(run_id).parent)
        before = len(store.list_runs())
        response = client.post(f"/runs/{run_id}/start", data={"csrf_token": token(client), "mode": "QUICK"},
                               follow_redirects=True)
        self.assertEqual(len(store.list_runs()), before)
        self.assertIn("The workbook of this check is no longer on the server", html.unescape(response.get_data(as_text=True)))

    def test_corrected_upload_link_prefills_program_and_week(self):
        app, *_ = make_app(start_worker=False)
        client = client_for(app)
        body = client.get("/?program=NMG%20Spanish&week=2026-10-11").get_data(as_text=True)
        self.assertIn('name="program" type="text" list="known-programs" maxlength="80" autocomplete="off" '
                      'placeholder="For example NMG Spanish" value="NMG Spanish"', body)
        self.assertIn('name="week_start" type="date" value="2026-10-11"', body)


class TheWayAround(unittest.TestCase):
    """Phase L task 3: Back and Home on every page but home."""

    def test_every_page_has_back_and_home(self):
        app, store, *_ = make_app(start_worker=False)
        store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        client = app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        client.post("/login", data={"username": "omar", "password": "Owner-pass-123", "csrf_token": tok})
        run_id = seed_week(store, "NMG", "2026-10-11")
        parents = {f"/runs/{run_id}": "/", "/programs/NMG": "/programs", "/programs": "/", "/team": "/",
                   "/admin/users": "/", "/account/password": "/"}
        for url, parent in parents.items():
            body = client.get(url).get_data(as_text=True)
            self.assertIn(f'<a href="{parent}" data-back>', body, url)
            self.assertIn('<a class="home" href="/">Home</a>', body, url)
        home = client.get("/").get_data(as_text=True)
        self.assertNotIn("data-back", home)
        self.assertIn('<a href="/">Home</a>', home)  # the menu's first item


class TheCleanWorkbooks(unittest.TestCase):
    """Phase L task 4: a blank and an example input workbook, from the home page."""

    def test_only_the_two_workbooks_download(self):
        app, *_ = make_app(start_worker=False)
        client = client_for(app)
        home = client.get("/").get_data(as_text=True)
        for name in ("Scheduler_Input_Blank.xlsx", "Scheduler_Input_Example.xlsx"):
            self.assertIn(f'href="/workbooks/{name}"', home)
            got = client.get(f"/workbooks/{name}")
            self.assertEqual((got.status_code, got.data[:2]), (200, b"PK"), name)
            self.assertIn("attachment", got.headers["Content-Disposition"])
        for bad in ("other.xlsx", "..%2Fapp.py", "Scheduler_Input_Blank.xlsx.bak"):
            self.assertEqual(client.get(f"/workbooks/{bad}").status_code, 404, bad)
        self.assertEqual(app.test_client().get("/workbooks/Scheduler_Input_Blank.xlsx").status_code, 302)


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
