# © 2026 Omar Mokhtar. All rights reserved.
"""Phase Z (owner, 2026-10-10: "Cant find any where in timeline or interval board todays achievement as discussed ?";
approved samples 04 and 05): one "Today's achievement" block above the RTA's tabs on every tab (the count of
intervals at the week's target, the share, the plan's count and one block per interval with a "now" mark), "At
target" or "Below" under each hour's cover on the Interval board, and the Timeline's Achieved row under the hours."""
import html
import io
import re
import shutil
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_ready import make_ready
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

EGYPT = timezone(timedelta(hours=3))
WED = date(2026, 10, 14)


def this_sunday() -> date:
    today = datetime.now(EGYPT).date()
    return today - timedelta(days=(today.weekday() + 1) % 7)


class _Rta(unittest.TestCase):
    """SAKS: NMG Tier 2 for the week of Sun 11 Oct (Wed 14 Oct is "another day"), NMG Tier 1 for this week (today).
    Both weeks at a 90% target."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        saks = programs.add_program("SAKS")
        cls.key = programs.add_lob(saks, "NMG Tier 2")
        cls.today_key = programs.add_lob(saks, "NMG Tier 1")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        for key, week in ((cls.key, "2026-10-11"), (cls.today_key, this_sunday().isoformat())):
            cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK",
                                           "program": key, "week_start": week,
                                           "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                            content_type="multipart/form-data")
            wait(cls.store, cls.store.list_runs()[0]["id"], statuses=("DONE", "REJECTED", "FAILED"))
            cls.client.post("/week/target", data={"csrf_token": token(cls.client), "program": key, "week": week,
                                                  "target": "90"})

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def day(self, key=None, on=WED, view="timeline"):
        got = self.client.get(f"/day?program={(key or self.key).replace(' ', '+')}&date={on.isoformat()}&view={view}")
        self.assertEqual(got.status_code, 200)
        return html.unescape(got.get_data(as_text=True))

    def target(self, key=None, on=WED):
        return self.app.extensions["days"].page(key or self.key, on)["target"]

    def block(self, page):
        found = re.search(r'(?s)<section class="achv"[^>]*>.*?</section>', page)
        self.assertIsNotNone(found, "no achievement block")
        return found.group(0)


class TheAchievementBlock(_Rta):
    def test_the_block_sits_above_the_tabs_on_every_tab(self):
        for view in ("timeline", "board", "adherence", "meeting", "cover"):
            page = self.day(view=view)
            self.assertLess(page.index('<section class="achv"'), page.index('class="daybar"'), view)
            self.assertEqual(page.count('<section class="achv"'), 1, view)

    def test_the_count_the_share_and_the_plan(self):
        t = self.target()
        self.assertEqual(t["target"], 0.9)
        block = self.block(self.day())
        self.assertIn(f'<p class="achv-num"><b>{t["now"]} of {t["intervals"]}</b> intervals at 90% or more</p>', block)
        share = round(100 * t["now"] / t["intervals"])
        self.assertIn(f"<b>{share}%</b> of the day's intervals reach the target, with attendance as marked. The plan "
                      f"had {t['plan']} of {t['intervals']}.", block)
        self.assertIn(">Target 90% for this week</a>", block)

    def test_one_block_per_interval_with_its_result(self):
        t = self.target()
        marks = re.findall(r'<i class="(ok|below|none)" title="(\d\d:\d\d)(?:: (\d+)%)?"', self.block(self.day()))
        self.assertEqual(len(marks), len(t["cells"]))
        for (kind, at, pct), c in zip(marks, t["cells"]):
            self.assertEqual(kind, "none" if c["ok"] is None else ("ok" if c["ok"] else "below"))
            self.assertEqual(at, f"{c['t'] // 60:02d}:{c['t'] % 60:02d}")
            self.assertEqual(pct, "" if c["pct"] is None else str(c["pct"]))

    def test_another_day_is_not_called_today(self):
        block = self.block(self.day())
        self.assertIn('<h2 id="achv-h">Achievement on Wed 14 Oct</h2>', block)
        self.assertNotIn("Today's achievement", block)
        self.assertNotIn("data-now", block)

    def test_today_is_called_today_with_a_now_mark(self):
        today = datetime.now(EGYPT)
        block = self.block(self.day(self.today_key, today.date()))
        self.assertIn('<h2 id="achv-h">Today\'s achievement</h2>', block)
        self.assertIn("of today's intervals reach the target", block)
        now = int(re.search(r'data-now="(\d+)"', block).group(1))
        self.assertLessEqual(abs(now - (today.hour * 60 + today.minute)), 2)


class TheBoardAndTheTimeline(_Rta):
    def test_the_board_says_at_target_or_below(self):
        page = self.day(view="board")
        self.assertIn('<span role="columnheader">Cover <small>(target 90%)</small></span>', page)
        for c in self.target()["cells"]:
            row = re.search(rf'(?s)id="row-{c["t"]}">.*?</div>', page).group(0)
            if c["ok"] is None:
                self.assertNotRegex(row, r"At target|Below")
            else:
                self.assertIn(f'<small class="{"ok" if c["ok"] else "below"}">{"At target" if c["ok"] else "Below"}'
                              "</small>", row)

    def test_the_timeline_puts_achieved_under_the_hours(self):
        page = self.day()
        rows = re.findall(r'<div class="tl-row ([a-z -]+)"[^>]*>(?:<span class="tl-lbl">([^<]*)</span>)?', page)
        axis = next(i for i, (cls, _) in enumerate(rows) if "tl-axis" in cls)
        self.assertEqual(rows[axis + 1][1], "Achieved (target 90%)")


if __name__ == "__main__":
    unittest.main()
