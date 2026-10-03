"""Re-run the Phase B release checks on saved final schedules.

For every saved run root under argv[1]: the current independent validator, the
canonical parity comparison with the engine audit that produced the schedule,
and the clean-room gate exactly as the runner now calls it. Reports anything
that would now block, so a new check that falsely blocks real schedules shows
up here before it ships."""
import glob, json, sys, importlib.util, tempfile
from pathlib import Path
sys.path.insert(0, 'engine/_tools')
import canonical_metrics as C
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod
iv = load("engine/tools/independent_validator.py", "iv")
runner = load("engine/RUN_UNIVERSAL_PRODUCTION.py", "runner")
NEW = {"coverage_split_gap_count"}
rows = []
roots = sorted({Path(p).parent.parent for p in glob.glob(sys.argv[1] + '/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True)})
for root in roots:
    s = str(root)
    if any(x in s for x in ('/pkg/', '/chk/', '/colab/', '/iso/', '/final/RC9_2_2', '/pkgA/', 'PRODUCTION_PACKAGE')):
        continue
    inp = sorted((root / 'input_snapshot').glob('*.xlsx')); out = sorted((root / 'production').glob('*BEST_FINAL*.xlsx'))
    aud = sorted(root.glob('*solver_audit.json'))
    if not (inp and out and aud):
        continue
    audit = json.loads(aud[0].read_text())
    ident = json.loads((root / 'UNIVERSAL_RUN_IDENTITY.json').read_text()) if (root / 'UNIVERSAL_RUN_IDENTITY.json').exists() else {}
    cmd = ident.get('command') or []
    lw = cmd[cmd.index('--language-working-window') + 1] if '--language-working-window' in cmd else None
    try:
        v = iv.validate(inp[0], out[0], Path('engine/_tools/l632_universal_scheduler.py'), language_working_window=lw)
    except Exception as exc:  # a workbook the current parser refuses is reported, not hidden
        rows.append({"case": str(root), "validator_error": f"{type(exc).__name__}: {exc}"}); print(json.dumps(rows[-1]), flush=True); continue
    eng = (audit.get('stage_metric_surface') or {}).get('metrics') or (audit.get('selected_candidate') or {}).get('metrics') or {}
    cmp = C.compare_metric_surfaces(eng, v['metrics'], engine_stage='FULL_SCHEDULE', validator_stage='FULL_SCHEDULE')
    tmp = Path(tempfile.mkdtemp())
    cr = runner.run_clean_room_gate(inp[0], out[0], aud[0], tmp / 'CLEAN_ROOM.json')
    rows.append({"case": str(root).split('scratchpad/')[-1], "validator_rule_failures": v['hard_fail_count'],
                 "validator_failure_types": sorted({f.get('type') for f in v.get('failures', [])}),
                 "parity_mismatches_existing_fields": [(m['field'], m['engine'], m['validator']) for m in cmp['mismatches'] if m['field'] not in NEW],
                 "parity_new_fields": [(m['field'], m['engine'], m['validator'], m.get('reason')) for m in cmp['mismatches'] if m['field'] in NEW],
                 "clean_room": {k: cr.get(k) for k in ('status', 'reason', 'violation_count', 'violations_by_rule', 'engine_mismatches')}})
    print(json.dumps(rows[-1]), flush=True)
json.dump(rows, open(sys.argv[2], 'w'), indent=1)
