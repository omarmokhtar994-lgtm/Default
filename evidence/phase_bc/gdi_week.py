# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BC: re-plans the owner's GDI week (the uploaded input workbook of 2026-10-18, with its own channel tabs) through the website's own Plan
channels page, with Suggest every day, in three settings, and reports the Chat and Email people. argv: workbook, week start, names (comma separated
Chat-and-Email-only associates), then optional --set NAME=VALUE overrides of channel_plan constants. The three names are from the owner's message;
the other associates' skills are the channels the owner's plan file shows them working (a lower bound)."""
import io, json, re, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from unittest import mock
from webapp import channel_plan
from webapp.channel_people import ChannelPeople
from webapp.programs import ProgramBook
from webapp.tests.test_runs import REPO, make_app, sign_in, token, wait

def stats(draft, names):
    out = {}
    for who in names:
        hours = {"P": 0.0, "C": 0.0, "E": 0.0}; longest = []; runs_per_day = []
        for day, plan in sorted(draft.items()):
            blocks = sorted((a, b, c) for a, b, c in plan["blocks"].get(who, []) if c in "PCE")
            runs, last = [], None
            for a, b, c in blocks:
                hours[c] += (b - a) / 60
                if last == c:
                    runs[-1] += b - a
                else:
                    runs.append(b - a)
                last = c
            if runs:
                longest.append(max(runs) / 60); runs_per_day.append(len(runs))
        out[who] = {"chat_h": round(hours["C"], 1), "email_h": round(hours["E"], 1), "days": len(longest),
                    "longest_h": round(sum(longest) / max(1, len(longest)), 2), "stretches_a_day": round(sum(runs_per_day) / max(1, len(runs_per_day)), 2)}
    return out

def main():
    book, week, names = Path(sys.argv[1]), sys.argv[2], sys.argv[3].split(",")
    plan_file = sys.argv[4]
    for item in sys.argv[5:]:
        key, value = item.split("=")
        setattr(channel_plan, key, int(value))
    from openpyxl import load_workbook
    wb = load_workbook(plan_file, data_only=True)
    skills = {}
    for who, p, c, e, a in list(wb["Week"].iter_rows(min_row=2, values_only=True)):
        skills[who] = "".join(l for l, h in (("P", p), ("C", c), ("E", e)) if h) or "PCE"
    for who in names:
        skills[who] = "CE"
    d = Path(tempfile.mkdtemp())
    app, store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
    store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
    programs = ProgramBook(store); program = programs.add_program("GDI"); key = programs.add_lob(program, "UK")
    admin = sign_in(app, "omar", "Owner-pass-123")
    admin.post("/runs", data={"csrf_token": token(admin), "kind": "ready", "mode": "QUICK", "program": key, "week_start": week,
                              "workbook": (io.BytesIO(book.read_bytes()), "week.xlsx")}, content_type="multipart/form-data")
    run_id = store.list_runs()[0]["id"]
    wait(store, run_id, statuses=("DONE", "REJECTED", "FAILED"), seconds=900)
    run = store.get_run(run_id)
    print("run:", run["status"], str(run.get("message") or run.get("error") or "")[:300], flush=True)
    version = app.extensions["schedules"].versions(run_id)[0]
    on_schedule = {a["name"] for a in json.loads(version["week"])["associates"]}
    missing = [n for n in names if n not in on_schedule]
    print("on the schedule:", len(on_schedule), "people; the named ones missing:", missing, flush=True)
    ChannelPeople(store).save(program, {n: s for n, s in skills.items() if n in on_schedule}, 1)
    url = f"/schedules/{version['id']}/channels"
    import os
    arms = (("balanced", {"balanced": "1"}), ("fixed", {"consistent": "1"}), ("no tick", {}))
    arms = [a for a in arms if a[0] in os.environ.get("ARMS", "balanced,fixed,no tick").split(",")]
    for label, form in arms:
        store.clear_channel_draft(version["id"])
        got = admin.post(url, data={"csrf_token": token(admin), "day": "Wed", "action": "suggest_week", "move": "1", **form})
        draft = store.get_channel_draft(version["id"])
        print(label, "days planned", len(draft), json.dumps(stats(draft, names)), flush=True)
        if os.environ.get("DUMP"):
            for who in names:
                for day, plan in sorted(draft.items()):
                    blocks = sorted((a, b, c) for a, b, c in plan["blocks"].get(who, []))
                    if blocks:
                        print("  ", who, day, " | ".join(f"{a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d} {c}" for a, b, c in blocks), flush=True)
    shutil.rmtree(d, True)

if __name__ == "__main__":
    main()
