# Phase BO change 2: stopping channel planning early. Not adopted (2026-11-12)

Idea: stop a channel-plan solve once no better plan has appeared for a few seconds, so small teams wait less than the full limit.
Checked first, before writing a rule (`channel_improvement_times.py`, exploratory, in-process solve with a callback; base_16 and large_30, Mon and Tue):

| Solve | Limit | Last better plan found at | Within 1% of the final objective at |
|---|---|---|---|
| base_16 day 1, channels | 12 s | 10.5 s | 7.6 s |
| base_16 day 1, moving breaks | 10 s | 10.0 s | 10.0 s |
| base_16 day 2, channels | 12 s | 9.2 s | 5.6 s |
| base_16 day 2, moving breaks | 10 s | 9.9 s | 9.6 s |
| large_30 day 1, channels | 12 s | 11.5 s | 6.4 s |
| large_30 day 1, moving breaks | 10 s | 9.6 s | 8.8 s |
| large_30 day 2, channels | 12 s | 8.8 s | 7.0 s |
| large_30 day 2, moving breaks | 10 s | 9.9 s | 9.9 s |

Every solve was still finding better plans in its last seconds (13 to 36 improving plans each, none proven best). There is no quiet tail to cut: a
stop after a few seconds without a better plan would rarely fire, and a shorter limit would give worse plans (the owner already chose more time, 25 s,
for placing breaks in Phase BL). So nothing is changed and no A/B was run. What would make it faster is a smaller model (for example counting
interchangeable people instead of assigning each one), which is a modelling project with its own A/B, not a setting.
