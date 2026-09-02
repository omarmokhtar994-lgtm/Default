# ChatGPT prompt — retrieve the RC9.1 comparator for Gates 2 and 9

Copy everything between the lines into ChatGPT, in the conversation/project that
holds the RC9.2.1 history.

---

I need you to retrieve specific existing artifacts from our earlier RC9.1 /
RC9.2.1 work. This is a **retrieval and verification** task, not a generation
task. Read the rule at the bottom before you answer.

## Background

We are validating release `L6.3.2.5-RC9.2.1-PROTECTED-TIER-RESIDUAL-BALANCE-RC1`
of the Universal WFM Scheduler (CP-SAT, workbook-driven). Nine release gates.
Seven are decided. Two are blocked, and both are blocked on the same missing
thing:

- **Gate 2** — NMG EN under RC9.2.1 must be *not materially worse* than the same
  scenario under RC9.1.
- **Gate 9** — regression quality across the scenario set under RC9.2.1 must be
  *not materially worse* than under RC9.1.

Both are defined relative to RC9.1. We hold the RC9.2.1 side in full. We hold
**no** RC9.1 side. Without it neither gate can be given an honest verdict, so
both are currently reported as `REQUIRES_RC9_1_BASELINE` rather than as a pass.

The RC9.1 engine is identified as:

```
version      L6.3.2.3-RC9.1-UNIVERSAL-SEARCH-RECOVERY-PLATFORM
engine_sha256 da21c3bacf577e5a806dae0c75fbc70411d0747b2ef599d391ad9f276074e415
```

The only RC9.1 artifact we have is one Cricut resume checkpoint
(`run_id fd33cad861ae89be822b98e3`, `input_sha256 675fd57a22c55762…`) whose input
workbook we do not have, so it cannot be re-run.

## What I need — either one of these unblocks BOTH gates

### Option A (strongly preferred — one file, settles everything)

**The RC9.1 engine source file itself**, the Python module whose SHA-256 is
`da21c3bacf577e5a806dae0c75fbc70411d0747b2ef599d391ad9f276074e415`.

Likely named `l632_universal_scheduler.py` or similar, roughly 15,000–20,000
lines, containing a line like
`VERSION = "L6.3.2.3-RC9.1-UNIVERSAL-SEARCH-RECOVERY-PLATFORM"`.

With this I run RC9.1 against the identical fixtures myself and produce the
comparison directly — no trust required, and it also answers a separate open
question (whether RC9.1 shared the deficit-masking candidate ordering or whether
that arrived in RC9.2).

If you have any RC9.1 engine file but cannot confirm the hash, send it anyway
and say plainly that the hash is unverified. I will hash it myself.

### Option B (acceptable — per-scenario RC9.1 KPIs)

RC9.1 **result artifacts** — result workbooks, `*.l6_3_2_3_summary.csv` files,
`*_solver_audit.json` files, or candidate leaderboards — for as many of these
scenarios as exist:

| Scenario | Workbook we hold |
|---|---|
| NMG EN historical A/B | `NMG_EN_RC9_1_HISTORICAL_AB_INPUT.xlsx` |
| NMG SP | `NMG_SP_RC9_1_READY_FIXED.xlsx` |
| Cricut Voice | `Cricut_Voice_RC9_1_READY_SKELETON.xlsx` |
| Cricut Chat | `Cricut_Chat_RC9_1_READY_SKELETON.xlsx` |
| GDI REAL28 24/7 | `GDI_REAL28_RC9_1_24_7_INPUT_RC9_1_UPDATED(2)_FINAL_READY.xlsx` |
| NMG EN & SP bilingual | `NMG_EN&SP.xlsx` |
| AE Arabic B2B | `AE_AR_B2B.xlsx` |

Gate 2 needs NMG EN. Gate 9 needs as many as you have. **Partial is useful** —
send whatever exists, scenario by scenario.

For each scenario I need these fields, which are the columns our gate report
compares:

```
status, functional_status, active_intervals,
before_target, after_target, before_floor, after_floor,
before_100 / before_90 / before_80, after_100 / after_90 / after_80,
severe_floor_gaps, max_consecutive_floor_gaps, floor_deficit_sum,
target_losses_from_breaks, floor_losses_from_breaks,
before_avoidable_overage_fte_sum, after_avoidable_overage_fte_sum,
no_break_exceptions, minimum_exception_proven,
quality_benchmark_status, elapsed_sec
```

Raw files are better than a transcription. If you can only give me numbers in
text, give them per scenario in a table and say which file each row came from.

### Option C (fallback — the Cricut checkpoint's input)

The input workbook with `input_sha256` starting `675fd57a22c55762`, which the
RC9.1 Cricut checkpoint was produced from. That makes exactly one RC9.1 run
reproducible. Weakest of the three, but better than nothing.

## Also useful, lower priority

1. The run parameters used for the RC9.1 runs: time limit, `--mode`,
   `--pattern-widths`, `--skeleton-profiles`, `--break-objective-modes`,
   `--solver-random-seed`, worker count. Without matching parameters an A/B is
   not apples to apples.
2. Any RC9.1 → RC9.2 → RC9.2.1 changelog, release note, or diff summary.
3. The OR-Tools version RC9.1 ran on (we are on 9.15.6755).

## Where to look

Search our earlier conversations and any attached files for: `da21c3ba`,
`RC9.1`, `RC9_1`, `UNIVERSAL-SEARCH-RECOVERY-PLATFORM`, `fd33cad8`, `675fd57a`,
`l632_universal_scheduler`, `l6_3_2_3_summary`, `solver_audit`,
`RUN_IDENTITY.json`, `CANDIDATE_LEADERBOARD`, `PRODUCTION_ARTIFACT_MANIFEST`.
Check ZIP bundles and any "engine" or "checkpoint" attachments as well as loose
files.

## How to answer

1. State first, in one line, which of A / B / C you can supply.
2. Attach the actual files. Split large ones rather than summarizing them.
3. For anything you cannot find, name it and say it is not present.
4. Where you are unsure a file is genuinely RC9.1, say so and let me verify by
   hash rather than deciding for me.

## The one hard rule

**Do not reconstruct, regenerate, approximate, infer, or estimate any of this.**

Do not write a "representative" RC9.1 engine. Do not produce plausible-looking
RC9.1 KPI numbers. Do not fill a gap in a table with a guess, an interpolation,
or a value carried over from RC9.2.1.

These numbers decide whether a scheduling engine ships. A fabricated baseline
would produce a confident, wrong release verdict, and it would be
indistinguishable from a real one once it entered the evidence pack. **A missing
comparator is a known blocker. A fabricated one is a silent failure.**

"I could not find it" is a complete and useful answer. Give me that instead of
anything invented.

---
