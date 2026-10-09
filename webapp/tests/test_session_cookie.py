# © 2026 Omar Mokhtar. All rights reserved.
"""Phase XY final review: a save's message ("Added Omar to Quality.") was sometimes missing on the next page. The
Add dialog's preview, started before the save and finished after it, re-sent the session cookie from before the save
(sessions are permanent, so every response re-sent it), and the message went with it. Seen twice in the browser
suite (Phase T and Phase U screens). Background requests from a page no longer re-send the session cookie; page
loads still do, so a signed-in person stays signed in while they use the site."""
import unittest

from webapp.programs import ProgramBook

BACKGROUND = {"Sec-Fetch-Mode": "cors"}  # what a browser sends with fetch(); a page load says "navigate"


class TheSessionCookie(unittest.TestCase):
    def setUp(self):
        from webapp.tests.test_runs import make_app, sign_in
        self.app, self.store, *_ = make_app(start_worker=False)
        self.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(self.store)
        self.key = programs.add_lob(programs.add_program("SAKS"), "NMG Tier 2")
        self.client = sign_in(self.app, "omar", "Owner-pass-123")

    def sets_session(self, response):
        return any(c.startswith("session=") for c in response.headers.getlist("Set-Cookie"))

    def test_a_page_load_keeps_the_session_alive(self):
        self.assertTrue(self.sets_session(self.client.get("/", headers={"Sec-Fetch-Mode": "navigate"})))

    def test_a_background_request_does_not_resend_the_session(self):
        self.assertFalse(self.sets_session(self.client.get("/", headers=BACKGROUND)))

    def test_a_late_background_answer_cannot_erase_a_saved_message(self):
        from webapp.tests.test_runs import token
        before = self.client.get_cookie("session").value
        url = "/setup/with?program=" + self.key.replace(" ", "+")
        self.client.post(url, data={"csrf_token": token(self.client), "program": self.key, "action": "add",
                                    "department": "Quality", "name": "Omar"})
        late = self.app.test_client()  # a preview sent with the cookie from before the save, answered after it
        late.set_cookie("session", before)
        answer = late.get("/", headers=BACKGROUND)
        for header in answer.headers.getlist("Set-Cookie"):  # the browser keeps whatever the late answer sets
            if header.startswith("session="):
                self.client.set_cookie("session", header.split(";", 1)[0].split("=", 1)[1])
        self.assertIn("Added Omar to Quality.", self.client.get(url).get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
