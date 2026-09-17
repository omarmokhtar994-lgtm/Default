# Why AE_IT_B2B's Stage-1 skeleton dropped

`before_target` 83 -> 78 and `before_floor` 93 -> 91 against the authors'
recorded baseline. This is the investigation.

## It is not the 45s slice change. It is my own sweep's reserve flags.

The Stage-1 phase allocation was cut almost exactly in half:

    phase                     NEW      BASE     delta
    stage1_search             824      1620      -796
    joint_refinement          734       438      +296
    break_search             1138       904      +234
    coordinated_repair        205       122       +83
    safe_incumbent            146        87       +59
    post_break_repair         117        70       +47
    target_lock_recovery      117        70       +47
    conflict_refinement        73        43       +30
    preflight / finalization  246       246        +0
    ------------------------------------------------
    TOTAL                    3600      3600        +0

Stage 1 lost 796 seconds and every other phase gained, summing to exactly
+796. The budget did not shrink; it was moved.

**Why it moved.** The authors' own runner
(`runners/run_real_schedules_quick.py`, line 436) builds its command from:

    --input --output-root --schedule-id --mode QUICK
    --num-workers --overwrite --stage FULL_SCHEDULE --time-limit

and nothing else. No reserve flags. It runs on engine defaults.

My sweep driver passed roughly 25 additional flags, including
`--joint-refinement-reserve-sec 900`, `--coordinated-repair-reserve-sec 300`,
and four separate 180-second reserves. Those reserves are taken off the top,
and Stage 1 is what is left. `run_identity.parameters_sha256` differs between
the two runs, which is the engine telling us the same thing.

Downstream, that is the whole observed effect:

                                  NEW            BASE
    deterministic_target_baseline  74.08s        180.01s
    STAGE1_PORTFOLIO window          337s           928s
    profiles funded                6 at 45s       3 at 240s
    profiles actually attempted    7 of 15        3 of 15
    before_target                       78             83

## The budget cut was uniform. The damage was not.

Every case lost the identical 796 seconds:

    case            NEW s1  BASE s1   delta   before_target n(base)
    AE_AR_B2B          824     1620    -796   168 (167)   +1
    AE_AR_Choice       824     1620    -796   141 (139)   +2
    AE_FR_B2B          824     1620    -796   112 (112)   +0
    AE_FR_Choice       824     1620    -796   112 (112)   +0
    AE_IT_B2B          824     1620    -796    78 ( 83)   -5

Four cases absorbed the cut; one converted it into a worse skeleton.

- `AE_FR_B2B` and `AE_FR_Choice` sit at 112 of 112 active intervals. They are
  saturated -- no amount of Stage-1 time can improve them.
- `AE_AR_B2B` and `AE_AR_Choice` improved slightly, so 7 shallow probes beat
  3 deep ones there.
- `AE_IT_B2B` is the only case where Stage-1 search time actually **binds**,
  and it is also the only CAPACITY_SHORT case among the five (short by 28
  hours, ceiling ~95%). Its skeleton problem is the hardest in the corpus, and
  it is the one case that genuinely needed the deeper slices.

## What this says about B-3 itself

The 45s slice was chosen to make a Stage-1 budget go further -- more profiles,
each shallower. On four of five cases it did exactly that. On the hardest case
it did not: seven 45-second probes produced a worse skeleton than three
240-second ones.

That is a real and actionable result about the slice constant, independent of
the flag confound. A fixed slice floor trades depth for breadth at a ratio that
is right for easy skeletons and wrong for hard ones. The obvious follow-up is
whether the slice should adapt to problem difficulty -- capacity headroom is
already computed at startup and would be a usable signal -- rather than being
one constant for every workbook.

## The correction this forces

**The sweep-vs-baseline comparison is confounded and its deltas are not
attributable to the code change.** Every number I reported as a delta against
the authors' baseline mixes two independent variables:

    engine code   f5f99789 (B-3 slice + A34/A35/A37 + others) vs 0e6f6435
    parameters    ~25 explicit flags                          vs engine defaults

So the headline I gave -- "measurable net after_target +6, after_floor +1" --
is the combined effect of code **and** parameters, not evidence for the code.
I should have compared `parameters_sha256` before treating that run as an A/B.
The engine records that field precisely so this mistake is catchable, and I
did not look at it.

## What is still sound

The **post-apply sweep now running is a clean A/B.** Its driver differs from
the pre-apply driver by one line (the output directory), and the run identities
confirm it:

    input_sha256        SAME
    parameters_sha256   SAME      <- the thing that was wrong before
    seed_sha256         SAME
    engine_sha256       DIFF      <- the only intended variable
    contract_sha256     DIFF      <- expected, see below

So pre-apply vs post-apply isolates the applied stack correctly, and remains
valid for task #48.

`contract_sha256` changes because W1 adds two fields to the
`whole_week_balance` contract block, `floor_loss_gate_mode` and
`maximum_floor_losses_from_breaks`. A new contract field must change the hash
or resume identity would be wrong, so this is correct behaviour rather than
drift. Verified by diffing the canonical snapshot: 40 keys before, 40 after,
none added or removed at top level, exactly one block changed.

B-12's recorded claim of "0 of 15 contract hashes change" was about B-12 in
isolation and is unaffected.

## Consequence for the record

To get a defensible statement about B-3 and the rest of the code change
against the authors' baseline, the baseline arm has to be re-run with the same
flags as the treatment arm -- or, more cheaply, the treatment arm re-run with
the authors' flags, which is one line in the driver. Until one of those exists,
the only honest claim is that the code change has not been measured against the
recorded baseline.
