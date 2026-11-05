# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BK (owner, 2026-11-04): "+ Add" after midnight on an overnight shift, with an operating day that starts at noon.

"associate today shift from 6 PM till 3 AM, we are on the 4th, I chose the associate, chose coaching, placed it at
1:10 AM, then it reflected on the 5th interval 1 AM, as I'm using an operating day that starts at 12 PM".
The 1:10 AM that belongs to the 4th's shift is on the 5th's calendar day, so the page's "+ Add" opened the 5th's
schedule day. Only shifts that start on that day were offered, and a person with a shift on both days got the
coaching on the 5th's shift (1:10 AM there is 25:10, the 6th's calendar day). The activity has to be kept on the
shift that is running at that time, the 4th's, in the minutes of that shift (25:10).
Made-up "Associate NN" data.
"""
import html
import json
import re
import unittest
from datetime import date, timedelta

from webapp.tests.test_as_requests import NIGHT, WED, _Fixture
from webapp.tests.test_runs import TOKEN, sign_in

THU = WED + timedelta(days=1)
ONE_TEN = 1440 + 70  # 01:10 on the next calendar day, in minutes from the operating day's own midnight


class OvernightAdd(_Fixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = sign_in(cls.app, "rta1", "Staff-pass-123")
        wed = cls.app.extensions["days"].version(cls.key, WED)[0]
        week = json.loads(wed["week"])
        for a in week["associates"]:
            if a["name"] == NIGHT:
                a["days"][3] = "18:00 - 03:00"
        week["breaks"] = [b for b in week["breaks"] if b["associate"] != NIGHT]
        cls.store.update_schedule(wed["id"], week=json.dumps(week))
        cls.store.set_day_start(cls.key, 12 * 60, cls.users["rta1"]["id"])

    def setUp(self):
        self.clear()

    def csrf(self):
        return TOKEN.search(self.client.get("/").get_data(as_text=True)).group(1)

    def dialog(self):
        """The "+ Add" dialog the RTA gets on Wednesday's operating day for 01:10 on Thursday."""
        page = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&window=operating"
                               f"&view=board&add={ONE_TEN}").get_data(as_text=True)
        return html.unescape(page)

    def coach(self, dialog, name=NIGHT):
        date_ = re.search(r'<dialog id="add-dialog".*?name="date" value="([^"]+)"', dialog, re.S).group(1)
        got = self.client.post("/day/add", data={
            "csrf_token": self.csrf(), "program": self.key, "date": date_, "associate": name, "what": "Coaching",
            "from": "01:10", "minutes": "15", "view": "board", "with_whom": "Omar", "why": "Weekly one to one"},
            follow_redirects=True)
        self.assertEqual(got.status_code, 200)
        return html.unescape(got.get_data(as_text=True))

    def kept(self):
        rows = [a for d in (WED, THU, THU + timedelta(days=1)) for a in
                self.store.list_activities(self.key, [d.isoformat()]) if a["associate"] == NIGHT and a["kind"] == "Coaching"]
        return [(a["shift_date"], a["start"]) for a in rows]

    def test_the_dialog_offers_the_shift_that_started_the_day_before(self):
        dialog = self.dialog()
        add = dialog[dialog.index('<dialog id="add-dialog"'):] if '<dialog id="add-dialog"' in dialog else ""
        who = re.search(r'<select name="associate" required>(.*?)</select>', add, re.S)
        self.assertIsNotNone(who, "nobody is offered at 01:10")
        mine = re.findall(rf'<option value="{NIGHT}"[^>]*>([^<]*)</option>', who.group(1))
        self.assertEqual(len(mine), 1, who.group(1))  # once, and as the shift that is running at 01:10
        self.assertIn("18:00 - 03:00", mine[0])

    def test_coaching_at_one_ten_is_kept_on_the_shift_that_is_running(self):
        said = self.coach(self.dialog())
        self.assertEqual(self.kept(), [(WED.isoformat(), ONE_TEN)], said)

    def test_a_person_with_a_shift_on_both_days_is_still_kept_on_the_one_running_at_one_ten(self):
        thu = self.app.extensions["days"].version(self.key, THU)[0]
        week = json.loads(thu["week"])
        for a in week["associates"]:
            if a["name"] == NIGHT:
                a["days"][4] = "18:00 - 03:00"
        self.store.update_schedule(thu["id"], week=json.dumps(week))
        try:
            self.coach(self.dialog())
            self.assertEqual(self.kept(), [(WED.isoformat(), ONE_TEN)])
        finally:
            week_ = json.loads(thu["week"])
            self.store.update_schedule(thu["id"], week=json.dumps(week_))


if __name__ == "__main__":
    unittest.main()
