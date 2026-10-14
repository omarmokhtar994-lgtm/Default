# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AF, B2 and B3: two rules for Plan channels.

B2, no break while someone is alone (owner, confirmed 2026-10-14, for someone who starts at 10:00 alone):
- someone who can take the queue arrives at 13:00: the first break comes after 13:00;
- nobody comes until later: the first break still comes within the first 4 hours, at whatever time hurts least;
- nobody comes all shift: breaks are planned normally.
A colleague of the same language is preferred; otherwise anyone who can take the queue.

B3, no short stint before a break: never a channel for less than the minimum block and then a break. A stint that
short is left only where the whole stretch is that short (from the shift's start or a break, to a break).
"""
import unittest

from webapp.channel_plan import plan_day
from webapp.tests.test_channel_plan import RULES, WED, day_people, grid, setup

H = 60


def person(name, start, breaks, language="English", skills="P"):
    return {"name": name, "language": language, "start": start * H, "end": start * H + 9 * H,
            "breaks": [(kind, None if at is None else int(at * H), minutes)
                       for (kind, minutes), at in zip((("Break 1", 15), ("Lunch", 30), ("Break 2", 15)), breaks)],
            "skills": skills, "counts_for": {language.casefold()}}


def quiet_phone():
    """Phone in play all day but asking for nobody: only B2 decides where the first break goes."""
    found = setup(need={"P": grid(lambda t: 0)}, email_mode="none", languages=[],
                  email_hours={d: {"hours": 0.0, "languages": {}, "start": 0, "end": 1440} for d in range(7)})
    found["rules"] = {**found["rules"], "max_run": {"P": 0, "C": 0, "E": 0}}  # no run limit moving breaks either
    return found


class NoBreakWhileAlone(unittest.TestCase):
    FIRST = (10.75, 13.5, 16)  # the schedule's breaks for the person who starts at 10:00 alone

    def first_break(self, others):
        people = [person("Associate 01", 10, self.FIRST)] + others
        return plan_day(people, quiet_phone(), RULES, WED)["breaks"]["Associate 01"][0]

    def test_someone_arrives_at_13_00(self):
        start = self.first_break([person("Associate 02", 13, (15.5, 17, 19.5))])
        self.assertGreaterEqual(start, 13 * H)
        self.assertLessEqual(start, 14 * H)

    def test_nobody_comes_until_later(self):
        self.assertLessEqual(self.first_break([person("Associate 02", 15, (17.5, 19, 21.5))]), 14 * H)

    def test_nobody_comes_all_shift(self):
        self.assertEqual(self.first_break([]), self.FIRST[0] * H)  # planned as the schedule has it


class NoShortStintBeforeABreak(unittest.TestCase):
    def test_no_quarter_hour_of_chat_before_a_break(self):
        # Phone needs one person from 10:00 to 11:00 and Chat from 11:00; the break is fixed at 11:15. A quarter
        # hour of Chat between an hour of Phone and the break is the stint the owner does not want.
        needs = setup(need={"P": grid(lambda t: 1 if 600 <= t < 660 else 0),
                            "C": grid(lambda t: 1 if 660 <= t < 690 else 0)},
                      email_mode="none", languages=[],
                      email_hours={d: {"hours": 0.0, "languages": {}, "start": 0, "end": 1440} for d in range(7)})
        one = person("Associate 01", 10, (11.25, 13.5, 16.5), skills="PC")
        runs = plan_day([one], needs, RULES, WED, move_breaks=False)["blocks"]["Associate 01"]
        before = [r for r in runs if r[1] == 11 * H + 15]
        self.assertEqual(len(before), 1)
        self.assertTrue(before[0][0] == 10 * H or before[0][1] - before[0][0] >= 60, runs)

    @classmethod
    def setUpClass(cls):
        cls.people = day_people(with_breaks=False)
        cls.plan = plan_day(cls.people, setup(), RULES, WED)

    def test_every_stint_before_a_break_is_a_full_block_or_the_whole_stretch(self):
        found = []
        for p in self.people:
            name = p["name"]
            breaks = sorted((s, s + m) for s, (_, _, m) in zip(self.plan["breaks"][name], p["breaks"]))
            cuts = {p["start"]} | {e for _, e in breaks}
            for start, end, letter in self.plan["blocks"][name]:
                if any(end == s for s, _ in breaks) and end - start < 60 and start not in cuts:
                    found.append((name, letter, start, end))
        self.assertEqual(found, [])


if __name__ == "__main__":
    unittest.main()
