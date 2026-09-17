# Is the logic correct, and where is the room for improvement?

Two questions, answered separately because they have different answers.

---

## Part 1 — is the logic correct?

### What I verified positively, by measurement

| area | evidence |
|---|---|
| Stage-1 objective | genuine weighted sum, **343/343 terms decisive** across 17 profiles |
| Stage-2 break objective | **152/152 terms decisive** across 8 modes |
| minimum-exception proof | `exception_penalty` provably dominates every other term in diagnostic mode |
| break-pattern legality | every generated pattern obeys margin, order and minimum gap |
| unbreakable shift durations | caught per-duration as a contract failure before any solve |
| metric arithmetic | every division guarded; **39 before/after pairs, 0 asymmetries** |
| checkpoint / resume identity | `run_id` covers input, contract, engine, seed, parameters, git; writes atomic |
| budget allocation | phase sum **equals** the total in every configuration tested |
| polish → validate ordering | polisher runs first; no value the validator recomputes is altered |
| gate semantics | a disabled gate reports `NOT_ENFORCED`, never `PASS` |
| CLI defaults | 72 flags vs 117 fields — no contradiction |
| dominance relation | irreflexive and antisymmetric |
| 8 deliberate mutations | all caught by the logic suite |

**The core equations are sound.** Coverage arithmetic, the two objectives, the
break model, budget allocation and checkpoint identity all hold up under direct
measurement. Where the engine documents a design decision, the documentation
was right and my assumption was wrong three times out of three.

### What is wrong

17 open register entries. Their shape matters more than their count: **almost
none are wrong equations.** They are wrong *plumbing* — a fallback that returns
a different quantity, a default looser than the declared one, a parser with no
error state, a metric that nothing gates. The one live defect (S11-1) is not a
miscalculation; `floor_losses_from_breaks` is computed perfectly correctly and
then nothing looks at it.

That is the honest summary: **the maths is right, the wiring around it is not.**

### What I did NOT verify — the limit of the claim

1. **I did not prove the CP-SAT model encodes the business rules.** I read the
   constraint construction and checked specific invariants. I did not establish
   equivalence between the written rule set and the model. The independent
   validator does that at runtime, and it passes on real artifacts — but that
   is **class-B evidence only**, and since it parses the same contract it
   cannot speak to classes A, C or D.

2. **The corpus cannot exercise large parts of the contract.** Measured across
   the 15 workbooks:

| dimension | distribution | |
|---|---|---|
| nesting groups | `{False: 15}` | **never exercised** |
| multiple shift durations (11H/3OFF) | `{False: 15}` | **never exercised** |
| fixed requests enabled | `{False: 14, True: 1}` | barely |
| **floor ratio** | `{0.80: 14, 0.85: 1}` | **14/15 identical** |
| target ratio | `{1.0: 8, 0.9: 6, 0.85: 1}` | varied |
| interval minutes | `{60: 9, 30: 6}` | varied |
| hard floor | `{False: 12, True: 3}` | varied |
| language rules | `{True: 12, False: 3}` | varied |

**4 of 12 contract dimensions have effectively no variation.**

This is not incidental — it *explains* several findings:

* The 10 `*_floor → *_80` fallbacks are invisible because on 14 of 15
  workbooks the configured floor **is** 80%. The corpus literally cannot tell
  the two apart.
* S6-1 (silent nesting UNSAT) and S6-2 (unreachable nesting check) both live
  in the one subsystem that 0 of 15 workbooks touch.
* Every workbook has a **single shift duration**, so the 11H/3OFF path, and
  `rest_compatible` across differing durations, are untested — and `use11` is
  one of the ten flags that fail open on a typo.

So: the logic is correct **in the region the corpus exercises**, and that
region is narrower than the contract the engine advertises.

---

## Part 2 — room for improvement

Improvements, not defects: none of these is wrong today. Each removes a
*class* of the defects above rather than an instance, and each is tied to
something measured.

### 1. One source of truth for every default
`ParsedInput` declares 117 defaults; 90 call sites declare a second, looser
answer. Delete the call-site defaults and read the attribute. Removes RC-B
entirely — as a class, not 90 fixes — and makes the release gate mean what the
contract says. **Contained: zero instances exist in any satellite module.**

### 2. Derive the orderings from one definition
Eleven candidate orderings exist over the same candidates, and at least one
pair is provably inconsistent (S9-2). If the dominance dimensions were
*generated* as a subset of the quality tuple's terms, S9-2 could not recur by
construction.

### 3. A contract vocabulary layer
`yes()`, `tri_state()`, `preference_kind()` and the name matchers all map
unrecognised input to a valid value. One helper that maps text → domain value
or raises a `HARD_` code would close C-2, C-3 and B-11 **as one class**. The
engine already has the pattern — B-7's `strict_bool` — used at 2 of 12 sites.

### 4. Declare what the validator models
The validator models coverage, breaks and week boundaries; it does not model
language reserve, skill allocation or employee quality at all. A manifest of
modelled subsystems, plus a rule that an unmodelled metric may not gate a
release, converts B-9's class-D gap from invisible to declared. That is a
scoping decision for the authors, not a patch.

### 5. Enforce the phase minimums instead of reporting them
`PHASE_MINIMUM_VIABLE_SECONDS` exists and is advisory. Skip a phase allocated
below its own floor and give the seconds to one that can use them.

### 6. Widen the fixture matrix — the highest-value item here
The measurement above says exactly which fixtures are missing:
a workbook with **floor ≠ 0.80** (would expose all 10 `*_floor → *_80`
fallbacks), one with a **nesting group** (would expose S6-1 immediately), one
with **multiple shift durations**, and one with **fixed requests enabled**.
Four workbooks would turn four latent findings into failing tests.

### 7. Break up `run_case`
3,666 lines in one function, 181 `audit[...]` assignments, 14 phases. It is the
least reviewable surface in the codebase and the one place I could only cover
structurally. Extracting phases would not change behaviour and would make the
next review tractable.

### 8. Wire the logic suite into the gate
41 tests, 5 ms, 8/8 mutations caught. It belongs in `run_tests.sh` in front of
every commit.

---

## The one-line answer

The equations are right; the wiring around them is not, and the corpus is too
uniform to have proved either way on four of twelve contract dimensions.
