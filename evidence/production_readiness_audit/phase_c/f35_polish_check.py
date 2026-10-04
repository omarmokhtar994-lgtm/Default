import sys, json, glob, importlib.util
from pathlib import Path
sys.path.insert(0, 'engine/_tools')
import l632_universal_scheduler as E
spec = importlib.util.spec_from_file_location('iv', 'engine/tools/independent_validator.py'); IV = importlib.util.module_from_spec(spec); spec.loader.exec_module(IV)
for root in sys.argv[1:]:
    root = Path(root)
    inp = sorted((root/'input_snapshot').glob('*.xlsx'))[0]
    out = sorted((root/'production').glob('*BEST_FINAL*.xlsx'))[0]
    a = json.load(open(sorted(root.glob('*solver_audit.json'))[0]))
    pol = a.get('shift_consistency_polish') or {}
    parsed = E.parse_input(inp)
    names = [x.name for x in parsed.associates]
    sched, _ = IV.parse_output_schedule(out, names)
    idx = {E.norm(s.label): s.index for s in parsed.shifts}
    rows = [[idx.get(E.norm(v)) for v in sched[E.norm(x.name)]] for x in parsed.associates]
    sk = E.SkeletonSolution("pub", "FEASIBLE", 0.0, 0.0, [list(sched[E.norm(x.name)]) for x in parsed.associates], rows, {})
    pub = E.shift_consistency_summary(parsed, sk)
    print(root.name, 'polish', pol.get('status'), 'moves', pol.get('moves'), 'cells', pol.get('cells_reassigned'),
          '| record before', (pol.get('before') or {}).get('distinct_start_times'), (pol.get('before') or {}).get('start_movement_hours'),
          '| record after', (pol.get('after') or {}).get('distinct_start_times'), (pol.get('after') or {}).get('start_movement_hours'),
          '| PUBLISHED', pub.get('distinct_start_times'), pub.get('start_movement_hours'))
