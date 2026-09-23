#!/usr/bin/env python3
"""Prepare immutable RC9.2.2 production workbooks for independent validation."""
from __future__ import annotations
import argparse,csv,hashlib,json,re,shutil,tempfile,zipfile
from datetime import datetime,timezone
from pathlib import Path

# Fallbacks only. These literals are what the published artifact used to assert
# unconditionally, and they had drifted badly: RELEASE named RC9.1 while the
# engine being published was RC9.2.1, and ENGINE was a hash matching no engine
# in the project - not RC9.1's da21c3ba, not RC9.2.1's 56ec2eef, not the current
# build. Every published workbook, release manifest and production ZIP filename
# therefore asserted a fabricated engine identity, which is precisely what the
# exact-engine-identity release gate exists to prevent.
#
# Legacy literals remain readable for old evidence only.  Production
# preparation below refuses to use them: an unknown identity is not a
# publishable identity.
RELEASE='L6.3.2.7-RC9.2.2-PRODUCTION-HARDENED-RC2'
SOLVER=RELEASE
COMMIT='RC9_2_2_MAX_COVERAGE_RC5'
ENGINE='FALLBACK_ENGINE_IDENTITY_REJECTED'
APPROVAL='PENDING_INDEPENDENT_VALIDATION; SEE SEALED MANIFEST IN THE PRODUCTION PACKAGE'

def run_identity(root):
 '''Identity of the run that produced this case, from its own artifacts.'''
 ident={'release':RELEASE,'solver':SOLVER,'commit':COMMIT,'engine_sha256':ENGINE,
        'contract_sha256':None,'run_id':None,'input_sha256':None,
        'identity_source':'FALLBACK_LITERALS'}
 # Read BOTH sources and fill gaps, rather than stopping at the first. A case
 # produced before the wrapper learned to merge the engine's identity has a
 # UNIVERSAL_RUN_IDENTITY.json without contract_sha256 or run_id, while
 # debug/RUN_IDENTITY.json alongside it carries them. Stopping at the first file
 # would publish those older cases with the contract hash still missing.
 sources=[]
 for name in ('UNIVERSAL_RUN_IDENTITY.json','debug/RUN_IDENTITY.json'):
  p=root/name
  if not p.is_file(): continue
  try: d=json.loads(p.read_text(encoding='utf-8'))
  except (OSError,json.JSONDecodeError): continue
  release=d.get('release') or d.get('version')
  if release and ident['identity_source']=='FALLBACK_LITERALS':
   ident['release']=release; ident['solver']=release
  for src,dst in (('engine_sha256','engine_sha256'),('contract_sha256','contract_sha256'),
                  ('run_id','run_id'),('input_sha256','input_sha256'),('git_commit','commit')):
   if d.get(src) and ident.get(dst) in (None,ENGINE,COMMIT): ident[dst]=d[src]
  sources.append(name)
  if ident['identity_source']=='FALLBACK_LITERALS': ident['identity_source']=name
 if len(sources)>1: ident['identity_source']='+'.join(sources)
 return ident
OUTPUT_STYLE_VERSION='RC9.2.2-OUTPUT-UX-RC1'
ORDER=['Read Me First','Schedule','Break Schedule','FT Wise After Breaks','Coverage Before Breaks','Production Summary','Validation Log','No-Break Exceptions','Break Spacing Audit','Interval Coverage Audit','Overage Audit','Next Sunday Carry-Out Audit','Canonical Contract','Rule Checks','Rest Gap Audit','Language Skill Audit','Language Reserve Summary','Skill Allocation Audit','Whole Week Balance Audit','Employee Quality Audit','Feasibility Certificate','Language Setup','Preference','Instructions','Fixed Shift Requests','Candidate Leaderboard','Target Tradeoff Audit','Feasibility Report','Blank Interval Audit','Shift Demand Fit Audit','Overnight Audit','Cyclic Sunday Audit']
TECH={'Final Schedule','Break Schedule Active','Daily Interval Review','FT Wise Active','FT Wise After Breaks Active','Scheduler Engine','Previous Engine','Balanced Scenario Schedule','Future Use','Implementation Notes','Formula Fix Notes','Review Runs','Balance Change Log','Benchmark Comparison','Dynamic Interval Guide','Constraint Isolation','Day Tail Fit Audit'}

# Presentation palette mirrors the RC9.2.2 input workbook.  This runs after all
# scheduling and validation evidence is serialized, so it cannot alter a solver
# decision, metric, break, or coverage result.
NAVY='1F2A44'; PURPLE='5B3C88'; TEAL='167D7F'; WHITE='FFFFFF'
PALE_BLUE='DCE6F1'; PALE_TEAL='DDEBF7'; PALE_GREEN='E2F0D9'
PALE_YELLOW='FFF4CC'; PALE_ORANGE='FCE4D6'; PALE_RED='FCE4E4'
LIGHT_GRAY='F2F4F7'; DARK='263238'

def _metric_map(ws):
 return {str(ws.cell(r,1).value).strip():ws.cell(r,2).value for r in range(1,ws.max_row+1) if ws.cell(r,1).value not in (None,'')}

def _num(value,default=0):
 try: return float(value)
 except (TypeError,ValueError): return default

def _count_text(value):
 n=_num(value)
 return str(int(n)) if n == int(n) else f'{n:,.2f}'

def _coverage_text(hits,active):
 h=_num(hits); a=_num(active)
 return f'{int(h):,} / {int(a):,}  ({h/a:.1%})' if a else f'{int(h):,}'

def _status_fill(status):
 s=str(status or '').upper()
 if any(x in s for x in ('FAIL','BLOCK','NO-GO')): return PALE_RED
 if any(x in s for x in ('WARN','MONITOR','PENDING','REVIEW')): return PALE_ORANGE
 return PALE_GREEN

def _border():
 from openpyxl.styles import Border,Side
 side=Side(style='thin',color='D9DEE7')
 return Border(left=side,right=side,top=side,bottom=side)

def _header(ws,row=1,start=1,end=None,color=NAVY):
 from openpyxl.styles import Alignment,Font,PatternFill
 end=end or ws.max_column
 for c in range(start,end+1):
  cell=ws.cell(row,c); cell.fill=PatternFill('solid',fgColor=color); cell.font=Font(color=WHITE,bold=True)
  cell.alignment=Alignment(horizontal='center',vertical='center',wrap_text=True); cell.border=_border()
 ws.row_dimensions[row].height=28

def _safe_filter(ws,header_row):
 if ws.max_row>header_row and ws.max_column>1:
  from openpyxl.utils import get_column_letter
  ws.auto_filter.ref=f'A{header_row}:{get_column_letter(ws.max_column)}{ws.max_row}'

def _fit_columns(ws,min_width=10,max_width=36,sample_rows=160):
 from openpyxl.utils import get_column_letter
 for col in range(1,ws.max_column+1):
  width=min_width
  for row in range(1,min(ws.max_row,sample_rows)+1):
   value=ws.cell(row,col).value
   if value is not None: width=max(width,min(max_width,len(str(value))+2))
  ws.column_dimensions[get_column_letter(col)].width=width

def _style_schedule(ws):
 from openpyxl.styles import Alignment,Font,PatternFill
 from openpyxl.utils import get_column_letter
 ws.sheet_view.showGridLines=False; ws.freeze_panes='G3'; ws.sheet_properties.tabColor=TEAL
 if ws.max_row<2: return
 if not any(str(rng)=='A1:'+get_column_letter(ws.max_column)+'1' for rng in ws.merged_cells.ranges):
  ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=ws.max_column)
 title=ws.cell(1,1); title.fill=PatternFill('solid',fgColor=NAVY); title.font=Font(color=WHITE,bold=True,size=16)
 title.alignment=Alignment(horizontal='left',vertical='center'); ws.row_dimensions[1].height=34
 _header(ws,2,1,ws.max_column,TEAL); _safe_filter(ws,2)
 widths={1:8,2:12,3:24,4:22,5:20,6:14}
 for c,w in widths.items(): ws.column_dimensions[get_column_letter(c)].width=w
 for c in range(7,ws.max_column+1): ws.column_dimensions[get_column_letter(c)].width=17
 for r in range(3,ws.max_row+1):
  ws.row_dimensions[r].height=22
  if r%2==0:
   for c in range(1,ws.max_column+1): ws.cell(r,c).fill=PatternFill('solid',fgColor='F8FAFC')
  for c in range(1,ws.max_column+1):
   cell=ws.cell(r,c); cell.border=_border(); cell.alignment=Alignment(vertical='center',horizontal='center' if c in (1,2) or c>=7 else 'left')
   text=str(cell.value or '').strip().upper()
   if c>=7 and text=='OFF': cell.fill=PatternFill('solid',fgColor=LIGHT_GRAY); cell.font=Font(color='6B7280',italic=True,bold=True)
   elif c>=7 and ('LEAVE' in text or text in {'SL','AL','VL'}): cell.fill=PatternFill('solid',fgColor=PALE_RED); cell.font=Font(color='9C0006',bold=True)
   elif c>=7 and text: cell.fill=PatternFill('solid',fgColor=PALE_GREEN); cell.font=Font(color='1F4E2A')

def _style_coverage(ws):
 from openpyxl.styles import Alignment,Font,PatternFill
 ws.sheet_view.showGridLines=False; ws.freeze_panes='A2'; ws.sheet_properties.tabColor=PURPLE
 _header(ws,1,1,ws.max_column,PURPLE); _safe_filter(ws,1); _fit_columns(ws,11,24)
 coverage_col=next((c for c in range(1,ws.max_column+1) if '%' in str(ws.cell(1,c).value or '')),None)
 for r in range(2,ws.max_row+1):
  for c in range(1,ws.max_column+1):
   cell=ws.cell(r,c); cell.border=_border(); cell.alignment=Alignment(horizontal='center',vertical='center')
  if coverage_col:
   cell=ws.cell(r,coverage_col); value=_num(cell.value,-1); cell.number_format='0.0%'
   color=PALE_RED if value<.80 else PALE_ORANGE if value<.90 else PALE_GREEN if value<1 else PALE_TEAL
   cell.fill=PatternFill('solid',fgColor=color); cell.font=Font(bold=True,color=DARK)

def _style_breaks(ws):
 from openpyxl.styles import Alignment,Font,PatternFill
 ws.sheet_view.showGridLines=False; ws.freeze_panes='A2'; ws.sheet_properties.tabColor=TEAL
 _header(ws,1,1,ws.max_column,TEAL); _safe_filter(ws,1); _fit_columns(ws,12,34)
 headers={str(ws.cell(1,c).value or '').strip().lower():c for c in range(1,ws.max_column+1)}
 type_col=headers.get('break type'); status_col=headers.get('status') or headers.get('review status')
 for r in range(2,ws.max_row+1):
  for c in range(1,ws.max_column+1): ws.cell(r,c).border=_border(); ws.cell(r,c).alignment=Alignment(vertical='center')
  if type_col:
   cell=ws.cell(r,type_col); cell.fill=PatternFill('solid',fgColor=PALE_YELLOW if 'lunch' in str(cell.value or '').lower() else PALE_TEAL)
  if status_col:
   cell=ws.cell(r,status_col); cell.fill=PatternFill('solid',fgColor=_status_fill(cell.value)); cell.font=Font(bold=True)

def _style_audit(ws):
 from openpyxl.styles import Alignment,PatternFill
 ws.sheet_view.showGridLines=False; ws.freeze_panes='A2'; ws.sheet_properties.tabColor='A5A5A5'
 if ws.max_row and ws.max_column: _header(ws,1,1,ws.max_column,NAVY); _safe_filter(ws,1); _fit_columns(ws,10,38)
 for r in range(2,min(ws.max_row,5000)+1):
  if r%2==0:
   for c in range(1,ws.max_column+1): ws.cell(r,c).fill=PatternFill('solid',fgColor='F8FAFC')
  for c in range(1,ws.max_column+1): ws.cell(r,c).border=_border(); ws.cell(r,c).alignment=Alignment(vertical='top',wrap_text=False)

def _build_dashboard(wb,ps,role,use):
 from openpyxl.chart import BarChart,Reference
 from openpyxl.chart.series import SeriesLabel
 from openpyxl.styles import Alignment,Font,PatternFill
 if 'Read Me First' in wb.sheetnames: del wb['Read Me First']
 ws=wb.create_sheet('Read Me First',0); m=_metric_map(ps); active=_num(m.get('Active Intervals'))
 final_status=m.get('Final Status') or m.get('Production Quality Gate') or 'NOT REPORTED'; hard=_num(m.get('Hard Validation Failures'))
 if role=='BEST_BEFORE_BREAKS_SCHEDULE': decision='REVIEW ONLY'
 elif hard>0 or 'FAIL' in str(final_status).upper(): decision='BLOCKED'
 elif 'WARN' in str(final_status).upper() or str(m.get('Production Quality Gate','')).upper()=='WARN': decision='GO WITH MONITORING'
 else: decision='GO — VALIDATE SEAL'
 ws.sheet_view.showGridLines=False; ws.sheet_properties.tabColor=TEAL; ws.freeze_panes='A3'
 for col,width in {'A':25,'B':19,'C':19,'D':15,'E':4,'F':24,'G':19,'H':22}.items(): ws.column_dimensions[col].width=width
 ws.merge_cells('A1:H1'); ws['A1']='RC9.2.2  |  Schedule Control Center'; ws['A1'].fill=PatternFill('solid',fgColor=NAVY); ws['A1'].font=Font(color=WHITE,bold=True,size=20); ws['A1'].alignment=Alignment(vertical='center'); ws.row_dimensions[1].height=42
 ws.merge_cells('A2:H2'); ws['A2']=f'{role}  •  {use}  •  {OUTPUT_STYLE_VERSION}'; ws['A2'].fill=PatternFill('solid',fgColor=PURPLE); ws['A2'].font=Font(color=WHITE,italic=True); ws['A2'].alignment=Alignment(vertical='center',wrap_text=True); ws.row_dimensions[2].height=32
 cards=[('A4','B4','A5','B6','Schedule Status',decision,_status_fill(decision)),('C4','D4','C5','D6','Interval Grid',f"{_count_text(m.get('Interval Minutes'))} minutes",PALE_BLUE),('F4','F4','F5','F6','After Target',_coverage_text(m.get('After Target Hits'),active),PALE_GREEN),('G4','H4','G5','H6','After Floor',_coverage_text(m.get('After Floor Hits'),active),PALE_TEAL)]
 for l1,l2,v1,v2,label,value,color in cards:
  ws.merge_cells(f'{l1}:{l2}'); ws.merge_cells(f'{v1}:{v2}'); ws[l1]=label; ws[v1]=value
  ws[l1].fill=PatternFill('solid',fgColor=NAVY); ws[l1].font=Font(color=WHITE,bold=True); ws[l1].alignment=Alignment(horizontal='center')
  ws[v1].fill=PatternFill('solid',fgColor=color); ws[v1].font=Font(color=DARK,bold=True,size=14); ws[v1].alignment=Alignment(horizontal='center',vertical='center',wrap_text=True)
  for row in ws[f'{l1}:{v2}']:
   for cell in row: cell.border=_border()
 ws['A8']='Coverage Attainment'; ws['A8'].font=Font(bold=True,size=14,color=NAVY)
 rows=[('100%',m.get('Before 100%'),m.get('After 100%')),('90%',m.get('Before 90%'),m.get('After 90%')),('80%',m.get('Before 80%'),m.get('After 80%')),('Target',m.get('Before Target Hits'),m.get('After Target Hits')),('Floor',m.get('Before Floor Hits'),m.get('After Floor Hits'))]
 for c,v in enumerate(('Threshold','Before breaks','After breaks','Change'),1): ws.cell(9,c).value=v
 _header(ws,9,1,4,PURPLE)
 for i,(label,before,after) in enumerate(rows,10):
  b=_num(before); a=_num(after); ws.cell(i,1).value=label; ws.cell(i,2).value=b; ws.cell(i,3).value=a; ws.cell(i,4).value=a-b
  for c in range(1,5): ws.cell(i,c).border=_border(); ws.cell(i,c).alignment=Alignment(horizontal='center')
  ws.cell(i,3).fill=PatternFill('solid',fgColor=PALE_GREEN if a>=b else PALE_YELLOW)
 chart=BarChart(); chart.type='col'; chart.style=10; chart.title='Coverage: Before vs After Breaks'; chart.y_axis.title='Intervals'; chart.height=5.1; chart.width=9.6
 chart.add_data(Reference(ws,min_col=2,max_col=3,min_row=9,max_row=14),titles_from_data=True); chart.set_categories(Reference(ws,min_col=1,min_row=10,max_row=14)); chart.legend.position='b'; ws.add_chart(chart,'F8')
 if len(chart.series)>=2:
  chart.series[0].tx=SeriesLabel(v='Before breaks')
  chart.series[1].tx=SeriesLabel(v='After breaks')
 ws['A16']='Risk & Exception Snapshot'; ws['A16'].font=Font(bold=True,size=14,color=NAVY)
 for c,v in enumerate(('Check','Count','Status','Operational note'),1): ws.cell(17,c).value=v
 _header(ws,17,1,4,TEAL)
 risks=[('Hard validation failures',m.get('Hard Validation Failures'),'Must be zero'),('Floor gaps',m.get('Floor Gaps'),'Review concentration and severity'),('Zero-staffed active intervals',m.get('Zero Staffed Active Quarters'),'Must be zero'),('Language gaps',m.get('Language Gaps'),'Must be zero'),('Opening gaps',m.get('Opening Gaps'),'Must be zero'),('No-break exceptions',m.get('No-Break Exception Count'),'Review any approved exception'),('Blank staffed intervals',m.get('Blank Staffed Intervals'),'Must be zero'),('Break concurrency violations',m.get('Break Concurrency Violations'),'Monitor if non-zero')]
 for i,(label,value,note) in enumerate(risks,18):
  n=_num(value); status='PASS' if n==0 else ('WARN' if label in {'Floor gaps','Break concurrency violations'} else 'REVIEW')
  ws.cell(i,1).value=label; ws.cell(i,2).value=n; ws.cell(i,3).value=status; ws.cell(i,4).value=note
  for c in range(1,5): ws.cell(i,c).border=_border(); ws.cell(i,c).alignment=Alignment(vertical='center',wrap_text=True)
  ws.cell(i,3).fill=PatternFill('solid',fgColor=_status_fill(status)); ws.cell(i,3).font=Font(bold=True)
 ws['F17']='Run Configuration'; ws['F17'].font=Font(bold=True,size=14,color=NAVY)
 cfg=[('Roster count',m.get('Roster Count')),('Legal shift count',m.get('Legal Shift Count')),('Target ratio',m.get('Target Ratio')),('Floor ratio',m.get('Floor Ratio')),('After target overage FTE',m.get('After Target Overage FTE Sum')),('After avoidable overage FTE',m.get('After Avoidable Overage FTE Sum')),('Final engine status',final_status),('Production quality gate',m.get('Production Quality Gate'))]
 for i,(label,value) in enumerate(cfg,18):
  ws.cell(i,6).value=label; ws.merge_cells(start_row=i,start_column=7,end_row=i,end_column=8); ws.cell(i,7).value=value
  for c in range(6,9): ws.cell(i,c).border=_border(); ws.cell(i,c).alignment=Alignment(vertical='center',wrap_text=True)
  ws.cell(i,6).fill=PatternFill('solid',fgColor=LIGHT_GRAY); ws.cell(i,6).font=Font(bold=True)
  if 'ratio' in label.lower(): ws.cell(i,7).number_format='0.0%'
 ws.merge_cells('A28:H28'); ws['A28']='How to use this workbook'; ws['A28'].fill=PatternFill('solid',fgColor=NAVY); ws['A28'].font=Font(color=WHITE,bold=True,size=13)
 instructions=[('1','Use Schedule as the operating roster; OFF and leave cells are color-coded.'),('2','Use Break Schedule for break execution; investigate WARN/REVIEW rows before release.'),('3','Review FT Wise After Breaks for interval coverage and color-coded attainment.'),('4','Use Production Summary and audit tabs for full traceability; hidden TECH tabs are retained.'),('5',f"This result uses a {_count_text(m.get('Interval Minutes'))}-minute grid. The engine supports both 30- and 60-minute workbooks.")]
 for i,(step,note) in enumerate(instructions,29):
  ws.cell(i,1).value=step; ws.cell(i,1).fill=PatternFill('solid',fgColor=TEAL); ws.cell(i,1).font=Font(color=WHITE,bold=True); ws.cell(i,1).alignment=Alignment(horizontal='center')
  ws.merge_cells(start_row=i,start_column=2,end_row=i,end_column=8); ws.cell(i,2).value=note; ws.cell(i,2).alignment=Alignment(wrap_text=True,vertical='center'); ws.cell(i,2).fill=PatternFill('solid',fgColor='F8FAFC')
  for c in range(1,9): ws.cell(i,c).border=_border()
 ws.row_dimensions[33].height=34
 return ws

def _apply_output_theme(wb,ps,role,use):
 from openpyxl.styles import Alignment,Font,PatternFill
 dashboard=_build_dashboard(wb,ps,role,use)
 for ws in wb.worksheets:
  if ws is dashboard: continue
  name=ws.title.lower()
  if name in {'schedule','final schedule'}: _style_schedule(ws)
  elif 'coverage' in name or name in {'ft wise after breaks','ft wise active','ft wise after breaks active'}: _style_coverage(ws)
  elif 'break schedule' in name or name=='no-break exceptions': _style_breaks(ws)
  else: _style_audit(ws)
  if name in {'validation log','rule checks','feasibility certificate'}:
   for row in ws.iter_rows(min_row=2):
    for cell in row:
     if str(cell.value or '').upper() in {'PASS','WARN','FAIL','PASS_WITH_QUALITY_WARNINGS'}:
      cell.fill=PatternFill('solid',fgColor=_status_fill(cell.value)); cell.font=Font(bold=True)
 ps.sheet_properties.tabColor=PURPLE; ps.column_dimensions['A'].width=42; ps.column_dimensions['B'].width=96
 for r in range(2,ps.max_row+1): ps.cell(r,2).alignment=Alignment(vertical='top',wrap_text=True)
 return dashboard

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for c in iter(lambda:f.read(1048576),b''): h.update(c)
 return h.hexdigest()
def one(root,pat):
 m=sorted(root.glob(pat))
 if not m: raise FileNotFoundError(f'{pat} in {root}')
 return m[0]
def one_of(root,*patterns):
 for pat in patterns:
  m=sorted(root.glob(pat))
  if m: return m[0]
 raise FileNotFoundError(f'{patterns} in {root}')
def read_csv(p):
 with p.open(newline='',encoding='utf-8') as f: r=list(csv.DictReader(f))
 return r[0] if r else {}
def mkey(m): return tuple(m.get(k) for k in ('after_100','after_90','after_80','after_target','after_floor','hard_floor_gap_count','week_boundary_after_target','week_boundary_after_floor','week_boundary_floor_gap_count','week_boundary_zero_staffed_active_quarters','week_boundary_language_gap_count','week_boundary_opening_gap_count','week_boundary_blank_staffed_quarters','severe_floor_gap_count','max_consecutive_floor_gaps','floor_deficit_sum'))
def roles(pareto):
 ex=pareto.get('exports') or []; rec=next((x for x in ex if x.get('role') in {'RECOMMENDED_FINAL','BEST_FINAL_AFTER_BREAKS'}),{}); rk=mkey(rec.get('metrics') or {}); out=[]
 for x in ex:
  role=x.get('role',''); m=x.get('metrics') or {}
  if role=='BEST_BEFORE_BREAKS': disp='Published as BEST_BEFORE_BREAKS_SCHEDULE (review only)'
  elif role in {'RECOMMENDED_FINAL','BEST_FINAL_AFTER_BREAKS'}: disp='Published as BEST_FINAL_AFTER_BREAKS_SCHEDULE'
  elif mkey(m)==rk: disp='Shared with BEST_FINAL_AFTER_BREAKS_SCHEDULE; duplicate workbook suppressed'
  else: disp='Distinct alternative retained in leaderboard/Pareto/debug evidence only'
  out.append([role,m.get('after_100',''),m.get('after_90',''),m.get('after_80',''),m.get('after_target',''),m.get('after_floor',''),disp])
 return out
def clean_book(src,dst,role,use,pareto,ident):
 from openpyxl import load_workbook
 from openpyxl.styles import Alignment,Font,PatternFill
 from openpyxl.workbook.properties import CalcProperties
 dst.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory() as td:
  stage=Path(td)/dst.name; shutil.copy2(src,stage); wb=load_workbook(stage)
  if 'Prefrence' in wb.sheetnames and 'Preference' not in wb.sheetnames: wb['Prefrence'].title='Preference'
  for ws in wb.worksheets:
   for row in ws.iter_rows():
    for cell in row:
     if isinstance(cell.value,str):
      cell.value=cell.value.replace('Dynamic Schedule - V10 interval-aware optimized output','Universal WFM Production Schedule').replace('V10 Dynamic Interval Pattern MILP optimizer','Universal WFM CP-SAT Scheduler')
      cell.value=re.sub(r'\bPrefrence\b','Preference',cell.value,flags=re.I)
  if 'Production Summary' not in wb.sheetnames:
   ps=wb.create_sheet('Production Summary',0); ps.append(['Metric','Value'])
  ps=wb['Production Summary']; existing={str(ps.cell(r,1).value or '').strip():r for r in range(1,ps.max_row+1)}
  fields={'Artifact Type':role,'Artifact Role':role,'Production Use':use,'Production Release':ident['release'],'Production Approval':APPROVAL,'Output Presentation Version':OUTPUT_STYLE_VERSION,'Solver Version':ident['solver'],'Week-Boundary Patch Commit':ident['commit'],'Engine SHA256':ident['engine_sha256'],'Contract SHA256':ident['contract_sha256'] or 'NOT_RECORDED','Run ID':ident['run_id'] or 'NOT_RECORDED','Identity Source':ident['identity_source'],'Validation Basis':'RC9 is a universal workbook-driven production platform. Artifact verification, hard validity, target/floor quality, and any quality-debt approval are reported separately for each uploaded workbook.','Week-Boundary Protection':'Current Saturday carry-out and next-Sunday active intervals are included in final release gates','Approved Waiver':'None encoded by program/client name. Waivers must come from workbook contract settings or documented human approval after the run.','Known Limitation':'No client-specific release pass is implied. Each uploaded workbook is solved and validated from its own contract; quality-blocked schedules require explicit approval before operational use.'}
  for k,v in fields.items():
   if k in existing: ps.cell(existing[k],2).value=v
   else: ps.append([k,v])
  ps.append([]); ps.append(['CANDIDATE ROLE CONSOLIDATION','After100','After90','After80','After Target','After Floor','Production Disposition'])
  for row in roles(pareto): ps.append(row)
  ps.sheet_view.showGridLines=False; ps.freeze_panes='A2'; ps.column_dimensions['A'].width=38; ps.column_dimensions['B'].width=105; ps.column_dimensions['G'].width=72
  for cell in ps[1]: cell.fill=PatternFill('solid',fgColor='1F4E78'); cell.font=Font(color='FFFFFF',bold=True); cell.alignment=Alignment(horizontal='center')
  _apply_output_theme(wb,ps,role,use)
  by={ws.title:ws for ws in wb.worksheets}; ordered=[]; used=set()
  for name in ORDER:
   if name in by: ordered.append(by[name]); used.add(name)
  ordered += [ws for ws in wb.worksheets if ws.title not in used]; wb._sheets=ordered
  for ws in wb.worksheets:
   ws.sheet_state='hidden' if ws.title in TECH else 'visible'
  wb.active=wb.sheetnames.index('Read Me First')
  if getattr(wb,'calculation',None) is None: wb.calculation=CalcProperties(calcMode='auto')
  wb.calculation.fullCalcOnLoad=True; wb.calculation.forceFullCalc=True; wb.save(dst); wb.close()
 with zipfile.ZipFile(dst) as z:
  bad=z.testzip()
  if bad: raise RuntimeError(bad)
 wb=load_workbook(dst,read_only=True); names=wb.sheetnames; wb.close()
 if not {'Production Summary','Schedule','Canonical Contract'}.issubset(names): raise RuntimeError('Required sheet missing')
 return {'path':str(dst),'size_bytes':dst.stat().st_size,'sha256':sha(dst),'sheet_count':len(names),'xlsx_zip_test':'PASS','reopen_test':'PASS'}
def publish(root):
 root=root.resolve(); summary=read_csv(one(root,'*.l6_3_2_3_summary.csv')); pareto=json.loads(one(root,'*_PARETO_EXPORT_MANIFEST.json').read_text()); cid=Path(summary.get('output','')).name.split('_L6_3_2_3_',1)[0]; prod=root/'production'; prod.mkdir(exist_ok=True); ident=run_identity(root)
 if ident['identity_source']=='FALLBACK_LITERALS' or not all(ident.get(k) for k in ('engine_sha256','contract_sha256','run_id','input_sha256')):
  raise RuntimeError('Complete run identity is required before production artifact preparation')
 before=clean_book(one(root,'*_BEST_BEFORE_BREAKS_SCHEDULE.xlsx'),prod/f'{cid}_L6_3_2_3_BEST_BEFORE_BREAKS_SCHEDULE.xlsx','BEST_BEFORE_BREAKS_SCHEDULE','REVIEW ONLY - strongest legal shift/OFF skeleton before breaks; not operational',pareto,ident)
 final=clean_book(one_of(root,'*_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx','*_RECOMMENDED_FINAL_AFTER_BREAKS_SCHEDULE.xlsx'),prod/f'{cid}_L6_3_2_3_BEST_FINAL_AFTER_BREAKS_SCHEDULE.xlsx','BEST_FINAL_AFTER_BREAKS_SCHEDULE','PREPARED OUTPUT - not operational until the independent validation seal and production package exist',pareto,ident)
 manifest={'release':ident['release'],'identity_source':ident['identity_source'],'contract_sha256':ident['contract_sha256'],'run_id':ident['run_id'],'input_sha256':ident['input_sha256'],'approval_status':'PENDING_INDEPENDENT_VALIDATION','production_ready':False,'generated_utc':datetime.now(timezone.utc).isoformat(),'case':cid,'solver':{'version':ident['solver'],'week_boundary_patch_commit':ident['commit'],'engine_sha256':ident['engine_sha256'],'optimization_logic_changed':True,'change_scope':'RC9.2.2 production hardening: protected-tier champion selection, exact-workbook validation, and fail-closed publication without client/case branching'},'two_artifact_contract':{'BEST_BEFORE_BREAKS_SCHEDULE':before,'BEST_FINAL_AFTER_BREAKS_SCHEDULE':final},'candidate_role_rows':roles(pareto),'source_status':summary.get('status','')}
 mp=prod/'PRODUCTION_ARTIFACT_MANIFEST.json'; mp.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
 print(json.dumps({'status':'PREPARED_PENDING_INDEPENDENT_VALIDATION','case':cid,'manifest':str(mp),'before':before,'final':final},indent=2))
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--case-root',type=Path); ap.add_argument('--prepare-only',action='store_true',help='Prepare polished workbooks without packaging; retained for explicit pipeline readability.'); ap.add_argument('--selfcheck',action='store_true'); a=ap.parse_args()
 if a.selfcheck:
  # Not `assert`: under `python -O` assertions are stripped and the selfcheck
  # would print PASS having verified nothing.
  if 'duplicate workbook suppressed' not in roles({'exports':[{'role':'RECOMMENDED_FINAL','metrics':{'after_100':1}},{'role':'MAX_FLOOR_CANDIDATE','metrics':{'after_100':1}}]})[1][-1]:
   print('PRODUCTION OUTPUT POLISHER SELFCHECK: FAIL (duplicate-role consolidation)'); return 1
  fb=run_identity(Path(tempfile.gettempdir())/'__rc922_no_such_case_root__')
  if fb['identity_source']!='FALLBACK_LITERALS':
   print('PRODUCTION OUTPUT POLISHER SELFCHECK: FAIL (identity fallback not marked)'); return 1
  print('PRODUCTION OUTPUT POLISHER SELFCHECK: PASS'); return 0
 if not a.case_root: raise SystemExit('--case-root required')
 publish(a.case_root); return 0
if __name__=='__main__': raise SystemExit(main())
