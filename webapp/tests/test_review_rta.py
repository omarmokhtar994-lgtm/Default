# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AC (deep review, findings 4, 10, 11, and Phase AB's open items): + Add never opens on someone marked sick
or on leave, and says who is away; its title reads well and follows Overtime; the "Post to the group" tick knows which
changes post and says when posting is only a preview; the wallboard has a main region and uses the LOB's name; the
RTA's tab title uses the LOB's name."""
import html
import re

from webapp.notify import KINDS
from webapp.tests.test_notify_daybook import SLACK, WED, _Tagged


class _Page(_Tagged):
    def page(self, extra="", program=None):
        q = (program or self.key).replace(" ", "+")
        got = self.client.get(f"/day?program={q}&date={WED.isoformat()}{extra}")
        self.assertEqual(got.status_code, 200)
        return html.unescape(got.get_data(as_text=True))

    def dialog(self, extra="&view=board&add=180"):
        body = self.page(extra)
        found = re.search(r'(?s)<dialog id="add-dialog".*?</dialog>', body)
        self.assertIsNotNone(found)
        return found.group(0)

    def settle(self, mode="on", kinds=",".join(KINDS)):
        self.store.set_notify(self.key, link=SLACK, service="slack", mode=mode, kinds=kinds, hold=120)


class TheWhoList(_Page):
    def test_add_lists_absent_people_last_and_says_so(self):
        sick = "Associate 006"  # 03:00 to 12:00 on Wednesday: on shift at 03:00
        self.days.set_status(self.key, WED, sick, "Sick", self.omar)
        try:
            dialog = self.dialog()
            who = re.search(r'(?s)<select name="associate" required>(.*?)</select>', dialog).group(1)
            options = re.findall(r'<option value="([^"]+)"[^>]*>([^<]+)</option>', who)
            self.assertNotEqual(options[0][0], sick)
            self.assertIn((sick, f"{sick}, 03:00 - 12:00, ENG, sick"), options)
            names = [o[0] for o in options]
            self.assertEqual(names[-1], sick)  # the only absent person goes last
        finally:
            self.days.set_status(self.key, WED, sick, "Present", self.omar)


class TheTitle(_Page):
    def test_title_reads_for_the_interval(self):
        self.assertIn('<h2 id="add-h" data-add-title="Add for 03:00 to 04:00">Add for 03:00 to 04:00</h2>',
                      self.dialog())


class TheTick(_Page):
    def test_the_tick_knows_what_posts(self):
        self.settle(kinds="break,overtime")
        try:
            dialog = self.dialog()
            self.assertIn('data-post-kinds="break overtime"', dialog)
            for what, kind in (("Sick", "private"), ("Coaching", "aux"), ("Overtime", "overtime"),
                               ("Break", "added_break"), ("Late", "late"), ("VTO", "overtime")):
                self.assertIn(f'<label class="k" data-kind="{kind}"><input type="radio" name="what" value="{what}"', dialog)
            brk = re.search(r'(?s)<dialog id="break-dialog".*?</dialog>', self.page()).group(0)
            self.assertIn('class="post-tick"', brk)
            self.settle(kinds="overtime")
            brk = re.search(r'(?s)<dialog id="break-dialog".*?</dialog>', self.page()).group(0)
            self.assertNotIn('class="post-tick"', brk)  # break moves do not post for this LOB
        finally:
            self.settle()

    def test_preview_tick_says_preview(self):
        self.settle(mode="preview")
        try:
            dialog = self.dialog()
            self.assertIn("Show in the preview on the Notifications page", dialog)
            self.assertNotIn("Post to the Slack group", dialog)
        finally:
            self.settle()

    def test_without_script_the_tick_is_plain(self):
        dialog = self.dialog()
        self.assertIn('<label class="post-tick"><input type="checkbox" name="post" value="1" checked> Post to the Slack '
                      'group', dialog)
        self.assertNotRegex(dialog, r'<label class="post-tick"[^>]*hidden')


class TheNames(_Page):
    def test_wallboard_has_main_and_names(self):
        got = self.client.get("/day/wallboard?program=" + self.key.replace(" ", "+") + "&date=2031-01-01")
        body = html.unescape(got.get_data(as_text=True))
        self.assertEqual(body.count("<main"), 1)
        self.assertIn("No schedule for SAKS, NMG Tier 2 today.", body)

    def test_day_title_uses_the_name(self):
        self.assertIn("<title>The day: SAKS, NMG Tier 2 on Team Scheduler</title>", self.page())


if __name__ == "__main__":
    import unittest
    unittest.main()
