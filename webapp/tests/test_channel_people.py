# © 2026 Omar Mokhtar. All rights reserved.
"""Phase V task 3: which channels each associate can work, kept on the website per program (owner, 2026-10-09: "Not
everyone can work all channels so we need somewhere to setup associates working channels", and "2 website").

Someone not listed can work all three. The people come from the program's newest schedule (each LOB's), plus anyone
already listed. A pasted list applies all of it or none of it, naming the lines that are wrong."""
import html
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.channel_people import ChannelPeople, can_work
from webapp.programs import ProgramBook
from webapp.store import Store


def add_version(store, unit, week_start, names, run_id=None, in_use=False):
    """A schedule version for ``unit`` holding these (name, language) people."""
    run_id = run_id or f"r{abs(hash((unit, week_start))) % 10 ** 10:010d}"
    if store.get_run(run_id) is None:
        store.add_run(run_id, 1, "w.xlsx", "READY", "DONE", program=unit, week_start=week_start)
    week = {"associates": [{"name": n, "language": lang, "slot": "", "days": ["OFF"] * 7} for n, lang in names],
            "breaks": [], "shifts": [], "settings": {}}
    sid = store.add_schedule(run_id=run_id, program=unit, week_start=week_start, kind="ready", number=1,
                             label="Ready schedule (uploaded)", file=f"{run_id}/ready.xlsx", week=json.dumps(week),
                             checks="{}")
    if in_use:
        store.update_schedule(sid, in_use=1)
    return sid


class TheChannelPeople(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = Store(self.dir / "scheduler.db")
        self.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(self.store)
        self.saks = programs.add_program("SAKS")
        self.tier2 = programs.add_lob(self.saks, "NMG Tier 2")
        self.tier1 = programs.add_lob(self.saks, "NMG Tier 1")
        self.gdi = programs.add_program("GDI")
        add_version(self.store, self.tier2, "2026-10-04", [("Associate 009", "English")])
        add_version(self.store, self.tier2, "2026-10-11", [("Associate 002", "English"), ("Associate 003", "Arabic")])
        add_version(self.store, self.tier1, "2026-10-11", [("Associate 010", "English")])
        self.people = ChannelPeople(self.store)

    def test_someone_not_listed_can_work_all_three(self):
        self.assertEqual(self.people.skills(self.saks), {})
        self.assertEqual(can_work({}, "Associate 002"), "PCE")
        self.assertEqual(self.people.save(self.saks, {"Associate 002": "PC"}, 1), 1)
        skills = self.people.skills(self.saks)
        self.assertEqual(skills, {"Associate 002": "PC"})
        self.assertEqual(can_work(skills, "associate 002"), "PC")  # names match whatever the case
        self.assertEqual(self.people.skills_for_unit(self.tier1), skills)  # the program's LOBs share the list
        self.assertEqual(self.people.skills(self.gdi), {})

    def test_the_people_come_from_each_lobs_newest_schedule(self):
        self.assertEqual(self.people.roster(self.saks),
                         [("Associate 002", "English"), ("Associate 003", "Arabic"), ("Associate 010", "English")])
        self.people.save(self.saks, {"Associate 003": "C"}, 1)
        add_version(self.store, self.tier2, "2026-10-18", [("Associate 002", "English")], run_id="r-next")
        # Associate 003 left the newest schedule but stays listed: kept, with no language known
        self.assertEqual(self.people.roster(self.saks),
                         [("Associate 002", "English"), ("Associate 003", ""), ("Associate 010", "English")])

    def test_ticking_no_channel_or_an_unknown_name_is_refused(self):
        with self.assertRaises(ValueError) as said:
            self.people.save(self.saks, {"Associate 002": ""}, 1)
        self.assertEqual(str(said.exception), "Tick at least one channel for Associate 002.")
        with self.assertRaises(ValueError) as said:
            self.people.save(self.saks, {"Associate 099": "P"}, 1)
        self.assertEqual(str(said.exception), "Associate 099 is not on SAKS's schedule.")
        self.assertEqual(self.people.skills(self.saks), {})

    def test_back_to_all_three_takes_the_person_off_the_list(self):
        self.people.save(self.saks, {"Associate 002": "PC"}, 1)
        self.assertEqual(self.people.save(self.saks, {"Associate 002": "PCE", "Associate 003": "PCE"}, 1), 1)
        self.assertEqual(self.people.skills(self.saks), {})

    def test_a_paste_applies_all_of_it_or_none_naming_the_lines(self):
        with self.assertRaises(ValueError) as said:
            self.people.paste(self.saks, "Associate 002, Yes, Yes, No\nAssociate 099, Yes, No, No\n"
                                         "Associate 003, Maybe, Yes, Yes\nAssociate 010, No, No, No\nAssociate 002", 1)
        text = str(said.exception)
        self.assertTrue(text.startswith("Nothing was changed."))
        for line in ("Line 2: Associate 099 is not on SAKS's schedule.",
                     "Line 3: Chat must be Yes or No; it reads Maybe.",
                     "Line 4: tick at least one channel for Associate 010.",
                     "Line 5: give the name, then Yes or No for Chat, Phone and Email."):
            self.assertIn(line, text)
        self.assertEqual(self.people.skills(self.saks), {})
        changed = self.people.paste(self.saks, "Name\tChat\tPhone\tEmail\nAssociate 002\tYes\tYes\tNo\n\n"
                                               "associate 010; no; yes; no", 1)
        self.assertEqual(changed, 2)
        self.assertEqual(self.people.skills(self.saks), {"Associate 002": "PC", "Associate 010": "P"})

    def test_deleting_a_program_deletes_its_list(self):
        programs = ProgramBook(self.store)
        nmg = programs.add_program("NMG")
        nmg_key = programs.program(nmg)["key"]
        add_version(self.store, nmg_key, "2026-10-11", [("Associate 020", "English")], run_id="r-nmg")
        self.people.save(nmg, {"Associate 020": "E"}, 1)
        self.store.delete_program_row(nmg)
        self.assertEqual(self.people.skills(nmg), {})


class TheChannelPeoplePage(unittest.TestCase):
    def setUp(self):
        from webapp.tests.test_runs import make_app, sign_in
        self.app, self.store, *_ = make_app(start_worker=False)
        self.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(self.store)
        self.saks = programs.add_program("SAKS")
        self.tier2 = programs.add_lob(self.saks, "NMG Tier 2")
        self.gdi = programs.add_program("GDI")
        add_version(self.store, self.tier2, "2026-10-11", [("Associate 002", "English"), ("Associate 003", "Arabic"),
                                                            ("Associate 010", "English")])
        nour = self.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
        self.store.update_user(nour, is_supervisor=1)
        self.store.set_user_programs(nour, [self.saks])
        lina = self.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)
        self.store.set_user_programs(lina, [self.saks])
        self.admin = sign_in(self.app, "omar", "Owner-pass-123")
        self.sup = sign_in(self.app, "nour", "Nour-pass-123")
        self.planner = sign_in(self.app, "lina", "Lina-pass-123")

    def url(self, key):
        return "/setup/channels?program=" + key.replace(" ", "+")

    def post(self, client, key, **data):
        from webapp.tests.test_runs import token
        return client.post("/setup/channels", data={"csrf_token": token(client), "program": key, **data})

    def page(self, client, key):
        return html.unescape(client.get(self.url(key)).get_data(as_text=True))

    def test_admins_and_the_programs_supervisors_keep_it(self):
        self.assertEqual(self.admin.get(self.url(self.tier2)).status_code, 200)
        self.assertEqual(self.admin.get(self.url("GDI")).status_code, 200)
        self.assertEqual(self.sup.get(self.url(self.tier2)).status_code, 200)
        self.assertEqual(self.sup.get(self.url("GDI")).status_code, 403)
        self.assertEqual(self.planner.get(self.url(self.tier2)).status_code, 403)
        self.assertEqual(self.post(self.planner, self.tier2, action="paste",
                                   lines="Associate 002, Yes, No, No").status_code, 403)
        self.assertEqual(ChannelPeople(self.store).skills(self.saks), {})

    def test_the_page_lists_people_with_their_channels_and_saves_ticks(self):
        page = self.page(self.sup, self.tier2)
        self.assertIn("<h1>Associate channels: SAKS</h1>", page)
        for words in ("Associate 002", "Associate 003", "Arabic", "all three",
                      "people on the schedule who are not listed here can work all three"):
            self.assertIn(words, page)
        rows = {"rows": "3", "who-0": "Associate 002", "C-0": "1", "P-0": "1",
                "who-1": "Associate 003", "C-1": "1", "P-1": "1", "E-1": "1",
                "who-2": "Associate 010", "P-2": "1"}
        self.assertEqual(self.post(self.sup, self.tier2, action="save", **rows).status_code, 303)
        page = self.page(self.sup, self.tier2)
        self.assertIn("Saved 2 changes.", page)
        self.assertIn("Phone, Chat only", page)
        self.assertIn("Phone only", page)
        self.assertEqual(ChannelPeople(self.store).skills(self.saks), {"Associate 002": "PC", "Associate 010": "P"})
        said = [e["detail"] for e in self.store.list_events(0, 2e9) if e["kind"] == "channels_changed"]
        self.assertEqual(said, ["Saved 2 changes: Associate 002 Phone, Chat; Associate 010 Phone."])

    def test_a_paste_with_a_wrong_line_changes_nothing_and_says_so(self):
        self.post(self.admin, self.tier2, action="paste", lines="Associate 002, Yes, No, No\nAssociate 099, Yes, No, No")
        page = self.page(self.admin, self.tier2)
        self.assertIn("Nothing was changed. Line 2: Associate 099 is not on SAKS's schedule.", page)
        self.assertEqual(ChannelPeople(self.store).skills(self.saks), {})

    def test_the_change_is_listed_in_exports_other_actions(self):
        from webapp.exports import OTHER_EVENTS
        self.assertEqual(OTHER_EVENTS["channels_changed"], "Associate channels")
