# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AK item 3 (owner, 2026-10-15: "For fix the day, rescue, etc they should work on 24 hours based on day start
at not fixed 00;00"): Fix the day's breaks, Rescue the day and Change several breaks work on the 24 hours from the
start picked, as the Timeline does; each change is kept on its shift's own date, and one Undo takes a change back."""
import unittest
from datetime import date

from webapp.tests import test_attendance as ta

AR = "AE/AR B2B"
WED, THU = date(2026, 10, 14), date(2026, 10, 15)
START = 7 * 60


class TheWindow(ta.TheAttendance.__bases__[0]):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def window(self):
        return self.days.window_page(AR, WED, START)

    def thursday_break(self):
        """A break of a shift kept on Thursday that falls inside the window (before 07:00 Thursday)."""
        view = self.window()["view"]
        for lane in view["lanes"]:
            for seg in lane["segments"]:
                if seg["offset"] == 0 and seg["date"] == THU and seg["breaks"]:
                    return lane["name"], seg, seg["breaks"][0]
        self.skipTest("the fixture has no Thursday shift with a break before 07:00")

    def test_the_window_holds_both_days(self):
        view = self.window()["view"]
        dates = {s["date"] for l in view["lanes"] for s in l["segments"] if s["offset"] == 0}
        self.assertEqual(dates, {WED, THU})
        self.assertEqual((view["cells"][0]["t"], view["start"]), (START, START))

    def test_from_midnight_nothing_changes(self):
        page = self.days.page(AR, WED)
        self.assertEqual(self.days.replan(page)["moves"], self.days.replan_window(AR, WED, 0)["moves"])

    def short(self):
        """Sick people on both days, so the window has short intervals for the tools to work on."""
        for on in (WED, THU):
            view = self.days.page(AR, on)["view"]
            present = [l["name"] for l in view["lanes"] if any(s["offset"] == 0 for s in l["segments"])]
            for name in present[::3]:
                self.days.set_status(AR, on, name, "Sick", self.sara)

    def test_fix_breaks_moves_carry_their_date(self):
        self.short()
        found = self.days.replan_window(AR, WED, START)
        self.assertTrue(found["moves"])
        for m in found["moves"]:
            self.assertIn(m["date"], (WED, THU))
            self.assertEqual(m["to"], m["day_to"] + 1440 * (m["date"] - WED).days)  # window minute vs its own day
            self.assertGreaterEqual(m["to"], START)

    def test_a_thursday_break_is_kept_on_thursday(self):
        name, seg, b = self.thursday_break()
        new = b["start"] + 15 if b["start"] + 15 + b["minutes"] <= seg["end"] else b["start"] - 15
        self.days.apply_replan(AR, WED, [(name, b["idx"], new - 1440, THU)], self.sara)
        kept = [(r["associate"], r["idx"], r["start"]) for r in self.store.list_actual_breaks(AR, [THU.isoformat()])]
        self.assertIn((name, b["idx"], (new - 1440) % 1440), kept)
        self.assertEqual(self.store.list_actual_breaks(AR, [WED.isoformat()]), [])
        self.days.undo_last(AR, WED, self.sara)  # one Undo, from the page's day, takes it back
        self.assertEqual(self.store.list_actual_breaks(AR, [THU.isoformat()]), [])

    def test_several_breaks_reach_a_thursday_shift(self):
        name, _, b = self.thursday_break()
        found = self.days.bulk_preview(AR, WED, [name], "all", "shift", 15, start=START)
        moved = [c for c in found["changes"] if c["name"] == name]
        self.assertTrue(moved)
        self.assertTrue(all(c["date"] == THU for c in moved))

    def test_rescue_moves_carry_their_date(self):
        self.short()
        found = self.days.rescue_plan(AR, WED, None, start=START)
        self.assertTrue(found["moves"], found["said"])
        for m in found["moves"]:
            self.assertIn(m["date"], (WED, THU))
            self.assertGreaterEqual(m["to"], START)


from webapp.tests import test_overtime_side as ots  # noqa: E402
from webapp.tests.test_runs import token  # noqa: E402


class ThePage(ots._Overtime):
    def test_the_tools_say_they_work_on_the_window(self):
        import html
        url = f"/day?program={self.key.replace(' ', '+')}&date=2026-10-14&tz=Africa/Cairo&start=07:00&view=replan"
        body = html.unescape(self.client.get(url).get_data(as_text=True))
        self.assertIn("Fix the rest of the day's breaks", body)
        self.assertNotIn("Rescue the day, Fix breaks and Change several breaks work on the schedule's day", body)


class TheApply(unittest.TestCase):
    """The AE/AR B2B week (with breaks), served as the website serves it."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_runs import REPO, client_for, make_app, versioned_run
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        versioned_run(cls.app, cls.store, cls.client, program=AR, week_start="2026-10-11")
        cls.days = cls.app.extensions["days"]

    def test_a_dated_move_from_the_form_is_kept_on_its_date(self):
        import html
        view = self.days.window_page(AR, WED, START)["view"]
        name, seg, b = next((l["name"], s, s["breaks"][0]) for l in view["lanes"] for s in l["segments"]
                            if s["offset"] == 0 and s["date"] == THU and s["breaks"])
        new = b["start"] + 15 - 1440 if b["start"] + 15 + b["minutes"] <= seg["end"] else b["start"] - 15 - 1440
        got = self.client.post("/day/replan/apply", data={"csrf_token": token(self.client), "program": AR,
                                                          "date": "2026-10-14", "start": "420",
                                                          "move": f"{name}|{b['idx']}|{new}|2026-10-15"},
                               follow_redirects=True)
        self.assertIn("Moved 1 break.", html.unescape(got.get_data(as_text=True)))
        kept = [(r["associate"], r["start"]) for r in self.store.list_actual_breaks(AR, ["2026-10-15"])]
        self.assertIn((name, new % 1440), kept)
