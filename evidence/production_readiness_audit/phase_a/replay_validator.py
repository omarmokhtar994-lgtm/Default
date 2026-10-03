"""Re-validate saved final schedules with the current validator; compare with the engine audit
that produced them (canonical parity), and with the validator result recorded at the time."""
import glob, json, sys, importlib.util
from pathlib import Path
sys.path.insert(0, 'engine/_tools')
import canonical_metrics as C
spec = importlib.util.spec_from_file_location("iv", "engine/tools/independent_validator.py")
iv = importlib.util.module_from_spec(spec); sys.modules["iv"] = iv; spec.loader.exec_module(iv)
NEW = {"max_concurrent_breaks_all_staffed_quarters", "max_concurrent_break_ratio_all_staffed_quarters",
       "break_concurrency_violation_count_all_staffed_quarters"}
rows = []
roots = sorted({Path(p).parent.parent for p in glob.glob(sys.argv[1] + '/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True)})
for root in roots:
    s = str(root)
    if any(x in s for x in ('/pkg/', '/chk/', '/colab/', '/iso/', '/final/RC9_2_2', '/advA/', '/phaseA/')):
        continue
    inp = sorted((root / 'input_snapshot').glob('*.xlsx')); out = sorted((root / 'production').glob('*BEST_FINAL*.xlsx'))
    aud = sorted(root.glob('*solver_audit.json'))
    if not (inp and out and aud):
        continue
    audit = json.loads(aud[0].read_text())
    ident = json.loads((root / 'UNIVERSAL_RUN_IDENTITY.json').read_text()) if (root / 'UNIVERSAL_RUN_IDENTITY.json').exists() else {}
    cmd = ident.get('command') or []
    lw = cmd[cmd.index('--language-working-window') + 1] if '--language-working-window' in cmd else None
    v = iv.validate(inp[0], out[0], Path('engine/_tools/l632_universal_scheduler.py'), language_working_window=lw)
    eng = (audit.get('stage_metric_surface') or {}).get('metrics') or (audit.get('selected_candidate') or {}).get('metrics') or {}
    cmp = C.compare_metric_surfaces(eng, v['metrics'], engine_stage='FULL_SCHEDULE', validator_stage='FULL_SCHEDULE')
    old_fields = [m for m in cmp['mismatches'] if m['field'] not in NEW]
    old_val = root / 'INDEPENDENT_VALIDATION.json'
    old_status = json.loads(old_val.read_text()).get('status') if old_val.exists() else None
    rows.append({"case": root.name, "rule_failures_now": v['hard_fail_count'],
                 "parity_mismatches_on_existing_fields": [(m['field'], m['engine'], m['validator']) for m in old_fields],
                 "all_staffed_ratio": v['metrics']['max_concurrent_break_ratio_all_staffed_quarters'],
                 "active_ratio": v['metrics']['max_concurrent_break_ratio_observed'],
                 "validator_status_at_the_time": old_status})
    print(json.dumps(rows[-1]), flush=True)
json.dump(rows, open(sys.argv[2], 'w'), indent=1)
