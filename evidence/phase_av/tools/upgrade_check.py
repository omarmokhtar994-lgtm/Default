import re, sqlite3, sys
from webapp.app import create_app
from webapp.tests.test_runs import TOKEN
D = "/tmp/upgrade_data"
cfg = {"DATA_DIR": D, "SECRET_KEY": "t", "TESTING": True, "HTTPS": False, "PACKAGE_ROOT": D + "/package", "START_WORKER": False}
app = create_app(cfg)
c = sqlite3.connect(D + "/scheduler.db")
tables = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
for t in ("incidents", "app_settings", "revoked_sessions"):
    print("table", t, t in tables)
cols = {r[1] for r in c.execute("pragma table_info(activities)")}
print("activities.session", "session" in cols)
for t, n in (("attendance", 1), ("actual_breaks", 1), ("users", 17), ("schedules", 1), ("runs", 1), ("day_log", 2)):
    got = c.execute(f"select count(*) from {t}").fetchone()[0]
    print("kept", t, got, "OK" if got == n else "CHANGED")
def login(u, p):
    cl = app.test_client(); t = TOKEN.search(cl.get("/login").get_data(as_text=True)).group(1)
    r = cl.post("/login", data={"username": u, "password": p, "csrf_token": t}); return cl, r.status_code
Q = "SAKS+NMG+Tier+2"
bad = 0
for who, pw in (("rta1", "Staff-pass-123"), ("tm1", "Staff-pass-123"), ("a027", "Associate-pass-1")):
    cl, code = login(who, pw)
    print("sign in", who, code)
    urls = ["/me", "/me/breaks"] if who.startswith("a") else [f"/day?program={Q}&date=2026-10-14", f"/day?program={Q}&date=2026-10-14&view=board", f"/day?program={Q}&date=2026-10-14&view=meeting", f"/day?program={Q}&date=2026-10-14&view=sessions", f"/week?program={Q}", f"/overview?program={Q}", f"/schedules?program={Q}", f"/requests?program={Q}", f"/incidents?program={Q}&from=2026-10-11&to=2026-10-15", f"/shrinkage?program={Q}&from=2026-10-11&to=2026-10-15&by=interval", "/exports", f"/exports/download?program={Q}&from=2026-10-11&to=2026-10-15&kind=attendance&kind=incidents&kind=sessions&kind=absence&kind=incident_summary&format=xlsx"]
    for u in urls:
        r = cl.get(u)
        ok = r.status_code == 200
        bad += not ok
        print("  ", r.status_code, u[:90])
cl, _ = login("rta1", "Staff-pass-123")
page = cl.get(f"/day?program={Q}&date=2026-10-14").get_data(as_text=True)
print("old Sick record shown:", "Sick" in page, "| old break move shown:", "moved" in page or "Break" in page)
print("PROBLEMS", bad)
