# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AD (owner, 2026-10-11: "i need to have the ability to bulk delete or change breaks for several associates at
the same time"; "for bulk actions we can remove bulk of breaks"; sample 04): pick people and a break, then cancel
(with a reason), move by the same amount, set the same time or put back to plan; the effect shows first; one apply is
one change for Undo, held from the group until Send. Anyone a change does not fit is left as they are, with why."""
import html
import re
from collections import Counter

from webapp import bulk_breaks
from webapp.day import CANCELLED
from webapp.tests.test_notify_daybook import WED, _Tagged, hm
from webapp.tests.test_runs import token

WHY = "Queue is long after the outage"


class _Bulk(_Tagged):
    def view(self):
        return self.days.page(self.key, WED)["view"]

    def segs(self):
        return [(l["name"], s) for l in self.view()["lanes"] for s in l["segments"]
                if s["offset"] == 0 and s["status"] == "Present"]

    def with_kind(self, n, untouched=True):
        """``n`` people present who have the most common break kind, by that break's start; their breaks put back to
        the plan after the test."""
        used = {r["associate"] for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])} if untouched else set()
        kinds = Counter(b["kind"] for _, s in self.segs() for b in s["breaks"])
        kind = kinds.most_common(1)[0][0]
        found = sorted(((next(b for b in s["breaks"] if b["kind"] == kind), name) for name, s in self.segs()
                        if name not in used and any(b["kind"] == kind for b in s["breaks"])),
                       key=lambda x: (x[0]["start"], x[1]))
        chosen = []
        for b, name in found:
            if not chosen or b["start"] > chosen[-1][1]["start"]:  # distinct starts, earliest first
                chosen.append((name, b))
            if len(chosen) == n:
                break
        self.assertEqual(len(chosen), n)
        for name, b in chosen:
            self.addCleanup(self.store.clear_actual_break, self.key, WED.isoformat(), name, b["idx"])
        return kind, chosen


class ThePlan(_Bulk):
    def test_cancel_several(self):
        kind, chosen = self.with_kind(5)
        now = chosen[0][1]["start"]  # the first one has started
        names = [n for n, _ in chosen]
        found = bulk_breaks.plan(self.view(), names, kind, "cancel", now=now)
        self.assertEqual([(c["name"], c["new"]) for c in found["changes"]], [(n, CANCELLED) for n in names[1:]])
        self.assertEqual(found["skipped"], [{"name": names[0], "kind": kind, "why": "it has started"}])
        done = self.days.apply_bulk(self.key, WED, names, kind, "cancel", self.omar, why=WHY, now=now)
        self.assertEqual(done, 4)
        rows = {r["associate"]: r for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])}
        self.assertTrue(all(rows[n]["cancelled"] and rows[n]["why"] == WHY for n in names[1:]))
        self.assertNotIn(names[0], rows)
        entry = self.store.day_actions(self.key, WED.isoformat())[-1]
        self.assertEqual((entry["kind"], entry["label"]), ("bulk", "Change several breaks: cancelled 4 breaks"))
        self.assertEqual({i["status"] for i in self.store.notify_items(action_id=entry["id"])}, {"held"})

    def test_cancel_needs_a_reason(self):
        kind, chosen = self.with_kind(2)
        with self.assertRaises(ValueError) as said:
            self.days.apply_bulk(self.key, WED, [n for n, _ in chosen], kind, "cancel", self.omar, why=" ")
        self.assertEqual(str(said.exception), "Say why the breaks are cancelled.")

    def test_shift_several_by_15(self):
        kind, chosen = self.with_kind(2)
        done = self.days.apply_bulk(self.key, WED, [n for n, _ in chosen], kind, "shift", self.omar, amount=15)
        self.assertEqual(done, 2)
        rows = {r["associate"]: r["start"] for r in self.store.list_actual_breaks(self.key, [WED.isoformat()])}
        self.assertEqual([rows[n] for n, _ in chosen], [b["start"] + 15 for _, b in chosen])
        self.assertEqual(self.store.day_actions(self.key, WED.isoformat())[-1]["label"],
                         "Change several breaks: moved 2 breaks")

    def test_set_the_same_time_skips_who_it_does_not_fit(self):
        kind, chosen = self.with_kind(2)
        segs = dict(self.segs())
        a, b = chosen
        at = a[1]["start"] + 5
        outside = not (segs[b[0]]["start"] <= at and at + b[1]["minutes"] <= segs[b[0]]["end"])
        found = bulk_breaks.plan(self.view(), [a[0], b[0]], kind, "set", at=hm(at))
        self.assertEqual(found["changes"][0]["new"], at)
        if outside:
            self.assertEqual(found["skipped"][0]["name"], b[0])
            self.assertTrue(found["skipped"][0]["why"].startswith("it would fall outside the shift"))
        late = bulk_breaks.plan(self.view(), [a[0]], kind, "set", at=hm(segs[a[0]]["end"] - 5))
        self.assertTrue(late["skipped"][0]["why"].startswith("it would fall outside the shift"), late)

    def test_back_to_plan_for_several(self):
        kind, chosen = self.with_kind(2)
        for name, b in chosen:
            self.days.move_break(self.key, WED, name, b["idx"], hm(b["start"] + 10), self.omar)
        done = self.days.apply_bulk(self.key, WED, [n for n, _ in chosen], kind, "plan", self.omar)
        self.assertEqual(done, 2)
        mine = [r for r in self.store.list_actual_breaks(self.key, [WED.isoformat()]) if r["associate"] in dict(chosen)]
        self.assertEqual(mine, [])

    def test_preview_changes_nothing(self):
        kind, chosen = self.with_kind(3)
        before = self.store.list_actual_breaks(self.key, [WED.isoformat()])
        found = self.days.bulk_preview(self.key, WED, [n for n, _ in chosen], kind, "cancel", why=WHY)
        self.assertEqual(self.store.list_actual_breaks(self.key, [WED.isoformat()]), before)
        self.assertEqual(len(found["changes"]), 3)
        self.assertGreaterEqual(found["after"]["now"], found["before"]["now"])  # cancelling only adds people
        self.assertLessEqual(found["after"]["short_hours"], found["before"]["short_hours"])


class ThePage(_Bulk):
    def test_panel_preview_and_apply(self):
        kind, chosen = self.with_kind(2)
        names = [n for n, _ in chosen]
        q = "&".join(f"who={n.replace(' ', '+')}" for n in names)
        url = (f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}&view=bulk&{q}"
               f"&which={kind.replace(' ', '+')}&act=cancel&why={WHY.replace(' ', '+')}&show=1")
        page = html.unescape(self.client.get(url).get_data(as_text=True))
        self.assertIn('<h2 id="bk-h">Change several breaks</h2>', page)
        self.assertRegex(page, r'<button class="danger" type="submit">Cancel 2 breaks</button>')
        got = self.client.post("/day/bulk/apply", data={"csrf_token": token(self.client), "program": self.key,
                                                         "date": WED.isoformat(), "who": names, "which": kind,
                                                         "act": "cancel", "why": WHY}, follow_redirects=True)
        self.assertIn("Cancelled 2 breaks.", html.unescape(got.get_data(as_text=True)))
        floor = html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}")
                              .get_data(as_text=True))
        self.assertRegex(floor, r'<a class="button" href="[^"]*view=bulk[^"]*">Change several breaks</a>')
        self.assertIn("Change several breaks: cancelled 2 breaks", re.sub(r"<[^>]+>", "", floor))


if __name__ == "__main__":
    import unittest
    unittest.main()
