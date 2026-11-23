# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL, task 6 (owner, 2026-11-07): sites.

"Sutherland is handling 100% phone, so phone volume is assigned to them; the internal team handles chat from 9 AM till 4 PM 100%, then
Sutherland handles 100% chat from 4 to 12 AM; email is shared between both sites 60% to 40% during weekdays, but on weekends everything is
100% Sutherland". "Both sites for scheduling etc."

A program has sites (a name, and the LOB the site is scheduled in) and rules: for a channel, on some weekdays, between two times, the share of
the contacts each site takes. Rules for one channel may not overlap, every rule's shares add to 100, and time no rule covers goes to the first
site (and is listed on the page, so it is a choice and not a surprise). Each site gets its own forecast, people needed and requirement workbook
from its share of every interval's contacts, the whole number of contacts kept. Made-up names only."""
import html
import io
import unittest
from datetime import timedelta

from openpyxl import load_workbook

from webapp import sites as S
from webapp.programs import ProgramBook
from webapp.tests.test_bi_volumes import KEY, SUN, book
from webapp.tests.test_bi_volumes_routes import PASSWORD, TODAY, _Volumes
from webapp.tests.test_bj_volumes_book import scaled
from webapp.tests.test_runs import sign_in, token

SUN_, MON, TUE, WED, THU, FRI, SAT = range(7)
WEEKDAYS, WEEKEND = [MON, TUE, WED, THU, FRI], [SAT, SUN_]
EVERY = list(range(7))


def sites(*names):
    return [{"name": n, "lob": ""} for n in names]


def rule(channel, days, start, end, **shares):
    return {"channel": channel, "days": days, "from": start, "to": end, "shares": shares}


def owners_example():
    return {"sites": sites("Internal", "Sutherland"),
            "rules": [rule("Phone", EVERY, 0, 1440, Sutherland=100),
                      rule("Chat", WEEKDAYS, 9 * 60, 16 * 60, Internal=100), rule("Chat", WEEKDAYS, 16 * 60, 24 * 60, Sutherland=100),
                      rule("Chat", WEEKEND, 0, 1440, Sutherland=100),
                      rule("Email", WEEKDAYS, 0, 1440, Internal=60, Sutherland=40), rule("Email", WEEKEND, 0, 1440, Sutherland=100)]}


class TheRules(unittest.TestCase):
    def setUp(self):
        self.doc = S.clean(owners_example())

    def test_the_owners_example_splits_as_described(self):
        at = lambda ch, d, h: S.split(self.doc, ch, d, h * 60)  # noqa: E731
        self.assertEqual(at("Phone", MON, 3), {"Internal": 0.0, "Sutherland": 100.0})
        self.assertEqual(at("Chat", WED, 10), {"Internal": 100.0, "Sutherland": 0.0})
        self.assertEqual(at("Chat", WED, 15), {"Internal": 100.0, "Sutherland": 0.0})
        self.assertEqual(at("Chat", WED, 16), {"Internal": 0.0, "Sutherland": 100.0})
        self.assertEqual(at("Chat", WED, 23), {"Internal": 0.0, "Sutherland": 100.0})
        self.assertEqual(at("Email", TUE, 12), {"Internal": 60.0, "Sutherland": 40.0})
        for channel in ("Phone", "Chat", "Email"):
            for day in WEEKEND:
                self.assertEqual(at(channel, day, 11), {"Internal": 0.0, "Sutherland": 100.0}, (channel, day))

    def test_time_no_rule_covers_goes_to_the_first_site_and_is_listed(self):
        self.assertEqual(S.split(self.doc, "Chat", WED, 3 * 60), {"Internal": 100.0, "Sutherland": 0.0})
        gaps = S.gaps(self.doc, "Chat")
        self.assertEqual(gaps[WED], [(0, 540)])
        self.assertEqual(S.gaps(self.doc, "Phone"), {})

    def test_a_channel_with_no_rules_goes_whole_to_the_first_site(self):
        doc = S.clean({"sites": sites("Internal", "Sutherland"), "rules": []})
        self.assertEqual(S.split(doc, "Phone", MON, 600), {"Internal": 100.0, "Sutherland": 0.0})

    def test_hours_past_midnight_belong_to_the_day_that_starts_them(self):
        doc = S.clean({"sites": sites("Internal", "Night"), "rules": [rule("Chat", [FRI], 22 * 60, 6 * 60 + 1440, Night=100)]})
        self.assertEqual(S.split(doc, "Chat", FRI, 23 * 60)["Night"], 100.0)
        self.assertEqual(S.split(doc, "Chat", SAT, 3 * 60)["Night"], 100.0)    # Saturday's small hours are Friday night's rule
        self.assertEqual(S.split(doc, "Chat", SAT, 7 * 60)["Night"], 0.0)
        self.assertEqual(S.split(doc, "Chat", THU, 3 * 60)["Night"], 0.0)

    def test_an_empty_program_has_no_sites_and_no_split(self):
        self.assertEqual(S.split(S.clean({}), "Phone", MON, 0), {})


class TheEntryIsStrict(unittest.TestCase):
    def refused(self, doc, *words):
        with self.assertRaises(ValueError) as caught:
            S.clean(doc)
        for w in words:
            self.assertIn(w, str(caught.exception))

    def test_shares_that_do_not_add_to_100_name_the_channel_and_the_days(self):
        doc = owners_example()
        doc["rules"][4] = rule("Email", WEEKDAYS, 0, 1440, Internal=60, Sutherland=30)
        self.refused(doc, "Email", "Mon", "100")

    def test_overlapping_rules_are_refused_by_name(self):
        doc = owners_example()
        doc["rules"].append(rule("Chat", [WED], 15 * 60, 17 * 60, Internal=100))
        self.refused(doc, "Chat", "Wed", "overlap")

    def test_a_share_for_a_site_that_does_not_exist_is_refused(self):
        self.refused({"sites": sites("A", "B"), "rules": [rule("Phone", EVERY, 0, 1440, A=50, C=50)]}, "C")

    def test_shares_are_numbers_from_0_to_100(self):
        for bad in (-5, 101, "x", None):
            with self.subTest(bad=bad):
                self.refused({"sites": sites("A", "B"), "rules": [rule("Phone", EVERY, 0, 1440, A=bad, B=100)]}, "share")

    def test_site_names_are_checked(self):
        self.refused({"sites": sites("A", "A"), "rules": []}, "twice")
        self.refused({"sites": sites(""), "rules": []}, "name")
        self.refused({"sites": sites("x" * 41), "rules": []}, "40")
        self.refused({"sites": sites(*[f"S{i}" for i in range(7)]), "rules": []}, "6")

    def test_a_name_that_could_be_read_as_a_formula_is_refused(self):
        for bad in ("=cmd", "+1", "-1", "@x"):
            with self.subTest(name=bad):
                self.refused({"sites": sites(bad), "rules": []}, "with a letter or a number")
        self.refused({"sites": [{"name": "Okay", "lob": "=1+1"}], "rules": []}, "LOB")

    def test_rule_fields_are_checked(self):
        self.refused({"sites": sites("A"), "rules": [rule("Fax", EVERY, 0, 1440, A=100)]}, "channel")
        self.refused({"sites": sites("A"), "rules": [rule("Phone", [], 0, 1440, A=100)]}, "day")
        self.refused({"sites": sites("A"), "rules": [rule("Phone", [9], 0, 1440, A=100)]}, "day")
        self.refused({"sites": sites("A"), "rules": [rule("Phone", EVERY, 600, 600, A=100)]}, "same")
        self.refused({"sites": sites("A"), "rules": [rule("Phone", EVERY, 0, 3000, A=100)]}, "time")

    def test_a_damaged_stored_document_reads_as_empty_not_trusted(self):
        self.assertEqual(S.read({"sites": "x"}), {"sites": [], "rules": []})
        self.assertEqual(S.read(None), {"sites": [], "rules": []})


class TheSitesInTheBook(unittest.TestCase):
    def setUp(self):
        self.store, self.vb = book()
        scaled(self.store, {})
        scaled(self.store, {}, channel="Chat", per_week=3000, aht=420.0)
        scaled(self.store, {}, channel="Email", per_week=1400, aht=480.0)
        self.vb.set_sites(KEY, owners_example(), 1)

    def forecast(self, channel="Phone", total=8000):
        return self.vb.forecast(KEY, channel, SUN, total=total)

    def test_the_sites_are_kept_and_read_back(self):
        self.assertEqual([s["name"] for s in self.vb.sites(KEY)["sites"]], ["Internal", "Sutherland"])
        self.assertEqual(len(self.vb.sites(KEY)["rules"]), 6)

    def test_saving_settings_and_hours_keeps_the_sites(self):
        self.vb.set_settings(KEY, {"Chat": {"occupancy": 80}}, 1)
        self.vb.set_open_hours(KEY, {"Phone": {"min_cover": 1, "days": {}}}, 1)
        self.assertEqual(len(self.vb.sites(KEY)["rules"]), 6)

    def test_every_contact_is_with_exactly_one_site_each_interval(self):
        f = self.forecast("Email", 1400)
        mine = {name: self.vb.for_site(KEY, f, name) for name in ("Internal", "Sutherland")}
        for d in range(7):
            for i in range(24):
                self.assertEqual(mine["Internal"]["calls"][d][i] + mine["Sutherland"]["calls"][d][i], f["calls"][d][i], (d, i))

    def test_the_email_split_is_60_40_on_weekdays_and_all_sutherland_on_weekends(self):
        f = self.forecast("Email", 1400)
        internal, suth = (self.vb.for_site(KEY, f, n) for n in ("Internal", "Sutherland"))
        self.assertAlmostEqual(sum(internal["calls"][MON]) / sum(f["calls"][MON]), 0.6, delta=0.01)
        self.assertEqual(sum(internal["calls"][SAT]), 0)
        self.assertEqual(sum(suth["calls"][SAT]), sum(f["calls"][SAT]))

    def test_phone_is_all_sutherlands_and_internal_needs_nobody(self):
        f = self.forecast("Phone")
        internal = self.vb.for_site(KEY, f, "Internal")
        self.assertEqual(sum(sum(r) for r in internal["calls"]), 0)
        self.assertEqual(sum(sum(r) for r in internal["needs"]), 0)
        suth = self.vb.for_site(KEY, f, "Sutherland")
        self.assertEqual(suth["calls"], f["calls"])
        self.assertEqual(suth["needs"], f["needs"])

    def test_each_site_is_staffed_for_its_own_contacts(self):
        f = self.forecast("Chat", 3000)
        internal, suth = self.vb.for_site(KEY, f, "Internal"), self.vb.for_site(KEY, f, "Sutherland")
        self.assertEqual(sum(internal["calls"][WED][16:]), 0)                      # from 16:00 the chat is Sutherland's
        self.assertGreater(sum(internal["calls"][WED][9:16]), 0)
        self.assertGreater(sum(internal["needs"][WED][9:16]), 0)
        self.assertEqual(sum(internal["needs"][WED][16:]), 0)
        self.assertEqual(sum(suth["calls"][WED][:16]), 0)                          # and before 16:00 it is not
        self.assertGreater(sum(suth["needs"][WED][16:]), 0)
        self.assertEqual(sum(internal["calls"][WED][:9]), sum(f["calls"][WED][:9]))  # 00:00 to 09:00 has no rule: the first site, as listed

    def test_a_site_with_no_share_needs_nobody_even_with_a_minimum_cover(self):
        self.vb.set_open_hours(KEY, {"Chat": {"min_cover": 2, "days": {"3": [0, 1440]}}}, 1)
        f = self.forecast("Chat", 3000)
        internal, suth = self.vb.for_site(KEY, f, "Internal"), self.vb.for_site(KEY, f, "Sutherland")
        self.assertEqual(sum(internal["needs"][WED][16:]), 0)       # Sutherland's hours: the minimum is Sutherland's to keep
        self.assertGreaterEqual(min(suth["needs"][WED][16:]), 2)
        self.assertGreaterEqual(min(internal["needs"][WED][9:16]), 2)

    def test_an_unknown_site_is_refused(self):
        with self.assertRaises(ValueError):
            self.vb.for_site(KEY, self.forecast("Phone"), "Nowhere")

    def test_no_sites_means_the_forecast_is_as_before(self):
        store, vb = book()
        scaled(store, {})
        f = vb.forecast(KEY, "Phone", SUN, total=8000)
        self.assertEqual(vb.sites(KEY), {"sites": [], "rules": []})
        self.assertEqual(vb.for_site(KEY, f, None), f)

    def test_each_site_has_its_own_requirement_workbook(self):
        from openpyxl import load_workbook
        import io
        forecasts = {ch: self.forecast(ch, t) for ch, t in (("Phone", 8000), ("Chat", 3000), ("Email", 1400))}
        books = {n: load_workbook(io.BytesIO(self.vb.requirement_workbook(KEY, SUN, forecasts, site=n))) for n in ("Internal", "Sutherland")}
        total = lambda wb, name: sum(c.value or 0 for row in wb[name].iter_rows(min_row=1) for c in row if isinstance(c.value, (int, float)))  # noqa: E731
        self.assertEqual(total(books["Internal"], "Phone 60 Min"), 0)
        self.assertGreater(total(books["Sutherland"], "Phone 60 Min"), 0)
        self.assertGreater(total(books["Internal"], "Chat 60 Min"), 0)
        self.assertIn("Sutherland", books["Sutherland"]["Phone 60 Min"]["A1"].value + books["Sutherland"]["Phone 60 Min"]["A2"].value)


class TheSitesOnThePage(_Volumes):
    def setUp(self):
        self.store.set_volume_settings(self.alpha, {}, 1)
        ProgramBook(self.store).set_measure(self.alpha_id, "sl")   # the people needed are worked out for a service-level program

    def tearDown(self):
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")

    def post(self, client, **fields):
        return client.post("/volumes/sites", data={"program": self.alpha, "csrf_token": token(client), **fields}, follow_redirects=True)

    def text(self, got):
        return html.unescape(got.get_data(as_text=True))

    def test_sites_and_rules_are_added_from_the_page_and_listed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, action="add_site", name="Internal", lob="Voice team")
        got = self.text(self.post(client, action="add_site", name="Sutherland", lob=""))
        self.assertIn("Added the site Sutherland", got)
        got = self.text(self.post(client, action="add_rule", channel="Email", days=["1", "2", "3"], start="00:00", end="24:00",
                                  **{"share.Internal": "60", "share.Sutherland": "40"}))
        self.assertIn("Added the rule", got)
        doc = self.vb.sites(self.alpha)
        self.assertEqual([(s["name"], s["lob"]) for s in doc["sites"]], [("Internal", "Voice team"), ("Sutherland", "")])
        self.assertEqual((doc["rules"][0]["days"], doc["rules"][0]["shares"]), ([1, 2, 3], {"Internal": 60.0, "Sutherland": 40.0}))
        page = self.text(client.get("/volumes", query_string={"program": self.alpha, "tab": "settings"}))
        self.assertIn("Sutherland", page)
        self.assertIn("goes to Internal", page)       # the time no rule covers is listed, with where it goes

    def test_a_rule_lists_only_the_sites_that_take_a_share_without_a_trailing_comma(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, action="add_site", name="Internal")
        self.post(client, action="add_site", name="Sutherland")
        self.post(client, action="add_rule", channel="Chat", days=["1"], start="09:00", end="16:00", **{"share.Internal": "100", "share.Sutherland": "0"})
        page = self.text(client.get("/volumes", query_string={"program": self.alpha, "tab": "settings"}))
        self.assertRegex(page, r"<td>Internal 100%</td>")

    def test_a_bad_rule_saves_nothing_and_says_why(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, action="add_site", name="A")
        self.post(client, action="add_site", name="B")
        got = self.text(self.post(client, action="add_rule", channel="Phone", days=["1"], start="00:00", end="24:00", **{"share.A": "60", "share.B": "30"}))
        self.assertIn("add up to 90", got)
        self.assertEqual(self.vb.sites(self.alpha)["rules"], [])
        got = self.text(self.post(client, action="add_rule", channel="Phone", days=["1"], start="9am", end="24:00", **{"share.A": "100", "share.B": "0"}))
        self.assertIn("Phone", got)
        self.assertEqual(self.vb.sites(self.alpha)["rules"], [])

    def test_a_site_a_rule_uses_cannot_be_removed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, action="add_site", name="A")
        self.post(client, action="add_site", name="B")
        self.post(client, action="add_rule", channel="Phone", days=["1"], start="00:00", end="24:00", **{"share.A": "60", "share.B": "40"})
        got = self.text(self.post(client, action="remove_site", name="B"))
        self.assertIn("rule", got)
        self.assertEqual(len(self.vb.sites(self.alpha)["sites"]), 2)
        self.post(client, action="remove_rule", index="0")
        self.post(client, action="remove_site", name="B")
        self.assertEqual([s["name"] for s in self.vb.sites(self.alpha)["sites"]], ["A"])

    def test_a_team_manager_looks_but_cannot_change_and_the_token_is_needed(self):
        client = sign_in(self.app, "tm_a", PASSWORD)
        self.assertEqual(client.post("/volumes/sites", data={"program": self.alpha, "csrf_token": token(client), "action": "add_site", "name": "X"}).status_code, 403)
        planner = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(planner.post("/volumes/sites", data={"program": self.alpha, "action": "add_site", "name": "X"}).status_code, 400)

    def test_the_forecast_shows_a_sites_share_and_downloads_its_workbook(self):
        self.history(self.alpha, channel="Phone")
        self.history(self.alpha, channel="Chat")
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, action="add_site", name="Internal")
        self.post(client, action="add_site", name="Sutherland")
        self.post(client, action="add_rule", channel="Phone", days=[str(d) for d in range(7)], start="00:00", end="24:00",
                  **{"share.Internal": "0", "share.Sutherland": "100"})
        week = (TODAY - timedelta(days=(TODAY.weekday() + 1) % 7) + timedelta(weeks=1)).isoformat()
        client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": week, "total": "7000", "action": "save"})
        base = {"program": self.alpha, "tab": "forecast", "channel": "Phone", "week": week}
        whole = self.text(client.get("/volumes", query_string=base))
        self.assertIn("Sutherland", whole)             # the site picker
        mine = self.text(client.get("/volumes", query_string={**base, "site": "Internal"}))
        self.assertIn("share of the contacts", mine)
        self.assertIn('value="7,000"', mine)           # the number is the whole program's, though Internal has none of the phone
        for site, nonzero in (("Internal", False), ("Sutherland", True)):
            got = client.get("/volumes/requirements.xlsx", query_string={"program": self.alpha, "week": week, "site": site})
            self.assertEqual(got.status_code, 200, site)
            self.assertIn(site, got.headers["Content-Disposition"])
            wb = load_workbook(io.BytesIO(got.get_data()))
            total = sum(c.value or 0 for row in wb[f"Phone {self.step} Min"].iter_rows(min_row=5, min_col=2) for c in row if isinstance(c.value, (int, float)))
            self.assertEqual(total > 0, nonzero, site)

    def test_an_unknown_site_in_the_address_is_ignored_on_the_page_and_refused_for_the_download(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(client.get("/volumes", query_string={"program": self.alpha, "tab": "forecast", "site": "Nowhere"}).status_code, 200)
        got = client.get("/volumes/requirements.xlsx", query_string={"program": self.alpha, "site": "Nowhere"})
        self.assertIn(got.status_code, (302, 303))


if __name__ == "__main__":
    unittest.main()
