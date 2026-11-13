# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): one calendar day, in any zone and from any start time.

"i dont need operating day to be something different than calendar day when i change timezone or change day start
time it should all be on the same calendar day options with everything"; "by changing the start time it should keep it
for all tabs timeline, interval board adherence etc"; "break should show in the new time zone and can be changed but
thing is being sent to the associates on the notification channel ... the time should be based the schedule default".

- The zone and the day's start are options on the RTA itself, kept while moving between tabs and days.
- The Timeline, the Interval board and Adherence show the 24 hours from the start, stitched from the schedule's days;
  the other tabs work on the schedule's day, with every time in the zone picked.
- Every time shown or typed is in the zone picked; the server turns typed times back into the schedule's own zone, so
  the day's records, its change log and the group posts keep the schedule's time.
Made-up "Associate NN" data.
"""
import html
import re
import unittest
from datetime import date, timedelta

from webapp.attendance import hm
from webapp.channels import hm as channel_hm
from webapp.clock import moved_text, shown, to_schedule
from webapp.day import _hm, window_view

ON = date(2026, 10, 14)
NY = -420  # New York is 7 hours behind Cairo in October


def seg(start, end, offset=0, status="Present", breaks=(), label="", acts=()):
    return {"offset": offset, "called_in": False, "label": label or f"{_hm(start)} - {_hm(end)}", "start": start,
            "end": end, "status": status, "billable": False, "from": None, "to": None, "away": (0, 0),
            "breaks": [{"idx": i, "kind": k, "start": s, "planned_start": s, "minutes": m, "moved": False}
                       for i, (k, s, m) in enumerate(breaks)],
            "cancelled": [], "activities": [{"kind": k, "start": a, "end": b, "billable": False, "id": 1}
                                            for k, a, b in acts],
            "with_whom": "", "why": "", "with_dept": ""}


def lane(name, *segments):
    return {"name": name, "slot": "", "language": "English", "segments": list(segments)}


def day(need, lanes=(), languages=None, channels=None):
    cells = [{"t": t, "required": need, "plan": need, "now": need, "slots": [need] * 12, "low": need, "need": need,
              "pm": 0.0 if need else None, "plan_pm": 0.0 if need else None, "cls": "ok" if need else "none",
              "absent": 0, "aux": 0, "late_early": 0, "breaks": 0, "overtime": 0, "vto": 0}
             for t in range(0, 1440, 60)]
    return {"interval": 60, "measure": "interval", "lanes": list(lanes), "cells": cells,
            "languages": languages or [], "tiles": {}, "channels": channels}


class TheClockShown(unittest.TestCase):
    def test_times_shown_in_the_zone_picked(self):
        with shown(NY):
            self.assertEqual((_hm(0), hm(30), channel_hm(60)), ("17:00", "17:30", "18:00"))
        self.assertEqual((_hm(0), hm(30), channel_hm(60)), ("00:00", "00:30", "01:00"))  # the schedule's own

    def test_texts_and_typed_times(self):
        self.assertEqual(moved_text("Break 1 moved 14:00 to 14:30, 2 h 20 min", NY),
                         "Break 1 moved 07:00 to 07:30, 2 h 20 min")
        self.assertEqual(moved_text("Lunch at 03:00", NY), "Lunch at 20:00")
        self.assertEqual(to_schedule("07:30", NY), "14:30")
        self.assertEqual(to_schedule("20:00", NY), "03:00")
        self.assertEqual(to_schedule("not a time", NY), "not a time")  # the DayBook refuses it as before
        self.assertEqual(to_schedule("", NY), "")


class TheWindow(unittest.TestCase):
    def test_cells_from_both_days_in_the_days_minutes(self):
        found = window_view({0: day(1.0), 1: day(2.0)}, 960, ON)
        self.assertEqual(len(found["cells"]), 24)
        self.assertEqual((found["cells"][0]["t"], found["cells"][0]["required"]), (960, 1.0))
        self.assertEqual((found["cells"][8]["t"], found["cells"][8]["required"]), (1440, 2.0))
        self.assertEqual(found["cells"][8]["date"], ON + timedelta(days=1))
        self.assertEqual(found["start"], 960)

    def test_new_york_from_its_midnight(self):
        found = window_view({0: day(1.0), 1: day(2.0)}, -NY, ON)
        with shown(NY):
            self.assertEqual([_hm(c["t"]) for c in found["cells"][:2]], ["00:00", "01:00"])
        self.assertEqual(found["cells"][16]["required"], 1.0)  # Cairo's 23:00
        self.assertEqual(found["cells"][17]["required"], 2.0)  # Cairo's next 00:00

    def test_each_shift_once_with_its_own_day(self):
        night = seg(1320, 1860, breaks=[("Lunch", 1560, 30)])
        today = {0: day(1.0, [lane("Associate 07", night), lane("Associate 08", seg(480, 1020))]),
                 1: day(1.0, [lane("Associate 07", seg(-120, 420, offset=-1, breaks=[("Lunch", 120, 30)])),
                              lane("Associate 09", seg(480, 1020, breaks=[("Break 1", 600, 15)]))])}
        found = window_view(today, 960, ON)
        segs = {(l["name"], s["date"]): s for l in found["lanes"] for s in l["segments"]}
        self.assertEqual(len([k for k in segs if k[0] == "Associate 07"]), 1)  # not again from the next day
        evening = segs[("Associate 07", ON)]
        self.assertEqual((evening["start"], evening["end"], evening["offset"]), (1320, 1860, 0))
        self.assertEqual(evening["breaks"][0]["start"], 1560)
        tomorrow = segs[("Associate 09", ON + timedelta(days=1))]
        self.assertEqual((tomorrow["start"], tomorrow["end"], tomorrow["offset"]), (1920, 2460, 0))
        self.assertEqual(tomorrow["breaks"][0]["start"], 2040)
        begun = segs[("Associate 08", ON)]
        self.assertEqual((begun["start"], begun["offset"]), (480, -1))  # began before the window

    def test_two_shifts_in_the_window_each_have_their_own_card(self):
        """Found in the final review: a shift at 16:30 and the next day's at 15:30 both start in the 24 hours from
        16:00, so both are offset 0; hovering the first showed the second's card (its times and its breaks)."""
        from webapp.day import hover_tips
        both = {0: day(1.0, [lane("Associate 07", seg(990, 1500, breaks=[("Lunch", 1230, 30)]))]),
                1: day(1.0, [lane("Associate 07", seg(930, 1440, breaks=[("Lunch", 1170, 60)]))])}
        found = window_view(both, 960, ON)
        first, second = found["lanes"][0]["segments"]
        tips = hover_tips(found, 1200)
        for s, label, lunch in ((first, "16:30 - 01:00", "Lunch, 20:30 to 21:00"),
                                (second, "15:30 - 00:00", "Lunch, 19:30 to 20:30")):
            tip = tips[("Associate 07", s["offset"], s["start"])]
            self.assertEqual(tip["shift"][0], f"Associate 07, {label}")
            self.assertEqual(tip["breaks"][0][0], lunch)
        self.assertEqual(tips[("Associate 07", 0)]["shift"][0], "Associate 07, 16:30 - 01:00")  # the row's card

    def test_a_missing_day_shows_no_figures(self):
        found = window_view({0: day(1.0), 1: None}, 960, ON)
        late = found["cells"][10]
        self.assertEqual((late["required"], late["pm"], late["cls"]), (0, None, "none"))

    def test_languages_and_channels_from_both_days(self):
        def french(gap):
            return [{"name": "French", "start": 0, "end": 1440, "minimum": 1, "eligible": ["french"],
                     "cells": [{"t": t, "count": 0 if t == gap else 1, "cls": "bad" if t == gap else "lok",
                                "minimum": 1} for t in range(0, 1440, 60)], "gaps": 1}]

        def chat(cls, runs):
            return {"planned": True, "warnings": [], "runs": runs,
                    "rows": [{"name": "Chat", "letter": "C", "cells": [{"t": t, "need": 1.0, "have": 1.0, "cls": cls}
                                                                       for t in range(0, 1440, 60)]}]}
        found = window_view({0: day(1.0, languages=french(17 * 60), channels=chat("ok", {"Associate 07": [(900, 1500, "C")]})),
                             1: day(1.0, languages=french(60), channels=chat("bad", {"Associate 07": [(-540, 60, "C")]}))},
                            960, ON)
        row = found["languages"][0]
        self.assertEqual([c["cls"] for c in row["cells"][:3]], ["lok", "bad", "lok"])
        self.assertEqual((row["cells"][9]["t"], row["cells"][9]["cls"]), (1500, "bad"))
        chat_row = found["channels"]["rows"][0]
        self.assertEqual([c["cls"] for c in chat_row["cells"][7:9]], ["ok", "bad"])
        self.assertEqual(found["channels"]["runs"]["Associate 07"], [(960, 1500, "C")])  # one stretch, not two

    def test_the_tiles_count_the_window(self):
        short = day(2.0)
        for c in short["cells"]:
            if c["t"] >= 1200:
                c.update(now=1.0, pm=-1.0, cls="bad")
        found = window_view({0: short, 1: day(1.0)}, 960, ON)
        self.assertEqual((found["tiles"]["short_hours"], found["tiles"]["short_intervals"]), (4.0, 4))


class OneCalendarDay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_notify_daybook
        test_notify_daybook._Tagged.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_notify_daybook
        test_notify_daybook._Tagged.tearDownClass.__func__(cls)

    def url(self, **extra):
        args = "".join(f"&{k}={v}" for k, v in extra.items())
        return f"/day?program={self.key.replace(' ', '+')}&date={ON.isoformat()}{args}"

    def get(self, **extra):
        import html
        return html.unescape(self.client.get(self.url(**extra)).get_data(as_text=True))

    def first_break(self, skip=()):
        for lane_ in self.days.page(self.key, ON)["view"]["lanes"]:
            for s in lane_["segments"]:
                if lane_["name"] not in skip and s["offset"] == 0 and s["status"] == "Present" and s["breaks"]:
                    return lane_["name"], s["breaks"][0]
        self.fail("nobody with breaks")

    def tearDown(self):
        self.client.get(self.url(tz="Africa/Cairo", start="00:00"))  # each test starts from the usual day

    def test_new_york_is_the_whole_rta_and_can_be_changed(self):
        name, b = self.first_break()
        page = self.get(tz="America/New_York")
        self.assertIn("Who is on the floor", page)
        self.assertNotIn("Read only", page)
        self.assertRegex(page, rf'class="brk[^"]*" data-name="{name}" data-date="{ON.isoformat()}" '
                               rf'data-idx="{b["idx"]}" [^>]*data-start="{_hm(b["start"] + NY)}"')
        self.assertIn('<option value="America/New_York" selected>', page)

    def test_a_break_moved_in_new_york_keeps_the_schedules_time(self):
        name, b = self.first_break()
        for step in (5, 10, 15, -5, -10, 20):
            got = self.client.post("/day/break", data={"csrf_token": self.token(), "program": self.key,
                                                       "date": ON.isoformat(), "associate": name, "idx": b["idx"],
                                                       "at": _hm(b["start"] + step + NY), "tz": "America/New_York"})
            if got.status_code == 200:
                break
        self.assertEqual(got.status_code, 200, got.get_json())
        moved = next(x for l in self.days.page(self.key, ON)["view"]["lanes"] if l["name"] == name
                     for s in l["segments"] if s["offset"] == 0 for x in s["breaks"] if x["idx"] == b["idx"])
        self.assertEqual(moved["start"], b["start"] + step)
        post = self.store.notify_items(unit=self.key)[-1]
        self.assertEqual(post["text"], f"{b['kind']} moved {_hm(b['start'])} to {_hm(b['start'] + step)}")
        log = self.get(tz="America/New_York")
        self.assertIn(f"moved {_hm(b['start'] + NY)} to {_hm(b['start'] + step + NY)}", log)  # the log, shown in NY

    def test_the_day_from_another_start_on_every_view(self):
        page = self.get(start="16:00")
        self.assertIn('viewBox="960 0 1440 30"', page)
        self.assertRegex(page, r'<div class="tl-ticks"><span>16:00</span>')
        board = self.get(view="board")  # kept while moving between tabs
        first = re.search(r'<div class="rb-row rb-\w+" role="row" data-t="(\d+)"', board)
        self.assertGreaterEqual(int(first.group(1)), 960)
        self.assertIn('<option value="16:00" selected>', board)
        later = self.get(view="adherence")
        self.assertIn('<option value="16:00" selected>', later)

    def test_tomorrows_shift_in_the_window_posts_its_own_date(self):
        page = self.get(start="16:00")
        nxt = (ON + timedelta(days=1)).isoformat()
        self.assertRegex(page, rf'class="att[^"]*" data-name="[^"]+" data-date="{nxt}"')

    def test_two_shifts_in_the_window_each_show_their_own_card(self):
        # Associate 014 starts at 21:00, and at 19:00 the next day: both in the 24 hours from 20:00
        page = self.get(start="20:00")
        track = re.search(r'<svg class="tl-track"[^>]*aria-label="Associate 014: .*?</svg>', page, re.S).group(0)
        cards = re.findall(r'<rect class="tl-bar[^"]*"[^>]*><title>([^\n<]*)', track)
        self.assertEqual([c[:20] for c in cards], ["Associate 014, 21:00", "Associate 014, 19:00"])

    def test_the_other_tabs_work_on_the_schedules_day_in_the_zone(self):
        page = self.get(tz="America/New_York", start="16:00", view="cover")
        self.assertIn("work on the schedule's day", page)

    def test_the_note_on_those_tabs_reads_as_information_not_as_an_error(self):
        # owner, 2026-10-29: a team member took it for an error ("00:00 to 00:00 the next day", in the warning colour)
        page = self.get(start="13:00", view="cover")
        note = re.search(r'<p class="notice[^"]*">(Find a time, Overtime and Channels.*?)</p>', page, re.S)
        self.assertIsNotNone(note)
        text = html.unescape(note.group(1))
        self.assertIn("work on the schedule's day", text)
        self.assertNotIn("00:00 to 00:00", text)
        self.assertIn("midnight to midnight", text)
        self.assertIn("show the 24 hours from 13:00 instead", text)
        self.assertIn('<p class="notice calm">', page)  # not the amber warning look

    def test_the_operating_day_is_one_of_the_starts(self):
        self.store.set_day_start(self.key, 16 * 60, self.omar)
        page = self.get()
        self.assertIn('<option value="16:00">16:00, the operating day</option>', page)
        page = self.get(window="operating")
        self.assertIn('<option value="16:00" selected>', page)

    def test_a_typed_time_is_read_in_the_zone_shown(self):
        name, b = self.first_break()
        got = self.client.post("/day/add", data={"csrf_token": self.token(), "program": self.key,
                                                 "date": ON.isoformat(), "associate": name, "what": "Coaching",
                                                 "from": _hm(b["start"] - 60 + NY), "minutes": "15", "view": "board",
                                                 "with_whom": "Omar", "why": "Weekly one to one",
                                                 "tz": "America/New_York"}, follow_redirects=True)
        said = got.get_data(as_text=True)
        coach = next(a for a in self.store.list_activities(self.key, [ON.isoformat()])
                     if a["associate"] == name and a["kind"] == "Coaching")
        self.assertEqual(coach["start"], b["start"] - 60)
        self.assertIn(_hm(b["start"] - 60 + NY), said)  # the message in New York time

    def token(self):
        from webapp.tests.test_runs import token
        return token(self.client)


if __name__ == "__main__":
    unittest.main()
