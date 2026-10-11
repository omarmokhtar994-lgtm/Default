# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "group breaks and fail one interval down to 50% if that will rescue other intervals
... maximum for 3 intervals ... not to drop more than 50% ... interval wise only not weighted volume"; answer 3: the 3
count the whole day, intervals already lost included; sample 02): Rescue the day.

The model is judged on small made-up days where the best answer is known by counting: four people, each with one
hour-long lunch somewhere inside 11:00 to 15:00, and four needed every hour. An hour reaches 90% with at most 25
person-minutes off the floor and stays at 50% with at most 120; the lunches are 240 person-minutes. So giving up two
hours rescues two, giving up one rescues one (the given-up hour was already short), and with nothing to give up there
is no rescue. Every result is recounted with the page's own ``day_view``."""
import unittest

from webapp import rescue
from webapp.day import at_target, day_view
from webapp.tests.test_notify_daybook import WED, _Tagged, hm
from webapp.tests.test_runs import token
from webapp.versions import DAYS

D = 3  # a Wednesday column
NEED = {660: 4.0, 720: 4.0, 780: 4.0, 840: 4.0}  # 11:00 to 15:00, four people every hour


def week(people):
    return {"associates": [{"name": n, "slot": str(i + 1), "language": lang,
                            "days": ["OFF"] * D + [shift] + ["OFF"] * (6 - D)}
                           for i, (n, lang, shift, _) in enumerate(people)],
            "breaks": [{"associate": n, "day": DAYS[D], "kind": k, "start": s, "minutes": mins}
                       for n, _, _, bs in people for k, s, mins in bs]}


def inputs(languages=()):
    return {"interval": 60, "required": {D: dict(NEED)}, "languages": list(languages), "previous_saturday": [],
            "gap_min": None, "gap_max": None}


LUNCHES = [("Associate 001", "ENG", "11:00 - 15:00", [("Lunch", "11:00", 60)]),
           ("Associate 002", "ENG", "11:00 - 15:00", [("Lunch", "12:00", 60)]),
           ("Associate 003", "ARA", "11:00 - 15:00", [("Lunch", "13:00", 60)]),
           ("Associate 004", "ARA", "11:00 - 15:00", [("Lunch", "14:00", 60)])]
ENGLISH = {"name": "ENG", "covers": {"eng"}, "start": 0, "end": 0, "minimum": 1, "days": list(range(7))}


class TheModel(unittest.TestCase):
    def day(self, may, languages=()):
        wk, inp = week(LUNCHES), inputs(languages)
        view = day_view(wk, inp, D, {}, {})
        found = rescue.solve(view, inp, 0.9, 0, may, seconds=20.0)
        after = day_view(wk, inp, D, {}, {(0, m["name"], m["idx"]): m["to"] for m in found["moves"]})
        return view, found, after

    def counted(self, view):
        return at_target(view["cells"], 0.9)

    def test_rescue_gives_up_one_to_save_more(self):
        before, found, after = self.day(may=1)
        self.assertEqual(self.counted(before)["now"], 0)
        self.assertEqual(self.counted(after)["now"], 1)  # the best there is with one hour to give up
        self.assertLessEqual(len(found["given_up"]), 1)

    def test_two_given_up_save_two(self):
        before, found, after = self.day(may=2)
        self.assertEqual(self.counted(after)["now"], 2)
        self.assertEqual(len(found["given_up"]), 2)

    def test_never_below_half(self):
        for may in (1, 2, 3):
            with self.subTest(may=may):
                _, _, after = self.day(may=may)
                shares = [c["pct"] for c in self.counted(after)["cells"] if c["pct"] is not None]
                self.assertGreaterEqual(min(shares), 50)

    def test_no_rescue_when_it_cannot_help(self):
        _, found, _ = self.day(may=0)
        self.assertEqual(found["moves"], [])
        self.assertEqual(found["status"], "no gain")
        wk, inp = week([(n, l, s, [("Lunch", "09:00", 60)]) for n, l, _, _ in LUNCHES for s in ["08:00 - 16:00"]]), inputs()
        view = day_view(wk, inp, D, {}, {})  # every hour at 100% already: nothing to rescue
        self.assertEqual(rescue.solve(view, inp, 0.9, 0, 3)["moves"], [])

    def test_breaks_stay_in_the_shift_on_5_minute_steps(self):
        _, found, _ = self.day(may=2)
        self.assertTrue(found["moves"])
        for m in found["moves"]:
            self.assertEqual(m["to"] % 5, 0)
            self.assertTrue(660 <= m["to"] <= 900 - 60, m)

    def test_language_minimum_holds(self):
        _, found, after = self.day(may=2, languages=[ENGLISH])
        lanes = {l["name"]: l["segments"][0] for l in after["lanes"]}
        for t in range(660, 900, 5):  # never both English speakers away at once (each is alone otherwise)
            off = [n for n in ("Associate 001", "Associate 002")
                   if any(b["start"] <= t < b["start"] + b["minutes"] for b in lanes[n]["breaks"])]
            self.assertLess(len(off), 2, hm(t))
        self.assertGreaterEqual(self.counted(after)["now"], 1)

    def test_lost_so_far_counts_toward_the_three(self):
        cells = [{"t": 0, "pct": 80, "ok": False}, {"t": 60, "pct": 95, "ok": True}, {"t": 120, "pct": None, "ok": None},
                 {"t": 180, "pct": 70, "ok": False}, {"t": 240, "pct": 60, "ok": False}]
        lost = rescue.lost_so_far(cells, now=200, step=60)  # 03:00 to 04:00 is not over yet
        self.assertEqual([c["t"] for c in lost], [0])
        self.assertEqual(rescue.allowance(lost), 2)
        self.assertEqual(rescue.allowance(rescue.lost_so_far(cells, now=1440, step=60)), 0)


class TheDay(_Tagged):
    def fresh(self, skip=()):
        used = {r["associate"] for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])}
        found = self.with_breaks(skip=set(skip) | used)
        self.addCleanup(self.store.clear_actual_break, self.key, WED.isoformat(), found[0], found[1])
        return found

    def test_rescue_apply_stopping_midway_undoes_as_one(self):
        name, idx, kind, start, _ = self.fresh()
        other, oidx, okind, ostart, _ = self.fresh(skip=[name])
        count = len(self.store.day_actions(self.key, WED.isoformat()))
        with self.assertRaises(ValueError):
            self.days.apply_rescue(self.key, WED, [(name, idx, start + 5), (other, oidx, 23 * 60 + 55)], self.omar)
        entries = self.store.day_actions(self.key, WED.isoformat())
        self.assertEqual(len(entries), count + 1)
        self.assertEqual((entries[-1]["kind"], entries[-1]["label"]), ("bulk", "Rescue the day moved 1 break"))
        self.days.undo_last(self.key, WED, self.omar)
        self.assertFalse([r for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])
                          if r["associate"] == name])

    def test_plan_figures_come_from_the_page(self):
        plan = self.days.rescue_plan(self.key, WED, now=None)
        page = self.days.page(self.key, WED)
        self.assertEqual(plan["before"]["now"], page["target"]["now"])
        self.assertEqual((plan["lost"], plan["may"]), ([], 3))  # another day than today: nothing lost yet
        if plan["moves"]:  # whatever it proposes, the page counts the same after it is kept
            self.days.apply_rescue(self.key, WED, [(m["name"], m["idx"], m["to"]) for m in plan["moves"]], self.omar)
            self.addCleanup(self.days.undo_last, self.key, WED, self.omar)
            self.assertEqual(self.days.page(self.key, WED)["target"]["now"], plan["after"]["now"])
        else:
            self.assertTrue(plan["said"])

    def test_every_rule_holds_on_the_recount(self):
        """A day made short (five people marked sick): what Rescue the day proposes is kept move by move through the
        same checks as a single move, the page then counts what the plan said, nobody's gap between breaks leaves the
        program's rules (or gets further outside them), no language loses ground, no interval given up is below 50%."""
        for name in ("Associate 008", "Associate 021", "Associate 037", "Associate 012", "Associate 010"):
            self.days.set_status(self.key, WED, name, "Sick", self.omar)
            self.addCleanup(self.days.set_status, self.key, WED, name, "Present", self.omar)
        before = self.days.page(self.key, WED)
        plan = self.days.rescue_plan(self.key, WED, now=None)
        self.assertTrue(plan["moves"], plan["said"])  # the made-short day has something to rescue
        self.assertGreater(plan["after"]["now"], plan["before"]["now"])
        self.assertLessEqual(len(plan["given_up"]), plan["may"])
        self.assertTrue(all(pct >= 50 for _, pct in plan["given_up"]), plan["given_up"])
        done = self.days.apply_rescue(self.key, WED, [(m["name"], m["idx"], m["to"]) for m in plan["moves"]], self.omar)
        self.addCleanup(self.days.undo_last, self.key, WED, self.omar)
        self.assertEqual(done, len(plan["moves"]))
        after = self.days.page(self.key, WED)
        self.assertEqual(after["target"]["now"], plan["after"]["now"])
        self.assertLessEqual(after["view"]["tiles"]["language_gaps"], before["view"]["tiles"]["language_gaps"])
        lo, hi = before["inputs"]["gap_min"], before["inputs"]["gap_max"]

        def gaps(page):
            out = {}
            for lane in page["view"]["lanes"]:
                for seg in lane["segments"]:
                    if seg["offset"] == 0:
                        b = sorted(seg["breaks"], key=lambda x: x["idx"])
                        out.update({(lane["name"], p["idx"]): q["start"] - p["start"] - p["minutes"]
                                    for p, q in zip(b, b[1:])})
            return out

        was = gaps(before)
        for key, gap in gaps(after).items():
            self.assertTrue(min(lo, was[key]) <= gap <= max(hi, was[key]), (key, was[key], gap))

    def page(self, extra=""):
        got = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}{extra}")
        return got.get_data(as_text=True)

    def test_page_and_button(self):
        self.assertIn("view=rescue", self.page())
        rescue_page = self.page("&view=rescue")
        self.assertIn('<h2 id="rs-h">Rescue the day</h2>', rescue_page)
        self.assertIn("The day may give up 3 at most", rescue_page)

    def test_service_level_measure_has_no_rescue(self):
        self.assertNotIn("view=rescue", self.page("&measure=sl"))
        said = self.page("&measure=sl&view=rescue")
        self.assertIn("Rescue the day counts intervals by interval compliance", said)

    def test_apply_route(self):
        name, idx, kind, start, _ = self.fresh()
        got = self.client.post("/day/rescue/apply", data={"csrf_token": token(self.client), "program": self.key,
                                                           "date": WED.isoformat(), "move": [f"{name}|{idx}|{start + 5}"]},
                               follow_redirects=True)
        self.assertIn("Rescue the day moved 1 break.", got.get_data(as_text=True))
        entry = self.store.day_actions(self.key, WED.isoformat())[-1]
        self.assertEqual({i["status"] for i in self.store.notify_items(action_id=entry["id"])}, {"held"})


if __name__ == "__main__":
    unittest.main()
