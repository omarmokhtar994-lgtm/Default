# Phase BR: rules for changing the forecast (pre-registered 2026-11-18, before any run)

Owner, 2026-11-18: "Develop current forecast first to be perfect then add capacity plan." Each change below is a behaviour change, so it ships
only if it meets the rule written here before its first run. The harness is `accuracy.py` (made-up histories with a known truth, fixed seeds).

## R1: the interval shape
**Today (`M`).** Each weekday's shape is the per-interval median of day shares over the chosen weeks, renormalised (`forecast.build_profile`).

**Candidates.** `A`: the per-interval mean of day shares. `P`: pooled (each interval's contacts summed over the chosen weeks, over the weekday's
total over the same weeks).

**Histories.** 30-minute intervals, 6 chosen weeks, Poisson counts around a known weekday shape (a two-peak day open 08:00 to 24:00; a lighter
weekend), at four week volumes (1,500; 7,000; 35,000; 200,000), and a fifth, "drift", at 7,000 where the evening peak grows 2 % a week.

**Score.** Interval WAPE (sum of absolute differences over the sum) of the forecast week against the known expected counts of the forecast week,
given the true week total, so only the shape is scored.

**Rule.** Adopt a candidate only if, on two seed sets (1 to 5 and 101 to 105), its WAPE is lower than `M`'s on at least 4 of the 5 histories and
never more than 0.5 points higher on any. If both pass, the one with the lower mean WAPE. Otherwise `M` stays.

## R2: handle time by interval
**Today.** One handle time for the whole week (volume-weighted over the chosen weeks, `VolumeBook._aht`).

**Candidate `H`.** Per weekday and interval, the volume-weighted handle time of the chosen weeks, pulled towards the week's handle time where little
volume stands behind it: weight n / (n + 20), n = contacts behind that interval over the chosen weeks.

**Histories.** The four volume levels above with a true handle time (average 300 s) that runs 25 % above the day's average from 20:00 and 15 %
below it from 08:00 to 11:00 (noise: each interval's recorded handle time is the mean of its contacts' times, each exponential around the true
mean); and each level again with a flat true handle time (the control).

**Score.** People needed per interval (Erlang C, 80 % in 20 s, occupancy cap 88 %) from the forecast (true week total, today's shape `M`, the
handle time under test) against the people needed with the true expected counts and the true handle time: sum of absolute differences over the sum
of the true needs.

**Rule.** Adopt `H` only if, on both seed sets, its error is lower on all four varying histories and no more than 1 point higher on any flat
control. Otherwise the single handle time stays.

## Results (run 2026-11-18, `accuracy.py 1` and `accuracy.py 101`; outputs `accuracy_run_1to5.txt`, `accuracy_run_101to105.txt`)

### R1
| history | M today (1-5 / 101-105) | A mean | P pooled |
|---|---|---|---|
| 1,500 | 14.66 / 13.92 | 12.60 / 12.22 | 12.56 / 12.26 |
| 7,000 | 6.40 / 6.23 | 5.55 / 5.41 | 5.57 / 5.40 |
| 35,000 | 2.80 / 2.68 | 2.41 / 2.38 | 2.42 / 2.38 |
| 200,000 | 1.20 / 1.14 | 1.05 / 1.04 | 1.05 / 1.04 |
| drift 7,000 | 7.10 / 7.24 | 6.16 / 6.40 | 6.17 / 6.37 |

Both candidates are lower than `M` on 5 of 5 histories on both seed sets (never higher). **The rule is met by both.** Tie-break, the mean WAPE over
the five histories and both seed sets: `P` 5.522, `A` 5.523, `M` 6.336. **`P` ships**: each weekday's interval shape is its contacts summed over the
chosen weeks, over that weekday's total. Interval error falls by about an eighth (14.7 to 12.6 % at 1,500 contacts a week, 6.4 to 5.6 % at 7,000).
Why: the median of each interval's share over six days is biased low where counts are small and skewed, and renormalising moves that bias onto the
busy intervals. The day mix (`day_shares`) is unchanged (still the median), as no rule tested it.

### R2
| history | one handle time (1-5 / 101-105) | H by interval |
|---|---|---|
| 1,500 varying | 11.82 / 12.66 | 11.91 / 12.18 |
| 7,000 varying | 8.87 / 8.78 | 6.25 / 6.23 |
| 35,000 varying | 8.50 / 8.31 | 3.38 / 3.40 |
| 200,000 varying | 7.89 / 7.94 | 1.53 / 1.53 |
| 1,500 flat | 9.68 / 10.41 | 11.23 / 11.35 |
| 7,000 flat | 4.42 / 4.86 | 6.05 / 6.45 |
| 35,000 flat | 2.49 / 2.55 | 3.40 / 3.61 |
| 200,000 flat | 1.17 / 1.17 | 1.51 / 1.53 |

`H` is not lower at 1,500 contacts a week on seeds 1 to 5, and on flat handle times it is up to 1.63 points worse (more than the 1 point allowed).
**The rule is not met: the single handle time stays.** What the run does show: where handle time really changes over the day and volume is
7,000 a week or more, planning by interval cuts the staffing error from about 8.5 % to between 1.5 and 6.3 %. A rule that first tests whether the
program's handle time really varies by interval could pass; it is not run in this phase (it would be a new rule, written before its run).
