# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AI (owner, 2026-10-15): "instead of endless scrolling they might have some pages to see more of runned
schedules same for OT and other staff". Long lists show 20 at a time with pages: the runs on Home, the RTA's changes
today and overtime offers, decided leave and swap requests, and a LOB's group posts. Made-up "Associate NN" data.
"""
import re
import time
import unittest

from webapp.paging import PAGE_SIZE, page_of
from webapp.tests.test_notify_daybook import WED, _Tagged


class OnePage(unittest.TestCase):
    def test_twenty_at_a_time(self):
        self.assertEqual(PAGE_SIZE, 20)
        shown, info = page_of(list(range(45)), 2)
        self.assertEqual(shown, list(range(20, 40)))
        self.assertEqual((info["page"], info["pages"], info["first"], info["last"], info["total"]), (2, 3, 21, 40, 45))

    def test_a_page_past_the_end_shows_the_last(self):
        shown, info = page_of(list(range(45)), 9)
        self.assertEqual((shown, info["page"]), (list(range(40, 45)), 3))
        self.assertEqual(page_of(list(range(45)), 0)[1]["page"], 1)

    def test_one_page_needs_no_pager(self):
        self.assertEqual(page_of(list(range(20)), 1), (list(range(20)), None))
        self.assertEqual(page_of([], 1), ([], None))

    def test_the_page_numbers_stay_short(self):
        _, info = page_of(list(range(400)), 10)
        self.assertEqual(info["numbers"], [1, None, 8, 9, 10, 11, 12, None, 20])


class ThePages(_Tagged):
    def pager(self, html, arg):
        nav = re.search(r'<nav class="pager"[^>]*>.*?</nav>', html, re.S)
        self.assertIsNotNone(nav, "no pager")
        self.assertIn(f"{arg}=2", nav.group(0).replace("&amp;", "&"))
        return nav.group(0)

    def test_runs_on_home(self):
        for i in range(45):
            self.store.add_run(f"{i:012x}", self.omar, f"old-{i}.xlsx", "READY", "DONE", program=self.key,
                               week_start="2026-09-06")
        html = self.client.get("/?all=1").get_data(as_text=True)
        table = re.search(r'<table class="runs">.*?</table>', html, re.S).group(0)
        self.assertEqual(len(re.findall(r'<tr>\s*<td><a href="/runs/', table)), 20)
        total = len(self.store.list_runs())
        self.assertIn(f"1 to 20 of {total}", self.pager(html, "runs_page"))
        last = self.client.get(f"/?all=1&runs_page={-(-total // 20)}").get_data(as_text=True)
        table = re.search(r'<table class="runs">.*?</table>', last, re.S).group(0)
        self.assertEqual(len(re.findall(r'<tr>\s*<td><a href="/runs/', table)), total - 20 * (total // 20) or 20)

    def test_changes_today(self):
        for i in range(25):
            self.store.add_day_log(program=self.key, shift_date=WED.isoformat(), associate=f"Associate {i:02d}",
                                   what="Break moved", user_id=self.omar)
        html = self.client.get(f"/day?program={self.key}&date={WED.isoformat()}").get_data(as_text=True)
        log = re.search(r'<h2 id="daylog-h">.*?</section>', html, re.S).group(0)
        self.assertEqual(log.count("<li>"), 20)
        self.pager(log, "log_page")

    def test_decided_requests(self):
        for i in range(25):
            rid = self.store.add_leave(program=self.key, associate=f"Associate {i:02d}", user_id=self.omar,
                                       kind="Planned leave", first_day="2026-11-02", last_day="2026-11-02", note="")
            self.store.move_leave(rid, "waiting_tm", status="refused", tm_id=self.omar, tm_at=time.time())
        html = self.client.get(f"/requests?program={self.key}").get_data(as_text=True)
        done = re.search(r'<ul class="req-done">.*?</ul>', html, re.S).group(0)
        self.assertEqual(done.count("<li>"), 20)
        self.pager(html, "done_page")

    def test_group_posts(self):
        for i in range(25):
            self.store.add_notify_post(unit=self.key, shift_date=WED.isoformat(), what="change", status="skipped",
                                       reason="Off", made_at=time.time())
        html = self.client.get(f"/notifications?unit={self.key}").get_data(as_text=True)
        posts = re.search(r'<table class="nf-recent">.*?</table>', html, re.S).group(0)
        self.assertEqual(posts.count("<tr>") - 1, 20)  # the head row
        self.pager(html, "posts_page")


if __name__ == "__main__":
    unittest.main()
