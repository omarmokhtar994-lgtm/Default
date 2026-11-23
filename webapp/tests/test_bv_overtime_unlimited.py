# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BV (owner, 2026-11-23: "The website is not accepting OT more than 4 hours make it unlimited with warnings"): overtime of any length is kept;
more than 4 hours (OVERTIME_MAX) says a warning, as a broken rest gap already does. Still refused: overtime that runs into the person's own shift the
day before or after (one person cannot work both), and overtime before a shift that would start the day before (unchanged)."""
import html
import re
import unittest

from webapp.tests.test_overtime_side import DAY, LATE, MIDNIGHT, NIGHT, WED, _Overtime


class AnyLength(_Overtime):
    def test_six_hours_after_a_day_shift_is_kept_with_a_warning(self):
        found = self.add(LATE, "after", 360)  # 08:00 to 17:00: 17:00 to 23:00
        self.assertEqual((found["lo"], found["hi"]), (1020, 1380))
        self.assertIn("6 hours of overtime, more than 4", found["warning"])

    def test_eight_hours_before_a_night_shift_is_kept_with_a_warning(self):
        found = self.add(NIGHT, "before", 480)  # 21:00 to 06:00: 13:00 to 21:00
        self.assertEqual((found["lo"], found["hi"]), (780, 1260))
        self.assertIn("8 hours of overtime, more than 4", found["warning"])

    def test_ten_hours_after_a_night_shift_runs_into_the_next_day(self):
        found = self.add(NIGHT, "after", 600)  # ends 06:00 the next morning: 06:00 to 16:00
        self.assertEqual((found["lo"], found["hi"]), (1800, 2400))

    def test_four_hours_or_less_says_no_length_warning(self):
        for minutes in (60, 240):
            self.assertNotIn("more than 4", self.add(LATE, "after", minutes).get("warning", ""), minutes)

    def test_typed_times_over_four_hours_are_kept_too(self):
        # re-pinned from test_aj_overtime (refused with "Overtime is offered up to 4 hours."): the owner lifted the cap on 2026-11-23
        rec = self.days.add_activity(self.key, WED, LATE, "Overtime", "17:00", "21:05", 1, dry_run=True)
        self.assertEqual((rec["start"], rec["end"]), (1020, 1265))
        self.assertIn("more than 4", rec["warning"])
        rec = self.days.add_activity(self.key, WED, NIGHT, "Overtime", "12:00", "21:00", 1, dry_run=True)
        self.assertEqual((rec["start"], rec["end"]), (720, 1260))

    def test_overtime_into_the_persons_next_shift_is_refused(self):
        # DAY starts early on Thursday: 16 hours after Wednesday's 17:00 end reaches into that shift
        with self.assertRaises(ValueError) as said:
            self.add(DAY, "after", 960)
        self.assertIn("next shift", str(said.exception))

    def test_before_a_shift_starting_at_midnight_is_still_refused(self):
        with self.assertRaises(ValueError):
            self.add(MIDNIGHT, "before", 300)

    def test_it_is_kept_when_not_a_dry_run_and_the_page_says_the_warning(self):
        client_form = self.form(associate=LATE, side="after", minutes="420")
        reply = self.client.post("/day/add", data=client_form, follow_redirects=True)
        page = html.unescape(reply.get_data(as_text=True))
        self.assertIn(f"Recorded: {LATE}", page)
        self.assertIn("7 hours of overtime, more than 4", page)
        kept = [r for r in self.store.list_activities(self.key, [WED.isoformat()]) if r["associate"] == LATE and r["kind"] == "Overtime"]
        self.assertEqual([(r["start"], r["end_min"]) for r in kept], [(1020, 1440)])
        self.store.delete_activity(kept[0]["id"])

    def test_the_preview_says_the_warning(self):
        reply = self.client.post("/day/add-preview", data=self.form(associate=LATE, side="after", minutes="300"))
        self.assertEqual(reply.status_code, 200, reply.get_data(as_text=True))
        self.assertIn("more than 4", reply.get_json()["text"])
        self.assertEqual(reply.get_json()["level"] if reply.get_json()["level"] == "bad" else "warn", reply.get_json()["level"])


class TheDialog(_Overtime):
    def test_add_offers_overtime_lengths_up_to_16_hours_for_overtime_only(self):
        page = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}"
                                             f"&view=board&add=480&person={DAY.replace(' ', '+')}").get_data(as_text=True))
        select = re.search(r'(?s)<select name="minutes">.*?</select>', page).group(0)
        for h in range(5, 17):
            self.assertRegex(select, rf'<option value="{h * 60}" data-ot-only[^>]*>{h} h</option>')
        self.assertIn('<option value="240"', select)
        self.assertNotRegex(select, r'value="240" data-ot-only')


if __name__ == "__main__":
    unittest.main()
