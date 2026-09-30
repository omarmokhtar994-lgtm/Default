#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def run_logged(cmd, cwd, log):
    started=time.time()
    with log.open('w',encoding='utf-8') as f:
        p=subprocess.Popen(cmd,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        assert p.stdout is not None
        for line in p.stdout:
            print(line,end=''); f.write(line)
        rc=p.wait()
    return rc,round(time.time()-started,2)


def first_summary(case_root:Path,case:str):
    path=next(case_root.rglob(f'{case}.l6_3_2_3_summary.csv'))
    return next(csv.DictReader(path.read_text(encoding='utf-8-sig').splitlines()))


def main():
    ap=argparse.ArgumentParser(description='Final Phase A closure revalidation harness')
    ap.add_argument('--output-root',type=Path,default=ROOT/'closure_revalidation_results')
    ap.add_argument('--rerun-diagnostic-guards',action='store_true',help='Also rerun the two expected-rejection historical diagnostics')
    args=ap.parse_args(); args.output_root.mkdir(parents=True,exist_ok=True)
    results=[]

    success_cases={
      'THIN_OVERNIGHT_BREAK_RESILIENCE':['--case','NMG12_BREAK_100','--time-limit','900','--pattern-widths','680','--repair-change-limits','2','--skeleton-profiles','break_safe_reserve,before_target_champion','--disable-no-break-exceptions'],
      'FIXED_FLEXIBLE_AND_HARD_FLOOR':['--case','SAKS_NEW','--time-limit','300','--diagnostics-only','--disable-post-break-repair','--disable-target-lock-recovery','--disable-deterministic-baseline'],
    }
    for name,extra in success_cases.items():
        out=args.output_root/name
        cmd=[sys.executable,'-u',str(ROOT/'RUN_UNIVERSAL_WFM.py'),*extra,'--output-root',str(out),'--case-id',name,'--overwrite']
        rc,elapsed=run_logged(cmd,ROOT,args.output_root/f'{name}.log')
        results.append({'gate':name,'classification':'MANDATORY_PASS','status':'PASS' if rc==0 else 'FAIL','return_code':rc,'elapsed_sec':elapsed})

    fastout=args.output_root/'FEASIBLE_MICROS_T42_T44'
    cmd=[sys.executable,'-u',str(ROOT/'regression_lab'/'run_fast70_migrated.py'),'--run-solvers','--only-ids','T42,T44','--time-limit-per-scenario','45','--pattern-widths','60,180,680','--workers','8','--output-dir',str(fastout)]
    rc,elapsed=run_logged(cmd,ROOT,args.output_root/'FEASIBLE_MICROS_T42_T44.log')
    report=json.loads((fastout/'FAST70_MIGRATED_REPORT.json').read_text(encoding='utf-8')) if (fastout/'FAST70_MIGRATED_REPORT.json').exists() else {}
    results.append({'gate':'FEASIBLE_11H_AND_DIRECTIONAL_SKILL_MICROS','classification':'MANDATORY_PASS','status':'PASS' if rc==0 and report.get('passed')==2 else 'FAIL','return_code':rc,'elapsed_sec':elapsed,'report':report})

    if args.rerun_diagnostic_guards:
        guards={
          'GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD':(['--case','GDI_REAL28','--time-limit','1800','--pattern-widths','180,680','--repair-change-limits','2,4,6','--skeleton-profiles','break_safe_reserve,target_priority_balanced,coverage_rebalance','--disable-no-break-exceptions'], 'FAIL_BREAKS_REQUIRE_EXPLICIT_EXCEPTION_FOR_TESTED_SKELETONS'),
          '11H_SKILL_REDUNDANCY_GUARD':(['--case','UNIVERSAL_30MIN_11H_SYNTHETIC','--time-limit','600','--pattern-widths','180,680','--repair-change-limits','2','--skeleton-profiles','break_safe_reserve','--disable-post-break-repair','--disable-target-lock-recovery','--disable-deterministic-baseline','--disable-no-break-exceptions'], 'FAIL_BREAKS_REQUIRE_EXPLICIT_EXCEPTION_FOR_TESTED_SKELETONS'),
        }
        for name,(extra,expected) in guards.items():
            out=args.output_root/name
            cmd=[sys.executable,'-u',str(ROOT/'RUN_UNIVERSAL_WFM.py'),*extra,'--output-root',str(out),'--case-id',name,'--overwrite']
            rc,elapsed=run_logged(cmd,ROOT,args.output_root/f'{name}.log')
            row=first_summary(out,name)
            ok=rc==2 and row.get('status')==expected
            if name=='GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD':
                ok=ok and int(row.get('operational_no_break_cap','-1'))==0 and int(row.get('best_exception_upper_bound','0'))>0
            else:
                ok=ok and int(row.get('best_exception_lower_bound','-1'))==int(row.get('best_exception_upper_bound','-2'))==12
            results.append({'gate':name,'classification':'EXPECTED_DIAGNOSTIC','status':'PASS' if ok else 'FAIL','return_code':rc,'elapsed_sec':elapsed,'observed':row})
    else:
        evidence=json.loads((ROOT/'qa'/'PHASE_A_CLOSURE_EVIDENCE.json').read_text(encoding='utf-8'))
        by={g['gate']:g for g in evidence['gates']}
        for name in ['GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD','11H_SKILL_REDUNDANCY_GUARD']:
            results.append({'gate':name,'classification':'EXPECTED_DIAGNOSTIC_INCLUDED_EVIDENCE','status':by[name]['status'],'source':'qa/PHASE_A_CLOSURE_EVIDENCE.json'})

    ok=all(str(r['status']).startswith('PASS') for r in results)
    report={'release':'L6.3.2.3-R1.2.0-A-CANONICAL-CONSOLIDATION-FROZEN-CHECKPOINT','status':'PASS' if ok else 'FAIL','results':results}
    (args.output_root/'PHASE_A_CLOSURE_REVALIDATION_REPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2)); return 0 if ok else 2

if __name__=='__main__': raise SystemExit(main())
