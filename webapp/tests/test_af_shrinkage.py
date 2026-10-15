# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, E1: shrinkage in and out of office on the RTA, per day (owner, 2026-10-14).

- Out of office, Sutherland: (unplanned leave + planned leave + sick) / scheduled employees, anyone on a day off left
  out. Out of office, client: the same with public holiday added. Planned leave is read from the schedule.
- In office: the minutes present people spend on what the program maps as in-office shrinkage (breaks and lunch, aux
  not billable by default; billable aux not), over their scheduled minutes.
- What counts is a program setting the admin or a supervisor maps; shown side by side (sample af05, approved).
"""
import unittest

from webapp.shrinkage import DEFAULT, day_shrinkage, mapping_from_form, read_mapping

H = 60
WED = 3


def seg(start, end, status="Present", billable=False, away=(0, 0), breaks=(15, 30, 15), acts=(), offset=0):
    return {"offset": offset, "start": start * H, "end": end * H, "status": status, "billable": billable,
            "away": (away[0] * H, away[1] * H), "breaks": [{"start": 0, "minutes": m} for m in breaks],
            "activities": [{"kind": k, "start": a * H, "end": b * H, "billable": bill} for k, a, b, bill in acts]}


def lane(name, *segments):
    return {"name": name, "segments": list(segments)}


def week_of(cells):
    """The schedule: each name's Wednesday cell (the other days are OFF)."""
    return {"associates": [{"name": n, "days": ["OFF"] * 3 + [c] + ["OFF"] * 3} for n, c in cells.items()]}


class OutOfOffice(unittest.TestCase):
    def setUp(self):
        self.view = {"lanes": [lane("Associate 01", seg(8, 17, "Unplanned leave")),
                               lane("Associate 02", seg(8, 17, "Sick")),
                               lane("Associate 03", seg(8, 17, "Public holiday")),
                               lane("Associate 04", seg(8, 17)), lane("Associate 05", seg(10, 19)),
                               lane("Associate 06", seg(16, 25)),
                               lane("Associate 07", seg(16, 25)), lane("Associate 08", seg(20, 29)),
                               lane("Associate 09", seg(-2, 7, offset=-1))]}  # last night's shift: not today's
        self.week = week_of({**{f"Associate 0{i}": "08:00 - 17:00" for i in range(1, 9)},
                             "Associate 10": "Leave", "Associate 11": "OFF", "Associate 12": ""})

    def test_sutherland_and_client(self):
        found = day_shrinkage(self.view, self.week, WED, read_mapping(None))
        # scheduled: 8 with a shift today and 1 on planned leave; the day off and the blank are left out
        self.assertEqual(found["sutherland"]["scheduled"], 9)
        self.assertAlmostEqual(found["sutherland"]["pct"], 3 / 9)  # unplanned 1 + planned 1 + sick 1
        self.assertAlmostEqual(found["client"]["pct"], 4 / 9)  # and public holiday 1
        self.assertEqual(found["sutherland"]["text"], "(unplanned 1 + planned 1 + sick 1) / 9 scheduled")
        # re-pinned in Phase AI: the owner added exam leave to the client's shrinkage (2026-10-15)
        self.assertEqual(found["client"]["text"],
                         "(unplanned 1 + planned 1 + sick 1 + public holiday 1 + exam leave 0) / 9 scheduled")
        self.assertIn("Public holiday counts for the client only", found["client"]["notes"])
        self.assertIn("Days off are not counted", found["sutherland"]["notes"])

    def test_the_mapping_decides(self):
        mapping = read_mapping('{"holiday": ["sutherland", "client"], "sick": ["client"]}')
        found = day_shrinkage(self.view, self.week, WED, mapping)
        self.assertEqual(found["sutherland"]["text"], "(unplanned 1 + planned 1 + public holiday 1) / 9 scheduled")
        self.assertIn("Sick counts for the client only", found["client"]["notes"])

    def test_nobody_scheduled(self):
        found = day_shrinkage({"lanes": []}, week_of({"Associate 01": "OFF"}), WED, read_mapping(None))
        self.assertIsNone(found["sutherland"]["pct"])
        self.assertIsNone(found["in_office"]["pct"])


class InOffice(unittest.TestCase):
    def test_breaks_and_aux_not_billable_by_default(self):
        view = {"lanes": [lane("Associate 01", seg(8, 17, acts=(("Coaching", 10, 10.5, False),))),
                          lane("Associate 02", seg(8, 17, acts=(("Meeting", 11, 12, True),))),
                          lane("Associate 03", seg(8, 17, "Training", away=(13, 14))),
                          lane("Associate 04", seg(8, 17, "Sick"))]}
        found = day_shrinkage(view, week_of({}), WED, read_mapping(None))["in_office"]
        # 3 present x 540 minutes; breaks 3 x 60, Coaching 30 and Training 60 (not billable); the billable Meeting
        # and the sick person's shift are left out
        self.assertEqual(found["scheduled"], 3 * 540)
        self.assertEqual(found["minutes"], 180 + 30 + 60)
        self.assertAlmostEqual(found["pct"], 270 / 1620)
        self.assertEqual(found["counted"], "breaks and lunch, aux not billable")

    def test_billable_aux_when_mapped(self):
        view = {"lanes": [lane("Associate 02", seg(8, 17, acts=(("Meeting", 11, 12, True),), breaks=()))]}
        mapping = read_mapping('{"aux_billable": ["in"], "breaks": []}')
        self.assertEqual(day_shrinkage(view, week_of({}), WED, mapping)["in_office"]["minutes"], 60)

    def test_planned_from_the_input(self):
        view = {"lanes": [lane("Associate 01", seg(8, 17))]}
        inputs = {"required": {WED: {480: 2.0, 540: 2.0, 600: 0.0}},
                  "planned_shrinkage": {WED: {480: 0.10, 540: 0.20, 600: 0.90}}}
        found = day_shrinkage(view, week_of({}), WED, read_mapping(None), inputs)["in_office"]
        self.assertAlmostEqual(found["planned"], 0.15)  # the intervals with demand only


class TheMapping(unittest.TestCase):
    def test_default(self):
        self.assertEqual(read_mapping(None), DEFAULT)
        self.assertEqual(read_mapping(None)["holiday"], {"client"})
        self.assertEqual(read_mapping(None)["aux_billable"], set())

    def test_a_measure_an_item_cannot_count_for_is_dropped(self):
        self.assertEqual(read_mapping('{"unplanned": ["in", "client"]}')["unplanned"], {"client"})

    def test_from_the_form(self):
        got = mapping_from_form({"breaks:in": "1", "holiday:client": "1", "sick:sutherland": "1", "sick:in": "1"})
        self.assertEqual(got["breaks"], ["in"])
        self.assertEqual(got["sick"], ["sutherland"])
        self.assertEqual(got["aux"], [])


class TheStore(unittest.TestCase):
    def test_kept_per_program_and_moved_by_a_rename(self):
        import tempfile
        from pathlib import Path
        from webapp.store import Store
        store = Store(Path(tempfile.mkdtemp()) / "app.db")
        self.assertIsNone(store.get_shrinkage_map("SAKS NMG Tier 2"))
        store.set_shrinkage_map("SAKS NMG Tier 2", {"holiday": ["client"]}, None)
        self.assertEqual(read_mapping(store.get_shrinkage_map("SAKS NMG Tier 2")["mapping"])["holiday"], {"client"})
        store.rename_program("SAKS NMG Tier 2", "SAKS NMG Tier 3", [])
        self.assertIsNone(store.get_shrinkage_map("SAKS NMG Tier 2"))
        self.assertIsNotNone(store.get_shrinkage_map("SAKS NMG Tier 3"))


class OnThePage(unittest.TestCase):
    """The RTA shows the three tiles side by side; admins and supervisors save the mapping, planners cannot."""

    @classmethod
    def setUpClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.setUpClass.__func__(cls)
        from webapp.tests.test_runs import sign_in
        cls.store.add_user("plan", "Planner", "Planner-pass-123", must_change=False)
        cls.planner = sign_in(cls.app, "plan", "Planner-pass-123")

    @classmethod
    def tearDownClass(cls):
        from webapp.tests import test_channel_day
        test_channel_day.TheChannelsTab.tearDownClass.__func__(cls)

    def url(self):
        from webapp.tests.test_channel_day import WED as wed
        return f"/day?program={self.key.replace(' ', '+')}&date={wed.isoformat()}"

    def test_three_tiles(self):
        page = self.admin.get(self.url()).get_data(as_text=True)
        self.assertIn('aria-labelledby="shr-today-h"', page)
        for words in ("In office", "Out of office, Sutherland", "Out of office, client", "Days off are not counted",
                      "What counts as shrinkage"):
            self.assertIn(words, page)

    def test_a_manager_saves_the_mapping(self):
        from webapp.tests.test_channel_day import WED as wed
        got = self.admin.post("/day/shrinkage", data={"csrf_token": self.token(self.admin), "program": self.key,
                                                      "date": wed.isoformat(), "breaks:in": "1",
                                                      "unplanned:sutherland": "1", "unplanned:client": "1",
                                                      "holiday:sutherland": "1", "holiday:client": "1"})
        self.assertEqual(got.status_code, 303)
        saved = read_mapping(self.store.get_shrinkage_map(self.key)["mapping"])
        self.assertEqual(saved["holiday"], {"sutherland", "client"})
        self.assertEqual(saved["aux"], set())

    def test_a_planner_cannot(self):
        got = self.planner.post("/day/shrinkage", data={"csrf_token": self.token(self.planner), "program": self.key,
                                                        "date": "2026-10-14", "breaks:in": "1"})
        self.assertEqual(got.status_code, 403)


if __name__ == "__main__":
    unittest.main()
