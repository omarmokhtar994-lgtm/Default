# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AO (owner, 2026-10-20: "swap rules are broke because when i choose any day it doesn't show that i can proceed
with any swaps always showing no one available under rules etc, also it should show the option with warning").
Causes: the page listed only colleagues who pass every rule and who have an account, with one message for every
reason. Now every colleague on another shift is listed; one who breaks a rule is offered with the warning, and the
approvers see it."""
import unittest
from datetime import date
from unittest import mock

from webapp.tests.test_ag_swaps import TUE, WED, Swaps as _Fixture
THU = date(2026, 10, 15)
from webapp.tests.test_runs import TOKEN, sign_in


class TheWarnings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _Fixture.setUpClass.__func__(cls)
        cls.taken = set()
        cls.book = cls.app.extensions["swaps"]

    @classmethod
    def tearDownClass(cls):
        _Fixture.tearDownClass.__func__(cls)

    def offer(self, a, b, on=WED, **kw):
        return self.book.offer(self.key, on, f"Associate {a}", self.users[f"a{a}"]["id"], f"Associate {b}", "",
                               today=TUE, **kw)

    def warned(self, on, askers):
        """(asker, other): ``other`` has an account and a swap with ``asker`` breaks a rule (but is a swap)."""
        taken = self.taken  # each test uses people no other test uses
        for asker in askers:
            for c in self.book.candidates(self.key, on, f"Associate {asker}"):
                if (c["has_account"] and c["problems"] and c["name"] not in taken and f"Associate {asker}" not in taken
                        and not self.book.check(self.key, on, f"Associate {asker}", c["name"])["blocked"]):
                    taken.update({c["name"], f"Associate {asker}"})
                    return asker, c["name"]
        self.fail("the fixture has no rule-breaking pair with an account")

    def test_a_candidate_says_whether_it_has_an_account(self):
        found = {c["name"]: c for c in self.book.candidates(self.key, WED, "Associate 012")}
        self.assertTrue(found["Associate 027"]["has_account"])
        self.assertFalse(found["Associate 016"]["has_account"])  # no account in this fixture, so it cannot accept

    def test_a_rule_breaking_offer_is_refused_unless_sent_with_its_warning(self):
        with self.assertRaisesRegex(ValueError, "would rest 7 hours"):
            self.offer("012", "016")  # (016 has no account either: the rule is said first)

    def test_sent_with_its_warning_it_is_kept_and_shown_to_the_approvers(self):
        asker, other = self.warned(THU, ["012"])
        sid = self.book.offer(self.key, THU, f"Associate {asker}", self.users[f"a{asker}"]["id"], other, "",
                              today=TUE, allow_warnings=True)
        self.assertIn("would rest", self.store.get_swap(sid)["warnings"])
        self.assertIn("would rest", self.book.mine(self.key, f"Associate {asker}")[-1]["warning_list"][0])
        self.book.answer(sid, self.users["a" + other.split()[-1]], accept=True)
        said = self.book.decide(sid, self.users["tm1"], approve=True)
        self.assertIn("Approved:", said)
        self.assertIn("Warning kept:", said)

    def test_two_people_who_cannot_swap_at_all_are_never_offered(self):
        with self.assertRaisesRegex(ValueError, "They work the same shift that day."):
            self.offer("012", "028", allow_warnings=True)
        with self.assertRaisesRegex(ValueError, "Associate 009 does not work on Wed 14 Oct."):
            self.offer("012", "009", allow_warnings=True)

    def test_my_week_lists_a_rule_breaking_colleague_with_a_warning_and_one_without_an_account_with_the_reason(self):
        asker, other = self.warned(THU, ["027", "033"])
        me = sign_in(self.app, f"a{asker}", "Associate-pass-1")
        page = me.get("/me?swap=2026-10-15").get_data(as_text=True)
        self.assertIn(f'name="other" value="{other}"', page)
        self.assertIn("Offer with the warning", page)
        self.assertIn("has no account", page)  # a colleague who cannot accept is said, not hidden
        tok = TOKEN.search(page).group(1)
        from webapp.tests.test_ag_leave import _Clock
        with mock.patch("webapp.app.datetime", _Clock):
            got = me.post("/me/swap", data={"csrf_token": tok, "day": "2026-10-15", "other": other, "anyway": "1"})
        self.assertEqual(got.status_code, 302)
        self.assertIn(f"Sent to {other}.", me.get("/me").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
