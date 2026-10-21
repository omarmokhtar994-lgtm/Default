# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AU: shape fit and interval cost of Suggest, over every day of the website's ready test week.
Run from the repository root: PYTHONPATH=. python evidence/phase_au/tools/break_shape_ab.py"""
import json
import shutil
import tempfile
from pathlib import Path

from webapp.break_plan import edge_margin, floor, slots_for, suggest
from webapp.day import read_inputs
from webapp.schedules import ScheduleBook
from webapp.store import Store
from webapp.tests.test_ready import make_ready
from webapp.tests.test_schedules import REPO
from webapp.versions import shift_span


def fits(rules, lo, hi, starts, slots):
    """(first ok, lunch ok, last ok) for one person; None where the part does not apply."""
    first = lunch = last = None
    kinds = [k.casefold() for k, _ in slots]
    if starts and starts[0] is not None:
        first = 120 <= starts[0] - lo <= 210
    if "lunch" in kinds:
        i = kinds.index("lunch")
        if i >= 1 and starts[i] is not None and starts[i - 1] is not None:
            lunch = 120 <= starts[i] - (starts[i - 1] + slots[i - 1][1]) <= 180
    if len(slots) >= 2 and starts[-1] is not None:
        after = True
        if "lunch" in kinds:
            i = kinds.index("lunch")
            after = i < len(slots) - 1 and starts[-1] >= starts[i] + slots[i][1]
        last = after and starts[-1] + slots[-1][1] <= hi - 60
    return first, lunch, last


def main():
    base = Path(tempfile.mkdtemp())
    store = Store(base / "scheduler.db")
    sara = store.add_user("sara", "Sara", "Sara-pass-1", must_change=False)
    store.add_run("rrrrrrrrrrrr", sara, "ready.xlsx", "READY", "DONE", program="SAKS NMG Tier 2", week_start="2026-10-11")
    book = ScheduleBook(store, base, REPO)
    book.ensure_ready(store.get_run("rrrrrrrrrrrr"), make_ready(base / "upload.xlsx"))
    version = book.versions("rrrrrrrrrrrr")[0]
    week, rules = json.loads(version["week"]), book.break_rules(version["id"])
    inputs = read_inputs(book.input_path("rrrrrrrrrrrr"))
    people_all = people_fit = 0
    worst = []
    for d in range(7):
        plan = suggest(week, inputs, rules, d, {})
        cells = floor(week, inputs, d, plan, rules)
        worst.append(round(min((c["pm"] for c in cells if c["pm"] is not None), default=0), 2))
        for a in week["associates"]:
            span = shift_span(a["days"][d])
            if not span or a["name"] not in plan:
                continue
            slots = slots_for(rules, span[1] - span[0])
            got = [x for x in fits(rules, span[0], span[1], plan[a["name"]], slots) if x is not None]
            if got:
                people_all += 1
                people_fit += all(got)
    print(json.dumps({"people": people_all, "fully_fit": people_fit, "tightest_buffer_by_day": worst}))
    shutil.rmtree(base, True)


main()
