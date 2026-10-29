# Phase BE: how the engine treats shift Preferences (owner, 2026-10-29: "it doesn't take it really into consideration even though there is availability")

Diagnostic only; nothing in the engine was changed. Scripts here; made-up "Agent A to L" data.

## What a Preference is in the engine
- OFF and Leave in Preference are hard when Hard OFF Preferences / Leave are Yes (honoured in the GDI week of 18 Oct: 13 of 13).
- A shift Preference is **soft** and exists **only in Stage 1** (`build_skeleton`, `profile["preference"] * distance * x`): a cost of 4 to 20 per quarter hour of start difference (one profile, `preference_neighborhood`, has 90). It penalises working a different shift; it does not reward working the asked one, and OFF costs nothing.
- `use_preferences` is read nowhere else. The joint model, the repair operators and the final candidate choice have no preference term. The per-employee minimum (`Employee Minimum Preference Satisfaction Ratio`, 0.50) is only a quality-gate check.

## Measured on a case where honouring costs nothing (`pref_free.py`)
12 associates, demand a staircase that two people per shift cover exactly, each asks for the shift the staircase needs anyway (60 requests; all 60 honoured is coverage-optimal).
- Stage 1, per profile, same coverage: `target90_restore_champion` 60 of 60; `quality_convergence` 50 of 60 (and 10 of 60 with the weight at 0); `floor_protected` 43 of 60 (worse coverage); `preference_neighborhood` 35 of 60 (worse coverage).
- The whole engine (`--time-limit 300`, 2 workers): best before breaks **60 of 60**; the final schedule **12 of 42 worked requested days (28 %)**. The preferences are lost after Stage 1, when other stages and the candidate choice work on coverage alone (`toy_leaderboard.csv`).

## Cause, in order of effect
1. After Stage 1, nothing carries the preference: the joint model and the repair operators change shifts for coverage with no preference term, and the final candidate is picked on coverage.
2. Inside Stage 1 the weight (4 to 20) is the same size as tie-breakers such as shift variety (20 to 35), so a preference wins only when everything else ties.
3. Different profiles honour different shares, and the profile that wins is chosen on coverage.
