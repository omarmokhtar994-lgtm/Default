"""Census: how many real Stage-2 break attempts does each run actually execute?

Reads every solver audit JSON under a root and reports, per run, the
break_search allocation, how many adaptive break attempts returned a solution,
how many were planned, and the slice the loop was offered when it stopped.

Run:  python3 tools/stage2_attempt_census.py <root> [<root> ...]
"""
import json, glob, os, sys


def census(roots):
    rows, seen = [], set()
    for root in roots:
        for f in sorted(glob.glob(f"{root}/**/*.l6_3_2_3_solver_audit.json",
                                  recursive=True)):
            try:
                a = json.load(open(f))
            except (OSError, ValueError):
                continue
            attempts = a.get("stage2_attempts") or []
            if not attempts:
                continue
            name = os.path.basename(f).split(".")[0]
            if name in seen:
                continue
            seen.add(name)
            g = a.get("global_budget") or {}
            bs = next((p for p in g.get("phases", [])
                       if p.get("phase") == "break_search"), {})
            stop = next((r for r in attempts
                         if r.get("cp_status") ==
                         "STOPPED_INSUFFICIENT_BREAK_SEARCH_DEPTH"), None)
            real = [r for r in attempts
                    if r.get("phase") == "adaptive_fully_compliant_break_search"
                    and r.get("cp_status") in ("FEASIBLE", "OPTIMAL")]
            rows.append({
                "run": name,
                "budget_sec": g.get("total_seconds"),
                "break_search_alloc_sec": bs.get("allocated_seconds"),
                "real_attempts": len(real),
                "attempts_planned": (stop or {}).get("attempts_planned"),
                "proposed_slice_sec": (stop or {}).get("proposed_slice_sec"),
            })
    return rows


if __name__ == "__main__":
    rows = census(sys.argv[1:] or ["."])
    hdr = ("run", "budget_sec", "break_search_alloc_sec", "real_attempts",
           "attempts_planned", "proposed_slice_sec")
    print(f"{hdr[0]:<34}{hdr[1]:>8}{hdr[2]:>12}{hdr[3]:>8}{hdr[4]:>10}{hdr[5]:>10}")
    for r in rows:
        print(f"{r['run']:<34}{str(r['budget_sec']):>8}"
              f"{str(r['break_search_alloc_sec']):>12}{r['real_attempts']:>8}"
              f"{str(r['attempts_planned']):>10}{str(r['proposed_slice_sec']):>10}")
    at1800 = [r for r in rows if r["budget_sec"] == 1800]
    zero = [r for r in at1800 if r["real_attempts"] == 0]
    print(f"\n1800s runs: {len(at1800)}   with ZERO real break attempts: {len(zero)}")
