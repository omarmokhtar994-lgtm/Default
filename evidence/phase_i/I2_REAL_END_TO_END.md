# Real end-to-end run through the website (finished 21:36 Egypt time, 2026-10-07)
Real input check, real safety gate (run_tests.sh inside the built package), real runner (QUICK, --time-limit 240 per seed so it fits this container, 2 seeds), real release-gate scoring. Driver: Flask test client against create_app with the default commands. Website code at d5f543f (labels refined later in 40c807f; RELEASABLE shows Approved either way).

run 0f1214060945
      0s QUEUED: Workbook accepted; waiting for its turn.
     10s GATE: Checking the installed package (safety gate).
    760s RUNNING: Building the schedule.
    960s DONE: Approved: the independent validator passed this schedule.
exit_code 0
RELEASE VERDICT NMG_SP_RC9_1_READY_FIXED: RELEASABLE - not evaluated: gate 4 protected tier: no protected minimum configured; gate 5 absolute after-break standard: none configured
RELEASE VERDICT (run): RELEASABLE
download 200 9445940
139 files; ['NMG_SP_RC9_1_READY_FIXED/NMG_SP_RC9_1_READY_FIXED_S9000_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', 'NMG_SP_RC9_1_READY_FIXED/PORTFOLIO/AFTER_BREAKS_BEST__S9000__NMG_SP_RC9_1_READY_FIXED_S9000_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx', 'NMG_SP_RC9_1_READY_FIXED/debug/raw_engine_output/NMG_SP_RC9_1_READY_FIXED_S9000_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx']
schedule 200 attachment; filename=NMG_SP_RC9_1_READY_FIXED_S9000_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx
gate stamp [PosixPath('/tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad/e2e/data/runs/_gate/480e29346d570b37d9ed2604b7d6a739ceac286f0fe9f4628a19214b5597d5b5.json')]

--- gate stamp
{
  "status": "PASS",
  "manifest_sha256": "480e29346d570b37d9ed2604b7d6a739ceac286f0fe9f4628a19214b5597d5b5",
  "summary": "GATE PASS \u2014 75 suite(s), 1529 tests (2 skipped) + 2 selfchecks + cross-module call signatures + undefined-name sweep",
  "checked_utc": "2026-10-07T18:33:14+00:00"
}
--- runner log tail
    gate 4 PASS_PROTECTED_NOT_EVALUATED quality_benchmark=PASS, protected_benchmark=NOT_CONFIGURED; no protected minimum was configured, so the protected tier was never checked
    gate 5 PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD target -5, floor -0 of 126 active; 0 exceptions (minimum proven); after-break target 121/126 = 96.0%; no absolute after-break minimum is configured, so only the break-stage delta was checked - add a 'Minimum After Break Target Ratio' row to the workbook's Instructions (Setup) sheet to hold an absolute standard
    gate 8 PASS                   0 hard failures on FINAL_AFTER_BREAKS

RELEASE VERDICT NMG_SP_RC9_1_READY_FIXED: RELEASABLE - not evaluated: gate 4 protected tier: no protected minimum configured; gate 5 absolute after-break standard: none configured
RELEASE VERDICT (run): RELEASABLE
written: /tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad/e2e/data/runs/0f1214060945/results/_gate_report/RC9_2_1_RELEASE_GATE_REPORT.csv
written: /tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad/e2e/data/runs/0f1214060945/results/_gate_report/RELEASE_VERDICT.json
gates 2 and 9 are decided against evidence/RC9_1_BASELINE.json (consolidated RC9.1 metrics, before-break only). A case is only compared when its input sha256, active-interval count and target ratio all match the baseline row; otherwise it is reported as NOT_COMPARABLE rather than compared.


case                     status                     G4     G5              G8          
----------------------------------------------------------------------------------------
NMG_SP_RC9_1_READY_FIXED PASS_WITH_QUALITY_WARNINGS PASS_P PASS_DELTA_ONLY PASS        

NMG_SP_RC9_1_READY_FIXED:
    gate 4 PASS_PROTECTED_NOT_EVALUATED quality_benchmark=PASS, protected_benchmark=NOT_CONFIGURED; no protected minimum was configured, so the protected tier was never checked
    gate 5 PASS_DELTA_ONLY_NO_ABSOLUTE_STANDARD target -5, floor -0 of 126 active; 0 exceptions (minimum proven); after-break target 121/126 = 96.0%; no absolute after-break minimum is configured, so only the break-stage delta was checked - add a 'Minimum After Break Target Ratio' row to the workbook's Instructions (Setup) sheet to hold an absolute standard
    gate 8 PASS                   0 hard failures on FINAL_AFTER_BREAKS

RELEASE VERDICT NMG_SP_RC9_1_READY_FIXED: RELEASABLE - not evaluated: gate 4 protected tier: no protected minimum configured; gate 5 absolute after-break standard: none configured
RELEASE VERDICT (run): RELEASABLE
written: /tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad/e2e/data/runs/0f1214060945/results/_gate_report/RC9_2_1_RELEASE_GATE_REPORT.csv
written: /tmp/claude-0/-home-user-Default/57e8acb4-ab5e-5113-8a50-dec0489e4e6a/scratchpad/e2e/data/runs/0f1214060945/results/_gate_report/RELEASE_VERDICT.json
gates 2 and 9 are decided against evidence/RC9_1_BASELINE.json (consolidated RC9.1 metrics, before-break only). A case is only compared when its input sha256, active-interval count and target ratio all match the baseline row; otherwise it is reported as NOT_COMPARABLE rather than compared.
