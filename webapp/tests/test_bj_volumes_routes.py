# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04): the pages end to end for the draft workbook (download, fill, upload), the grid typed on the site, and the forecast with the
weeks used, the events, AI periods, growth and last year. The walls and the check-then-save rule hold for every new way in."""
import html
import io
import re
import unittest
from datetime import date, timedelta

from openpyxl import load_workbook

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


if __name__ == "__main__":
    unittest.main()
