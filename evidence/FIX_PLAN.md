# The fix plan — one list

Correcting a structural flaw in my own reporting: I published a 17-entry defect
register and an 8-entry improvements list as if they were different work. They
are not. **Five of the eight "improvements" were the fix strategy for defects
already registered** — the same work, written down twice under two names. Three
never reached the register at all, including the highest-value item in the
review.

This is the merged list. Everything below is "to be fixed"; nothing is a
separate category of nice-to-have.

---

## W1 — Cap and gate floor losses *(fixes register #1, S11-1)*

The only finding with a live observation.

* add `quality_max_floor_losses_from_breaks` to the contract
* gate it in `production_quality_gate` beside the target check
* stop line 14310 borrowing `quality_max_target_losses_from_breaks`
* remove the asymmetry: the floor bound applies only in `"fail"` mode while the
  target bound is unconditional

**Effort:** small. **Unlocks:** would have flagged sweep case 2's floor
regression (160 → 159, `floor_losses_from_breaks=3`, gate `PASS`).

## W2 — A contract vocabulary layer *(fixes #2 B-11, #3 C-3, #11 C-2 — one class)*

`yes()`, `tri_state()`, `preference_kind()` and the three name matchers all map
unrecognised input to a *valid* value instead of an error. One helper that maps
text → domain value or raises a `HARD_` code closes all three.

The pattern already exists: B-7's `strict_bool`, used at 2 of 12 sites.

* B-11 is already staged and verified (14/15 workbooks clean, gate 17 suites PASS)
* C-3 needs the vocabulary widened **and** `"other"` to stop meaning silence
* C-2 comes free once the flags route through the same parser

**Effort:** medium. **Unlocks:** removes the whole "silently discarded leave"
family, which parity is structurally blind to.

## W3 — Four fixtures *(NEW — was missing from the register entirely)*

The corpus measurement says exactly which are missing, and each turns a latent
finding into a failing test:

| fixture | exposes |
|---|---|
| a workbook with **floor ≠ 0.80** | all 10 `*_floor → *_80` fallbacks (#5) — invisible today because on 14/15 workbooks the floor *is* 80% |
| a workbook with a **nesting group** | S6-1 (#8) immediately, as an `INFEASIBLE` in 0.04s |
| a workbook with **multiple shift durations** | the 11H/3OFF path and `rest_compatible` across durations, both at 0/15 coverage |
| a workbook with **fixed requests enabled** | the fixed/nesting subsystem (#16), at 1/15 |

**Effort:** small–medium. **Unlocks:** this is the cheapest way to convert four
latent findings into caught ones, and it is why they stayed invisible.

## W4 — One source of truth for defaults *(fixes #6, RC-B / C-1 / S10-1)*

`ParsedInput` declares 117 defaults; 90 call sites declare a second, looser
answer, some inside `production_quality_gate`. Delete the call-site defaults and
read the attribute.

**Effort:** small, mechanical. **Contained:** zero instances in any satellite
module. **Unlocks:** removes the class, not 90 instances.

## W5 — The 18 cross-metric fallbacks *(fixes #5, RC-A)*

Replace each `get(A, get(B, …))` with a direct read, or an explicit branch where
the before/after distinction is real — which is what `_candidate_quality_tuple`
already does correctly at 10213.

**Effort:** small, mechanical. **Sequence after W3**, so the floor ≠ 0.80
fixture proves the change rather than assuming it.

## W6 — Enforce the phase minimums *(fixes #7, S15-3; resolves task #37)*

`PHASE_MINIMUM_VIABLE_SECONDS` exists and is advisory. Skip a phase allocated
below its own floor; redistribute the seconds.

**Effort:** small. **Needs:** A/B with repeats — the effect size is one interval
and multi-worker runs are nondeterministic.

## W7 — B-9 as staged, then a scoping decision *(fixes #9)*

The staged patch adds 7 derivations (parity surface 41 → 48, verified 8/8 pass
patched / 27 failures unpatched). The residual is **three subsystems the
validator does not model at all** — language reserve, skill allocation,
employee quality.

That second half is a decision, not a patch: either build the validator side,
or declare those metrics engine-only and stop letting them gate releases.
**Needs the authors.**

## W8 — Derive the orderings from one definition *(fixes #10 S9-2, #13 S9-1, #14 S9-3)*

Eleven orderings over the same candidates, one pair provably inconsistent. If
the dominance dimensions were generated as a subset of the quality tuple's
terms, S9-2 could not recur by construction. Also the place to state S9-1's
unwritten invariant (that `prefix="before"` requires a no-break metrics dict).

**Effort:** medium.

## W9 — B-10, the break-slice cap *(fixes #4)*

Split the constant into a floor and a cap, then A/B with repeats.

## W10 — Wire the logic suite into the gate *(NEW)*

41 tests, 5 ms, 8/8 mutations caught. Belongs in `run_tests.sh` in front of
every commit. Add the CM-1 alias regression (#12) with it.

**Effort:** trivial.

## W11 — Break up `run_case` *(NEW)*

3,666 lines, 181 `audit[...]` assignments, 14 phases. The least reviewable
surface in the codebase and the only section I could cover structurally rather
than by reading. Extracting phases changes no behaviour.

Also delete the 213 dead lines (#15) here — including the dead budget planner
whose docstring reads as current policy.

**Effort:** large. **Do last**, and only with the gate green.

---

## Order, and why

**W1 → W2 → W3 → W4 → W5 → W6 → W7 → W8 → W9 → W10 → W11**

W1 first because it is the only live-observed defect. W2 next because it closes
the highest-severity class and half of it is already staged. **W3 third and not
later** — every fix after it is easier to prove once the corpus can tell a
configured floor from 80%.

W10 is trivial and could be done at any point; it is listed late only because it
protects the work rather than producing it.

Nothing is applied. The sweep is still importing the release tree.
