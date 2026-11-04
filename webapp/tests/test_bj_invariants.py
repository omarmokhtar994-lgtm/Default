# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "dont come back unless this is 500% accurate and working 0 problems"): rules that must hold for any input, checked on
many seeded random cases (no new dependency): the same N whole weeks for every weekday, a forecast that always adds up to its total, a waterfall that adds up
exactly, drivers that never leave their ranges, uploads that either keep everything or nothing. A failing case prints its seed."""
import io
import random
import shutil
import unittest
from datetime import date, timedelta

from openpyxl import load_workbook

from webapp import drivers as D
from webapp import erlang, volumes_draft as V, volumes_formulas as VF
from webapp.tests.test_bi_volumes import KEY, STEP, SUN, TODAY, book, weights
from webapp.volumes_io import CHANNELS, parse_grid

WEEK = [SUN + timedelta(days=k) for k in range(7)]


def random_history(rng, store, channel="Phone", weeks=12):
    """A history with holes: closed weekdays, missing days, outage days and holiday weeks; known to be hard for a naive reader."""
    closed = {4, 5} if rng.random() < 0.3 else set()
    holiday_weeks = {w for w in range(1, weeks + 1) if rng.random() < 0.12}
    rows = []
    for w in range(1, weeks + 1):
        scale = rng.uniform(0.9, 1.1) * (0.3 if w in holiday_weeks else 1.0)
        for k in range(7):
            day = SUN - timedelta(weeks=w) + timedelta(days=k)
            if day.weekday() in closed or rng.random() < 0.04:
                continue
            total = 7000 / 7 * scale * (1.3 if day.weekday() in (6, 0) else 1.0) * (0.1 if rng.random() < 0.03 else 1.0)
            wts = weights(day.weekday())
            s = sum(wts.values())
            for h, v in wts.items():
                rows.append((day.isoformat(), h * 60, round(total * v / s), 300.0))
    store.replace_volume_rows(KEY, channel, rows, 1)


def random_drivers(rng, vb):
    for _ in range(rng.randint(0, 3)):
        start = SUN + timedelta(days=rng.randint(-5, 9))
        try:
            vb.add_driver(KEY, "events", {"kind": rng.choice(D.KINDS), "name": f"E{rng.randint(1, 99)}", "channels": rng.sample(CHANNELS, rng.randint(1, 3)),
                                          "start": start.isoformat(), "end": (start + timedelta(days=rng.randint(0, 5))).isoformat(),
                                          "change": rng.choice((-60, -30, -5, 7, 25, 80)), "after_days": rng.choice((0, 0, 2)),
                                          "after_change": rng.choice((-20, 15))}, 1)
        except ValueError:
            pass
    for _ in range(rng.randint(0, 3)):
        start = SUN + timedelta(days=rng.randint(-10, 5))
        move = rng.random() < 0.5
        ch = rng.choice(CHANNELS)
        row = {"channel": ch, "start": start.isoformat(), "end": (start + timedelta(days=rng.randint(0, 20))).isoformat(), "change": rng.choice((-40, -15, -5, 10, 30)),
               "move_to": rng.choice([c for c in CHANNELS if c != ch]) if move else "", "move_share": rng.choice((20, 50, 100)) if move else 0}
        if row["change"] > 0:
            row["move_to"], row["move_share"] = "", 0
        try:
            vb.add_driver(KEY, "ai", row, 1)
        except ValueError:
            pass
    if rng.random() < 0.4:
        vb.set_growth(KEY, {ch: rng.choice((-20, 0, 6, 40)) for ch in rng.sample(CHANNELS, 2)}, rng.choice(D.METHODS), 1)
    if rng.random() < 0.4:
        vb.set_last_year(KEY, SUN, {ch: rng.randint(1000, 20000) for ch in rng.sample(CHANNELS, 2)}, 1)


class TheEqualDaysRule(unittest.TestCase):
    """Owner: "must be same count of days, so no if 6 Sundays then 6 Saturdays"."""

    def test_every_open_weekday_is_read_from_the_same_weeks_on_random_histories(self):
        for seed in range(60):
            rng = random.Random(seed)
            store, vb = book()
            random_history(rng, store)
            wanted = rng.randint(3, 10)
            skip = [(SUN - timedelta(weeks=rng.randint(1, 12))).isoformat() for _ in range(rng.randint(0, 3))]
            f = vb.forecast(KEY, "Phone", SUN, total=8000, weeks=wanted, skip_weeks=skip)
            if f["error"]:
                self.assertEqual(f["calls"], [], seed)
                continue
            used = f["weeks"]["used"]
            self.assertLessEqual(len(used), wanted, seed)
            self.assertEqual(len(set(used)), len(used), seed)
            self.assertFalse(set(used) & set(skip), seed)
            self.assertTrue(all(date.fromisoformat(u) < SUN for u in used), seed)
            counts = {n for n in f["profile"]["weeks_used"].values() if n}
            self.assertEqual(counts, {len(used)}, (seed, f["profile"]["weeks_used"]))      # one count for all open weekdays
            days = vb.history(KEY, "Phone", SUN, wanted)
            for name_index in range(7):
                if f["profile"]["weeks_used"][("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")[name_index]]:
                    wd = (name_index - 1) % 7
                    present = [d for d in days if d.weekday() == wd and (d - timedelta(days=(d.weekday() + 1) % 7)).isoformat() in used]
                    self.assertEqual(len(present), len(used), (seed, wd))                  # as many Saturdays as Sundays

    def test_a_week_with_one_missing_open_day_is_left_out_whole(self):
        for seed in range(20):
            rng = random.Random(1000 + seed)
            store, vb = book()
            random_history(rng, store, weeks=10)
            f = vb.forecast(KEY, "Phone", SUN, total=8000)
            if f["error"]:
                continue
            open_days = [w for w, n in f["profile"]["weeks_used"].items() if n]
            for start in f["weeks"]["used"]:
                sunday = date.fromisoformat(start)
                have = {d for d in vb.history(KEY, "Phone", SUN, 6) if sunday <= d <= sunday + timedelta(days=6)}
                self.assertEqual(len(have), 7 - (7 - len(open_days)) if len(open_days) < 7 else 7, (seed, start))


class TheForecastAlwaysAddsUp(unittest.TestCase):
    def test_random_histories_drivers_and_settings(self):
        for seed in range(80):
            rng = random.Random(5000 + seed)
            store, vb = book(rng.choice(("sl", "volume")))
            for ch in CHANNELS:
                if rng.random() < 0.85:
                    random_history(rng, store, ch)
            random_drivers(rng, vb)
            ch = rng.choice(CHANNELS)
            kind = rng.choice(("typed", "typed_days", "suggestion", "last_year"))       # the last two give no grid: the total is the planner's
            kwargs = {}
            if kind == "typed":
                kwargs["total"] = rng.randint(0, 20000)
            elif kind == "typed_days":
                kwargs.update(total=rng.randint(2000, 20000), day_totals={rng.randint(0, 6): rng.randint(0, 900)})
            elif kind == "last_year":
                kwargs["base"] = "last_year"
            try:
                f = vb.forecast(KEY, ch, SUN, weeks=rng.randint(3, 12), **kwargs)
            except ValueError:
                continue                                                                 # a refusal in words is allowed; a crash is not
            tag = (seed, kind, ch)
            if kind in ("suggestion", "last_year") and not f["error"]:
                self.assertEqual((f["calls"], f["total"], f["source"]), ([], None, None), tag)       # never made up from the suggestion
                if f["suggestion"]:
                    sug = f["suggestion"]
                    self.assertEqual(sug["base"] + sum(x["delta"] for x in sug["steps"]), sug["final"], tag)
                continue
            if f["error"]:
                self.assertEqual(f["calls"], [], tag)
                self.assertTrue(f["error"].strip(), tag)
                continue
            calls = f["calls"]
            self.assertEqual(len(calls), 7, tag)
            self.assertTrue(all(len(r) == 1440 // STEP for r in calls), tag)
            self.assertTrue(all(isinstance(v, int) and v >= 0 for r in calls for v in r), tag)
            self.assertEqual(sum(map(sum, calls)), f["total"], tag)                      # the grid is exactly the total
            for d, v in kwargs.get("day_totals", {}).items():
                if v <= f["total"]:
                    self.assertEqual(sum(calls[d]), v, tag)
            for name in f["profile"]["closed"]:
                if not kwargs.get("day_totals"):
                    self.assertEqual(sum(calls[("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat").index(name)]), 0, tag)
            sug = f["suggestion"]
            if sug:
                self.assertEqual(sug["base"] + sum(x["delta"] for x in sug["steps"]), sug["final"], tag)
                self.assertGreaterEqual(sug["final"], 0, tag)
                if sug["low"] is not None:
                    self.assertLessEqual(sug["low"], sug["final"], tag)
                    self.assertLessEqual(sug["final"], sug["high"], tag)
            if f["needs"]:
                self.assertTrue(all(n >= 0 for r in f["needs"] for n in r), tag)
                self.assertTrue(all((n == 0) == (c == 0) for rn, rc in zip(f["needs"], calls) for n, c in zip(rn, rc)), tag)    # people only where there are contacts

    def test_a_saved_forecast_is_never_moved_by_later_changes(self):
        for seed in range(25):
            rng = random.Random(9000 + seed)
            store, vb = book()
            random_history(rng, store)
            try:
                vb.save_forecast(KEY, "Phone", SUN, rng.randint(1000, 15000), {}, 1, weeks=rng.randint(3, 9))
            except ValueError:
                continue
            before = vb.forecast(KEY, "Phone", SUN)
            random_history(rng, store)                                                   # a different history
            random_drivers(rng, vb)
            vb.set_settings(KEY, {"Phone": {"sl_target": rng.choice((70, 90)), "shrinkage": rng.choice((10, 40))}}, 1)
            after = vb.forecast(KEY, "Phone", SUN)
            self.assertEqual(after["calls"], before["calls"], seed)
            self.assertEqual((after["source"], after["total"]), ("saved", before["total"]), seed)

    def test_the_people_needed_always_meet_the_target_or_the_occupancy_cap_binds(self):
        for seed in range(30):
            rng = random.Random(7000 + seed)
            store, vb = book()
            random_history(rng, store)
            f = vb.forecast(KEY, "Phone", SUN, total=rng.randint(2000, 30000))
            if f["error"]:
                continue
            s = vb.settings(KEY)["Phone"]
            for day in range(7):
                for i, c in enumerate(f["calls"][day]):
                    if not c:
                        continue
                    n = f["needs"][day][i]
                    self.assertGreaterEqual(erlang.service_level(n, c, f["aht"], STEP * 60, s["sl_seconds"]) + 1e-9, s["sl_target"] / 100.0, (seed, day, i))
                    self.assertLessEqual(erlang.erlangs(c, f["aht"], STEP * 60) / n, s["occupancy"] / 100.0 + 1e-9, (seed, day, i))


class TheDriversStayInRange(unittest.TestCase):
    def test_the_waterfall_adds_up_and_factors_multiply_on_random_rows(self):
        for seed in range(200):
            rng = random.Random(seed)
            events, ais = [], []
            for _ in range(rng.randint(0, 4)):
                start = SUN + timedelta(days=rng.randint(-8, 8))
                after = rng.choice((0, 3))
                events.append({**D.clean_event({"kind": "Promotion", "name": "x", "channels": ["Phone"], "start": start.isoformat(),
                                                "end": (start + timedelta(days=rng.randint(0, 6))).isoformat(), "change": rng.choice((-50, -10, 5, 30, 120)),
                                                "after_days": after, "after_change": rng.choice((-30, 20)) if after else 0}), "id": str(len(events))})
            for k in range(rng.randint(0, 3)):
                start = SUN + timedelta(days=rng.randint(-8, 8))
                ais.append({**D.clean_ai({"channel": "Phone", "start": start.isoformat(), "end": (start + timedelta(days=rng.randint(0, 6))).isoformat(),
                                          "change": rng.choice((-40, -5, 15))}), "id": str(k)})
            shares = [rng.random() for _ in range(7)]
            shares = [x / sum(shares) for x in shares]
            base = rng.randint(0, 50000)
            w = D.waterfall(base, shares, WEEK, "Phone", events, ais)
            self.assertEqual(base + sum(s["delta"] for s in w["steps"]), w["total"], seed)
            expected = D.day_factors(events, ais, "Phone", WEEK)
            for a, b in zip(w["factors"], expected):
                self.assertAlmostEqual(a, b, places=9, msg=seed)
            self.assertAlmostEqual(w["total"], base * sum(s * f for s, f in zip(shares, expected)), delta=0.5 + 1e-9, msg=seed)

    def test_moves_conserve_contacts(self):
        for seed in range(100):
            rng = random.Random(300 + seed)
            change = -rng.randint(1, 99)
            share = rng.randint(1, 100)
            start = SUN + timedelta(days=rng.randint(-3, 3))
            row = D.clean_ai({"channel": "Phone", "start": start.isoformat(), "end": (start + timedelta(days=rng.randint(0, 6))).isoformat(), "change": change,
                              "move_to": "Chat", "move_share": share})
            before = [rng.randint(0, 5000) for _ in range(7)]
            moved = D.ai_moves([row], "Phone", WEEK, before).get("Chat", [0.0] * 7)
            removed = [b * (-change) / 100.0 if _in(start, row, d) else 0.0 for b, d in zip(before, WEEK)]
            for r, m in zip(removed, moved):
                self.assertAlmostEqual(m, r * share / 100.0, places=6, msg=seed)
            self.assertLessEqual(sum(moved), sum(removed) + 1e-6, seed)

    def test_hostile_values_are_refused_or_clean_and_never_crash(self):
        rng = random.Random(77)
        junk = [None, True, False, 0, -1, 10 ** 30, float("nan"), float("inf"), -float("inf"), "", " ", "abc", "1e999", "١٢٣", "25%", "2026-02-30", "x" * 5000,
                "<script>", "=1+1", [], {}, [1], {"a": 1}, b"bytes", (1, 2), object()]
        for _ in range(3000):
            raw_event = {k: rng.choice(junk) for k in ("kind", "name", "channels", "start", "end", "change", "after_days", "after_change")}
            raw_ai = {k: rng.choice(junk) for k in ("channel", "start", "end", "change", "move_to", "move_share")}
            for fn, raw in ((D.clean_event, raw_event), (D.clean_ai, raw_ai)):
                try:
                    out = fn(raw)
                except ValueError:
                    continue
                self.assertTrue(D.CHANGE_LOW < out["change"] <= D.CHANGE_HIGH, out)
                self.assertTrue(date.fromisoformat(out["start"]) <= date.fromisoformat(out["end"]), out)
                self.assertTrue(set(out.get("channels", [out.get("channel")])) <= set(CHANNELS), out)
            for fn, args in ((D.clean_growth, (rng.choice(junk), rng.choice(junk))), (D.clean_document, (rng.choice(junk),)),
                             (D.with_last_year, ({}, rng.choice(junk), rng.choice(junk))), (D.with_skip_weeks, ({}, rng.choice(junk)))):
                try:
                    fn(*args)
                except ValueError:
                    pass

    def test_a_stored_document_that_was_tampered_with_never_crashes_the_page(self):
        store, vb = book()
        rng = random.Random(5)
        for _ in range(200):
            store.set_volume_drivers(KEY, {k: rng.choice([None, 1, "x", [], {}, [{"kind": "Promotion"}], {"yoy": 5}]) for k in ("events", "ai", "growth", "last_year", "skip_weeks", "seq")}, 1)
            store_f = vb.forecast(KEY, "Phone", SUN, total=100)
            self.assertIn("error", store_f)
        with store._db() as db:
            db.execute("update volume_drivers set drivers = 'not json'")
        self.assertIn("error", vb.forecast(KEY, "Phone", SUN, total=100))


class TheZonesNeverLoseOrInventContacts(unittest.TestCase):
    def test_converted_rows_keep_their_total_and_land_on_real_intervals(self):
        from webapp import volumes_zone as Z
        from webapp.clock import ZONES
        keys = [k for k, _ in ZONES]
        for seed in range(150):
            rng = random.Random(seed)
            a, b = rng.sample(keys, 2)
            step = rng.choice((10, 15, 30, 60))
            start = date(2026, 1, 1) + timedelta(days=rng.randint(0, 330))
            rows = [((start + timedelta(days=k)).isoformat(), m, float(rng.randint(0, 40)), rng.choice((None, 120.0, 300.0)))
                    for k in range(rng.randint(1, 9)) for m in range(0, 1440, step)]
            out, problems = Z.convert_rows(rows, a, b, step)
            if problems:
                self.assertEqual(out, [], seed)                                           # a refusal keeps nothing
                continue
            self.assertAlmostEqual(sum(r[2] for r in out), sum(r[2] for r in rows), places=6, msg=seed)
            self.assertTrue(all(m % step == 0 and 0 <= m < 1440 for _d, m, _o, _a in out), seed)
            self.assertEqual(len({(d, m) for d, m, _o, _a in out}), len(out), seed)       # one row per interval
            weighted_in = sum(r[2] * r[3] for r in rows if r[3] is not None)
            weighted_out = sum(r[2] * r[3] for r in out if r[3] is not None)
            self.assertAlmostEqual(weighted_in, weighted_out, places=4, msg=seed)         # handle time stays weighted by volume

    def test_a_grid_in_another_zone_keeps_its_total_and_goes_there_and_back(self):
        from webapp import volumes_zone as Z
        from webapp.clock import ZONES
        keys = [k for k, _ in ZONES]
        for seed in range(150):
            rng = random.Random(900 + seed)
            a, b = rng.sample(keys, 2)
            step = rng.choice((15, 30, 60))
            week = date(2026, 1, 4) + timedelta(weeks=rng.randint(0, 50))
            g = [[rng.randint(0, 50) for _ in range(1440 // step)] for _ in range(7)]
            there = Z.rotate_grid(g, week, a, b, step)
            self.assertEqual(sum(map(sum, there)), sum(map(sum, g)), (seed, a, b, week))
            back = Z.rotate_grid(there, week, b, a, step)
            self.assertEqual(sum(map(sum, back)), sum(map(sum, g)), seed)

    def test_there_and_back_is_exact_in_a_week_with_no_clock_change_in_either_zone(self):
        from webapp import volumes_zone as Z
        for seed in range(40):
            rng = random.Random(3000 + seed)
            g = [[rng.randint(0, 50) for _ in range(24)] for _ in range(7)]
            for a, b in (("Africa/Cairo", "America/New_York"), ("America/New_York", "Africa/Cairo"), ("Europe/London", "Asia/Dubai")):
                self.assertEqual(Z.rotate_grid(Z.rotate_grid(g, date(2026, 1, 11), a, b, 60), date(2026, 1, 11), b, a, 60), g, (seed, a, b))


def _in(start, row, day):
    return date.fromisoformat(row["start"]) <= day <= date.fromisoformat(row["end"])


class TheUploadsKeepEverythingOrNothing(unittest.TestCase):
    def test_random_garbage_in_a_grid_never_partly_saves(self):
        rng = random.Random(11)
        junk = [None, "", "0", "5", 12, 7.5, -3, "abc", "1,200", " 4 ", 10 ** 9, "=1+1", float("nan"), "٣", True]
        for n in range(300):
            slots = [f"{h:02d}:00" for h in range(8, 12)]
            table = [["Interval", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]] + [[t] + [rng.choice(junk) for _ in range(7)] for t in slots]
            try:
                got = parse_grid(table, SUN - timedelta(weeks=1), "Phone", None, 60, TODAY)
            except ValueError:
                continue
            if got.problems:
                self.assertEqual((got.rows, got.summary), ({}, {}), n)
            else:
                for _day, _minute, offered, aht in got.rows["Phone"]:
                    self.assertTrue(offered >= 0 and offered == int(offered), n)
                    self.assertIsNone(aht, n)

    def test_random_drafts_round_trip_or_are_refused_whole(self):
        rng = random.Random(13)
        for n in range(40):
            wb = load_workbook(io.BytesIO(V.draft_workbook(SUN - timedelta(weeks=2), 60)))
            put = {}
            for ch in CHANNELS:
                if rng.random() < 0.6:
                    ws = wb[ch]
                    head = next(r for r in range(1, 15) if ws.cell(r, 1).value == "Interval")
                    for _ in range(rng.randint(1, 30)):
                        slot, day, v = rng.randint(0, 23), rng.randint(0, 6), rng.randint(0, 500)
                        ws.cell(head + 1 + slot, 2 + day).value = v
                        put[(ch, day, slot)] = v
            out = io.BytesIO()
            wb.save(out)
            got = V.parse_draft(out.getvalue(), "d.xlsx", 60, TODAY)
            self.assertEqual(got.problems, [], n) if put else self.assertTrue(got.problems, n)
            for ch in CHANNELS:
                want = sum(v for (c, _d, _s), v in put.items() if c == ch)
                have = sum(r[2] for r in got.rows.get(ch, []))
                self.assertEqual(have, want, (n, ch))


@unittest.skipUnless(shutil.which("soffice"), "LibreOffice is not installed here")
class TheFormulaWorkbookOnRandomInputs(unittest.TestCase):
    def test_random_settings_recalculated_equal_the_sites_erlang(self):
        from webapp.tests.test_bj_volumes_formulas import FIRST, recalc, forecasts
        vb, f = forecasts()
        base_settings = vb.settings(KEY)
        rng = random.Random(2026)
        for n in range(6):
            data = VF.formulas_workbook(SUN, STEP, f, base_settings)
            wb = load_workbook(io.BytesIO(data))
            aht, sl, secs, occ = rng.choice((150, 300, 420, 600)), rng.choice((60, 80, 90, 95)), rng.choice((10, 20, 30, 60)), rng.choice((60, 75, 88, 100))
            for ch in ("Phone", "Chat"):
                ws = wb[ch]
                ws["B4"], ws["B6"], ws["B7"], ws["B8"] = aht, sl, secs, occ
            ws = wb["Chat"]
            ws["B9"] = conc = rng.choice((1, 2, 3, 4))
            out = io.BytesIO()
            wb.save(out)
            got = recalc(out.getvalue())
            for ch in ("Phone", "Chat"):
                for d in range(7):
                    for i, c in enumerate(f[ch]["calls"][d]):
                        want = 0 if not c else (erlang.agents_needed(c, aht, STEP * 60, sl / 100.0, secs, occ / 100.0) if ch == "Phone" else
                                                erlang.chat_agents_needed(c, aht, STEP * 60, sl / 100.0, secs, conc, occ / 100.0))
                        self.assertEqual(got[ch].cell(FIRST + i, 10 + d).value, want, (n, ch, d, i, aht, sl, secs, occ, conc))


if __name__ == "__main__":
    unittest.main()
