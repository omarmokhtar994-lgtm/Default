# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AB: the queue and the sender. A LOB's changes wait a short while so a burst goes as one post, changes undone
in that time are left out, nothing is sent in preview, a failed post is tried again after 1, 5 and 15 minutes, and
one LOB's trouble never stops another. A fake group records what it receives; a fake clock moves time."""
import http.server
import json
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from webapp.notify import PRIVATE, Notifier, post_json, reason_for, send_json
from webapp.store import Store

EGYPT = timezone(timedelta(hours=3))
UNIT, OTHER = "SAKS NMG Tier 2", "SAKS NMG Tier 9"
LABELS = {UNIT: "SAKS, NMG Tier 2", OTHER: "SAKS, NMG Tier 9"}
SLACK = "https://hooks.slack.com/services/T0000/B0000/abcdEFGHijkl"
SLACK_9 = "https://hooks.slack.com/services/T0000/B0009/zzzzYYYYxxxx"
DAY = "2026-10-10"
T0 = datetime(2026, 10, 10, 19, 0, tzinfo=EGYPT).timestamp()


def hm(epoch):
    return datetime.fromtimestamp(epoch, EGYPT).strftime("%H:%M")


class Group:
    """A fake group: records each (url, body) and answers from a script, then (True, 200)."""

    def __init__(self, answers=None, raises_for=()):
        self.calls, self.answers, self.raises_for = [], list(answers or []), raises_for

    def __call__(self, url, body):
        self.calls.append((url, body))
        if url in self.raises_for:
            raise RuntimeError("the network went away")
        return self.answers.pop(0) if self.answers else (True, 200)


class _Sender(unittest.TestCase):
    def setUp(self):
        self.store = Store(Path(tempfile.mkdtemp()) / "scheduler.db")
        self.now = T0
        self.group = Group()
        self.notifier = self.make()
        self.log = 100

    def make(self):
        return Notifier(self.store, transport=self.group, clock=lambda: self.now, label=LABELS.get)

    def settle(self, unit=UNIT, link=SLACK, mode="on", kinds="break,added_break,overtime,called_in,channel",
               hold=120):
        self.store.set_notify(unit, link=link, service="slack", mode=mode, kinds=kinds, hold=hold,
                              site="https://rta.example/")

    def queue(self, text="Lunch moved 12:15 to 12:45", kind="break", who="Associate 019", unit=UNIT, **extra):
        self.log += 1
        self.notifier.queue(self.log, unit, DAY, who, kind, text, "Omar Mokhtar", **extra)
        return self.log

    def items(self, **where):
        return self.store.notify_items(**where)


class TheQueue(_Sender):
    def test_off_keeps_nothing(self):
        self.queue()
        self.assertEqual(self.items(), [])
        self.settle(mode="off")
        self.queue()
        self.assertEqual(self.items(), [])

    def test_private_left_out_and_unticked_are_skipped(self):
        self.settle(kinds="break")
        sick = self.queue("Sick", kind=PRIVATE)
        out = self.queue(left_out=True)
        aux = self.queue("Coaching 14:00 to 14:30 (billable), with Lina", kind="aux")
        moved = self.queue()
        got = {i["log_id"]: (i["status"], i["reason"]) for i in self.items()}
        self.assertEqual(got[sick], ("skipped", "kept private"))
        self.assertEqual(got[out], ("skipped", "left out on the RTA"))
        self.assertEqual(got[aux], ("skipped", "not ticked for this LOB"))
        self.assertEqual(got[moved], ("waiting", ""))

    def test_undone_changes_are_not_posted(self):
        self.settle()
        ref = "break:Associate 019:2"
        a = self.queue("Lunch moved 12:15 to 12:45", ref=ref, before="12:15", after="12:45")
        b = self.queue("Lunch moved 12:45 to 13:00", ref=ref, before="12:45", after="13:00")
        kept = self.queue("Overtime 17:00 to 18:00", kind="overtime", who="Associate 008", ref="activity:7",
                          before="", after="on")
        c = self.queue("Lunch back to plan (12:15)", ref=ref, before="13:00", after="12:15")
        got = {i["log_id"]: (i["status"], i["reason"]) for i in self.items()}
        for log in (a, b, c):
            self.assertEqual(got[log], ("skipped", "undone before it was posted"))
        self.assertEqual(got[kept][0], "waiting")
        self.now += 130
        self.notifier.run_once()
        self.assertEqual(len(self.group.calls), 1)
        text = json.dumps(self.group.calls[0][1])
        self.assertIn("Overtime 17:00 to 18:00", text)
        self.assertNotIn("Lunch", text)


class TheSender(_Sender):
    def test_items_wait_for_the_hold_then_go_as_one_post(self):
        self.settle()
        self.queue()
        self.now += 60
        self.queue("Overtime 17:00 to 18:00", kind="overtime", who="Associate 008")
        self.assertEqual(self.notifier.run_once(T0 + 170), 0)
        self.assertEqual(self.group.calls, [])
        self.assertEqual(self.notifier.run_once(T0 + 180), 1)
        url, body = self.group.calls[0]
        self.assertEqual(url, SLACK)
        text = json.dumps(body)
        self.assertIn("SAKS, NMG Tier 2: changes for Sat 10 Oct", text)
        self.assertIn("Lunch moved 12:15 to 12:45", text)
        self.assertIn("Overtime 17:00 to 18:00", text)
        self.assertEqual({i["status"] for i in self.items()}, {"sent"})
        self.assertEqual([p["status"] for p in self.store.notify_posts(unit=UNIT)], ["sent"])
        self.assertEqual(self.notifier.run_once(T0 + 400), 0)  # sent once

    def test_a_busy_day_posts_after_ten_minutes(self):
        self.settle()
        for step in range(7):  # a change every 100 seconds: the hold never runs out
            self.now = T0 + 100 * step
            self.queue(f"Break 1 moved 10:{step:02d} to 10:30", who=f"Associate {step:03d}")
        self.assertEqual(self.notifier.run_once(T0 + 599), 0)
        self.assertEqual(self.notifier.run_once(T0 + 600), 1)
        self.assertEqual(json.dumps(self.group.calls[0][1]).count("Break 1 moved"), 7)

    def test_preview_sends_nothing(self):
        self.settle(mode="preview")
        self.queue()
        self.notifier.run_once(T0 + 200)
        self.assertEqual(self.group.calls, [])
        self.assertEqual({i["status"] for i in self.items()}, {"preview"})
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual(post["status"], "preview")
        self.assertIn("Lunch moved 12:15 to 12:45", post["body"])

    def test_failure_retries_then_fails(self):
        self.settle()
        self.group.answers = [(False, 500)] * 4
        self.queue()
        start = T0 + 120
        self.notifier.run_once(start)
        self.assertEqual(len(self.group.calls), 1)
        self.notifier.run_once(start + 59)
        self.assertEqual(len(self.group.calls), 1)
        for at, calls in ((start + 60, 2), (start + 360, 3), (start + 1260, 4)):
            self.notifier.run_once(at)
            self.assertEqual(len(self.group.calls), calls, at - start)
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual((post["status"], post["reason"]), ("failed", "Slack had a problem (500)"))
        self.assertEqual({(i["status"], i["reason"]) for i in self.items()}, {("failed", "Slack had a problem (500)")})
        self.notifier.run_once(start + 99999)
        self.assertEqual(len(self.group.calls), 4)

    def test_retry_then_success(self):
        self.settle()
        self.group.answers = [(False, 503)]
        self.queue()
        self.notifier.run_once(T0 + 120)
        self.notifier.run_once(T0 + 180)
        self.assertEqual(len(self.group.calls), 2)
        self.assertEqual(self.store.notify_posts(unit=UNIT)[0]["status"], "sent")

    def test_turning_off_stops_waiting_posts(self):
        self.settle()
        self.group.answers = [(False, 500)]
        self.queue()
        self.notifier.run_once(T0 + 120)
        self.settle(mode="off")
        self.notifier.run_once(T0 + 180)
        self.assertEqual(len(self.group.calls), 1)
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual((post["status"], post["reason"]), ("failed", "posting was turned off"))
        # a link removed while a post waits: not sent to the old group
        self.settle()
        self.group.answers = [(False, 500)]
        self.queue("Overtime 17:00 to 18:00", kind="overtime")
        self.notifier.run_once(T0 + 400)
        self.settle(link="")
        self.notifier.run_once(T0 + 500)
        self.assertEqual(len(self.group.calls), 2)
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual((post["status"], post["reason"]), ("failed", "the group link was removed"))

    def test_waiting_items_are_dropped_when_posting_is_turned_off(self):
        self.settle()
        self.queue()
        self.settle(mode="off")
        self.notifier.run_once(T0 + 200)
        self.assertEqual(self.group.calls, [])
        self.assertEqual({(i["status"], i["reason"]) for i in self.items()}, {("skipped", "posting was turned off")})

    def test_one_lob_failing_does_not_stop_another(self):
        self.settle()
        self.settle(unit=OTHER, link=SLACK_9)
        self.group.raises_for = (SLACK,)
        self.queue()
        self.queue("Overtime 17:00 to 18:00", kind="overtime", unit=OTHER)
        with self.assertLogs("webapp.notify", "ERROR"):
            self.notifier.run_once(T0 + 200)
        self.assertEqual(self.store.notify_posts(unit=OTHER)[0]["status"], "sent")
        self.assertEqual(self.store.notify_posts(unit=UNIT)[0]["status"], "waiting")

    def test_run_once_survives_a_transport_exception(self):
        self.settle()
        self.group.raises_for = (SLACK,)
        self.queue()
        with self.assertLogs("webapp.notify", "ERROR") as logged:
            self.assertEqual(self.notifier.run_once(T0 + 200), 1)
        self.assertIn("the network went away", "\n".join(logged.output))
        self.assertNotIn(SLACK, "\n".join(logged.output))  # the link never reaches the log
        post = self.store.notify_posts(unit=UNIT)[0]
        self.assertEqual((post["status"], post["tries"], post["reason"]), ("waiting", 1, "Slack could not be reached"))

    def test_an_rta_change_never_waits_for_a_slow_group(self):
        self.settle()
        self.queue()
        release, started = threading.Event(), threading.Event()

        def slow(url, body):
            started.set()
            release.wait(5)
            return True, 200
        self.notifier.transport = slow
        sender = threading.Thread(target=self.notifier.run_once, args=(T0 + 200,))
        sender.start()
        self.assertTrue(started.wait(5))
        took = time.monotonic()
        self.queue("Overtime 17:00 to 18:00", kind="overtime")
        took = time.monotonic() - took
        release.set()
        sender.join(5)
        self.assertLess(took, 1.0)

    def test_a_new_notifier_picks_up_waiting_items(self):
        self.settle()
        self.queue()
        again = self.make()  # the website restarted during the hold
        self.assertEqual(again.run_once(T0 + 200), 1)
        self.assertEqual(self.notifier.run_once(T0 + 300), 0)
        self.assertEqual(again.run_once(T0 + 400), 0)
        self.assertEqual(len(self.group.calls), 1)


class TheStatuses(_Sender):
    def test_statuses_for_the_rta(self):
        self.settle()
        moved = self.queue()
        sick = self.queue("Sick", kind=PRIVATE)
        got = self.notifier.statuses(UNIT, DAY)
        self.assertEqual(got[moved], {"state": "waiting", "text": f"Waiting: posts by {hm(T0 + 120)}"})
        self.assertEqual(got[sick], {"state": "skipped", "text": "Not posted: kept private"})
        self.group.answers = [(False, 429)]
        self.notifier.run_once(T0 + 120)
        self.assertEqual(self.notifier.statuses(UNIT, DAY)[moved],
                         {"state": "waiting", "text": f"Waiting: Slack did not take it, trying again at {hm(T0 + 180)}"})
        self.notifier.run_once(T0 + 180)
        self.assertEqual(self.notifier.statuses(UNIT, DAY)[moved],
                         {"state": "sent", "text": f"Posted to Slack, {hm(T0 + 180)}"})
        self.settle(mode="preview")
        late = self.queue()
        self.notifier.run_once(T0 + 400)
        self.assertEqual(self.notifier.statuses(UNIT, DAY)[late], {"state": "preview", "text": "Preview only: not sent"})
        self.assertEqual(self.notifier.statuses(UNIT, "2026-10-11"), {})

    def test_reason_texts(self):
        cases = {0: "Teams could not be reached", 400: "Teams refused the message (400)",
                 401: "Teams says this link may not post (401); replace the link",
                 403: "Teams says this link may not post (403); replace the link",
                 404: "Teams says the link no longer works (404); replace the link",
                 410: "Teams says the link no longer works (410); replace the link",
                 429: "Teams asked to slow down (429)", 502: "Teams had a problem (502)", 302: "Teams answered 302"}
        for code, text in cases.items():
            self.assertEqual(reason_for("teams", code), text)

    def test_old_items_go_with_the_day(self):
        self.settle()
        self.queue()
        self.notifier.run_once(T0 + 200)
        self.store.delete_day_before("2026-10-10")
        self.assertEqual(len(self.items()), 1)
        self.store.delete_day_before("2026-10-11")
        self.assertEqual(self.items(), [])
        self.assertEqual(self.store.notify_posts(), [])


class _Handler(http.server.BaseHTTPRequestHandler):
    hits = []

    def do_POST(self):  # noqa: N802 (the standard library's name)
        body = self.rfile.read(int(self.headers["Content-Length"]))
        _Handler.hits.append((self.path, self.headers["Content-Type"], body))
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/elsewhere")
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(2)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *args):
        pass


class TheTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_send_json_posts_json_and_follows_no_redirect(self):
        _Handler.hits.clear()
        self.assertEqual(send_json(self.base + "/ok", {"text": "hi"}), (True, 200))
        path, kind, body = _Handler.hits[-1]
        self.assertEqual((path, kind, json.loads(body)), ("/ok", "application/json", {"text": "hi"}))
        self.assertEqual(send_json(self.base + "/redirect", {}), (False, 302))
        self.assertNotIn("/elsewhere", [h[0] for h in _Handler.hits])
        self.assertEqual(send_json(self.base + "/slow", {}, timeout=0.5), (False, 0))
        self.assertEqual(send_json("http://127.0.0.1:1/closed", {}), (False, 0))

    def test_post_json_refuses_a_local_link(self):
        _Handler.hits.clear()
        with self.assertRaises(ValueError):
            post_json(self.base + "/ok", {})
        self.assertEqual(_Handler.hits, [])


if __name__ == "__main__":
    unittest.main()
