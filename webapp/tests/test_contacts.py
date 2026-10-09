# © 2026 Omar Mokhtar. All rights reserved.
"""Phase U: who an aux is with, picked from each program's departments and people (owner, 2026-10-09: "Can the who
be categorized as well by 2 things department and names and those to be added for each program by admin or
supervisor for each program individually and then that will popup as a drop down list while choosing them ? So i
will add list of departments along with list of possible who to ensure consitenty for later on analysis")."""
import shutil
import tempfile
import unittest
from pathlib import Path

from webapp.contacts import ContactBook, pick_contact
from webapp.programs import ProgramBook
from webapp.store import Store


class TheContactBook(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.store = Store(self.dir / "scheduler.db")
        self.programs = ProgramBook(self.store)
        self.saks = self.programs.add_program("SAKS")
        self.tier2 = self.programs.add_lob(self.saks, "NMG Tier 2")
        self.gdi = self.programs.add_program("GDI")
        self.book = ContactBook(self.store)

    def names(self, program_id):
        return [(d["name"], [p["name"] for p in d["people"]]) for d in self.book.lists(program_id)]

    def test_departments_and_people_are_kept_per_program(self):
        self.book.add(self.saks, "Quality", "Lina", 1)
        self.book.add(self.saks, "Quality", "Omar", 1)
        self.book.add(self.saks, "Training", "", 1)  # a department first, its people later
        self.book.add(self.gdi, "IT", "Help desk", 1)
        self.assertEqual(self.names(self.saks), [("Quality", ["Lina", "Omar"]), ("Training", [])])
        self.assertEqual(self.names(self.gdi), [("IT", ["Help desk"])])
        self.assertEqual(self.book.for_unit(self.tier2), self.book.lists(self.saks))  # a LOB uses its program's
        self.assertEqual(self.book.for_unit("No such program"), [])

    def test_the_same_name_twice_is_refused_whatever_the_case(self):
        self.book.add(self.saks, "Quality", "Lina", 1)
        with self.assertRaises(ValueError) as said:
            self.book.add(self.saks, "quality", "LINA", 1)
        self.assertEqual(str(said.exception), "Lina is already on Quality's list.")
        self.book.add(self.saks, " quality ", "Omar", 1)  # an existing department, written another way
        self.assertEqual(self.names(self.saks), [("Quality", ["Lina", "Omar"])])
        with self.assertRaises(ValueError) as said:
            self.book.add(self.saks, "QUALITY", "", 1)
        self.assertEqual(str(said.exception), "Quality is already a department.")

    def test_names_are_checked_not_cut(self):
        for dept, name, said in (("", "Lina", "Give the department."), ("D" * 61, "", "60 characters"),
                                 ("Quality", "N" * 81, "80 characters")):
            with self.assertRaises(ValueError) as refused:
                self.book.add(self.saks, dept, name, 1)
            self.assertIn(said, str(refused.exception))
        self.assertEqual(self.book.lists(self.saks), [])

    def test_a_pasted_list_adds_departments_and_people(self):
        # one per line: "Department, Name", or two columns copied from Excel (a tab between them)
        added = self.book.add_many(self.saks, "Quality, Lina\nQuality\tOmar\n\nTraining\nWorkforce; Sara\n", 1)
        self.assertEqual(added, (3, 3))  # departments, people
        self.assertEqual(self.names(self.saks), [("Quality", ["Lina", "Omar"]), ("Training", []),
                                                 ("Workforce", ["Sara"])])

    def test_a_pasted_list_with_a_bad_line_keeps_nothing(self):
        with self.assertRaises(ValueError) as said:
            self.book.add_many(self.saks, "Quality, Lina\nQuality, Lina\n, Omar\n", 1)
        self.assertEqual(str(said.exception), "Nothing was added. Line 2: Lina is already on Quality's list. "
                                              "Line 3: Give the department.")
        self.assertEqual(self.book.lists(self.saks), [])

    def test_removing(self):
        self.book.add_many(self.saks, "Quality, Lina\nQuality, Omar\nTraining, Sara", 1)
        quality, training = self.book.lists(self.saks)
        self.book.remove_person(self.saks, quality["people"][0]["id"], 1)
        self.book.remove_department(self.saks, training["id"], 1)  # with its people
        self.assertEqual(self.names(self.saks), [("Quality", ["Omar"])])
        with self.assertRaises(ValueError):  # another program's entry is not this program's to remove
            self.book.remove_department(self.gdi, quality["id"], 1)
        self.assertEqual(self.names(self.saks), [("Quality", ["Omar"])])

    def test_deleting_a_program_takes_its_lists(self):
        self.book.add(self.gdi, "IT", "Help desk", 1)
        self.programs.delete_program(self.gdi)
        self.assertEqual(self.book.lists(self.gdi), [])
        self.assertEqual(self.store.list_aux_departments(self.gdi), [])

    def test_a_program_made_a_lob_brings_its_lists(self):
        # GDI becomes a LOB of SAKS: its departments and people join SAKS's; a department both have is merged
        self.book.add_many(self.saks, "IT, Help desk\nQuality, Lina", 1)
        self.book.add_many(self.gdi, "IT, help desk\nIT, Network team\nFinance, Omar", 1)
        self.programs.adopt("GDI", self.saks, "GDI")
        self.assertEqual(self.names(self.saks), [("Finance", ["Omar"]), ("IT", ["Help desk", "Network team"]),
                                                 ("Quality", ["Lina"])])
        self.assertEqual(self.store.list_aux_departments(self.gdi), [])

    def test_pick_contact_takes_only_what_is_listed(self):
        self.book.add_many(self.saks, "Quality, Lina\nTraining", 1)
        lists = self.book.lists(self.saks)
        self.assertEqual(pick_contact(lists, "Coaching", " quality ", "lina"), ("Quality", "Lina"))
        for dept, name, said in (("", "", "Pick the department the coaching is with."),
                                 ("Sales", "Lina", "Sales is not a department on this program's list."),
                                 ("Quality", "", "Pick who in Quality the coaching is with."),
                                 ("Quality", "Sara", "Sara is not on Quality's list for this program."),
                                 ("Training", "Lina", "Lina is not on Training's list for this program.")):
            with self.assertRaises(ValueError) as refused:
                pick_contact(lists, "Coaching", dept, name)
            self.assertEqual(str(refused.exception), said)



class TheContactsPage(unittest.TestCase):
    """Phase U: admins keep every program's lists; a supervisor keeps their own programs'; planners book from them."""

    def setUp(self):
        from webapp.tests.test_runs import make_app, sign_in
        self.app, self.store, *_ = make_app(start_worker=False)
        self.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(self.store)
        self.saks = programs.add_program("SAKS")
        self.tier2 = programs.add_lob(self.saks, "NMG Tier 2")
        self.gdi = programs.add_program("GDI")
        nour = self.store.add_user("nour", "Nour", "Nour-pass-123", must_change=False)
        self.store.update_user(nour, is_supervisor=1)
        self.store.set_user_programs(nour, [self.saks])
        lina = self.store.add_user("lina", "Lina", "Lina-pass-123", must_change=False)
        self.store.set_user_programs(lina, [self.saks])
        self.admin = sign_in(self.app, "omar", "Owner-pass-123")
        self.sup = sign_in(self.app, "nour", "Nour-pass-123")
        self.planner = sign_in(self.app, "lina", "Lina-pass-123")

    def url(self, key):
        return "/setup/with?program=" + key.replace(" ", "+")

    def post(self, client, key, **data):
        from webapp.tests.test_runs import token
        return client.post("/setup/with", data={"csrf_token": token(client), "program": key, **data})

    def page(self, client, key):
        import html
        return html.unescape(client.get(self.url(key)).get_data(as_text=True))

    def test_admins_and_the_programs_supervisors_keep_the_lists(self):
        self.assertEqual(self.admin.get(self.url(self.tier2)).status_code, 200)
        self.assertEqual(self.admin.get(self.url("GDI")).status_code, 200)
        self.assertEqual(self.sup.get(self.url(self.tier2)).status_code, 200)
        self.assertEqual(self.sup.get(self.url("GDI")).status_code, 403)  # not one of his programs
        self.assertEqual(self.planner.get(self.url(self.tier2)).status_code, 403)
        self.assertEqual(self.post(self.planner, self.tier2, action="add", department="Quality").status_code, 403)
        self.assertEqual(self.store.list_aux_departments(self.saks), [])

    def test_add_paste_and_remove_on_the_page(self):
        got = self.post(self.sup, self.tier2, action="add", department="Quality", name="Lina")
        self.assertEqual(got.status_code, 303)
        self.post(self.sup, self.tier2, action="paste", lines="Quality, Omar\nTraining\tSara\nWorkforce")
        page = self.page(self.sup, self.tier2)
        self.assertIn("Added 2 departments and 2 people.", page)
        self.assertIn("<h1>Departments and people: SAKS</h1>", page)
        self.assertIn("every LOB of SAKS", page)
        for words in ("Quality", "Lina", "Omar", "Training", "Sara", "Workforce",
                      "No people yet: it is not offered when booking until someone is added."):
            self.assertIn(words, page)
        quality = ContactBook(self.store).lists(self.saks)[0]
        self.post(self.sup, self.tier2, action="remove_person", id=str(quality["people"][0]["id"]))
        self.post(self.sup, self.tier2, action="remove_department", id=str(quality["id"]))
        self.assertIn("Removed the department Quality and its people.", self.page(self.sup, self.tier2))
        self.assertEqual([d["name"] for d in ContactBook(self.store).lists(self.saks)], ["Training", "Workforce"])
        said = [e["detail"] for e in self.store.list_events(0, 2e9) if e["kind"] == "with_list_changed"]
        self.assertEqual(said, ["Added Lina to Quality.", "Added 2 departments and 2 people.", "Removed Lina from Quality.",
                                "Removed the department Quality and its people."])

    def test_a_bad_paste_says_which_lines(self):
        self.post(self.admin, self.tier2, action="paste", lines="Quality, Lina\nQuality, Lina")
        self.assertIn("Nothing was added. Line 2: Lina is already on Quality's list.", self.page(self.admin, self.tier2))
        self.assertEqual(self.store.list_aux_departments(self.saks), [])

    def test_the_menu_offers_it_to_admins_and_supervisors(self):
        import html
        link = f'href="{self.url(self.tier2)}">Departments and people</a>'
        for client, shown in ((self.admin, True), (self.sup, True), (self.planner, False)):
            body = html.unescape(client.get(f"/day?program={self.tier2.replace(' ', '+')}").get_data(as_text=True))
            self.assertEqual(link in body, shown)


if __name__ == "__main__":
    unittest.main()
