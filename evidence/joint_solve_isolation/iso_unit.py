import os, sys, time, tempfile, traceback, random
from typing import Any, Dict, List, Optional, Tuple
exec(open(sys.argv[1]).read())
from ortools.sat.python import cp_model
def build(n=300, seed=1):
    rnd=random.Random(seed); m=cp_model.CpModel()
    xs=[m.new_bool_var(f"x{i}") for i in range(n)]
    for _ in range(n*2):
        a,b,c=rnd.sample(xs,3); m.add_bool_or([a,b.Not(),c])
    m.add(sum(xs) <= n//2)
    m.maximize(sum(rnd.randint(1,9)*x for x in xs))
    return m, xs
def conf(s):
    s.parameters.max_time_in_seconds=10; s.parameters.num_search_workers=1; s.parameters.random_seed=7
    s.parameters.max_deterministic_time=1.0
for seed in range(3):
    m,xs=build(seed=seed)
    a=cp_model.CpSolver(); conf(a); sa=a.Solve(m)
    b=isolated_cp_solver(cp_model); conf(b); sb=b.Solve(m)
    same = (sa==sb, a.ObjectiveValue()==b.ObjectiveValue(), a.BestObjectiveBound()==b.BestObjectiveBound(),
            [a.Value(x) for x in xs]==[b.Value(x) for x in xs], a.NumBranches()==b.NumBranches(), a.NumConflicts()==b.NumConflicts(),
            a.StatusName(sa)==b.StatusName(sb), a.response_proto.deterministic_time==b.response_proto.deterministic_time)
    print(seed, a.StatusName(sa), a.ObjectiveValue(), same, b.isolation_record)
