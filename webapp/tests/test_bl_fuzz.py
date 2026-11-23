# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL audit: random inputs against the new code, each checked against a simple model written separately from it (an oracle) or against an
invariant that must hold for every input. Seeds are fixed, so a failure can be repeated; the failing seed is in the message.

- open hours: ``ranges`` and ``apply`` against a minute-by-minute model, with windows that pass midnight and the week wrapping;
- site rules: every random document is refused in words or gives, at every minute of every day, shares that add to 100 and match a brute-force lookup;
- day totals of email: every email kept, spread within one of even;
- the roster options: no cell value, however odd, makes the reader raise;
- the shift length rule: against its definition;
- the months ahead: for random histories (gaps, closed weekdays, short, long), no crash and the figures add up, stay non-negative and keep their order.
Made-up data only."""
import random
import unittest
from datetime import date, timedelta

from webapp import open_hours as H, outlook as O, sites as S
from webapp.tests.test_bi_volumes import KEY, SUN, book
from webapp.tests.test_bl_outlook import long_history, yearly
from webapp.volumes_io import parse_long

DAYS7 = range(7)


def rng(seed):
    return random.Random(20261107 * 1000 + seed)


class TheOpenHoursAgainstAMinuteByMinuteModel(unittest.TestCase):
    def model(self, days, day, minute):
        """Open at this minute of this weekday? None when nothing is set for the day (and nothing spills into it)."""
        own = days.get(str(day), "unset")
        spill = days.get(str((day - 1) % 7))
        spilling = isinstance(spill, list) and minute < spill[1] - 1440
        inside = isinstance(own, list) and own[0] <= minute < min(own[1], 1440)
        if inside or spilling:
            return True
        return None if own == "unset" else False

    def test_random_weeks(self):
        for seed in range(150):
            r = rng(seed)
            days = {}
            for d in DAYS7:
                kind = r.choice(["unset", "closed", "window", "window", "overnight"])
                if kind == "closed":
                    days[str(d)] = None
                elif kind == "window":
                    start = r.randrange(0, 1380, 15)
                    days[str(d)] = [start, r.randrange(start + 15, min(start + 1440, 1440) + 1, 15)]
                elif kind == "overnight":
                    start = r.randrange(600, 1440, 15)
                    days[str(d)] = [start, r.randrange(1441, start + 1441, 15)]
            hours = H.read({"min_cover": r.randrange(0, 4), "days": days})
            self.assertEqual(hours["days"], days, f"seed {seed}: a valid week must read back as it was")
            for d in DAYS7:
                ranges = H.ranges(hours, d)
                for step in (15, 30, 60):
                    needs = [r.choice([0, 0.4, 1, 3.7]) for _ in range(1440 // step)]
                    got = H.apply(needs, ranges, step, hours["min_cover"], H.free_from(hours, d))
                    for i, n in enumerate(needs):
                        # open at any minute of the interval?
                        flags = {self.model(days, d, m) for m in range(i * step, (i + 1) * step)}
                        if flags == {None}:
                            self.assertEqual(got[i], n, f"seed {seed} day {d} step {step} interval {i}: unset days are left alone")
                        elif True in flags:
                            self.assertEqual(got[i], max(n, hours["min_cover"]), f"seed {seed} day {d} step {step} interval {i}")
                        else:
                            self.assertEqual(got[i], 0, f"seed {seed} day {d} step {step} interval {i}")

    def test_the_form_never_raises_anything_but_a_value_error(self):
        words = ["", "09:00", "9:00", "24:00", "00:00", "25:00", "9am", "12:61", "-1:00", "ab", "23:59", " 07:30 ", "7", "९:००"]
        for seed in range(200):
            r = rng(seed)
            form = {"min_cover": r.choice(["1", "0", "20", "21", "-1", "x", "", "1.5", " 2 "])}
            for d in DAYS7:
                form[f"{d}.from"], form[f"{d}.to"] = r.choice(words), r.choice(words)
                form[f"{d}.closed"] = r.choice(["", "", "1", "on"])
            try:
                got = H.from_form(form, r.choice(["Phone", "Chat", "Email"]))
            except ValueError:
                continue
            self.assertEqual(H.read(got), got, f"seed {seed}: what the form accepts is what is kept")


class TheSiteRulesAgainstABruteForceLookup(unittest.TestCase):
    def random_doc(self, r):
        names = [f"Site {i}" for i in range(r.randrange(1, 4))]
        rules = []
        for _ in range(r.randrange(0, 5)):
            start = r.randrange(0, 1440, 30)
            rules.append({"channel": r.choice(["Phone", "Chat", "Email"]), "days": r.sample(range(7), r.randrange(1, 4)), "from": start,
                          "to": r.randrange(start + 30, start + 1441, 30),
                          "shares": dict(zip(names, self.shares(r, len(names))))})
        return {"sites": [{"name": n, "lob": ""} for n in names], "rules": rules}

    def shares(self, r, n):
        cuts = sorted(r.randrange(0, 101) for _ in range(n - 1))
        parts = [b - a for a, b in zip([0] + cuts, cuts + [100])]
        return [float(p) for p in parts]

    def brute(self, doc, channel, day, minute):
        first = doc["sites"][0]["name"]
        for rule in doc["rules"]:
            if rule["channel"] != channel:
                continue
            for d in rule["days"]:
                # a minute of weekday ``day`` belongs to the window if it falls in the rule's own day, or in the part past midnight of the day before
                own = d == day and rule["from"] <= minute < min(rule["to"], 1440)
                spill = (d + 1) % 7 == day and rule["to"] > 1440 and minute < rule["to"] - 1440
                if own or spill:
                    return rule["shares"]
        return {n["name"]: (100.0 if n["name"] == first else 0.0) for n in doc["sites"]}

    def test_random_documents(self):
        accepted = refused = 0
        for seed in range(120):
            r = rng(seed)
            doc = self.random_doc(r)
            try:
                clean = S.clean(doc)
            except ValueError as exc:
                refused += 1
                self.assertIn("overlap", str(exc), f"seed {seed}: the only way these documents are wrong is overlap, got {exc}")
                continue
            accepted += 1
            for _ in range(60):
                channel, day, minute = r.choice(["Phone", "Chat", "Email"]), r.randrange(7), r.randrange(1440)
                got = S.split(clean, channel, day, minute)
                self.assertAlmostEqual(sum(got.values()), 100.0, places=6, msg=f"seed {seed}")
                self.assertTrue(all(0 <= v <= 100 for v in got.values()), f"seed {seed}")
                self.assertEqual(got, self.brute(clean, channel, day, minute), f"seed {seed} {channel} day {day} minute {minute}")
            table = S.table(clean, "Chat", 30)
            for d in DAYS7:
                for i in (0, 7, 23, 47):
                    self.assertEqual(table[d][i], S.split(clean, "Chat", d, i * 30), f"seed {seed}")
            for d, runs in S.gaps(clean, "Phone").items():
                for lo, hi in runs:
                    covered = [m for rule in clean["rules"] if rule["channel"] == "Phone" for m in range(lo, hi)
                               if self.brute({**clean, "rules": [rule]}, "Phone", d, m) == rule["shares"]
                               and any(rr["channel"] == "Phone" and d in rr["days"] and rr["from"] <= m < rr["to"] for rr in [rule])]
                    self.assertEqual(covered, [], f"seed {seed}: a gap must not be covered")
        self.assertGreater(accepted, 20)
        self.assertGreater(refused, 3)       # the generator really does produce overlaps, and they are refused

    def test_names_that_a_spreadsheet_would_read_as_formulas_never_get_in(self):
        for first in "=+-@":
            for tail in ("x", "cmd|' /C calc'!A0", " 1"):
                with self.assertRaises(ValueError):
                    S.clean({"sites": [{"name": first + tail, "lob": ""}], "rules": []})


class TheDayTotalsOfEmail(unittest.TestCase):
    def test_random_totals_are_all_kept_and_spread_evenly(self):
        for seed in range(80):
            r = rng(seed)
            step = r.choice([5, 10, 15, 20, 30, 60])
            days = [date(2026, 3, 1) + timedelta(days=k) for k in range(r.randrange(1, 12))]
            totals = [r.choice([0, 1, 7, 99, 100, 1439, 1440, 1441, 123456]) for _ in days]
            table = [["Date", "Emails"], *[[d, t] for d, t in zip(days, totals)]]
            got = parse_long(table, "Email", step, date(2026, 11, 7))
            self.assertEqual(got.problems, [], f"seed {seed}")
            rows = got.rows["Email"]
            for d, t in zip(days, totals):
                kept = [x[2] for x in rows if x[0] == d.isoformat()]
                self.assertEqual((len(kept), sum(kept)), (1440 // step, t), f"seed {seed} {d} step {step}")
                self.assertLessEqual(max(kept) - min(kept), 1, f"seed {seed}")

    def test_odd_cells_are_refused_never_a_crash(self):
        cells = [-1, 2.5, "x", None, "", True, 10 ** 12, float("nan"), float("inf"), "1e3", " 12 ", "١٢"]
        for seed in range(100):
            r = rng(seed)
            table = [["Date", "Emails", "AHT"], *[[r.choice([date(2026, 3, 1), "2026-03-02", "nope", None, 5]), r.choice(cells), r.choice(cells + [480])]
                                                  for _ in range(r.randrange(1, 6))]]
            try:
                got = parse_long(table, "Email", 60, date(2026, 11, 7))
            except ValueError:
                continue
            self.assertTrue(got.problems or got.rows, f"seed {seed}: either something was kept or something was said")
            if got.problems:
                self.assertEqual(got.rows, {}, f"seed {seed}: one bad row means nothing is kept")


class TheRosterOptionsNeverRaise(unittest.TestCase):
    def test_every_odd_cell(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "_tools"))
        import l632_universal_scheduler as E
        values = [None, "", " ", 0, 1, 5, 6, 7, 8.5, "8.5", "8,5", "9h", "9 hours", "abc", "5-6", "+5", "-1", float("nan"), float("inf"), True, False,
                  10 ** 9, "٥", "Part time", "part-time", "FT", "full", "PT", "x" * 400, "\u0000", "5\n", ["5"], {"a": 1}, b"5"]
        for kind in ("hours", "type", "days", "count"):
            for v in values:
                try:
                    ok, got = E._roster_option(kind, v)
                except Exception as exc:                                  # noqa: BLE001
                    self.fail(f"{kind} {v!r} raised {type(exc).__name__}: {exc}")
                self.assertIsInstance(ok, bool)
                if ok and got is not None:
                    if kind == "hours":
                        self.assertTrue(240 <= got <= 960 and got % 1 == 0, (kind, v, got))
                    elif kind in ("days", "count"):
                        self.assertTrue(0 <= got <= 6 and isinstance(got, int), (kind, v, got))
                    else:
                        self.assertIsInstance(got, bool)
                if not ok:
                    self.assertIsNone(got)

    def test_valid_numbers_round_trip(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "_tools"))
        import l632_universal_scheduler as E
        for hours in (4, 4.5, 5, 8, 8.5, 9, 10.75, 16):
            self.assertEqual(E._roster_option("hours", hours), (True, int(round(hours * 60))))
            self.assertEqual(E._roster_option("hours", f"{hours} h"), (True, int(round(hours * 60))))
        for n in range(0, 7):
            self.assertEqual(E._roster_option("days", n), (True, n))
            self.assertEqual(E._roster_option("count", str(n)), (True, n))
        for bad in (3.99, 16.01, 17, 0, 0.5, 100):
            self.assertEqual(E._roster_option("hours", bad), (False, None), bad)

    def test_the_shift_length_rule_against_its_definition(self):
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine" / "_tools"))
        import l632_universal_scheduler as E
        for seed in range(300):
            r = rng(seed)
            length = r.choice([None, 300, 450, 510, 540, 600])
            part = r.random() < 0.5
            associate = E.Associate(index=0, row=1, slot=1, emp_id=None, email="", name="A", tl="", language="", shift_minutes=length, part_time=part)
            shift = E.Shift(index=0, label="x", start_min=0, end_min=0, duration_min=r.choice([295, 300, 305, 306, 510, 540, 545, 550]),
                            part_time_only=r.random() < 0.4)
            if length is None:
                want = not (shift.part_time_only and not part)
            else:
                want = abs(shift.duration_min - length) <= 5
            self.assertEqual(E.shift_length_allows(associate, shift), want, f"seed {seed}")


class TheMonthsAheadForRandomHistories(unittest.TestCase):
    def test_random_weekly_series(self):
        for seed in range(150):
            r = rng(seed)
            n = r.choice([3, 4, 10, 25, 26, 40, 51, 52, 55, 56, 60, 104, 110])
            start = date(2025, 1, 5) + timedelta(weeks=r.randrange(0, 20))
            base, slope = r.uniform(50, 5000), r.uniform(-3, 8)
            season = r.choice([lambda w: 1.0, yearly, lambda w: 1.0 + 0.5 * (w % 7 == 0)])
            weekly = [(start + timedelta(weeks=k), max(0.0, (base + slope * k) * season(O.woy(start + timedelta(weeks=k))) * r.uniform(0.9, 1.1)))
                      for k in range(n) if r.random() > 0.08]
            if len(weekly) < 3:
                continue
            model = O.fit(weekly, left_out=[w for w, _ in weekly if r.random() < 0.05] if len(weekly) > 10 else [])
            for ahead in (-3, 0, 1, 8, 9, 26, 52, 80):
                got = O.project(model, model.last + timedelta(weeks=ahead), yoy=r.choice([None, None, -30.0, 0.0, 15.0, 200.0]),
                                typed=r.choice([None, {}, {m: r.uniform(50, 200) for m in range(1, 13)}]))
                if got is None:
                    self.assertEqual(model.kind, "trend", f"seed {seed}")
                    self.assertGreater(ahead, O.TREND_REACH, f"seed {seed}")
                    continue
                self.assertGreaterEqual(got["expected"], 0.0, f"seed {seed}")
                self.assertLessEqual(got["low"], got["expected"] + 1e-9, f"seed {seed}")
                self.assertLessEqual(got["expected"], got["high"] + 1e-9, f"seed {seed}")
                self.assertIn(got["basis"], O.BAND, f"seed {seed}")

    def test_random_histories_through_the_book(self):
        for seed in range(25):
            r = rng(seed)
            store, vb = book()
            weeks = r.choice([2, 3, 8, 20, 30, 48, 60, 90])
            long_history(store, weeks, base=r.uniform(500, 9000), slope=r.uniform(-4, 12), season=r.choice([lambda w: 1.0, yearly]),
                         skip=set(r.sample(range(weeks), min(weeks // 6, weeks))))
            if r.random() < 0.5:
                vb.add_driver(KEY, "events", {"kind": r.choice(["Promotion", "Holiday", "Outage"]), "name": "E", "channels": ["Phone"],
                                              "start": (SUN + timedelta(days=r.randrange(5, 200))).isoformat(),
                                              "end": (SUN + timedelta(days=r.randrange(200, 260))).isoformat(), "change": r.choice([-60, -10, 25, 80])}, 1)
            if r.random() < 0.3:
                vb.set_growth(KEY, {"Phone": str(r.choice([-20, 0, 10, 40])), "Chat": "", "Email": ""}, "growth", 1)
            months = r.choice([1, 3, 6, 12, 24])
            try:
                got = vb.outlook(KEY, "Phone", start=SUN + timedelta(weeks=1), months=months)
            except ValueError:
                self.assertLess(weeks, 3 + 1, f"seed {seed}: only a history too short may be refused")
                continue
            self.assertEqual(sum(m["expected"] for m in got["months"]), got["total"]["expected"], f"seed {seed}")
            for w in got["weeks"]:
                self.assertEqual(sum(d["expected"] for d in w["days"]), w["expected"], f"seed {seed}")
                self.assertTrue(all(d["low"] <= d["expected"] <= d["high"] and d["expected"] >= 0 for d in w["days"]), f"seed {seed}")
            self.assertTrue(all(m["low"] <= m["expected"] <= m["high"] for m in got["months"]), f"seed {seed}")
            self.assertEqual(len(got["months"]), len({m["month"] for m in got["months"]}), f"seed {seed}: each month once")
            if got["model"]["kind"] == "trend":
                self.assertLessEqual(len(got["weeks"]), O.TREND_REACH + 2, f"seed {seed}")


if __name__ == "__main__":
    unittest.main()
