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
