# Cricut Chat skeleton retention — root cause and measurement

**The symptom.** Cricut Chat was the only measured quality gap in the RC9.2.1
evidence: the best before-break skeleton found was 187 target intervals, but the
one carried into the winning after-break pair was 172. A loss of 15, against a
configured `max_final_before_target_loss` of 6, which is why Gate 4 sat at WARN.

**The hypothesis under test.** Either the strongest skeleton genuinely had no
production break solution (structural), or Stage 2 never got far enough to find
one (budget).

**The method.** Re-run the identical input and seed at 2,700 s instead of 900 s.
Nothing else changed.

| Metric | 900 s | 2,700 s | |
|---|---|---|---|
| Stage-1 profiles attempted | 1 | **3** | |
| `global_best_before_target` | 187 | **196** | better skeleton found |
| `before_target` (selected) | 172 | **196** | |
| **Retention loss** | **15** | **0** | the gap closes completely |
| `before_floor` | 216 | **234** | |
| `quality_benchmark_status` | WARN | **PASS** | |
| Gate 4 | **FAIL** (retention −15) | PASS | |
| `target_losses_from_breaks` | 8 | **38** | |
| `after_target` | **164** | 158 | |
| Gate 5 | PASS | **FAIL** (38/242 = 15.7%) | |

**Root cause: budget, not structure.** At 900 s the engine explores one of its
fifteen skeleton profiles (see A28 in `CODE_AUDIT.md`); at 2,700 s it explores
three, finds a materially better skeleton, and carries it through with **zero**
retention loss. The retention defect is not an engine defect.

**But this is not a clean win, and it should not be reported as one.** The
stronger skeleton is harder to place breaks into. Break placement cost 38 target
intervals instead of 8, so the metric that actually ships — `after_target` on
`BEST_FINAL_AFTER_BREAKS` — went **164 → 158**. Gate 4 passed and Gate 5 failed.
The failure moved; it did not disappear.

**What that implies.** Stage 1 optimises before-break coverage without regard to
how breakable the resulting skeleton is, and the selector's retention penalty
(`max_final_before_target_loss`) measures what was lost, not what a candidate
will cost at break time. Under a longer budget the two stages pull against each
other.

**Deliberately not fixed here.** Making Stage-1 selection breakability-aware is a
change to release selection policy. It cannot be validated without many
multi-hour runs across the scenario set, and guessing at it would be exactly the
kind of speculative retune this audit has avoided. It is recorded as the finding
it is, with the numbers that establish it.

**What to do with this.** Every published RC9.2.1 quality number so far comes
from a 900 s run against a DEEP design budget of 14,400 s. The scenario set needs
re-running at the design budget before any of these figures — including the
Cricut Voice comparison against RC9.1 — is treated as a property of the engine.
