# NMG EN+SP break damage — all three hypotheses closed

Three candidates were listed after the A40 experiment ruled out concurrency.
All three are now answered.

## 1. Break window and spacing rules — RULED OUT

| | |
|---|---|
| Shift | 9h = 540 min |
| Breaks | 15 + 30 + 15 = 60 min |
| Two gaps at *preferred* 150 min | 300 min |
| **Span at preferred spacing** | **360 of 540 min** |
| **Freedom remaining** | **180 min** |
| Absolute minimum gap | 60 min |
| Edge margin | 0 min |

The pattern fits with three hours to spare and compression stays legal down to
60 minutes. The 82 recorded compressions are the solver choosing to squeeze, not
the contract forcing breaks onto covered intervals. **Not the cause.**

## 2. Skeleton break-compatibility — CONFIRMED, and it is arithmetic

Per quarter-slot: how many people can go on break without dropping the interval
below target (bounded by the concurrency cap)? Sum that and compare with the
break-quarters that must be placed.

| | NMG EN+SP | Cricut Voice |
|---|---|---|
| active quarter-slots | 504 | 528 |
| **slots with ZERO target slack** | **396 (78.6%)** | 108 (20.5%) |
| break-quarters that must be placed | 340 | 660 |
| **lossless capacity available** | **112** | **902** |
| | **deficit 228** | surplus 242 |
| **verdict** | **FORCED** | NOT FORCED |
| observed absorption | **−25%** | **97%** |

**On NMG EN+SP, 228 break-quarters have nowhere lossless to go.** Nearly four
fifths of the week runs at exactly target with no spare body, so any break in
those intervals costs coverage. No break placement can avoid it and no engine
change can create the slack.

Cricut Voice, on the same engine, has a surplus of 242 and absorbs 97%. The
difference between the two scenarios is staffing headroom, not engine capability
— which is exactly what the absorption figures showed and now has a mechanism.

**This is the answer.** NMG EN+SP's Gate 5 failure reports a real business
constraint: the roster cannot cover the contract *and* take its breaks. It is
fixed by headcount, a lower target, or shorter/fewer breaks — not by the
scheduler.

## 3. Selector — CONFIRMED as a real but separate defect

My earlier phrasing, "ranking among already-damaged candidates rather than
preventing the damage", was **wrong**. The winner is the *least* damaged
candidate (35 lost against 42). Corrected statement: the selector maximises
`after_target` lexicographically and is indifferent to floor, overage and tier
breadth once `after_target` is settled.

The leaderboard is a clean Pareto frontier — rows 3-11 are all the same skeleton:

| # | b90 | a90 | after_floor | overage FTE | extreme |
|---|---|---|---|---|---|
| **1 (shipped)** | 188 | **153** | 203 | 29.96 | 14 |
| 3 | **192** | 150 | **212** | **22.07** | **9** |
| 11 | 192 | 130 | **223** | **18.86** | 11 |

Row 3's skeleton is better before breaks on both axes (192/239 against 188/225)
and better after breaks on floor and overage. It loses on exactly one metric —
the one ranked first. Nine after-break floor intervals, five extreme-overage
intervals and 7.89 FTE of avoidable overage were traded for three target
intervals.

This is real and worth fixing, but it is **not** what causes the 35-interval
break loss. Given the forced deficit above, even a perfect selector cannot
recover most of it.

## Consequence for release

The largest remaining quality complaint against RC9.2.2 is **not an engine
defect**. Gate 5's failure on NMG EN+SP is the gate correctly reporting that the
roster is too thin to cover the contract and take breaks.

The selector trade remains open as a genuine improvement (P1), scoped to an
epsilon-constraint that forbids losing more than N floor intervals to gain one
target interval. It is not a release blocker.
