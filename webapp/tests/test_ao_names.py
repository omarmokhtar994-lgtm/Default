# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: "When I'm selecting GDI and updating associates name should only show names under that
roaster not for saks associates"; "when assigning a team manager should show the ones related to the assigned program
only"; "when i choose a name on the roaster it's not found and telling me not existing"). Each name on People carries
the programs whose schedules hold it, so the form can show only the picked programs' names; a name is matched without
regard to case or extra spaces, and across the program's recent kept weeks, not only its newest."""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.programs import ProgramBook
from webapp.tests.test_channel_people import add_version
from webapp.tests.test_runs import REPO, make_app, sign_in, token


class _People(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.saks_id = programs.add_program("SAKS")
        cls.gdi_id = programs.add_program("GDI")
        cls.saks = programs.add_lob(cls.saks_id, "NMG Tier 2")
        cls.gdi = programs.add_lob(cls.gdi_id, "GDI English")
        add_version(cls.store, cls.saks, "2026-10-11", [("Associate 101", "English"), ("Associate 102", "English")])
        add_version(cls.store, cls.gdi, "2026-10-04", [("Associate 201", "French"), ("Associate 202", "French")])
        add_version(cls.store, cls.gdi, "2026-10-11", [("Associate 201", "French"), ("Associate 203", "English")])
        cls.client = sign_in(cls.app, "omar", "Owner-pass-123")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def add(self, username, roster_name, program_id, role="associate"):
        return self.client.post("/admin/users", data={
            "csrf_token": token(self.client), "username": username, "display_name": username,
            "password": "Temporary-pass-1", "role": role, "roster_name": roster_name,
            "programs": [str(program_id)]}, follow_redirects=True).get_data(as_text=True)

    def user(self, username):
        return next((u for u in self.store.list_users() if u["username"] == username), None)


class TheNameList(_People):
    def options(self):
        page = self.client.get("/admin/users").get_data(as_text=True)
        return {m.group(1): m.group(2).split() for m in re.finditer(
            r'<option value="([^"]+)" data-programs="([^"]*)">', page.split('<datalist id="roster-names"')[1].split("</datalist>")[0])}

    def test_each_name_says_which_programs_hold_it(self):
        found = self.options()
        self.assertEqual(found["Associate 101"], [str(self.saks_id)])
        self.assertEqual(found["Associate 201"], [str(self.gdi_id)])

    def test_a_name_from_an_older_kept_week_is_still_listed(self):
        self.assertEqual(self.options()["Associate 202"], [str(self.gdi_id)])  # only on the week before the newest

    def test_the_bulk_team_manager_choices_say_their_programs(self):
        for n, pid in (("tm_saks", self.saks_id), ("tm_gdi", self.gdi_id)):
            uid = self.store.add_user(n, n, "Manager-pass-1", must_change=False)
            self.store.update_user(uid, is_team_manager=1)
            self.store.set_user_programs(uid, [pid])
        self.add("assoc_for_bulk", "Associate 203", self.gdi_id)
        page = self.client.get("/admin/users").get_data(as_text=True)
        bulk = page.split("Set the team manager of several associates")[1].split("</section>")[0]
        self.assertRegex(bulk, r'<option value="\d+" data-programs="%d">tm_gdi' % self.gdi_id)
        self.assertRegex(bulk, r'<option value="\d+" data-programs="%d">tm_saks' % self.saks_id)
        self.assertRegex(bulk, r'<input type="checkbox" name="who" value="\d+" data-programs="%d">' % self.gdi_id)


class TheNameMatch(_People):
    def test_the_name_of_another_program_is_refused(self):
        page = self.add("wrong", "Associate 101", self.gdi_id)
        self.assertIn("Associate 101 is not on a schedule of GDI.", page)
        self.assertIsNone(self.user("wrong"))

    def test_case_and_spaces_do_not_matter_and_the_schedules_spelling_is_kept(self):
        self.add("typed", "  associate   201 ", self.gdi_id)
        self.assertEqual(self.user("typed")["roster_name"], "Associate 201")

    def test_a_name_only_on_an_older_kept_week_is_found(self):
        self.add("older", "Associate 202", self.gdi_id)
        self.assertEqual(self.user("older")["roster_name"], "Associate 202")


if __name__ == "__main__":
    unittest.main()
