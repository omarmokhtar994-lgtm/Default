# Overnight session: facts, measured

Every number below came from a run or a count. Inferences are labelled as such.

---

## APPLIED, TESTED, KEPT

| change | evidence | verification |
|---|---|---|
| Solver telemetry | instrumentation only | gate 20 suites |
| Memory ceiling 6000 MB | binds before the 7760 MB OOM point | gate 21 suites |
| Gap limit left OFF | see fact 2 below | — |
| **Joint refinement OFF at SMOKE/QUICK** | 69 attempts, 7 workbooks, `improved: 0` | gate 22 suites + end-to-end |

End-to-end verification, AE_AR_B2B 1800s: peak **8197 -> 798 MB**, stage1/stage2
attempts identical (9/2), coverage identical, floor +1, parity PASS. No revert.

DEEP and OVERNIGHT keep joint refinement ON. They allot it 5400s/8400s and
remain unmeasured.

---

## FACT 1 — six strategies have never executed

48 leaderboards. Of 15 skeleton profiles: **5 ever win, 4 run and never win,
6 have never run at all** (positions 9-15; truncation always lands first).
Break objective modes: **2 of 7 never execute** (`balanced`, `target_100`).

`before_target_champion` is position 14, never executed — and the Voice
investigation measured that exact profile reaching 250 against a run's 247.

Not concluded: that reordering is the fix. A34 says reordering "was written and
then removed" and points at a rationale file that is **not in `evidence/`**.

---

## FACT 2 — the gap-stop lever is dead. It was mine, and I retract it.

167 telemetry records. **106 solves (63%) consume >=99% of their slice.** Of the
103 reporting both objective and bound:

| | |
|---|---|
| median relative gap | **88.93%** |
| tightest solve in corpus | 14.39% |
| would stop at 1e-6 / 1e-5 / 1e-4 / 1e-3 | **0 / 103 at every threshold** |

I had claimed a gap stop "would return roughly 40 of those 45 seconds" from one
solve measured at 0.00058%. That was an outlier. Retracted.

What replaces it is better: with `branches_per_conflict` reaching **73,797** and
B-5's **400,000,000:1** objective range, the engine is **bound-starved, not
time-starved**. Weak relaxation -> weak bound -> no pruning -> enumeration ->
full slice every time. **B-5 was closed for coverage and never tested for
speed.** That is the open lever.

---

## FACT 3 — the OOM is fixed, verified at the budget that crashed

AE_AR_B2B at 3600s, the run killed at 7,758,648 kB with no schedule:

| | before | after |
|---|---|---|
| peak RSS | **7760 MB, SIGKILL** | **827 MB** |
| return code | -9 | 0 |
| schedule | none | valid, production eligible |

---

## FACT 4 — worker count is the largest quality lever measured

All at 1800s. 1 worker versus 4:

| case | 1 worker | 4 workers | delta |
|---|---|---|---|
| **Cricut Voice** | 246 / **224** | 250 / **248** | **+24** |
| GDI_REAL28 | 141 / 137 | 153 / 141 | +4 |
| AE_AR_B2B | — / 165 | — / **168 (ceiling)** | +3 |
| Cricut Chat | 176 / 163 | 169 / 159 | **-4** |

**Voice gains 24 intervals from worker count alone**, no code change. Its RC9.1
target gap narrows from -10 to **-6** (250 vs 256), and its floor is separately
proven arithmetically capped by fixed requests.

Chat is the exception and went backwards at 1800s; at 3600s/4w it recovers to
164. Multi-worker is nondeterministic, and these are single runs.

**This qualifies every 1-worker figure in the review as a lower bound.**

---

## FACT 5 — QUICK's 3600s budget is justified. Do NOT cut it.

1800 -> 3600, all at 4 workers:

| case | 1800s | 3600s | verdict |
|---|---|---|---|
| AE_AR_B2B | 168/168 = **100%** | — | ceiling at 1800 |
| AE_FR_B2B | 112/112 = **100%** | — | ceiling at 1800 |
| Cricut Voice | 248 (94%) | 247 | plateau (-1, inside noise) |
| GDI_REAL28 | 141 (90%) | **150 (96%)** | **climbing +9** |
| Cricut Chat | 159 (66%) | **164 (68%)** | **climbing +5** |

The corpus splits: capacity-rich cases finish at 1800s, hard cases still gain at
3600s. **A single global budget cannot serve both, and cutting to 1800 would
cost Chat and GDI real coverage.**

This retracts my earlier inference from two cases that "QUICK is at least 2x
larger than needed". Measuring the hard cases contradicted it.

---

## RANKED, BY MEASURED EVIDENCE

1. **Raise the effective worker count.** Largest measured quality lever (+24 on
   Voice). Shipped default is `max(1, min(8, cpu_count))`, so a 4-core host gets
   4. Needs a host-capacity decision, not a code fix.
2. **Test B-5 for solve speed.** Three independent measurements point at it;
   never tested. Cheap: rescale coefficients, same seed, compare bound
   trajectory.
3. **Run the six never-executed strategies directly.** Answers their value with
   evidence instead of reordering theory.
4. **Keep QUICK at 3600.** Measured, not assumed.
5. **Adaptive per-case budget** — the two-population split suggests it. This is
   a design idea, NOT a measurement, and is listed last for that reason.
