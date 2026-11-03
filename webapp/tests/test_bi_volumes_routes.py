# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BI (owner, 2026-11-03: actuals in, forecast from a typed total, people needed with Erlang, how did we do, the grids like the input sheet so
they copy and paste). The pages end to end: the walls between programs and roles, the check-then-save upload, the forecast, the downloads."""
import html
import io
import re
import unittest
from datetime import date, timedelta

from openpyxl import load_workbook

from webapp.programs import ProgramBook
from webapp.tests import test_ar_walls as fx
from webapp.tests.test_runs import sign_in, token

PASSWORD = fx.PASSWORD
TODAY = date.today()


def weights(weekday):
    base = {8: 4, 9: 8, 10: 10, 11: 9, 12: 6, 13: 6, 14: 8, 15: 9, 16: 7, 17: 5, 18: 3, 19: 2}
    return {h: v for h, v in base.items() if 10 <= h <= 15} if weekday in (4, 5) else base


class _Volumes(fx._Walls):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vb = cls.app.extensions["volumes"]
        cls.step = cls.vb.step(cls.alpha)

    def history(self, key, weeks=8, per_week=7000, channel="Phone"):
        """Eight weeks before this week, a known shape, in the program's own interval."""
        sunday = TODAY - timedelta(days=(TODAY.weekday() + 1) % 7)
        rows = []
        for w in range(1, weeks + 1):
            for k in range(7):
                day = sunday - timedelta(weeks=w) + timedelta(days=k)
                wts = weights(day.weekday())
                total, s = per_week / 7, sum(wts.values())
                for h, v in wts.items():
                    for sub in range(60 // self.step):
                        rows.append((day.isoformat(), h * 60 + sub * self.step, round(total * v / s / (60 // self.step)), 300.0))
        self.store.replace_volume_rows(key, channel, rows, self.admin_id)

    def page(self, who, **query):
        return sign_in(self.app, who, PASSWORD).get("/volumes", query_string={"program": self.alpha, **query})


class TheWalls(_Volumes):
    def test_a_planner_opens_their_program_and_not_another(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for tab in ("actuals", "forecast", "how", "settings"):
            self.assertEqual(client.get("/volumes", query_string={"program": self.alpha, "tab": tab}).status_code, 200, tab)
            self.assertEqual(client.get("/volumes", query_string={"program": self.bravo, "tab": tab}).status_code, 403, tab)

    def test_nothing_of_another_program_is_written_or_read(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        tok = token(client)
        self.history(self.bravo)
        for path, data in (("/volumes/forecast", {"action": "save", "total": "9999", "channel": "Phone"}),
                           ("/volumes/actuals/check", {"paste": "Interval\tMon\n09:00\t5", "channel": "Phone"}),
                           ("/volumes/actuals/delete", {"first": "2020-01-01", "last": "2030-01-01", "confirm": "1", "channel": "Phone"}),
                           ("/volumes/settings", {"Phone.sl_target": "99"})):
            got = client.post(path, data={"program": self.bravo, "csrf_token": tok, **data})
            self.assertEqual(got.status_code, 403, path)
        for path in ("/volumes/table.xlsx", "/volumes/requirements.xlsx"):
            self.assertEqual(client.get(path, query_string={"program": self.bravo}).status_code, 403, path)
        self.assertTrue(self.store.volume_days(self.bravo, "Phone"))   # still there
        self.assertIsNone(self.store.volume_forecast(self.bravo, "Phone", "2026-01-01"))
        self.store.delete_volume_days(self.bravo, "Phone", "2000-01-01", "2100-01-01")

    def test_a_team_manager_looks_but_cannot_change(self):
        client = sign_in(self.app, "tm_a", PASSWORD)
        self.assertEqual(client.get("/volumes", query_string={"program": self.alpha, "tab": "settings"}).status_code, 200)
        tok = token(client)
        for path in ("/volumes/forecast", "/volumes/actuals/check", "/volumes/actuals/save", "/volumes/actuals/delete", "/volumes/settings"):
            self.assertEqual(client.post(path, data={"program": self.alpha, "csrf_token": tok}).status_code, 403, path)

    def test_an_associate_sees_nothing(self):
        client = sign_in(self.app, "assoc_a", PASSWORD)
        got = client.get("/volumes", query_string={"program": self.alpha})
        self.assertIn(got.status_code, (302, 303, 403))

    def test_the_menu_link_follows_the_permission(self):
        body = sign_in(self.app, "plan_a", PASSWORD).get("/").get_data(as_text=True)
        self.assertIn('href="/volumes', body)
        self.assertNotIn('href="/volumes', sign_in(self.app, "assoc_a", PASSWORD).get("/me").get_data(as_text=True))

    def test_every_form_needs_the_token(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for path in ("/volumes/forecast", "/volumes/actuals/check", "/volumes/actuals/save", "/volumes/actuals/delete", "/volumes/settings"):
            self.assertEqual(client.post(path, data={"program": self.alpha}).status_code, 400, path)


class TheActuals(_Volumes):
    @property
    def GRID(self):  # the program's own interval, so the check is not about the step
        rows = [(h * 60 + m) for h in range(8, 12) for m in range(0, 60, self.step)]
        return "Interval\tSun\tMon\tTue\tWed\tThu\tFri\tSat\n" + "".join(
            f"{t // 60:02d}:{t % 60:02d}\t{t // 60}\t{t // 30}\t{t // 20}\t{t // 30}\t{t // 30}\t{t // 60}\t{t // 60}\n" for t in rows)

    def week_text(self):
        d = TODAY - timedelta(days=(TODAY.weekday() + 1) % 7) - timedelta(weeks=1)
        return d.isoformat()

    def check(self, client, **form):
        return client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone",
                                                          "week": self.week_text(), **form})

    def test_a_pasted_grid_is_checked_then_saved(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])
        got = self.check(client, paste=self.GRID)
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("The table is good", body)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])       # checked, not saved
        tok = re.search(r'name="token" value="([^"]+)"', body).group(1)
        saved = client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok}, follow_redirects=True)
        self.assertIn("Saved.", html.unescape(saved.get_data(as_text=True)))
        self.assertEqual(len(self.store.volume_days(self.alpha, "Phone")), 7)
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")

    def test_a_bad_table_saves_nothing_and_says_which_row(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        bad = "Date\tInterval\tChannel\tOffered\n2026-10-26\t09:00\tPhone\t-5\n"
        body = html.unescape(self.check(client, paste=bad).get_data(as_text=True))
        self.assertIn("Nothing was saved", body)
        self.assertIn("Row 2", body)
        self.assertNotIn('name="token"', body)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])

    def test_a_check_cannot_be_saved_by_someone_else_or_for_another_program(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = html.unescape(self.check(client, paste=self.GRID).get_data(as_text=True))
        tok = re.search(r'name="token" value="([^"]+)"', body).group(1)
        other = sign_in(self.app, "sup_a", PASSWORD)
        got = other.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(other), "token": tok}, follow_redirects=True)
        self.assertIn("expired", html.unescape(got.get_data(as_text=True)))
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])
        again = client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok}, follow_redirects=True)
        self.assertIn("Saved.", html.unescape(again.get_data(as_text=True)))   # the owner of the check still can
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")

    def test_a_workbook_upload_works_and_a_hostile_one_does_not(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        good = io.BytesIO()
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Date", "Interval", "Channel", "Offered", "AHT"])
        ws.append([TODAY - timedelta(days=3), "09:00", "Phone", 12, 300])
        wb.save(good)
        got = client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone",
                                                          "file": (io.BytesIO(good.getvalue()), "actuals.xlsx")}, content_type="multipart/form-data")
        self.assertIn("The table is good", html.unescape(got.get_data(as_text=True)))
        for name, data in (("x.xlsx", b"PK\x03\x04 not a workbook"), ("x.exe", b"MZ"), ("x.csv", b"\xff\xfe\x00")):
            got = client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone",
                                                              "file": (io.BytesIO(data), name)}, content_type="multipart/form-data")
            self.assertLess(got.status_code, 500, name)
            self.assertNotIn("The table is good", html.unescape(got.get_data(as_text=True)), name)

    def test_days_can_be_deleted_only_when_confirmed(self):
        self.history(self.alpha, weeks=2)
        client = sign_in(self.app, "plan_a", PASSWORD)
        first = self.store.volume_days(self.alpha, "Phone")[0]
        client.post("/volumes/actuals/delete", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "first": first, "last": first})
        self.assertIn(first, self.store.volume_days(self.alpha, "Phone"))
        client.post("/volumes/actuals/delete", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "first": first, "last": first, "confirm": "1"})
        self.assertNotIn(first, self.store.volume_days(self.alpha, "Phone"))
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")

    def test_what_was_done_is_recorded(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = html.unescape(self.check(client, paste=self.GRID).get_data(as_text=True))
        tok = re.search(r'name="token" value="([^"]+)"', body).group(1)
        client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok})
        kinds = [e["kind"] for e in self.store.list_events(0, 4e9, self.alpha)]
        self.assertIn("volumes_uploaded", kinds)
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")


class TheForecast(_Volumes):
    def setUp(self):
        self.history(self.alpha)
        ProgramBook(self.store).set_measure(self.alpha_id, "sl")
        week = TODAY + timedelta(weeks=1)
        self.week = (week - timedelta(days=(week.weekday() + 1) % 7)).isoformat()

    def tearDown(self):
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")
        self.store.delete_volume_forecast(self.alpha, "Phone", self.week)
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")

    def work(self, client, **form):
        return client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                       "action": "preview", **form})

    def test_a_typed_total_comes_out_as_a_grid_like_the_input_sheet(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = self.work(client, total="12,600").get_data(as_text=True)
        self.assertIn('data-copy-table="#tbl-calls"', body)
        table = re.search(r'<table class="vol-grid" id="tbl-calls">(.*?)</table>', body, re.S).group(1)
        head = re.findall(r"<th scope=\"col\">([^<]+)</th>", table)
        self.assertEqual(head, ["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(len(re.findall(r"<tr>", table)), 1 + 1440 // self.step)
        self.assertIn("<th scope=\"row\">10:00</th>", table)
        cells = [int(x) for x in re.findall(r"<td[^>]*>(\d+)</td>", table)]
        self.assertEqual(sum(cells), 12600)

    def test_people_needed_appear_for_a_service_level_program_and_not_for_interval(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertIn('id="tbl-needs"', self.work(client, total="8000").get_data(as_text=True))
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")
        self.assertNotIn('id="tbl-needs"', self.work(client, total="8000").get_data(as_text=True))

    def test_bad_totals_are_said_in_words_not_a_crash(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for bad in ("-5", "abc", "1.5", "99999999999", "0x10"):
            got = self.work(client, total=bad)
            self.assertEqual(got.status_code, 200, bad)
            self.assertIn("whole number", html.unescape(got.get_data(as_text=True)), bad)

    def test_a_forecast_is_saved_and_can_be_removed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = self.work(client, total="9,100", action="save")
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.store.volume_forecast(self.alpha, "Phone", self.week)["total"], 9100)
        self.work(client, action="remove")
        self.assertIsNone(self.store.volume_forecast(self.alpha, "Phone", self.week))

    def test_typed_days_are_kept(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.work(client, total="9000", d1="1500", action="save")
        self.assertEqual(self.store.volume_forecast(self.alpha, "Phone", self.week)["days"], {"1": 1500})
        bad = self.work(client, total="1000", d1="900", d2="900", action="save")
        self.assertEqual(self.store.volume_forecast(self.alpha, "Phone", self.week)["total"], 9000)  # the bad one saved nothing
        self.assertIn("more than", html.unescape(bad.get_data(as_text=True)))

    def test_the_requirement_workbook_downloads_and_is_laid_out_like_the_input_sheet(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/volumes/requirements.xlsx", query_string={"program": self.alpha, "week": self.week})
        self.assertEqual(got.status_code, 200)
        wb = load_workbook(io.BytesIO(got.data))
        self.assertEqual(wb.sheetnames[0], f"FT Wise {self.step} Min")
        self.assertIn(f"Phone {self.step} Min", wb.sheetnames)

    def test_an_interval_program_has_no_requirement_workbook(self):
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/volumes/requirements.xlsx", query_string={"program": self.alpha, "week": self.week})
        self.assertEqual(got.status_code, 303)

    def test_each_grid_downloads_as_a_sheet(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for what in ("calls", "needs"):
            got = client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "week": self.week, "what": what, "total": "8000"})
            self.assertEqual(got.status_code, 200, what)
            ws = load_workbook(io.BytesIO(got.data)).active
            self.assertEqual([c.value for c in ws[1]], ["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"])
        self.assertEqual(client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "what": "nonsense"}).status_code, 404)


class TheReport(_Volumes):
    def test_how_did_we_do_reads_the_saved_forecast_against_the_actuals(self):
        ProgramBook(self.store).set_measure(self.alpha_id, "sl")
        self.history(self.alpha)
        sunday = TODAY - timedelta(days=(TODAY.weekday() + 1) % 7)
        week = sunday - timedelta(weeks=1)
        self.vb.save_forecast(self.alpha, "Phone", week, 7000, {}, self.admin_id)
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = client.get("/volumes", query_string={"program": self.alpha, "tab": "how", "week": week.isoformat()}).get_data(as_text=True)
        self.assertIn("Offered over forecast", body)
        self.assertIn('id="tbl-otf"', body)
        self.assertRegex(body, r'class="ot-(on|over|under)"')
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")
        self.store.delete_volume_forecast(self.alpha, "Phone", week.isoformat())
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")

    def test_a_week_with_nothing_says_so(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = html.unescape(client.get("/volumes", query_string={"program": self.alpha, "tab": "how"}).get_data(as_text=True))
        self.assertIn("No actual volume", body)


class TheSettings(_Volumes):
    def test_settings_are_saved_and_a_bad_one_saves_nothing(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        client.post("/volumes/settings", data={"program": self.alpha, "csrf_token": token(client), "Phone.sl_target": "90", "Phone.sl_seconds": "30"})
        self.assertEqual(self.vb.settings(self.alpha)["Phone"]["sl_target"], 90)
        got = client.post("/volumes/settings", data={"program": self.alpha, "csrf_token": token(client), "Phone.sl_target": "10"}, follow_redirects=True)
        self.assertEqual(self.vb.settings(self.alpha)["Phone"]["sl_target"], 90)
        self.assertIn("Service level target", html.unescape(got.get_data(as_text=True)))
        self.store.set_volume_settings(self.alpha, {}, 1)


if __name__ == "__main__":
    unittest.main()
