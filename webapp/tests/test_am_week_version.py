# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AM item 3 (owner, 2026-10-16: "In weeks tab for As planned i dont have the option to choose after break or
before break or a different version"). The Weeks page has a Version pick: the week's versions, the one in use first.
It sets the grid and Hours needed "As planned"; "As recorded" and the RTA keep the version in use."""
import html
import re
import unittest

from webapp.tests.test_runs import REPO, client_for, make_app, versioned_run


def short_count(body):
    return int(re.search(r"All short intervals \((\d+)\)", html.unescape(body)).group(1))


class TheVersionPick(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.store, *_ = make_app(VALIDATOR_ROOT=str(REPO))
        cls.client = client_for(cls.app)
        cls.run_id = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-11")
        book = cls.app.extensions["schedules"]
        cls.tool = book.versions(cls.run_id)[0]
        user = cls.store.list_users()[0]["id"]
        cls.edited = book.change_many(cls.tool["id"], user, [(f"Associate {n:03d}", "Wed", "OFF") for n in range(1, 31)],
                                      "a quiet Wednesday", "a quiet Wednesday")
        other = versioned_run(cls.app, cls.store, cls.client, program="AE/AR B2B", week_start="2026-10-18")
        cls.other = book.versions(other)[0]["id"]

    def week(self, **args):
        args = {"program": "AE/AR B2B", "week": "2026-10-11", **args}
        return self.client.get("/week", query_string=args)

    def test_the_pick_lists_the_weeks_versions(self):
        body = html.unescape(self.week().get_data(as_text=True))
        self.assertIn('<select name="v"', body)
        self.assertIn(f'<option value="{self.tool["id"]}"', body)
        self.assertIn(f'<option value="{self.edited}"', body)
        self.assertNotIn(f'<option value="{self.other}"', body)

    def test_as_planned_follows_the_version_picked(self):
        tool = short_count(self.week(basis="planned", v=self.tool["id"]).get_data(as_text=True))
        edited = self.week(basis="planned", v=self.edited).get_data(as_text=True)
        self.assertGreater(short_count(edited), tool)  # 30 of the week's 39 people off on Wednesday
        self.assertIn(f'name="v" value="{self.edited}"', html.unescape(edited))  # kept by the Hours needed forms

    def test_as_recorded_keeps_the_version_in_use(self):
        default = short_count(self.week(basis="recorded").get_data(as_text=True))
        self.assertEqual(short_count(self.week(basis="recorded", v=self.edited).get_data(as_text=True)), default)

    def test_another_weeks_version_is_refused(self):
        self.assertEqual(self.week(v=self.other).status_code, 404)


if __name__ == "__main__":
    unittest.main()
