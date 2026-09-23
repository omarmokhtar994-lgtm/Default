# Formula audit — start here

**Scope.** Every arithmetic statement in the five engine files:
`l632_universal_scheduler.py`, `phase_b_maturity.py`, `canonical_metrics.py`,
`independent_validator.py`, `RUN_UNIVERSAL_PRODUCTION.py` —
**1,102 formula statements** across 212 functions, extracted by AST so coverage
is provable rather than asserted (`formula_statements.json`).

**Method.** Three independent attacks, because reading 1,102 lines by eye
misses things:

1. **Mechanical scans for known defect classes** across every statement —
   shrinkage direction, division by zero, rounding direction on staffing.
2. **Reference implementations** for every domain formula — each checked
   against code that shares none of the engine's logic (`datetime` for time,
   brute force for break patterns, the metric's own definition for headcount).
3. **Engine-versus-validator parity** on real schedules, with every shared
   dependency verified on its own so agreement means independence.

**Files.**

| file | contents |
|---|---|
| `FINDINGS.md` | every section's result, and findings F-1 … F-5 with measurements and blast radius |
| `INDUSTRY_COMPARISON.md` | the engine against published WFM practice, with sources |
| `formula_statements.json` | the full inventory |
| `unguarded_divisions.json`, `divisions_to_triage.json` | the division-by-zero working |

**Findings at a glance.**

| id | what | status |
|---|---|---|
| F-1 | Stage-2 decided coverage hits in rounded ×100 arithmetic; disagreed with the metric on 70 of 2.8M cases, all on Cricut's 12/130 shrinkage | fix behind a deterministic A/B |
| F-2 | shifts off the 15-minute grid were silently mis-modelled | latent (0/197 shifts); fixed as a contract failure |
| F-3 | break headcount recommendation divided a weekly deficit by one day's contribution — up to 3.5× too many people | reporting only; fixed |
| F-4 | overage caps above 150% silently divided by 100; the order check was unreachable | latent (no workbook overrides caps); fixed |
| F-5 | target-loss gate typos silent, floor-loss typos reported under the wrong name — **introduced by this project's own W1 tool** | latent (no workbook sets either); fixed |
