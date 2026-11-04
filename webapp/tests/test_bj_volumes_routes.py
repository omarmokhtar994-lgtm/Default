# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04): the pages end to end for the draft workbook (download, fill, upload), the grid typed on the site, and the forecast with the
weeks used, the events, AI periods, growth and last year. The walls and the check-then-save rule hold for every new way in."""
import html
import io
import re
import unittest
from datetime import date, timedelta

from openpyxl import load_workbook

from webapp.programs import ProgramBook
from webapp.tests.test_bi_volumes_routes import PASSWORD, TODAY, _Volumes
from webapp.tests.test_runs import sign_in, token


def last_sunday():
    return TODAY - timedelta(days=(TODAY.weekday() + 1) % 7) - timedelta(weeks=1)


class TheDraft(_Volumes):
    def get(self, client, **query):
        return client.get("/volumes/draft.xlsx", query_string={"program": self.alpha, "week": last_sunday().isoformat(), **query})

    def fill(self, cells, sheet="Phone", mutate=None):
        got = self.get(sign_in(self.app, "plan_a", PASSWORD))
        wb = load_workbook(io.BytesIO(got.get_data()))
        ws = wb[sheet]
        head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
        for (day, slot), value in cells.items():
            ws.cell(head + 1 + slot, 2 + day).value = value
        if mutate:
            mutate(wb)
        out = io.BytesIO()
        wb.save(out)
        return out.getvalue()

    def upload(self, data, name="draft.xlsx"):
        client = sign_in(self.app, "plan_a", PASSWORD)
        return client, client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone",
                                                                  "file": (io.BytesIO(data), name)}, content_type="multipart/form-data")

    def test_the_draft_downloads_in_the_programs_interval(self):
        got = self.get(sign_in(self.app, "plan_a", PASSWORD))
        self.assertEqual(got.status_code, 200)
        self.assertIn("spreadsheetml", got.mimetype)
        self.assertIn(f"Volumes_draft_{last_sunday().isoformat()}.xlsx", got.headers["Content-Disposition"])
        wb = load_workbook(io.BytesIO(got.get_data()))
        self.assertEqual(wb.sheetnames, ["Read me", "Phone", "Chat", "Email"])
        ws = wb["Chat"]
        self.assertEqual(sum(1 for r in range(1, 400) if re.fullmatch(r"\d\d:\d\d", str(ws.cell(r, 1).value or ""))), 1440 // self.step)
        self.assertEqual(ws["B2"].value.date(), last_sunday())

    def test_a_bad_week_falls_back_and_never_crashes(self):
        for week in ("", "x", "2026-13-45", "9999-12-31", "<script>"):
            got = self.get(sign_in(self.app, "plan_a", PASSWORD), week=week)
            self.assertEqual(got.status_code, 200, week)

    def test_the_walls_hold(self):
        self.assertEqual(self.get(sign_in(self.app, "plan_a", PASSWORD), program=self.bravo).status_code, 403)
        self.assertEqual(self.get(sign_in(self.app, "sup_a", PASSWORD)).status_code, 200)       # a supervisor may look
        self.assertEqual(self.app.test_client().get("/volumes/draft.xlsx").status_code, 302)    # not signed in
        self.assertIn(self.get(sign_in(self.app, "assoc_a", PASSWORD)).status_code, (302, 403, 404))

    def test_a_filled_draft_is_checked_then_saved(self):
        slot = lambda hour: hour * 60 // self.step           # noqa: E731
        data = self.fill({(1, slot(9)): 40, (1, slot(10)): 55, (2, slot(9)): 31})
        client, got = self.upload(data)
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("The table is good", body)
        self.assertIn("the draft workbook", body)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])                          # checked, not saved
        tok = re.search(r'name="token" value="([^"]+)"', body).group(1)
        saved = client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok}, follow_redirects=True)
        self.assertIn("Saved.", html.unescape(saved.get_data(as_text=True)))
        self.assertEqual(len(self.store.volume_days(self.alpha, "Phone")), 2)
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")

    def test_the_channel_on_the_form_does_not_matter_for_a_draft(self):
        slot = 9 * 60 // self.step
        def chat(wb):
            wb["Chat"].cell(next(r for r in range(1, 15) if wb["Chat"].cell(r, 1).value == "Interval") + 1 + slot, 3).value = 7
        client, got = self.upload(self.fill({}, mutate=chat))                                       # the form says Phone; the sheet is Chat
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("The table is good", body)
        self.assertIn("Chat:", body)

    def test_one_bad_cell_saves_nothing_and_does_not_echo_it(self):
        _, got = self.upload(self.fill({(1, 9 * 60 // self.step): "banana split"}))
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("Nothing was saved", body)
        self.assertIn("Phone:", body)
        self.assertNotIn("banana split", body)
        self.assertNotIn('name="token"', body)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])

    def test_an_empty_draft_says_so(self):
        _, got = self.upload(self.fill({}))
        self.assertIn("no numbers", html.unescape(got.get_data(as_text=True)))

    def test_hostile_drafts_are_refused_in_words(self):
        card = self.fill({(1, 9 * 60 // self.step): 5}, mutate=lambda wb: wb["Phone"].__setitem__("K2", "4111 1111 1111 1111"))
        for name, data in (("card.xlsx", card), ("junk.xlsx", b"PK\x03\x04 junk"), ("empty.xlsx", b"")):
            client, got = self.upload(data, name)
            self.assertLess(got.status_code, 500, name)
            self.assertNotIn("The table is good", html.unescape(got.get_data(as_text=True)), name)
        self.assertEqual(self.store.volume_days(self.alpha, "Phone"), [])

    def test_a_typed_grid_with_handle_times_is_checked_like_a_paste(self):
        rows = [h * 60 + m for h in (9, 10) for m in range(0, 60, self.step)]
        offered = "Interval\tSun\tMon\tTue\tWed\tThu\tFri\tSat\n" + "".join(f"{t // 60:02d}:{t % 60:02d}\t\t12\t\t\t\t\t\n" for t in rows)
        aht = "Interval\tSun\tMon\tTue\tWed\tThu\tFri\tSat\n" + "".join(f"{t // 60:02d}:{t % 60:02d}\t\t310\t\t\t\t\t\n" for t in rows)
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone",
                                                          "week": last_sunday().isoformat(), "paste": offered, "aht_paste": aht})
        body = html.unescape(got.get_data(as_text=True))
        self.assertIn("The table is good", body)
        tok = re.search(r'name="token" value="([^"]+)"', body).group(1)
        client.post("/volumes/actuals/save", data={"program": self.alpha, "csrf_token": token(client), "token": tok})
        day = (last_sunday() + timedelta(days=1)).isoformat()
        held = self.store.volume_rows(self.alpha, "Phone", day, day)
        self.assertTrue(held and all(r["offered"] == 12 and r["aht"] == 310 for r in held))
        self.store.delete_volume_days(self.alpha, "Phone", "2000-01-01", "2100-01-01")

    def test_the_actuals_page_offers_the_three_ways(self):
        body = html.unescape(self.page("plan_a", tab="actuals").get_data(as_text=True))
        self.assertIn("Download the draft (Excel)", body)
        self.assertIn("data-entry-form", body)
        self.assertIn(f'data-entry-grid="offered" data-entry-step="{self.step}"', body)
        self.assertIn('data-entry-grid="aht"', body)
        self.assertIn("Upload or paste", body)


class TheForecastPage(_Volumes):
    def setUp(self):
        self.history(self.alpha)
        self.history(self.alpha, channel="Chat", per_week=3000)
        ProgramBook(self.store).set_measure(self.alpha_id, "sl")
        nxt = TODAY + timedelta(weeks=1)
        self.sunday = nxt - timedelta(days=(nxt.weekday() + 1) % 7)
        self.week = self.sunday.isoformat()

    def tearDown(self):
        for ch in ("Phone", "Chat"):
            self.store.delete_volume_days(self.alpha, ch, "2000-01-01", "2100-01-01")
            self.store.delete_volume_forecast(self.alpha, ch, self.week)
        self.store.set_volume_drivers(self.alpha, {}, 1)
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")

    def view(self, client=None, channel="Phone", **query):
        client = client or sign_in(self.app, "plan_a", PASSWORD)
        return client.get("/volumes", query_string={"program": self.alpha, "tab": "forecast", "channel": channel, "week": self.week, **query})

    def post(self, client, action, **form):
        return client.post("/volumes/drivers", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                     "action": action, **form})

    def event(self, **kw):
        return {"kind": "Promotion", "name": "Black Friday", "channels": ["Phone"], "start": (self.sunday + timedelta(days=2)).isoformat(),
                "end": (self.sunday + timedelta(days=4)).isoformat(), "change": "25", **kw}

    def text(self, got):
        return html.unescape(got.get_data(as_text=True))

    # -- the weeks behind a forecast
    def test_the_weeks_of_history_are_asked_for_and_shown(self):
        body = self.text(self.view(hist_weeks="4", total="8000"))
        self.assertIn("4 used", body)
        self.assertEqual(len(re.findall(r'name="skip" value="', body)), 4)
        self.assertIn("6 used", self.text(self.view(total="8000")))

    def test_a_bad_number_of_weeks_is_said_in_words(self):
        for bad in ("2", "27", "abc", "-4", "1e3"):
            got = self.view(hist_weeks=bad, total="8000")
            self.assertEqual(got.status_code, 200, bad)
            self.assertIn("3 to 26", self.text(got), bad)

    def test_a_week_left_out_is_named_and_replaced(self):
        oldest = (self.sunday - timedelta(weeks=2)).isoformat()
        body = self.text(self.view(total="8000", skip_sent="1", skip=oldest))
        self.assertIn("left out by you", body)
        self.assertRegex(body, r'<input type="checkbox" name="skip" value="%s" checked>' % oldest)
        self.assertIn("6 used", body)

    def test_remembered_weeks_apply_until_the_form_says_otherwise(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        out = (self.sunday - timedelta(weeks=1)).isoformat()
        got = client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                     "action": "remember_weeks", "skip_sent": "1", "skip": out})
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.vb.drivers(self.alpha)["skip_weeks"], [out])
        self.assertIn("left out by you", self.text(self.view(client, total="8000")))
        self.assertNotIn("left out by you", self.text(self.view(client, total="8000", skip_sent="1")))

    def test_a_forecast_saved_with_other_weeks_keeps_them(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                               "action": "save", "total": "9,000", "hist_weeks": "4"})
        basis = self.store.volume_forecast(self.alpha, "Phone", self.week)["basis"]
        self.assertEqual(len(basis["weeks"]["used"]), 4)
        self.assertIn("kept with its own grid", self.text(self.view(client)))

    # -- events
    def test_an_event_is_added_listed_built_into_the_suggestion_and_removed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        plain = self.vb.forecast(self.alpha, "Phone", self.sunday)["suggestion"]["final"]
        got = self.post(client, "add_event", **self.event())
        self.assertEqual(got.status_code, 303)
        body = self.text(self.view(client))
        self.assertIn("Black Friday", body)
        self.assertIn("How the suggestion is built", body)
        final = self.vb.forecast(self.alpha, "Phone", self.sunday)["suggestion"]["final"]
        self.assertGreater(final, plain)
        self.assertIn(f"{final:,}", body)
        ident = self.vb.drivers(self.alpha)["events"][0]["id"]
        self.post(client, "remove", list="events", id=ident)
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])
        self.assertEqual(self.vb.forecast(self.alpha, "Phone", self.sunday)["suggestion"]["final"], plain)

    def test_what_was_removed_is_named_and_a_second_removal_is_said(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, "add_event", **self.event(name="Spring sale"))
        ident = self.vb.drivers(self.alpha)["events"][0]["id"]
        said = self.text(client.post("/volumes/drivers", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                               "action": "remove", "list": "events", "id": ident}, follow_redirects=True))
        self.assertIn("Removed Spring sale.", said)
        again = self.text(client.post("/volumes/drivers", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                                "action": "remove", "list": "events", "id": ident}, follow_redirects=True))
        self.assertIn("That one was already removed.", again)

    def test_the_weeks_table_says_the_status_of_every_week(self):
        body = self.text(self.view(total="8000", skip_sent="1", skip=(self.sunday - timedelta(weeks=2)).isoformat()))
        self.assertIn('<th scope="col">Status</th>', body)
        self.assertIn("Not used: left out by you", body)
        self.assertRegex(body, r'<td class="vol-why">Used</td>')

    def test_a_bad_event_is_refused_in_words_and_the_form_keeps_what_was_typed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = self.post(client, "add_event", **self.event(change="900", name="Spring sale"))
        body = self.text(got)
        self.assertEqual(got.status_code, 200)
        self.assertIn("is in percent, more than -100 and at most 500", body)
        self.assertIn('value="Spring sale"', body)
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])
        for bad in (self.event(end=(self.sunday - timedelta(days=3)).isoformat()), self.event(channels=[]), self.event(name="=cmd|' /C calc'!A0"),
                    self.event(kind="Party"), self.event(start="tomorrow"), self.event(after_days="40")):
            self.assertEqual(self.post(client, "add_event", **bad).status_code, 200)
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])

    def test_a_name_with_markup_is_shown_as_text(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, "add_event", **self.event(name="<script>alert(1)</script>"))
        raw = self.view(client).get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", raw)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", raw)

    # -- AI
    def test_ai_periods_are_added_checked_for_overlap_and_move_contacts(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        chat = self.vb.forecast(self.alpha, "Chat", self.sunday)["suggestion"]["final"]
        a, b = self.sunday.isoformat(), (self.sunday + timedelta(days=6)).isoformat()
        self.assertEqual(self.post(client, "add_ai", ai_channel="Phone", start=a, end=b, change="-20", move_to="Chat", move_share="50").status_code, 303)
        again = self.post(client, "add_ai", ai_channel="Phone", start=b, end=b, change="-30")
        self.assertIn("overlaps", self.text(again))
        self.assertEqual(len(self.vb.drivers(self.alpha)["ai"]), 1)
        body = self.text(self.view(client, channel="Chat"))
        self.assertIn("Moved in from other channels", body)
        self.assertGreater(self.vb.forecast(self.alpha, "Chat", self.sunday)["suggestion"]["final"], chat)

    def test_ai_that_moves_to_its_own_channel_or_grows_is_refused(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        a = self.sunday.isoformat()
        for bad in ({"move_to": "Phone", "move_share": "50", "change": "-10"}, {"move_to": "Chat", "move_share": "50", "change": "10"},
                    {"move_to": "Chat", "move_share": "150", "change": "-10"}, {"change": "abc"}, {"ai_channel": "Fax"}):
            got = self.post(client, "add_ai", **{"ai_channel": "Phone", "start": a, "end": a, "change": "-10", **bad})
            self.assertEqual(got.status_code, 200, bad)
        self.assertEqual(self.vb.drivers(self.alpha)["ai"], [])

    # -- growth and last year
    def test_growth_and_last_year_are_saved_and_shown(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(self.post(client, "growth", **{"yoy.Phone": "8", "yoy.Chat": "", "method": "measured"}).status_code, 303)
        self.assertEqual(self.vb.drivers(self.alpha)["growth"], {"yoy": {"Phone": 8.0}, "method": "measured"})
        self.post(client, "last_year", **{"ly.Phone": "12,000", "ly.Chat": ""})
        body = self.text(self.view(client))
        self.assertIn("grown by 8% = 12,960", body)
        grown = self.text(self.view(client, base="last_year"))
        self.assertIn("12,960", grown)
        self.assertIn("Last year's same week, grown by 8%", grown)

    def test_a_bad_rate_or_total_is_refused_and_nothing_is_kept(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for form in ({"yoy.Phone": "-80", "method": "growth"}, {"yoy.Phone": "abc", "method": "growth"}, {"yoy.Phone": "5", "method": "magic"}):
            self.assertEqual(self.post(client, "growth", **form).status_code, 200, form)
        for form in ({"ly.Phone": "-4"}, {"ly.Phone": "1.5"}, {"ly.Phone": "abc"}):
            self.assertEqual(self.post(client, "last_year", **form).status_code, 200, form)
        doc = self.vb.drivers(self.alpha)
        self.assertEqual((doc["growth"]["yoy"], doc["last_year"]), ({}, {}))

    def test_an_unknown_action_or_list_changes_nothing(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for action, extra in (("", {}), ("drop_everything", {}), ("remove", {"list": "notes", "id": "1"}), ("remove", {"list": "events", "id": "nope"})):
            self.assertLess(self.post(client, action, **extra).status_code, 400, (action, extra))
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])



    # -- the total is the planner's
    def test_with_no_number_typed_the_page_asks_for_one_and_makes_nothing_up(self):
        body = self.text(self.view())
        self.assertIn("Type the contacts you expect for this week", body)
        self.assertNotIn('id="tbl-calls"', body)
        self.assertNotIn('id="tbl-needs"', body)
        self.assertIn("Help with the number (optional)", body)
        self.assertIn("It is never used unless you press Use the suggestion", body)

    def test_a_number_typed_shows_everything_from_it(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        body = self.text(client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                                                "action": "preview", "total": "1000"}))
        for part in ('id="tbl-calls"', 'id="tbl-needs"', "Contacts forecast", "Needed on the floor at the peak", "Contacts, like the input sheet", "interval by interval"):
            self.assertIn(part, body, part)
        table = re.search(r'<table class="vol-grid" id="tbl-calls">(.*?)</table>', body, re.S).group(1)
        self.assertEqual(sum(int(x) for x in re.findall(r"<td[^>]*>(\d+)</td>", table)), 1000)
        self.assertNotIn("Type the contacts you expect for this week", body)

    def test_the_weeks_are_labelled_as_the_pattern(self):
        body = self.text(self.view())
        self.assertIn("Weeks for the pattern", body)
        self.assertIn("The number is yours", body)
        self.assertNotIn("Weeks of history", body)

    def test_the_requirement_workbook_needs_a_saved_forecast(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/volumes/requirements.xlsx", query_string={"program": self.alpha, "week": self.week}, follow_redirects=True)
        self.assertIn("Save a forecast for at least one channel first", self.text(got))

    # -- the workbook with live formulas
    def test_the_formulas_workbook_is_this_channel_as_the_page_shows_it(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/volumes/formulas.xlsx", query_string={"program": self.alpha, "channel": "Phone", "week": self.week, "total": "8000", "hist_weeks": "4"})
        self.assertEqual(got.status_code, 200)
        self.assertIn("Volumes_Phone_formulas_", got.headers["Content-Disposition"])
        wb = load_workbook(io.BytesIO(got.data))
        self.assertEqual(wb.sheetnames, ["Read me", "Phone"])
        ws = wb["Phone"]
        self.assertEqual(sum(ws.cell(r, c).value for r in range(14, 14 + 1440 // self.step) for c in range(2, 9)), 8000)
        self.assertTrue(str(ws.cell(14, 10).value).startswith("=IF("))

    def test_an_interval_program_or_a_bad_request_has_no_formulas_workbook(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        for bad in ({"hist_weeks": "2", "total": "8000"}, {"total": "abc"}):
            self.assertEqual(client.get("/volumes/formulas.xlsx", query_string={"program": self.alpha, "week": self.week, **bad}).status_code, 400, bad)
        ProgramBook(self.store).set_measure(self.alpha_id, "interval")
        self.assertEqual(client.get("/volumes/formulas.xlsx", query_string={"program": self.alpha, "week": self.week, "total": "8000"}).status_code, 404)

    def test_the_formulas_workbook_is_walled_like_the_rest(self):
        self.assertEqual(sign_in(self.app, "plan_a", PASSWORD).get("/volumes/formulas.xlsx", query_string={"program": self.bravo}).status_code, 403)
        self.assertEqual(self.app.test_client().get("/volumes/formulas.xlsx").status_code, 302)
        self.assertEqual(sign_in(self.app, "tm_a", PASSWORD).get("/volumes/formulas.xlsx", query_string={"program": self.alpha, "week": self.week,
                                                                                                          "total": "8000"}).status_code, 200)

    def test_the_page_offers_the_workbook_and_the_function_to_copy(self):
        body = self.text(self.view(total="8000"))
        self.assertIn("Download with live =AGENTS formulas (Excel)", body)
        self.assertIn('data-copy-text="#agents-lambda"', body)
        self.assertIn("=LAMBDA(calls, aht, interval, target, secs, maxocc", body)
        self.assertRegex(body, r'href="[^"]*formulas\.xlsx[^"]*hist_weeks=6')


    def test_weeks_at_the_edge_of_the_calendar_never_crash_a_page_or_a_download(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        tok = token(client)
        for week in ("0001-01-05", "0001-06-01", "2014-12-28", "2101-01-03", "9999-12-25", "9999-12-31"):
            for tab in ("actuals", "forecast", "how", "settings"):
                self.assertLess(client.get("/volumes", query_string={"program": self.alpha, "tab": tab, "week": week}).status_code, 500, (tab, week))
            for path, extra in (("/volumes/table.xlsx", {"what": "calls", "total": "100"}), ("/volumes/table.xlsx", {"what": "actual"}),
                                ("/volumes/formulas.xlsx", {"total": "100"}), ("/volumes/draft.xlsx", {}), ("/volumes/requirements.xlsx", {})):
                self.assertLess(client.get(path, query_string={"program": self.alpha, "week": week, **extra}).status_code, 500, (path, week))
            for path, form in (("/volumes/forecast", {"action": "preview", "total": "100"}), ("/volumes/forecast", {"action": "save", "total": "100"}),
                               ("/volumes/drivers", {"action": "last_year", "ly.Phone": "5"}), ("/volumes/drivers", {"action": "growth", "method": "measured"})):
                self.assertLess(client.post(path, data={"program": self.alpha, "csrf_token": tok, "channel": "Phone", "week": week, **form}).status_code, 500, (path, week))
        self.assertEqual(self.vb.drivers(self.alpha)["last_year"], {})                  # a write to a week that is not one is refused, not moved to another week
        self.assertEqual(self.vb.drivers(self.alpha)["growth"]["yoy"], {})
        self.assertIsNone(self.store.volume_forecast(self.alpha, "Phone", self.week))
        for week in ("0001-01-05", "9999-12-31"):
            got = client.post("/volumes/actuals/check", data={"program": self.alpha, "csrf_token": tok, "channel": "Phone", "week": week,
                                                              "paste": "Interval\tMon\n09:00\t5"})
            self.assertIn("Nothing was saved", html.unescape(got.get_data(as_text=True)), week)

    # -- panels stay open where the person is working
    def test_a_panel_with_entries_is_open_and_so_is_the_one_that_refused_an_answer(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertNotIn("<details open><summary>Promotions", self.view(client).get_data(as_text=True))
        bad = self.post(client, "add_event", **self.event(change="900")).get_data(as_text=True)
        self.assertIn("<details open><summary>Promotions", bad)
        self.assertNotIn("<details open><summary>AI and automation", bad)
        self.post(client, "add_event", **self.event())
        self.assertIn("<details open><summary>Promotions", self.view(client).get_data(as_text=True))
        wrong = self.post(client, "add_ai", ai_channel="Phone", start=self.week, end=self.week, change="abc").get_data(as_text=True)
        self.assertIn("<details open><summary>AI and automation", wrong)
        self.post(client, "growth", **{"yoy.Phone": "8", "method": "measured"})
        self.assertIn("<details open><summary>Customer growth", self.view(client).get_data(as_text=True))

    def test_the_definitions_box_has_a_name_for_a_screen_reader(self):
        body = self.view(total="8000").get_data(as_text=True)
        self.assertRegex(body, r'<pre id="agents-lambda"[^>]*role="region"[^>]*aria-label="[^"]+"')

    # -- walls
    def test_only_those_who_may_change_volumes_can_change_drivers(self):
        client = sign_in(self.app, "tm_a", PASSWORD)
        self.assertEqual(self.post(client, "add_event", **self.event()).status_code, 403)
        self.assertEqual(self.vb.drivers(self.alpha)["events"], [])
        self.assertIn(sign_in(self.app, "assoc_a", PASSWORD).post("/volumes/drivers", data={"program": self.alpha, "action": "add_event"}).status_code,
                      (302, 400, 403))

    def test_a_team_manager_can_read_the_questions_but_not_answer_them(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, "add_event", **self.event())
        body = self.text(self.view(sign_in(self.app, "tm_a", PASSWORD)))
        self.assertIn("Black Friday", body)
        self.assertNotIn('value="add_event"', body)
        self.assertNotIn('value="remove"', body)

    def test_another_program_is_walled_off(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.post("/volumes/drivers", data={"program": self.bravo, "csrf_token": token(client), "action": "add_event", **self.event()})
        self.assertEqual(got.status_code, 403)
        self.assertEqual(self.vb.drivers(self.bravo)["events"], [])

    def test_the_token_is_needed(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(client.post("/volumes/drivers", data={"program": self.alpha, "action": "add_event", **self.event()}).status_code, 400)

    def test_what_was_done_is_recorded(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        self.post(client, "add_event", **self.event())
        self.assertIn("volumes_drivers_saved", [e["kind"] for e in self.store.list_events(0, 4e9, self.alpha)])

    # -- hostile input
    def test_every_new_query_value_is_refused_or_escaped(self):
        hostile = ["<script>alert(1)</script>", "' or 1=1 --", "../../etc/passwd", "%00", "9" * 400, "{{7*7}}"]
        for value in hostile:
            for key in ("hist_weeks", "base", "skip", "total", "week"):
                got = self.view(**{key: value}, **({"skip_sent": "1"} if key == "skip" else {}))
                self.assertLess(got.status_code, 500, (key, value))
                self.assertNotIn("<script>alert(1)</script>", got.get_data(as_text=True), (key, value))

    def test_a_thousand_left_out_weeks_are_bounded(self):
        got = self.view(total="8000", skip_sent="1", skip=[f"2026-01-{d:02d}" for d in range(1, 29)] * 60)
        self.assertLess(got.status_code, 500)

    def test_the_downloads_follow_the_page_and_a_bad_request_is_a_400(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "week": self.week, "what": "calls", "total": "8000", "hist_weeks": "4"})
        self.assertEqual(got.status_code, 200)
        ws = load_workbook(io.BytesIO(got.data)).active
        self.assertEqual(sum(c.value or 0 for row in ws.iter_rows(min_row=2, min_col=2) for c in row), 8000)
        for bad in ({"hist_weeks": "2"}, {"total": "abc"}):
            self.assertEqual(client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "week": self.week, "what": "calls", **bad}).status_code,
                             400, bad)
        self.assertEqual(client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "week": self.week, "what": "calls",
                                                                         "base": "last_year"}).status_code, 404)     # nothing to start from: no grid

    def test_a_saved_forecast_downloads_as_saved(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        client.post("/volumes/forecast", data={"program": self.alpha, "csrf_token": token(client), "channel": "Phone", "week": self.week,
                                               "action": "save", "total": "9,000"})
        self.history(self.alpha, per_week=20000)
        ws = load_workbook(io.BytesIO(client.get("/volumes/table.xlsx", query_string={"program": self.alpha, "week": self.week, "what": "calls"}).data)).active
        self.assertEqual(sum(c.value or 0 for row in ws.iter_rows(min_row=2, min_col=2) for c in row), 9000)
        link = re.search(r'href="([^"]*table\.xlsx[^"]*what=calls[^"]*)"', self.text(self.view(client))).group(1)
        self.assertNotIn("total=", link)                                    # a saved forecast is downloaded as saved, not worked out again


if __name__ == "__main__":
    unittest.main()
