"""C1 rule R1 (second bullet): the F-07 metric change leaves every saved final schedule's
week_boundary_hard_failure_count identical, because none of them has a next-Sunday floor gap.

F-07 only removes next-Sunday FLOOR gaps from week_boundary_hard_failure_count and from the
validator's NEXT_SUNDAY_CARRY_OUT failure. So on a schedule with no such gap, both are
unchanged. For every saved run root under argv[1] (the roots golden replay reads) this
records the current validator's next_sunday_floor_gap_count (recomputed from the published
cells) and the floor gap count the producing engine wrote to its audit. Writes argv[2]."""
import glob, importlib.util, json, sys
from pathlib import Path

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod

sys.path.insert(0, 'engine/_tools')
IV = load('engine/tools/independent_validator.py', 'iv_new')
rows = []
roots = sorted({Path(p).parent.parent for p in glob.glob(sys.argv[1] + '/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True)})
for root in roots:
    s = str(root)
    if any(x in s for x in ('/pkg/', '/chk/', '/colab/', '/iso/', '/final/RC9_2_2', '/pkgA/', 'PRODUCTION_PACKAGE', '/advC/')):
        continue
    inp = sorted((root / 'input_snapshot').glob('*.xlsx')); out = sorted((root / 'production').glob('*BEST_FINAL*.xlsx'))
    aud = sorted(root.glob('*solver_audit.json'))
    if not (inp and out and aud):
        continue
    ident = json.loads((root / 'UNIVERSAL_RUN_IDENTITY.json').read_text()) if (root / 'UNIVERSAL_RUN_IDENTITY.json').exists() else {}
    cmd = ident.get('command') or []
    lw = cmd[cmd.index('--language-working-window') + 1] if '--language-working-window' in cmd else None
    audit = json.loads(aud[0].read_text())
    m = (audit.get('stage_metric_surface') or {}).get('metrics') or (audit.get('selected_candidate') or {}).get('metrics') or {}
    row = {"case": s.split('scratchpad/')[-1],
           "engine_audit_week_boundary_floor_gap_count": m.get("week_boundary_floor_gap_count"),
           "engine_audit_week_boundary_hard_failure_count": m.get("week_boundary_hard_failure_count")}
    try:
        v = IV.validate(inp[0], out[0], Path('engine/_tools/l632_universal_scheduler.py'), language_working_window=lw)
        row["validator_next_sunday_floor_gap_count"] = v["metrics"].get("next_sunday_floor_gap_count")
        row["validator_next_sunday_carry_out_failure"] = any(f.get("type") == "NEXT_SUNDAY_CARRY_OUT" for f in v.get("failures", []))
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:300]
    rows.append(row); print(json.dumps(row), flush=True)
json.dump(rows, open(sys.argv[2], 'w'), indent=1)
