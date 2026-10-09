# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V task 5: one day's channels, and the breaks it may move, planned with CP-SAT on the website (owner,
2026-10-09: "it can automatically plan same as for breaks to cover that as much as possible", and "this needs to
be connected somehow with breaks as well").

``score_day`` is the judge: it recounts a plan from its blocks and breaks alone (no solver values) and checks every
break with the break planner's own row check. The planner is tested against it."""
import unittest

from webapp.channel_plan import counts_for, plan_day, score_day

WED = 3
RULES = {"segments": [[15, "Break 1"], [30, "Lunch"], [15, "Break 2"]], "by_length": [],
         "windows": {"break 1": {"earliest": None, "latest": None}, "lunch": {"earliest": None, "latest": None},
                     "break 2": {"earliest": None, "latest": None}},
         "edge_margin": None, "min_gap": 60, "preferred_gap": 150, "max_gap": 210, "max_concurrent": 4}
NO_BREAKS = {**RULES, "segments": []}
ARABIC = {3, 4, 8, 11, 12, 16}
SKILLS = {2: "PC", 6: "CE", 10: "P", 15: "CE"}


def phone_need(t):
    h = t / 60
    return 0 if h < 8 or h >= 22 else 2 if h < 10 else 4 if h < 12 else 5 if h < 13 else 6 if h < 17 else 5 if h < 19 \
        else 3 if h < 21 else 2


def chat_need(t):
    h = t / 60
    return 0 if h < 8 or h >= 22 else 1 if h < 10 else 2 if h < 12 else 3 if h < 13 else 4 if h < 19 else 3 if h < 21 \
        else 1


def grid(fn, step=30):
    return {d: {t: fn(t) for t in range(0, 1440, step)} for d in range(7)}


def setup(**over):
    found = {"step": 30, "need": {"P": grid(phone_need), "C": grid(chat_need)}, "email_mode": "hours",
             "email_hours": {d: {"hours": 22.0, "languages": {}, "start": 480, "end": 1320} for d in range(7)},
             "rules": {"min_block": 60, "max_run": {"P": 120, "C": 0, "E": 0}, "order": ["P", "C", "E"],
                       "strict": True, "fair": True},
             "languages": [{"channel": "P", "language": "Arabic", "minimum": 1, "start": 600, "end": 1200,
                            "days": set(range(7)), "active": True},
                           {"channel": "C", "language": "Arabic", "minimum": 1, "start": 720, "end": 1200,
                            "days": set(range(7)), "active": True}],
             "blended": [], "notes": [], "tabs": [], "hours_tab": "Email Hours"}
    found.update(over)
    return found


def day_people(with_breaks=True):
    """16 made-up associates: shifts of 9 hours from 08:00, 10:00, 12:00 and 13:00, staggered breaks."""
    people = []
    for i in range(1, 17):
        start = (8, 10, 12, 13)[(i - 1) // 4] * 60
        k = (i - 1) % 4
        breaks = [("Break 1", start + 120 + 15 * k, 15), ("Lunch", start + 255 + 15 * k, 30),
                  ("Break 2", start + 420 + 15 * (k % 2), 15)]
        language = "Arabic" if i in ARABIC else "English"
        people.append({"name": f"Associate {i:03d}", "language": language, "start": start, "end": start + 540,
                       "breaks": breaks if with_breaks else [(kind, None, m) for kind, _, m in breaks],
                       "skills": SKILLS.get(i, "PCE"), "counts_for": {language.casefold()}})
    return people


class TheDayPlan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.people = day_people()
        cls.setup = setup()
        cls.plan = plan_day(cls.people, cls.setup, RULES, WED)
        cls.score = score_day(cls.people, cls.plan, cls.setup, WED, RULES)

    def test_every_slot_is_one_channel_the_person_works_or_a_break_and_every_rule_holds(self):
        self.assertEqual(self.score["problems"], [])
        for p in self.people:
            for start, end, ch in self.plan["blocks"][p["name"]]:
                self.assertIn(ch, p["skills"], p["name"])

    def test_the_day_is_covered_as_the_samples_showed(self):
        self.assertEqual(self.score["short"]["P"], 0)
        self.assertLessEqual(self.score["short"]["C"], 0.5)
        self.assertEqual(self.score["language_short"], 0)
        self.assertGreaterEqual(self.score["email"], 22)  # spare people may do more email

    def test_email_hours_stay_inside_the_window(self):
        tight = setup(email_hours={d: {"hours": 10.0, "languages": {}, "start": 600, "end": 1200} for d in range(7)})
        plan = plan_day(self.people, tight, RULES, WED)
        for p in self.people:
            if p["skills"] == "E":
                continue
            for start, end, ch in plan["blocks"][p["name"]]:
                if ch == "E":
                    self.assertTrue(600 <= start and end <= 1200, (p["name"], start, end))
        self.assertGreaterEqual(score_day(self.people, plan, tight, WED, RULES)["email"], 10)

    def test_the_planner_says_the_same_shortfall_as_the_judge(self):
        self.assertEqual(self.plan["metrics"]["short"], self.score["short"])
        self.assertEqual(self.plan["metrics"]["language_short"], self.score["language_short"])

    def test_a_suggestion_takes_well_under_a_minute(self):
        # Measured (task 5's ledger): breaks kept first, best plan proven in 4 to 11 s; then breaks may move,
        # starting from it, for at most 10 s. On 4 cores the stages do not give the same plan every time, only
        # one as good (a plan once suggested is kept as a draft until saved or dropped).
        self.assertLess(self.plan["seconds"], 40)
        self.assertEqual(self.plan["note"], "")


class TheBreaks(unittest.TestCase):
    def test_empty_breaks_are_placed_inside_the_rules(self):
        people = day_people(with_breaks=False)
        plan = plan_day(people, setup(), RULES, WED)
        self.assertEqual(score_day(people, plan, setup(), WED, RULES)["problems"], [])
        self.assertTrue(all(len(plan["breaks"][p["name"]]) == 3 and None not in plan["breaks"][p["name"]]
                            for p in people))

    def test_kept_when_not_allowed_to_move_and_locked_ones_never_move(self):
        people = day_people()
        kept = plan_day(people, setup(), RULES, WED, move_breaks=False)
        self.assertEqual(kept["moved"], [])
        self.assertEqual(kept["breaks"], {p["name"]: [s for _, s, _ in p["breaks"]] for p in people})
        locked = {(p["name"], 1) for p in people}  # every lunch typed on the page
        moving = plan_day(people, setup(), RULES, WED, locked=locked)
        for p in people:
            self.assertEqual(moving["breaks"][p["name"]][1], p["breaks"][1][1])
        self.assertTrue(all(kind != "Lunch" for _, kind, _, _ in moving["moved"]))

    def test_a_phone_only_associate_gets_a_break_inside_every_two_hours_of_phone(self):
        people = day_people()
        plan = plan_day(people, setup(), RULES, WED)
        self.assertEqual(score_day(people, plan, setup(), WED, RULES)["long"], {})
        fixed = plan_day(people, setup(), RULES, WED, move_breaks=False)
        # With the schedule's breaks, Associate 010 (Phone only, 12:00 to 21:00) has two stretches over 2 hours:
        # 12:00 to 14:15 and 17:00 to 19:15; the other two are 2 hours and 1.5 hours.
        self.assertEqual(score_day(people, fixed, setup(), WED, RULES)["long"], {"Associate 010": 2})

    def test_when_no_break_can_move_inside_the_rules_the_breaks_are_kept_and_it_says_so(self):
        people = day_people()
        # one person on a break at a time: 16 people need 64 break slots between 08:00 and 22:00, which has 56
        one_at_a_time = {**RULES, "max_concurrent": 1}
        plan = plan_day(people, setup(), one_at_a_time, WED)
        self.assertEqual(plan["breaks"], {p["name"]: [s for _, s, _ in p["breaks"]] for p in people})
        self.assertTrue(plan["note"].startswith("Breaks were kept as they are. "), plan["note"])


class TheOrderAndTheTimes(unittest.TestCase):
    """Two people who can work everything, Chat needing both all day, Phone needing one from 12:00 to 12:30: covering
    that half hour of Phone takes an hour's block (the minimum) away from Chat."""

    def two(self, **rules):
        people = [{"name": f"Associate {i:03d}", "language": "English", "start": 480, "end": 1020, "breaks": [],
                   "skills": "PCE", "counts_for": {"english"}} for i in (1, 2)]
        need = {"P": grid(lambda t: 1 if 720 <= t < 750 else 0), "C": grid(lambda t: 2 if 480 <= t < 1020 else 0)}
        found = setup(need=need, email_mode="none", languages=[],
                      email_hours={d: {"hours": 0.0, "languages": {}, "start": 0, "end": 1440} for d in range(7)},
                      rules={"min_block": 60, "max_run": {"P": 0, "C": 0, "E": 0}, "order": ["P", "C", "E"],
                             "strict": True, "fair": False, **rules})
        return people, found

    def test_strict_covers_phone_first_balanced_weighs_the_hours(self):
        people, strict = self.two()
        got = score_day(people, plan_day(people, strict, NO_BREAKS, WED), strict, WED, NO_BREAKS)
        self.assertEqual((got["short"]["P"], got["short"]["C"]), (0, 1))
        people, balanced = self.two(strict=False)
        got = score_day(people, plan_day(people, balanced, NO_BREAKS, WED), balanced, WED, NO_BREAKS)
        self.assertEqual((got["short"]["P"], got["short"]["C"]), (0.5, 0))
        people, chat_first = self.two(order=["C", "P", "E"])
        got = score_day(people, plan_day(people, chat_first, NO_BREAKS, WED), chat_first, WED, NO_BREAKS)
        self.assertEqual((got["short"]["P"], got["short"]["C"]), (0.5, 0))

    def test_all_channels_times_give_everyone_every_channel_they_work(self):
        people = day_people()
        evening = setup(blended=[{"days": {WED}, "start": 1200, "end": 1320}])
        plan = plan_day(people, evening, RULES, WED)
        score = score_day(people, plan, evening, WED, RULES)
        self.assertEqual(score["problems"], [])
        late = [b for p in people for b in plan["blocks"][p["name"]] if b[1] > 1200]
        self.assertTrue(late)
        self.assertTrue(all(ch == "A" and start >= 1200 for start, end, ch in late if end > 1200 and start >= 1200))

    def test_an_overnight_shift_is_planned_past_midnight(self):
        people = [{"name": "Associate 030", "language": "English", "start": 1320, "end": 1860,
                   "breaks": [("Break 1", None, 15), ("Lunch", None, 30), ("Break 2", None, 15)],
                   "skills": "PC", "counts_for": {"english"}}]
        night = setup(need={"P": grid(lambda t: 1), "C": grid(lambda t: 0)}, email_mode="none", languages=[])
        plan = plan_day(people, night, RULES, WED)
        blocks = plan["blocks"]["Associate 030"]
        self.assertEqual((blocks[0][0], blocks[-1][1]), (1320, 1860))
        self.assertEqual(score_day(people, plan, night, WED, RULES)["problems"], [])


class TheLanguages(unittest.TestCase):
    def test_who_counts_for_a_language_follows_language_setup(self):
        setup_rows = [{"name": "Arabic", "covers": {"arabic"}}, {"name": "Bilingual", "covers": {"bilingual", "arabic",
                                                                                                    "english"}}]
        self.assertEqual(counts_for("Bilingual", setup_rows), {"bilingual", "arabic", "english"})
        self.assertEqual(counts_for("French", setup_rows), {"french"})


if __name__ == "__main__":
    unittest.main()
