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


class TheWeekPage(unittest.TestCase):
    """Phase M task 2: one run's week, or a program's week, interval by interval."""

    def finished(self, **fields):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client, name="REAL_week.xlsx", **fields))
        wait(store, run_id)
        return app, store, client, run_id

    def page(self, client, url):
        response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return html.unescape(response.get_data(as_text=True))

    def test_week_view_for_a_run(self):
        app, store, client, run_id = self.finished()
        body = self.page(client, f"/runs/{run_id}/week")
        for text in ("Achieved every 30 minutes", "Where overtime is needed", "Extra hours available",
                     "107 of 126", "9.5 h", "24.5 h", "02:00 to 17:00"):
            self.assertIn(text, body)
        self.assertIn("125 of 126", self.page(client, f"/runs/{run_id}/week?side=before"))

    def test_week_view_by_program_and_week(self):
        app, store, client, run_id = self.finished(program="NMG", week_start="2026-10-11")
        body = self.page(client, "/week?program=NMG&week=2026-10-11")
        self.assertIn("NMG, week of 11 Oct", body)
        self.assertIn("107 of 126", body)
        self.assertIn('<option value="NMG" selected>', body)
        self.assertIn('<option value="2026-10-11" selected>', body)
        self.assertIn("107 of 126", self.page(client, "/week"))  # no choice yet: the latest program week

    def test_week_view_survives_file_expiry(self):
        app, store, client, run_id = self.finished()
        app.extensions["runs"].cleanup(now=time.time() + 31 * 86400)
        self.assertIn("107 of 126", self.page(client, f"/runs/{run_id}/week"))

    def test_older_runs_gain_intervals(self):
        app, store, client, run_id = self.finished()
        m = json.loads(store.get_run(run_id)["metrics"])
        self.assertIn("intervals", m)
        del m["intervals"]
        store.update_run(run_id, metrics=json.dumps(m))  # as a run finished before Phase M
        self.assertEqual(app.extensions["runs"].backfill(), 1)
        self.assertEqual(len(json.loads(store.get_run(run_id)["metrics"])["intervals"]), 126)  # intervals with demand

    def test_unknown_week_says_so(self):
        app, store, client, run_id = self.finished()
        self.assertIn("No finished run for this program and week", self.page(client, "/week?program=Nope&week=2026-10-11"))
        rejected = run_id_of(upload(client, name="bad.xlsx"))
        self.assertIn("No interval figures for this run", self.page(client, f"/runs/{rejected}/week"))

    def test_week_links_from_run_and_program_pages(self):
        app, store, client, run_id = self.finished(program="NMG", week_start="2026-10-11")
        self.assertIn(f'href="/runs/{run_id}/week"', self.page(client, f"/runs/{run_id}"))
        self.assertIn(f'href="/runs/{run_id}/week"', self.page(client, "/programs/NMG"))


REPO = Path(__file__).resolve().parents[2]
B3_INPUT = REPO / "fixtures" / "real_runs" / "week_boundary" / "B3_ARB2B_S30" / "input_snapshot" / "AE_AR_B2B_SLICE30.xlsx"


def versioned_run(app, store, client, **fields):
    """A finished run whose files are a real schedule week (fake runner, real workbooks)."""
    run_id = run_id_of(upload(client, name="VERSIONED_week.xlsx", data=B3_INPUT.read_bytes(), **fields))
    wait(store, run_id)
    end = time.time() + 60
    while time.time() < end and not app.extensions["schedules"].versions(run_id):
        time.sleep(0.2)
    return run_id


class TheKeptSchedules(unittest.TestCase):
    """Phase N task 2: a finished run's schedules are kept as versions."""

    def test_finished_run_keeps_its_schedules(self):
        app, store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        client = client_for(app)
        run_id = versioned_run(app, store, client, program="AE/AR B2B", week_start="2026-10-11")
        versions = app.extensions["schedules"].versions(run_id)
        self.assertEqual([(v["kind"], v["program"]) for v in versions], [("tool_after", "AE/AR B2B")])
        self.assertEqual(json.loads(versions[0]["checks"])["status"], "PASS")

    def test_a_finished_run_has_kept_its_schedules_already(self):
        # "finished" means the run's work is over: its versions are kept before the status says
        # so (a clean-up starting the moment a run reads finished must not race the copy)
        app, store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        client = client_for(app)
        run_id = run_id_of(upload(client, name="VERSIONED_week.xlsx", data=B3_INPUT.read_bytes()))
        wait(store, run_id)
        self.assertTrue(app.extensions["schedules"].versions(run_id))


class TheSchedulesPage(unittest.TestCase):
    """Phase N task 3: versions, edits with their warning, in use, downloads."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("lina", "Lina", "Lina-pass-12", must_change=False)
        cls.client = client_for(cls.app)
        cls.run_id = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-11")
        cls.tool = cls.app.extensions["schedules"].versions(cls.run_id)[0]["id"]

    def post(self, url, client=None, **data):
        client = client or self.client
        return client.post(url, data={"csrf_token": token(client), **data})

    def test_schedules_page_lists_versions_and_marks(self):
        body = html.unescape(self.client.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True))
        self.assertIn("AE/AR B2B, week of 11 Oct: schedules", body)
        self.assertIn("Tool, after breaks", body)
        self.assertIn('data-name="Associate 001" data-day="Wed" data-value="12:00 - 21:00"', body)
        self.assertIn('<option value="21:00 - 06:00">', body)
        draft = self.app.extensions["schedules"].change(self.tool, 1, "Associate 001", "Wed", "21:00 - 06:00", "swap")
        body = html.unescape(self.client.get(f"/runs/{self.run_id}/schedules?v={draft}").get_data(as_text=True))
        self.assertRegex(body, r'class="ed changed sev-red"[^>]*data-name="Associate 001" data-day="Wed"')
        self.assertIn('class="dot red"', body)
        self.assertIn("rests only 6 hours", body)
        self.assertIn("swap", body)  # the change log

    def test_check_returns_new_problems_only(self):
        got = self.post(f"/schedules/{self.tool}/check", associate="Associate 001", day="Wed", value="21:00 - 06:00").get_json()
        self.assertEqual(got["severity"], "red")
        self.assertEqual(len(got["added"]), 3)
        self.assertTrue(any("rests only 6 hours" in p["text"] for p in got["added"]))
        same = self.post(f"/schedules/{self.tool}/check", associate="Associate 001", day="Wed", value="12:00 - 21:00").get_json()
        self.assertEqual((same["severity"], same["added"]), ("ok", []))

    def test_change_needs_a_reason_when_it_breaks_rules(self):
        refused = self.post(f"/schedules/{self.tool}/change", associate="Associate 004", day="Wed", value="21:00 - 06:00")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("reason", refused.get_json()["error"])
        kept = self.post(f"/schedules/{self.tool}/change", associate="Associate 004", day="Wed", value="21:00 - 06:00",
                         reason="cover for a colleague").get_json()
        self.assertIn("/schedules?v=", kept["url"])
        self.assertNotEqual(kept["schedule_id"], self.tool)

    def test_slot_swap_checked_then_kept(self):
        body = html.unescape(self.client.get(f"/runs/{self.run_id}/schedules").get_data(as_text=True))
        self.assertIn("Slot 1 · English", body)
        got = self.post(f"/schedules/{self.tool}/swap-check", first="Associate 005", second="Associate 006").get_json()
        self.assertIn(got["severity"], ("ok", "yellow", "red"))
        refused = self.post(f"/schedules/{self.tool}/swap", first="Associate 005", second="Associate 005", reason="x")
        self.assertEqual(refused.status_code, 400)
        kept = self.post(f"/schedules/{self.tool}/swap", first="Associate 005", second="Associate 006",
                         reason="swap requested").get_json()
        week = json.loads(self.store.get_schedule(kept["schedule_id"])["week"])
        self.assertEqual([a["name"] for a in week["associates"] if a["slot"] in ("5", "6")],
                         ["Associate 006", "Associate 005"])
        page = html.unescape(self.client.get(kept["url"]).get_data(as_text=True))
        self.assertIn("Associate 005 moved from Slot 5 to Slot 6 (slot swap)", page)

    def test_in_use_only_for_owner_or_admin(self):
        other = self.app.test_client()
        tok = TOKEN.search(other.get("/login").get_data(as_text=True)).group(1)
        other.post("/login", data={"username": "lina", "password": "Lina-pass-12", "csrf_token": tok})
        self.assertEqual(self.post(f"/schedules/{self.tool}/in-use", client=other).status_code, 403)
        self.assertEqual(self.post(f"/schedules/{self.tool}/in-use").status_code, 302)
        self.assertEqual(self.app.extensions["schedules"].in_use("AE/AR B2B", "2026-10-11")["id"], self.tool)

    def test_download_a_version(self):
        tool = self.client.get(f"/schedules/{self.tool}/download")
        self.assertEqual((tool.status_code, tool.data[:2]), (200, b"PK"))
        draft = self.app.extensions["schedules"].change(self.tool, 1, "Associate 002", "Sun", "OFF", "leave")
        got = self.client.get(f"/schedules/{draft}/download")
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(got.data))
        self.assertEqual(book.sheetnames[0], "Version Notes")
        notes = [c for row in book["Version Notes"].iter_rows(values_only=True) for c in row if c]
        self.assertIn("Associate 002", " ".join(map(str, notes)))
        self.assertIn("attachment", got.headers["Content-Disposition"])

    def test_week_view_of_a_version(self):
        body = html.unescape(self.client.get(f"/schedules/{self.tool}/week").get_data(as_text=True))
        self.assertIn("Tool, after breaks", body)
        self.assertIn("Achieved every hour", body)  # this program's demand is hourly

    def test_links_to_the_schedules(self):
        self.assertIn(f'href="/runs/{self.run_id}/schedules"', self.client.get(f"/runs/{self.run_id}").get_data(as_text=True))


class TheDayPage(unittest.TestCase):
    """Phase N task 4: the day from the schedule in use, attendance and actual breaks."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.run_id = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-11")
        cls.url = "/day?program=AE/AR+B2B&date=2026-10-14"

    def post(self, url, **data):
        return self.client.post(url, data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                           "date": "2026-10-14", **data})

    def page(self):
        return html.unescape(self.client.get(self.url).get_data(as_text=True))

    def test_day_page_shows_lanes_rows_and_tiles(self):
        body = self.page()
        self.assertIn("AE/AR B2B, Wednesday 14 Oct: the day", body)
        self.assertIn("No version is marked in use for this week", body)
        self.assertIn('data-name="Associate 001" data-date="2026-10-14"', body)
        for row in ("Needed on the floor", "Planned on the floor", "On the floor now", "Plus / minus (hours)",
                    "English on the floor", "On shift today", "Short of demand"):
            self.assertIn(row, body)
        self.assertIn('href="/day"', body)  # the menu's Today

    def test_status_kept_or_refused_with_a_reason(self):
        refused = self.post("/day/attendance", associate="Associate 001", status="Late")
        self.assertEqual((refused.status_code, refused.get_json()["error"]), (400, "Give the time they arrived."))
        refused = self.post("/day/attendance", associate="Associate 001", status="Late", to="22:00")
        self.assertIn("outside Associate 001's shift", refused.get_json()["error"])
        self.assertEqual(self.post("/day/attendance", associate="Associate 001", status="Late", to="13:00").get_json(),
                         {"ok": True})
        body = self.page()
        self.assertRegex(body, r'<option value="Late" selected>Late</option>')
        self.assertIn("Late, arrived 13:00", body)  # the day's log

    def test_break_moved_or_refused(self):
        refused = self.post("/day/break", associate="Associate 008", idx="1", at="13:07")
        self.assertEqual(refused.status_code, 400)
        self.assertIn("5-minute steps", refused.get_json()["error"])
        self.assertEqual(self.post("/day/break", associate="Associate 008", idx="1", at="13:05").get_json(), {"ok": True})
        body = self.page()
        self.assertRegex(body, r'class="brk moved"[^>]*data-name="Associate 008"[^>]*data-idx="1"')
        self.assertIn("Lunch moved 12:30 to 13:05", body)
        self.assertEqual(self.post("/day/break", associate="Associate 008", idx="1", at="").get_json(), {"ok": True})
        self.assertIn("Lunch back to plan (12:30)", self.page())

    def test_bad_requests_answer_plainly(self):
        self.assertEqual(self.post("/day/break", associate="Associate 008", idx="x", at="13:05").status_code, 400)
        self.assertEqual(self.post("/day/attendance", associate="Nobody", status="Sick").status_code, 400)
        got = self.client.post("/day/attendance", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                        "date": "14-10-2026", "associate": "Associate 001",
                                                        "status": "Sick"})
        self.assertEqual((got.status_code, got.get_json()["error"]), (400, "Pick a day."))

    def test_measure_and_billable_aux(self):
        self.assertEqual(self.post("/day/attendance", associate="Associate 012", status="Coaching", **{"from": "10:00"},
                                   to="11:00", billable="1").get_json(), {"ok": True})
        body = self.page()
        self.assertIn("Coaching (billable) 10:00 to 11:00", body)
        self.assertRegex(body, r'<option value="interval" selected>Interval compliance</option>')
        self.assertIn('<option value="sl">Service level</option>', body)
        sl = html.unescape(self.client.get(self.url + "&measure=sl").get_data(as_text=True))
        self.assertRegex(sl, r'<option value="sl" selected>Service level</option>')
        self.assertEqual(self.client.get(self.url + "&measure=weekly").status_code, 200)  # unknown: the default

    def test_slot_ids_and_the_interval_board(self):
        body = self.page()
        self.assertIn("Slot 1", body)
        board = html.unescape(self.client.get(self.url + "&view=board").get_data(as_text=True))
        for column in ("Interval", "Needed", "On the floor", "Buffer (h:mm)", "Status", "Lunch", "Short breaks",
                       "Late, early, aux", "Unplanned leave", "Languages"):
            self.assertIn(column, board)
        self.assertRegex(board, r'class="chip[^"]*"[^>]*data-name="Associate 008"[^>]*data-idx="1"')

    def test_a_broken_day_says_why(self):
        from unittest import mock
        with mock.patch.object(self.app.extensions["days"], "page", side_effect=ValueError("The input is missing.")):
            got = self.client.get(self.url)
        self.assertEqual(got.status_code, 200)
        self.assertIn("The input is missing.", got.get_data(as_text=True))

    def test_adherence_tab(self):
        self.post("/day/attendance", associate="Associate 021", status="Late", to="08:40")
        body = html.unescape(self.client.get(self.url + "&view=adherence").get_data(as_text=True))
        for words in ("Team adherence", "Team conformance", "Late and early leave", "By person (lowest first)",
                      "Actual shrinkage against your input"):
            self.assertIn(words, body)
        self.assertRegex(body, r"Associate 021</b></td><td>08:00 - 17:00</td><td>Late</td>")
        self.assertIn("Adherence", body)  # the tab

    def test_find_a_time_and_book_it(self):
        url = (self.url + "&view=meeting&who=Associate+001&who=Associate+012&minutes=30&from=13:00&to=17:00"
               "&kind=Training&billable=1")
        body = html.unescape(self.client.get(url).get_data(as_text=True))
        self.assertIn("Find a time", body)
        starts = re.findall(r'name="start" value="(\d+)"', body)
        self.assertTrue(starts)
        got = self.client.post("/day/book", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                  "date": "2026-10-14", "who": ["Associate 001", "Associate 012"],
                                                  "start": starts[0], "minutes": "30", "kind": "Training", "billable": "1"})
        self.assertEqual(got.status_code, 303)
        page = self.page()
        self.assertRegex(page, r'class="tl-act aux billable"')
        self.assertIn("Associate 012, Training", page)
        again = self.client.post("/day/book", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                    "date": "2026-10-14", "who": ["Associate 001"], "start": starts[0],
                                                    "minutes": "30", "kind": "Meeting"}, follow_redirects=True)
        self.assertIn("Not free then: Associate 001. Nobody was booked.", html.unescape(again.get_data(as_text=True)))

    def test_overtime_and_vto_tab(self):
        body = html.unescape(self.client.get(self.url + "&view=cover").get_data(as_text=True))
        for words in ("Short: offer overtime", "Above demand: offer voluntary time off", "Activities on this day"):
            self.assertIn(words, body)
        got = self.client.post("/day/activity", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                      "date": "2026-10-14", "associate": "Associate 028",
                                                      "kind": "Overtime", "from": "07:00", "to": "09:00", "view": "cover"})
        self.assertEqual(got.status_code, 303)
        self.assertIn("view=cover", got.headers["Location"])
        body = html.unescape(self.client.get(self.url + "&view=cover").get_data(as_text=True))
        self.assertIn("Associate 028, Overtime 07:00 to 09:00", body)
        made = re.search(r'Associate 028, Overtime 07:00 to 09:00</b>\s*<form[^>]*>(?:<input[^>]*>)*?<input type="hidden" '
                         r'name="id" value="(\d+)"', body).group(1)
        self.client.post("/day/activity/cancel", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                       "date": "2026-10-14", "id": made, "view": "cover"})
        self.assertIn("Cancelled: Overtime 07:00 to 09:00", self.page())
        refused = self.client.post("/day/activity", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                          "date": "2026-10-14", "associate": "Associate 028",
                                                          "kind": "Overtime", "from": "10:00", "to": "11:00",
                                                          "view": "cover"}, follow_redirects=True)
        self.assertIn("Overtime has to start when", html.unescape(refused.get_data(as_text=True)))

    def test_autopilot_preview_and_apply(self):
        body = html.unescape(self.client.get(self.url + "&view=replan").get_data(as_text=True))
        for words in ("Fix the rest of the day's breaks", "Tightest interval", "Hours short"):
            self.assertIn(words, body)
        got = self.client.post("/day/replan/apply", data={"csrf_token": token(self.client), "program": "AE/AR B2B",
                                                          "date": "2026-10-14", "move": ["Associate 021|1|775"]})
        self.assertEqual(got.status_code, 303)
        self.assertIn("Lunch moved 12:30 to 12:55 (autopilot)", self.page())

    def test_week_without_a_schedule_and_defaults(self):
        body = html.unescape(self.client.get("/day?program=AE/AR+B2B&date=2026-11-04").get_data(as_text=True))
        self.assertIn("No schedule for AE/AR B2B in the week of 01 Nov", body)
        self.assertEqual(self.client.get("/day").status_code, 200)
        self.assertEqual(self.client.get("/day?date=not-a-date").status_code, 200)


class TheRecord(unittest.TestCase):
    """Phase O task 1: runs, downloads and people admin are recorded with who and when."""

    def events(self, store):
        return [(e["kind"], e["by_name"], e["subject"]) for e in store.list_events(0, time.time() + 60)]

    def test_upload_stop_resume_recorded(self):
        app, store, *_ = make_app(start_worker=False)
        client = client_for(app)
        run_id = run_id_of(upload(client, name="week42.xlsx"))
        client.post(f"/runs/{run_id}/stop", data={"csrf_token": token(client)})
        client.post(f"/runs/{run_id}/resume", data={"csrf_token": token(client)})
        self.assertEqual(self.events(store), [("run_uploaded", "Sara", "week42.xlsx"), ("run_stopped", "Sara", "week42.xlsx"),
                                              ("run_resumed", "Sara", "week42.xlsx")])
        self.assertEqual({e["run_id"] for e in store.list_events(0, time.time() + 60)}, {run_id})

    def test_downloads_recorded(self):
        app, store, *_ = make_app()
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        self.assertEqual(client.get(f"/runs/{run_id}/download").status_code, 200)
        kind, by, subject = self.events(store)[-1]
        self.assertEqual((kind, by), ("downloaded", "Sara"))
        self.assertTrue(subject.endswith(".zip"))

    def test_people_admin_recorded_without_passwords(self):
        app, store, *_ = make_app(start_worker=False)
        store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        client = app.test_client()
        tok = TOKEN.search(client.get("/login").get_data(as_text=True)).group(1)
        client.post("/login", data={"username": "omar", "password": "Owner-pass-123", "csrf_token": tok})
        client.post("/admin/users", data={"csrf_token": token(client), "username": "lina", "display_name": "Lina",
                                          "password": "Lina-temp-pass-1"})
        lina = next(u for u in store.list_users() if u["username"] == "lina")["id"]
        for action in ("disable", "enable", "reset"):
            client.post(f"/admin/users/{lina}/{action}", data={"csrf_token": token(client)})
        self.assertEqual(self.events(store), [("user_added", "Omar", "lina"), ("user_disabled", "Omar", "lina"),
                                              ("user_enabled", "Omar", "lina"), ("password_reset", "Omar", "lina")])
        everything = " ".join(str(v) for e in store.list_events(0, time.time() + 60) for v in e.values())
        self.assertNotIn("Lina-temp-pass-1", everything)

    def test_run_files_kept_30_to_60_days(self):
        from webapp import serve
        base = {"SCHEDULER_DATA_DIR": "/var/lib/scheduler"}
        self.assertEqual(serve.config_from_env(base)["RUN_FILES_DAYS"], 30)
        self.assertEqual(serve.config_from_env({**base, "SCHEDULER_RUN_FILES_DAYS": "60"})["RUN_FILES_DAYS"], 60)
        for bad in ("29", "61", "forever"):
            with self.assertRaises(SystemExit):
                serve.config_from_env({**base, "SCHEDULER_RUN_FILES_DAYS": bad})
        app, store, data, _ = make_app(RUN_FILES_DAYS=45)
        client = client_for(app)
        run_id = run_id_of(upload(client))
        wait(store, run_id)
        queue = app.extensions["runs"]
        self.assertEqual(queue.cleanup(now=time.time() + 44 * 86400), 0)
        self.assertEqual(queue.cleanup(now=time.time() + 46 * 86400), 1)


class TheExportsPage(unittest.TestCase):
    """Phase O task 2: the Exports page and its downloads."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.run_id = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-11")
        cls.client.post("/day/attendance", data={"csrf_token": token(cls.client), "program": "AE/AR B2B",
                                                 "date": "2026-10-14", "associate": "Associate 001", "status": "Sick"})

    def test_page_lists_the_period(self):
        body = html.unescape(self.client.get("/exports?from=2026-10-01&to=2026-10-31").get_data(as_text=True))
        for words in ("Exports", "What to export", "In this period", "Attendance", "Schedule changes and swaps",
                      "Worked hours and adherence", 'name="kind" value="attendance" checked', 'href="/exports"'):
            self.assertIn(words, body)
        self.assertRegex(body, r"<td>Attendance</td><td class=\"n\">1</td><td>Sara, ")

    def test_download_is_recorded(self):
        got = self.client.get("/exports/download?from=2026-10-14&to=2026-10-14&kind=attendance&kind=activity"
                              "&format=xlsx&measure=interval")
        self.assertEqual(got.status_code, 200)
        self.assertIn("attachment; filename=Team_Scheduler_2026-10-14_to_2026-10-14.xlsx",
                      got.headers["Content-Disposition"])
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(got.data))
        self.assertEqual(wb.sheetnames, ["About this export", "Attendance", "Day activity"])
        last = self.store.list_events(0, time.time() + 60, kinds=["exported"])[-1]
        self.assertEqual((last["by_name"], last["subject"]), ("Sara", "Team_Scheduler_2026-10-14_to_2026-10-14.xlsx"))

    def test_a_request_it_cannot_answer_says_why(self):
        got = self.client.get("/exports/download?from=2026-10-14&to=2026-10-01&kind=attendance&format=xlsx")
        self.assertEqual(got.status_code, 400)
        self.assertIn("The period ends before it starts.", got.get_data(as_text=True))
        got = self.client.get("/exports/download?from=2026-10-14&to=2026-10-14&kind=attendance&kind=runs&format=csv")
        self.assertIn("A CSV file holds one item", got.get_data(as_text=True))

    def test_signed_out_cannot_export(self):
        got = self.app.test_client().get("/exports/download?from=2026-10-14&to=2026-10-14&kind=attendance")
        self.assertEqual(got.status_code, 302)
        self.assertIn("/login", got.headers["Location"])


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
