import shutil, sys
from webapp.tests.test_as_requests import WED, _Fixture
class S(_Fixture):
    def runTest(self): pass
S.setUpClass()
S().clear()
days = S.app.extensions["days"]; store = S.store; key = S.key
# some real day records, as the live site would hold
page = days.page(key, WED)
lane = next(l for l in page["view"]["lanes"] if any(s["offset"] == 0 and s["status"] == "Present" and s["breaks"] for s in l["segments"]))
seg = next(s for s in lane["segments"] if s["offset"] == 0)
b = seg["breaks"][0]
days.move_break(key, WED, lane["name"], b["idx"], f"{(b['start'] + 5) // 60:02d}:{(b['start'] + 5) % 60:02d}", S.users["rta1"]["id"])
days.set_status(key, WED, "Associate 012", "Sick", S.users["rta1"]["id"])
shutil.copytree(store.path.parent, "/tmp/olddata", dirs_exist_ok=True)
print("KEY", key, "DB", store.path)
