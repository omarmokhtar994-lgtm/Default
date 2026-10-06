#!/usr/bin/env python3
"""Phase E, F-E3: does a window-aware break stand-in predict the after-break
metric better than Stage 1's flat one? Report-only; changes no engine file.

Stage 1 counts each head on a shift at (paid - break) / paid presence in every
quarter. Breaks can only fall inside the shift's legal break patterns, so the
window-aware stand-in uses, per offset, 1 - (share of legal patterns of that
shift length that break there). For each saved engine week (final after-breaks
workbook + its input snapshot) both stand-ins predict intervals at target after
breaks; the truth is calculate_metrics with the engine's own breaks.

    python3 tools/break_proxy_diagnostic.py --engine ENGINE --out OUT.json RUN_DIR [...]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_synthetic_suite as S  # noqa: E402
from score_break_plan import engine_break_selection  # noqa: E402


def presence_profile(E, p, shift, mode: str) -> List[float]:
    n = shift.duration_q
    if mode == "flat":
        return [(n - E.break_quarters_for(p, shift.duration_min)) / n] * n
    if mode != "window":
        raise ValueError(f"mode must be flat or window, not {mode!r}")
    pats = [pt for pt in E.generate_break_patterns(p) if pt.duration_q == n]
    if not pats:
        return [1.0] * n
    hits = [0] * n
    for pt in pats:
        for o in pt.broken_offsets:
            if 0 <= o < n:
                hits[o] += 1
    return [1.0 - h / len(pats) for h in hits]


def predicted_after_hits(E, p, skeleton, mode: str) -> int:
    qpi = p.qslots_per_interval
    prof: Dict[int, List[float]] = {}
    pres = [0.0] * (7 * 96)
    for a, d, si in E.scheduled_cells(skeleton):
        sh = p.shifts[si]
        if si not in prof:
            prof[si] = presence_profile(E, p, sh, mode)
        base = d * 96 + sh.start_min // 15
        for o in range(sh.duration_q):
            if base + o < 7 * 96:
                pres[base + o] += prof[si][o]
    hits = 0
    for d in range(7):
        for i in range(p.intervals_per_day):
            if not p.active[d][i]:
                continue
            req = float(p.requirements[d][i] or 0.0)
            eff = 1.0 - float(p.shrinkage[d][i])
            qs = [d * 96 + i * qpi + k for k in range(qpi)]
            cov = sum(pres[q] + len(E.prior_covering_associates(p, q)) for q in qs) * eff / qpi
            pct = cov / req if req > 0 else 1.0
            hits += int(pct + 1e-9 >= p.target_ratio)
    return hits


def score_run(E, run_dir: Path) -> Dict:
    final = sorted(run_dir.glob("*BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx"))
    inp = sorted((run_dir / "input_snapshot").glob("*.xlsx"))
    if not final or not inp:
        raise FileNotFoundError(f"{run_dir}: no final workbook or input snapshot")
    p = E.parse_input(inp[0])
    sk = E.load_seed_skeleton(p, final[0], "diagnostic_week")
    if sk is None or sk.diagnostics.get("invalid_seed_cells"):
        raise ValueError(f"{run_dir}: week not readable")
    selected, unmatched = engine_break_selection(E, p, sk, final[0])
    m = E.calculate_metrics(p, sk, selected, E.generate_break_patterns(p))
    return {"run": run_dir.name, "input": inp[0].name, "before_target": m["before_target"],
            "after_target": m["after_target"], "unmatched_break_sets": len(unmatched),
            "pred_flat": predicted_after_hits(E, p, sk, "flat"),
            "pred_window": predicted_after_hits(E, p, sk, "window")}


def spearman(xs: List[float], ys: List[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda k: v[k])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2.0
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("run_dirs", nargs="+")
    a = ap.parse_args()
    E = S.load_engine(a.engine)
    rows, errors = [], []
    for pattern in a.run_dirs:
        for d in sorted(glob.glob(pattern)):
            try:
                rows.append(score_run(E, Path(d)))
            except Exception as exc:  # recorded, never hidden
                errors.append({"run": d, "error": f"{type(exc).__name__}: {exc}"})
    summary = {}
    for mode in ("flat", "window"):
        err = [abs(r[f"pred_{mode}"] - r["after_target"]) for r in rows]
        summary[mode] = {"mae": round(sum(err) / len(err), 3) if err else None,
                         "mean_signed": round(sum(r[f"pred_{mode}"] - r["after_target"] for r in rows) / len(rows), 3) if rows else None,
                         "spearman_with_after": round(spearman([r[f"pred_{mode}"] for r in rows],
                                                               [r["after_target"] for r in rows]), 3) if len(rows) > 2 else None}
    out = {"runs": len(rows), "summary": summary, "rows": rows, "errors": errors}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(out, indent=1))
    print(json.dumps({"runs": len(rows), "errors": len(errors), "summary": summary}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
