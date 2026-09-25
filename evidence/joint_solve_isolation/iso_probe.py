"""Replay Chat's DEEP joint refinement with the isolated-solve engine on an
emulated CAP-MB machine: free memory = CAP - PSS of this process and its
children (so the running measurement's memory does not leak in). The earlier
in-process replay died with MemoryError in attempt 2 (evidence/DEEP_MODE_OOM.md)."""
import sys, json, glob, io, time, threading, importlib.util, os
from pathlib import Path
eng, run_dir, CAP = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
spec = importlib.util.spec_from_file_location("E", eng); E = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(Path(eng).parent)); sys.modules["E"] = E; spec.loader.exec_module(E)

def pss(pid):
    try:
        with open(f"/proc/{pid}/smaps_rollup") as f:
            for line in f:
                if line.startswith("Pss:"):
                    return int(line.split()[1]) // 1024
    except Exception:
        return 0
    return 0
def tree_pss():
    me = os.getpid(); total = pss(me)
    for tid in os.listdir(f"/proc/{me}/task"):
        try:
            kids = open(f"/proc/{me}/task/{tid}/children").read().split()
        except Exception:
            kids = []
        total += sum(pss(int(k)) for k in kids)
    return total
peak = {"v": 0}
def emulated_free():
    used = tree_pss(); peak["v"] = max(peak["v"], used)
    return CAP - used, CAP
E.machine_free_memory_mb = emulated_free

P = E.parse_input(next(iter(glob.glob(str(run_dir / "input_snapshot" / "*.xlsx")))))
pool = json.load(open(run_dir / "debug" / "CANDIDATE_POOL_CHECKPOINT.json"))
cands = [E.deserialize_break_candidate(P, r) for r in pool["compliant"]]
for sk, br in cands:
    br.metrics = E.calculate_metrics(P, sk, br.selected_pattern, br.patterns)
best_before = max((sk for sk, _ in cands), key=lambda s: (E.ensure_before_break_metrics(P, s) or {}).get("before_target", 0))
print(f"loaded {len(cands)} candidates, pss {tree_pss()}MB, emulated machine {CAP} MB, kill below {E.joint_solve_kill_threshold_mb(CAP)} MB free", flush=True)

class Tee(io.StringIO):
    def write(self, s):
        if "JOINT" in s: print("  LOG", s.strip()[:300], f"pss={tree_pss()}MB", flush=True)
        return super().write(s)
t0 = time.time()
added, recs, ex = E.run_adaptive_decomposed_joint_optimizer(
    P, cands, best_before, 115, time.time() + float(sys.argv[4]), 2, Tee(), 9000,
    base_shift_options_per_cell=10, base_patterns_per_shift=64, maximum_attempts=48, no_improvement_limit=16,
    protected_target_tolerance=1, operational_exception_cap=E.operational_no_break_exception_cap(P))
print("RETURNED NORMALLY", {k: ex.get(k) for k in ("attempted", "accepted", "improved", "truncated")},
      f"peak tree pss {peak['v']}MB {time.time()-t0:.0f}s", flush=True)
print("memory_headroom_stop:", json.dumps(ex.get("memory_headroom_stop"))[:600], flush=True)
print("memory stops:", json.dumps(E._JOINT_SOLVE_MEMORY_STOPS), flush=True)
