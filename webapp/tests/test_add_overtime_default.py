# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "Yes" to + Add opening on Overtime at an hour when nobody is on shift; sample 06):
+ Add opens on Overtime for the person whose shift starts right after (or ends right before) the interval, placed and
long enough to cover it; an interval with someone on shift still opens on Break. Fix the rest of the day's breaks
applies as one change for Undo and waits for Send like the other bulk changes."""
import html
import re

from webapp.tests.test_notify_daybook import WED, _Tagged
from webapp.tests.test_runs import token


class _Add(_Tagged):
    def view(self):
        return self.days.page(self.key, WED)["view"]

    def empty_hour(self):
        """An hour of Wednesday with nobody present on shift in it: the quietest hour, its people marked sick (put
        back to present after the test). The fixture day has someone on shift every hour."""
        lanes = [(l["name"], s) for l in self.view()["lanes"] for s in l["segments"]
                 if s["offset"] == 0 and s["status"] == "Present"]
        on = {t: [n for n, s in lanes if s["start"] < t + 60 and t < s["end"]] for t in range(0, 1440, 60)}
        t = min((t for t in on if on[t]), key=lambda t: (len(on[t]), t))
        for name in on[t]:
            self.days.set_status(self.key, WED, name, "Sick", self.omar)
            self.addCleanup(self.days.set_status, self.key, WED, name, "Present", self.omar)
        return t

    def dialog(self, t):
        got = self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&view=board&add={t}")
        return re.search(r'(?s)<dialog id="add-dialog".*?</dialog>', html.unescape(got.get_data(as_text=True))).group(0)


class TheDefaults(_Add):
    def test_nobody_on_shift_opens_on_overtime(self):
        t = self.empty_hour()
        self.assertIsNotNone(t, "the fixture day needs an hour with nobody on shift")
        dialog = self.dialog(t)
        self.assertRegex(dialog, r'<input type="radio" name="what" value="Overtime" checked>')
        first = re.search(r'<select name="associate" required><option value="([^"]+)" data-start="(\d+)" '
                          r'data-end="(\d+)"', dialog)
        start, end = int(first.group(2)), int(first.group(3))
        segs = [s for l in self.view()["lanes"] for s in l["segments"] if s["offset"] == 0 and s["status"] == "Present"]
        self.assertFalse([s for s in segs if s["start"] < t + 60 and t < s["end"]])  # nobody present then
        nearest = min(min(abs(s["start"] - (t + 60)), abs(t - s["end"])) for s in segs)
        self.assertEqual(min(abs(start - (t + 60)), abs(t - end)), nearest)  # the shift next to the hour
        side = "before" if start >= t + 60 else "after"
        self.assertRegex(dialog, rf'<input type="radio" name="side" value="{side}" checked')
        minutes = int(re.search(r'<select name="minutes">.*?<option value="(\d+)" selected', dialog, re.S).group(1))
        reach = start - t if side == "before" else t + 60 - end
        self.assertGreaterEqual(minutes, min(reach, 120))  # long enough to cover the hour (2 hours at most)
        self.assertIn("data-keep-minutes", dialog)

    def test_someone_on_shift_still_opens_on_break(self):
        segs = [s for l in self.view()["lanes"] for s in l["segments"] if s["offset"] == 0 and s["status"] == "Present"]
        t = segs[0]["start"] - segs[0]["start"] % 60 + 60
        dialog = self.dialog(t)
        self.assertRegex(dialog, r'<input type="radio" name="what" value="Break" checked>')
        self.assertNotIn("data-keep-minutes", dialog)


class TheFixBreaks(_Add):
    def test_fix_breaks_apply_is_one_held_change(self):
        used = set()
        moves = []
        for _ in range(2):
            name, idx, kind, start, _ = self.with_breaks(skip=used)
            used.add(name)
            self.addCleanup(self.store.clear_actual_break, self.key, WED.isoformat(), name, idx)
            moves.append(f"{name}|{idx}|{start + 5}")
        got = self.client.post("/day/replan/apply", data={"csrf_token": token(self.client), "program": self.key,
                                                           "date": WED.isoformat(), "move": moves},
                               follow_redirects=True)
        self.assertIn("Moved 2 breaks.", html.unescape(got.get_data(as_text=True)))
        entry = self.store.day_actions(self.key, WED.isoformat())[-1]
        self.assertEqual((entry["kind"], entry["label"]), ("bulk", "Fix breaks moved 2 breaks"))
        self.assertEqual({i["status"] for i in self.store.notify_items(action_id=entry["id"])}, {"held"})


if __name__ == "__main__":
    import unittest
    unittest.main()
