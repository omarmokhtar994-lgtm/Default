# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AA (owner, 2026-10-10: "review any uploaded schedule not necessarily the last one maybe with a filter per
week so we can choose the week and compare between all shedules and confirm on which one we will use"; approved
sample 03): the menu's Schedules is a page of its own with a week picker and the chosen week's schedules side by
side, with the figures their pages already work out."""
import html
import json
import re
from datetime import datetime, timedelta, timezone

from webapp.programs import ProgramBook
from webapp.tests.test_runs import sign_in, token
from webapp.tests.test_week_list import WEEK, TwoSchedulesForOneWeek
from webapp.week import view as week_view

EGYPT = timezone(timedelta(hours=3))
PREV, NEXT = "2026-10-04", "2026-10-18"


def default_week():
    today = datetime.now(EGYPT).date()
    sunday = (today - timedelta(days=(today.weekday() + 1) % 7)).isoformat()
    return sunday if sunday in (PREV, WEEK, NEXT) else NEXT


class _ByWeek(TwoSchedulesForOneWeek):
    """Phase Z's week of Sun 11 Oct (week_v1.xlsx in use with breaks, week_v2.xlsx without), plus one upload for
    the week before and one for the week after, and a planner with access who uploaded nothing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prev = cls.upload("week_prev.xlsx", week=PREV)
        cls.next = cls.upload("week_next.xlsx", week=NEXT)
        programs = ProgramBook(cls.store)
        saks = next(p["id"] for p in cls.store.list_programs() if p["name"] == "SAKS")
        cls.empty = programs.add_lob(saks, "NMG Tier 9")
        nour = cls.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
        cls.store.set_user_programs(nour, [saks])
        cls.nour = sign_in(cls.app, "nour", "Nour-pass-123")

    def page(self, url, client=None):
        got = (client or self.client).get(url)
        self.assertEqual(got.status_code, 200, url)
        return html.unescape(got.get_data(as_text=True))

    def week_page(self, week=None, client=None):
        return self.page("/schedules?program=" + self.key.replace(" ", "+") + (f"&week={week}" if week else ""),
                         client)

    def table(self, page):
        found = re.search(r'(?s)<table class="cmp".*?</table>', page)
        self.assertIsNotNone(found, "no comparison table")
        return found.group(0)

    def row(self, table, label):
        found = re.search(rf'(?s)<tr><th scope="row">{re.escape(label)}</th>(.*?)</tr>', table)
        self.assertIsNotNone(found, label)
        return re.findall(r"(?s)<td[^>]*>(.*?)</td>", found.group(1))


class TheWeekPage(_ByWeek):
    def test_the_menu_opens_the_week_page(self):
        page = self.week_page()
        self.assertIn("<h1>Schedules: SAKS, NMG Tier 2</h1>", page)
        picker = re.search(r'(?s)<nav class="weekpick".*?</nav>', page).group(0)
        self.assertEqual(re.findall(r"<b>Week of (\d\d \w{3})</b>", picker), ["04 Oct", "11 Oct", "18 Oct"])
        self.assertRegex(picker, r'<a href="[^"]*week=2026-10-11"[^>]*><b>Week of 11 Oct</b><small>2 schedules')
        self.assertRegex(picker, r"<b>Week of 04 Oct</b><small>1 schedule\b")
        self.assertRegex(picker, rf'week={default_week()}" aria-current="true"')

    def test_the_weeks_schedules_sit_side_by_side(self):
        table = self.table(self.week_page(WEEK))
        heads = re.findall(r"<th scope=\"col\"><b>([^<]+)</b>", table)
        self.assertEqual(heads, ["week_v1.xlsx", "week_v2.xlsx"])  # the one in use first
        for label in ("Versions", "Hours at 100%", "Overtime needed for 100%", "Extra hours available",
                      "Breaks planned", "Channel needs"):
            self.row(table, label)
        for run_id, cell in zip((self.first, self.second), self.row(table, "Hours at 100%")):
            shown = next(e["shown"] for e in self.book.week_list(self.key, WEEK) if e["run"]["id"] == run_id)
            tiles = week_view(json.loads(shown["checks"])["intervals"], "after")["totals"]
            self.assertIn(f"{tiles['full']} of {tiles['active']}", cell)
        self.assertEqual([re.sub(r"<[^>]+>", "", c).strip() for c in self.row(table, "Breaks planned")],
                         ["Yes", "Not yet"])

    def test_better_is_marked_only_when_both_have_breaks(self):
        table = self.table(self.week_page(WEEK))
        self.assertNotIn('class="better"', table)
        self.assertIn("before breaks: not compared", self.row(table, "Hours at 100%")[1])
        shown = self.book.versions(self.second)[-1]["id"]
        self.client.post(f"/schedules/{shown}/auto-breaks", data={"csrf_token": token(self.client), "use": "0"})
        try:
            table = self.table(self.week_page(WEEK))
            self.assertNotIn("before breaks: not compared", table)
            marked = [label for label in ("Hours at 100%", "Overtime needed for 100%", "Extra hours available")
                      if any('class="better"' in c or "<small>better</small>" in c for c in self.row(table, label))]
            entries = self.book.week_compare(self.key, WEEK)
            expected = [k for k in ("full", "overtime", "extra") if any(k in e["better"] for e in entries)]
            self.assertEqual(len(marked), len(expected))
        finally:
            for v in self.book.versions(self.second):
                if v["kind"] == "edited":
                    self.store.delete_schedule(v["id"])

    def test_actions_follow_permissions(self):
        table = self.table(self.week_page(WEEK))
        acts = self.row(table, '<span class="sr-only">Actions</span>')
        self.assertIn(f'href="/runs/{self.first}/schedules">Open</a>', acts[0])
        self.assertNotIn("Set in use", acts[0])
        self.assertNotIn("Delete", acts[0])
        self.assertIn("Set in use</button>", acts[1])
        self.assertIn(f'href="/runs/{self.second}/schedules#delete">Delete</a>', acts[1])
        self.assertRegex(acts[1], r'href="/schedules/\d+/week">Week view</a>')
        nour = self.table(self.week_page(WEEK, self.nour))
        self.assertNotIn("Delete", nour)
        self.assertNotIn("Set in use", nour)

    def test_another_week_from_the_picker(self):
        page = self.week_page(PREV)
        self.assertEqual(re.findall(r"<th scope=\"col\"><b>([^<]+)</b>", self.table(page)), ["week_prev.xlsx"])
        self.assertRegex(page, r"<h2[^>]*>Week of 04 Oct: 1 schedule</h2>")
        self.assertRegex(self.week_page("2020-01-05"), rf'week={default_week()}" aria-current="true"')

    def test_a_week_with_three_schedules_and_one_without_figures(self):
        third = self.upload("week_v3.xlsx")
        shown = self.book.versions(third)[-1]
        checks = json.loads(shown["checks"])
        checks.pop("intervals", None)
        with self.store._db() as db:
            db.execute("update schedules set checks = ? where id = ?", (json.dumps(checks), shown["id"]))
        try:
            page = self.week_page(WEEK)
            table = self.table(page)
            heads = re.findall(r'<th scope="col"><b>([^<]+)</b>', table)
            self.assertEqual(len(heads), 3)
            self.assertEqual(heads[1], "week_v3.xlsx")  # in use first, then the newest
            self.assertEqual(re.sub(r"<[^>]+>", "", self.row(table, "Hours at 100%")[1]).strip(), "–")
            self.assertNotIn('class="better"', table)
            self.assertRegex(page, r'<div class="scroll" role="region" tabindex="0" aria-label="[^"]+">\s*<table class="cmp"')
        finally:
            for v in self.book.versions(third):
                self.store.delete_schedule(v["id"])

    def test_a_program_without_schedules_says_so(self):
        empty = self.page("/schedules?program=" + self.empty.replace(" ", "+"))
        self.assertIn("No schedules for", empty)


if __name__ == "__main__":
    import unittest
    unittest.main()
