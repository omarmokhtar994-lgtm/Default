# © 2026 Omar Mokhtar. All rights reserved.
"""Phase AR (owner, 2026-10-21: "each program has its own everything and no one can view it except if they have
access: TMs, departments, names, associates, schedules, uploads, everything hidden from other programs").

Two made-up programs, ALPHA and BRAVO, each with a LOB, people, a team manager, departments, an upload, a kept
schedule and a group link. People who have only ALPHA open every page the site has, with and without BRAVO's ids and
names in the address, and nothing in any answer may carry a BRAVO word. A person who has BRAVO must see them, so the
test cannot pass by the fixture being empty."""
import json
import re
import unittest
from urllib.parse import unquote

from webapp.contacts import ContactBook
from webapp.programs import ProgramBook
from webapp.tests.test_channel_people import add_version
from webapp.tests.test_runs import make_app, sign_in, token

WEEK = "2026-10-11"
PASSWORD = "Wall-pass-12345"
# Words only BRAVO's data holds. A page may echo what the address said (BRAVO's program name, the word Zor): that is not
# a leak, so the address never carries these. The bare address (no query) is also held to BRAVO's name and first person.
STRICT = re.compile(r"zorro (person two|manager|dept|contact|planner)|zorro_secret|zorrosecret", re.I)
BARE = re.compile(r"bravo|zorro person one", re.I)
BINARY = ("application/vnd.openxmlformats", "application/octet-stream", "application/zip", "image/")


class _Walls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token = staticmethod(token)
        cls.app, cls.store, *_ = make_app(start_worker=False)
        cls.app.config["PROPAGATE_EXCEPTIONS"] = False  # a page that fails is a status, not a stop
        cls.admin_id = cls.store.add_user("omar", "Omar", "Owner-pass-123", is_admin=True, must_change=False)
        programs = ProgramBook(cls.store)
        cls.alpha_id, cls.bravo_id = programs.add_program("ALPHA"), programs.add_program("BRAVO")
        cls.alpha, cls.bravo = programs.add_lob(cls.alpha_id, "Alpha One"), programs.add_lob(cls.bravo_id, "Bravo One")
        cls.sched, cls.runs = {}, {}
        for n, (unit, people) in enumerate(((cls.alpha, ["Alpha Person One", "Alpha Person Two"]),
                                            (cls.bravo, ["Zorro Person One", "Zorro Person Two"]))):
            rid = f"00000000a{n}00"
            sid = add_version(cls.store, unit, WEEK, [(p, "English") for p in people], run_id=rid, in_use=True)
            cls.store.update_run(rid, workbook=("zorro" if unit == cls.bravo else "alpha") + "_secret_week.xlsx")
            cls.sched[unit], cls.runs[unit] = sid, rid
        book = ContactBook(cls.store)
        book.add(cls.alpha_id, "Alpha Dept", "Alpha Contact", cls.admin_id)
        book.add(cls.bravo_id, "Zorro Dept", "Zorro Contact", cls.admin_id)
        for unit, who in ((cls.alpha, "plan_a"), (cls.bravo, "plan_b")):  # who uploaded each (made below with the users)
            cls.uploader = getattr(cls, "uploader", {})
            cls.uploader[unit] = who
        cls.store.set_notify(cls.bravo, service="slack", link="https://hooks.slack.com/services/T0/B0/ZORROSECRET",
                             mode="on")
        cls.users = {}
        for name, shown, program, flags in (
                ("plan_a", "Alpha Planner", cls.alpha_id, {}),
                ("sup_a", "Alpha Supervisor", cls.alpha_id, {"is_supervisor": 1}),
                ("tm_a", "Alpha Manager", cls.alpha_id, {"is_team_manager": 1}),
                ("assoc_a", "Alpha Person One", cls.alpha_id, {"is_associate": 1, "roster_name": "Alpha Person One"}),
                ("plan_b", "Zorro Planner", cls.bravo_id, {}),
                ("tm_b", "Zorro Manager", cls.bravo_id, {"is_team_manager": 1}),
                ("assoc_b", "Zorro Person One", cls.bravo_id, {"is_associate": 1, "roster_name": "Zorro Person One"})):
            uid = cls.store.add_user(name, shown, PASSWORD, must_change=False)
            if flags:
                cls.store.update_user(uid, **flags)
            cls.store.set_user_programs(uid, [program])
            cls.users[name] = uid
        cls.store.update_user(cls.users["assoc_b"], team_manager_id=cls.users["tm_b"])
        for unit, who in cls.uploader.items():
            cls.store.update_run(cls.runs[unit], user_id=cls.users[who])

    def values_for_bravo(self):
        """What an address needs for each id kind, taken from BRAVO."""
        return {"run_id": self.runs[self.bravo], "schedule_id": self.sched[self.bravo], "name": self.bravo,
                "user_id": self.users["tm_b"], "program": self.bravo}

    def rules(self):
        return [r for r in self.app.url_map.iter_rules() if "GET" in r.methods and r.endpoint != "static"]

    def crawl(self, who):
        """(url, status, found) for every GET page, three ways: bare, with BRAVO's program and day, with its words."""
        client = sign_in(self.app, who, PASSWORD)
        seen, skipped = [], []
        values = self.values_for_bravo()
        queries = ({}, {"program": self.bravo, "date": "2026-10-14", "week": WEEK},
                   {"program": self.bravo, "q": "Zor", "who": "Zorro Person One", "from": "2026-10-01",
                    "to": "2026-10-31", "start": WEEK, "pick": f"key:{self.bravo}"})
        for rule in self.rules():
            args = {a: values[a] for a in rule.arguments if a in values}
            if set(rule.arguments) - set(args):
                skipped.append(rule.rule)
                continue
            for query in queries:
                with self.app.test_request_context():
                    from flask import url_for
                    url = url_for(rule.endpoint, **args, **query)
                got = client.get(url)
                kind = got.headers.get("Content-Type", "")
                text = "" if kind.startswith(BINARY) else got.get_data(as_text=True)
                for echoed in (url.split("?")[0], unquote(url.split("?")[0])):
                    text = text.replace(echoed, "")  # the address itself, repeated in a sign-in link, is not a leak
                found = bool(STRICT.search(text)) or bool(STRICT.search(got.headers.get("Location", "")))
                if not query:
                    found = found or bool(BARE.search(text))
                seen.append((url, got.status_code, found))
        return seen, skipped


class TheWalls(_Walls):
    def test_the_fixture_shows_bravo_to_a_bravo_planner(self):
        seen, _ = self.crawl("plan_b")
        self.assertGreater(sum(1 for _u, status, found in seen if found and status == 200), 5)

    def test_nobody_without_bravo_sees_a_bravo_word_on_any_page(self):
        for who in ("plan_a", "sup_a", "tm_a", "assoc_a"):
            with self.subTest(who):
                seen, skipped = self.crawl(who)
                leaks = sorted({url for url, status, found in seen if found})
                self.assertEqual(leaks, [], f"{who} saw BRAVO on: {leaks}")
                self.assertGreater(len(seen), 50)

    def test_the_new_schedule_picker_lists_only_the_programs_a_person_has(self):
        page = sign_in(self.app, "plan_a", PASSWORD).get("/").get_data(as_text=True)
        self.assertIn('optgroup label="ALPHA"', page)
        self.assertNotIn('optgroup label="BRAVO"', page)
        admin = sign_in(self.app, "omar", "Owner-pass-123").get("/").get_data(as_text=True)
        self.assertIn('optgroup label="BRAVO"', admin)

    def test_a_person_cannot_upload_into_a_program_they_do_not_have(self):
        import io
        client = sign_in(self.app, "plan_a", PASSWORD)
        before = len(self.store.list_runs())
        got = client.post("/runs", data={"csrf_token": self.token(client), "kind": "ready", "program": self.bravo,
                                         "week_start": "2026-10-18",
                                         "workbook": (io.BytesIO(b"PK\x03\x04 not a real workbook"), "w.xlsx")},
                          content_type="multipart/form-data")
        self.assertEqual(got.status_code, 403)
        self.assertEqual(len(self.store.list_runs()), before)

    def test_a_person_cannot_move_their_own_run_into_a_program_they_do_not_have(self):
        client = sign_in(self.app, "plan_a", PASSWORD)
        got = client.post(f"/runs/{self.runs[self.alpha]}/tag", data={
            "csrf_token": self.token(client), "program": self.bravo, "week_start": WEEK, "reason": "mistake"})
        self.assertEqual(got.status_code, 403)
        self.assertEqual(self.store.get_run(self.runs[self.alpha])["program"], self.alpha)


if __name__ == "__main__":
    unittest.main()
