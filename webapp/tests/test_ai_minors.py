# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15: "no other bugs or something we agreed on and missed"): the minors left from Phase AG.

- A leave request left "applying" by a server stopped during the RTA's approval was stuck: it goes back to the RTA
  when the website starts, and approving it again finishes it (days already Leave are not changed twice).
- A leave over two weeks, each with its schedule kept, changes each week's schedule.
- My week's swap finder says why nobody is listed when you asked for leave that day, or do not work it.
Made-up "Associate NN" data.
"""
import re
import unittest
from datetime import timedelta

from webapp.leave import LeaveBook
from webapp.tests.test_ag_leave import THU, TUE, WED


class _Leave(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_ag_leave
        test_ag_leave.Leave.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_ag_leave
        test_ag_leave.Leave.tearDownClass.__func__(cls)


class AStoppedApproval(_Leave):
    def test_goes_back_to_the_rta_and_finishes(self):
        rid = self.book.ask(self.key, "Associate 007", self.omar, "Planned leave", WED, WED, "", today=TUE)
        self.book.decide(rid, self.users["tm1"], approve=True)
        self.store.move_leave(rid, "waiting_rta", status="applying", rta_id=self.users["rta1"]["id"], rta_at=1.0)
        self.assertEqual(LeaveBook(self.store, self.app.extensions["days"]).recover(), 1)
        row = self.store.get_leave(rid)
        self.assertEqual((row["status"], row["rta_id"]), ("waiting_rta", None))
        said = self.book.decide(rid, self.users["rta2"], approve=True)
        self.assertTrue(said.startswith("Approved: Leave on Wed 14 Oct."), said)


class TwoWeeks(_Leave):
    def test_each_weeks_schedule_changes(self):
        import io
        from datetime import date
        from webapp.tests.test_runs import wait
        sat, tue = date(2026, 10, 17), date(2026, 10, 20)
        self.admin.post("/runs", data={"csrf_token": self.token(self.admin), "kind": "ready", "mode": "QUICK",
                                       "program": self.key, "week_start": "2026-10-18",
                                       "workbook": (io.BytesIO((self.dir / "upload.xlsx").read_bytes()), "next.xlsx")},
                        content_type="multipart/form-data")
        wait(self.store, self.store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
        days = self.app.extensions["days"]
        before = {d: days.version(self.key, d)[0]["id"] for d in (sat, tue)}
        rid = self.book.ask(self.key, "Associate 012", self.omar, "Planned leave", sat, tue, "", today=TUE)
        self.book.decide(rid, self.users["tm1"], approve=True)
        said = self.book.decide(rid, self.users["rta1"], approve=True)
        self.assertEqual(said, "Approved: Leave on Sat 17 Oct and Tue 20 Oct. Sun 18 Oct and Mon 19 Oct are days off.")
        cells = [dict(days.roster(self.key, sat + timedelta(days=i)))["Associate 012"] for i in range(4)]
        self.assertEqual(cells, ["Leave", "OFF", "OFF", "Leave"])
        for d in (sat, tue):  # a new version of each week's schedule, set in use
            self.assertNotEqual(days.version(self.key, d)[0]["id"], before[d])


class MyWeeksSwapFinder(_Leave):
    def setUp(self):
        from webapp.tests.test_runs import sign_in
        self.me = sign_in(self.app, "a12", "Associate-pass-1")

    def said(self, day):
        html = self.me.get(f"/me?swap={day.isoformat()}").get_data(as_text=True)
        return re.search(r'<li class="empty">([^<]*)</li>', html).group(1)

    def test_says_when_you_asked_for_leave(self):
        self.book.ask(self.key, "Associate 012", self.users["a12"]["id"], "Planned leave", THU, THU, "", today=TUE)
        self.assertEqual(self.said(THU), "You asked for leave on Thu 15 Oct, so there is no shift to swap.")

    def test_says_when_you_do_not_work(self):
        monday = TUE - timedelta(days=1)  # Associate 012 is off on Monday 12 October
        self.assertEqual(self.said(monday), "You do not work on Mon 12 Oct.")


if __name__ == "__main__":
    unittest.main()
