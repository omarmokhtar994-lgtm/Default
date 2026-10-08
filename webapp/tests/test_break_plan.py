# © 2026 Omar Mokhtar. All rights reserved.
"""Phase R task 8: a week's breaks planned on the website (owner, 2026-10-08: "we can plot breaks manually").

The rules come from the engine's own parser (break set per shift length, windows, edge margin, gaps), run in a
subprocess as the validator does. A grid per day holds each shift's breaks; Suggest fills empty ones inside the
rules where the floor has most room; saving makes a new version, checked like every other."""
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from webapp.attendance import DayBook
from webapp.break_plan import check_row, slots_for, suggest
from webapp.day import read_inputs
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_ready import make_ready
from webapp.tests.test_schedules import REPO
from webapp.versions import DAYS, read_week, shift_span, validate

WED = 3
BREAK_FAILURES = {"BREAK_SEGMENT_COUNT_OR_DURATION", "BREAK_ORDER_OR_TYPE", "BREAK_MINIMUM_GAP", "BREAK_WINDOW",
                  "BREAK_EDGE_MARGIN", "BREAK_NOT_QUARTER_HOUR_ALIGNED", "BREAK_OUTSIDE_SHIFT", "OVERLAPPING_BREAK"}


def hm(minute):
    return f"{(minute // 60) % 24:02d}:{minute % 60:02d}"


class TheBreakPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """One ready run and its version (the validator runs once); each test gets a copy."""
        cls.base = Path(tempfile.mkdtemp())
        store = Store(cls.base / "scheduler.db")
        cls.sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
        store.add_run("rrrrrrrrrrrr", cls.sara, "ready.xlsx", "READY", "DONE", program="SAKS NMG Tier 2",
                      week_start="2026-10-11")
        ready = make_ready(cls.base / "upload.xlsx")
        ScheduleBook(store, cls.base, REPO).ensure_ready(store.get_run("rrrrrrrrrrrr"), ready)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base, True)

    def setUp(self):
        self.data = Path(tempfile.mkdtemp()) / "data"
        self.addCleanup(shutil.rmtree, self.data.parent, True)
        shutil.copytree(self.base, self.data)
        self.store = Store(self.data / "scheduler.db")
        self.book = ScheduleBook(self.store, self.data, REPO)
        self.version = self.book.versions("rrrrrrrrrrrr")[0]
        self.week = json.loads(self.version["week"])
        self.rules = self.book.break_rules(self.version["id"])
        self.inputs = read_inputs(self.book.input_path("rrrrrrrrrrrr"))

    def working(self, d):
        return [a for a in self.week["associates"] if shift_span(a["days"][d])]

    def checked(self, schedule_id):
        row = self.store.get_schedule(schedule_id)
        return validate(self.book.input_path(row["run_id"]), self.book.path(schedule_id), REPO)

    def test_rules_come_from_the_engine_parser(self):
        self.assertEqual(slots_for(self.rules, 540), [("Break 1", 15), ("Lunch", 30), ("Break 2", 15)])
        self.assertEqual((self.rules["min_gap"], self.rules["preferred_gap"], self.rules["max_gap"]), (60, 150, 210))
        self.assertTrue((self.book.root / "rrrrrrrrrrrr" / "break_rules.json").is_file())  # read once per run

    def test_check_row_names_the_gap(self):
        self.assertEqual(check_row(self.rules, "10:00 - 19:00", [None, None, None]), ("none", "Not placed yet"))
        self.assertEqual(check_row(self.rules, "10:00 - 19:00", [12 * 60, 14 * 60 + 30, 17 * 60]), ("ok", "OK"))
        level, text = check_row(self.rules, "10:00 - 19:00", [12 * 60, 12 * 60 + 30, 17 * 60])
        self.assertEqual(level, "warn")
        self.assertIn("Lunch starts 15 minutes after Break 1 ends; the minimum gap is 60", text)
        level, text = check_row(self.rules, "10:00 - 19:00", [12 * 60 + 5, 14 * 60 + 30, 17 * 60])
        self.assertIn("15-minute steps", text)
        level, text = check_row(self.rules, "10:00 - 19:00", [12 * 60, 14 * 60 + 30, 18 * 60 + 50])
        self.assertIn("outside the shift", text)

    def test_suggest_fills_empty_slots_inside_the_rules(self):
        plan = suggest(self.week, self.inputs, self.rules, WED, {})
        people = self.working(WED)
        self.assertEqual(set(plan), {a["name"] for a in people})
        for a in people:
            starts = plan[a["name"]]
            self.assertTrue(all(s is not None for s in starts), a["name"])
            self.assertEqual(check_row(self.rules, a["days"][WED], starts), ("ok", "OK"), a["name"])
        saved, left_out = self.book.save_breaks(self.version["id"], self.sara, {"Wed": plan}, "planned Wednesday")
        self.assertEqual(left_out, [])
        found = self.checked(saved)
        wrong = [f for f in found["failures"] if f.get("type") in BREAK_FAILURES and f.get("day") == "Wed"]
        self.assertEqual(wrong, [])

    def test_suggest_keeps_what_was_typed(self):
        first = self.working(WED)[0]
        span = shift_span(first["days"][WED])
        mine = [span[0] + 120, None, None]
        plan = suggest(self.week, self.inputs, self.rules, WED, {first["name"]: mine})
        self.assertEqual(plan[first["name"]][0], span[0] + 120)
        self.assertIsNotNone(plan[first["name"]][2])

    def test_overnight_shift_breaks_cross_midnight(self):
        d, person = next((d, a) for d in range(7) for a in self.week["associates"]
                         if shift_span(a["days"][d]) and shift_span(a["days"][d])[1] > 1440)
        plan = suggest(self.week, self.inputs, self.rules, d, {})
        starts = plan[person["name"]]
        self.assertEqual(check_row(self.rules, person["days"][d], starts), ("ok", "OK"))
        self.assertTrue(any(s >= 1440 for s in starts) or shift_span(person["days"][d])[0] >= 1440 - 60)
        saved, _ = self.book.save_breaks(self.version["id"], self.sara, {DAYS[d]: {person["name"]: starts}}, "night")
        breaks = [b for b in read_week(self.book.path(saved))["breaks"] if b["associate"] == person["name"]
                  and b["day"] == DAYS[d]]
        self.assertEqual([b["start"] for b in breaks], [hm(s) for s in starts])
        wrong = [f for f in self.checked(saved)["failures"] if f.get("type") in BREAK_FAILURES
                 and f.get("associate") == person["name"] and f.get("day") == DAYS[d]]
        self.assertEqual(wrong, [])

    def test_draft_survives_switching_days_and_save_makes_a_version(self):
        first = self.working(WED)[0]
        span = shift_span(first["days"][WED])
        typed = {first["name"]: [span[0] + 120, span[0] + 240, span[0] + 390]}
        self.store.set_break_draft(self.version["id"], "Wed", typed, self.sara)
        self.store.set_break_draft(self.version["id"], "Thu", {}, self.sara)
        self.assertEqual(self.store.get_break_draft(self.version["id"]), {"Wed": typed, "Thu": {}})
        saved, left_out = self.book.save_breaks(self.version["id"], self.sara, self.store.get_break_draft(
            self.version["id"]), "first breaks")
        self.assertNotEqual(saved, self.version["id"])
        row = self.store.get_schedule(saved)
        self.assertEqual((row["kind"], row["base_id"]), ("edited", self.version["id"]))
        breaks = [b for b in json.loads(row["week"])["breaks"] if b["associate"] == first["name"] and b["day"] == "Wed"]
        self.assertEqual([(b["kind"], b["start"], b["minutes"]) for b in breaks],
                         [("Break 1", hm(span[0] + 120), 15), ("Lunch", hm(span[0] + 240), 30),
                          ("Break 2", hm(span[0] + 390), 15)])
        changes = self.store.list_changes(saved)
        self.assertEqual([(c["associate"], c["day"], c["old"]) for c in changes], [(first["name"], "Wed", "no breaks")])
        self.assertIn("Break 1 " + hm(span[0] + 120), changes[0]["new"])
        self.store.clear_break_draft(self.version["id"])
        self.assertEqual(self.store.get_break_draft(self.version["id"]), {})

    def test_draft_for_a_day_off_is_reported_not_saved(self):
        off = next(a for a in self.week["associates"] if not shift_span(a["days"][WED]))
        saved, left_out = self.book.save_breaks(self.version["id"], self.sara,
                                                {"Wed": {off["name"]: [600, 720, 900]}}, "typo")
        self.assertEqual(left_out, [f"{off['name']}, Wed: no shift that day ({off['days'][WED]}), so these breaks "
                                    "were left out."])
        self.assertEqual([b for b in read_week(self.book.path(saved))["breaks"] if b["associate"] == off["name"]], [])

    def test_ready_schedule_with_planned_breaks_shows_them_in_rta(self):
        plan = suggest(self.week, self.inputs, self.rules, WED, {})
        saved, _ = self.book.save_breaks(self.version["id"], self.sara, {"Wed": plan}, "planned", use=True)
        self.assertEqual(self.store.get_schedule(saved)["in_use"], 1)
        page = DayBook(self.store, self.book).page("SAKS NMG Tier 2", date(2026, 10, 14))
        self.assertEqual(page["version"]["id"], saved)
        name = self.working(WED)[0]["name"]
        lane = next(l for l in page["view"]["lanes"] if l["name"] == name)
        seg = next(s for s in lane["segments"] if s["offset"] == 0)
        self.assertEqual([b["start"] for b in seg["breaks"]], plan[name])


class TheBreakPlanPage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import io
        from webapp.programs import ProgramBook
        from webapp.tests.test_runs import make_app, run_id_of, sign_in, token
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx").read_bytes()
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        book = ProgramBook(cls.store)
        cls.key = book.add_lob(book.add_program("SAKS"), "NMG Tier 2")
        book.add_program("GDI")
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")
        run_id = run_id_of(cls.admin.post("/runs", data={
            "csrf_token": token(cls.admin), "kind": "ready", "program": cls.key, "week_start": "2026-10-11",
            "workbook": (io.BytesIO(ready), "ready.xlsx")}, content_type="multipart/form-data"))
        cls.version = cls.app.extensions["schedules"].versions(run_id)[0]
        gdi = next(p["id"] for p in book.tree() if p["name"] == "GDI")
        lina = cls.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)
        cls.store.set_user_programs(lina, [gdi])
        cls.lina = sign_in(cls.app, "lina", "Lina-pass-123")
        cls.token = staticmethod(token)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def url(self, day="Wed"):
        return f"/schedules/{self.version['id']}/breaks?day={day}"

    def test_breaks_page_access_is_checked(self):
        self.assertEqual(self.lina.get(self.url()).status_code, 403)
        self.assertEqual(self.admin.get(self.url()).status_code, 200)

    def test_grid_suggest_keep_and_save(self):
        import html
        page = html.unescape(self.admin.get(self.url()).get_data(as_text=True))
        for words in ("plan breaks", "Break 1, 15 min", "Lunch, 30 min", "Break 2, 15 min", "Not placed yet",
                      "Suggest times for the empty ones", "Save as a new version"):
            self.assertIn(words, page)
        got = self.admin.post(self.url(), data={"csrf_token": self.token(self.admin), "action": "suggest",
                                                "day": "Wed"})
        self.assertEqual(got.status_code, 303)
        draft = self.store.get_break_draft(self.version["id"])
        self.assertTrue(draft["Wed"])
        self.assertTrue(all(all(s is not None for s in v) for v in draft["Wed"].values()))
        got = self.admin.post(self.url(), data={"csrf_token": self.token(self.admin), "action": "save", "day": "Wed",
                                                "use": "1", "reason": "Wednesday planned"})
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.store.get_break_draft(self.version["id"]), {})
        saved = [v for v in self.app.extensions["schedules"].versions(self.version["run_id"]) if v["kind"] == "edited"]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["in_use"], 1)


if __name__ == "__main__":
    unittest.main()
