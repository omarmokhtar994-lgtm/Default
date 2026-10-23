# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AY (owner, 2026-10-23: "Coaching is showing as a small bar above the timeline, I would prefer to see it the same as breaks
with different colors based on the reason"): on the Timeline a booked activity (coaching, meeting, training, system issue, task) is a
full-height box on the person's bar like a break, its class naming the reason so each reason has its own colour; an added break or
lunch is the break's own colour; the legend names the reasons that are on the day. Overtime and VTO are drawn as before."""
import html
import re
import unittest

from webapp.tests.test_av_sessions import WED, _Sessions, hm


class TheActivityBars(_Sessions):
    def timeline(self):
        got = self.client.get("/day", query_string={"program": self.key, "date": WED.isoformat(), "view": "timeline"})
        return html.unescape(got.get_data(as_text=True))

    def test_coaching_is_a_full_height_box_with_its_reason_in_the_class(self):
        names, start = self.booked(2)
        body = self.timeline()
        bars = re.findall(r'<rect class="tl-act aux k-coaching[^"]*"[^>]*>', body)
        self.assertEqual(len(bars), 2)
        for bar in bars:
            self.assertIn('y="5"', bar)
            self.assertIn('height="20"', bar)
            self.assertNotIn("hatch", bar)

    def test_a_meeting_has_its_own_class_and_the_legend_names_the_reasons_on_the_day(self):
        names = self.present(2)
        start = self.free(names)[0]
        self.days.add_activity(self.key, WED, names[0], "Coaching", hm(start), hm(start + 30), self.omar)
        self.days.add_activity(self.key, WED, names[1], "Meeting", hm(start), hm(start + 30), self.omar)
        self.addCleanup(self.clear)
        body = self.timeline()
        self.assertIn("tl-act aux k-coaching", body)
        self.assertIn("tl-act aux k-meeting", body)
        legend = re.search(r'<p class="legend2">.*?</p>', body, re.S).group(0)
        self.assertIn('class="k aux k-coaching"', legend)
        self.assertIn('class="k aux k-meeting"', legend)
        self.assertNotIn("k-training", legend)

    def test_an_added_break_is_drawn_in_the_breaks_colour(self):
        name = self.present(1)[0]
        lo = self.free([name])[0]
        self.days.add_activity(self.key, WED, name, "Break", hm(lo), hm(lo + 15), self.omar)
        self.addCleanup(self.clear)
        self.assertRegex(self.timeline(), r'<rect class="tl-act aux k-break[^"]*"[^>]*height="20"')
        css = open("webapp/static/app.css", encoding="utf-8").read()
        self.assertIn(".tl-act.aux.k-break", css)


if __name__ == "__main__":
    unittest.main()
