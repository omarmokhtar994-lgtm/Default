#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, hashlib, json, os, re, shutil, subprocess, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "_tools" / "l632_universal_scheduler.py"
POLISHER = ROOT / "production" / "production_output_polisher.py"
QUALITY_REPORTER = ROOT / "production" / "phase_c_quality_report.py"
PACKAGER = ROOT / "production" / "package_phase_c_outputs.py"
VALIDATOR = ROOT / "tools" / "independent_validator.py"
def _engine_release() -> str:
    """Read the release identity from the engine itself.

    This was previously a hardcoded literal in this wrapper, and it had drifted:
    the wrapper stamped every run "L6.3.2.4-RC9.2-PROTECTED-BALANCE-RC1" while
    the engine it invoked was "L6.3.2.5-RC9.2.1-...".  Because this value is
    written into run identity and manifest output, RC9.2.1 runs were being
    recorded under the RC9.2 release name, which defeats the exact-engine-
    identity release gate.  Deriving it from the engine's own VERSION constant
    makes that class of drift impossible rather than merely corrected once.

    Fails loudly: a wrong-but-plausible release string is worse than no run.
    """
    text = ENGINE.read_text(encoding='utf-8', errors='replace')
    match = re.search(r'^VERSION\s*=\s*["\'](.+?)["\']', text, re.MULTILINE)
    if not match:
        raise SystemExit(
            f'Cannot determine engine release identity: no VERSION constant in {ENGINE}. '
            'Refusing to stamp runs with an assumed release name.'
        )
    return match.group(1)


RELEASE = _engine_release()

DEFAULT_SKELETON_PROFILES = (
    "target90_restore_champion,target90_restore_productive,release_gate_floor_satisfaction,"
    "target_floor_pareto_master,floor_gate_hunter_before,floor_gate_hunter_productive,"
    "aggregate_floor_binding,quality_convergence,daily_floor_balanced,break_safe_reserve,"
    "target_priority_balanced,floor_protected,coverage_rebalance,before_target_champion,"
    "protected_balance_polish"
)
DEFAULT_BREAK_OBJECTIVES = "target_priority,release_quality_guard,coverage_rebalance,quality_convergence,floor_protected,balanced,target_100"


def _contract_run_settings(input_path):
    """Read Run Stage and Run Depth from the workbook, or (None, None).

    Never fatal. If the workbook cannot be parsed here the engine will fail on
    it a moment later with a far better message, and a runner that dies while
    reading a convenience setting would hide that.
    """
    try:
        sys.path.insert(0, str(ENGINE.parent))
        import l632_universal_scheduler as engine_module
        parsed = engine_module.parse_input(Path(input_path))
        return parsed.run_stage, parsed.run_depth
    except Exception as exc:
        print(f'[run] could not read Run Stage/Run Depth from the workbook '
              f'({type(exc).__name__}); using defaults', flush=True)
        return None, None


def safe_id(value: str) -> str:
    cleaned = ''.join(ch if ch.isalnum() or ch in '_.-' else '_' for ch in str(value or 'schedule'))
    return cleaned.strip('_') or 'schedule'


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_summary_metrics(case_root: Path) -> dict:
    summary_files = sorted(case_root.glob('*.l6_3_2_3_summary.csv'))
    if not summary_files:
        summary_files = sorted(case_root.glob('*_SKELETON_ONLY_SUMMARY.csv'))
    if not summary_files:
        return {}
    with summary_files[0].open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    return rows[0] if rows else {}


def hard_valid_artifact(audit_path: Path) -> bool:
    if not audit_path.exists():
        return False
    try:
        audit = json.loads(audit_path.read_text(encoding='utf-8'))
    except Exception:
        return False
    return audit.get('artifact_state') == 'FINAL_VERIFIED' and audit.get('hard_valid_schedule_exists') is True


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='RC9 universal workbook-driven WFM production runner. No client/case branching.')
    p.add_argument('--input', type=Path, required=False, help='Any supported Universal WFM input workbook (.xlsx)')
    p.add_argument('--output-root', type=Path, default=ROOT / 'results')
    p.add_argument('--schedule-id', help='Optional display/job ID. Defaults to input filename stem.')
    p.add_argument('--mode', choices=['SMOKE','QUICK','DEEP','OVERNIGHT','FULL'], default=None,
                   help='Run depth. Omit to take Run Depth from the workbook, '
                        'falling back to DEEP. FULL is a legacy alias for OVERNIGHT.')
    p.add_argument('--stage', choices=['BEFORE_BREAKS_ONLY','FULL_SCHEDULE'], default=None,
                   help='Omit to take Run Stage from the workbook, falling back '
                        'to FULL_SCHEDULE. BEFORE_BREAKS_ONLY runs Stage 1 and '
                        'exports the before-break champion without placing breaks.')
    p.add_argument('--time-limit', type=int, help='Override total solver budget seconds')
    p.add_argument('--num-workers', type=int, default=max(1, min(8, os.cpu_count() or 4)))
    p.add_argument('--pattern-widths', default='24,44,60,115')
    p.add_argument('--repair-change-limits', default='2,4,6,8,12')
    p.add_argument('--skeleton-profiles', default=DEFAULT_SKELETON_PROFILES)
    p.add_argument('--break-objective-modes', default=DEFAULT_BREAK_OBJECTIVES)
    p.add_argument('--use-input-schedule-as-seed', action='store_true', default=True)
    p.add_argument('--disable-input-schedule-seed', action='store_true')
    p.add_argument('--allow-no-break-exceptions', action='store_true')
    p.add_argument('--disable-no-break-exceptions', action='store_true')
    p.add_argument('--max-no-break-exceptions', type=int)
    p.add_argument('--allow-headcount-mismatch', action='store_true')
    p.add_argument('--diagnostics-only', action='store_true')
    p.add_argument('--skeleton-only', action='store_true', help='Run Stage 1 only and export ranked before-break skeletons.')
    p.add_argument('--export-top-skeletons', type=int, default=5)
    p.add_argument('--enable-bundled-regression-fallbacks', action='store_true', help='Off by default in production; regression assets must not steer new client workbooks unless explicitly enabled.')
    p.add_argument('--solver-random-seed', type=int, default=9000)
    p.add_argument('--overwrite', action='store_true', default=True)
    p.add_argument('--resume', action='store_true')
    p.add_argument('--skip-independent-validation', action='store_true', help='Development-only bypass; production defaults to independent validation.')
    p.add_argument('--selfcheck', action='store_true')
    return p


def selfcheck() -> int:
    errors = []
    for path in [ENGINE, POLISHER, QUALITY_REPORTER, PACKAGER, VALIDATOR]:
        if not path.exists():
            errors.append(f'MISSING {path}')
    for py in [ENGINE, POLISHER, QUALITY_REPORTER, PACKAGER, VALIDATOR, Path(__file__)]:
        if py.exists():
            rc = subprocess.call([sys.executable, '-m', 'py_compile', str(py)])
            if rc:
                errors.append(f'COMPILE_FAIL {py}')
    if ENGINE.exists():
        rc = subprocess.call([sys.executable, str(ENGINE), '--selfcheck'])
        if rc:
            errors.append('ENGINE_SELFCHECK_FAIL')
    if POLISHER.exists():
        rc = subprocess.call([sys.executable, str(POLISHER), '--selfcheck'])
        if rc:
            errors.append('POLISHER_SELFCHECK_FAIL')
    if errors:
        print(json.dumps({'status':'FAIL','release':RELEASE,'errors':errors}, indent=2))
        return 1
    print(json.dumps({'status':'PASS','release':RELEASE,'engine_sha256': sha256_file(ENGINE)}, indent=2))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    if args.selfcheck:
        return selfcheck()
    if args.input is None:
        raise SystemExit('--input is required unless --selfcheck is used')
    input_path = args.input.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if input_path.suffix.lower() != '.xlsx':
        raise ValueError('Input must be an .xlsx workbook')

    schedule_id = safe_id(args.schedule_id or input_path.stem)
    case_root = (args.output_root / schedule_id).resolve()
    case_root.mkdir(parents=True, exist_ok=True)
    work_dir = case_root / 'debug'
    output = case_root / f'{schedule_id}_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx'
    audit = case_root / f'{schedule_id}.l6_3_2_3_solver_audit.json'
    summary = case_root / f'{schedule_id}.l6_3_2_3_summary.csv'

    # Run stage and depth come from the workbook unless the command line says
    # otherwise, so a scheduler picks them from a dropdown in the business
    # contract instead of remembering flags. An explicit flag always wins.
    contract_stage, contract_depth = _contract_run_settings(input_path)
    mode = args.mode or contract_depth or 'DEEP'
    if mode == 'FULL':
        mode = 'OVERNIGHT'
    stage = args.stage or contract_stage or 'FULL_SCHEDULE'

    all_mode_defaults = {
        'SMOKE': {'time_limit': 900, 'joint': 120, 'safe': 120, 'post': 60, 'target': 60, 'final': 60, 'adaptive': 6, 'joint_attempts': 4, 'joint_no_improve': 2},
        'QUICK': {'time_limit': 3600, 'joint': 900, 'safe': 180, 'post': 180, 'target': 180, 'final': 120, 'adaptive': 18, 'joint_attempts': 16, 'joint_no_improve': 6},
        # RC9.1 production defaults: Deep may use four hours and Overnight six.
        # The engine remains workbook-driven; longer time only expands universal search breadth/depth.
        'DEEP': {'time_limit': 14400, 'joint': 5400, 'safe': 360, 'post': 600, 'target': 600, 'final': 240, 'adaptive': 48, 'joint_attempts': 48, 'joint_no_improve': 16},
        'OVERNIGHT': {'time_limit': 21600, 'joint': 8400, 'safe': 480, 'post': 900, 'target': 900, 'final': 300, 'adaptive': 72, 'joint_attempts': 72, 'joint_no_improve': 22},
    }
    mode_defaults = all_mode_defaults[mode]
    time_limit = int(args.time_limit or mode_defaults['time_limit'])
    diagnostics_only = bool(args.diagnostics_only or mode == 'SMOKE')
    # One source of truth. `--skeleton-only` already existed as a flag with full
    # downstream handling; the workbook's Run Stage is a second way to ask for
    # the same thing, so both feed one variable. Deriving the stage from the
    # flag as well keeps the two from disagreeing in the run record.
    skeleton_only = bool(args.skeleton_only) or stage == 'BEFORE_BREAKS_ONLY'
    if skeleton_only:
        stage = 'BEFORE_BREAKS_ONLY'
    # The engine renames its own output in skeleton-only mode; renaming it here
    # too produced a doubled ..._BEST_BEFORE_BREAKS_SCHEDULE_BEST_BEFORE_BREAKS
    # _SCHEDULE.xlsx, so the path stays as-is and the engine decides the name.
    print(f'[run] stage={stage} depth={mode} time_limit={time_limit}s '
          f'(stage source: {"cli" if args.stage else ("workbook" if contract_stage else "default")}; '
          f'depth source: {"cli" if args.mode else ("workbook" if contract_depth else "default")})',
          flush=True)

    command = [
        sys.executable, '-u', str(ENGINE),
        '--input', str(input_path),
        '--output', str(output),
        '--audit-json', str(audit),
        '--summary-csv', str(summary),
        '--work-dir', str(work_dir),
        '--time-limit', str(time_limit),
        '--num-workers', str(args.num_workers),
        '--pattern-widths', args.pattern_widths,
        '--repair-change-limits', args.repair_change_limits,
        '--skeleton-profiles', args.skeleton_profiles,
        '--break-objective-modes', args.break_objective_modes,
        '--min-after90-gain-per-after80-loss', '1.0',
        '--adaptive-no-improvement-attempts', str(mode_defaults['adaptive']),
        '--primary-target-tolerance', '1',
        '--max-final-before-target-loss', '6',
        '--solver-random-seed', str(args.solver_random_seed),
        '--exception-search-reserve-sec', '180',
        '--post-break-repair-reserve-sec', str(mode_defaults['post']),
        '--target-lock-recovery-reserve-sec', str(mode_defaults['target']),
        '--finalization-reserve-sec', str(mode_defaults['final']),
        '--safe-incumbent-reserve-sec', str(mode_defaults['safe']),
        '--conflict-refinement-reserve-sec', '120',
        '--coordinated-repair-reserve-sec', '300',
        '--coordinated-repair-cycles', '1',
        '--joint-refinement-reserve-sec', str(mode_defaults['joint']),
        '--joint-change-limits', '8,16,24,36,54',
        '--joint-shift-options-per-cell', '10',
        '--joint-patterns-per-shift', '64',
        '--adaptive-joint-attempts', str(mode_defaults['joint_attempts']),
        '--adaptive-joint-no-improvement-limit', str(mode_defaults['joint_no_improve']),
    ]
    if not args.enable_bundled_regression_fallbacks:
        command.append('--disable-bundled-fallbacks')
    if args.use_input_schedule_as_seed and not args.disable_input_schedule_seed:
        command.append('--use-input-schedule-as-seed')
    if args.allow_no_break_exceptions:
        command.append('--allow-no-break-exceptions')
    if args.disable_no_break_exceptions:
        command.append('--disable-no-break-exceptions')
    if args.max_no_break_exceptions is not None:
        command += ['--max-no-break-exceptions', str(args.max_no_break_exceptions)]
    if args.allow_headcount_mismatch:
        command.append('--allow-headcount-mismatch')
    if diagnostics_only:
        command.append('--diagnostics-only')
    if skeleton_only:
        command += ['--skeleton-only', '--export-top-skeletons', str(max(0, args.export_top_skeletons))]
    if args.overwrite:
        command.append('--overwrite')
    if args.resume:
        command.append('--resume')

    identity = {
        'schema_version': 1,
        'release': RELEASE,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'schedule_id': schedule_id,
        'mode': mode, 'stage': stage,
        'input_path': str(input_path),
        'input_sha256': sha256_file(input_path),
        'engine_sha256': sha256_file(ENGINE),
        'case_branching': False,
        'rc9_1_search_recovery': True,
        'rc9_2_protected_balance': True,
        'skeleton_only': bool(skeleton_only),
        'stage2_strategy': 'breadth_first_expand_then_next_skeleton',
        'bundled_regression_fallbacks_enabled': bool(args.enable_bundled_regression_fallbacks),
        'command': command,
    }
    (case_root / 'UNIVERSAL_RUN_IDENTITY.json').write_text(json.dumps(identity, indent=2), encoding='utf-8')
    print('COMMAND:', ' '.join(command), flush=True)
    engine_rc = subprocess.call(command)
    rc = engine_rc

    # Complete the case-root identity from the engine's own run identity.
    #
    # The wrapper can only know the input and engine hashes before the run; the
    # contract hash, parameters hash and run id are derived by the engine while
    # parsing. They were therefore written only to work_dir/RUN_IDENTITY.json,
    # leaving UNIVERSAL_RUN_IDENTITY.json - the file at case root that a
    # reviewer or packager reads - carrying two of the four identity axes, with
    # contract_sha256 and run_id absent. The release gate requires identity by
    # input, contract and engine hash plus run metadata, so an artifact that
    # cannot state its own contract hash cannot satisfy it.
    engine_identity_path = work_dir / 'RUN_IDENTITY.json'
    if engine_identity_path.exists():
        try:
            engine_identity = json.loads(engine_identity_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            identity['engine_identity_error'] = f'{type(exc).__name__}: {exc}'
        else:
            for key in ('contract_sha256', 'run_id', 'parameters_sha256', 'seed_sha256',
                        'canonical_coverage_evaluator', 'git_commit', 'git_describe', 'git_dirty'):
                if engine_identity.get(key) is not None:
                    identity[key] = engine_identity[key]
            # Cross-check rather than trust: if the engine resolved a different
            # input or engine hash than the wrapper stamped, the artifact is
            # self-inconsistent and that must be visible, not silently merged.
            for key in ('input_sha256', 'engine_sha256'):
                engine_value = engine_identity.get(key)
                if engine_value is not None and engine_value != identity.get(key):
                    identity.setdefault('identity_mismatches', {})[key] = {
                        'wrapper': identity.get(key), 'engine': engine_value,
                    }
        identity['engine_identity_source'] = str(engine_identity_path)
    else:
        identity['engine_identity_source'] = None
    (case_root / 'UNIVERSAL_RUN_IDENTITY.json').write_text(
        json.dumps(identity, indent=2), encoding='utf-8')

    if audit.exists():
        qrc = subprocess.call([sys.executable, '-u', str(QUALITY_REPORTER), '--audit-json', str(audit), '--case-root', str(case_root)])
        if qrc != 0 and rc == 0:
            rc = qrc
    independent_validation = {
        'enabled': not bool(args.skip_independent_validation),
        'status': 'NOT_RUN',
        'return_code': None,
        'workbook': None,
        'json': None,
        'csv': None,
    }
    validation_workbook = None
    if not diagnostics_only and engine_rc == 0:
        if skeleton_only:
            before_candidates = sorted(case_root.glob('*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx'))
            validation_workbook = before_candidates[0] if before_candidates else None
        else:
            if output.exists():
                validation_workbook = output
            elif hard_valid_artifact(audit):
                candidates = sorted(case_root.glob('*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx'))
                validation_workbook = candidates[0] if candidates else None

    if not diagnostics_only and not skeleton_only and (engine_rc == 0 or hard_valid_artifact(audit)):
        prc = subprocess.call([sys.executable, '-u', str(POLISHER), '--case-root', str(case_root)])
        if prc != 0:
            return prc
        if output.exists():
            validation_workbook = output

    if validation_workbook is not None and not args.skip_independent_validation:
        validation_json = case_root / 'INDEPENDENT_VALIDATION.json'
        validation_csv = case_root / 'INDEPENDENT_VALIDATION.csv'
        vrc = subprocess.call([
            sys.executable, '-u', str(VALIDATOR),
            '--input', str(input_path), '--output', str(validation_workbook),
            '--json-out', str(validation_json), '--csv-out', str(validation_csv),
        ])
        # The validator exits 0 on PASS and 2 when it has evaluated the schedule
        # and found hard-rule violations.  Any other code means it did not
        # complete - a crash, a missing file, an unreadable sheet.  Collapsing
        # every non-zero code to 'FAIL' reported a broken tool as a broken
        # schedule, which is a materially different claim: one blocks release
        # for a real defect, the other for a bug in the checker.  Both still
        # block (an unvalidated schedule must never pass), but they are now
        # distinguishable.
        if vrc == 0:
            validation_status = 'PASS'
        elif vrc == 2:
            validation_status = 'FAIL'
        else:
            validation_status = 'ERROR_VALIDATOR_DID_NOT_COMPLETE'
        independent_validation.update({
            'status': validation_status,
            'return_code': int(vrc),
            'workbook': str(validation_workbook),
            'json': str(validation_json),
            'csv': str(validation_csv),
        })
        if vrc != 0:
            rc = 4
    elif validation_workbook is not None:
        independent_validation.update({'status': 'SKIPPED_BY_EXPLICIT_FLAG', 'workbook': str(validation_workbook)})
    elif not diagnostics_only and engine_rc == 0:
        independent_validation['status'] = 'FAIL_OUTPUT_NOT_FOUND'
        if not args.skip_independent_validation:
            rc = 4

    if not diagnostics_only and not skeleton_only and (engine_rc == 0 or hard_valid_artifact(audit)) and rc != 4:
        pkg_rc = subprocess.call([sys.executable, '-u', str(PACKAGER), '--case-root', str(case_root)])
        if pkg_rc != 0:
            return pkg_rc
    metrics = read_summary_metrics(case_root)
    run_status = {
        'schema_version': 1,
        'release': RELEASE,
        'schedule_id': schedule_id,
        'mode': mode, 'stage': stage,
        'return_code': rc,
        'engine_return_code': engine_rc,
        'hard_valid_artifact': hard_valid_artifact(audit),
        'metrics': metrics,
        'case_root': str(case_root),
        'independent_validation': independent_validation,
    }
    (case_root / 'UNIVERSAL_RUN_STATUS.json').write_text(json.dumps(run_status, indent=2, default=str), encoding='utf-8')
    print(json.dumps(run_status, indent=2, default=str), flush=True)
    return rc

if __name__ == '__main__':
    raise SystemExit(main())
