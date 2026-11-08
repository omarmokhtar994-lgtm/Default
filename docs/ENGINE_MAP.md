# Engine map

Written by `tools/engine_map.py` from `engine/_tools/l632_universal_scheduler.py`; do not edit by hand. `python3 tools/engine_map.py --check` fails when the engine has changed since this was written.

- File: `engine/_tools/l632_universal_scheduler.py`, sha256 `e476f2699f952cbf95fb599e595a9ccbae37d52983c1949a0fc91a8d81506c47`
- 26,830 lines; 369 functions, 12 classes

## 1. The stages of `run_case`

`run_case` is lines 21479 to 25433 (3,955 lines, 72 parameters). Its body is one `with` block (lines 21555 to 25433) of 470 statements in sequence. The outline below is read from what it calls, in order of first call; a function of 100 lines or more is a stage of its own.

| Order | First call at line | Function | Lines | Job |
|---|---|---|---|---|
| 1 | 21556 | `parse_input` | 809 | Input reading and contract |
| 2 | 21657 | `capacity_diagnostics` | 280 | Coverage, demand and capacity |
| 3 | 21658 | `coverage_split_capacity_report` | 160 | Coverage, demand and capacity |
| 4 | 21668 | `validate_input_contract` | 466 | Input reading and contract |
| 5 | 21736 | `calculate_metrics` | 916 | Metrics |
| 6 | 21745 | `validate_schedule` | 115 | Audit and self-check |
| 7 | 21773 | `load_validated_fallback_candidate` | 184 | Candidate selection |
| 8 | 21843 | `skeleton_profiles` | 192 | Skeleton search (stage 1) |
| 9 | 22281 | `run_shortfall_pass` | 133 | Search phases (`run_*`) |
| 10 | 22306 | `aggregate_pattern_mix_guidance` | 365 | Skeleton search (stage 1) |
| 11 | 22342 | `build_skeleton` | 931 | Skeleton search (stage 1) |
| 12 | 22807 | `break_capacity_headcount_requirement` | 116 | Breaks |
| 13 | 22993 | `run_qualified_language_break_certificate_repairs` | 134 | Search phases (`run_*`) |
| 14 | 23014 | `run_logic_based_break_cut_feedback` | 180 | Search phases (`run_*`) |
| 15 | 23133 | `language_break_overlap_repair_plan` | 190 | Languages |
| 16 | 23473 | `run_protected_target_champion_break_proof` | 100 | Search phases (`run_*`) |
| 17 | 23539 | `run_zero_exception_recovery_phase` | 182 | Search phases (`run_*`) |
| 18 | 23636 | `solve_breaks` | 671 | Breaks |
| 19 | 23941 | `run_rc8_best_before_break_recovery` | 115 | Search phases (`run_*`) |
| 20 | 23974 | `run_day_neighbourhood_break_search` | 197 | Search phases (`run_*`) |
| 21 | 24036 | `bootstrap_exception_anchors_for_joint` | 139 | Joint, repair and neighbourhood search |
| 22 | 24089 | `run_adaptive_decomposed_joint_optimizer` | 643 | Search phases (`run_*`) |
| 23 | 24144 | `run_break_load_feedback` | 111 | Search phases (`run_*`) |
| 24 | 24165 | `run_coordinated_shift_off_break_loop` | 267 | Search phases (`run_*`) |
| 25 | 24221 | `run_post_break_repair_phase` | 191 | Search phases (`run_*`) |
| 26 | 24245 | `run_target_lock_recovery_phase` | 110 | Search phases (`run_*`) |
| 27 | 24779 | `write_output_workbook` | 638 | Output and publishing |
| 28 | 24870 | `select_export_candidates` | 300 | Candidate selection |
| 29 | 24893 | `preference_swap_polish` | 118 | Preferences, OFF days and fixed requests |
| 30 | 24923 | `shift_consistency_polish` | 138 | Shifts and rest |

Blocks inside `run_case` of 70 lines or more, in order:

| Lines | Size | Starts with |
|---|---|---|
| 21971 to 22060 | 90 | `run_parameters = {` |
| 22124 to 22245 | 122 | `audit: Dict[str, Any] = {` |
| 22583 to 22677 | 95 | `for profile_index, profile in enumerate(profiles_to_run):` |
| 22685 to 22763 | 79 | `if skeleton_only and successful_skeletons and polish_deadline - time.time() >= 45:` |
| 22786 to 22910 | 125 | `if skeleton_only:` |
| 23038 to 23111 | 74 | `if blanket_global_reserve_enabled and operational_no_break_exception_cap(parsed) == 0:` |
| 23132 to 23218 | 87 | `for anchor_index, anchor in enumerate(skill_overlap_anchors):` |
| 23241 to 23314 | 74 | `for anchor_index, anchor in enumerate(repair_anchors[:3]):` |
| 23739 to 23905 | 167 | `for task_index, task in enumerate(tasks):` |
| 24057 to 24136 | 80 | `if joint_refinement and joint_search_pool and not completed_phases.get("joint_refinement_c` |
| 24264 to 24388 | 125 | `if not compliant and parsed.allow_no_break_exceptions and not completed_phases.get("except` |
| 24615 to 24868 | 254 | `if not candidates:` |
| 25255 to 25425 | 171 | `row = {` |

## 2. Functions by job

| Job | Functions | Lines |
|---|---|---|
| Run control and command line | 6 | 4,268 |
| Search phases (`run_*`) | 16 | 2,609 |
| Files, hashing and small utilities | 24 | 293 |
| Input reading and contract | 53 | 3,185 |
| Languages | 15 | 1,492 |
| Breaks | 36 | 2,178 |
| Preferences, OFF days and fixed requests | 12 | 493 |
| Shifts and rest | 22 | 369 |
| Metrics | 6 | 1,001 |
| Coverage, demand and capacity | 31 | 1,016 |
| Skeleton search (stage 1) | 25 | 1,812 |
| Joint, repair and neighbourhood search | 21 | 1,189 |
| Candidate selection | 23 | 1,196 |
| Output and publishing | 13 | 1,115 |
| Audit and self-check | 6 | 776 |
| Shift consistency polish | 5 | 257 |
| Tiers, exceptions and quality figures | 16 | 437 |
| Workbook styling | 4 | 70 |
| Time reserves and machine limits | 6 | 180 |
| Other helpers | 29 | 889 |

### Run control and command line

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `infeasibility_diagnosis_budget` | 21457 to 21466 | 10 | `run_case` |  | Seconds a no-schedule run may spend naming its cause. |
| `stage1_minimum_budget_seconds` | 21469 to 21476 | 8 | `run_case` |  | What a Stage-1 portfolio of ``portfolio_size`` profiles needs at the configured |
| `run_case` | 21479 to 25433 | 3955 | `main` |  |  |
| `build_arg_parser` | 25750 to 25861 | 112 | `main` |  |  |
| `cli_search_controls` | 26641 to 26659 | 19 | `main`, `run_case` |  | Translate the options the caller typed into engine parameter values. |
| `main` | 26662 to 26825 | 164 | `_build_business_outcome_core` |  |  |

### Search phases (`run_*`)

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `run_shortfall_pass` | 8772 to 8904 | 133 | `run_case` |  | Audit F-06: the best schedule that meets every PERSON rule, with every |
| `run_constraint_isolation` | 8907 to 8933 | 27 | `run_case` |  |  |
| `run_conflict_refinement` | 8936 to 8998 | 63 | `run_case` |  | Return a bounded family-level infeasibility core. |
| `run_qualified_language_break_certificate_repairs` | 9651 to 9784 | 134 | `run_case` |  | Repair language single-points-of-failure with complete legal break patterns. |
| `run_protected_floor_break_guard` | 12667 to 12734 | 68 | `run_case` |  | Spend protected Stage-2 time on floor-shaped skeletons before repair search. |
| `run_protected_target_champion_break_proof` | 12786 to 12885 | 100 | `run_case` |  | Try to convert the highest target skeletons to legal break schedules. |
| `run_adaptive_decomposed_joint_optimizer` | 17830 to 18472 | 643 | `run_cap_feasible_target_recovery_phase`, `run_case` |  | RC4.4 adaptive decomposed joint optimizer. |
| `run_break_load_feedback` | 18496 to 18606 | 111 | `run_case` |  | Feed the break load Stage 2 left on under-target intervals back to Stage 1. |
| `run_coordinated_shift_off_break_loop` | 18609 to 18875 | 267 | `run_case` |  | Transaction-safe repair across clean, near-feasible and exception pools. |
| `run_logic_based_break_cut_feedback` | 18961 to 19140 | 180 | `run_case` |  | Feed break evidence back through progressive, isolatable master cuts. |
| `run_zero_exception_recovery_phase` | 19330 to 19511 | 182 | `run_case` |  | Search beyond positive diagnostic minima and recover within the workbook exception cap. |
| `run_day_neighbourhood_break_search` | 19697 to 19893 | 197 | `run_break_load_feedback`, `run_case` |  | Improve the best compliant candidates' breaks one day at a time. |
| `run_post_break_repair_phase` | 20582 to 20772 | 191 | `run_case` |  | Late repair for compliant, near-feasible, and exception candidates. |
| `run_cap_feasible_target_recovery_phase` | 20865 to 20952 | 88 | `run_case` |  | Recover target KPIs around a proven within-cap language-break anchor. |
| `run_rc8_best_before_break_recovery` | 20984 to 21098 | 115 | `run_case` |  | Give the current-run BEST BEFORE skeleton a dedicated full-width break lane. |
| `run_target_lock_recovery_phase` | 21101 to 21210 | 110 | `run_case` |  | Maximize target, lock it, then recover floor quality for the active pool. |

### Files, hashing and small utilities

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `norm` | 260 to 263 | 4 | `_alias_key`, `_apply_preference_mapping`, `_authored_language_windows`, `_consistency_greedy_swaps` +66 | 1 file |  |
| `safe_name` | 266 to 267 | 2 | `discover_validated_fallback_candidates`, `run_case`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `normalized_output_prefix` | 270 to 280 | 11 | `case_identity_warnings`, `cleanup_stale_run_outputs`, `run_case` |  |  |
| `to_float` | 323 to 331 | 9 | `_optional_instruction_minutes`, `load_validated_fallback_candidate`, `parse_input` |  |  |
| `strict_float` | 334 to 362 | 29 | `_detect_interval_minutes`, `_parse_break_segments`, `_parse_break_sets_by_shift_length`, `_parse_coverage_split` +4 |  | Parse a numeric workbook value without converting bad text to zero. |
| `yes` | 365 to 369 | 5 | `_parse_duration_set`, `_parse_fixed_nesting`, `_parse_language_rules`, `blank_requirement_mode` +2 |  |  |
| `tri_state` | 372 to 378 | 7 | `parse_input` |  |  |
| `minute_in_inclusive_window` | 394 to 400 | 7 | `add_half_hour_twins`, `shift_start_contract_allows` |  |  |
| `minute_of_day` | 424 to 443 | 20 | `_detect_interval_minutes`, `_discover_requirement_sheet`, `_parse_coverage_split`, `_parse_language_rules` +5 |  |  |
| `ceil_units` | 511 to 512 | 2 | `build_skeleton`, `coverage_hit_threshold_units`, `critical_exception_cells`, `global_zero_exception_break_reserve_requirements` +1 |  |  |
| `ensure_parent` | 568 to 569 | 2 | `atomic_save_workbook`, `run_case`, `write_csv`, `write_json` +1 |  |  |
| `git_repository_identity` | 572 to 602 | 31 | `run_case` |  | Return portable Git provenance without making Git a runtime dependency. |
| `write_json` | 605 to 609 | 5 | `main`, `publish_business_outcome`, `publish_recovery_checkpoint`, `record_unexpected_run_failure` +3 |  |  |
| `write_csv` | 612 to 623 | 12 | `_augment_summary_with_business_outcome`, `record_unexpected_run_failure`, `run_case` |  | Atomically write a CSV so stale/partial leaderboard files are never published. |
| `sha256_file` | 626 to 631 | 6 | `benchmark_provenance`, `run_case`, `verify_xlsx` |  |  |
| `canonical_hash` | 634 to 636 | 3 | `benchmark_provenance`, `candidate_lineage_id`, `capacity_diagnostics`, `logic_based_break_feasibility_cut_plan` +3 | 1 file |  |
| `verify_xlsx` | 639 to 664 | 26 | `atomic_save_workbook`, `run_case` |  | Reopen the XLSX as ZIP and workbook; return a release-verification record. |
| `atomic_save_workbook` | 667 to 677 | 11 | `write_before_break_workbook`, `write_output_workbook` |  | Save to a sibling temporary file, verify, then atomically publish. |
| `normalize_language_window_mode` | 3417 to 3445 | 29 | `parse_input`, `run_case` |  | How the Language Setup Coverage Start/End bounds working hours. |
| `normalize_language_window_shift_rule` | 3454 to 3462 | 9 | `parse_input` |  | Phase AQ (owner, 2026-10-21): what a Language Working Window limits. START is the default and what t |
| `normalize_run_stage` | 3651 to 3659 | 9 | `parse_input` |  | Map a workbook Run Stage cell to a canonical stage, or None if unset. |
| `normalize_run_depth` | 3662 to 3666 | 5 | `parse_input` |  | Map a workbook Run Depth cell to a canonical depth, or None if unset. |
| `import_cp_sat` | 5202 to 5207 | 6 | `_consistency_swap_model`, `build_skeleton`, `dnbs_day_neighbourhood_model`, `run_day_neighbourhood_break_search` +3 | 2 files |  |
| `configure_solver_limits` | 5262 to 5304 | 43 | `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Apply the two native CP-SAT limits the engine otherwise leaves at default. |

### Input reading and contract

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `parse_time_window` | 381 to 391 | 11 | `parse_input` |  |  |
| `blank_requirement_mode` | 413 to 421 | 9 | `parse_input` |  |  |
| `_sheet_by_alias` | 1238 to 1243 | 6 | `_apply_preference_mapping`, `_discover_requirement_sheet`, `_discover_setup_sheet`, `_fallback_no_break_evidence` +11 | 1 file |  |
| `_discover_setup_sheet` | 1246 to 1263 | 18 | `synchronize_contract_metadata` |  | Find an optional presentation/setup sheet without program-name aliases. |
| `_instruction_pairs` | 1273 to 1298 | 26 | `_instruction_duplicates`, `_instruction_map` |  | (row, label, value) pairs on an Instructions-style sheet. |
| `_instruction_map` | 1301 to 1305 | 5 | `parse_input` | 1 file |  |
| `_instruction_duplicates` | 1308 to 1318 | 11 | `parse_input` |  | Labels given more than once on one sheet with DIFFERENT values. |
| `_parse_search_controls` | 1413 to 1471 | 59 | `parse_input` |  | Read the search controls a workbook actually states, and only those. |
| `_instruction_get` | 1474 to 1478 | 5 | `_detect_interval_minutes`, `_discover_requirement_sheet`, `_optional_instruction_minutes`, `_parse_break_segments` +6 |  |  |
| `_terms_in_distinct_cells` | 1556 to 1574 | 19 | `_find_header_row` |  | True when every term can be matched to a DIFFERENT cell of the row. |
| `_find_header_row` | 1577 to 1628 | 52 | `_apply_preference_mapping`, `_discover_requirement_sheet`, `_fallback_no_break_evidence`, `_parse_coverage_split` +6 |  | Locate the header row of a sheet by the terms it must carry. |
| `_is_day_header` | 1631 to 1642 | 12 | `_day_columns` |  | True when a normalized header names this weekday and nothing else. |
| `_day_columns` | 1645 to 1693 | 49 | `_discover_requirement_sheet`, `_fallback_no_break_evidence`, `_find_header_row`, `_parse_fixed_nesting` +4 |  | Bind each weekday to its column by header text. |
| `_parse_roster` | 1731 to 1820 | 90 | `load_seed_skeleton`, `parse_input` |  |  |
| `_parse_departed_acknowledgements` | 1823 to 1835 | 13 | `parse_input` |  | Names the scheduler has explicitly declared as no longer on the roster. |
| `_report_unmatched_name` | 1838 to 1881 | 44 | `_parse_fixed_nesting`, `_parse_preferences` |  | Report an unmatched row, hard unless it asserts nothing or was acknowledged. |
| `_sheet_has_named_rows` | 1884 to 1888 | 5 | `_parse_fixed_nesting`, `_parse_preferences` |  | True when any row under the header carries a name, i.e. the sheet asserts something. |
| `_report_missing_day_columns` | 1891 to 1896 | 6 | `_parse_fixed_nesting`, `_parse_preferences`, `parse_input` |  |  |
| `_parse_preferences` | 1899 to 1991 | 93 | `parse_input` |  |  |
| `_parse_fixed_nesting` | 2045 to 2113 | 69 | `parse_input` |  |  |
| `_parse_duration_set` | 2116 to 2142 | 27 | `parse_input` |  |  |
| `parse_11h_associate_limit` | 2148 to 2164 | 17 | `parse_input` |  | Phase H: blank = no limit; a whole number >= 1 = at most that many |
| `add_11h_associate_limit` | 2167 to 2174 | 8 | `build_skeleton`, `solve_joint_shift_off_language_break_refinement` |  | Phase H: at most "Max 11H/3OFF Associates" associates work the 11H/3OFF |
| `forced_long_mode_associates` | 2177 to 2191 | 15 | `validate_input_contract` |  | Associates who can only work the 11H/3OFF pattern: every legal shift is |
| `long_mode_summary_rows` | 2194 to 2202 | 9 | `write_output_workbook` |  | Production Summary rows for the 11H/3OFF pattern; none when it is off. |
| `add_half_hour_twins` | 2205 to 2226 | 22 | `parse_input` |  | Phase F: every on-the-hour shift gets a twin starting 30 minutes later, |
| `half_hour_fallback_usage` | 2229 to 2236 | 8 | `half_hour_summary_rows` |  | Phase F output marking: the shift-days of a week that use a :30 twin. |
| `half_hour_summary_rows` | 2239 to 2250 | 12 | `write_output_workbook` |  | Production Summary rows marking :30 twins; none when the switch is off, |
| `_parse_shifts` | 2253 to 2301 | 49 | `parse_input` |  |  |
| `_discover_requirement_sheet` | 2304 to 2327 | 24 | `_parse_requirement_table` | 1 file |  |
| `_detect_interval_minutes` | 2333 to 2370 | 38 | `_parse_requirement_table` |  | Interval granularity: the workbook's value when it states one. |
| `_parse_requirement_table` | 2385 to 2508 | 124 | `parse_input` |  |  |
| `_split_languages` | 2511 to 2512 | 2 | `_parse_language_rules` |  |  |
| `_alias_key` | 2523 to 2530 | 8 | `_parse_language_days` |  | Normalise for alias matching: lowercase, alphanumerics only. |
| `_parse_language_days` | 2533 to 2582 | 50 | `_parse_language_rules` |  | Parse Language Setup Coverage Days; invalid text must not mean all days. |
| `_parse_language_rules` | 2585 to 2703 | 119 | `parse_input` |  |  |
| `_parse_coverage_split` | 2930 to 3040 | 111 | `parse_input` |  | Read the optional Coverage Split sheet. |
| `_parse_break_segments` | 3046 to 3114 | 69 | `parse_input` |  | Break structure exactly as the workbook states it. |
| `_parse_break_sets_by_shift_length` | 3164 to 3208 | 45 | `parse_input` |  | Audit F-20: per-shift-length break sets stated in the workbook. |
| `_optional_instruction_minutes` | 3271 to 3276 | 6 | `_parse_break_window_controls` |  |  |
| `_parse_break_window_controls` | 3279 to 3385 | 107 | `parse_input` |  | Parse instruction-driven break placement windows and flexible spacing. |
| `_coerce_language_window_entries` | 3465 to 3479 | 15 | `_authored_language_windows`, `_input_contract_payload_core` | 1 file | Normalize legacy single-window and current multi-window values. |
| `_authored_language_windows` | 3482 to 3492 | 11 | `associate_language_windows`, `language_working_window_violations` |  | Return all authored windows before mode-specific filtering. |
| `parse_input` | 3669 to 4477 | 809 | `run_case`, `selfcheck` | 12 files |  |
| `input_contract_payload` | 4480 to 4494 | 15 | `canonical_contract_snapshot` |  |  |
| `_input_contract_payload_core` | 4497 to 4702 | 206 | `input_contract_payload` |  |  |
| `canonical_contract_snapshot` | 4705 to 4707 | 3 | `benchmark_provenance`, `run_case` | 1 file | Single normalized contract object used by hashes, resume identity and QA. |
| `validate_input_contract` | 4710 to 5175 | 466 | `run_case`, `selfcheck` | 2 files | Fail before CP-SAT when the workbook contract is malformed or provably impossible. |
| `case_identity_warnings` | 5178 to 5199 | 22 | `run_case` |  | Warn when an explicit workbook program identity conflicts with the case/output label. |
| `discover_validated_fallback_candidates` | 7731 to 7776 | 46 | `run_case` |  | Revalidate explicit and bundled schedule workbooks as safe incumbents. |
| `split_candidate_pool` | 12977 to 13005 | 29 | `merge_candidate_pools_with_safe_incumbent`, `run_case` |  |  |
| `synchronize_contract_metadata` | 14652 to 14707 | 56 | `write_output_workbook` |  | Replace stale workbook labels with the canonical parsed contract. |
| `read_production_summary_metadata` | 21357 to 21391 | 35 | `benchmark_provenance` |  | Read provenance fields from a previously exported production workbook. |

### Languages

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `associate_language_windows` | 3495 to 3505 | 11 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `associate_language_window`, `build_skeleton` +2 |  | Return all applicable working windows for one associate-day. |
| `associate_language_window` | 3508 to 3513 | 6 |  |  | Backward-compatible first-window accessor for legacy callers/tests. |
| `shift_within_language_window` | 3516 to 3544 | 29 | `language_window_allows` |  | True when the shift's START falls inside the window (with ``whole_shift`` its END must too: Phase AQ |
| `language_window_allows` | 3547 to 3550 | 4 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `fixed_requests_outside_language_windows` +2 |  | ``shift_within_language_window`` under the input's Language Working Window Shift Rule (Phase AQ). |
| `shift_overlaps_required_language_for_noneligible` | 3553 to 3576 | 24 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement` +2 |  | Return the first required language rule this associate cannot cover. |
| `language_working_window_violations` | 3579 to 3617 | 39 | `run_case` |  | Shifts scheduled outside their language's window, reported either way. |
| `fixed_requests_outside_language_windows` | 3620 to 3648 | 29 | `run_case`, `validate_input_contract` | 1 file | Fixed shift requests that start outside their associate's enforced |
| `language_eligible` | 6228 to 6229 | 2 | `_consistency_cell_allowed`, `_max_possible_raw_at_qslot`, `adaptive_operator_focus_cells`, `break_resilience_diagnostics` +16 |  |  |
| `language_rules_at` | 6232 to 6274 | 43 | `_rule_active_qslots_for_day`, `build_skeleton`, `calculate_metrics`, `capacity_diagnostics` +8 |  | Rules in force for the quarter-hour slot beginning at `minute`. |
| `language_operational_reserve_target` | 6277 to 6286 | 10 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return the qualified after-break staffing target for a required language. |
| `language_reserve_status` | 6289 to 6294 | 6 | `calculate_metrics` |  |  |
| `language_rule_key` | 9390 to 9400 | 11 | `break_resilience_diagnostics`, `build_skeleton`, `language_break_overlap_repair_plan` |  | Return a stable, client-neutral identity for a directional skill rule. |
| `language_break_overlap_repair_plan` | 9403 to 9592 | 190 | `logic_based_break_feasibility_cut_plan`, `run_case`, `run_zero_exception_recovery_phase` |  | Build a sparse, pattern-aware same-skill overlap repair plan. |
| `qualified_language_break_certificate_targets` | 9594 to 9648 | 55 | `run_qualified_language_break_certificate_repairs` |  | Resolve language-blocked exception rows into exact associate-day targets. |
| `solve_joint_shift_off_language_break_refinement` | 16655 to 17687 | 1033 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Jointly choose shift, OFF/leave state, language coverage, and breaks. |

### Breaks

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `break_attempt_key` | 1110 to 1130 | 21 | `run_case` |  | Stable replay/cache key for every materially different break model. |
| `serialize_break_candidate` | 1133 to 1149 | 17 | `publish_recovery_checkpoint`, `run_case`, `save_candidate_pool_checkpoint` |  |  |
| `deserialize_break_candidate` | 1152 to 1175 | 24 | `load_candidate_pool_checkpoint`, `run_case` | 1 file |  |
| `_apply_associate_break_counts` | 3120 to 3161 | 42 | `parse_input` |  | Phase BL (owner, 2026-11-07): a Schedule row's ``Breaks`` N gives the shift length on that row the f |
| `break_segments_for` | 3254 to 3264 | 11 | `break_quarters_for`, `build_break_constraint_isolation_report`, `generate_break_patterns`, `load_validated_fallback_candidate` +1 |  | The break set for a shift of ``duration_min`` minutes (audit F-20). |
| `break_quarters_for` | 3267 to 3268 | 2 | `break_capacity_headcount_requirement`, `break_resilience_diagnostics`, `build_skeleton`, `capacity_diagnostics` +4 |  |  |
| `break_concurrency_weight` | 5898 to 5919 | 22 | `solve_breaks` |  | Penalty for one interval of excess concurrent breaks. |
| `maximum_concurrent_breaks` | 5922 to 5929 | 8 | `break_capacity_headcount_requirement`, `calculate_metrics`, `dnbs_day_neighbourhood_model`, `solve_breaks` |  | Hard concurrent-break ceiling while preserving at least one working associate. |
| `_fallback_no_break_evidence` | 7321 to 7457 | 137 | `load_validated_fallback_candidate` |  | Reconstruct audited no-break exception cells from an exported workbook. |
| `_generic_break_patterns` | 9044 to 9137 | 94 | `build_break_constraint_isolation_report`, `generate_break_patterns`, `validate_input_contract` |  | Generate legal 15-minute break combinations with soft spacing quality. |
| `generate_break_patterns` | 9139 to 9152 | 14 | `build_skeleton`, `deserialize_break_candidate`, `language_break_overlap_repair_plan`, `selfcheck` +2 |  |  |
| `selected_break_spacing_rows` | 9156 to 9200 | 45 | `load_validated_fallback_candidate`, `run_day_neighbourhood_break_search`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return auditable spacing deviations for selected break patterns. |
| `build_break_constraint_isolation_report` | 9245 to 9303 | 59 | `run_case` |  | Summarize break-model search coverage and likely blockers. |
| `after_break_raw_expression` | 9787 to 9808 | 22 | `solve_breaks` |  | A NEW ``headcount - breaks`` expression for one quarter, built for one use. |
| `solve_breaks` | 9811 to 10481 | 671 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `minimum_exception_diagnostic`, `prove_selected_exceptions` +11 | 3 files |  |
| `break_qslots` | 10536 to 10548 | 13 | `break_damage_focus_cells`, `calculate_metrics`, `distinct_skill_allocation_audit`, `structural_schedule_audit` |  |  |
| `break_resilience_diagnostics` | 11832 to 12002 | 171 | `capacity_diagnostics` |  | Actionable pre-solver diagnostics for mandatory breaks and skills. |
| `select_protected_floor_break_anchors` | 12642 to 12664 | 23 | `run_protected_floor_break_guard` |  | Return production skeletons whose before-break floor shape deserves Stage-2 time. |
| `select_protected_target_break_anchors` | 12767 to 12783 | 17 | `run_protected_target_champion_break_proof` |  |  |
| `before_break_leaderboard_rows` | 13085 to 13157 | 73 | `run_case` |  | Build the canonical leaderboard rows used by success and failure artifacts. |
| `candidate_selection_breakdown` | 13191 to 13223 | 33 | `run_case` |  | Explain the universal target-protected champion ordering. |
| `break_solution_key` | 13326 to 13335 | 10 | `_quality_delta`, `acquire_early_safe_incumbent`, `adaptive_nondominated_anchor_pool`, `publish_recovery_checkpoint` +5 | 1 file | Target-driven deterministic ordering for otherwise valid final candidates. |
| `default_break_objective_modes` | 13338 to 13354 | 17 | `acquire_early_safe_incumbent`, `run_case` |  | Workbook-target-driven break objective order. |
| `dedupe_break_candidates` | 13357 to 13370 | 14 | `adaptive_nondominated_anchor_pool`, `bootstrap_exception_anchors_for_joint`, `choose_repair_anchors`, `discover_validated_fallback_candidates` +16 |  |  |
| `break_damage_focus_cells` | 13436 to 13474 | 39 | `adaptive_operator_focus_cells`, `derive_adaptive_feedback_cuts`, `run_adaptive_decomposed_joint_optimizer`, `run_coordinated_shift_off_break_loop` +2 |  | Associate-days whose selected breaks caused target/floor losses. |
| `break_release_diagnostic_only` | 14151 to 14183 | 33 | `select_export_candidates` |  | Stage-2 counterpart of ``skeleton_release_diagnostic_only``. |
| `ensure_before_break_metrics` | 14186 to 14206 | 21 | `protected_floor_anchor_key`, `run_case`, `run_protected_target_champion_break_proof`, `run_rc8_best_before_break_recovery` +6 | 1 file | Attach canonical no-break metrics to a feasible skeleton exactly once. |
| `break_capacity_headcount_requirement` | 14287 to 14402 | 116 | `before_break_leaderboard_rows`, `run_case` |  | How much headcount the schedule needs for breaks to have somewhere to go. |
| `write_before_break_workbook` | 14710 to 14800 | 91 | `run_case` |  | Export the independently strongest shift/OFF skeleton before breaks. |
| `skeleton_breakability_priority_key` | 15616 to 15633 | 18 | `run_case`, `run_logic_based_break_cut_feedback` |  | Prioritize skeletons that are already within the workbook exception cap. |
| `operational_no_break_exception_cap` | 15766 to 15770 | 5 | `build_skeleton`, `candidate_satisfies_explicit_kpi_locks`, `cap_feasible_target_recovery_decision`, `joint_candidate_within_operational_cap` +7 |  | Return the only exception cap that any C3 integrated output may use. |
| `break_load_by_interval` | 18482 to 18493 | 12 | `run_break_load_feedback` |  | Coverage units breaks removed per interval (before_effective - after_effective, |
| `logic_based_break_feasibility_cut_plan` | 18879 to 18928 | 50 | `run_logic_based_break_cut_feedback` |  | Build sparse master-model feedback from a fixed-skeleton break subproblem. |
| `global_zero_exception_break_reserve_requirements` | 19142 to 19181 | 40 | `run_case` |  | Return unanchored break-reserve raw staffing requirements. |
| `zero_exception_break_reserve_plan` | 19184 to 19327 | 144 | `logic_based_break_feasibility_cut_plan`, `run_zero_exception_recovery_phase` |  | Translate certified exception bottlenecks into universal staffing reserve constraints. |
| `_business_break_blockers` | 25929 to 25977 | 49 | `_build_business_outcome_core` |  |  |

### Preferences, OFF days and fixed requests

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_apply_preference_mapping` | 1997 to 2042 | 46 | `parse_input` |  | Translate site-specific Preference/Fixed codes via an optional mapping sheet. |
| `_preference_tokens` | 5763 to 5765 | 3 | `_extended_preference_kind` |  |  |
| `_extended_preference_kind` | 5768 to 5785 | 18 | `preference_kind` |  |  |
| `preference_kind` | 5788 to 5798 | 11 | `_consistency_swap_model`, `_parse_preferences`, `aggregate_pattern_mix_guidance`, `associate_day_eligible_shifts` +15 |  |  |
| `required_off_days` | 5819 to 5833 | 15 | `validate_schedule` |  | How many OFF days the weekly rule asks of this associate. |
| `separate_off_in_preference` | 5837 to 5852 | 16 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement`, `validate_schedule` |  | Whether this associate's own request rows name hard OFF days that are not next to each other (Phase  |
| `add_weekly_off_rule` | 5854 to 5880 | 27 | `build_skeleton`, `solve_joint_shift_off_language_break_refinement` |  | The weekly OFF rule, shared by every model that decides OFF days. ``owed`` (Phase BL) is the Schedul |
| `_prefixed_metric` | 13238 to 13250 | 13 | `_candidate_quality_tuple`, `before_break_leaderboard_rows`, `candidate_selection_breakdown` | 1 file | Read ``{prefix}_{key}`` when present, else fall back to the bare key. |
| `target_priority_tradeoff_select` | 13516 to 13725 | 210 | `select_export_candidates` |  | Choose the final schedule from the workbook target, not a fixed 80% anchor. |
| `add_preference_export` | 20299 to 20306 | 8 | `run_case` |  | Publish an applied preference swap as PREFERENCE_CANDIDATE, beside the selected schedule (F-35: neve |
| `preference_distance` | 20452 to 20459 | 8 | `preference_swap_polish` |  | Minutes between associate a's Preference shift on day d and the shift worked (0 when there is no shi |
| `preference_swap_polish` | 20462 to 20579 | 118 | `run_case` |  | Phase BE: same-day swaps between interchangeable associates that bring both closer to their Preferen |

### Shifts and rest

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `shift_start_contract_allows` | 403 to 410 | 8 | `_parse_shifts`, `structural_schedule_audit`, `validate_input_contract` |  |  |
| `hhmm` | 446 to 448 | 3 | `_contract_display_rows`, `_parse_requirement_table`, `_parse_shifts`, `add_half_hour_twins` +17 | 1 file |  |
| `shift_parts` | 497 to 508 | 12 | `_consistency_swap_model`, `_parse_preferences`, `_parse_shifts`, `build_skeleton` +5 |  |  |
| `_time_column` | 2373 to 2382 | 10 | `_parse_requirement_table` |  |  |
| `rest_compatible` | 5883 to 5885 | 3 | `_consistency_row_allowed`, `_consistency_swap_model`, `build_skeleton`, `solve_joint_shift_off_language_break_refinement` +2 |  |  |
| `previous_saturday_compatible` | 5888 to 5895 | 8 | `_consistency_row_allowed`, `_consistency_swap_model`, `associate_day_eligible_shifts`, `build_skeleton` +4 |  |  |
| `shift_covers_week_qslot` | 6012 to 6014 | 3 | `_max_possible_raw_at_qslot`, `_shift_interval_cover_fraction`, `_shift_overlap_qslots`, `aggregate_pattern_mix_guidance` +5 |  |  |
| `next_sunday_own_qslot` | 6052 to 6054 | 3 | `build_skeleton`, `calculate_metrics`, `cyclic_next_sunday_coverage_vars`, `cyclic_next_sunday_covering_occurrences` +3 |  | Map a pseudo day-eight quarter to the repeated Sunday quarter. |
| `previous_saturday_covers_qslot` | 6199 to 6205 | 7 | `calculate_metrics`, `prior_constant_cover`, `prior_covering_associates`, `structural_schedule_audit` |  |  |
| `coverage_vars_at_qslot` | 6310 to 6324 | 15 | `build_skeleton`, `coverage_vars`, `cyclic_next_sunday_coverage_vars` |  |  |
| `shift_day_demand_fit` | 6345 to 6387 | 43 | `demand_fit_blocked`, `structural_schedule_audit` |  | Demand shape for one (day, shift) pair, memoised per parsed contract. |
| `_shift_day_demand_fit_uncached` | 6390 to 6417 | 28 | `shift_day_demand_fit` |  |  |
| `scheduled_covering_qslot` | 9010 to 9015 | 6 | `adaptive_operator_focus_cells`, `break_capacity_headcount_requirement`, `break_damage_focus_cells`, `calculate_metrics` +9 |  |  |
| `shift_length_allows` | 11726 to 11732 | 7 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `shift_length_failures` +2 |  | Phase BL (owner, 2026-11-07): an associate whose Schedule row names a Shift Length may only work shi |
| `shift_length_failures` | 11735 to 11746 | 12 | `validate_schedule` |  | Phase BL: scheduled shifts whose length is not the one the associate's row names. |
| `_max_possible_raw_at_qslot` | 11789 to 11811 | 23 | `capacity_diagnostics` |  |  |
| `_rule_active_qslots_for_day` | 11815 to 11825 | 11 | `break_resilience_diagnostics` |  |  |
| `_shift_overlap_qslots` | 11828 to 11829 | 2 | `break_resilience_diagnostics` |  |  |
| `_shift_interval_cover_fraction` | 15997 to 16004 | 8 | `donor_receiver_shift_plan` |  |  |
| `shift_consistency_cost` | 19945 to 19953 | 9 | `_consistency_greedy_swaps`, `_consistency_swap_model`, `shift_consistency_polish`, `shift_consistency_summary` |  | (distinct start times, minutes of start movement between consecutive worked days). |
| `shift_consistency_summary` | 19956 to 19965 | 10 | `shift_consistency_polish` |  |  |
| `shift_consistency_polish` | 20309 to 20446 | 138 | `parse_input`, `run_case` |  | Return a more consistent schedule, or the original with the reason it was kept. |

### Metrics

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `require_metric` | 59 to 78 | 20 | `protected_floor_anchor_key`, `run_case`, `run_protected_target_champion_break_proof`, `select_export_candidates` +4 |  | Read a decision metric, failing loudly when it is absent. |
| `fractional_safe_overage_metrics` | 10670 to 10712 | 43 | `calculate_metrics` |  | Classify overage without penalizing indivisible whole-associate staffing. |
| `calculate_metrics` | 10799 to 11714 | 916 | `ensure_before_break_metrics`, `load_validated_fallback_candidate`, `preference_swap_polish`, `run_break_load_feedback` +11 | 3 files | Rebuild canonical before/after coverage truth from the final schedule. |
| `compact_metric_surface` | 11718 to 11723 | 6 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `discover_validated_fallback_candidates`, `publish_recovery_checkpoint` +8 |  | Keep scalar metrics while excluding only bulky row/detail collections. |
| `dnbs_metrics_no_worse` | 19565 to 19571 | 7 | `run_break_load_feedback`, `run_day_neighbourhood_break_search` |  | True when after_target strictly rose and no guarded metric got worse. |
| `_consistency_metrics_no_worse` | 20003 to 20011 | 9 | `preference_swap_polish`, `shift_consistency_polish` |  |  |

### Coverage, demand and capacity

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `cyclic_active_window` | 451 to 494 | 44 | `structural_schedule_audit` |  | Describe a day's active demand without flattening an overnight block. |
| `scaled_effective_factor` | 518 to 527 | 10 | `dnbs_day_neighbourhood_model`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Integer effective-FTE multiplier aligned with the canonical evaluator. |
| `scaled_coverage_threshold` | 530 to 537 | 8 | `dnbs_day_neighbourhood_model`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return the exact scaled average-coverage threshold for an interval. |
| `coverage_hit_threshold_units` | 540 to 565 | 26 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `critical_exception_cells` |  | Hit threshold for one interval in Stage-1 / guide coverage units |
| `coverage_split_required_headcount` | 2711 to 2724 | 14 | `build_skeleton`, `calculate_metrics`, `coverage_split_capacity_report`, `solve_breaks` |  | Grossed-up headcount one group must field for an interval it owns. |
| `coverage_split_capacity_report` | 2727 to 2886 | 160 | `run_case` |  | Can each owning group actually field what its window demands? |
| `merge_coverage_split_rules` | 2889 to 2921 | 33 | `_consistency_cell_allowed`, `build_skeleton`, `calculate_metrics`, `coverage_split_capacity_report` +1 |  | Groups whose windows overlap COVER THE INTERVAL TOGETHER. |
| `coverage_split_rules_at` | 2924 to 2927 | 4 | `_consistency_cell_allowed`, `build_skeleton`, `calculate_metrics`, `solve_breaks` |  |  |
| `volume_weight` | 3211 to 3228 | 18 | `build_skeleton`, `solve_breaks` |  | Audit F-28: an interval's miss weight, scaled by its requirement when the |
| `apply_coverage_objective_override` | 3234 to 3251 | 18 | `run_case` |  | Which coverage measure the run uses, and where it came from (audit F-28). |
| `next_sunday_raw_cap` | 5932 to 5951 | 20 | `build_skeleton`, `calculate_metrics`, `language_break_overlap_repair_plan`, `solve_breaks` +2 |  | Integer-safe raw cap that never conflicts with a harder opening/language minimum. |
| `next_sunday_raw_requirement` | 5954 to 5961 | 8 | `next_sunday_adjacent_raw_limit` |  | Minimum integer raw staffing for one Next-Sunday interval. |
| `next_sunday_adjacent_raw_limit` | 5964 to 5979 | 16 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Demand-aware adjacent raw-HC movement limit. |
| `whole_week_raw_requirement` | 5982 to 5987 | 6 | `whole_week_adjacent_raw_limit`, `whole_week_raw_cap` |  |  |
| `whole_week_raw_cap` | 5990 to 6002 | 13 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `whole_week_adjacent_raw_limit` | 6005 to 6009 | 5 | `build_skeleton`, `calculate_metrics`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `next_sunday_spill_quarters` | 6017 to 6025 | 9 | `calculate_metrics`, `next_sunday_capacity_preflight`, `next_sunday_interval_quarters` |  | Maximum legal Saturday spill into the following Sunday, in 15-minute slots. |
| `next_sunday_interval_quarters` | 6028 to 6049 | 22 | `break_damage_focus_cells`, `build_skeleton`, `calculate_metrics`, `critical_exception_cells` +4 |  | Return every mirrored Sunday quarter inside the Saturday spill horizon. |
| `next_sunday_interval_indices` | 6057 to 6058 | 2 |  |  |  |
| `next_sunday_capacity_preflight` | 6078 to 6196 | 119 | `validate_input_contract` |  | Optimistic proof that Saturday assignments can protect next Sunday early demand. |
| `opening_intervals_for_day` | 6208 to 6225 | 18 | `build_skeleton`, `calculate_metrics`, `capacity_diagnostics`, `critical_exception_cells` +5 |  |  |
| `coverage_vars` | 6327 to 6329 | 3 | `build_skeleton` |  |  |
| `cyclic_next_sunday_coverage_vars` | 6332 to 6342 | 11 | `build_skeleton` |  | Saturday carry-out plus the repeated Sunday decision variables. |
| `demand_fit_blocked` | 6420 to 6432 | 13 | `_consistency_cell_allowed`, `associate_day_eligible_shifts`, `build_skeleton`, `donor_receiver_shift_plan` +3 |  |  |
| `coverage_quality_limits` | 6853 to 6869 | 17 | `_candidate_quality_tuple`, `aggregate_pattern_mix_guidance`, `build_skeleton`, `candidate_selection_breakdown` +4 |  | Return release-quality limits with safe defaults for synthetic replays. |
| `cyclic_next_sunday_covering_occurrences` | 9018 to 9026 | 9 | `calculate_metrics`, `cyclic_next_sunday_covering` |  | Return (associate, start_day, shift_index, source_qslot) for cyclic coverage. |
| `cyclic_next_sunday_covering` | 9029 to 9032 | 4 | `critical_exception_cells`, `language_break_overlap_repair_plan`, `solve_breaks` |  |  |
| `capacity_diagnostics` | 12004 to 12283 | 280 | `run_case`, `selfcheck` |  | Deterministic fail-fast feasibility diagnostics before CP-SAT. |
| `coverage_rebalance_focus_cells` | 13477 to 13513 | 37 | `adaptive_operator_focus_cells`, `run_adaptive_decomposed_joint_optimizer`, `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` +1 |  | Find donor overage cells and receiver shortage neighborhoods for transaction-safe repair. |
| `coverage_first_stage2_anchor_candidates` | 15636 to 15659 | 24 | `run_case` |  | Return production skeletons eligible for the protected Stage-2 anchor. |
| `phase_c_c2_overage_transaction_gate` | 16188 to 16232 | 45 | `run_coordinated_shift_off_break_loop` |  | Require strict overage improvement with complete multi-tier retention. |

### Skeleton search (stage 1)

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `skeleton_fingerprint` | 1078 to 1079 | 2 | `break_attempt_key`, `candidate_lineage_id`, `logic_based_break_feasibility_cut_plan`, `run_case` +6 |  |  |
| `serialize_skeleton` | 1082 to 1092 | 11 | `save_skeleton_checkpoint`, `serialize_break_candidate` |  |  |
| `deserialize_skeleton` | 1095 to 1107 | 13 | `deserialize_break_candidate`, `load_skeleton_checkpoint` |  |  |
| `save_skeleton_checkpoint` | 1178 to 1183 | 6 | `run_case` |  |  |
| `load_skeleton_checkpoint` | 1186 to 1192 | 7 | `run_case` |  |  |
| `rotate_stage1_profiles` | 5345 to 5355 | 11 | `run_case` |  | The profile order for seed `seed_index` of `seed_count`; see STAGE1_PROFILE_ROTATION. |
| `skeleton_profiles` | 6435 to 6626 | 192 | `rotate_stage1_profiles`, `run_break_load_feedback`, `run_case`, `run_shortfall_pass` | 5 files | Universal target-aware profiles, led by release-quality convergence. |
| `stage1_starved_basis_profile` | 6748 to 6774 | 27 | `run_case` |  | The one profile to run when the portfolio cannot fund even its first. |
| `stage1_fundable_profile_count` | 6794 to 6808 | 15 | `run_case` |  | How many Stage-1 profiles a wall-clock window can pay for at full depth. |
| `stage1_slice_seconds` | 6811 to 6834 | 24 | `run_case` |  | Per-profile Stage-1 solver slice: fund depth, not width. |
| `aggregate_pattern_mix_guidance` | 6882 to 7246 | 365 | `run_case` |  | Solve a small aggregate MILP before named-associate CP-SAT. |
| `repair_profile` | 7248 to 7257 | 10 | `run_case`, `run_coordinated_shift_off_break_loop`, `run_logic_based_break_cut_feedback`, `run_post_break_repair_phase` +2 |  |  |
| `_empty_skeleton` | 7260 to 7261 | 2 | `build_skeleton` |  |  |
| `load_seed_skeleton` | 7264 to 7316 | 53 | `load_validated_fallback_candidate`, `run_case` | 1 file | Read schedule cells from any compatible workbook as a generic anchor seed. |
| `build_skeleton` | 7778 to 8708 | 931 | `run_break_load_feedback`, `run_case`, `run_conflict_refinement`, `run_constraint_isolation` +7 | 5 files |  |
| `pattern_map` | 10532 to 10533 | 2 | `break_qslots`, `candidate_lineage_id`, `dnbs_day_neighbourhood_model`, `selected_break_spacing_rows` +3 |  |  |
| `skeleton_release_diagnostic_only` | 14134 to 14148 | 15 | `coverage_first_stage2_anchor_candidates`, `protected_floor_anchor_key`, `run_case`, `select_best_before_skeleton` +4 |  | Return True for feasibility probes/warm-start anchors that must not win release. |
| `skeleton_exceeds_exception_cap` | 14209 to 14224 | 16 | `select_best_shippable_before_skeleton` |  | True when this skeleton PROVABLY cannot ship under the workbook's policy. |
| `select_best_shippable_before_skeleton` | 14227 to 14250 | 24 | `run_case` |  | The strongest before-break skeleton that could actually be delivered. |
| `select_best_before_skeleton` | 14405 to 14421 | 17 | `run_case`, `select_best_shippable_before_skeleton` |  | Select the independent hard-clean pre-break winner by workbook target. |
| `select_stage1_hint_skeleton` | 14424 to 14452 | 29 | `run_case` |  | Return the strongest safe Stage-1 hint without making hints a release gate. |
| `skeleton_quality_key` | 15605 to 15613 | 9 | `acquire_early_safe_incumbent`, `bootstrap_exception_anchors_for_joint`, `run_case`, `run_zero_exception_recovery_phase` +1 |  |  |
| `skeleton_hard_clean` | 15662 to 15669 | 8 | `acquire_early_safe_incumbent`, `load_validated_fallback_candidate`, `retain_zero_exception_diagnostic_candidate`, `run_break_load_feedback` +11 | 1 file |  |
| `dedupe_skeletons` | 15897 to 15908 | 12 | `bootstrap_exception_anchors_for_joint`, `run_case`, `run_logic_based_break_cut_feedback`, `run_qualified_language_break_certificate_repairs` +3 |  |  |
| `_consistency_skeleton` | 20019 to 20029 | 11 | `_consistency_greedy_swaps`, `preference_swap_polish`, `shift_consistency_polish` |  |  |

### Joint, repair and neighbourhood search

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `joint_memory_headroom` | 5231 to 5258 | 28 | `run_adaptive_decomposed_joint_optimizer`, `run_case` |  | Whether the machine can afford another joint shift+break model. |
| `joint_solve_kill_threshold_mb` | 5416 to 5417 | 2 | `isolated_cp_solve` |  |  |
| `_child_prepare_for_isolated_solve` | 5420 to 5444 | 25 | `isolated_cp_solve` |  | In the forked child: die with the parent, and be the OOM killer's first choice. |
| `isolated_cp_solve` | 5447 to 5579 | 133 | `isolated_cp_solver` |  | Run in_process_solve(model) in a forked, memory-watched child; see the block comment above. |
| `joint_solve_isolation_audit` | 5582 to 5600 | 19 | `run_case` |  | Every joint solve of this run: how it ran and how its child ended. |
| `isolated_cp_solver` | 5603 to 5620 | 18 | `solve_joint_shift_off_language_break_refinement` |  | A CpSolver whose Solve runs through isolated_cp_solve; otherwise the stock class. |
| `stage2_anchor_slice_seconds` | 6701 to 6742 | 42 | `run_case` |  | Time limit for the guaranteed Stage-2 anchor solve. |
| `protected_floor_anchor_key` | 12607 to 12639 | 33 | `select_protected_floor_break_anchors` |  | Lower-is-better key for deciding which skeleton deserves protected break time. |
| `target_anchor_key` | 12737 to 12764 | 28 | `select_protected_target_break_anchors` |  | Lower-is-better key for protected break proof of the target champion. |
| `repair_candidate_key` | 12937 to 12974 | 38 | `choose_repair_anchors`, `run_case`, `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  | Lower-is-better repair debt, then stronger target/floor quality. |
| `choose_repair_anchors` | 13008 to 13028 | 21 | `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  | Keep representation from clean, near-feasible, and exception pools. |
| `retain_search_only_diagnostic_joint_anchor` | 15721 to 15763 | 43 | `run_case` |  | Retain a feasible diagnostic assignment only as an integrated-search anchor. |
| `joint_candidate_within_operational_cap` | 15773 to 15774 | 2 | `run_adaptive_decomposed_joint_optimizer` |  |  |
| `mark_cap_descent_search_anchor` | 15794 to 15814 | 21 | `run_adaptive_decomposed_joint_optimizer` |  | Mark an above-cap integrated result as search-only, never releasable. |
| `donor_receiver_shift_plan` | 16007 to 16185 | 179 | `run_coordinated_shift_off_break_loop` |  | Build a bounded transaction-safe donor/receiver shift-target plan. |
| `adaptive_nondominated_anchor_pool` | 16350 to 16427 | 78 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Keep a diverse nondominated anchor set for adaptive refinement. |
| `derive_adaptive_feedback_cuts` | 16430 to 16515 | 86 | `run_adaptive_decomposed_joint_optimizer` | 1 file | Translate break/coverage damage into replayable master feedback cuts. |
| `adaptive_operator_focus_cells` | 16518 to 16598 | 81 | `run_adaptive_decomposed_joint_optimizer` |  | Build operator-specific destroy neighborhoods from current damage. |
| `_joint_candidate_shift_indices` | 16601 to 16652 | 52 | `solve_joint_shift_off_language_break_refinement` |  | Return a small universal shift neighborhood for a joint refinement cell. |
| `bootstrap_exception_anchors_for_joint` | 17690 to 17828 | 139 | `run_case` |  | Create operational exception anchors before adaptive joint refinement. |
| `dnbs_day_neighbourhood_model` | 19574 to 19694 | 121 | `run_day_neighbourhood_break_search` |  | Aggregated break model for the shifts starting on ``day``. |

### Candidate selection

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `save_candidate_pool_checkpoint` | 1195 to 1216 | 22 | `run_case` |  | Persist all useful candidate classes without changing release semantics. |
| `load_candidate_pool_checkpoint` | 1219 to 1235 | 17 | `run_case` |  |  |
| `load_validated_fallback_candidate` | 7459 to 7642 | 184 | `discover_validated_fallback_candidates`, `run_case` |  | Load and revalidate a previously exported fully evaluated schedule. |
| `bundled_schedule_candidate_inventory` | 7646 to 7729 | 84 | `discover_validated_fallback_candidates`, `run_case` |  | Return data-driven current-contract champions and seed-only workbooks. |
| `prove_selected_exceptions` | 10500 to 10530 | 31 | `run_case` |  |  |
| `candidate_validation_snapshot` | 12888 to 12900 | 13 | `candidate_pool_class`, `promote_zero_exception_diagnostic_candidate`, `retain_search_only_diagnostic_joint_anchor`, `run_case` +1 |  | Return and persist the full release validation for a candidate. |
| `candidate_pool_class` | 12903 to 12934 | 32 | `adaptive_nondominated_anchor_pool`, `bootstrap_exception_anchors_for_joint`, `candidate_satisfies_explicit_kpi_locks`, `choose_repair_anchors` +20 | 1 file | Classify a feasible candidate without weakening any release gate. |
| `candidate_damage_present` | 13031 to 13045 | 15 | `run_case` |  | Return whether a candidate still deserves bounded recovery effort. |
| `_deficit_bucket` | 13226 to 13235 | 10 | `_candidate_quality_tuple`, `before_break_leaderboard_rows`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` | 1 file | Quantize a coverage-deficit sum to an operationally meaningful bucket. |
| `_candidate_quality_tuple` | 13253 to 13323 | 71 | `break_solution_key`, `run_case`, `select_best_before_skeleton`, `select_export_candidates` +3 | 1 file | Positive-is-better universal target-protected ordering. |
| `merge_candidate_pools_with_safe_incumbent` | 13373 to 13433 | 61 | `run_case` |  | Retain a validated incumbent in its correct release pool. |
| `candidate_dominates` | 13728 to 13769 | 42 | `nondominated_candidates` |  | Pareto dominance after hard-gate and exception-count filtering. |
| `nondominated_candidates` | 13772 to 13777 | 6 | `pareto_frontier_signature`, `select_export_candidates` |  |  |
| `select_export_candidates` | 13832 to 14131 | 300 | `run_case`, `selfcheck` |  | Select recommended, max-target, and max-floor candidates safely. |
| `select_release_candidates_with_protection` | 14466 to 14505 | 40 | `run_case` |  | Prefer zero-exception schedules, but never discard a protected exception champion. |
| `candidate_record` | 14552 to 14596 | 45 | `publish_recovery_checkpoint`, `run_case` |  |  |
| `retain_zero_exception_diagnostic_candidate` | 15672 to 15718 | 47 | `promote_zero_exception_diagnostic_candidate`, `run_case` |  | Retain every real zero-exception assignment as clean or near-feasible. |
| `promote_zero_exception_diagnostic_candidate` | 15817 to 15866 | 50 | `run_case` |  | Promote a zero-exception diagnostic solution to a safe fallback. |
| `minimum_exception_candidate_pool` | 15912 to 15919 | 8 | `run_target_lock_recovery_phase` |  |  |
| `_candidate_identity` | 16254 to 16260 | 7 | `adaptive_nondominated_anchor_pool` |  |  |
| `candidate_lineage_id` | 16263 to 16284 | 22 | `run_adaptive_decomposed_joint_optimizer`, `solve_joint_shift_off_language_break_refinement`, `validate_replay_candidate_mapping` |  | Stable identity for one coherent shift/OFF/break candidate. |
| `validate_replay_candidate_mapping` | 16287 to 16347 | 61 | `run_adaptive_decomposed_joint_optimizer`, `solve_joint_shift_off_language_break_refinement` |  | Prove a replay anchor is internally coherent before building CP-SAT. |
| `candidate_satisfies_explicit_kpi_locks` | 20777 to 20804 | 28 | `cap_feasible_target_recovery_decision` |  | Return True only for a release-class candidate satisfying every explicit lock. |

### Output and publishing

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `cleanup_stale_run_outputs` | 283 to 320 | 38 | `run_case` |  | Remove only the known artifacts for an intentional non-resume overwrite. |
| `_write_records` | 14533 to 14538 | 6 | `run_shortfall_pass`, `synchronize_contract_metadata`, `write_output_workbook` |  |  |
| `production_quality_gate` | 14803 to 14963 | 161 | `load_validated_fallback_candidate`, `write_output_workbook` |  | Classify hard coverage quality separately from declared operational quality debt. |
| `write_output_workbook` | 14965 to 15602 | 638 | `publish_recovery_checkpoint`, `run_case`, `run_shortfall_pass`, `write_before_break_workbook` |  |  |
| `publish_recovery_checkpoint` | 21287 to 21355 | 69 | `run_case` |  | Atomically persist the best validated pre-late-phase candidate. |
| `_business_int` | 25865 to 25871 | 7 | `_build_business_outcome_core`, `_business_contract_message`, `_business_exception_rows` |  |  |
| `_business_failure_rows` | 25874 to 25880 | 7 | `_build_business_outcome_core` |  |  |
| `_business_exception_rows` | 25883 to 25914 | 32 | `_business_break_blockers` |  |  |
| `_business_reason_window` | 25917 to 25926 | 10 | `_business_break_blockers` |  |  |
| `_business_contract_message` | 25980 to 26048 | 69 | `_build_business_outcome_core` |  |  |
| `_business_hard_conflict` | 26067 to 26109 | 43 | `_build_business_outcome_core` |  | Plain-language findings for a hard-rule contradiction. |
| `_business_finding_text` | 26112 to 26126 | 15 | `format_business_outcome` |  | One readable line per finding: named fields, never nested solver dumps. |
| `publish_business_outcome` | 26505 to 26524 | 20 | `main` |  |  |

### Audit and self-check

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_validate_numeric_instruction` | 1481 to 1500 | 20 | `parse_input` |  | Flag malformed numeric controls before permissive legacy coercion runs. |
| `_validate_boolean_instructions` | 1538 to 1553 | 16 | `parse_input` |  | A switch row holding something that is neither yes nor no fails the contract. |
| `distinct_skill_allocation_audit` | 10552 to 10667 | 116 | `calculate_metrics` |  | Audit simultaneous skill minima using distinct available associates. |
| `structural_schedule_audit` | 12286 to 12481 | 196 | `validate_schedule` |  | Audit blank bridges, day tails, overnight shifts and cyclic Sunday truth. |
| `validate_schedule` | 12484 to 12598 | 115 | `acquire_early_safe_incumbent`, `candidate_damage_present`, `candidate_validation_snapshot`, `load_validated_fallback_candidate` +9 |  |  |
| `selfcheck` | 25435 to 25747 | 313 | `main` |  |  |

### Shift consistency polish

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_consistency_cell_allowed` | 19968 to 19985 | 18 | `_consistency_greedy_swaps`, `_consistency_swap_model`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `_consistency_row_allowed` | 19988 to 20000 | 13 | `_consistency_greedy_swaps`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `_consistency_employee_no_worse` | 20014 to 20016 | 3 | `_consistency_greedy_swaps`, `preference_swap_polish` |  |  |
| `_consistency_greedy_swaps` | 20032 to 20079 | 48 | `shift_consistency_polish` |  | Pairwise same-day swaps that lower the two associates' cost; the model |
| `_consistency_swap_model` | 20082 to 20256 | 175 | `shift_consistency_polish` |  | Re-deal each day's shifts within (language, shift length) groups. |

### Tiers, exceptions and quality figures

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `status_name` | 5210 to 5218 | 9 | `build_skeleton`, `capture_solver_telemetry`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  |  |
| `enrich_exception_rows` | 9203 to 9242 | 40 | `build_break_constraint_isolation_report`, `solve_breaks` |  | Attach exact blocking evidence to minimum-exception cells. |
| `critical_exception_cells` | 9305 to 9387 | 83 | `solve_breaks` |  |  |
| `minimum_exception_diagnostic` | 10483 to 10497 | 15 | `run_case`, `run_logic_based_break_cut_feedback`, `run_qualified_language_break_certificate_repairs` |  | Bound the minimum no-break associate-days required by this skeleton. |
| `employee_operational_quality` | 10715 to 10796 | 82 | `_consistency_greedy_swaps`, `calculate_metrics`, `preference_swap_polish`, `shift_consistency_polish` |  |  |
| `near_feasible_failure_status` | 13048 to 13065 | 18 | `run_case` |  | Describe the candidate-level reason a retained diagnostic was not released. |
| `hard_floor_failure_rows` | 13068 to 13082 | 15 | `run_case` |  | Return exact intervals below the configured hard floor for evidence output. |
| `_protected_tier_counts` | 13160 to 13178 | 19 | `_candidate_quality_tuple`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` | 1 file | Return safety tiers strictly between the workbook target and configured floor. |
| `pareto_frontier_signature` | 13780 to 13796 | 17 | `run_case` |  |  |
| `_tier_minimum_failures` | 13799 to 13816 | 18 | `_meets_tier_minima`, `run_case` |  | Return explicit 100/90/80 benchmark failures for one metric surface. |
| `_meets_tier_minima` | 13819 to 13829 | 11 | `select_export_candidates` |  |  |
| `protected_benchmark_pass` | 14455 to 14463 | 9 | `select_release_candidates_with_protection` |  |  |
| `exception_reason_map` | 14541 to 14549 | 9 | `write_output_workbook` |  |  |
| `exception_cap_descent_targets` | 15777 to 15791 | 15 | `run_adaptive_decomposed_joint_optimizer` |  | Return a monotone one-exception-at-a-time path to the release cap. |
| `_quality_delta` | 16234 to 16249 | 16 | `run_coordinated_shift_off_break_loop`, `run_post_break_repair_phase` |  |  |
| `benchmark_provenance` | 21394 to 21454 | 61 | `run_case` |  | Classify a benchmark as authoritative only when its contract provenance matches. |

### Workbook styling

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_replace_sheet` | 14508 to 14511 | 4 | `run_shortfall_pass`, `synchronize_contract_metadata`, `write_output_workbook` |  |  |
| `_style_header` | 14514 to 14519 | 6 | `_write_records` |  |  |
| `_autosize` | 14522 to 14530 | 9 | `_write_records` |  |  |
| `_contract_display_rows` | 14599 to 14649 | 51 | `synchronize_contract_metadata` |  |  |

### Time reserves and machine limits

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_cgroup_memory_headroom_mb` | 5365 to 5393 | 29 | `machine_free_memory_mb` |  | limit - usage of this process's own memory cgroup (v2 or v1), if limited. |
| `machine_free_memory_mb` | 5396 to 5413 | 18 | `isolated_cp_solve`, `joint_memory_headroom` |  | (free MB, total MB): MemAvailable, tightened by a cgroup limit if one applies. |
| `capture_solver_telemetry` | 5624 to 5722 | 99 | `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Read back what the solve already computed. Costs no solver time. |
| `preflight_probe_retry_seconds` | 6782 to 6791 | 10 | `run_case` |  | Seconds for a second hard-feasibility probe after an UNKNOWN first one. |
| `guaranteed_stage2_reserve_seconds` | 15869 to 15877 | 9 | `bounded_stage2_guard_reserve_seconds` |  | Wall-time reserve protected from Stage 1 and diagnostics. |
| `bounded_stage2_guard_reserve_seconds` | 15880 to 15894 | 15 | `run_case`, `selfcheck` |  | Protect at least one real break solve even in short functional runs. |

### Other helpers

| Function | Lines | Size | Called by (engine) | Used outside (not tests) | What it does |
|---|---|---|---|---|---|
| `_roster_option` | 1699 to 1718 | 20 | `_parse_roster` |  | Phase BL: one optional Schedule-sheet cell. (True, value) when blank (None) or readable, (False, Non |
| `circular_minute_distance` | 5801 to 5803 | 3 | `_consistency_swap_model`, `_joint_candidate_shift_indices`, `build_skeleton`, `employee_operational_quality` +2 |  |  |
| `pinned_leave_days` | 5806 to 5816 | 11 | `build_skeleton`, `required_off_days`, `solve_joint_shift_off_language_break_refinement` |  | Days this associate is pinned to Leave by the contract (fixed or approved leave). |
| `cyclic_requirement_context` | 6061 to 6075 | 15 | `_shift_day_demand_fit_uncached`, `structural_schedule_audit` |  | Map a current-week or pseudo-next-Sunday qslot to weekday/interval/minute. |
| `prior_constant_cover` | 6297 to 6307 | 11 | `build_skeleton` |  |  |
| `active_interval_segments` | 6837 to 6850 | 14 | `aggregate_pattern_mix_guidance`, `build_skeleton`, `solve_breaks`, `solve_joint_shift_off_language_break_refinement` |  | Return contiguous active interval segments; blank periods reset runs. |
| `eligible_shift_day_pairs` | 6872 to 6879 | 8 | `aggregate_pattern_mix_guidance`, `run_case` |  |  |
| `elastic_slack_rows` | 8711 to 8731 | 21 | `build_skeleton`, `solve_breaks` |  | One row per minimum the solution actually misses, with the measured deficit. |
| `shortfall_pass_allowed` | 8766 to 8769 | 4 | `run_case` |  | True when every contract failure is a capacity proof (F-06). |
| `scheduled_cells` | 9001 to 9007 | 7 | `adaptive_operator_focus_cells`, `break_qslots`, `calculate_metrics`, `dnbs_day_neighbourhood_model` +23 | 3 files |  |
| `prior_covering_associates` | 9035 to 9041 | 7 | `_max_possible_raw_at_qslot`, `aggregate_pattern_mix_guidance`, `break_capacity_headcount_requirement`, `break_resilience_diagnostics` +9 |  |  |
| `associate_day_eligible_shifts` | 11749 to 11786 | 38 | `_joint_candidate_shift_indices`, `_max_possible_raw_at_qslot`, `break_resilience_diagnostics`, `capacity_diagnostics` +1 |  | Return shifts that can possibly be used by one associate-day before weekly coupling. |
| `_target_secondary_counts` | 13181 to 13189 | 9 | `_candidate_quality_tuple`, `candidate_selection_breakdown`, `target_priority_tradeoff_select` |  | Return only tiers ABOVE the workbook target as late upside tie-breaks. |
| `associate_workdays` | 14269 to 14273 | 5 | `break_resilience_diagnostics`, `capacity_diagnostics`, `coverage_split_capacity_report` |  | Phase BL: days one associate works in a week for the capacity estimates: the usual week, or 7 minus  |
| `default_workdays_per_week` | 14276 to 14284 | 9 | `associate_workdays`, `break_capacity_headcount_requirement`, `break_resilience_diagnostics`, `capacity_diagnostics` +1 |  | Days one associate works in a week, for converting weekly capacity. |
| `acquire_early_safe_incumbent` | 15922 to 15994 | 73 | `run_case` |  | Acquire a fully evaluated incumbent before the expensive Pareto search. |
| `feedback_cut_variants` | 18931 to 18958 | 28 | `run_logic_based_break_cut_feedback` |  | Split a break-feasibility cut into progressively stronger master repairs. |
| `recommended_export_pair` | 20263 to 20279 | 17 | `run_case` |  | The recommended pair, checked to be the RECOMMENDED_FINAL pair the writer publishes. |
| `add_more_consistent_export` | 20282 to 20296 | 15 | `run_case` |  | Publish an applied polish as MORE_CONSISTENT_CANDIDATE, beside the selected schedule. |
| `cap_feasible_target_recovery_decision` | 20807 to 20863 | 57 | `run_case` |  | Decide whether RC6 recovery should run without disturbing healthy schedules. |
| `derive_dynamic_before_search_locks` | 20954 to 20981 | 28 | `run_case` |  | Derive search-only Stage-1 retention locks from current-contract truth. |
| `classify_late_phase_execution_gate` | 21213 to 21283 | 71 | `run_case` |  | Classify late-phase execution without confusing candidate and engine failure. |
| `build_business_outcome` | 26129 to 26173 | 45 | `publish_business_outcome` |  | The run's business outcome, plus the shortfall schedule when one was made (F-06). |
| `_build_business_outcome_core` | 26176 to 26433 | 258 | `build_business_outcome` |  |  |
| `shortfall_text_line` | 26436 to 26440 | 5 | `format_business_outcome` |  |  |
| `format_business_outcome` | 26446 to 26483 | 38 | `publish_business_outcome` |  |  |
| `_augment_summary_with_business_outcome` | 26486 to 26502 | 17 | `publish_business_outcome` |  |  |
| `record_unexpected_run_failure` | 26527 to 26560 | 34 | `main` |  | Persist a truthful terminal status for an unexpected engine exception. |
| `explicitly_supplied_options` | 26618 to 26638 | 21 | `main` | 1 file | Return the argparse destinations the caller actually typed. |

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
| `FINAL_RECOVERY_ENDGAME_ENABLED` | 5333 | `main` | `run_case` |
| `STAGE1_PROFILE_ROTATION` | 5342 | `main` | `run_case` |
| `BREAK_LOAD_FEEDBACK_ENABLED` | 18478 | `main` | `run_case` |
| `DAY_NEIGHBOURHOOD_BREAK_SEARCH_ENABLED` | 19534 | `main` | `run_case` |
| `SHIFT_CONSISTENCY_CLI_OVERRIDE` | 19925 | `main` | `run_case` |
| `SOLVER_DETERMINISTIC_TIME` | 5226 | `run_shortfall_pass` | `configure_solver_limits` |

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
| The workbook is misread or refused | `parse_input` (3669), `validate_input_contract` (4710), `preference_kind` (5788) |
| A language minimum is not met | `language_rules_at` (6232), `language_reserve_status` (6289), `associate_language_windows` (3495), `solve_joint_shift_off_language_break_refinement` (16655) |
| A break is placed too late, too early or too many at once | `solve_breaks` (9811), `maximum_concurrent_breaks` (5922), `run_day_neighbourhood_break_search` (19697) |
| A coverage figure on the output is wrong | `calculate_metrics` (10799), `coverage_vars` (6327), `coverage_quality_limits` (6853) |
| An OFF or shift request is not honoured | `preference_kind` (5788), `required_off_days` (5819), `add_weekly_off_rule` (5854) |
| A different candidate is published than expected | `select_export_candidates` (13832), `target_priority_tradeoff_select` (13516), `_candidate_quality_tuple` (13253) |
| The output workbook and the validator disagree | `write_output_workbook` (14965), `structural_schedule_audit` (12286), `publish_business_outcome` (26505) |
| A run takes longer or shorter than asked | `run_case` (21479), `main` (26662), `stage1_minimum_budget_seconds` (21469) |
| The first (skeleton) search is weak | `build_skeleton` (7778), `skeleton_profiles` (6435), `aggregate_pattern_mix_guidance` (6882) |
| A fixed or nested shift is broken | `rest_compatible` (5883), `previous_saturday_compatible` (5888), `shift_parts` (497) |
