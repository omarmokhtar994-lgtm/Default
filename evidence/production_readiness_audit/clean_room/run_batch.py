import glob, json, subprocess, sys, os
from pathlib import Path
SP=sys.argv[1]; OUT=Path(sys.argv[2])
roots=set()
for p in glob.glob(SP+'/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True):
    root=Path(p).parent.parent
    if '/pkg/' in str(root) or '/chk/' in str(root) or '/colab/' in str(root) or '/iso/' in str(root) or '/final/RC9_2_2' in str(root) or '/advA/' in str(root) or '/phaseA/' in str(root): continue
    roots.add(root)
for p in glob.glob('/home/user/Default/fixtures/real_runs/**/production/*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', recursive=True):
    roots.add(Path(p).parent.parent)
rows=[]
for root in sorted(roots):
    inp=sorted((root/'input_snapshot').glob('*.xlsx'))
    out=sorted((root/'production').glob('*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx'))
    aud=sorted(root.glob('*solver_audit.json'))
    val=root/'INDEPENDENT_VALIDATION.json'
    if not inp or not out:
        rows.append({"case":str(root),"status":"SKIPPED_NO_INPUT_OR_OUTPUT"}); continue
    cmd=[sys.executable,'tools/clean_room_check.py','--input',str(inp[0]),'--output',str(out[0]),'--json-out',str(OUT/(root.name+'.json'))]
    if aud: cmd+=['--audit',str(aud[0])]
    if val.exists(): cmd+=['--validation',str(val)]
    r=subprocess.run(cmd,capture_output=True,text=True)
    try:
        res=json.loads((OUT/(root.name+'.json')).read_text())
        rows.append({"case":root.name,"path":str(root),"rc":r.returncode,"violations":res["violations_by_rule"],
                     "engine_mismatches":res.get("engine_mismatches"),"validator_mismatches":res.get("validator_mismatches"),
                     "validator_status":res.get("validator_status"),"window_mode":res["language_window_mode"],
                     "after_target":res["metrics"].get("after_target"),"active":res["metrics"].get("active_intervals")})
    except Exception as e:
        rows.append({"case":root.name,"path":str(root),"status":"ERROR","stderr":r.stderr[-800:]})
(OUT/'SUMMARY.json').write_text(json.dumps(rows,indent=1))
for row in rows: print(json.dumps(row))
