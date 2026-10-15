# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AL item 2 (owner, 2026-10-15: "We need to add fairness for channels now as a start during the day/week etc";
answers: same share and turns, the week mainly and the day where the week cannot, coverage wins, a fairness view
first, compared among people with the same channels and language). Counted from the plan the Plan channels page
shows; a break is not channel time and does not end a turn."""
import unittest

from webapp.channel_fair import fairness

RULES = {"segments": [[30, "Lunch"]], "by_length": []}
OFF = ["OFF"] * 7


def person(name, language="English", **days):
    out = list(OFF)
    for day, label in days.items():
        out[["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].index(day)] = label
    return {"name": name, "language": language, "days": out}


WEEK = {"associates": [person("Associate 001", Sun="09:00 - 17:00", Mon="09:00 - 17:00"),
                       person("Associate 002", Sun="09:00 - 17:00"),
                       person("Associate 003", "French", Sun="09:00 - 17:00")],
        "channels": [], "breaks": []}


def day(blocks, breaks=None):
    return {"blocks": blocks, "breaks": breaks or {}, "moved": [], "note": ""}


DRAFT = {"Sun": day({"Associate 001": [[540, 1020, "P"]],
                     "Associate 002": [[540, 780, "P"], [780, 1020, "C"]],
                     "Associate 003": [[540, 1020, "E"]]}),
         "Mon": day({"Associate 001": [[540, 1020, "C"]]})}


def row(groups, name):
    return next(r for g in groups for r in g["people"] if r["name"] == name)


class TheShares(unittest.TestCase):
    def test_the_day_compares_people_with_the_same_channels_and_language(self):
        got = fairness(WEEK, RULES, DRAFT, {}, [], 0)["day"]
        english = next(g for g in got if "Associate 001" in [r["name"] for r in g["people"]])
        self.assertEqual(english["label"], "All three channels, English")
        self.assertAlmostEqual(english["even"]["P"], 0.75)
        first, second = row(got, "Associate 001"), row(got, "Associate 002")
        self.assertEqual((first["minutes"]["P"], second["minutes"]["P"], second["minutes"]["C"]), (480, 240, 240))
        self.assertEqual((first["gap"], second["gap"]), (25.0, 25.0))
        self.assertTrue(first["furthest"] and second["furthest"])  # a tie marks both

    def test_the_week_counts_every_day(self):
        got = fairness(WEEK, RULES, DRAFT, {}, [], 0)["week"]
        self.assertEqual((row(got, "Associate 001")["minutes"]["P"], row(got, "Associate 001")["minutes"]["C"]),
                         (480, 480))

    def test_someone_alone_in_their_group_is_listed_not_compared(self):
        alone = row(fairness(WEEK, RULES, DRAFT, {}, [], 0)["day"], "Associate 003")
        self.assertEqual((alone["minutes"]["E"], alone["gap"], alone["furthest"]), (480, None, False))

    def test_other_channels_make_another_group(self):
        got = fairness(WEEK, RULES, DRAFT, {"Associate 002": "PC"}, [], 0)["day"]
        self.assertIsNone(row(got, "Associate 002")["gap"])


class TheTurns(unittest.TestCase):
    def test_a_break_is_not_channel_time_and_does_not_end_the_turn(self):
        draft = {"Sun": day({"Associate 001": [[540, 1020, "P"]]}, {"Associate 001": [720]})}
        got = row(fairness(WEEK, RULES, draft, {}, [], 0)["day"], "Associate 001")
        self.assertEqual((got["minutes"]["P"], got["longest"], got["longest_day"]), (450, 450, "Sun"))

    def test_a_change_of_channel_ends_the_turn(self):
        self.assertEqual(row(fairness(WEEK, RULES, DRAFT, {}, [], 0)["week"], "Associate 002")["longest"], 240)


class TheSource(unittest.TestCase):
    def test_a_draft_day_counts_instead_of_the_versions(self):
        week = dict(WEEK, channels=[{"associate": "Associate 002", "day": "Sun", "start": "09:00", "end": "17:00",
                                     "channel": "E"}])
        self.assertEqual(row(fairness(week, RULES, {}, {}, [], 0)["day"], "Associate 002")["minutes"]["E"], 480)
        self.assertEqual(row(fairness(week, RULES, DRAFT, {}, [], 0)["day"], "Associate 002")["minutes"]["E"], 0)


if __name__ == "__main__":
    unittest.main()


from webapp.tests import test_channel_page as cp  # noqa: E402


class ThePage(cp._Page):
    """The Plan channels page shows the fairness of the plan it shows: the week first, then the day picked."""

    @classmethod
    def setUpClass(cls):
        cls.start()
        working = cls.working(cls)
        lang = next(l for l in {a["language"] for a in working}
                    if sum(a["language"] == l for a in working) >= 2)
        cls.pair = [a for a in working if a["language"] == lang][:2]
        for a, letter in zip(cls.pair, "PC"):
            start, end = cp.shift_span(a["days"][cp.WED])
            cls.admin.post(cls.url, data={"csrf_token": cp.token(cls.admin), "day": "Wed", "action": "edit",
                                          "who": a["name"], "start": f"{start // 60 % 24:02d}:{start % 60:02d}",
                                          "end": f"{end // 60 % 24:02d}:{end % 60:02d}", "channel": letter})

    def test_the_fairness_section(self):
        code, page = self.page("Wed")
        self.assertEqual(code, 200)
        section = page[page.index('id="cp-fair-h"'):]
        section = section[:section.index("</section>")]
        for words in ("Fairness", "This week", "Wednesday", f"All three channels, {self.pair[0]['language']}",
                      "Longest on one channel", "Coverage and the planner are unchanged", self.pair[0]["name"]):
            self.assertIn(words, section)
        self.assertEqual(section.count("furthest from even"), 4)  # both of the pair, in the week and in the day
