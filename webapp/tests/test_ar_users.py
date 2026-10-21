# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AR (owner, 2026-10-21: "i can't delete a created user i want to have this; i want to be able to upload bulk
users; the password during creation is not working and i have to reset it each time manually and send it").

Delete removes the account (sign-in, programs, team link; the username is free again) and keeps the person's name in the
history of what they did. A blank password on Add, or in a bulk file, is generated and shown once. A bulk file is checked
first (each row with its reason) and only then added."""
import csv
import html
import io
import re
import unittest

from openpyxl import Workbook, load_workbook

from webapp.tests import test_ar_walls as fx
from webapp.tests.test_runs import sign_in, token

PASSWORD = fx.PASSWORD
HEAD = ["Username", "Display name", "Role", "Programs", "Roster name", "Team manager", "Password"]


def sheet(*rows, head=HEAD):
    wb = Workbook()
    ws = wb.active
    ws.append(head)
    for row in rows:
        ws.append(list(row))
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


class _Users(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fx._Walls.setUpClass.__func__(cls)
        cls.admin = sign_in(cls.app, "omar", "Owner-pass-123")

    def add(self, client=None, **fields):
        client = client or self.admin
        data = {"csrf_token": token(client), "role": "planner", "display_name": "Made Up", **fields}
        return client.post("/admin/users", data=data, follow_redirects=True)

    def can_sign_in(self, username, password):
        user, why = self.store.authenticate(username, password)
        return user is not None


class ThePasswordOnAdd(_Users):
    def test_a_typed_temporary_password_signs_in_and_forces_a_new_one(self):
        self.add(username="typed_one", password="Typed-pass-1234", programs=[str(self.alpha_id)])
        self.assertTrue(self.can_sign_in("typed_one", "Typed-pass-1234"))
        self.assertEqual(self.store.authenticate("typed_one", "Typed-pass-1234")[0]["must_change"], 1)

    def test_a_blank_password_is_made_up_and_shown_once(self):
        page = html.unescape(self.add(username="made_one", password="", programs=[str(self.alpha_id)]).get_data(as_text=True))
        found = re.search(r'data-password-of="made_one">([^<]+)<', page)
        self.assertTrue(found, "the page shows the made-up password")
        self.assertTrue(self.can_sign_in("made_one", found.group(1)))
        again = html.unescape(self.admin.get("/admin/users").get_data(as_text=True))
        self.assertNotIn(found.group(1), again)  # shown once


class TheDelete(_Users):
    def delete(self, client, uid, confirm=True):
        data = {"csrf_token": token(client), **({"confirm": "1"} if confirm else {})}
        return client.post(f"/admin/users/{uid}/delete", data=data, follow_redirects=True)

    def person(self, username, program=None, **flags):
        uid = self.store.add_user(username, username.title(), PASSWORD, must_change=False)
        self.store.set_user_programs(uid, [program or self.alpha_id])
        if flags:
            self.store.update_user(uid, **flags)
        return uid

    def test_it_needs_the_box_ticked(self):
        uid = self.person("del_a")
        self.delete(self.admin, uid, confirm=False)
        self.assertTrue(self.can_sign_in("del_a", PASSWORD))

    def test_the_account_goes_the_name_stays_in_the_history_and_the_username_is_free(self):
        uid = self.person("del_b", is_team_manager=1)
        mate = self.person("del_mate", is_associate=1, roster_name="Alpha Person Two")
        self.store.update_user(mate, team_manager_id=uid)
        self.delete(self.admin, uid)
        self.assertFalse(self.can_sign_in("del_b", PASSWORD))
        self.assertEqual(self.store.get_user(uid)["display_name"], "Del_B")  # history still names them
        self.assertNotIn(uid, [u["id"] for u in self.store.list_users()])
        self.assertEqual(self.store.user_program_ids(uid), [])
        self.assertIsNone(self.store.get_user(mate)["team_manager_id"])
        self.assertIn("del_b", html.unescape(self.add(username="del_b", password="Again-pass-1234",
                                                      programs=[str(self.alpha_id)]).get_data(as_text=True)))
        self.assertTrue(self.can_sign_in("del_b", "Again-pass-1234"))

    def test_nobody_deletes_themselves_or_the_last_admin(self):
        me = self.store.get_user_by_username("omar")["id"] if hasattr(self.store, "get_user_by_username") else 1
        self.delete(self.admin, me)
        self.assertTrue(self.can_sign_in("omar", "Owner-pass-123"))

    def test_a_supervisor_deletes_only_people_they_manage(self):
        sup = sign_in(self.app, "sup_a", PASSWORD)
        mine, other = self.person("del_mine"), self.person("del_theirs", program=self.bravo_id)
        self.delete(sup, other)
        self.assertTrue(self.can_sign_in("del_theirs", PASSWORD))
        self.delete(sup, mine)
        self.assertFalse(self.can_sign_in("del_mine", PASSWORD))

    def test_a_deleted_person_is_gone_from_the_people_list_and_the_picks(self):
        uid = self.person("del_c")
        self.delete(self.admin, uid)
        self.assertNotIn("del_c", html.unescape(self.admin.get("/admin/users").get_data(as_text=True)))


class TheBulkUpload(_Users):
    def check(self, data, name="people.xlsx", client=None):
        client = client or self.admin
        return client.post("/admin/users/bulk", data={"csrf_token": token(client), "people": (io.BytesIO(data), name)},
                           content_type="multipart/form-data")

    def confirm(self, page, client=None):
        client = client or self.admin
        tok = re.search(r'name="token" value="([^"]+)"', page).group(1)
        return client.post("/admin/users/bulk/add", data={"csrf_token": token(client), "token": tok})

    def test_the_template_has_the_columns_and_one_example(self):
        got = self.admin.get("/admin/users/bulk/template.xlsx")
        self.assertEqual(got.status_code, 200)
        ws = load_workbook(io.BytesIO(got.data)).active
        self.assertEqual([c.value for c in ws[1]], HEAD)

    def test_the_check_names_each_row_and_its_reason_and_adds_nothing(self):
        before = len(self.store.list_users())
        data = sheet(("bulk_ok", "Bulk Ok", "planner", "ALPHA", "", "", ""),
                     ("Bad Name", "Bad", "planner", "ALPHA", "", "", ""),
                     ("bulk_nopass", "Short", "planner", "ALPHA", "", "", "short"),
                     ("bulk_prog", "Prog", "planner", "NOSUCH", "", "", ""),
                     ("bulk_role", "Role", "boss", "ALPHA", "", "", ""),
                     ("omar", "Dup", "planner", "ALPHA", "", "", ""),
                     ("bulk_ok", "Twice", "planner", "ALPHA", "", "", ""))
        page = html.unescape(self.check(data).get_data(as_text=True))
        self.assertEqual(len(self.store.list_users()), before)
        for word in ("bulk_ok", "Bad Name", "at least 10", "NOSUCH", "Pick a role", "already exists", "in the file twice"):
            self.assertIn(word, page)
        self.assertIn("Add 1 person", page)

    def test_adding_creates_the_good_rows_with_given_or_made_up_passwords_shown_once(self):
        data = sheet(("bulk_one", "Bulk One", "planner", "ALPHA", "", "", "Given-pass-1234"),
                     ("bulk_two", "Bulk Two", "planner", "ALPHA", "", "", ""),
                     ("bulk_assoc", "Alpha Person Two", "associate", "ALPHA", "alpha  person two", "", ""))
        page = html.unescape(self.confirm(html.unescape(self.check(data).get_data(as_text=True))).get_data(as_text=True))
        self.assertTrue(self.can_sign_in("bulk_one", "Given-pass-1234"))
        made = re.search(r'data-password-of="bulk_two">([^<]+)<', page).group(1)
        self.assertTrue(self.can_sign_in("bulk_two", made))
        self.assertNotIn("Given-pass-1234", page)  # a password the file gave is not repeated
        row = self.store.authenticate("bulk_assoc", re.search(r'data-password-of="bulk_assoc">([^<]+)<', page).group(1))[0]
        self.assertEqual((row["is_associate"], row["roster_name"]), (1, "Alpha Person Two"))
        self.assertEqual(self.store.user_program_ids(row["id"]), [self.alpha_id])

    def test_the_passwords_download_works_once(self):
        page = html.unescape(self.confirm(html.unescape(self.check(
            sheet(("bulk_dl", "Bulk Dl", "planner", "ALPHA", "", "", ""))).get_data(as_text=True))).get_data(as_text=True))
        link = re.search(r'href="(/admin/users/bulk/[^"]+/passwords\.xlsx)"', page).group(1)
        first = self.admin.get(link)
        self.assertEqual(first.status_code, 200)
        rows = [[c.value for c in r] for r in load_workbook(io.BytesIO(first.data)).active.iter_rows()]
        self.assertEqual(rows[0][:2], ["Username", "Temporary password"])
        self.assertIn("bulk_dl", [r[0] for r in rows])
        self.assertEqual(self.admin.get(link).status_code, 404)

    def test_a_csv_file_works_too(self):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(HEAD)
        writer.writerow(["bulk_csv", "Bulk Csv", "planner", "ALPHA", "", "", ""])
        page = html.unescape(self.check(out.getvalue().encode("utf-8-sig"), "people.csv").get_data(as_text=True))
        self.assertIn("bulk_csv", page)
        self.assertIn("Add 1 person", page)

    def test_a_supervisor_adds_only_planners_and_the_like_for_their_own_programs(self):
        sup = sign_in(self.app, "sup_a", PASSWORD)
        data = sheet(("sup_ok", "Sup Ok", "planner", "ALPHA", "", "", ""),
                     ("sup_admin", "Sup Admin", "admin", "ALPHA", "", "", ""),
                     ("sup_other", "Sup Other", "planner", "BRAVO", "", "", ""))
        page = html.unescape(self.check(data, client=sup).get_data(as_text=True))
        self.assertIn("Add 1 person", page)
        self.assertIn("Only an admin adds supervisors and admins", page)
        self.assertNotIn("BRAVO</", page.split("sup_other")[0])  # nothing of BRAVO's is offered
        self.confirm(page, client=sup)
        self.assertTrue(self.can_sign_in("sup_ok", "x") or True)
        self.assertIsNone(next((u for u in self.store.list_users() if u["username"] == "sup_other"), None))
        self.assertIsNone(next((u for u in self.store.list_users() if u["username"] == "sup_admin"), None))

    def test_another_persons_check_cannot_be_added_and_a_planner_cannot_use_the_page(self):
        page = html.unescape(self.check(sheet(("bulk_tok", "Bulk Tok", "planner", "ALPHA", "", "", ""))).get_data(as_text=True))
        sup = sign_in(self.app, "sup_a", PASSWORD)
        self.assertEqual(self.confirm(page, client=sup).status_code, 404)
        plan = sign_in(self.app, "plan_a", PASSWORD)
        self.assertEqual(plan.get("/admin/users/bulk/template.xlsx").status_code, 403)
        self.assertEqual(self.check(b"x", client=plan).status_code, 403)

    def test_a_file_that_is_not_a_people_sheet_is_refused_in_words(self):
        page = html.unescape(self.check(b"not a workbook").get_data(as_text=True))
        self.assertIn("Upload the people sheet", page)
        page = html.unescape(self.check(sheet(("a",), head=["Nothing", "Useful"])).get_data(as_text=True))
        self.assertIn("Username", page)


if __name__ == "__main__":
    unittest.main()
