# © 2026 Omar Mokhtar. All rights reserved.
"""Phase XY (review findings 7, 11, 12, 13 and the Phase Y copy): markup that screen readers and keyboards need,
checked on the rendered pages of a real ready schedule with its breaks planned."""
import html
import io
import re
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from webapp.programs import ProgramBook


class TheMarkup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from webapp.tests.test_ready import make_ready
        from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait
        cls.dir = Path(tempfile.mkdtemp())
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        today = date.today()
        cls.sunday = today - timedelta(days=(today.weekday() + 1) % 7)
        cls.app, cls.store, _, _ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar Mokhtar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")
        ready = make_ready(cls.dir / "ready.xlsx")
        cls.client.post("/runs", data={"csrf_token": token(cls.client), "kind": "ready", "mode": "QUICK", "program": cls.key,
                                       "week_start": cls.sunday.isoformat(),
                                       "workbook": (io.BytesIO(ready.read_bytes()), "week.xlsx")},
                        content_type="multipart/form-data")
        run_id = cls.store.list_runs()[0]["id"]
        wait(cls.store, run_id, statuses=("DONE", "REJECTED", "FAILED"))
        version = cls.app.extensions["schedules"].versions(run_id)[-1]["id"]
        cls.client.post(f"/schedules/{version}/auto-breaks", data={"csrf_token": token(cls.client), "use": "1"})
        cls.q = cls.key.replace(" ", "+")

    def page(self, url):
        got = self.client.get(url)
        self.assertEqual(got.status_code, 200, url)
        return got.get_data(as_text=True)

    def day(self, view=""):
        return self.page(f"/day?program={self.q}&date={self.sunday.isoformat()}" + (f"&view={view}" if view else ""))

    def test_the_first_link_skips_to_the_page(self):
        page = self.page("/")
        after_body = page[page.index("<body>"):]
        self.assertEqual(re.search(r"<a [^>]*>[^<]*</a>", after_body).group(0),
                         '<a class="skip" href="#main">Skip to the page</a>')
        self.assertIn('<main id="main" tabindex="-1">', page)

    def test_timeline_lanes_are_groups(self):
        lanes = re.findall(r'<svg class="tl-track"[^>]*>', self.day())
        self.assertTrue(lanes)
        for lane in lanes:
            self.assertNotIn('role="img"', lane)
            self.assertIn('role="group"', lane)
            self.assertRegex(lane, r'aria-label="[^"]+"')

    def test_each_add_link_names_its_interval(self):
        cells = re.findall(r'<b>(\d\d:\d\d)</b><small>to \d\d:\d\d</small><a class="rb-add" [^>]*>(.*?)</a>', self.day("board"))
        self.assertTrue(cells)
        for start, text in cells:
            self.assertEqual(text, f'+ Add<span class="sr-only"> to {start}</span>')

    def test_scroll_boxes_are_named_regions(self):
        pages = [self.page(f"/week?program={self.q}&week={self.sunday.isoformat()}"), self.day("adherence")]
        boxes = [box for page in pages for box in re.findall(r'<div class="scroll"[^>]*>', page)]
        self.assertGreaterEqual(len(boxes), 3)
        for box in boxes:
            self.assertIn('role="region"', box)
            self.assertIn('tabindex="0"', box)
            self.assertRegex(html.unescape(box), r'aria-label="[^"]+ \(scrolls sideways\)"')

    def test_every_scroll_box_in_the_templates_is_a_named_region(self):
        """The same box on every page: a keyboard reaches it and a screen reader names it."""
        templates = Path(__file__).resolve().parents[1] / "templates"
        unnamed = [f"{f.name}: {box}" for f in sorted(templates.glob("*.html"))
                   for box in re.findall(r'<div class="scroll"[^>]*>', f.read_text())
                   if not ('role="region"' in box and 'tabindex="0"' in box and "aria-label=" in box)]
        self.assertEqual(unnamed, [])

    def test_the_timeline_note_matches_the_new_colours(self):
        page = html.unescape(self.day())
        self.assertIn("Shifts are the blue bars; breaks are the marks on them.", page)
        self.assertNotIn("breaks in amber", page)


CSS = Path(__file__).resolve().parents[1] / "static" / "app.css"
# Phase Y proposal, approved by the owner (evidence/phase_y/proposal.css, measured in PALETTE.md)
NIGHT = {"--action": "#E6EDF5", "--action-hover": "#FFFFFF", "--on-action": "#0E1A2B", "--edge": "#627389",
         "--done": "#54749A", "--covered-text": "#2BC4B4", "--over-text": "#9086EE", "--on-covered": "#0E1A2B",
         "--on-short": "#0E1A2B", "--on-gap": "#0E1A2B", "--on-over": "#0E1A2B", "--selected": "#1B2D47",
         "--ch-email": "#4D7D8D"}
DAY = {"--action": "#12233A", "--action-hover": "#22385A", "--on-action": "#FFFFFF", "--edge": "#77869A",
       "--done": "#7692B4", "--covered-text": "#0B776C", "--over-text": "#715ED8", "--covered": "#06A496",
       "--short": "#C98304", "--gap": "#D53D38", "--over": "#7560E3", "--on-covered": "#0E1A2B",
       "--on-short": "#0E1A2B", "--on-gap": "#FFFFFF", "--on-over": "#FFFFFF", "--selected": "#E3EAF2"}


def block(text, opener):
    """The body of the first {...} that follows ``opener`` (braces balanced)."""
    start = text.index(opener)
    i = text.index("{", start + len(opener) - 1)
    depth, j = 0, i
    while True:
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        if depth == 0:
            return text[i + 1:j]
        j += 1


def tokens(body):
    return {k: v.upper() for k, v in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9A-Fa-f]{6})", body)}


class TheStylesheet(unittest.TestCase):
    """Phase XY task 6 (review finding 14 and the Phase Y colours): sizes follow the reader's text size, and the
    approved colours are in every look."""

    @classmethod
    def setUpClass(cls):
        cls.css = re.sub(r"/\*.*?\*/", "", CSS.read_text(), flags=re.S)

    def test_every_font_size_is_in_rem(self):
        screen = self.css.replace(block(self.css, "@media print"), "")
        px = re.findall(r"font-size\s*:\s*[\d.]+px[^;}]*", screen) + re.findall(r"\bfont\s*:[^;}]*?\b[\d.]+px[^;}]*", screen)
        self.assertEqual(px, [])

    def test_the_night_tokens_are_the_approved_ones(self):
        night = {}
        for at in [i for i in range(len(self.css)) if self.css.startswith(":root {", i)]:  # every plain :root block
            night.update(tokens(block(self.css[at:], ":root {")))
        self.assertEqual({k: night.get(k) for k in NIGHT}, NIGHT)

    def test_the_proposed_tokens_are_in_both_day_blocks(self):
        device = tokens(block(block(self.css, "@media (prefers-color-scheme: light)"), ':root:not([data-theme="dark"])'))
        picked = tokens(block(self.css, ':root[data-theme="light"]'))
        self.assertEqual({k: device.get(k) for k in DAY}, DAY)
        self.assertEqual({k: picked.get(k) for k in DAY}, DAY)


if __name__ == "__main__":
    unittest.main()
