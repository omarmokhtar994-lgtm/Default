# © 2026 Omar Mokhtar. All rights reserved.
"""Phase BJ (owner, 2026-11-04: "I want the one equals =agents() in Excel"): the Erlang staffing as Excel formulas.

Two forms of the same calculation:
  * ``agents_formula`` / ``service_level_formula``: ONE ordinary cell formula each, written with functions every Excel version and LibreOffice have
    (POISSON, SUMPRODUCT, ROW, INDIRECT, EXP; no LET, no LAMBDA, no array entry, no macro). Verified by recalculating them in LibreOffice on thousands of
    random cases against the Python Erlang the site uses (webapp/tests/test_bj_excel_agents.py).
  * ``lambda_definitions``: the same expressions as named Excel 365 functions, so a cell can say ``=AGENTS(calls, aht, interval, target, secs, maxocc)``.
    The text is pasted into Name Manager once.

The method is the site's (webapp/erlang.py): traffic A = calls x AHT / interval; Erlang B through the Poisson ratio B = POISSON(N, A, FALSE) / POISSON(N, A, TRUE);
Erlang C = B / (1 - (A / N) x (1 - B)); service level = 1 - C x EXP(-(N - A) x secs / AHT); the agents needed are the fewest N above A with the service level at
least the target and the occupancy A / N at most the cap. Because the service level only rises with N, the answer is
INT(A) + 1 + (the N tried that fail): a count, so no array entry is needed.
"""
from __future__ import annotations


def _traffic(calls: str, aht: str, interval: str) -> str:
    return f"({calls}*{aht}/{interval})"


def agents_formula(calls: str, aht: str, interval: str, target: str, secs: str, max_occ: str) -> str:
    """The cell formula (no leading "=") for the agents needed. Arguments are cell references or numbers, as text: ``calls``; ``aht`` seconds;
    ``interval`` seconds; ``target`` the service level as a fraction (0.8); ``secs`` the answer time; ``max_occ`` the highest occupancy as a fraction."""
    a = _traffic(calls, aht, interval)
    m = f"(ROUNDUP(2*{a}+60,0)-INT({a}))"                       # how many agent counts are tried above the traffic
    n = f"(INT({a})+ROW(INDIRECT(\"1:\"&{m})))"                 # INT(A)+1 ... : every one is above the traffic
    b = f"(POISSON({n},{a},FALSE)/POISSON({n},{a},TRUE))"       # Erlang B
    c = f"({b}/(1-({a}/{n})*(1-{b})))"                          # Erlang C
    sl = f"(1-{c}*EXP(-({n}-{a})*{secs}/{aht}))"
    passed = f"SUMPRODUCT(({sl}>={target}-1E-12)*({a}/{n}-{max_occ}<=1E-12))"  # compared to 12 places, as erlang.agents_needed does
    return f"IF({calls}<=0,0,IF({passed}=0,NA(),INT({a})+1+{m}-{passed}))"


def service_level_formula(agents: str, calls: str, aht: str, interval: str, secs: str) -> str:
    """The cell formula (no leading "=") for the share answered within ``secs`` seconds (0 to 1) with ``agents`` on the phone."""
    a = _traffic(calls, aht, interval)
    b = f"(POISSON({agents},{a},FALSE)/POISSON({agents},{a},TRUE))"
    return (f"IF({calls}<=0,1,IF({agents}<={a},0,MAX(0,1-{b}/(1-({a}/{agents})*(1-{b}))*EXP(-({agents}-{a})*{secs}/{aht}))))")


def lambda_definitions() -> str:
    """Text for Excel 365's Name Manager (Formulas, Name Manager, New): a name, then this in "Refers to". Same expressions as the cell formulas."""
    agents = ("=LAMBDA(calls, aht, interval, target, secs, maxocc, IF(calls<=0, 0, LET(erl, calls*aht/interval, cnt, ROUNDUP(2*erl+60,0)-INT(erl), "
              "nn, INT(erl)+SEQUENCE(cnt), erlb, POISSON(nn,erl,FALSE)/POISSON(nn,erl,TRUE), erlc, erlb/(1-(erl/nn)*(1-erlb)), "
              "sla, 1-erlc*EXP(-(nn-erl)*secs/aht), hits, SUM((sla>=target-1E-12)*(erl/nn-maxocc<=1E-12)), IF(hits=0, NA(), INT(erl)+1+cnt-hits)))))")
    level = ("=LAMBDA(agents, calls, aht, interval, secs, IF(calls<=0, 1, LET(erl, calls*aht/interval, IF(agents<=erl, 0, "
             "LET(erlb, POISSON(agents,erl,FALSE)/POISSON(agents,erl,TRUE), MAX(0, 1-erlb/(1-(erl/agents)*(1-erlb))*EXP(-(agents-erl)*secs/aht)))))))")
    return ("AGENTS\n" + agents + "\n\nSERVICELEVEL\n" + level + "\n")
