# Coverage Split — end-to-end verification

What this file answers: does the Coverage Split feature actually make a group
staff the hours it owns, and do overlapping windows pool instead of stacking.
Both were claimed before they were measured; this is the measurement.

Engine: `L6.3.2.6-RC9.2.2-BUDGETED-SEARCH-AND-BREAK-CONCURRENCY-RC1`,
sha256 `4fe4c287…`. Workbook: Cricut Voice roster (40 associates — 8
International, 32 Domestic), DEEP, 2400s, 4 workers, seed 9000.

---

## 1. The problem the feature exists to solve

Language Setup's `Coverage Start` / `Coverage End` with `Minimum Per Interval`
is a **presence** rule: "at least N of this group are on the floor". It never
said who *carries* the requirement. On Cricut Voice that meant International's
03:00–16:00 window with a minimum of 1 was satisfied by a single International
associate while Domestic staffed the daytime — which is not the split the roster
was built around.

The user's own diagnosis was correct and worth recording: removing International
made the workbook solve, and setting International's minimum to 0 made it solve,
because the constraint that was actually binding was International's — not
Domestic's.

## 2. Overlapping windows: measured

Fixture `voice_split_overlap.xlsx` — deliberately overlapping:

| Coverage Group | Window | Ratio | Eligible |
|---|---|---|---|
| International | 03:00–17:00 | 0.6 | international |
| Domestic | 16:00–03:00 | 0.6 | domestic, international |

They share 16:00–16:45, four quarter-hours.

**Preflight** (`COVERAGE_SPLIT` lines, before the solver starts):

```
TIGHT International               : 8 eligible, 4 needed at the Wed 13:00 peak
                                    once breaks are covered, ceiling about 5
OK    International + Domestic    : 32 eligible, peak need 9 at Wed 16:00,
                                    11 once breaks are covered, ceiling about 22
OK    Domestic                    : 32 eligible, peak need 10 at Sun 19:00,
                                    12 once breaks are covered, ceiling about 22
SHARED International (03:00-17:00) and Domestic (16:00-03:00) share 4
       quarter-hours from 16:00 to 16:45.
```

Note the middle row. The shared span is scored **once**, as a pooled unit of 32
eligible against a need of 9. Before this change the report scored each rule
against the whole requirement independently, which charged International the
16:00 peak of 9 against its 8-person pool and reported **SHORT** — a shortage
the solver never sees.

**Enforcement, checked against the schedule the engine produced:**

| Span | Owned intervals with a requirement | Intervals below the requirement |
|---|---|---|
| International solo, 03:00–16:00 | 130 | **0** |
| Pooled, 16:00–17:00 | 10 | **0** |
| Domestic, 17:00–03:00 | 124 | **0** |

International staffs all 130 of its daytime intervals at 60% of the grossed-up
requirement. That is the behaviour the Language Setup window never produced.

**Why pooling is not a cosmetic difference.** At Sun 16:00 the requirement is 8:

```
need 8 | pooled on the floor 14  (International 3 + Domestic 11)
```

Under the old stacking rule that hour demanded 8 **International** people *and*
8 from Domestic. There are only 8 International associates in the entire roster,
so with two OFF days each that is arithmetically impossible — stacking makes the
run infeasible on a fixture that pooling solves with six to spare.

## 3. The break stage is the honest limit, and it was predicted

The overlap run reached a full before-breaks skeleton — 263 of 264 active
intervals at target, 264 at floor — and then failed break placement:

```
FAIL_BREAKS_REQUIRE_EXPLICIT_EXCEPTION_FOR_TESTED_SKELETONS
proven minimum no-break exceptions: 7, permitted: 0
```

This is exactly what the preflight said would happen: International at 0.6 was
reported `TIGHT` with headroom 1 and the words "expect no-break exceptions".
Eight people cannot hold 60% of a 14-hour daytime window *and* take their own
breaks. That is a headcount fact, not a solver defect, and the value of the
capacity report is that it says so in one line before 40 minutes of solving
rather than as a bare `INFEASIBLE` afterwards.

Ratio sweep on the same roster, from the capacity report:

| International ratio | verdict | peak need → with breaks | ceiling |
|---|---|---|---|
| 0.60 | TIGHT | 3 → 4 | 5 |
| 0.55 | TIGHT | 3 → 4 | 5 |
| 0.50 | **OK** | 2 → 3 | 5 |
| 0.45 | OK | 2 → 3 | 5 |
| 0.40 | OK | 2 → 3 | 5 |

## 4. Complementary windows at an achievable ratio

<!-- FINAL_RUN_RESULT -->

## 5. What is *not* claimed

* **No packaged scenario is affected.** All seven ship with no Coverage Split
  rows; a workbook without the tab, or with the tab and no active rows, builds
  zero coverage-split constraints. Pinned by a guard that parses all seven.
* **A `TIGHT` or `OK` verdict is not a promise of a solve.** Like the break
  capacity measure it shares arithmetic with, it counts room, not whether break
  windows and spacing let a placement reach that room. A `SHORT` verdict is the
  side that proves something.
* **The overlap fixture is synthetic.** The real Cricut Voice split is
  complementary (International 03:00–16:00, Domestic 16:00–03:00). The overlap
  was constructed to exercise pooling, because no packaged workbook overlaps.
