"""Parse every input workbook in the repo; record the contract outcome and a fingerprint of the parsed facts.

    python3 snapshot_workbooks.py ENGINE_TOOLS_DIR OUT.json

Phase A's facts plus the values Phase B touched (max shift variety, durations,
no-break limit, coverage split flags, language rules in force per day/quarter)."""
import sys, json, glob, hashlib
sys.path.insert(0, sys.argv[1])
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
    extra = {
        "max_different_shifts": parsed.max_different_shifts,
        "durations": sorted(parsed.allowed_shift_durations),
        "use_11h": parsed.use_11h_3off,
        "allow_no_break": parsed.allow_no_break_exceptions,
        "split_full": [(r.group, r.start_min, r.end_min, r.coverage_ratio, r.exclusive, sorted(r.eligible_languages)) for r in parsed.coverage_split_rules],
        "split_gate_mode": parsed.coverage_split_gate_mode,
        # Where every language rule is in force, quarter by quarter: the B1 change.
        "rules_in_force_sha": hashlib.sha256(json.dumps(
            [[sorted(r.group for r in E.language_rules_at(parsed, q * 15, 15, day=d)) for q in range(96)] for d in range(7)]
        ).encode()).hexdigest()[:16],
    }
    out[p] = {"codes": codes, "hard_warnings": sorted({w.split(':')[0] for w in parsed.parser_warnings if w.startswith('HARD_')}),
              "facts_sha": hashlib.sha256(json.dumps(facts, default=str, sort_keys=True).encode()).hexdigest()[:16],
              "extra": extra}
json.dump(out, open(sys.argv[2], "w"), indent=1)
print(len(out), "workbooks;", sum(1 for v in out.values() if "error" in v), "parse errors;", sum(1 for v in out.values() if v.get("codes")), "with contract failures")
