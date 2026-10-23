# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "I can't find an option to remove support from outside the roster"; answer: make 1 and 2): the cover
from outside the roster could be deleted only from a small "Delete" link in the list on the Overtime and VTO tab. Now (1) that
link is a button that says "Delete cover", and (2) the cover's entry on the Interval board has a "Remove" button beside it, which
brings the person back to the board."""
import html
import re
import unittest

from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token

NAME = "Made-up Support 01"


class TheCoverCanBeRemoved(_Overtime):
    def setUp(self):
        letters = self.days.page(self.key, WED)["view"].get("channels")
        channel = next((r["letter"] for r in (letters or {}).get("rows", []) if "language" not in r), "")
        self.cover = self.days.add_cover(self.key, WED, NAME, "Support", "10:00", "12:00", 1, channel=channel)
        self.addCleanup(lambda: self.days.store.get_cover(self.cover) and self.days.cancel_cover(self.key, WED, self.cover, 1))

    def page(self, view):
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": view})
        return html.unescape(got.get_data(as_text=True))

    def test_the_list_on_the_overtime_tab_says_delete_cover(self):
        body = self.page("cover")
        found = re.search(r'<button[^>]*class="[^"]*danger[^"]*"[^>]*aria-label="Delete the cover of ' + NAME + r'[^"]*"[^>]*>([^<]*)</button>', body)
        self.assertTrue(found, "no delete button for the cover")
        self.assertEqual(found.group(1).strip(), "Delete cover")

    def test_the_board_entry_has_a_remove_button_for_that_cover(self):
        body = self.page("board")
        form = re.search(r'<form[^>]*action="/day/cover/cancel"[^>]*>(?:(?!</form>).)*name="id" value="' + str(self.cover) +
                         r'"(?:(?!</form>).)*</form>', body, re.S)
        self.assertTrue(form, "no remove form for the cover on the board")
        self.assertIn('name="view" value="board"', form.group(0))
        self.assertIn(f"Remove the cover of {NAME}", form.group(0))
        self.assertEqual(len(re.findall(r'action="/day/cover/cancel"', body)), 1)

    def test_removing_from_the_board_keeps_the_person_on_the_board(self):
        got = self.client.post("/day/cover/cancel", data={"csrf_token": token(self.client), "program": self.key,
                                                          "date": WED.isoformat(), "id": str(self.cover), "view": "board"})
        self.assertEqual(got.status_code, 303)
        self.assertIn("view=board", got.headers["Location"])
        self.assertEqual(self.days.covers(self.key, WED), [])
        body = html.unescape(self.client.get(got.headers["Location"]).get_data(as_text=True))
        self.assertNotIn("from outside the roster, covering", body)

    def test_removing_from_the_list_still_goes_back_to_that_tab(self):
        got = self.client.post("/day/cover/cancel", data={"csrf_token": token(self.client), "program": self.key,
                                                          "date": WED.isoformat(), "id": str(self.cover), "view": "cover"})
        self.assertIn("view=cover", got.headers["Location"])
        self.assertEqual(self.days.covers(self.key, WED), [])

    def test_the_cover_of_last_night_is_not_offered_a_remove_button_on_this_day(self):
        # a cover that began yesterday and runs past midnight shows on this day's board, but it belongs to yesterday's list
        yesterday = WED.replace(day=WED.day - 1)
        letters = self.days.page(self.key, yesterday)["view"].get("channels")
        channel = next((r["letter"] for r in (letters or {}).get("rows", []) if "language" not in r), "")
        late = self.days.add_cover(self.key, yesterday, "Made-up Support 02", "Support", "22:00", "02:00", 1, channel=channel)
        self.addCleanup(lambda: self.days.store.get_cover(late) and self.days.cancel_cover(self.key, yesterday, late, 1))
        body = self.page("board")
        self.assertNotIn(f'name="id" value="{late}"', body)


if __name__ == "__main__":
    unittest.main()
