#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'qa'/'PHASE_A_CLOSURE_EVIDENCE.json').read_text(encoding='utf-8'))
assert data['status']=='FROZEN_PHASE_A_CHECKPOINT_NOT_DEPLOYED'
by={g['gate']:g for g in data['gates']}
assert by['MIGRATED_FAST70_FRESH_SOLVER']['passed']==70
assert by['THIN_OVERNIGHT_BREAK_RESILIENCE']['no_break_exceptions']==0
assert by['FIXED_FLEXIBLE_AND_HARD_FLOOR']['probe_status'] in {'OPTIMAL','FEASIBLE'}
assert by['FEASIBLE_11H_3OFF_MICRO_T42']['break_status'] in {'OPTIMAL','FEASIBLE'}
assert by['FEASIBLE_DIRECTIONAL_SKILL_MICRO_T44']['language_gap_count']==0
assert by['GDI_HISTORICAL_DIRECTIONAL_SKILL_GUARD']['classification']=='EXPECTED_GUARDED_REJECTION_DIAGNOSTIC'
assert by['11H_SKILL_REDUNDANCY_GUARD']['exception_lower_bound']==12
print(json.dumps({'status':'PASS','release':data['release'],'engine_sha256':data['engine_sha256']},indent=2))
