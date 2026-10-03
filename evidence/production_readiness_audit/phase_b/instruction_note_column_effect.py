"""What the note-column rule in _instruction_pairs changes, workbook by workbook.

Parses every input workbook twice with the Phase B engine, with the rule off
and on, and compares the canonical contract snapshot (every enforced setting)
plus the parser's hard warnings."""
import sys, json, glob
sys.path.insert(0, 'engine/_tools')
import l632_universal_scheduler as E
from pathlib import Path
paths = sorted(p for p in glob.glob('**/*.xlsx', recursive=True)
               if not p.startswith(('dist/', '.git/')) and 'SCHEDULE' not in p and 'CANDIDATE' not in p and '/production/' not in p)
rows = {}
def flat(d, prefix=''):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items(): out.update(flat(v, f'{prefix}{k}.'))
    else:
        out[prefix[:-1]] = json.dumps(d, default=str, sort_keys=True)
    return out
for p in paths:
    res = {}
    for aware in (False, True):
        E.INSTRUCTION_NOTE_COLUMN_AWARE = aware
        try:
            parsed = E.parse_input(Path(p))
        except Exception as exc:
            res[aware] = {"error": str(exc)[:200]}; continue
        res[aware] = {"contract": flat(E.canonical_contract_snapshot(parsed)),
                      "hard": sorted({w.split(':')[0] for w in parsed.parser_warnings if w.startswith('HARD_')})}
    if "error" in res[False] or "error" in res[True]:
        rows[p] = {"error": [res[False].get("error"), res[True].get("error")]}; continue
    changed = {k: [res[False]["contract"].get(k), res[True]["contract"].get(k)]
               for k in set(res[False]["contract"]) | set(res[True]["contract"])
               if res[False]["contract"].get(k) != res[True]["contract"].get(k)}
    if changed or res[False]["hard"] != res[True]["hard"]:
        rows[p] = {"contract_fields_changed": changed, "hard_without_rule": res[False]["hard"], "hard_with_rule": res[True]["hard"]}
json.dump({"workbooks": len(paths), "changed": rows}, open(sys.argv[1], "w"), indent=1)
print(len(paths), "workbooks;", len(rows), "differ")
for p, r in rows.items(): print(p, json.dumps(r)[:600])
