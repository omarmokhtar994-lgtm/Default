"""Best compliant candidate of an engine run -> hint JSON for agg_joint.py."""
import sys, json, importlib.util
from pathlib import Path
engine_file, wb, pool, out = sys.argv[1:5]
spec = importlib.util.spec_from_file_location("E", engine_file); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(engine_file).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)
P = E.parse_input(Path(wb))
d = json.load(open(pool))
best = None
for row in d["compliant"]:
    sk, br = E.deserialize_break_candidate(P, row)
    mm = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
    key = (mm["break_concurrency_violation_count"] == 0 and mm["zero_staffed_active_quarters"] == 0, mm["after_target"], mm["after_floor"])
    if best is None or key > best[0]: best = (key, sk, br, mm)
key, sk, br, mm = best
print(f"{len(d['compliant'])} compliant candidates; best after {mm['after_target']}/{mm['after_floor']} conc_viol={mm['break_concurrency_violation_count']}")
json.dump({"selected_shift_index": sk.selected_shift_index,
           "selected_pattern": [[a, dd, p] for (a, dd), p in br.selected_pattern.items()]}, open(out, "w"))
