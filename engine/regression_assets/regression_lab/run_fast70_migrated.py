#!/usr/bin/env python3
"""L6.3.2.3 migrated Fast70 integration lab.

This suite restores the former T01-T70 rule-coverage intent using versioned,
synthetic ParsedInput scenarios. It is NOT the exact historical workbook archive.
Every PASS/WARN case is eligible for a fresh bounded CP-SAT skeleton+break solve
when OR-Tools is installed and --run-solvers is used.
"""
from __future__ import annotations
import argparse, csv, importlib.util, json, sys, time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT=Path(__file__).resolve().parents[1]
ENGINE_PATH=ROOT/'_tools'/'l632_universal_scheduler.py'
CATALOG=Path(__file__).with_name('FAST70_MIGRATION_CATALOG.json')


def load_engine():
    spec=importlib.util.spec_from_file_location('l632_engine', ENGINE_PATH)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base_parsed(e, interval:int=60, long_shift:bool=False):
    ipd=1440//interval
    languages=['English']*8
    associates=[]
    for i,lang in enumerate(languages):
        associates.append(e.Associate(i,i+3,i+1,f'E{i+1}',f'a{i+1}@example.invalid',f'Agent {i+1}','TL',lang))
    if long_shift:
        shifts=[e.Shift(0,'08:00 - 19:00',480,1140,660), e.Shift(1,'12:00 - 23:00',720,1380,660)]
        allowed={660}
    else:
        shifts=[e.Shift(0,'08:00 - 17:00',480,1020,540), e.Shift(1,'12:00 - 21:00',720,1260,540)]
        allowed={540}
    req=[[None]*ipd for _ in range(7)]
    shr=[[0.10]*ipd for _ in range(7)]
    active=[[False]*ipd for _ in range(7)]
    start=8*60//interval; end=21*60//interval
    for d in range(7):
        for i in range(start,min(end,ipd)):
            req[d][i]=2.0; active[d][i]=True
    windows={
        'break_1':{'earliest_q':4,'latest_q':12},
        'lunch':{'earliest_q':12,'latest_q':24},
        'break_2':{'earliest_q':24,'latest_q':32},
    }
    return e.ParsedInput(
        path=Path('MIGRATED_FAST70_SYNTHETIC'), associates=associates, shifts=shifts,
        requirements=req, shrinkage=shr, active=active, language_rules=[],
        language_capabilities={'english':{'english'}}, instructions={},
        instructed_headcount=len(associates), headcount_mismatch_allowed=False,
        headcount_mismatch_source='Disabled', dates=[None]*7, interval_minutes=interval,
        intervals_per_day=ipd, hard_off=True, strict_off=True, separate_off_days=True,
        leave_enabled=True, use_preferences=True, fixed_enabled=False,
        max_different_shifts=3, rest_gap_hours=11.0, opening_guard_enabled=False,
        opening_minimum=1, opening_intervals=1, target_ratio=0.90, floor_ratio=0.80,
        floor_mode='protected', program_name='MIGRATED_FAST70_SYNTHETIC',
        target_priority_confirmed=True, overage_control_enabled=True,
        overage_soft_cap_ratio=1.10, overage_severe_cap_ratio=1.20,
        overage_extreme_cap_ratio=1.40, overage_penalty_weight=40,
        minimum_final_before_target=None, minimum_best_before_target=None,
        quality_benchmark_tolerance=0,
        hard_floor_ratio=None, hard_floor_tolerance=None,
        hard_floor_source='Protected floor only', use_11h_3off=long_shift,
        allowed_shift_durations=allowed, allowed_shift_start_min=None,
        allowed_shift_start_end=None, shift_start_step_minutes=1,
        allowed_shift_start_source='Unrestricted',
        break_segments_q=((1,'Break 1'),(2,'Lunch'),(1,'Break 2')),
        break_window_rules_q=windows, break_edge_margin_q=2, break_min_gap_q=6,
        break_preferred_gap_q=8, break_normal_max_gap_q=10,
        break_window_source='instructions', allow_no_break_exceptions=False,
        max_no_break_exceptions=0, no_break_permission_source='Disabled',
        demand_fit_guard_mode='no', blank_requirement_mode='allow',
        blank_requirement_text='', demand_fit_guard_enabled=False,
        demand_fit_min_active_minutes=180,
        demand_fit_min_active_ratio=0.45, demand_fit_max_blank_minutes=180,
        parser_warnings=[], requirement_sheet='synthetic', shrinkage_sheet='synthetic')


def set_period(p,start_min,end_min,req=2.0,days=range(7)):
    ipd=p.intervals_per_day; step=p.interval_minutes
    p.requirements=[[None]*ipd for _ in range(7)]; p.active=[[False]*ipd for _ in range(7)]
    for d in days:
        mins=list(range(start_min, end_min if end_min>start_min else 1440, step))
        if end_min<=start_min: mins+=list(range(0,end_min,step))
        for minute in mins:
            i=minute//step
            p.requirements[d][i]=float(req); p.active[d][i]=True
    return p


def add_language(e,p,minimum=1,eligible_count=2,start=600,end=1200):
    for i,a in enumerate(p.associates): a.language='French' if i<eligible_count else 'English'
    p.language_rules=[e.LanguageRule('French','French',start,end,minimum,True,{'french'},{'french'})]
    p.language_capabilities={'french':{'french'},'english':{'english'}}
    return p


def build_case(e,row):
    interval=int(row['interval_minutes']); kind=row['builder_kind']
    p=base_parsed(e,interval,long_shift=kind in {'long_shift','long_break_shortage'})
    if kind in {'base30','fixed_valid30','nesting30','capacity_infeasible30','language_evening','overnight30','cyclic30','reopening_valid','shortage_warning30','blank_fixed_shortage30','long_break_shortage','moving_peak30'}:
        p=base_parsed(e,30,long_shift=kind in {'long_break_shortage'})
    if kind=='overnight' or kind=='boundary_low_overnight':
        p.shifts=[e.Shift(0,'18:00 - 03:00',1080,180,540),e.Shift(1,'20:00 - 05:00',1200,300,540)]; set_period(p,18*60,5*60,2)
        for a in p.associates: a.previous_saturday='20:00 - 05:00'
    elif kind=='overnight30':
        p.shifts=[e.Shift(0,'18:00 - 03:00',1080,180,540),e.Shift(1,'20:00 - 05:00',1200,300,540)]; set_period(p,18*60,5*60,2)
        for a in p.associates: a.previous_saturday='20:00 - 05:00'
    elif kind in {'cyclic','cyclic30'}:
        p.shifts=[e.Shift(0,'18:00 - 03:00',1080,180,540),e.Shift(1,'20:00 - 05:00',1200,300,540)]; set_period(p,18*60,5*60,2); p.associates[0].previous_saturday='20:00 - 05:00'
    elif kind=='weekend_only': set_period(p,9*60,20*60,2,days=[0,6])
    elif kind=='closed_day': set_period(p,8*60,21*60,2,days=[0,1,2,4,5,6])
    elif kind=='closed_all_week': set_period(p,0,0,0,days=[])
    elif kind in {'midday_peak','narrow_spike','break_sensitive'}:
        set_period(p,8*60,21*60,1); peak=12*60//p.interval_minutes
        for d in range(7):
            for i in range(peak,min(peak+(2 if kind!='narrow_spike' else 1),p.intervals_per_day)):
                p.requirements[d][i]=6.0
    elif kind in {'two_peaks','fixed_overage'}:
        set_period(p,8*60,21*60,1)
        for d in range(7):
            for minute in (10*60,17*60):
                i=minute//p.interval_minutes
                for j in range(i,min(i+2,p.intervals_per_day)): p.requirements[d][j]=5.0
    elif kind=='sparse' or kind=='blank_guard':
        set_period(p,8*60,10*60,2); step=p.interval_minutes
        for d in range(7):
            for minute in range(16*60,18*60,step):
                i=minute//step; p.requirements[d][i]=2.0; p.active[d][i]=True
        if kind=='blank_guard': p.demand_fit_guard_enabled=True; p.demand_fit_max_blank_minutes=480; p.demand_fit_min_active_ratio=0.20; p.demand_fit_min_active_minutes=120
    elif kind in {'late_tail','friday_late'}:
        days=[5] if kind=='friday_late' else range(7); set_period(p,12*60,2*60,2,days=days); p.shifts=[e.Shift(0,'12:00 - 21:00',720,1260,540),e.Shift(1,'17:00 - 02:00',1020,120,540)]
        for a in p.associates[:4]: a.previous_saturday='17:00 - 02:00'
    elif kind=='opening_valid': p.opening_guard_enabled=True; p.opening_minimum=1; p.opening_intervals=2
    elif kind=='reopening_valid':
        set_period(p,8*60,11*60,2)
        for d in range(7):
            for minute in range(16*60,20*60,p.interval_minutes):
                i=minute//p.interval_minutes; p.requirements[d][i]=2.0; p.active[d][i]=True
        p.opening_guard_enabled=True; p.opening_minimum=1; p.opening_intervals=1
    elif kind=='opening_impossible': p.opening_guard_enabled=True; p.opening_minimum=20; p.opening_intervals=2
    elif kind in {'capacity_infeasible','capacity_infeasible30'}: set_period(p,8*60,21*60,30); p.floor_mode='hard'; p.hard_floor_ratio=p.floor_ratio; p.hard_floor_tolerance=0.0; p.hard_floor_source='Synthetic hard-floor case'
    elif kind=='low_demand': set_period(p,8*60,21*60,0.5)
    elif kind=='alternating':
        set_period(p,8*60,17*60,2,days=[0,2,4,6])
        for d in [1,3,5]:
            for minute in list(range(18*60,24*60,p.interval_minutes))+list(range(0,3*60,p.interval_minutes)):
                i=minute//p.interval_minutes; p.requirements[d][i]=2.0; p.active[d][i]=True
        p.shifts=[e.Shift(0,'08:00 - 17:00',480,1020,540),e.Shift(1,'18:00 - 03:00',1080,180,540)]
    elif kind=='weekday_weekend_night':
        set_period(p,8*60,17*60,2,days=[1,2,3,4,5]); p.shifts=[e.Shift(0,'08:00 - 17:00',480,1020,540),e.Shift(1,'18:00 - 03:00',1080,180,540)]
        for a in p.associates[:4]: a.previous_saturday='18:00 - 03:00'
        for d in [0,6]:
            for minute in list(range(18*60,24*60,p.interval_minutes))+list(range(0,3*60,p.interval_minutes)):
                i=minute//p.interval_minutes; p.requirements[d][i]=2.0; p.active[d][i]=True
    elif kind in {'fixed_valid','fixed_valid30','fixed_overage'}:
        p.fixed_enabled=True; p.associates[0].fixed_schedule[0]=p.shifts[0].label
    elif kind in {'nesting','nesting30','blank_fixed_shortage30'}:
        p.fixed_enabled=True; p.associates[0].nesting_group='N1'; p.associates[1].nesting_group='N1'
        if kind=='blank_fixed_shortage30':
            set_period(p,18*60,3*60,6); p.shifts=[e.Shift(0,'18:00 - 03:00',1080,180,540)]
            for a in p.associates: a.previous_saturday='18:00 - 03:00'
    elif kind=='language_tight': add_language(e,p,2,3)
    elif kind=='language_exact': add_language(e,p,2,2)
    elif kind=='language_no_match': add_language(e,p,2,0)
    elif kind=='language_evening': add_language(e,p,1,3,17*60,23*60)
    elif kind=='leave_language': add_language(e,p,1,3); p.associates[0].preferences[2]='Leave'
    elif kind=='leave_language_gap': add_language(e,p,2,2); p.associates[0].preferences[2]='Leave'; p.associates[1].preferences[2]='Leave'
    elif kind=='hard_off': p.associates[0].preferences[0]='OFF'; p.hard_off=True
    elif kind=='soft_off': p.associates[0].preferences[0]='OFF'; p.hard_off=False
    elif kind=='consecutive_off': p.separate_off_days=False
    elif kind=='separate_off': p.separate_off_days=True
    elif kind=='max_one_shift': p.max_different_shifts=1
    elif kind=='preference': p.associates[0].preferences[0]=p.shifts[0].label
    elif kind=='rest_valid': p.rest_gap_hours=12
    elif kind=='previous_rest': p.associates[0].previous_saturday='20:00 - 05:00'; p.rest_gap_hours=12
    elif kind=='closed_tuesday_late': set_period(p,8*60,21*60,2,days=[0,1,3,4,5,6])
    elif kind=='hc_mismatch': p.instructed_headcount=len(p.associates)+1
    elif kind=='hc_override': p.instructed_headcount=len(p.associates)+1; p.headcount_mismatch_allowed=True; p.headcount_mismatch_source='Synthetic explicit override'
    elif kind=='invalid_target': p.target_ratio=1.2
    elif kind=='invalid_floor': p.floor_ratio=0.95; p.target_ratio=0.90
    elif kind=='invalid_shrinkage': p.shrinkage[0][8*60//p.interval_minutes]=1.0
    elif kind=='unknown_fixed': p.fixed_enabled=True; p.associates[0].fixed_schedule[0]='99:00 - 100:00'
    elif kind=='shortage_warning30': set_period(p,8*60,21*60,10); p.floor_mode='protected'
    elif kind=='long_break_shortage': set_period(p,8*60,23*60,7); p.floor_mode='protected'
    elif kind=='closed_early_shortage': set_period(p,3*60,8*60,12,days=[2]); p.shifts=[e.Shift(0,'08:00 - 17:00',480,1020,540)]; p.floor_mode='hard'; p.hard_floor_ratio=p.floor_ratio; p.hard_floor_tolerance=0.0; p.hard_floor_source='Synthetic hard-floor case'
    elif kind=='moving_peak30':
        set_period(p,8*60,21*60,1)
        for d in range(7):
            start=(10+d)%18
            i=(start*60)//p.interval_minutes
            for j in range(i,min(i+4,p.intervals_per_day)): p.requirements[d][j]=5.0
    return p


def codes(rows): return {str(x.get('code','')) for x in rows}


def evaluation_scope(row):
    category=row['category']; expected=row['expected_outcome']
    if expected=='EXPECTED_CONTRACT_FAIL': return 'CONTRACT_ONLY'
    if category=='input_contract': return 'SHIFT_ONLY'
    if category in {'fixed','nesting','leave','off_pattern','preferences','rest','shift_variety','staff_integrity','capacity'}:
        return 'SHIFT_ONLY'
    return 'FULL_BREAK'


def break_width_tiers(row,args):
    configured=[int(x) for x in str(args.pattern_widths).split(',') if str(x).strip()]
    configured=sorted({max(1,x) for x in configured}) or [60,180,680]
    category=row['category']
    if category in {'language','opening','breaks','shift_pattern'}:
        preferred=[180,680]
    elif category in {'overnight','cyclic_boundary','reference'}:
        preferred=[60,180,680]
    else:
        preferred=[60,180]
    tiers=[x for x in preferred if x in configured]
    if not tiers: tiers=[configured[-1]]
    return tiers


def _is_feasible_status(status):
    return status in {'OPTIMAL', 'FEASIBLE'}


def _compact_break_metrics(metrics):
    if not isinstance(metrics, dict):
        return {}
    keep = {
        'before_target', 'after_target', 'before_floor', 'after_floor',
        'zero_staffed_active_quarters', 'language_gap_count',
        'opening_gap_count', 'hard_floor_gap_count',
        'week_boundary_hard_failure_count', 'no_break_exception_count',
    }
    return {key: metrics.get(key) for key in sorted(keep) if key in metrics}


def _focus_from_exception_evidence(e, parsed, skeleton, diagnostic):
    rows = list((diagnostic.diagnostics or {}).get('selected_exception_rows', []) or [])
    focus = set()
    for row in rows:
        a, d = row.get('associate_index'), row.get('day_index')
        if not isinstance(a, int) or not isinstance(d, int):
            continue
        for fd in range(max(0, d - 1), min(6, d + 1) + 1):
            focus.add((a, fd))
    if hasattr(e, 'critical_exception_cells'):
        try:
            critical, _ = e.critical_exception_cells(parsed, skeleton)
            for a, d in critical:
                for fd in range(max(0, d - 1), min(6, d + 1) + 1):
                    focus.add((a, fd))
        except Exception:
            pass
    if not focus:
        # A bounded repair with an empty focus penalizes all changed cells equally.
        # Keep the candidate neighborhood small without inventing client-specific
        # windows or skill names.
        focus = {(a, d) for a, d, _ in e.scheduled_cells(skeleton)}
    reserve, donor_focus, reserve_rows = ({}, set(), [])
    if hasattr(e, 'language_break_overlap_repair_plan'):
        try:
            reserve, donor_focus, reserve_rows = e.language_break_overlap_repair_plan(parsed, skeleton, rows)
        except Exception:
            reserve, donor_focus, reserve_rows = ({}, set(), [])
    focus.update(donor_focus)
    return rows, focus, reserve, reserve_rows


def _solve_break_widths(row, e, args, parsed, skeleton, attempts, stage):
    final_break = None
    for width in break_width_tiers(row, args):
        br = e.solve_breaks(
            parsed, skeleton, width, False,
            args.time_limit_per_scenario, args.workers, sys.stdout,
            objective_mode='target_priority', random_seed=args.random_seed,
        )
        attempts.append({
            'stage': stage,
            'profile': skeleton.profile,
            'solver_status': skeleton.cp_status,
            'break_status': br.cp_status,
            'break_width': width,
            'break_metrics': _compact_break_metrics(br.metrics),
        })
        final_break = br
        if _is_feasible_status(br.cp_status):
            return br
    return final_break


def _release_path_break_repair(row, e, args, parsed, hard, skeletons, attempts):
    """Mirror the production release path after an ordinary break-search miss.

    The former migrated harness called build_skeleton()+solve_breaks() directly
    and therefore bypassed the RC1.2 minimum-exception diagnostic, zero-exception
    promotion, directional-skill overlap repair, and bounded shift/OFF repair.
    This helper reuses those engine primitives so the regression result reflects
    the actual engine path rather than a reduced harness-only path.
    """
    if not skeletons:
        return None, None
    full_width = max(break_width_tiers(row, args))
    diagnostic_time = max(args.time_limit_per_scenario, min(90.0, args.time_limit_per_scenario * 1.5))
    repair_limits = tuple(sorted({2, 4, 6, int(getattr(args, 'max_repair_changes', 6))}))
    for anchor in skeletons[:3]:
        diagnostic = e.minimum_exception_diagnostic(
            parsed, anchor, full_width, diagnostic_time,
            args.workers, sys.stdout,
        )
        attempts.append({
            'stage': 'minimum_exception_diagnostic',
            'profile': anchor.profile,
            'solver_status': anchor.cp_status,
            'break_status': diagnostic.cp_status,
            'break_width': full_width,
            'exception_lower_bound': (diagnostic.diagnostics or {}).get('exception_lower_bound'),
            'exception_upper_bound': (diagnostic.diagnostics or {}).get('exception_upper_bound'),
            'minimum_exception_proven': bool((diagnostic.diagnostics or {}).get('minimum_exception_proven')),
            'selected_exception_count': len(diagnostic.no_break_cells or set()),
            'break_metrics': _compact_break_metrics(diagnostic.metrics),
        })
        promoted = e.promote_zero_exception_diagnostic_candidate(parsed, anchor, diagnostic)
        if promoted is not None:
            promoted_skeleton, promoted_break = promoted
            attempts.append({
                'stage': 'diagnostic_zero_exception_promotion',
                'profile': promoted_skeleton.profile,
                'solver_status': promoted_skeleton.cp_status,
                'break_status': promoted_break.cp_status,
                'break_width': promoted_break.pattern_width,
                'break_metrics': _compact_break_metrics(promoted_break.metrics),
            })
            return promoted_skeleton, promoted_break

        rows, focus, reserve, reserve_rows = _focus_from_exception_evidence(
            e, parsed, anchor, diagnostic
        )
        for limit in repair_limits:
            profile = e.repair_profile(f'fast70_release_path_repair_{row["id"]}_{limit}')
            repaired = e.build_skeleton(
                parsed, profile, hard,
                args.time_limit_per_scenario, args.workers, sys.stdout,
                anchor=anchor, max_changes=limit, focus_cells=focus,
                language_break_reserve_requirements=reserve,
                random_seed=args.random_seed,
            )
            attempts.append({
                'stage': 'bounded_release_path_repair',
                'profile': repaired.profile,
                'anchor_profile': anchor.profile,
                'max_changes': limit,
                'focus_cell_count': len(focus),
                'reserve_constraint_count': len(reserve),
                'reserve_rows': reserve_rows,
                'source_exception_count': len(rows),
                'solver_status': repaired.cp_status,
                'break_status': 'NOT_RUN',
                'break_width': None,
            })
            if not _is_feasible_status(repaired.cp_status):
                continue
            br = _solve_break_widths(
                row, e, args, parsed, repaired, attempts,
                stage='bounded_release_path_repair_breaks',
            )
            if br is not None and _is_feasible_status(br.cp_status):
                return repaired, br
    return None, None


def evaluate(row,e,args):
    parsed=build_case(e,row)
    feasibility=e.capacity_diagnostics(parsed)
    contract=e.validate_input_contract(parsed,feasibility)
    expected=row['expected_outcome']; cf=codes(contract.get('failures',[])); cw=codes(contract.get('warnings',[]))
    scope=evaluation_scope(row)
    warning_observed=(contract.get('status')=='WARN' or feasibility.get('status')=='WARN' or bool(cw) or bool(feasibility.get('warnings')))
    result={'id':row['id'],'name':row['name'],'expected_outcome':expected,'evaluation_scope':scope,
            'contract_status':contract['status'],'contract_failure_codes':sorted(cf),'contract_warning_codes':sorted(cw),
            'feasibility_status':feasibility['status'],'warning_observed':warning_observed,
            'solver_status':'NOT_RUN','break_status':'NOT_RUN','evidence_class':'MIGRATED_SYNTHETIC_INTEGRATION'}
    if expected=='EXPECTED_CONTRACT_FAIL':
        result['status']='PASS' if contract['status']=='FAIL' else 'FAIL'; return result
    if expected=='EXPECTED_INFEASIBLE' and contract['status']=='FAIL':
        result['status']='PASS'; result['solver_status']='PRE_SOLVER_PROVEN_INFEASIBLE'; return result
    if contract['status']=='FAIL': result['status']='FAIL'; return result
    if not args.run_solvers:
        result['status']='CATALOG_ONLY_PASS'; return result

    hard=e.HardConfig(hard_floor=parsed.floor_mode=='hard')
    profile_names=[
        'target_priority_balanced','break_safe_reserve','floor_protected',
        'coverage_rebalance','before_target_champion','preference_neighborhood',
    ]
    attempts=[]; feasible_skeletons=[]; selected_sk=None; selected_br=None; last_sk=None; last_br=None
    for profile_name in profile_names:
        profile=e.skeleton_profiles([profile_name])[0]
        sk=e.build_skeleton(parsed,profile,hard,args.time_limit_per_scenario,args.workers,sys.stdout,random_seed=args.random_seed)
        last_sk=sk
        attempts.append({
            'stage':'primary_skeleton','profile':profile_name,
            'solver_status':sk.cp_status,'break_status':'NOT_RUN','break_width':None,
        })
        if not _is_feasible_status(sk.cp_status):
            continue
        feasible_skeletons.append(sk)
        if scope!='FULL_BREAK':
            selected_sk=sk
            break
        br=_solve_break_widths(row,e,args,parsed,sk,attempts,stage='primary_break_search')
        last_br=br
        if br is not None and _is_feasible_status(br.cp_status):
            selected_sk,selected_br=sk,br
            break

    if scope=='FULL_BREAK' and selected_br is None and getattr(args,'release_path_repair',False):
        repaired_sk,repaired_br=_release_path_break_repair(
            row,e,args,parsed,hard,feasible_skeletons,attempts
        )
        if repaired_br is not None and _is_feasible_status(repaired_br.cp_status):
            selected_sk,selected_br=repaired_sk,repaired_br

    result['attempts']=attempts
    best_sk=selected_sk or (feasible_skeletons[0] if feasible_skeletons else last_sk)
    result['solver_status']=best_sk.cp_status if best_sk is not None else 'NOT_RUN'
    if selected_br is not None:
        result['break_status']=selected_br.cp_status
        result['metrics']=selected_br.metrics
    elif scope!='FULL_BREAK':
        result['break_status']='NOT_REQUIRED'
    else:
        result['break_status']=last_br.cp_status if last_br is not None else 'NOT_RUN'
        if last_br is not None: result['metrics']=last_br.metrics
    shift_feasible=bool(feasible_skeletons or (selected_sk is not None and _is_feasible_status(selected_sk.cp_status)))
    feasible_break=selected_br is not None and _is_feasible_status(selected_br.cp_status)
    all_shift_infeasible=attempts and all(a.get('solver_status') not in {'OPTIMAL','FEASIBLE'} for a in attempts if a.get('stage') in {'primary_skeleton','bounded_release_path_repair'})
    break_rows=[a for a in attempts if a.get('break_status') not in {None,'NOT_RUN','NOT_REQUIRED'}]
    all_break_infeasible=bool(break_rows) and scope=='FULL_BREAK' and not feasible_break and all(a.get('break_status') in {'INFEASIBLE','MODEL_INVALID','UNKNOWN'} for a in break_rows)

    if expected=='PASS':
        result['status']='PASS' if (shift_feasible and (scope!='FULL_BREAK' or feasible_break)) else 'FAIL'
    elif expected=='EXPECTED_WARNING':
        result['status']='PASS' if warning_observed and shift_feasible else 'FAIL'
    elif expected=='EXPECTED_INFEASIBLE':
        result['status']='PASS' if all_shift_infeasible or all_break_infeasible else 'FAIL'
    else:
        result['status']='FAIL'
    result['evidence_class']='MIGRATED_SYNTHETIC_INTEGRATION_FRESH_CP_SAT_RELEASE_PATH'
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--run-solvers',action='store_true')
    ap.add_argument('--catalog-only',action='store_true')
    ap.add_argument('--start-at',type=int,default=1)
    ap.add_argument('--max-scenarios',type=int,default=70)
    ap.add_argument('--only-ids',default='')
    ap.add_argument('--time-limit-per-scenario',type=float,default=8.0)
    ap.add_argument('--pattern-widths',default='60,180,680')
    ap.add_argument('--workers',type=int,default=1)
    ap.add_argument('--random-seed',type=int,default=0)
    ap.add_argument('--release-path-repair',action=argparse.BooleanOptionalAction,default=True)
    ap.add_argument('--max-repair-changes',type=int,default=6)
    ap.add_argument('--output-dir',type=Path,default=ROOT/'regression_results'/'FAST70_MIGRATED')
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args()
    data=json.loads(CATALOG.read_text(encoding='utf-8'))
    assert len(data)==70 and len({r['id'] for r in data})==70
    required={'closed_day','fixed','nesting','language','overnight','cyclic_boundary','breaks','capacity','input_contract'}
    assert required <= {r['category'] for r in data}
    chosen=data[args.start_at-1:args.start_at-1+args.max_scenarios]
    if args.only_ids:
        allow={x.strip() for x in args.only_ids.split(',') if x.strip()}; chosen=[r for r in data if r['id'] in allow]
    args.output_dir.mkdir(parents=True,exist_ok=True)
    summary_json=args.output_dir/'FAST70_MIGRATED_RESULTS.json'; summary_csv=args.output_dir/'FAST70_MIGRATED_RESULTS.csv'
    existing={}
    if args.resume and summary_json.exists(): existing={r['id']:r for r in json.loads(summary_json.read_text(encoding='utf-8'))}
    e=load_engine(); results=[]
    for idx,row in enumerate(chosen,1):
        if row['id'] in existing and existing[row['id']].get('status')=='PASS':
            result=existing[row['id']]; result['resume_status']='SKIPPED_EXISTING_PASS'
        else:
            started=time.time()
            try: result=evaluate(row,e,args)
            except Exception as exc: result={'id':row['id'],'name':row['name'],'expected_outcome':row['expected_outcome'],'status':'ERROR','error':repr(exc)}
            result['elapsed_sec']=round(time.time()-started,3)
        results.append(result)
        summary_json.write_text(json.dumps(results,indent=2,default=str),encoding='utf-8')
        print(f"[{idx}/{len(chosen)}] {row['id']} {result.get('status')} expected={row['expected_outcome']}")
    fields=sorted({k for r in results for k in r if k!='metrics'})
    with summary_csv.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(results)
    bad=[r for r in results if r.get('status') not in {'PASS','CATALOG_ONLY_PASS'}]
    report={'suite':'MIGRATED_FAST70','exact_historical_archive':False,'evidence_note':'Synthetic migrated integration suite; not the exact historical workbook archive.',
            'selected':len(results),'passed':len(results)-len(bad),'failed':len(bad),'failed_ids':[r['id'] for r in bad],
            'fresh_solver_mode':bool(args.run_solvers),'results_json':str(summary_json),'results_csv':str(summary_csv)}
    (args.output_dir/'FAST70_MIGRATED_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2)); return 1 if bad else 0
if __name__=='__main__': raise SystemExit(main())
