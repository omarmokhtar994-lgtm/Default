"""Parse every input workbook in the repo; record contract outcome + fingerprint of parsed facts."""
import sys, json, glob, hashlib, os
sys.path.insert(0, 'engine/_tools')
import l632_universal_scheduler as E
from pathlib import Path
out = {}
paths = sorted(p for p in glob.glob('**/*.xlsx', recursive=True)
               if not p.startswith(('dist/', '.git/')) and 'SCHEDULE' not in p and 'CANDIDATE' not in p and '/production/' not in p)
for p in paths:
    try:
        parsed = E.parse_input(Path(p))
    except Exception as exc:
        out[p] = {"error": f"{type(exc).__name__}: {exc}"[:300]}; continue
    try:
        cap = E.capacity_diagnostics(parsed)
        c = E.validate_input_contract(parsed, cap)
        codes = sorted({f.get("code") for f in c["failures"]})
    except Exception as exc:
        codes = [f"CONTRACT_ERROR {type(exc).__name__}: {exc}"[:200]]
    facts = {
        "assoc": [(a.name, a.language, a.preferences, a.fixed_schedule, a.previous_saturday, a.nesting_group, str(a.emp_id)) for a in parsed.associates],
        "req": parsed.requirements, "shr": parsed.shrinkage, "shifts": [s.label for s in parsed.shifts],
        "rules": sorted((r.group, r.start_min, r.end_min, r.minimum, sorted(r.active_days), sorted(r.eligible_languages)) for r in parsed.language_rules),
        "windows": {k: str(v) for k, v in parsed.language_windows.items()},
        "split": [(r.group, r.start_min, r.end_min, r.coverage_ratio) for r in parsed.coverage_split_rules],
        "maxnb": parsed.max_no_break_exceptions,
    }
    out[p] = {"codes": codes, "hard_warnings": sorted({w.split(':')[0] for w in parsed.parser_warnings if w.startswith('HARD_')}),
              "facts_sha": hashlib.sha256(json.dumps(facts, default=str, sort_keys=True).encode()).hexdigest()[:16],
              "leave_heavy": [a.name for a in parsed.associates if sum(E.preference_kind(x) == "leave" for x in a.preferences) >= 5]}
json.dump(out, open(sys.argv[1], "w"), indent=1)
print(len(out), "workbooks;", sum(1 for v in out.values() if "error" in v), "parse errors;", sum(1 for v in out.values() if v.get("codes")), "with contract failures")
