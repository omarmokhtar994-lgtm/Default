# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BY (owner, 2026-11-23: "Yes build the roster name to team manager sheet"): one sheet per LOB with two columns, Roster name and Team manager,
uploaded from the RTA (the setup right) and downloaded back. It gives the Timeline's team manager filter and the small names (Phase BX) without an
account for each associate. A team manager set on an associate's account (People page) wins, as approvals use it; the sheet covers everyone else. A
sheet name that is a team manager's account (display name or username) is grouped with that account. Made-up people."""
import csv
import html
import io
import re
import unittest

from openpyxl import Workbook, load_workbook

from webapp import team_sheet as T
from webapp.permissions import ENDPOINTS
from webapp.programs import ProgramBook
from webapp.tests.test_overtime_side import WED, _Overtime
from webapp.tests.test_runs import token


def xlsx(rows):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def as_csv(rows):
    out = io.StringIO()
    csv.writer(out).writerows(rows)
    return out.getvalue().encode()


class TheSheet(unittest.TestCase):
    def test_it_reads_the_two_columns_from_xlsx_and_csv(self):
        rows = [["Roster name", "Team manager"], ["Associate 01", "Team Manager 01"], ["Associate 02", " Team  Manager 02 "], [None, None]]
        want = {"Associate 01": "Team Manager 01", "Associate 02": "Team Manager 02"}
        self.assertEqual(T.read(xlsx(rows), "teams.xlsx"), want)
        self.assertEqual(T.read(as_csv([[c or "" for c in r] for r in rows]), "teams.csv"), want)

    def test_the_header_may_sit_lower_in_any_case_with_other_columns(self):
        rows = [["Team list"], [], ["Site", "TEAM MANAGER", "roster name"], ["Cairo", "Team Manager 01", "Associate 01"]]
        self.assertEqual(T.read(xlsx(rows), "t.xlsx"), {"Associate 01": "Team Manager 01"})

    def test_a_row_with_no_team_manager_is_left_out(self):
        self.assertEqual(T.read(xlsx([["Roster name", "Team manager"], ["Associate 01", ""], ["Associate 02", "Team Manager 01"]]), "t.xlsx"),
                         {"Associate 02": "Team Manager 01"})

    def test_one_name_with_two_team_managers_is_refused_by_name(self):
        with self.assertRaisesRegex(ValueError, "Associate 01 is on rows 2 and 3 with two team managers"):
            T.read(xlsx([["Roster name", "Team manager"], ["Associate 01", "Team Manager 01"], ["Associate 01", "Team Manager 02"]]), "t.xlsx")

    def test_a_sheet_without_the_two_headings_is_refused(self):
        with self.assertRaisesRegex(ValueError, "Roster name.*Team manager"):
            T.read(xlsx([["Name", "Manager"], ["Associate 01", "Team Manager 01"]]), "t.xlsx")

    def test_an_empty_sheet_and_a_long_name_are_refused(self):
        with self.assertRaisesRegex(ValueError, "no names"):
            T.read(xlsx([["Roster name", "Team manager"]]), "t.xlsx")
        with self.assertRaisesRegex(ValueError, "80 characters"):
            T.read(xlsx([["Roster name", "Team manager"], ["Associate 01", "x" * 81]]), "t.xlsx")

    def test_a_card_number_in_a_cell_is_refused(self):
        with self.assertRaises(ValueError):
            T.read(xlsx([["Roster name", "Team manager"], ["Associate 01", "4111 1111 1111 1111"]]), "t.xlsx")

    def test_the_download_is_the_sheet_back_and_a_formula_stays_text(self):
        ws = load_workbook(io.BytesIO(T.workbook({"Associate 02": "Team Manager 01", "Associate 01": "=cmd"}))).active
        rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
        self.assertEqual(rows[0], ("Roster name", "Team manager"))
        self.assertEqual(rows[1:3], [("Associate 01", "'=cmd"), ("Associate 02", "Team Manager 01")])

    def test_an_empty_download_is_a_template_with_an_example(self):
        ws = load_workbook(io.BytesIO(T.workbook({}))).active
        self.assertEqual([tuple(r) for r in ws.iter_rows(values_only=True)][:2], [("Roster name", "Team manager"), ("Associate 01", "Team Manager 01")])


class OnTheRta(_Overtime):
    def setUp(self):
        self.lanes = [l["name"] for l in self.days.page(self.key, WED)["view"]["lanes"]]
        self.addCleanup(self.days.set_team_sheet, self.key, {})

    def upload(self, rows, name="teams.xlsx", **form):
        data = {"csrf_token": token(self.client), "program": self.key, "date": WED.isoformat(), **form}
        if rows is not None:
            data["sheet"] = (io.BytesIO(xlsx(rows)), name)
        return self.client.post("/day/teams", data=data, content_type="multipart/form-data", follow_redirects=True)

    def timeline(self, **args):
        q = "".join(f"&{k}={v}" for k, v in args.items())
        return html.unescape(self.client.get(f"/day?program={self.key.replace(' ', '+')}&date={WED.isoformat()}{q}").get_data(as_text=True))

    def test_the_rights_are_setup_to_change_and_rta_view_to_download(self):
        self.assertEqual((ENDPOINTS["day_team_sheet"], ENDPOINTS["day_team_sheet_xlsx"]), ("setup", "rta_view"))

    def test_an_uploaded_sheet_gives_the_filter_and_the_names(self):
        rows = [["Roster name", "Team manager"]] + [[n, "Team Lead A"] for n in self.lanes[:3]] + [[n, "Team Lead B"] for n in self.lanes[3:5]]
        page = html.unescape(self.upload(rows).get_data(as_text=True))
        self.assertIn("Team managers sheet kept: 5 people, 2 team managers.", page)
        page = self.timeline()
        bar = re.search(r'(?s)aria-label="Filter by team manager">.*?</div>', page).group(0)
        self.assertRegex(bar, r"<b>Team Lead A</b><small>3 people")
        self.assertRegex(bar, r"<b>Team Lead B</b><small>2 people")
        self.assertRegex(page, rf'<b title="{self.lanes[0]}"><a [^>]*>{self.lanes[0]}</a><small class="tl-tm">Team Lead A</small></b>')
        key = re.search(r'tm=([^"&]+)"[^>]*><b>Team Lead A</b>', bar).group(1)
        shown = re.findall(r'<div class="tl-who"><b title="([^"]+)">', self.timeline(tm=key))
        self.assertEqual(shown, self.lanes[:3])

    def test_a_names_not_on_the_schedule_are_kept_and_said(self):
        page = html.unescape(self.upload([["Roster name", "Team manager"], [self.lanes[0], "Team Lead A"], ["Associate 999", "Team Lead A"]])
                             .get_data(as_text=True))
        self.assertIn("1 name is not on this week's schedule: Associate 999.", page)
        self.assertEqual(self.days.team_sheet(self.key), {self.lanes[0]: "Team Lead A", "Associate 999": "Team Lead A"})

    def test_a_bad_sheet_keeps_the_old_one(self):
        self.upload([["Roster name", "Team manager"], [self.lanes[0], "Team Lead A"]])
        page = html.unescape(self.upload([["Name", "Boss"], ["x", "y"]]).get_data(as_text=True))
        self.assertIn("Roster name", page)
        self.assertEqual(self.days.team_sheet(self.key), {self.lanes[0]: "Team Lead A"})

    def test_clear_removes_it(self):
        self.upload([["Roster name", "Team manager"], [self.lanes[0], "Team Lead A"]])
        page = html.unescape(self.upload(None, clear="1").get_data(as_text=True))
        self.assertIn("Team managers sheet removed.", page)
        self.assertEqual(self.days.team_sheet(self.key), {})

    def test_the_download_is_what_was_uploaded(self):
        self.upload([["Roster name", "Team manager"], [self.lanes[1], "Team Lead B"], [self.lanes[0], "Team Lead A"]])
        reply = self.client.get(f"/day/teams.xlsx?program={self.key.replace(' ', '+')}")
        self.assertEqual(reply.status_code, 200)
        rows = [tuple(r) for r in load_workbook(io.BytesIO(reply.data)).active.iter_rows(values_only=True)]
        self.assertEqual(sorted(rows[1:]), sorted([(self.lanes[1], "Team Lead B"), (self.lanes[0], "Team Lead A")]))

    def test_an_account_team_manager_wins_and_a_matching_name_joins_its_account(self):
        store = self.store
        pid = ProgramBook(store).unit(self.key)["program"]["id"]
        tm = store.add_user("by_tm01", "Team Manager 07", "Made-up-pass-123", must_change=False)
        store.update_user(tm, is_team_manager=1)
        store.set_user_programs(tm, [pid])
        a = store.add_user("by_a0", self.lanes[0], "Made-up-pass-123", must_change=False)
        store.update_user(a, is_associate=1, roster_name=self.lanes[0], team_manager_id=tm)
        store.set_user_programs(a, [pid])
        self.days.set_team_sheet(self.key, {self.lanes[0]: "Team Lead A", self.lanes[1]: "team manager 07", self.lanes[2]: "by_tm01"})
        team = self.days.team_of(self.key)
        self.assertEqual(team[self.lanes[0]], {"id": tm, "name": "Team Manager 07"})       # the account, not the sheet
        self.assertEqual(team[self.lanes[1]], {"id": tm, "name": "Team Manager 07"})       # the sheet's name is that account
        self.assertEqual(team[self.lanes[2]], {"id": tm, "name": "Team Manager 07"})       # so is its username
        store.update_user(a, roster_name="", team_manager_id=None)


if __name__ == "__main__":
    unittest.main()
