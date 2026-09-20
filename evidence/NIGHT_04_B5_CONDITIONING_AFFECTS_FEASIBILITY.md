# B-5 tested for SPEED: compressing the weights turned UNKNOWN into FEASIBLE

B-5 was measured and correctly closed for **coverage** impact -- priority comes
from lexicographic selection and hard constraints, not the weights. It had
**never been tested for solve behaviour**. Three measurements pointed at it:
median relative gap 88.93%, `branches_per_conflict` up to 73,797, and 100%
slice consumption on every solve.

## Test

Same workbook, same profile (`target90_restore_champion`), same seed, same 120s
slice. Only change: profile weights remapped **rank-preserving** (i-th distinct
weight -> 4^i), so tier ORDER is identical and only the spread changes.

| case | weights | status | b/conflict | conflicts |
|---|---|---|---|---|
| AE_AR_B2B | original | **UNKNOWN** | 4,085 | 133 |
| AE_AR_B2B | compressed | **FEASIBLE** | 3,835 | 177 |
| Cricut_Chat | original | **UNKNOWN** | **369,110** | **11** |
| Cricut_Chat | compressed | **FEASIBLE** | **7,139** | **381** |

**On both cases the original weights found no solution in 120s and the
compressed weights did.**

On Cricut_Chat the search changes character completely: conflicts 11 -> 381
(35x more learning) and branches per conflict 369,110 -> 7,139 (52x less
enumeration). That is exactly the mechanism predicted by the bound-starvation
reading: a badly spread objective degrades the LP relaxation, the bound stays
weak, nothing prunes, and the search enumerates instead of learning.

## What this does NOT establish

* **Two cases, one profile, one slice length.** UNKNOWN at 120s may partly
  reflect a short slice rather than conditioning alone.
* **The compression reached only the profile-level weights** -- 4 distinct
  values spanning 91:1, narrowed to 64:1. B-5's measured **400,000,000:1** range
  arises during model construction, multiplying these through. The dramatic
  change came from a comparatively small adjustment, which is suggestive but
  means the real lever has not been touched yet.
* **Coverage was not compared.** Neither run reached the metrics stage, so this
  says nothing yet about whether compressed weights produce equal schedules.
  Since B-5 established the tiers do not separate, compression CAN change which
  solution is optimal. A faster-but-worse result would be a trade-off, not a win.

## Why it matters anyway

This is the first evidence that objective conditioning affects **whether a
solution is found at all**, not merely how fast. The Stage-2 `UNKNOWN` results
that have gone unexplained all session -- 3/3 on AE_AR_B2B at every worker
count, unaffected by the subsolver threshold -- now have a candidate mechanism
that has not been ruled out.

## Next measurement

Compress the construction-level coefficients rather than the profile weights,
at a production slice length, and compare coverage as well as status. That is
the test that decides whether this is a real lever or an artifact of a short
slice.
