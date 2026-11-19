# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BL differential check: what every function the phase touched returns, as hashes, for each workbook given.

    python ab_functions.py ENGINE_TOOLS_DIR WORKBOOK [WORKBOOK ...]

One line per workbook: the workbook and a SHA-256 for each aspect: every parsed field (the new Associate and Shift fields left out), the input contract's
failures and warnings, the capacity, coverage-split and break-resilience diagnostics, each associate's eligible shifts and whether the consistency step
may put each shift on each day, the off days owed, the break set of every shift length, and every break pattern. Run once with the engine from before the
phase and once with the engine after it: the lines must be identical for every workbook that has none of the new columns."""
import dataclasses
import hashlib
import json
import sys
from pathlib import Path

tools, workbooks = Path(sys.argv[1]), sys.argv[2:]
sys.path.insert(0, str(tools))
import l632_universal_scheduler as E  # noqa: E402

NEW = {"shift_minutes", "part_time", "off_days", "breaks_per_day", "part_time_only"}


def h(value) -> str:
    return hashlib.sha256(repr(value).encode()).hexdigest()[:16]


def fields(obj):
    if dataclasses.is_dataclass(obj):
        return {f.name: fields(getattr(obj, f.name)) for f in dataclasses.fields(obj) if f.name not in NEW}
    if isinstance(obj, (list, tuple)):
        return [fields(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): fields(v) for k, v in sorted(obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (set, frozenset)):
        return sorted(repr(x) for x in obj)
    return obj


def guarded(fn):
    try:
        return fn()
    except Exception as exc:                      # an exception is part of the behaviour: it must be the same one
        return f"EXC {type(exc).__name__}: {str(exc)[:120]}"


for path in workbooks:
    out = {"workbook": Path(path).name}
    parsed = guarded(lambda: E.parse_input(path))
    if isinstance(parsed, str):
        out["parse"] = h(parsed)
        print(json.dumps(out, sort_keys=True))
        continue
    skip = {"associates", "shifts"}
    out["fields"] = h({k: fields(v) for k, v in sorted(vars(parsed).items()) if k not in skip})
    out["associates"] = h(fields(parsed.associates))
    out["shifts"] = h(fields(parsed.shifts))
    contract = guarded(lambda: E.validate_input_contract(parsed))
    out["contract"] = h(json.dumps(contract, sort_keys=True, default=str))
    out["capacity"] = h(guarded(lambda: json.dumps(E.capacity_diagnostics(parsed), sort_keys=True, default=str)))
    out["coverage_split"] = h(guarded(lambda: json.dumps(E.coverage_split_capacity_report(parsed), sort_keys=True, default=str)))
    out["break_resilience"] = h(guarded(lambda: json.dumps(E.break_resilience_diagnostics(parsed), sort_keys=True, default=str)))
    out["eligible"] = h(guarded(lambda: [[[s.index for s in E.associate_day_eligible_shifts(parsed, a, d)] for d in range(7)] for a in parsed.associates]))
    out["cells"] = h(guarded(lambda: [[[E._consistency_cell_allowed(parsed, a, d, s) for s in parsed.shifts] for d in range(7)]
                                        for a in range(len(parsed.associates))]))
    out["off_owed"] = h(guarded(lambda: [[E.required_off_days(parsed, a, lm) for lm in (False, True)] for a in parsed.associates]))
    out["break_sets"] = h(guarded(lambda: sorted({(s.duration_min, E.break_segments_for(parsed, s.duration_min)) for s in parsed.shifts})))
    out["patterns"] = h(guarded(lambda: [(p.duration_q, p.breaks, p.score) for p in E.generate_break_patterns(parsed)]))
    print(json.dumps(out, sort_keys=True))
