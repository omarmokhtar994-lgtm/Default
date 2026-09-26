# Stage-2 -> Stage-1 feedback probes on SYNTH_M2 (saved pool M2_NEW_9000, anchor after_target 111, before 117; 1 worker)

## m2_damaged.out
M2_NEW_9000: pool 23; best after_target 111 floor 117 before 117 (target90_restore_champion/fully_compliant_target_priority)
{'round': 1, 'variant': 'LOCAL-8', 'load_intervals': 6, 'stage1': 'FEASIBLE', 't1': 300.0, 'before_target': 117, 'stage2': 'FEASIBLE', 'after_stage2': 98, 'after_dnbs': 99, 'floor': 117, 'cls': 'compliant', 'accepted': False, 'worse': ['after_90', 'after_100', 'after_severe_overage_count', 'whole_week_imbalance_violation_count']}

## m2_carry.out
M2_NEW_9000: pool 23; best after_target 111 floor 117 before 117 (target90_restore_champion/fully_compliant_target_priority)
{'round': 1, 'variant': 'LOCAL-8', 'load_intervals': 6, 'stage1': 'FEASIBLE', 't1': 300.0, 'before_target': 117, 'stage2': 'CARRIED', 'after_stage2': 83, 'after_dnbs': 85, 'floor': 117, 'cls': 'compliant', 'accepted': False, 'worse': ['after_90', 'after_100', 'break_concurrency_violation_count', 'after_severe_overage_count']}

## load on all intervals (first run)
M2_NEW_9000: pool 23; best after_target 111 floor 117 before 117 (target90_restore_champion/fully_compliant_target_priority)
{'round': 1, 'variant': 'FULL', 'load_intervals': 105, 'stage1': 'FEASIBLE', 't1': 270.0, 'before_target': 117, 'stage2': 'FEASIBLE', 'after_stage2': 106, 'after_dnbs': 107, 'floor': 117, 'cls': 'compliant', 'accepted': False, 'worse': ['after_100', 'after_severe_overage_count', 'after_avoidable_overage_fte_sum', 'after_target']}
{'round': 1, 'variant': 'LOCAL-12', 'load_intervals': 105, 'stage1': 'FEASIBLE', 't1': 84.7, 'before_target': 117, 'stage2': 'FEASIBLE', 'after_stage2': 111, 'after_dnbs': 111, 'floor': 117, 'cls': 'compliant', 'accepted': False, 'worse': ['after_target']}
{'round': 1, 'variant': 'LOCAL-24', 'load_intervals': 105, 'stage1': 'FEASIBLE', 't1': 31.7, 'before_target': 117, 'stage2': 'FEASIBLE', 'after_stage2': 111, 'after_dnbs': 111, 'floor': 117, 'cls': 'compliant', 'accepted': False, 'worse': ['after_target']}
RESULT {"case": "M2_NEW_9000", "start_after_target": 111, "end_after_target": 111, "start_floor": 117, "end_floor": 117, "accepted": 0, "rounds": 1}
