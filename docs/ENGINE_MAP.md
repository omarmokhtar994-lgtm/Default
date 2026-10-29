# Engine map

Written by `tools/engine_map.py` from `engine/_tools/l632_universal_scheduler.py`; do not edit by hand. `python3 tools/engine_map.py --check` fails when the engine has changed since this was written.

- File: `engine/_tools/l632_universal_scheduler.py`, sha256 `1162ab8773985a0746b718803e6e89520742cbb4095f3e44c198ed527c05462a`
- 26,634 lines; 363 functions, 12 classes

## 1. The stages of `run_case`

`run_case` is lines 21294 to 25237 (3,944 lines, 72 parameters). Its body is one `with` block (lines 21370 to 25237) of 470 statements in sequence. The outline below is read from what it calls, in order of first call; a function of 100 lines or more is a stage of its own.

| Order | First call at line | Function | Lines | Job |
|---|---|---|---|---|
| 1 | 21371 | `parse_input` | 805 | Input reading and contract |
| 2 | 21472 | `capacity_diagnostics` | 280 | Coverage, demand and capacity |
| 3 | 21473 | `coverage_split_capacity_report` | 160 | Coverage, demand and capacity |
| 4 | 21483 | `validate_input_contract` | 454 | Input reading and contract |
| 5 | 21551 | `calculate_metrics` | 916 | Metrics |
| 6 | 21560 | `validate_schedule` | 114 | Audit and self-check |
| 7 | 21588 | `load_validated_fallback_candidate` | 184 | Candidate selection |
| 8 | 21658 | `skeleton_profiles` | 192 | Skeleton search (stage 1) |
| 9 | 22096 | `run_shortfall_pass` | 133 | Search phases (`run_*`) |
| 10 | 22121 | `aggregate_pattern_mix_guidance` | 365 | Skeleton search (stage 1) |
| 11 | 22157 | `build_skeleton` | 926 | Skeleton search (stage 1) |
| 12 | 22622 | `break_capacity_headcount_requirement` | 116 | Breaks |
| 13 | 22808 | `run_qualified_language_break_certificate_repairs` | 134 | Search phases (`run_*`) |
| 14 | 22829 | `run_logic_based_break_cut_feedback` | 180 | Search phases (`run_*`) |
| 15 | 22948 | `language_break_overlap_repair_plan` | 190 | Languages |
| 16 | 23288 | `run_protected_target_champion_break_proof` | 100 | Search phases (`run_*`) |
| 17 | 23354 | `run_zero_exception_recovery_phase` | 182 | Search phases (`run_*`) |
| 18 | 23451 | `solve_breaks` | 671 | Breaks |
| 19 | 23756 | `run_rc8_best_before_break_recovery` | 115 | Search phases (`run_*`) |
| 20 | 23789 | `run_day_neighbourhood_break_search` | 197 | Search phases (`run_*`) |
| 21 | 23851 | `bootstrap_exception_anchors_for_joint` | 139 | Joint, repair and neighbourhood search |
| 22 | 23904 | `run_adaptive_decomposed_joint_optimizer` | 643 | Search phases (`run_*`) |
| 23 | 23959 | `run_break_load_feedback` | 111 | Search phases (`run_*`) |
| 24 | 23980 | `run_coordinated_shift_off_break_loop` | 267 | Search phases (`run_*`) |
| 25 | 24036 | `run_post_break_repair_phase` | 191 | Search phases (`run_*`) |
| 26 | 24060 | `run_target_lock_recovery_phase` | 110 | Search phases (`run_*`) |
| 27 | 24594 | `write_output_workbook` | 638 | Output and publishing |
| 28 | 24685 | `select_export_candidates` | 300 | Candidate selection |
| 29 | 24707 | `preference_swap_polish` | 111 | Preferences, OFF days and fixed requests |
| 30 | 24737 | `shift_consistency_polish` | 138 | Shifts and rest |

Blocks inside `run_case` of 70 lines or more, in order:

| Lines | Size | Starts with |
|---|---|---|
| 21786 to 21875 | 90 | `run_parameters = {` |
| 21939 to 22060 | 122 | `audit: Dict[str, Any] = {` |
| 22398 to 22492 | 95 | `for profile_index, profile in enumerate(profiles_to_run):` |
| 22500 to 22578 | 79 | `if skeleton_only and successful_skeletons and polish_deadline - time.time() >= 45:` |
| 22601 to 22725 | 125 | `if skeleton_only:` |
| 22853 to 22926 | 74 | `if blanket_global_reserve_enabled and operational_no_break_exception_cap(parsed) == 0:` |
| 22947 to 23033 | 87 | `for anchor_index, anchor in enumerate(skill_overlap_anchors):` |
| 23056 to 23129 | 74 | `for anchor_index, anchor in enumerate(repair_anchors[:3]):` |
| 23554 to 23720 | 167 | `for task_index, task in enumerate(tasks):` |
| 23872 to 23951 | 80 | `if joint_refinement and joint_search_pool and not completed_phases.get("joint_refinement_c` |
| 24079 to 24203 | 125 | `if not compliant and parsed.allow_no_break_exceptions and not completed_phases.get("except` |
| 24430 to 24683 | 254 | `if not candidates:` |
| 25061 to 25229 | 169 | `row = {` |

## 2. Functions by job

| Job | Functions | Lines |
|---|---|---|
| Run control and command line | 6 | 4,257 |
| Search phases (`run_*`) | 16 | 2,609 |
| Files, hashing and small utilities | 24 | 293 |
| Input reading and contract | 53 | 3,159 |
| Languages | 15 | 1,489 |
| Breaks | 35 | 2,135 |
| Preferences, OFF days and fixed requests | 11 | 470 |
| Shifts and rest | 20 | 350 |
| Metrics | 6 | 1,001 |
| Coverage, demand and capacity | 31 | 1,016 |
| Skeleton search (stage 1) | 25 | 1,807 |
| Joint, repair and neighbourhood search | 21 | 1,189 |
| Candidate selection | 23 | 1,196 |
| Output and publishing | 13 | 1,114 |
| Audit and self-check | 6 | 775 |
| Shift consistency polish | 5 | 255 |
| Tiers, exceptions and quality figures | 16 | 437 |
| Workbook styling | 4 | 70 |
| Time reserves and machine limits | 6 | 180 |
| Other helpers | 27 | 862 |

### Run control and command line

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `infeasibility_diagnosis_budget` | 21272 to 21281 | 10 | `run_case` |  | Seconds a no-schedule run may spend naming its cause. |
| `stage1_minimum_budget_seconds` | 21284 to 21291 | 8 | `run_case` |  | What a Stage-1 portfolio of ``portfolio_size`` profiles needs at the configured |
| `run_case` | 21294 to 25237 | 3944 | `main` |  |  |
| `build_arg_parser` | 25554 to 25665 | 112 | `main` |  |  |
| `cli_search_controls` | 26445 to 26463 | 19 | `main`, `run_case` |  | Translate the options the caller typed into engine parameter values. |
| `main` | 26466 to 26629 | 164 | `_build_business_outcome_core` |  |  |

### Search phases (`run_*`)

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `run_shortfall_pass` | 8646 to 8778 | 133 | `run_case` |  | Audit F-06: the best schedule that meets every PERSON rule, with every |
| `run_constraint_isolation` | 8781 to 8807 | 27 | `run_case` |  |  |
| `run_conflict_refinement` | 8810 to 8872 | 63 | `run_case` |  | Return a bounded family-level infeasibility core. |
| `run_qualified_language_break_certificate_repairs` | 9525 to 9658 | 134 | `run_case` |  | Repair language single-points-of-failure with complete legal break patterns. |
| `run_protected_floor_break_guard` | 12514 to 12581 | 68 | `run_case` |  | Spend protected Stage-2 time on floor-shaped skeletons before repair search. |
| `run_protected_target_champion_break_proof` | 12633 to 12732 | 100 | `run_case` |  | Try to convert the highest target skeletons to legal break schedules. |
| `run_adaptive_decomposed_joint_optimizer` | 17664 to 18306 | 643 | `run_cap_feasible_target_recovery_phase`, `run_case` |  | RC4.4 adaptive decomposed joint optimizer. |
| `run_break_load_feedback` | 18330 to 18440 | 111 | `run_case` |  | Feed the break load Stage 2 left on under-target intervals back to Stage 1. |
| `run_coordinated_shift_off_break_loop` | 18443 to 18709 | 267 | `run_case` |  | Transaction-safe repair across clean, near-feasible and exception pools. |
| `run_logic_based_break_cut_feedback` | 18795 to 18974 | 180 | `run_case` |  | Feed break evidence back through progressive, isolatable master cuts. |
| `run_zero_exception_recovery_phase` | 19164 to 19345 | 182 | `run_case` |  | Search beyond positive diagnostic minima and recover within the workbook exception cap. |
| `run_day_neighbourhood_break_search` | 19531 to 19727 | 197 | `run_break_load_feedback`, `run_case` |  | Improve the best compliant candidates' breaks one day at a time. |
| `run_post_break_repair_phase` | 20397 to 20587 | 191 | `run_case` |  | Late repair for compliant, near-feasible, and exception candidates. |
| `run_cap_feasible_target_recovery_phase` | 20680 to 20767 | 88 | `run_case` |  | Recover target KPIs around a proven within-cap language-break anchor. |
| `run_rc8_best_before_break_recovery` | 20799 to 20913 | 115 | `run_case` |  | Give the current-run BEST BEFORE skeleton a dedicated full-width break lane. |
| `run_target_lock_recovery_phase` | 20916 to 21025 | 110 | `run_case` |  | Maximize target, lock it, then recover floor quality for the active pool. |

### Files, hashing and small utilities

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `norm` | 260 to 263 | 4 | `_alias_key`, `_apply_preference_mapping`, `_authored_language_windows`, `_consistency_greedy_swaps` +66 | 1 file |  |
| `safe_name` | 266 to 267 | 2 | `discover_validated_fallback_candidates`, `run_case`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `normalized_output_prefix` | 270 to 280 | 11 | `case_identity_warnings`, `cleanup_stale_run_outputs`, `run_case` |  |  |
| `to_float` | 322 to 330 | 9 | `_optional_instruction_minutes`, `load_validated_fallback_candidate`, `parse_input` |  |  |
| `strict_float` | 333 to 361 | 29 | `_detect_interval_minutes`, `_parse_break_segments`, `_parse_break_sets_by_shift_length`, `_parse_coverage_split` +4 |  | Parse a numeric workbook value without converting bad text to zero. |
| `yes` | 364 to 368 | 5 | `_parse_duration_set`, `_parse_fixed_nesting`, `_parse_language_rules`, `blank_requirement_mode` +2 |  |  |
| `tri_state` | 371 to 377 | 7 | `parse_input` |  |  |
| `minute_in_inclusive_window` | 393 to 399 | 7 | `add_half_hour_twins`, `shift_start_contract_allows` |  |  |
| `minute_of_day` | 423 to 442 | 20 | `_detect_interval_minutes`, `_discover_requirement_sheet`, `_parse_coverage_split`, `_parse_language_rules` +5 |  |  |
| `ceil_units` | 510 to 511 | 2 | `build_skeleton`, `coverage_hit_threshold_units`, `critical_exception_cells`, `global_zero_exception_break_reserve_requirements` +1 |  |  |
| `ensure_parent` | 567 to 568 | 2 | `atomic_save_workbook`, `run_case`, `write_csv`, `write_json` +1 |  |  |
| `git_repository_identity` | 571 to 601 | 31 | `run_case` |  | Return portable Git provenance without making Git a runtime dependency. |
| `write_json` | 604 to 608 | 5 | `main`, `publish_business_outcome`, `publish_recovery_checkpoint`, `record_unexpected_run_failure` +3 |  |  |
| `write_csv` | 611 to 622 | 12 | `_augment_summary_with_business_outcome`, `record_unexpected_run_failure`, `run_case` |  | Atomically write a CSV so stale/partial leaderboard files are never published. |
| `sha256_file` | 625 to 630 | 6 | `benchmark_provenance`, `run_case`, `verify_xlsx` |  |  |
| `canonical_hash` | 633 to 635 | 3 | `benchmark_provenance`, `candidate_lineage_id`, `capacity_diagnostics`, `logic_based_break_feasibility_cut_plan` +3 | 1 file |  |
| `verify_xlsx` | 638 to 663 | 26 | `atomic_save_workbook`, `run_case` |  | Reopen the XLSX as ZIP and workbook; return a release-verification record. |
| `atomic_save_workbook` | 666 to 676 | 11 | `write_before_break_workbook`, `write_output_workbook` |  | Save to a sibling temporary file, verify, then atomically publish. |
| `normalize_language_window_mode` | 3320 to 3348 | 29 | `parse_input`, `run_case` |  | How the Language Setup Coverage Start/End bounds working hours. |
| `normalize_language_window_shift_rule` | 3357 to 3365 | 9 | `parse_input` |  | Phase AQ (owner, 2026-10-21): what a Language Working Window limits. START is the default and what t |
| `normalize_run_stage` | 3554 to 3562 | 9 | `parse_input` |  | Map a workbook Run Stage cell to a canonical stage, or None if unset. |
| `normalize_run_depth` | 3565 to 3569 | 5 | `parse_input` |  | Map a workbook Run Depth cell to a canonical depth, or None if unset. |
| `import_cp_sat` | 5089 to 5094 | 6 | `_consistency_swap_model`, `build_skeleton`, `dnbs_day_neighbourhood_model`, `run_day_neighbourhood_break_search` +3 | 2 files |  |
| `configure_solver_limits` | 5149 to 5191 | 43 | `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Apply the two native CP-SAT limits the engine otherwise leaves at default. |

### Input reading and contract

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `parse_time_window` | 380 to 390 | 11 | `parse_input` |  |  |
| `blank_requirement_mode` | 412 to 420 | 9 | `parse_input` |  |  |
| `_sheet_by_alias` | 1230 to 1235 | 6 | `_apply_preference_mapping`, `_discover_requirement_sheet`, `_discover_setup_sheet`, `_fallback_no_break_evidence` +11 | 1 file |  |
| `_discover_setup_sheet` | 1238 to 1255 | 18 | `synchronize_contract_metadata` |  | Find an optional presentation/setup sheet without program-name aliases. |
| `_instruction_pairs` | 1265 to 1290 | 26 | `_instruction_duplicates`, `_instruction_map` |  | (row, label, value) pairs on an Instructions-style sheet. |
| `_instruction_map` | 1293 to 1297 | 5 | `parse_input` | 1 file |  |
| `_instruction_duplicates` | 1300 to 1310 | 11 | `parse_input` |  | Labels given more than once on one sheet with DIFFERENT values. |
| `_parse_search_controls` | 1405 to 1463 | 59 | `parse_input` |  | Read the search controls a workbook actually states, and only those. |
| `_instruction_get` | 1466 to 1470 | 5 | `_detect_interval_minutes`, `_discover_requirement_sheet`, `_optional_instruction_minutes`, `_parse_break_segments` +6 |  |  |
| `_terms_in_distinct_cells` | 1548 to 1566 | 19 | `_find_header_row` |  | True when every term can be matched to a DIFFERENT cell of the row. |
| `_find_header_row` | 1569 to 1620 | 52 | `_apply_preference_mapping`, `_discover_requirement_sheet`, `_fallback_no_break_evidence`, `_parse_coverage_split` +6 |  | Locate the header row of a sheet by the terms it must carry. |
| `_is_day_header` | 1623 to 1634 | 12 | `_day_columns` |  | True when a normalized header names this weekday and nothing else. |
| `_day_columns` | 1637 to 1685 | 49 | `_discover_requirement_sheet`, `_fallback_no_break_evidence`, `_find_header_row`, `_parse_fixed_nesting` +4 |  | Bind each weekday to its column by header text. |
| `_parse_roster` | 1688 to 1767 | 80 | `load_seed_skeleton`, `parse_input` |  |  |
| `_parse_departed_acknowledgements` | 1770 to 1782 | 13 | `parse_input` |  | Names the scheduler has explicitly declared as no longer on the roster. |
| `_report_unmatched_name` | 1785 to 1828 | 44 | `_parse_fixed_nesting`, `_parse_preferences` |  | Report an unmatched row, hard unless it asserts nothing or was acknowledged. |
| `_sheet_has_named_rows` | 1831 to 1835 | 5 | `_parse_fixed_nesting`, `_parse_preferences` |  | True when any row under the header carries a name, i.e. the sheet asserts something. |
| `_report_missing_day_columns` | 1838 to 1843 | 6 | `_parse_fixed_nesting`, `_parse_preferences`, `parse_input` |  |  |
| `_parse_preferences` | 1846 to 1938 | 93 | `parse_input` |  |  |
| `_parse_fixed_nesting` | 1992 to 2060 | 69 | `parse_input` |  |  |
| `_parse_duration_set` | 2063 to 2089 | 27 | `parse_input` |  |  |
| `parse_11h_associate_limit` | 2095 to 2111 | 17 | `parse_input` |  | Phase H: blank = no limit; a whole number >= 1 = at most that many |
| `add_11h_associate_limit` | 2114 to 2121 | 8 | `build_skeleton`, `solve_joint_shift_off_language_break_refinement` |  | Phase H: at most "Max 11H/3OFF Associates" associates work the 11H/3OFF |
| `forced_long_mode_associates` | 2124 to 2138 | 15 | `validate_input_contract` |  | Associates who can only work the 11H/3OFF pattern: every legal shift is |
| `long_mode_summary_rows` | 2141 to 2149 | 9 | `write_output_workbook` |  | Production Summary rows for the 11H/3OFF pattern; none when it is off. |
| `add_half_hour_twins` | 2152 to 2173 | 22 | `parse_input` |  | Phase F: every on-the-hour shift gets a twin starting 30 minutes later, |
| `half_hour_fallback_usage` | 2176 to 2183 | 8 | `half_hour_summary_rows` |  | Phase F output marking: the shift-days of a week that use a :30 twin. |
| `half_hour_summary_rows` | 2186 to 2197 | 12 | `write_output_workbook` |  | Production Summary rows marking :30 twins; none when the switch is off, |
| `_parse_shifts` | 2200 to 2248 | 49 | `parse_input` |  |  |
| `_discover_requirement_sheet` | 2251 to 2274 | 24 | `_parse_requirement_table` | 1 file |  |
| `_detect_interval_minutes` | 2280 to 2317 | 38 | `_parse_requirement_table` |  | Interval granularity: the workbook's value when it states one. |
| `_parse_requirement_table` | 2332 to 2455 | 124 | `parse_input` |  |  |
| `_split_languages` | 2458 to 2459 | 2 | `_parse_language_rules` |  |  |
| `_alias_key` | 2470 to 2477 | 8 | `_parse_language_days` |  | Normalise for alias matching: lowercase, alphanumerics only. |
| `_parse_language_days` | 2480 to 2529 | 50 | `_parse_language_rules` |  | Parse Language Setup Coverage Days; invalid text must not mean all days. |
| `_parse_language_rules` | 2532 to 2650 | 119 | `parse_input` |  |  |
| `_parse_coverage_split` | 2877 to 2987 | 111 | `parse_input` |  | Read the optional Coverage Split sheet. |
| `_parse_break_segments` | 2993 to 3061 | 69 | `parse_input` |  | Break structure exactly as the workbook states it. |
| `_parse_break_sets_by_shift_length` | 3067 to 3111 | 45 | `parse_input` |  | Audit F-20: per-shift-length break sets stated in the workbook. |
| `_optional_instruction_minutes` | 3174 to 3179 | 6 | `_parse_break_window_controls` |  |  |
| `_parse_break_window_controls` | 3182 to 3288 | 107 | `parse_input` |  | Parse instruction-driven break placement windows and flexible spacing. |
| `_coerce_language_window_entries` | 3368 to 3382 | 15 | `_authored_language_windows`, `_input_contract_payload_core` | 1 file | Normalize legacy single-window and current multi-window values. |
| `_authored_language_windows` | 3385 to 3395 | 11 | `associate_language_windows`, `language_working_window_violations` |  | Return all authored windows before mode-specific filtering. |
| `parse_input` | 3572 to 4376 | 805 | `run_case`, `selfcheck` | 12 files |  |
| `input_contract_payload` | 4379 to 4393 | 15 | `canonical_contract_snapshot` |  |  |
| `_input_contract_payload_core` | 4396 to 4601 | 206 | `input_contract_payload` |  |  |
| `canonical_contract_snapshot` | 4604 to 4606 | 3 | `benchmark_provenance`, `run_case` | 1 file | Single normalized contract object used by hashes, resume identity and QA. |
| `validate_input_contract` | 4609 to 5062 | 454 | `run_case`, `selfcheck` | 2 files | Fail before CP-SAT when the workbook contract is malformed or provably impossible. |
| `case_identity_warnings` | 5065 to 5086 | 22 | `run_case` |  | Warn when an explicit workbook program identity conflicts with the case/output label. |
| `discover_validated_fallback_candidates` | 7610 to 7655 | 46 | `run_case` |  | Revalidate explicit and bundled schedule workbooks as safe incumbents. |
| `split_candidate_pool` | 12824 to 12852 | 29 | `merge_candidate_pools_with_safe_incumbent`, `run_case` |  |  |
| `synchronize_contract_metadata` | 14489 to 14544 | 56 | `write_output_workbook` |  | Replace stale workbook labels with the canonical parsed contract. |
| `read_production_summary_metadata` | 21172 to 21206 | 35 | `benchmark_provenance` |  | Read provenance fields from a previously exported production workbook. |

### Languages

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `associate_language_windows` | 3398 to 3408 | 11 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `associate_language_window`, `build_skeleton` +2 |  | Return all applicable working windows for one associate-day. |
| `associate_language_window` | 3411 to 3416 | 6 |  |  | Backward-compatible first-window accessor for legacy callers/tests. |
| `shift_within_language_window` | 3419 to 3447 | 29 | `language_window_allows` |  | True when the shift's START falls inside the window (with ``whole_shift`` its END must too: Phase AQ |
| `language_window_allows` | 3450 to 3453 | 4 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `fixed_requests_outside_language_windows` +2 |  | ``shift_within_language_window`` under the input's Language Working Window Shift Rule (Phase AQ). |
| `shift_overlaps_required_language_for_noneligible` | 3456 to 3479 | 24 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement` +2 |  | Return the first required language rule this associate cannot cover. |
| `language_working_window_violations` | 3482 to 3520 | 39 | `run_case` |  | Shifts scheduled outside their language's window, reported either way. |
| `fixed_requests_outside_language_windows` | 3523 to 3551 | 29 | `run_case`, `validate_input_contract` | 1 file | Fixed shift requests that start outside their associate's enforced |
| `language_eligible` | 6107 to 6108 | 2 | `_consistency_cell_allowed`, `_max_possible_raw_at_qslot`, `adaptive_operator_focus_cells`, `break_resilience_diagnostics` +16 |  |  |
| `language_rules_at` | 6111 to 6153 | 43 | `_rule_active_qslots_for_day`, `build_skeleton`, `calculate_metrics`, `capacity_diagnostics` +8 |  | Rules in force for the quarter-hour slot beginning at `minute`. |
| `language_operational_reserve_target` | 6156 to 6165 | 10 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return the qualified after-break staffing target for a required language. |
| `language_reserve_status` | 6168 to 6173 | 6 | `calculate_metrics` |  |  |
| `language_rule_key` | 9264 to 9274 | 11 | `break_resilience_diagnostics`, `build_skeleton`, `language_break_overlap_repair_plan` |  | Return a stable, client-neutral identity for a directional skill rule. |
| `language_break_overlap_repair_plan` | 9277 to 9466 | 190 | `logic_based_break_feasibility_cut_plan`, `run_case`, `run_zero_exception_recovery_phase` |  | Build a sparse, pattern-aware same-skill overlap repair plan. |
| `qualified_language_break_certificate_targets` | 9468 to 9522 | 55 | `run_qualified_language_break_certificate_repairs` |  | Resolve language-blocked exception rows into exact associate-day targets. |
| `solve_joint_shift_off_language_break_refinement` | 16492 to 17521 | 1030 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Jointly choose shift, OFF/leave state, language coverage, and breaks. |

### Breaks

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `break_attempt_key` | 1102 to 1122 | 21 | `run_case` |  | Stable replay/cache key for every materially different break model. |
| `serialize_break_candidate` | 1125 to 1141 | 17 | `publish_recovery_checkpoint`, `run_case`, `save_candidate_pool_checkpoint` |  |  |
| `deserialize_break_candidate` | 1144 to 1167 | 24 | `load_candidate_pool_checkpoint`, `run_case` | 1 file |  |
| `break_segments_for` | 3157 to 3167 | 11 | `break_quarters_for`, `build_break_constraint_isolation_report`, `generate_break_patterns`, `load_validated_fallback_candidate` +1 |  | The break set for a shift of ``duration_min`` minutes (audit F-20). |
| `break_quarters_for` | 3170 to 3171 | 2 | `break_capacity_headcount_requirement`, `break_resilience_diagnostics`, `build_skeleton`, `capacity_diagnostics` +4 |  |  |
| `break_concurrency_weight` | 5777 to 5798 | 22 | `solve_breaks` |  | Penalty for one interval of excess concurrent breaks. |
| `maximum_concurrent_breaks` | 5801 to 5808 | 8 | `break_capacity_headcount_requirement`, `calculate_metrics`, `dnbs_day_neighbourhood_model`, `solve_breaks` |  | Hard concurrent-break ceiling while preserving at least one working associate. |
| `_fallback_no_break_evidence` | 7200 to 7336 | 137 | `load_validated_fallback_candidate` |  | Reconstruct audited no-break exception cells from an exported workbook. |
| `_generic_break_patterns` | 8918 to 9011 | 94 | `build_break_constraint_isolation_report`, `generate_break_patterns`, `validate_input_contract` |  | Generate legal 15-minute break combinations with soft spacing quality. |
| `generate_break_patterns` | 9013 to 9026 | 14 | `build_skeleton`, `deserialize_break_candidate`, `language_break_overlap_repair_plan`, `selfcheck` +2 |  |  |
| `selected_break_spacing_rows` | 9030 to 9074 | 45 | `load_validated_fallback_candidate`, `run_day_neighbourhood_break_search`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return auditable spacing deviations for selected break patterns. |
| `build_break_constraint_isolation_report` | 9119 to 9177 | 59 | `run_case` |  | Summarize break-model search coverage and likely blockers. |
| `after_break_raw_expression` | 9661 to 9682 | 22 | `solve_breaks` |  | A NEW ``headcount - breaks`` expression for one quarter, built for one use. |
| `solve_breaks` | 9685 to 10355 | 671 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `minimum_exception_diagnostic`, `prove_selected_exceptions` +11 | 3 files |  |
| `break_qslots` | 10410 to 10422 | 13 | `break_damage_focus_cells`, `calculate_metrics`, `distinct_skill_allocation_audit`, `structural_schedule_audit` |  |  |
| `break_resilience_diagnostics` | 11681 to 11850 | 170 | `capacity_diagnostics` |  | Actionable pre-solver diagnostics for mandatory breaks and skills. |
| `select_protected_floor_break_anchors` | 12489 to 12511 | 23 | `run_protected_floor_break_guard` |  | Return production skeletons whose before-break floor shape deserves Stage-2 time. |
| `select_protected_target_break_anchors` | 12614 to 12630 | 17 | `run_protected_target_champion_break_proof` |  |  |
| `before_break_leaderboard_rows` | 12932 to 13004 | 73 | `run_case` |  | Build the canonical leaderboard rows used by success and failure artifacts. |
| `candidate_selection_breakdown` | 13038 to 13070 | 33 | `run_case` |  | Explain the universal target-protected champion ordering. |
| `break_solution_key` | 13173 to 13182 | 10 | `_quality_delta`, `acquire_early_safe_incumbent`, `adaptive_nondominated_anchor_pool`, `publish_recovery_checkpoint` +5 | 1 file | Target-driven deterministic ordering for otherwise valid final candidates. |
| `default_break_objective_modes` | 13185 to 13201 | 17 | `acquire_early_safe_incumbent`, `run_case` |  | Workbook-target-driven break objective order. |
| `dedupe_break_candidates` | 13204 to 13217 | 14 | `adaptive_nondominated_anchor_pool`, `bootstrap_exception_anchors_for_joint`, `choose_repair_anchors`, `discover_validated_fallback_candidates` +16 |  |  |
| `break_damage_focus_cells` | 13283 to 13321 | 39 | `adaptive_operator_focus_cells`, `derive_adaptive_feedback_cuts`, `run_adaptive_decomposed_joint_optimizer`, `run_coordinated_shift_off_break_loop` +2 |  | Associate-days whose selected breaks caused target/floor losses. |
| `break_release_diagnostic_only` | 13998 to 14030 | 33 | `select_export_candidates` |  | Stage-2 counterpart of ``skeleton_release_diagnostic_only``. |
| `ensure_before_break_metrics` | 14033 to 14053 | 21 | `protected_floor_anchor_key`, `run_case`, `run_protected_target_champion_break_proof`, `run_rc8_best_before_break_recovery` +6 | 1 file | Attach canonical no-break metrics to a feasible skeleton exactly once. |
| `break_capacity_headcount_requirement` | 14124 to 14239 | 116 | `before_break_leaderboard_rows`, `run_case` |  | How much headcount the schedule needs for breaks to have somewhere to go. |
| `write_before_break_workbook` | 14547 to 14637 | 91 | `run_case` |  | Export the independently strongest shift/OFF skeleton before breaks. |
| `skeleton_breakability_priority_key` | 15453 to 15470 | 18 | `run_case`, `run_logic_based_break_cut_feedback` |  | Prioritize skeletons that are already within the workbook exception cap. |
| `operational_no_break_exception_cap` | 15603 to 15607 | 5 | `build_skeleton`, `candidate_satisfies_explicit_kpi_locks`, `cap_feasible_target_recovery_decision`, `joint_candidate_within_operational_cap` +7 |  | Return the only exception cap that any C3 integrated output may use. |
| `break_load_by_interval` | 18316 to 18327 | 12 | `run_break_load_feedback` |  | Coverage units breaks removed per interval (before_effective - after_effective, |
| `logic_based_break_feasibility_cut_plan` | 18713 to 18762 | 50 | `run_logic_based_break_cut_feedback` |  | Build sparse master-model feedback from a fixed-skeleton break subproblem. |
| `global_zero_exception_break_reserve_requirements` | 18976 to 19015 | 40 | `run_case` |  | Return unanchored break-reserve raw staffing requirements. |
| `zero_exception_break_reserve_plan` | 19018 to 19161 | 144 | `logic_based_break_feasibility_cut_plan`, `run_zero_exception_recovery_phase` |  | Translate certified exception bottlenecks into universal staffing reserve constraints. |
| `_business_break_blockers` | 25733 to 25781 | 49 | `_build_business_outcome_core` |  |  |

### Preferences, OFF days and fixed requests

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_apply_preference_mapping` | 1944 to 1989 | 46 | `parse_input` |  | Translate site-specific Preference/Fixed codes via an optional mapping sheet. |
| `_preference_tokens` | 5650 to 5652 | 3 | `_extended_preference_kind` |  |  |
| `_extended_preference_kind` | 5655 to 5672 | 18 | `preference_kind` |  |  |
| `preference_kind` | 5675 to 5685 | 11 | `_consistency_swap_model`, `_parse_preferences`, `aggregate_pattern_mix_guidance`, `associate_day_eligible_shifts` +15 |  |  |
| `required_off_days` | 5706 to 5718 | 13 | `validate_schedule` |  | How many OFF days the weekly rule asks of this associate. |
| `separate_off_in_preference` | 5722 to 5736 | 15 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement`, `validate_schedule` |  | Whether this associate's own request rows name hard OFF days that are not next to each other (Phase  |
| `add_weekly_off_rule` | 5738 to 5759 | 22 | `build_skeleton`, `solve_joint_shift_off_language_break_refinement` |  | The weekly OFF rule, shared by every model that decides OFF days. |
| `_prefixed_metric` | 13085 to 13097 | 13 | `_candidate_quality_tuple`, `before_break_leaderboard_rows`, `candidate_selection_breakdown` | 1 file | Read ``{prefix}_{key}`` when present, else fall back to the bare key. |
| `target_priority_tradeoff_select` | 13363 to 13572 | 210 | `select_export_candidates` |  | Choose the final schedule from the workbook target, not a fixed 80% anchor. |
| `preference_distance` | 20274 to 20281 | 8 | `preference_swap_polish` |  | Minutes between associate a's Preference shift on day d and the shift worked (0 when there is no shi |
| `preference_swap_polish` | 20284 to 20394 | 111 | `run_case` |  | Phase BE: same-day swaps between interchangeable associates that bring both closer to their Preferen |

### Shifts and rest

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `shift_start_contract_allows` | 402 to 409 | 8 | `_parse_shifts`, `structural_schedule_audit`, `validate_input_contract` |  |  |
| `hhmm` | 445 to 447 | 3 | `_contract_display_rows`, `_parse_requirement_table`, `_parse_shifts`, `add_half_hour_twins` +17 | 1 file |  |
| `shift_parts` | 496 to 507 | 12 | `_consistency_swap_model`, `_parse_preferences`, `_parse_shifts`, `build_skeleton` +5 |  |  |
| `_time_column` | 2320 to 2329 | 10 | `_parse_requirement_table` |  |  |
| `rest_compatible` | 5762 to 5764 | 3 | `_consistency_row_allowed`, `_consistency_swap_model`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement` +2 |  |  |
| `previous_saturday_compatible` | 5767 to 5774 | 8 | `_consistency_row_allowed`, `_consistency_swap_model`, `associate_day_eligible_shifts`, `build_skeleton` +4 |  |  |
| `shift_covers_week_qslot` | 5891 to 5893 | 3 | `_max_possible_raw_at_qslot`, `_shift_interval_cover_fraction`, `_shift_overlap_qslots`, `aggregate_pattern_mix_guidance` +5 |  |  |
| `next_sunday_own_qslot` | 5931 to 5933 | 3 | `build_skeleton`, `calculate_metrics`, `cyclic_next_sunday_coverage_vars`, `cyclic_next_sunday_covering_occurrences` +3 |  | Map a pseudo day-eight quarter to the repeated Sunday quarter. |
| `previous_saturday_covers_qslot` | 6078 to 6084 | 7 | `calculate_metrics`, `prior_constant_cover`, `prior_covering_associates`, `structural_schedule_audit` |  |  |
| `coverage_vars_at_qslot` | 6189 to 6203 | 15 | `build_skeleton`, `coverage_vars`, `cyclic_next_sunday_coverage_vars` |  |  |
| `shift_day_demand_fit` | 6224 to 6266 | 43 | `demand_fit_blocked`, `structural_schedule_audit` |  | Demand shape for one (day, shift) pair, memoised per parsed contract. |
| `_shift_day_demand_fit_uncached` | 6269 to 6296 | 28 | `shift_day_demand_fit` |  |  |
| `scheduled_covering_qslot` | 8884 to 8889 | 6 | `adaptive_operator_focus_cells`, `break_capacity_headcount_requirement`, `break_damage_focus_cells`, `calculate_metrics` +9 |  |  |
| `_max_possible_raw_at_qslot` | 11638 to 11660 | 23 | `capacity_diagnostics` |  |  |
| `_rule_active_qslots_for_day` | 11664 to 11674 | 11 | `break_resilience_diagnostics` |  |  |
| `_shift_overlap_qslots` | 11677 to 11678 | 2 | `break_resilience_diagnostics` |  |  |
| `_shift_interval_cover_fraction` | 15834 to 15841 | 8 | `donor_receiver_shift_plan` |  |  |
| `shift_consistency_cost` | 19779 to 19787 | 9 | `_consistency_greedy_swaps`, `_consistency_swap_model`, `shift_consistency_polish`, `shift_consistency_summary` |  | (distinct start times, minutes of start movement between consecutive worked days). |
| `shift_consistency_summary` | 19790 to 19799 | 10 | `shift_consistency_polish` |  |  |
| `shift_consistency_polish` | 20131 to 20268 | 138 | `parse_input`, `run_case` |  | Return a more consistent schedule, or the original with the reason it was kept. |

### Metrics

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `require_metric` | 59 to 78 | 20 | `protected_floor_anchor_key`, `run_case`, `run_protected_target_champion_break_proof`, `select_export_candidates` +4 |  | Read a decision metric, failing loudly when it is absent. |
| `fractional_safe_overage_metrics` | 10544 to 10586 | 43 | `calculate_metrics` |  | Classify overage without penalizing indivisible whole-associate staffing. |
| `calculate_metrics` | 10673 to 11588 | 916 | `ensure_before_break_metrics`, `load_validated_fallback_candidate`, `preference_swap_polish`, `run_break_load_feedback` +11 | 3 files | Rebuild canonical before/after coverage truth from the final schedule. |
| `compact_metric_surface` | 11592 to 11597 | 6 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `discover_validated_fallback_candidates`, `publish_recovery_checkpoint` +8 |  | Keep scalar metrics while excluding only bulky row/detail collections. |
| `dnbs_metrics_no_worse` | 19399 to 19405 | 7 | `run_break_load_feedback`, `run_day_neighbourhood_break_search` |  | True when after_target strictly rose and no guarded metric got worse. |
| `_consistency_metrics_no_worse` | 19835 to 19843 | 9 | `preference_swap_polish`, `shift_consistency_polish` |  |  |

### Coverage, demand and capacity

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `cyclic_active_window` | 450 to 493 | 44 | `structural_schedule_audit` |  | Describe a day's active demand without flattening an overnight block. |
| `scaled_effective_factor` | 517 to 526 | 10 | `dnbs_day_neighbourhood_model`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Integer effective-FTE multiplier aligned with the canonical evaluator. |
| `scaled_coverage_threshold` | 529 to 536 | 8 | `dnbs_day_neighbourhood_model`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return the exact scaled average-coverage threshold for an interval. |
| `coverage_hit_threshold_units` | 539 to 564 | 26 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `critical_exception_cells` |  | Hit threshold for one interval in Stage-1 / guide coverage units |
| `coverage_split_required_headcount` | 2658 to 2671 | 14 | `build_skeleton`, `calculate_metrics`, `coverage_split_capacity_report`, `solve_breaks` |  | Grossed-up headcount one group must field for an interval it owns. |
| `coverage_split_capacity_report` | 2674 to 2833 | 160 | `run_case` |  | Can each owning group actually field what its window demands? |
| `merge_coverage_split_rules` | 2836 to 2868 | 33 | `_consistency_cell_allowed`, `build_skeleton`, `calculate_metrics`, `coverage_split_capacity_report` +1 |  | Groups whose windows overlap COVER THE INTERVAL TOGETHER. |
| `coverage_split_rules_at` | 2871 to 2874 | 4 | `_consistency_cell_allowed`, `build_skeleton`, `calculate_metrics`, `solve_breaks` |  |  |
| `volume_weight` | 3114 to 3131 | 18 | `build_skeleton`, `solve_breaks` |  | Audit F-28: an interval's miss weight, scaled by its requirement when the |
| `apply_coverage_objective_override` | 3137 to 3154 | 18 | `run_case` |  | Which coverage measure the run uses, and where it came from (audit F-28). |
| `next_sunday_raw_cap` | 5811 to 5830 | 20 | `build_skeleton`, `calculate_metrics`, `language_break_overlap_repair_plan`, `solve_breaks` +2 |  | Integer-safe raw cap that never conflicts with a harder opening/language minimum. |
| `next_sunday_raw_requirement` | 5833 to 5840 | 8 | `next_sunday_adjacent_raw_limit` |  | Minimum integer raw staffing for one Next-Sunday interval. |
| `next_sunday_adjacent_raw_limit` | 5843 to 5858 | 16 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Demand-aware adjacent raw-HC movement limit. |
| `whole_week_raw_requirement` | 5861 to 5866 | 6 | `whole_week_adjacent_raw_limit`, `whole_week_raw_cap` |  |  |
| `whole_week_raw_cap` | 5869 to 5881 | 13 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `whole_week_adjacent_raw_limit` | 5884 to 5888 | 5 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `next_sunday_spill_quarters` | 5896 to 5904 | 9 | `calculate_metrics`, `next_sunday_capacity_preflight`, `next_sunday_interval_quarters` |  | Maximum legal Saturday spill into the following Sunday, in 15-minute slots. |
| `next_sunday_interval_quarters` | 5907 to 5928 | 22 | `break_damage_focus_cells`, `build_skeleton`, `calculate_metrics`, `critical_exception_cells` +4 |  | Return every mirrored Sunday quarter inside the Saturday spill horizon. |
| `next_sunday_interval_indices` | 5936 to 5937 | 2 |  |  |  |
| `next_sunday_capacity_preflight` | 5957 to 6075 | 119 | `validate_input_contract` |  | Optimistic proof that Saturday assignments can protect next Sunday early demand. |
| `opening_intervals_for_day` | 6087 to 6104 | 18 | `build_skeleton`, `calculate_metrics`, `capacity_diagnostics`, `critical_exception_cells` +5 |  |  |
| `coverage_vars` | 6206 to 6208 | 3 | `build_skeleton` |  |  |
| `cyclic_next_sunday_coverage_vars` | 6211 to 6221 | 11 | `build_skeleton` |  | Saturday carry-out plus the repeated Sunday decision variables. |
| `demand_fit_blocked` | 6299 to 6311 | 13 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `donor_receiver_shift_plan` +3 |  |  |
| `coverage_quality_limits` | 6732 to 6748 | 17 | `_candidate_quality_tuple`, `aggregate_pattern_mix_guidance`, `build_skeleton`, `candidate_selection_breakdown` +4 |  | Return release-quality limits with safe defaults for synthetic replays. |
| `cyclic_next_sunday_covering_occurrences` | 8892 to 8900 | 9 | `calculate_metrics`, `cyclic_next_sunday_covering` |  | Return (associate, start_day, shift_index, source_qslot) for cyclic coverage. |
| `cyclic_next_sunday_covering` | 8903 to 8906 | 4 | `critical_exception_cells`, `language_break_overlap_repair_plan`, `solve_breaks` |  |  |
| `capacity_diagnostics` | 11852 to 12131 | 280 | `run_case`, `selfcheck` |  | Deterministic fail-fast feasibility diagnostics before CP-SAT. |
| `coverage_rebalance_focus_cells` | 13324 to 13360 | 37 | `adaptive_operator_focus_cells`, `run_adaptive_decomposed_joint_optimizer`, `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` +1 |  | Find donor overage cells and receiver shortage neighborhoods for transaction-safe repair. |
| `coverage_first_stage2_anchor_candidates` | 15473 to 15496 | 24 | `run_case` |  | Return production skeletons eligible for the protected Stage-2 anchor. |
| `phase_c_c2_overage_transaction_gate` | 16025 to 16069 | 45 | `run_coordinated_shift_off_break_loop` |  | Require strict overage improvement with complete multi-tier retention. |

### Skeleton search (stage 1)

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `skeleton_fingerprint` | 1070 to 1071 | 2 | `break_attempt_key`, `candidate_lineage_id`, `logic_based_break_feasibility_cut_plan`, `run_case` +6 |  |  |
| `serialize_skeleton` | 1074 to 1084 | 11 | `save_skeleton_checkpoint`, `serialize_break_candidate` |  |  |
| `deserialize_skeleton` | 1087 to 1099 | 13 | `deserialize_break_candidate`, `load_skeleton_checkpoint` |  |  |
| `save_skeleton_checkpoint` | 1170 to 1175 | 6 | `run_case` |  |  |
| `load_skeleton_checkpoint` | 1178 to 1184 | 7 | `run_case` |  |  |
| `rotate_stage1_profiles` | 5232 to 5242 | 11 | `run_case` |  | The profile order for seed `seed_index` of `seed_count`; see STAGE1_PROFILE_ROTATION. |
| `skeleton_profiles` | 6314 to 6505 | 192 | `rotate_stage1_profiles`, `run_break_load_feedback`, `run_case`, `run_shortfall_pass` | 5 files | Universal target-aware profiles, led by release-quality convergence. |
| `stage1_starved_basis_profile` | 6627 to 6653 | 27 | `run_case` |  | The one profile to run when the portfolio cannot fund even its first. |
| `stage1_fundable_profile_count` | 6673 to 6687 | 15 | `run_case` |  | How many Stage-1 profiles a wall-clock window can pay for at full depth. |
| `stage1_slice_seconds` | 6690 to 6713 | 24 | `run_case` |  | Per-profile Stage-1 solver slice: fund depth, not width. |
| `aggregate_pattern_mix_guidance` | 6761 to 7125 | 365 | `run_case` |  | Solve a small aggregate MILP before named-associate CP-SAT. |
| `repair_profile` | 7127 to 7136 | 10 | `run_case`, `run_coordinated_shift_off_break_loop`, `run_logic_based_break_cut_feedback`, `run_post_break_repair_phase` +2 |  |  |
| `_empty_skeleton` | 7139 to 7140 | 2 | `build_skeleton` |  |  |
| `load_seed_skeleton` | 7143 to 7195 | 53 | `load_validated_fallback_candidate`, `run_case` | 1 file | Read schedule cells from any compatible workbook as a generic anchor seed. |
| `build_skeleton` | 7657 to 8582 | 926 | `run_break_load_feedback`, `run_case`, `run_conflict_refinement`, `run_constraint_isolation` +7 | 5 files |  |
| `pattern_map` | 10406 to 10407 | 2 | `break_qslots`, `candidate_lineage_id`, `dnbs_day_neighbourhood_model`, `selected_break_spacing_rows` +3 |  |  |
| `skeleton_release_diagnostic_only` | 13981 to 13995 | 15 | `coverage_first_stage2_anchor_candidates`, `protected_floor_anchor_key`, `run_case`, `select_best_before_skeleton` +4 |  | Return True for feasibility probes/warm-start anchors that must not win release. |
| `skeleton_exceeds_exception_cap` | 14056 to 14071 | 16 | `select_best_shippable_before_skeleton` |  | True when this skeleton PROVABLY cannot ship under the workbook's policy. |
| `select_best_shippable_before_skeleton` | 14074 to 14097 | 24 | `run_case` |  | The strongest before-break skeleton that could actually be delivered. |
| `select_best_before_skeleton` | 14242 to 14258 | 17 | `run_case`, `select_best_shippable_before_skeleton` |  | Select the independent hard-clean pre-break winner by workbook target. |
| `select_stage1_hint_skeleton` | 14261 to 14289 | 29 | `run_case` |  | Return the strongest safe Stage-1 hint without making hints a release gate. |
| `skeleton_quality_key` | 15442 to 15450 | 9 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `run_case`, `run_zero_exception_recovery_phase` +1 |  |  |
| `skeleton_hard_clean` | 15499 to 15506 | 8 | `acquire_early_safe_incumbent`, `load_validated_fallback_candidate`, `retain_zero_exception_diagnostic_candidate`, `run_break_load_feedback` +11 | 1 file |  |
| `dedupe_skeletons` | 15734 to 15745 | 12 | `bootstrap_exception_anchors_for_joint`, `run_case`, `run_logic_based_break_cut_feedback`, `run_qualified_language_break_certificate_repairs` +3 |  |  |
| `_consistency_skeleton` | 19851 to 19861 | 11 | `_consistency_greedy_swaps`, `preference_swap_polish`, `shift_consistency_polish` |  |  |

### Joint, repair and neighbourhood search

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `joint_memory_headroom` | 5118 to 5145 | 28 | `run_adaptive_decomposed_joint_optimizer`, `run_case` |  | Whether the machine can afford another joint shift+break model. |
| `joint_solve_kill_threshold_mb` | 5303 to 5304 | 2 | `isolated_cp_solve` |  |  |
| `_child_prepare_for_isolated_solve` | 5307 to 5331 | 25 | `isolated_cp_solve` |  | In the forked child: die with the parent, and be the OOM killer's first choice. |
| `isolated_cp_solve` | 5334 to 5466 | 133 | `isolated_cp_solver` |  | Run in_process_solve(model) in a forked, memory-watched child; see the block comment above. |
| `joint_solve_isolation_audit` | 5469 to 5487 | 19 | `run_case` |  | Every joint solve of this run: how it ran and how its child ended. |
| `isolated_cp_solver` | 5490 to 5507 | 18 | `solve_joint_shift_off_language_break_refinement` |  | A CpSolver whose Solve runs through isolated_cp_solve; otherwise the stock class. |
| `stage2_anchor_slice_seconds` | 6580 to 6621 | 42 | `run_case` |  | Time limit for the guaranteed Stage-2 anchor solve. |
| `protected_floor_anchor_key` | 12454 to 12486 | 33 | `select_protected_floor_break_anchors` |  | Lower-is-better key for deciding which skeleton deserves protected break time. |
| `target_anchor_key` | 12584 to 12611 | 28 | `select_protected_target_break_anchors` |  | Lower-is-better key for protected break proof of the target champion. |
| `repair_candidate_key` | 12784 to 12821 | 38 | `choose_repair_anchors`, `run_case`, `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  | Lower-is-better repair debt, then stronger target/floor quality. |
| `choose_repair_anchors` | 12855 to 12875 | 21 | `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  | Keep representation from clean, near-feasible, and exception pools. |
| `retain_search_only_diagnostic_joint_anchor` | 15558 to 15600 | 43 | `run_case` |  | Retain a feasible diagnostic assignment only as an integrated-search anchor. |
| `joint_candidate_within_operational_cap` | 15610 to 15611 | 2 | `run_adaptive_decomposed_joint_optimizer` |  |  |
| `mark_cap_descent_search_anchor` | 15631 to 15651 | 21 | `run_adaptive_decomposed_joint_optimizer` |  | Mark an above-cap integrated result as search-only, never releasable. |
| `donor_receiver_shift_plan` | 15844 to 16022 | 179 | `run_coordinated_shift_off_break_loop` |  | Build a bounded transaction-safe donor/receiver shift-target plan. |
| `adaptive_nondominated_anchor_pool` | 16187 to 16264 | 78 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Keep a diverse nondominated anchor set for adaptive refinement. |
| `derive_adaptive_feedback_cuts` | 16267 to 16352 | 86 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Translate break/coverage damage into replayable master feedback cuts. |
| `adaptive_operator_focus_cells` | 16355 to 16435 | 81 | `run_adaptive_decomposed_joint_optimizer` |  | Build operator-specific destroy neighborhoods from current damage. |
| `_joint_candidate_shift_indices` | 16438 to 16489 | 52 | `solve_joint_shift_off_language_break_refinement` |  | Return a small universal shift neighborhood for a joint refinement cell. |
| `bootstrap_exception_anchors_for_joint` | 17524 to 17662 | 139 | `run_case` |  | Create operational exception anchors before adaptive joint refinement. |
| `dnbs_day_neighbourhood_model` | 19408 to 19528 | 121 | `run_day_neighbourhood_break_search` |  | Aggregated break model for the shifts starting on ``day``. |

### Candidate selection

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `save_candidate_pool_checkpoint` | 1187 to 1208 | 22 | `run_case` |  | Persist all useful candidate classes without changing release semantics. |
| `load_candidate_pool_checkpoint` | 1211 to 1227 | 17 | `run_case` |  |  |
| `load_validated_fallback_candidate` | 7338 to 7521 | 184 | `discover_validated_fallback_candidates`, `run_case` |  | Load and revalidate a previously exported fully evaluated schedule. |
| `bundled_schedule_candidate_inventory` | 7525 to 7608 | 84 | `discover_validated_fallback_candidates`, `run_case` |  | Return data-driven current-contract champions and seed-only workbooks. |
| `prove_selected_exceptions` | 10374 to 10404 | 31 | `run_case` |  |  |
| `candidate_validation_snapshot` | 12735 to 12747 | 13 | `candidate_pool_class`, `promote_zero_exception_diagnostic_candidate`, `retain_search_only_diagnostic_joint_anchor`, `run_case` +1 |  | Return and persist the full release validation for a candidate. |
| `candidate_pool_class` | 12750 to 12781 | 32 | `adaptive_nondominated_anchor_pool`, `bootstrap_exception_anchors_for_joint`, `candidate_satisfies_explicit_kpi_locks`, `choose_repair_anchors` +20 | 1 file | Classify a feasible candidate without weakening any release gate. |
| `candidate_damage_present` | 12878 to 12892 | 15 | `run_case` |  | Return whether a candidate still deserves bounded recovery effort. |
| `_deficit_bucket` | 13073 to 13082 | 10 | `_candidate_quality_tuple`, `before_break_leaderboard_rows`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` | 1 file | Quantize a coverage-deficit sum to an operationally meaningful bucket. |
| `_candidate_quality_tuple` | 13100 to 13170 | 71 | `break_solution_key`, `run_case`, `select_best_before_skeleton`, `select_export_candidates` +3 | 1 file | Positive-is-better universal target-protected ordering. |
| `merge_candidate_pools_with_safe_incumbent` | 13220 to 13280 | 61 | `run_case` |  | Retain a validated incumbent in its correct release pool. |
| `candidate_dominates` | 13575 to 13616 | 42 | `nondominated_candidates` |  | Pareto dominance after hard-gate and exception-count filtering. |
| `nondominated_candidates` | 13619 to 13624 | 6 | `pareto_frontier_signature`, `select_export_candidates` |  |  |
| `select_export_candidates` | 13679 to 13978 | 300 | `run_case`, `selfcheck` |  | Select recommended, max-target, and max-floor candidates safely. |
| `select_release_candidates_with_protection` | 14303 to 14342 | 40 | `run_case` |  | Prefer zero-exception schedules, but never discard a protected exception champion. |
| `candidate_record` | 14389 to 14433 | 45 | `publish_recovery_checkpoint`, `run_case` |  |  |
| `retain_zero_exception_diagnostic_candidate` | 15509 to 15555 | 47 | `promote_zero_exception_diagnostic_candidate`, `run_case` |  | Retain every real zero-exception assignment as clean or near-feasible. |
| `promote_zero_exception_diagnostic_candidate` | 15654 to 15703 | 50 | `run_case` |  | Promote a zero-exception diagnostic solution to a safe fallback. |
| `minimum_exception_candidate_pool` | 15749 to 15756 | 8 | `run_target_lock_recovery_phase` |  |  |
| `_candidate_identity` | 16091 to 16097 | 7 | `adaptive_nondominated_anchor_pool` |  |  |
| `candidate_lineage_id` | 16100 to 16121 | 22 | `run_adaptive_decomposed_joint_optimizer`, `solve_joint_shift_off_language_break_refinement`, `validate_replay_candidate_mapping` |  | Stable identity for one coherent shift/OFF/break candidate. |
| `validate_replay_candidate_mapping` | 16124 to 16184 | 61 | `run_adaptive_decomposed_joint_optimizer`, `solve_joint_shift_off_language_break_refinement` |  | Prove a replay anchor is internally coherent before building CP-SAT. |
| `candidate_satisfies_explicit_kpi_locks` | 20592 to 20619 | 28 | `cap_feasible_target_recovery_decision` |  | Return True only for a release-class candidate satisfying every explicit lock. |

### Output and publishing

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `cleanup_stale_run_outputs` | 283 to 319 | 37 | `run_case` |  | Remove only the known artifacts for an intentional non-resume overwrite. |
| `_write_records` | 14370 to 14375 | 6 | `run_shortfall_pass`, `synchronize_contract_metadata`, `write_output_workbook` |  |  |
| `production_quality_gate` | 14640 to 14800 | 161 | `load_validated_fallback_candidate`, `write_output_workbook` |  | Classify hard coverage quality separately from declared operational quality debt. |
| `write_output_workbook` | 14802 to 15439 | 638 | `publish_recovery_checkpoint`, `run_case`, `run_shortfall_pass`, `write_before_break_workbook` |  |  |
| `publish_recovery_checkpoint` | 21102 to 21170 | 69 | `run_case` |  | Atomically persist the best validated pre-late-phase candidate. |
| `_business_int` | 25669 to 25675 | 7 | `_build_business_outcome_core`, `_business_contract_message`, `_business_exception_rows` |  |  |
| `_business_failure_rows` | 25678 to 25684 | 7 | `_build_business_outcome_core` |  |  |
| `_business_exception_rows` | 25687 to 25718 | 32 | `_business_break_blockers` |  |  |
| `_business_reason_window` | 25721 to 25730 | 10 | `_business_break_blockers` |  |  |
| `_business_contract_message` | 25784 to 25852 | 69 | `_build_business_outcome_core` |  |  |
| `_business_hard_conflict` | 25871 to 25913 | 43 | `_build_business_outcome_core` |  | Plain-language findings for a hard-rule contradiction. |
| `_business_finding_text` | 25916 to 25930 | 15 | `format_business_outcome` |  | One readable line per finding: named fields, never nested solver dumps. |
| `publish_business_outcome` | 26309 to 26328 | 20 | `main` |  |  |

### Audit and self-check

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_validate_numeric_instruction` | 1473 to 1492 | 20 | `parse_input` |  | Flag malformed numeric controls before permissive legacy coercion runs. |
| `_validate_boolean_instructions` | 1530 to 1545 | 16 | `parse_input` |  | A switch row holding something that is neither yes nor no fails the contract. |
| `distinct_skill_allocation_audit` | 10426 to 10541 | 116 | `calculate_metrics` |  | Audit simultaneous skill minima using distinct available associates. |
| `structural_schedule_audit` | 12134 to 12329 | 196 | `validate_schedule` |  | Audit blank bridges, day tails, overnight shifts and cyclic Sunday truth. |
| `validate_schedule` | 12332 to 12445 | 114 | `acquire_early_safe_incumbent`, `candidate_damage_present`, `candidate_validation_snapshot`, `load_validated_fallback_candidate` +9 |  |  |
| `selfcheck` | 25239 to 25551 | 313 | `main` |  |  |

### Shift consistency polish

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_consistency_cell_allowed` | 19802 to 19817 | 16 | `_consistency_greedy_swaps`, `_consistency_swap_model`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `_consistency_row_allowed` | 19820 to 19832 | 13 | `_consistency_greedy_swaps`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `_consistency_employee_no_worse` | 19846 to 19848 | 3 | `_consistency_greedy_swaps`, `preference_swap_polish` |  |  |
| `_consistency_greedy_swaps` | 19864 to 19911 | 48 | `shift_consistency_polish` |  | Pairwise same-day swaps that lower the two associates' cost; the model |
| `_consistency_swap_model` | 19914 to 20088 | 175 | `shift_consistency_polish` |  | Re-deal each day's shifts within (language, shift length) groups. |

### Tiers, exceptions and quality figures

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `status_name` | 5097 to 5105 | 9 | `build_skeleton`, `capture_solver_telemetry`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `enrich_exception_rows` | 9077 to 9116 | 40 | `build_break_constraint_isolation_report`, `solve_breaks` |  | Attach exact blocking evidence to minimum-exception cells. |
| `critical_exception_cells` | 9179 to 9261 | 83 | `solve_breaks` |  |  |
| `minimum_exception_diagnostic` | 10357 to 10371 | 15 | `run_case`, `run_logic_based_break_cut_feedback`, `run_qualified_language_break_certificate_repairs` |  | Bound the minimum no-break associate-days required by this skeleton. |
| `employee_operational_quality` | 10589 to 10670 | 82 | `_consistency_greedy_swaps`, `calculate_metrics`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `near_feasible_failure_status` | 12895 to 12912 | 18 | `run_case` |  | Describe the candidate-level reason a retained diagnostic was not released. |
| `hard_floor_failure_rows` | 12915 to 12929 | 15 | `run_case` |  | Return exact intervals below the configured hard floor for evidence output. |
| `_protected_tier_counts` | 13007 to 13025 | 19 | `_candidate_quality_tuple`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` | 1 file | Return safety tiers strictly between the workbook target and configured floor. |
| `pareto_frontier_signature` | 13627 to 13643 | 17 | `run_case` |  |  |
| `_tier_minimum_failures` | 13646 to 13663 | 18 | `_meets_tier_minima`, `run_case` |  | Return explicit 100/90/80 benchmark failures for one metric surface. |
| `_meets_tier_minima` | 13666 to 13676 | 11 | `select_export_candidates` |  |  |
| `protected_benchmark_pass` | 14292 to 14300 | 9 | `select_release_candidates_with_protection` |  |  |
| `exception_reason_map` | 14378 to 14386 | 9 | `write_output_workbook` |  |  |
| `exception_cap_descent_targets` | 15614 to 15628 | 15 | `run_adaptive_decomposed_joint_optimizer` |  | Return a monotone one-exception-at-a-time path to the release cap. |
| `_quality_delta` | 16071 to 16086 | 16 | `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  |  |
| `benchmark_provenance` | 21209 to 21269 | 61 | `run_case` |  | Classify a benchmark as authoritative only when its contract provenance matches. |

### Workbook styling

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_replace_sheet` | 14345 to 14348 | 4 | `run_shortfall_pass`, `synchronize_contract_metadata`, `write_output_workbook` |  |  |
| `_style_header` | 14351 to 14356 | 6 | `_write_records` |  |  |
| `_autosize` | 14359 to 14367 | 9 | `_write_records` |  |  |
| `_contract_display_rows` | 14436 to 14486 | 51 | `synchronize_contract_metadata` |  |  |

### Time reserves and machine limits

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_cgroup_memory_headroom_mb` | 5252 to 5280 | 29 | `machine_free_memory_mb` |  | limit - usage of this process's own memory cgroup (v2 or v1), if limited. |
| `machine_free_memory_mb` | 5283 to 5300 | 18 | `isolated_cp_solve`, `joint_memory_headroom` |  | (free MB, total MB): MemAvailable, tightened by a cgroup limit if one applies. |
| `capture_solver_telemetry` | 5511 to 5609 | 99 | `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Read back what the solve already computed. Costs no solver time. |
| `preflight_probe_retry_seconds` | 6661 to 6670 | 10 | `run_case` |  | Seconds for a second hard-feasibility probe after an UNKNOWN first one. |
| `guaranteed_stage2_reserve_seconds` | 15706 to 15714 | 9 | `bounded_stage2_guard_reserve_seconds` |  | Wall-time reserve protected from Stage 1 and diagnostics. |
| `bounded_stage2_guard_reserve_seconds` | 15717 to 15731 | 15 | `run_case`, `selfcheck` |  | Protect at least one real break solve even in short functional runs. |

### Other helpers

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `circular_minute_distance` | 5688 to 5690 | 3 | `_consistency_swap_model`, `_joint_candidate_shift_indices`, `build_skeleton`, `employee_operational_quality` +2 |  |  |
| `pinned_leave_days` | 5693 to 5703 | 11 | `build_skeleton`, `required_off_days`, `solve_joint_shift_off_language_break_refinement` |  | Days this associate is pinned to Leave by the contract (fixed or approved leave). |
| `cyclic_requirement_context` | 5940 to 5954 | 15 | `_shift_day_demand_fit_uncached`, `structural_schedule_audit` |  | Map a current-week or pseudo-next-Sunday qslot to weekday/interval/minute. |
| `prior_constant_cover` | 6176 to 6186 | 11 | `build_skeleton` |  |  |
| `active_interval_segments` | 6716 to 6729 | 14 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return contiguous active interval segments; blank periods reset runs. |
| `eligible_shift_day_pairs` | 6751 to 6758 | 8 | `aggregate_pattern_mix_guidance`, `run_case` |  |  |
| `elastic_slack_rows` | 8585 to 8605 | 21 | `build_skeleton`, `solve_breaks` |  | One row per minimum the solution actually misses, with the measured deficit. |
| `shortfall_pass_allowed` | 8640 to 8643 | 4 | `run_case` |  | True when every contract failure is a capacity proof (F-06). |
| `scheduled_cells` | 8875 to 8881 | 7 | `adaptive_operator_focus_cells`, `break_qslots`, `calculate_metrics`, `dnbs_day_neighbourhood_model` +23 | 3 files |  |
| `prior_covering_associates` | 8909 to 8915 | 7 | `_max_possible_raw_at_qslot`, `aggregate_pattern_mix_guidance`, `break_capacity_headcount_requirement`, `break_resilience_diagnostics` +9 |  |  |
| `associate_day_eligible_shifts` | 11600 to 11635 | 36 | `_joint_candidate_shift_indices`, `_max_possible_raw_at_qslot`, `break_resilience_diagnostics`, `capacity_diagnostics` +1 |  | Return shifts that can possibly be used by one associate-day before weekly coupling. |
| `_target_secondary_counts` | 13028 to 13036 | 9 | `_candidate_quality_tuple`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` |  | Return only tiers ABOVE the workbook target as late upside tie-breaks. |
| `default_workdays_per_week` | 14113 to 14121 | 9 | `break_capacity_headcount_requirement`, `break_resilience_diagnostics`, `capacity_diagnostics`, `coverage_split_capacity_report` |  | Days one associate works in a week, for converting weekly capacity. |
| `acquire_early_safe_incumbent` | 15759 to 15831 | 73 | `run_case` |  | Acquire a fully evaluated incumbent before the expensive Pareto search. |
| `feedback_cut_variants` | 18765 to 18792 | 28 | `run_logic_based_break_cut_feedback` |  | Split a break-feasibility cut into progressively stronger master repairs. |
| `recommended_export_pair` | 20095 to 20111 | 17 | `run_case` |  | The recommended pair, checked to be the RECOMMENDED_FINAL pair the writer publishes. |
| `add_more_consistent_export` | 20114 to 20128 | 15 | `run_case` |  | Publish an applied polish as MORE_CONSISTENT_CANDIDATE, beside the selected schedule. |
| `cap_feasible_target_recovery_decision` | 20622 to 20678 | 57 | `run_case` |  | Decide whether RC6 recovery should run without disturbing healthy schedules. |
| `derive_dynamic_before_search_locks` | 20769 to 20796 | 28 | `run_case` |  | Derive search-only Stage-1 retention locks from current-contract truth. |
| `classify_late_phase_execution_gate` | 21028 to 21098 | 71 | `run_case` |  | Classify late-phase execution without confusing candidate and engine failure. |
| `build_business_outcome` | 25933 to 25977 | 45 | `publish_business_outcome` |  | The run's business outcome, plus the shortfall schedule when one was made (F-06). |
| `_build_business_outcome_core` | 25980 to 26237 | 258 | `build_business_outcome` |  |  |
| `shortfall_text_line` | 26240 to 26244 | 5 | `format_business_outcome` |  |  |
| `format_business_outcome` | 26250 to 26287 | 38 | `publish_business_outcome` |  |  |
| `_augment_summary_with_business_outcome` | 26290 to 26306 | 17 | `publish_business_outcome` |  |  |
| `record_unexpected_run_failure` | 26331 to 26364 | 34 | `main` |  | Persist a truthful terminal status for an unexpected engine exception. |
| `explicitly_supplied_options` | 26422 to 26442 | 21 | `main` | 1 file | Return the argparse destinations the caller actually typed. |

## 3. What is used from outside the engine file

Names that other code (the wrapper, the validator, the tools, the website; not the tests, which use the engine freely) uses, by number of files. A change to one of these reaches those files.

| Name | Files | Examples |
|---|---|---|
| `parse_input` | 12 | `engine/RUN_UNIVERSAL_PRODUCTION.py`, `tools/b13_joint_direct_ab.py`, `tools/b4_probe.py` |
| `HardConfig` | 5 | `tools/b5_tiers.py`, `tools/b6_detect.py`, `tools/break_slice_depth_probe.py` |
| `build_skeleton` | 5 | `tools/b5_tiers.py`, `tools/b6_detect.py`, `tools/break_slice_depth_probe.py` |
| `skeleton_profiles` | 5 | `tools/b5_tiers.py`, `tools/b6_detect.py`, `tools/break_slice_depth_probe.py` |
| `calculate_metrics` | 3 | `tools/b4_probe.py`, `tools/break_slice_depth_probe.py`, `tools/stage1_slice_depth_probe.py` |
| `scheduled_cells` | 3 | `tools/b4_probe.py`, `tools/break_slice_depth_probe.py`, `tools/stage1_slice_depth_probe.py` |
| `solve_breaks` | 3 | `tools/b4_probe.py`, `tools/break_slice_depth_probe.py`, `tools/stage2_decisive_probe.py` |
| `import_cp_sat` | 2 | `tools/b5_tiers.py`, `tools/b6_detect.py` |
| `validate_input_contract` | 2 | `tools/build_input_template.py`, `tools/check_input_workbook.py` |
| `_candidate_quality_tuple` | 1 | `tools/replay_candidate_ranking.py` |
| `_coerce_language_window_entries` | 1 | `tools/check_input_workbook.py` |
| `_deficit_bucket` | 1 | `tools/replay_candidate_ranking.py` |
| `_discover_requirement_sheet` | 1 | `tools/build_web_workbooks.py` |
| `_instruction_map` | 1 | `tools/build_web_workbooks.py` |
| `_prefixed_metric` | 1 | `tools/replay_candidate_ranking.py` |
| `_protected_tier_counts` | 1 | `tools/replay_candidate_ranking.py` |
| `_sheet_by_alias` | 1 | `tools/build_web_workbooks.py` |
| `adaptive_nondominated_anchor_pool` | 1 | `tools/b13_joint_direct_ab.py` |
| `break_solution_key` | 1 | `tools/b13_joint_direct_ab.py` |
| `candidate_pool_class` | 1 | `tools/b13_joint_direct_ab.py` |
| `canonical_contract_snapshot` | 1 | `tools/enforce_workbook_validations.py` |
| `canonical_hash` | 1 | `tools/enforce_workbook_validations.py` |
| `derive_adaptive_feedback_cuts` | 1 | `tools/b13_joint_direct_ab.py` |
| `deserialize_break_candidate` | 1 | `tools/b13_joint_direct_ab.py` |
| `ensure_before_break_metrics` | 1 | `tools/stage2_decisive_probe.py` |
| `explicitly_supplied_options` | 1 | `engine/RUN_UNIVERSAL_PRODUCTION.py` |
| `fixed_requests_outside_language_windows` | 1 | `tools/check_input_workbook.py` |
| `hhmm` | 1 | `tools/check_input_workbook.py` |
| `load_seed_skeleton` | 1 | `tools/b4_probe.py` |
| `norm` | 1 | `tools/b6_symmetry.py` |
| `skeleton_hard_clean` | 1 | `tools/b4_probe.py` |
| `solve_joint_shift_off_language_break_refinement` | 1 | `tools/b13_joint_direct_ab.py` |

## 4. Process-wide switches

Module-level names written with `global` and read elsewhere. Code moved to another module must read them as `settings.NAME`, never `from x import NAME`, or a write would not be seen.

| Switch | Defined at line | Written in | Read in |
|---|---|---|---|
| `FINAL_RECOVERY_ENDGAME_ENABLED` | 5220 | `main` | `run_case` |
| `STAGE1_PROFILE_ROTATION` | 5229 | `main` | `run_case` |
| `BREAK_LOAD_FEEDBACK_ENABLED` | 18312 | `main` | `run_case` |
| `DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED` | 19368 | `main` | `run_case` |
| `SHIFT_CONSISTENCY_CLI_OVERRIDE` | 19759 | `main` | `run_case` |
| `SOLVER_DETERMINISTIC_TIME` | 5113 | `run_shortfall_pass` | `configure_solver_limits` |

## 5. Places that pin or check the engine's hash

After any engine edit, these must agree with the new file: run `python3 tools/refresh_engine_identity.py --previous <old sha256>`, then `python3 tools/engine_map.py --write`, then the gate.

The two data files that hold it are `engine/RELEASE_IDENTITY_RC9_2_2.json` (`engine_file_sha256`) and `packages/rc9_2_2_production/SCENARIOS.json` (`engine_sha256`); the refresh script writes both. The code that reads or checks it:

| File | Lines that name the hash |
|---|---|
| `engine/RUN_UNIVERSAL_PRODUCTION.py` | 4 |
| `engine/_tools/l632_universal_scheduler.py` | 6 |
| `engine/production/package_phase_c_outputs.py` | 1 |
| `engine/production/production_output_polisher.py` | 5 |
| `engine/regression_assets/regression_lab/verify_phase_a_closure.py` | 1 |
| `engine/tools/independent_validator.py` | 2 |
| `packages/rc9_2_2_production/runners/rc921_runner.py` | 4 |
| `tools/build_production_package.py` | 3 |
| `tools/refresh_engine_identity.py` | 4 |
| `tools/release_gate_report.py` | 1 |

## 6. Where to look first

| What you see | Look at (line) |
|---|---|
| The workbook is misread or refused | `parse_input` (3572), `validate_input_contract` (4609), `preference_kind` (5675) |
| A language minimum is not met | `language_rules_at` (6111), `language_reserve_status` (6168), `associate_language_windows` (3398), `solve_joint_shift_off_language_break_refinement` (16492) |
| A break is placed too late, too early or too many at once | `solve_breaks` (9685), `maximum_concurrent_breaks` (5801), `run_day_neighbourhood_break_search` (19531) |
| A coverage figure on the output is wrong | `calculate_metrics` (10673), `coverage_vars` (6206), `coverage_quality_limits` (6732) |
| An OFF or shift request is not honoured | `preference_kind` (5675), `required_off_days` (5706), `add_weekly_off_rule` (5738) |
| A different candidate is published than expected | `select_export_candidates` (13679), `target_priority_tradeoff_select` (13363), `_candidate_quality_tuple` (13100) |
| The output workbook and the validator disagree | `write_output_workbook` (14802), `structural_schedule_audit` (12134), `publish_business_outcome` (26309) |
| A run takes longer or shorter than asked | `run_case` (21294), `main` (26466), `stage1_minimum_budget_seconds` (21284) |
| The first (skeleton) search is weak | `build_skeleton` (7657), `skeleton_profiles` (6314), `aggregate_pattern_mix_guidance` (6761) |
| A fixed or nested shift is broken | `rest_compatible` (5762), `previous_saturday_compatible` (5767), `shift_parts` (496) |
