# Patch P-1 — memoised `shift_day_demand_fit`

Applied on top of RC5. **Measurement only. No scheduling behaviour changes.**

| | |
|---|---|
| Base RC5 engine | `0e6f643552c5e59f284fefbabc74803c3450b2a1cd2de47fad44781f6408cc5c` |
| Patched engine | `b005d6b6edd3000b79addb5f362acfc20dcfb12aaa1ab3d0ea274da5da703af4` |
| Files changed | `engine/_tools/l632_universal_scheduler.py` (one function split in two), plus one new test file |
| Offline gate | **12 suites, 459 tests, PASS** (was 11 suites, 453) |

## What changed

`shift_day_demand_fit` is a pure function of `(day, shift.index, start, duration)`.
It reads only `parsed.active`, `parsed.interval_minutes` and
`parsed.intervals_per_day` plus the shift's own start and duration — none of
which is written after `parse_input` returns. There are at most
7 x len(shifts) distinct answers, 168 on every packaged workbook.

It was being recomputed **over 600,000 times per run**:

```
shift_day_demand_fit          632,649 calls  ->  168 distinct results
cyclic_requirement_context 22,775,364 calls
```

The computation is now cached on the parsed contract, so the cache is scoped to
one run and is collected with it — no module-level state and no `id()` reuse
hazard. The original body is preserved verbatim as
`_shift_day_demand_fit_uncached`.

## Why it matters beyond speed

Stage 1 is wall-clock budgeted and already reports
`TRUNCATED_INSUFFICIENT_STAGE1_BUDGET` on long runs. Time spent here is search
that never happens. The same function is also called from
`solve_joint_shift_off_language_break_refinement` (line ~13165), inside the
search loop — that gain is **unmeasured** and is not claimed here.

## Measured: identical output, faster

Every packaged workbook, `capacity_diagnostics` and `validate_input_contract`
compared as canonicalised JSON:

| Workbook | Base | Patched | Speedup | Capacity | Preflight |
|---|---:|---:|---:|---|---|
| AE_AR_B2B | 11.10s | 1.48s | 7.5x | IDENTICAL | IDENTICAL |
| Cricut_Chat | 6.87s | 0.80s | 8.5x | IDENTICAL | IDENTICAL |
| Cricut_Voice | 3.18s | 0.87s | 3.7x | IDENTICAL | IDENTICAL |
| GDI_REAL28 | 6.91s | 0.85s | 8.1x | IDENTICAL | IDENTICAL |
| NMG_EN_AND_SP | 1.46s | 0.21s | 6.8x | IDENTICAL | IDENTICAL |
| NMG_EN_FIXED_NESTING | 3.25s | 1.22s | 2.7x | IDENTICAL | IDENTICAL |
| NMG_SP | 0.06s | 0.02s | 2.6x | IDENTICAL | IDENTICAL |
| NMG_EN_PRODUCTION | 3.23s | 1.21s | 2.7x | IDENTICAL | IDENTICAL |
| **Total** | **36.07s** | **6.67s** | **5.4x** | | |

## Guards added

`tests/test_rc9_2_3_demand_fit_memo.py` — 6 tests pinning the two ways a cache
of this shape corrupts results, plus the inertness claim itself:

- repeated calls agree with the uncached computation;
- a cache hit returns a **fresh mapping** (`demand_fit_blocked` writes
  `blank_requirement_blocked` into the returned dict — sharing it would leak
  that flag between unrelated shifts);
- two shifts sharing an index do not collide (start and duration are in the key);
- two parsed contracts in one process do not share a cache;
- a contract that refuses attributes still answers correctly, uncached;
- **capacity output is byte-identical to the uncached engine on every packaged
  workbook.**

## What was NOT changed

`FINAL_VALIDATION_AND_READINESS_REPORT.md` still records the base RC5 engine
hash. That is deliberate: it is the evidence for the build as originally
validated, and it was not rewritten to describe a build it did not test.

`RELEASE_STATUS.json` is unchanged — still
`NO_GO_PENDING_RC5_TARGETED_RUNTIME_REVIEW`, `production_ready: false`.
This patch does not change the release decision.
