# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "call in and overtime should show on the time line and I can have the option to schedule breaks for them,
especially for call in"): a person called in on a day off for typed times that no one else works has no breaks (a call-in copies the breaks
of someone on the same shift, and nobody is). "Plan their breaks" places them by the same rules as the rest of the day: the breaks the
workbook says a shift of that length takes, at the times the intervals' buffer and the usual shape give, kept as breaks added on the day.
The timeline already draws the call-in as a bar and overtime beside the shift (checked here too). Made-up names, Wednesday 14 Oct."""
import html
import re
import unittest

from webapp.break_plan import fit, slots_for
from webapp.tests import test_attendance as ta
from webapp.tests.test_attendance import WED

AR = "AE/AR B2B"
OFF = "Associate 004"  # off on Wednesday (Tuesday night shift)
CUSTOM = ("10:30", "16:30")  # six hours: nobody works exactly this, so a call-in has no pattern to copy


class TheCallInBreaks(unittest.TestCase):
    setUpClass = classmethod(ta.TheAttendance.setUpClass.__func__)
    tearDownClass = classmethod(ta.TheAttendance.tearDownClass.__func__)
    setUp = ta.TheAttendance.setUp

    def called_in(self):
        self.days.add_activity(AR, WED, OFF, "Called in", *CUSTOM, self.sara)

    def extra(self):
        return sorted((r["start"], r["end_min"], r["kind"]) for r in self.store.list_activities(AR, [WED.isoformat()])
                      if r["associate"] == OFF and r["kind"] in ("Break", "Lunch"))

    def test_a_call_in_for_typed_times_has_no_breaks_to_begin_with(self):
        self.called_in()
        seg = next(s for l in self.days.page(AR, WED)["view"]["lanes"] if l["name"] == OFF for s in l["segments"] if s["offset"] == 0)
        self.assertEqual(seg["breaks"], [])

    def test_planning_places_the_breaks_the_rules_give_a_shift_of_that_length(self):
        self.called_in()
        rules = self.book.break_rules(self.tool["id"])
        made = self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        wanted = slots_for(rules, 360)
        self.assertEqual(len(made), len(wanted))
        extra = self.extra()
        self.assertEqual(len(extra), len(wanted))
        self.assertEqual(sorted(e[1] - e[0] for e in extra), sorted(m for _, m in wanted))
        lo, hi = 10 * 60 + 30, 16 * 60 + 30
        for start, end, kind in extra:
            self.assertTrue(lo <= start and end <= hi, (start, end))

    def test_the_breaks_keep_the_engines_gaps_and_do_not_overlap(self):
        self.called_in()
        rules = self.book.break_rules(self.tool["id"])
        self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        starts = [e[0] for e in self.extra()]
        self.assertEqual(fit(rules, "10:30 - 16:30", starts)[1], 0)  # no engine rule broken
        spans = self.extra()
        for (a0, a1, _), (b0, b1, _) in zip(spans, spans[1:]):
            self.assertLessEqual(a1, b0)

    def test_they_show_on_the_day_as_breaks_added_and_the_log_says_so(self):
        self.called_in()
        self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        seg = next(s for l in self.days.page(AR, WED)["view"]["lanes"] if l["name"] == OFF for s in l["segments"] if s["offset"] == 0)
        self.assertTrue([a for a in seg["activities"] if a["kind"] in ("Break", "Lunch")])
        said = " ".join(e["what"] for e in self.days.page(AR, WED)["log"] if e["associate"] == OFF)
        self.assertRegex(said, r"Break \d\d:\d\d to \d\d:\d\d")
        self.assertIn("Lunch", said)

    def test_a_person_who_already_has_breaks_or_is_not_called_in_is_refused(self):
        with self.assertRaises(ValueError) as refused:
            self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)  # not called in
        self.assertIn("called in", str(refused.exception))
        self.called_in()
        self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        with self.assertRaises(ValueError) as again:
            self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        self.assertIn("already has breaks", str(again.exception))

    def test_undo_takes_all_of_them_back(self):
        self.called_in()
        self.days.plan_call_in_breaks(AR, WED, OFF, self.sara)
        self.days.undo_last(AR, WED, self.sara)
        self.assertEqual(self.extra(), [])


class ThePage(unittest.TestCase):
    """The ready schedule of Wed 14 Oct through the website."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_overtime_side import _Overtime
        cls.ot = _Overtime
        cls.ot.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.ot.tearDownClass()

    def setUp(self):
        self.client, self.days, self.key, self.store = self.ot.client, self.ot.days, self.ot.key, self.ot.store
        self.days.add_activity(self.key, WED, OFF, "Called in", *CUSTOM, 1)
        self.days.add_activity(self.key, WED, "Associate 008", "Overtime", "17:00", "18:00", 1)

        def clean():
            for r in self.store.list_activities(self.key, [WED.isoformat()]):
                self.store.delete_activity(r["id"])
        self.addCleanup(clean)

    def page(self, view):
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": view})
        return html.unescape(got.get_data(as_text=True))

    def test_the_timeline_draws_the_call_in_as_a_bar_and_the_overtime_beside_the_shift(self):
        body = self.page("timeline")
        lane = lambda name: re.search(r'<div class="tl-row tl-lane".{0,300}?' + name + r'.*?</svg>', body, re.S).group(0)
        self.assertIn('class="tl-bar called"', lane(OFF))
        self.assertIn('class="tl-act ot"', lane("Associate 008"))

    def test_the_activities_list_offers_to_plan_the_breaks_of_a_call_in_without_any(self):
        from webapp.tests.test_runs import token
        body = self.page("cover")
        form = re.search(r'<form[^>]*action="/day/call-in/breaks"[^>]*>(?:(?!</form>).)*name="associate" value="' + OFF +
                         r'"(?:(?!</form>).)*</form>', body, re.S)
        self.assertTrue(form, "no Plan their breaks form")
        self.assertIn("Plan their breaks", form.group(0))
        data = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', form.group(0)))
        got = self.client.post("/day/call-in/breaks", data=data)
        self.assertEqual(got.status_code, 303)
        self.assertTrue([r for r in self.store.list_activities(self.key, [WED.isoformat()])
                         if r["associate"] == OFF and r["kind"] in ("Break", "Lunch")])
        self.assertNotRegex(self.page("cover"), r'action="/day/call-in/breaks"[^>]*>(?:(?!</form>).)*name="associate" value="' + OFF + '"')

    def test_a_call_in_that_has_breaks_is_not_offered_the_button(self):
        self.days.plan_call_in_breaks(self.key, WED, OFF, 1)
        self.assertNotRegex(self.page("cover"), r'action="/day/call-in/breaks"[^>]*>(?:(?!</form>).)*name="associate" value="' + OFF + '"')


if __name__ == "__main__":
    unittest.main()
