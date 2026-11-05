# © 2026 Omar Mokhtar. All rights reserved.
"""Owner D, 16 October 2026: AM's token-free draft contract, with CSRF retained.

These real Flask tests replace the discarded revision-guard tests because the
owner explicitly removed that feature; failures are not hidden or skipped.
"""
import unittest

from webapp.tests.test_channel_page import _Page
from webapp.tests.test_runs import token


class DraftHTTP(_Page):
    @classmethod
    def setUpClass(cls):
        cls.start()

    def test_channel_discard_does_not_require_a_revision(self):
        got = self.admin.post(self.url, data={"csrf_token": token(self.admin), "day": "Wed", "action": "discard"})
        self.assertEqual(got.status_code, 303)

    def test_break_discard_does_not_require_a_revision(self):
        got = self.admin.post(self.url.replace("/channels", "/breaks"),
                              data={"csrf_token": token(self.admin), "day": "Wed", "action": "discard"})
        self.assertEqual(got.status_code, 303)

    def test_old_page_does_not_add_a_draft_conflict(self):
        self.assertEqual(self.admin.get(self.url).status_code, 200)
        self.store.set_channel_draft(self.version["id"], "Wed", {"blocks": {}, "breaks": {}}, 1)
        got = self.admin.post(self.url, data={"csrf_token": token(self.admin), "day": "Wed", "action": "discard"})
        self.assertEqual(got.status_code, 303)
        self.assertEqual(self.store.get_channel_draft(self.version["id"]), {})

    def test_csrf_is_still_required(self):
        got = self.admin.post(self.url, data={"day": "Wed", "action": "discard"})
        self.assertEqual(got.status_code, 400)


if __name__ == "__main__":
    unittest.main()
