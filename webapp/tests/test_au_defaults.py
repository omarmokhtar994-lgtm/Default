# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU (owner, 2026-10-21): LOBs and defaults holds every default of a program and its LOBs: how it counts (interval
or volume), the default interval target, when its operating day starts, what counts as shrinkage; and they are the
defaults on every other page. A week's own target, and a LOB's own operating day or shrinkage, still win."""
import re
import unittest
from datetime import date

from webapp.programs import ProgramBook
from webapp.tests.test_as_requests import WED, _Fixture


class _Defaults(_Fixture):
    def setUp(self):
        self.programs = ProgramBook(self.store)
        self.days = self.app.extensions["days"]
        self.addCleanup(self.reset)
        self.reset()

    def reset(self):
        self.programs.set_rta_defaults(self.pid, target=None, day_start=None, shrinkage=None)
        self.programs.set_measure(self.pid, "interval")
        with self.store._db() as db:
            for table in ("interval_targets", "operating_days", "shrinkage_maps"):
                db.execute(f"delete from {table}")


class TheProgramDefaults(_Defaults):
    def test_they_start_empty_and_are_kept(self):
        self.assertEqual(self.programs.rta_defaults(self.pid), {"target": None, "day_start": None, "shrinkage": None})
        self.programs.set_rta_defaults(self.pid, target=85, day_start=16 * 60, shrinkage={"breaks": ["in"], "sick": ["client"]})
        got = self.programs.rta_defaults(self.pid)
        self.assertEqual((got["target"], got["day_start"]), (85, 960))
        self.assertEqual(got["shrinkage"]["sick"], ["client"])

    def test_they_are_checked(self):
        for bad in ({"target": 0}, {"target": 101}, {"day_start": 7}, {"day_start": -15}, {"day_start": 1440}):
            with self.assertRaises(ValueError, msg=bad):
                self.programs.set_rta_defaults(self.pid, **{"target": None, "day_start": None, "shrinkage": None, **bad})

    def test_a_lob_reads_its_programs_default_and_none_leaks_to_another_program(self):
        self.programs.set_rta_defaults(self.pid, target=80, day_start=None, shrinkage=None)
        self.assertEqual(self.store.rta_default(self.key, "target"), 80)
        other = self.programs.add_program("OTHER")
        self.assertIsNone(self.store.rta_default(self.programs.add_lob(other, "One"), "target"))


class TheTarget(_Defaults):
    def target(self):
        return self.days.target_for(self.key, WED)

    def test_the_chain_is_the_weeks_own_then_the_programs_then_the_workbooks(self):
        workbook, how = self.target()
        self.assertEqual(how["kind"], "workbook")
        self.programs.set_rta_defaults(self.pid, target=80, day_start=None, shrinkage=None)
        got, how = self.target()
        self.assertEqual((got, how["kind"]), (0.8, "program"))
        row, _ = self.days.version(self.key, WED)
        self.store.set_interval_target(self.key, row["week_start"], 95, None)
        got, how = self.target()
        self.assertEqual((got, how["kind"]), (0.95, "set"))

    def test_the_day_page_colours_with_the_programs_target(self):
        self.programs.set_rta_defaults(self.pid, target=80, day_start=None, shrinkage=None)
        page = self.days.page(self.key, WED)
        self.assertEqual(page["target"]["target"], 0.8)


class TheOperatingDayAndShrinkage(_Defaults):
    def test_the_operating_day_falls_back_to_the_program_and_a_lob_can_have_its_own(self):
        self.assertIsNone(self.store.get_day_start(self.key))
        self.programs.set_rta_defaults(self.pid, target=None, day_start=16 * 60, shrinkage=None)
        self.assertEqual(self.store.get_day_start(self.key), 960)
        self.store.set_day_start(self.key, 8 * 60, None)
        self.assertEqual(self.store.get_day_start(self.key), 480)
        self.store.clear_day_start(self.key)
        self.assertEqual(self.store.get_day_start(self.key), 960)

    def test_shrinkage_falls_back_the_same_way(self):
        self.assertIsNone(self.store.get_shrinkage_map(self.key))
        self.programs.set_rta_defaults(self.pid, target=None, day_start=None, shrinkage={"breaks": ["in"], "sick": []})
        kept = self.store.get_shrinkage_map(self.key)
        self.assertIn('"sick": []', kept["mapping"])
        self.store.set_shrinkage_map(self.key, {"breaks": []}, None)
        self.assertIn('"breaks": []', self.store.get_shrinkage_map(self.key)["mapping"])
        self.store.clear_shrinkage_map(self.key)
        self.assertIn('"sick": []', self.store.get_shrinkage_map(self.key)["mapping"])


class TheMeasure(_Defaults):
    def test_every_page_that_asks_for_no_measure_gets_the_programs(self):
        self.assertEqual(self.days.page(self.key, WED)["view"]["measure"], "interval")
        self.programs.set_measure(self.pid, "volume")
        self.assertEqual(self.days.page(self.key, WED)["view"]["measure"], "sl")
        self.assertEqual(self.days.page(self.key, WED, "interval")["view"]["measure"], "interval")   # asked for: kept

    def test_the_new_run_form_starts_from_it(self):
        from webapp.tests.test_runs import sign_in
        admin = sign_in(self.app, "omar", "Owner-pass-123") if any(u["username"] == "omar" for u in self.store.list_users()) else None
        if admin is None:
            uid = self.store.add_user("omar_d", "Omar", "Owner-pass-123", must_change=False)
            self.store.update_user(uid, is_admin=1)
            admin = sign_in(self.app, "omar_d", "Owner-pass-123")
        self.programs.set_measure(self.pid, "volume")
        import html as _html
        found = [_html.unescape(f) for f in re.findall(r'data-defaults="([^"]*)"', admin.get("/").get_data(as_text=True))]
        self.assertTrue(any('"coverage_measure": "VOLUME_WEIGHTED"' in f or '"coverage_measure":"VOLUME_WEIGHTED"' in f
                            for f in found), found)
        self.programs.set_measure(self.pid, "interval")
        found = [_html.unescape(f) for f in re.findall(r'data-defaults="([^"]*)"', admin.get("/").get_data(as_text=True))]
        self.assertFalse(any("coverage_measure" in f for f in found), found)       # interval is the default: follow the workbook


class TheSetupPage(_Defaults):
    def as_admin(self):
        from webapp.tests.test_runs import sign_in
        if self.store.get_user_by_name("setup_admin") is None:
            uid = self.store.add_user("setup_admin", "Setup Admin", "Owner-pass-123", must_change=False)
            self.store.update_user(uid, is_admin=1)
        return sign_in(self.app, "setup_admin", "Owner-pass-123")

    def post(self, client, **data):
        from webapp.tests.test_runs import token
        return client.post("/setup/programs", data={"csrf_token": token(client), "program_id": str(self.pid), **data})

    def test_one_form_sets_the_target_and_the_operating_day_and_blank_clears_them(self):
        client = self.as_admin()
        page = client.get("/setup/programs").get_data(as_text=True)
        self.assertIn("Default target", page)
        self.assertIn("Operating day starts", page)
        self.post(client, action="rta_defaults", target="85", day_start="16:00")
        self.assertEqual(self.programs.rta_defaults(self.pid)["target"], 85)
        self.assertEqual(self.programs.rta_defaults(self.pid)["day_start"], 960)
        self.post(client, action="rta_defaults", target="", day_start="")
        self.assertEqual(self.programs.rta_defaults(self.pid)["target"], None)

    def test_a_bad_value_is_said_and_nothing_changes(self):
        client = self.as_admin()
        got = client.post("/setup/programs", data={"csrf_token": __import__("webapp.tests.test_runs", fromlist=["token"]).token(client),
                                                    "action": "rta_defaults", "program_id": str(self.pid), "target": "150", "day_start": "16:07"},
                          follow_redirects=True)
        self.assertIn("1 to 100", got.get_data(as_text=True))
        self.assertEqual(self.programs.rta_defaults(self.pid), {"target": None, "day_start": None, "shrinkage": None})

    def test_the_shrinkage_form_saves_and_resets(self):
        client = self.as_admin()
        self.post(client, action="shrinkage", **{"breaks:in": "1", "sick:client": "1"})
        self.assertEqual(self.programs.rta_defaults(self.pid)["shrinkage"]["sick"], ["client"])
        self.assertEqual(self.programs.rta_defaults(self.pid)["shrinkage"]["unplanned"], [])
        self.post(client, action="shrinkage_standard")
        self.assertIsNone(self.programs.rta_defaults(self.pid)["shrinkage"])

    def test_a_lobs_own_settings_are_listed_and_can_go_back_to_the_programs(self):
        self.store.set_day_start(self.key, 8 * 60, None)
        client = self.as_admin()
        self.assertIn("Use the program's", client.get("/setup/programs").get_data(as_text=True))
        self.post(client, action="reset_unit", unit=self.key, field="day_start")
        self.assertIsNone(self.store._day_start_own(self.key))

    def test_only_an_admin_reaches_it(self):
        from webapp.tests.test_runs import sign_in
        self.assertEqual(sign_in(self.app, "rta1", "Staff-pass-123").get("/setup/programs").status_code, 403)


class TheRtaStillOpensOnTheCalendarDay(_Defaults):
    """Owner, 2026-10-15: "i dont need operating day to be something different than calendar day". The program's operating
    day start is offered on the RTA as "the operating day" in Day starts at; it is not the page's default."""
    def test_with_nothing_picked_the_rta_starts_at_midnight_and_offers_the_programs_operating_day(self):
        from webapp.tests.test_runs import sign_in
        self.programs.set_rta_defaults(self.pid, target=None, day_start=16 * 60, shrinkage=None)
        page = sign_in(self.app, "rta1", "Staff-pass-123").get(
            "/day", query_string={"program": self.key, "date": WED.isoformat(), "tz": "Africa/Cairo"}).get_data(as_text=True)
        self.assertRegex(page, r'<option value="00:00"[^>]* selected')
        self.assertIn("16:00, the operating day", page.replace("&#34;", '"'))


class TheDayPageLabels(_Defaults):
    def test_the_target_says_where_it_came_from(self):
        from webapp.tests.test_runs import sign_in
        self.programs.set_rta_defaults(self.pid, target=80, day_start=None, shrinkage=None)
        page = sign_in(self.app, "rta1", "Staff-pass-123").get(
            "/day", query_string={"program": self.key, "date": WED.isoformat()}).get_data(as_text=True)
        self.assertIn("program default", page.lower())


if __name__ == "__main__":
    unittest.main()
