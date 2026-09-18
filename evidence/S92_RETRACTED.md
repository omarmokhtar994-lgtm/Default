# S9-2 retracted: the frontier overriding the ordering is the design, not the defect

Earlier today I corrected S9-2 from "affects alternatives" to "decides a shipped
artifact". That correction was right. The conclusion I drew from it -- that the
disagreement is a defect needing a fix -- was wrong.

## What I built, and what it broke

The fix required a frontier candidate to be no worse than the anchor on the full
quality tuple before it could ship. The engine's own selfcheck rejected it:

    selector_regressions/gdi_real28   ctl: safer_143_154_168  ->  s92: strict_144_153_167
    selector_regressions/nmg12        ctl: max_target_68_128_159 -> s92: engine_68_127_161
    status                            PASS -> FAIL

Both regressions exist to pin that the selector CAN choose a candidate trading a
little target for more floor. `safer_143_154_168` gives up one target interval
for one floor interval against `strict_144_153_167`. My guard rejected it and
fell back to the anchor, which is exactly the behaviour those tests were written
to prevent.

## Why the guard was incoherent

`recommendation_anchor` comes from `target_priority_tradeoff_select`. It IS the
maximum of the target-priority ordering, by construction. So "not worse than the
anchor on the full ordering" can only ever be satisfied by a tie, and the filter
reduces `safer_options` to approximately nothing. I did not build a narrower
guard; I disabled the mechanism.

## What S9-2 actually is

The lexicographic order is target-priority. The dominance frontier exists
precisely to surface candidates that are better on safety dimensions that
target-priority under-weights, and `genuinely_safer_than_strict` is the guard on
that trade -- it already requires no regression on hard floor gaps, severe floor
gaps, consecutive floor gaps and floor deficit sum.

So dominance and the lexicographic order disagreeing is not a bug. It is the
whole point. A mechanism designed to override an ordering will, correctly,
disagree with it.

The open question S9-2 could have asked is whether those four safety dimensions
are the right guard -- but that is a scheduling-policy question about which
trades are acceptable, not an engineering defect, and it belongs with the
authors alongside the floor-loss cap.

Closed as not-a-defect. Applier discarded.

## Fourth register description to prove wrong today

    S9-1   "add the missing prefix"    -- no prefixed variant exists
    B-10   "a CAP used as a FLOOR"     -- correctly a floor; my misreading
    S9-2   "not the release pick"      -- it does decide a shipped artifact...
    S9-2   "...therefore a defect"     -- but the override is the design

S9-2 took two corrections in opposite directions in one evening. The first was
right and the second reversed the conclusion I drew from it. The lesson is the
same each time: the register's summary is a hypothesis, and the source and the
engine's own regression suite are the evidence.
